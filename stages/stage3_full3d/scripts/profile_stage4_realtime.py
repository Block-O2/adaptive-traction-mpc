#!/usr/bin/env python3
"""Fixed-seed implementation timing audit for the current Stage-4 MPC.

This is an engineering benchmark, not a controller experiment.  It replays
registered controller inputs and never writes into a scientific result tree.
"""

from __future__ import annotations

import argparse
import cProfile
from dataclasses import replace
import io
import json
from pathlib import Path
import pstats
from time import perf_counter
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, HIP_HEIGHT_M
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel, PlanarCuffGeometry
from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.mpc import HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.reference import continuous_teaching_reference
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant


def _model(trace: dict[str, np.ndarray], index: int) -> BaseParameterHumanModel:
    vector = np.asarray(trace["geometry_estimate"][index], dtype=float)
    axis = vector[5:8].copy()
    axis /= np.linalg.norm(axis)
    plane_x = np.array([1.0, 0.0, 0.0])
    plane_x -= axis * float(axis @ plane_x)
    plane_x /= np.linalg.norm(plane_x)
    plane_z = np.cross(plane_x, axis)
    plane_z /= np.linalg.norm(plane_z)
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=plane_x,
        joint_axis_world=axis,
        plane_z_world=plane_z,
        hip_plane_m=vector[:2].copy(),
        thigh_length_m=float(vector[2]),
        knee_to_cuff_in_cuff_m=vector[3:5].copy(),
    )
    return BaseParameterHumanModel(
        geometry=geometry,
        beta=np.asarray(trace["dynamic_base_estimate"][index], dtype=float).copy(),
    )


def _reference(trace: dict[str, np.ndarray]) -> Callable[[float], CuffPoseReference]:
    time = np.asarray(trace["time_s"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    speed = np.asarray(trace["reference_speed_scale"], dtype=float)
    speed_rate = np.asarray(trace["reference_speed_scale_rate_per_s"], dtype=float)

    def reference(wall_time_s: float) -> CuffPoseReference:
        query = float(wall_time_s)
        phase_now = float(np.interp(query, time, phase))
        speed_now = float(np.interp(query, time, speed))
        speed_rate_now = float(np.interp(query, time, speed_rate))
        base = continuous_teaching_reference(phase_now)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=speed_now * base.dq_rad_s,
            ddq_rad_s2=(
                speed_now**2 * base.ddq_rad_s2
                + speed_rate_now * base.dq_rad_s
            ),
            world_from_cuff=base.world_from_cuff,
        )

    return reference


def _percentiles(values_s: list[float]) -> dict[str, float]:
    values = 1000.0 * np.asarray(values_s, dtype=float)
    return {
        "count": int(len(values)),
        "mean_ms": float(np.mean(values)),
        "median_ms": float(np.median(values)),
        "p95_ms": float(np.percentile(values, 95.0)),
        "max_ms": float(np.max(values)),
    }


def _controller(
    implementation: str, *, record_timing_breakdown: bool = False
) -> HumanSpaceMPC:
    if implementation == "current":
        return HumanSpaceMPC(
            record_timing_breakdown=record_timing_breakdown
        )
    try:
        return HumanSpaceMPC(
            implementation=implementation,
            record_timing_breakdown=record_timing_breakdown,
        )
    except TypeError as error:
        raise RuntimeError(
            f"implementation={implementation!r} is not available in this checkout"
        ) from error


def _replay(
    trace: dict[str, np.ndarray],
    *,
    implementation: str,
    warmup_calls: int,
    measured_calls: int,
    repeats: int,
    profile_calls: int,
) -> tuple[dict[str, Any], str]:
    control_time = np.asarray(trace["control_time_s"], dtype=float)
    control_state = np.asarray(trace["control_estimated_state"], dtype=float)
    trace_time = np.asarray(trace["time_s"], dtype=float)
    reference = _reference(trace)
    stride = int(round(0.02 / CONTROL_DT_S))
    timings: list[float] = []
    actions: list[np.ndarray] = []
    objectives: list[float] = []
    margins: list[float] = []
    for repeat in range(repeats):
        controller = _controller(implementation)
        total_calls = warmup_calls + measured_calls
        for solve_index in range(total_calls):
            control_index = solve_index * stride
            wall_time = float(control_time[control_index])
            trace_index = min(
                int(np.searchsorted(trace_time, wall_time + 0.5e-3)),
                len(trace_time) - 1,
            )
            state = control_state[control_index]
            human = _model(trace, trace_index)
            timed = solve_index >= warmup_calls
            start = perf_counter()
            action, diagnostics = controller.solve(
                state, wall_time, reference, human
            )
            elapsed = perf_counter() - start
            if timed:
                timings.append(elapsed)
                if repeat == 0:
                    actions.append(action.copy())
                    objectives.append(float(diagnostics["objective"]))
                    margins.append(float(diagnostics["minimum_constraint_margin"]))

    profiler = cProfile.Profile()
    controller = _controller(implementation)
    for solve_index in range(warmup_calls + profile_calls):
        control_index = solve_index * stride
        wall_time = float(control_time[control_index])
        trace_index = min(
            int(np.searchsorted(trace_time, wall_time + 0.5e-3)),
            len(trace_time) - 1,
        )
        if solve_index == warmup_calls:
            profiler.enable()
        controller.solve(
            control_state[control_index],
            wall_time,
            reference,
            _model(trace, trace_index),
        )
    profiler.disable()
    section_samples: dict[str, list[float]] = {}
    controller = _controller(implementation, record_timing_breakdown=True)
    for solve_index in range(warmup_calls + measured_calls):
        control_index = solve_index * stride
        wall_time = float(control_time[control_index])
        trace_index = min(
            int(np.searchsorted(trace_time, wall_time + 0.5e-3)),
            len(trace_time) - 1,
        )
        _, diagnostics = controller.solve(
            control_state[control_index],
            wall_time,
            reference,
            _model(trace, trace_index),
        )
        if solve_index >= warmup_calls:
            for key, value_ms in diagnostics["implementation_timing_ms"].items():
                section_samples.setdefault(key, []).append(1.0e-3 * value_ms)
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
        pstats.SortKey.CUMULATIVE
    ).print_stats(200)
    config = _controller(implementation).config
    result = {
        "evidence_category": "engineering_replay_timing_not_scientific",
        "implementation": implementation,
        "warmup_calls_per_repeat": warmup_calls,
        "measured_calls_per_repeat": measured_calls,
        "repeats": repeats,
        "fixed_seed": config.random_seed,
        "scientific_dimensions": {
            "candidate_count": config.candidate_count,
            "cem_iterations": config.cem_iterations,
            "horizon_steps": config.horizon_steps,
            "elite_count": config.elite_count,
        },
        "mpc": _percentiles(timings),
        "mpc_sections": {
            key: _percentiles(values) for key, values in section_samples.items()
        },
        "effective_hz_from_mean": float(1.0 / np.mean(timings)),
        "first_repeat_actions": np.asarray(actions).tolist(),
        "first_repeat_objectives": objectives,
        "first_repeat_constraint_margins": margins,
    }
    section_total = result["mpc_sections"].get("solve_total", {}).get(
        "mean_ms", result["mpc"]["mean_ms"]
    )
    for key, stats in result["mpc_sections"].items():
        stats["percent_of_section_solve_mean"] = float(
            100.0 * stats["mean_ms"] / section_total
        )
    return result, stream.getvalue()


def _full_cycle_replay(
    trace: dict[str, np.ndarray],
    *,
    implementation: str,
    warmup_calls: int,
    measured_calls: int,
    repeats: int,
) -> dict[str, Any]:
    case = {item.name: item for item in sensor_realism_cases()}[
        "noise_bias_drift_200hz"
    ]
    control_time = np.asarray(trace["control_time_s"], dtype=float)
    control_state = np.asarray(trace["control_estimated_state"], dtype=float)
    trace_time = np.asarray(trace["time_s"], dtype=float)
    reference = _reference(trace)
    stride = int(round(0.02 / CONTROL_DT_S))
    component_names = (
        "sensing_preprocessing",
        "state_reconstruction",
        "estimator_trust",
        "mpc",
        "cuff_wrench_allocation",
        "command_output_logging",
        "full_cycle",
    )
    samples: dict[str, list[float]] = {name: [] for name in component_names}
    for _ in range(repeats):
        true_human, _ = registered_cold_start_perturbed_human()
        plant = SensorBoundaryStage4Plant(true_human)
        initial = plant.reset(continuous_teaching_reference(0.0).q_rad)
        layers = [CausalMeasurementLayer(case, initial) for _ in range(3)]
        estimator = OnlineSingleChallengerTrustEstimator(
            layers[0].current,
            continuous_teaching_reference(0.0).q_rad,
            measurement_case=case,
            apply_qualified_model=True,
        )
        pacing = ReferenceExecutionLayer(
            continuous_teaching_reference, confidence_aware=True
        )
        controller = _controller(implementation)
        total_calls = warmup_calls + measured_calls
        for solve_index in range(total_calls):
            timed = solve_index >= warmup_calls
            full_start = perf_counter()
            start = perf_counter()
            measurements = None
            for substep in range(4):
                truth = replace(
                    initial,
                    time_s=(4 * solve_index + substep + 1) * CONTROL_DT_S,
                )
                measurements = [layer.update(truth) for layer in layers]
            sensing = perf_counter() - start
            assert measurements is not None

            start = perf_counter()
            _, diagnostics = estimator.observe_measurement(measurements[0])
            pacing.update_from_estimator(
                measurements[1].arrival_time_s,
                estimator,
                diagnostics["geometry"],
                diagnostics["dynamics"],
            )
            estimator_time = perf_counter() - start

            control_index = solve_index * stride
            wall_time = float(control_time[control_index])
            trace_index = min(
                int(np.searchsorted(trace_time, wall_time + 0.5e-3)),
                len(trace_time) - 1,
            )
            human = _model(trace, trace_index)
            start = perf_counter()
            reconstructed = human.geometry.estimate_state(
                measurements[1].attachment_position_m,
                measurements[1].attachment_rotation_matrix,
                measurements[1].attachment_velocity_m_s,
                measurements[1].attachment_angular_velocity_rad_s,
            )
            state_time = perf_counter() - start

            start = perf_counter()
            action, _ = controller.solve(
                control_state[control_index], wall_time, reference, human
            )
            mpc_time = perf_counter() - start

            start = perf_counter()
            allocation = controller.cuff_allocator.allocate(
                action, reconstructed[:2], human
            )
            allocation_time = perf_counter() - start

            start = perf_counter()
            plant.apply_measured_nominal_cartesian_control(
                measurements[2],
                measurements[2].attachment_position_m,
                measurements[2].attachment_velocity_m_s,
                measurements[2].attachment_rotation_matrix,
                measurements[2].attachment_angular_velocity_rad_s,
                np.asarray(allocation["wrench_world"]),
            )
            _log_record = {
                "time_s": wall_time,
                "state": reconstructed.copy(),
                "action": action.copy(),
                "wrench": np.asarray(allocation["wrench_world"]).copy(),
                "speed": pacing.status(measurements[2].arrival_time_s),
            }
            assert _log_record["state"].shape == (4,)
            output_time = perf_counter() - start
            full_time = perf_counter() - full_start
            if timed:
                for name, value in (
                    ("sensing_preprocessing", sensing),
                    ("state_reconstruction", state_time),
                    ("estimator_trust", estimator_time),
                    ("mpc", mpc_time),
                    ("cuff_wrench_allocation", allocation_time),
                    ("command_output_logging", output_time),
                    ("full_cycle", full_time),
                ):
                    samples[name].append(value)
    result = {name: _percentiles(values) for name, values in samples.items()}
    total_mean = result["full_cycle"]["mean_ms"]
    for name in component_names[:-1]:
        result[name]["percent_of_full_cycle_mean"] = float(
            100.0 * result[name]["mean_ms"] / total_mean
        )
    result["effective_hz_from_mean"] = float(1000.0 / total_mean)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--implementation", choices=("current", "scalar", "batched"), default="current"
    )
    parser.add_argument("--warmup-calls", type=int, default=10)
    parser.add_argument("--measured-calls", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile-calls", type=int, default=10)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    with np.load(args.trace) as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    result, profile = _replay(
        trace,
        implementation=args.implementation,
        warmup_calls=args.warmup_calls,
        measured_calls=args.measured_calls,
        repeats=args.repeats,
        profile_calls=args.profile_calls,
    )
    result["full_cycle"] = _full_cycle_replay(
        trace,
        implementation=args.implementation,
        warmup_calls=args.warmup_calls,
        measured_calls=args.measured_calls,
        repeats=args.repeats,
    )
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "timing.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "cprofile.txt").write_text(profile, encoding="utf-8")
    print(
        json.dumps(
            {
                "mpc": result["mpc"],
                "mpc_hz": result["effective_hz_from_mean"],
                "full_cycle": result["full_cycle"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
