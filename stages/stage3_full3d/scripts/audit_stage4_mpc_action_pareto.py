#!/usr/bin/env python3
"""Replay existing MPC call contexts and persist candidate-level Pareto evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, HIP_HEIGHT_M
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import (
    DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG,
)
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
)
from traction_mpc_stage4.mpc import (
    INTERACTION_AWARE_MPC_CONFIG,
    HumanMPCConfig,
    HumanSpaceMPC,
)
from traction_mpc_stage4.mpc_action_pareto_audit import (
    aggregate_call_summaries,
    summarize_candidate_call,
)
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    continuous_teaching_reference,
)
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


def _estimated_model(trace: dict[str, np.ndarray], trace_index: int) -> BaseParameterHumanModel:
    vector = np.asarray(trace["geometry_estimate"][trace_index], dtype=float)
    axis = vector[5:8].copy()
    axis /= np.linalg.norm(axis)
    prior_x = np.array([1.0, 0.0, 0.0])
    plane_x = prior_x - axis * float(axis @ prior_x)
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
        beta=np.asarray(trace["dynamic_base_estimate"][trace_index], dtype=float).copy(),
    )


def _saved_timewarp_reference(
    trace: dict[str, np.ndarray],
) -> Callable[[float], CuffPoseReference]:
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


def _representative_calls(trace: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    completion = np.flatnonzero(phase >= CONTINUOUS_TEACHING_DURATION_S - 1e-9)
    stop = int(completion[0]) if len(completion) else len(time) - 1
    allocated = np.asarray(trace["allocated_wrench_world"])
    sagittal = np.asarray(trace["allocated_sagittal_wrench"])
    local_measured = np.asarray(trace["cuff_wrench_local_god_view"])
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    surface = np.linalg.norm(
        local_measured[: stop + 1] @ surface_model.minimum_norm_operator.T,
        axis=1,
    )
    source_indices = {
        "allocated_moment_peak": int(np.argmax(np.abs(sagittal[: stop + 1, 2]))),
        "allocated_force_peak": int(
            np.argmax(np.linalg.norm(allocated[: stop + 1, :3], axis=1))
        ),
        "measured_surface_proxy_peak": int(np.argmax(surface)),
        "high_flexion_phase_13s": int(np.argmin(np.abs(phase[: stop + 1] - 13.0))),
    }
    control_time = np.asarray(trace["control_time_s"])
    high_level_stride = int(round(0.02 / CONTROL_DT_S))
    high_level_time = control_time[::high_level_stride]
    high_level_phase = np.interp(high_level_time, time, phase)
    by_call: dict[int, dict[str, Any]] = {}
    for label, source_index in source_indices.items():
        source_phase = float(phase[source_index])
        solve_index = int(np.argmin(np.abs(high_level_phase - source_phase)))
        entry = by_call.setdefault(
            solve_index,
            {
                "solve_index": solve_index,
                "wall_time_s": float(high_level_time[solve_index]),
                "reference_phase_s": float(high_level_phase[solve_index]),
                "labels": [],
            },
        )
        entry["labels"].append(label)
    return [by_call[index] for index in sorted(by_call)]


def _trace_index_after_call(time: np.ndarray, wall_time_s: float) -> int:
    return min(int(np.searchsorted(time, wall_time_s + 0.5e-3)), len(time) - 1)


def _replay(
    trace: dict[str, np.ndarray],
    representatives: list[dict[str, Any]],
    config: HumanMPCConfig,
) -> tuple[HumanSpaceMPC, dict[str, float]]:
    selected = frozenset(item["solve_index"] for item in representatives)
    controller = HumanSpaceMPC(
        config,
        candidate_audit_solve_indices=selected,
    )
    reference = _saved_timewarp_reference(trace)
    control_time = np.asarray(trace["control_time_s"])
    control_state = np.asarray(trace["control_estimated_state"])
    trace_time = np.asarray(trace["time_s"])
    stored_action = np.asarray(trace["desired_human_action_nm"])
    high_level_stride = int(round(config.prediction_dt_s / CONTROL_DT_S))
    maximum_solve = max(selected)
    action_errors: list[float] = []
    for solve_index in range(maximum_solve + 1):
        control_index = solve_index * high_level_stride
        wall_time = float(control_time[control_index])
        trace_index = _trace_index_after_call(trace_time, wall_time)
        model = _estimated_model(trace, trace_index)
        action, _ = controller.solve(
            np.asarray(control_state[control_index]),
            wall_time,
            reference,
            model,
        )
        action_errors.append(float(np.linalg.norm(action - stored_action[trace_index])))
    return controller, {
        "maximum_action_replay_error_nm": float(np.max(action_errors)),
        "rms_action_replay_error_nm": float(
            np.sqrt(np.mean(np.asarray(action_errors) ** 2))
        ),
        "compared_call_count": len(action_errors),
    }


def _write_summary(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 MPC action-level Pareto audit",
        "",
        "Offline deterministic replay of saved MPC call contexts; no plant rerun or tuning.",
        "",
        "`A_dagger w` is a minimum-norm cylindrical surface-load proxy, not pressure.",
        "",
        "| mode | phase | feasible/Pareto | track best | registered best | interaction/base at base best | same selected candidate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, mode_result in result["modes"].items():
        for call in mode_result["calls"]:
            lines.append(
                f'| {mode} | {call["reference_phase_s"]:.3f} s | '
                f'{call["feasible_candidate_count"]}/{call["pareto_candidate_count"]} | '
                f'{call["tracking_best"]["tracking_cost"]:.4f} | '
                f'{call["registered_interaction_best"]["tracking_cost"]:.4f} | '
                f'{100.0 * call["cost_scale"]["registered_interaction_over_base_task_at_base_best"]:.3f}% | '
                f'{call["ranking"]["base_and_registered_select_same_candidate"]} |'
            )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    with np.load(args.trace) as stored:
        trace = {name: stored[name] for name in stored.files}
    representatives = _representative_calls(trace)
    modes: dict[str, Any] = {}
    raw_captures: dict[str, Any] = {}
    for name, config in (
        ("exact_tracking_objective", HumanMPCConfig()),
        ("registered_interaction_objective", INTERACTION_AWARE_MPC_CONFIG),
    ):
        controller, replay = _replay(trace, representatives, config)
        by_index = {
            int(item["solve_index"]): item
            for item in controller.candidate_audit_history
        }
        calls = [
            summarize_candidate_call(
                by_index[item["solve_index"]],
                reference_phase_s=item["reference_phase_s"],
                label="+".join(item["labels"]),
            )
            for item in representatives
        ]
        modes[name] = {
            "config": config.objective_contract(),
            "replay_validation_against_saved_exact_tracking_rollout": replay,
            "aggregate": aggregate_call_summaries(calls),
            "calls": calls,
        }
        raw_captures[name] = controller.candidate_audit_history
    result = {
        "evidence_category": "stage4_mpc_action_level_pareto_audit",
        "formal_experiment": False,
        "source": {
            "trace": str(args.trace),
            "trajectory": "existing_registered_continuous_high_flexion",
            "human": "registered_cold_start_perturbed",
            "saved_state_estimates_and_retained_parameter_models_replayed": True,
            "plant_rerun": False,
            "estimator_rerun": False,
            "fixed_reference_timewarp_replayed": True,
        },
        "frozen_default_allocator": DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.as_dict(),
        "representative_calls": representatives,
        "modes": modes,
        "raw_candidate_captures": raw_captures,
        "scientific_settings_changed": False,
        "cem_changed": False,
        "safety_limits_changed": False,
        "tracking_corridor_or_tube_added": False,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, result)


if __name__ == "__main__":
    main()
