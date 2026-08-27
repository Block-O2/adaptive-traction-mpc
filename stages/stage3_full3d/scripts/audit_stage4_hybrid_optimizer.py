#!/usr/bin/env python3
"""Validate the fixed smooth local-refinement stencil on saved MPC calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, HIP_HEIGHT_M
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel, PlanarCuffGeometry
from traction_mpc_stage4.hybrid_optimizer import SmoothTemporalLocalRefiner
from traction_mpc_stage4.mpc import INTERACTION_AWARE_MPC_CONFIG, HumanSpaceMPC
from traction_mpc_stage4.mpc_local_resolution_audit import evaluate_local_sequence
from traction_mpc_stage4.reference import continuous_teaching_reference


def _estimated_model(
    trace: dict[str, np.ndarray], trace_index: int
) -> BaseParameterHumanModel:
    vector = np.asarray(trace["geometry_estimate"][trace_index], dtype=float)
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


def _metrics(
    controller: HumanSpaceMPC,
    *,
    state: np.ndarray,
    sequence: np.ndarray,
    previous_action: np.ndarray,
    q_ref: np.ndarray,
    dq_ref: np.ndarray,
    human: Any,
) -> dict[str, Any]:
    return evaluate_local_sequence(
        controller,
        state=state,
        sequence=sequence,
        previous_action=previous_action,
        q_ref=q_ref,
        dq_ref=dq_ref,
        human=human,
    )


def _relative(after: float, before: float) -> float:
    return float(after / before - 1.0) if before != 0.0 else 0.0


def _write_summary(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 hybrid MPC offline validation",
        "",
        "Saved-call replay only. The global CEM, MPC objective, allocator, estimator, and safety settings are unchanged.",
        "",
        "| phase | objective | tracking | base task | interaction | force RMS | My RMS | surface RMS | local time | feasible |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for call in result["calls"]:
        delta = call["relative_change"]
        lines.append(
            f'| {call["reference_phase_s"]:.3f} s | '
            f'{100.0 * delta["objective"]:+.3f}% | '
            f'{100.0 * delta["tracking_cost"]:+.3f}% | '
            f'{100.0 * delta["base_task_cost"]:+.3f}% | '
            f'{100.0 * delta["interaction_cost"]:+.3f}% | '
            f'{100.0 * delta["force_rms"]:+.3f}% | '
            f'{100.0 * delta["moment_rms"]:+.3f}% | '
            f'{100.0 * delta["surface_rms"]:+.3f}% | '
            f'{call["local_runtime_ms"]:.2f} ms | '
            f'{call["refinement"]["feasible_candidate_evaluations"]}/'
            f'{call["refinement"]["candidate_evaluations"]} |'
        )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--local-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    with np.load(args.trace) as stored:
        trace = {name: stored[name] for name in stored.files}
    local_audit = json.loads(args.local_audit.read_text(encoding="utf-8"))
    reference = _saved_timewarp_reference(trace)
    trace_time = np.asarray(trace["time_s"])
    control_time = np.asarray(trace["control_time_s"])
    control_state = np.asarray(trace["control_estimated_state"])
    stride = int(round(INTERACTION_AWARE_MPC_CONFIG.prediction_dt_s / CONTROL_DT_S))
    calls: list[dict[str, Any]] = []
    for saved in local_audit["calls"]:
        solve_index = int(saved["solve_index"])
        control_index = solve_index * stride
        wall_time_s = float(control_time[control_index])
        trace_index = min(
            int(np.searchsorted(trace_time, wall_time_s + 0.5e-3)),
            len(trace_time) - 1,
        )
        state = np.asarray(control_state[control_index], dtype=float)
        human = _estimated_model(trace, trace_index)
        previous_action = np.asarray(saved["previous_action_nm"], dtype=float)
        sequence = np.asarray(saved["registered_sequence_nm"], dtype=float)
        controller = HumanSpaceMPC(INTERACTION_AWARE_MPC_CONFIG)
        controller.last_action = previous_action.copy()
        q_ref, dq_ref, _ = controller._reference_arrays(wall_time_s, reference)

        def evaluate(candidate: np.ndarray) -> tuple[float, float, np.ndarray | None]:
            return controller._evaluate_sequence(
                state,
                candidate,
                q_ref,
                dq_ref,
                human,
                previous_action=previous_action,
            )

        baseline_evaluation = evaluate(sequence)
        refiner = SmoothTemporalLocalRefiner(INTERACTION_AWARE_MPC_CONFIG)
        start = perf_counter()
        refined_sequence, refined_evaluation, diagnostics = refiner.refine(
            sequence, baseline_evaluation, evaluate
        )
        local_runtime_ms = 1000.0 * (perf_counter() - start)
        baseline = _metrics(
            controller,
            state=state,
            sequence=sequence,
            previous_action=previous_action,
            q_ref=q_ref,
            dq_ref=dq_ref,
            human=human,
        )
        refined = _metrics(
            controller,
            state=state,
            sequence=refined_sequence,
            previous_action=previous_action,
            q_ref=q_ref,
            dq_ref=dq_ref,
            human=human,
        )
        np.testing.assert_allclose(
            baseline["total_interaction_aware_cost"], baseline_evaluation[0]
        )
        np.testing.assert_allclose(
            refined["total_interaction_aware_cost"], refined_evaluation[0]
        )
        calls.append(
            {
                "solve_index": solve_index,
                "reference_phase_s": float(saved["reference_phase_s"]),
                "labels": saved["labels"],
                "baseline": baseline,
                "refined": refined,
                "refinement": diagnostics,
                "local_runtime_ms": local_runtime_ms,
                "relative_change": {
                    "objective": _relative(
                        refined["total_interaction_aware_cost"],
                        baseline["total_interaction_aware_cost"],
                    ),
                    "tracking_cost": _relative(
                        refined["tracking_cost"], baseline["tracking_cost"]
                    ),
                    "base_task_cost": _relative(
                        refined["base_task_cost"], baseline["base_task_cost"]
                    ),
                    "interaction_cost": _relative(
                        refined["interaction_cost"], baseline["interaction_cost"]
                    ),
                    "force_rms": _relative(
                        refined["resultant_force_n"]["rms"],
                        baseline["resultant_force_n"]["rms"],
                    ),
                    "moment_rms": _relative(
                        refined["abs_sagittal_moment_nm"]["rms"],
                        baseline["abs_sagittal_moment_nm"]["rms"],
                    ),
                    "surface_rms": _relative(
                        refined["cylindrical_surface_proxy_n"]["rms"],
                        baseline["cylindrical_surface_proxy_n"]["rms"],
                    ),
                },
            }
        )
    result = {
        "evidence_category": "stage4_hybrid_optimizer_offline_saved_call_validation",
        "formal_experiment": False,
        "source": {
            "trace": str(args.trace),
            "local_resolution_audit": str(args.local_audit),
            "plant_rerun": False,
            "estimator_rerun": False,
        },
        "single_variable": "post_cem_smooth_temporal_local_refinement",
        "global_cem_changed": False,
        "mpc_objective": INTERACTION_AWARE_MPC_CONFIG.objective_contract(),
        "frozen_allocator": DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.as_dict(),
        "local_refinement": SmoothTemporalLocalRefiner(
            INTERACTION_AWARE_MPC_CONFIG
        ).config.as_dict(INTERACTION_AWARE_MPC_CONFIG),
        "calls": calls,
        "controller_weights_changed": False,
        "estimator_changed": False,
        "confidence_pacing_changed": False,
        "plant_changed": False,
        "trajectory_changed": False,
        "safety_limits_changed": False,
        "tracking_corridor_or_tube_added": False,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, result)


if __name__ == "__main__":
    main()
