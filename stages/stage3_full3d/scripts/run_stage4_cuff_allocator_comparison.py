#!/usr/bin/env python3
"""Compare current and cuff-aware exact-torque sagittal allocators."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.cuff_allocator import (
    REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG,
    CuffAwareSagittalAllocator,
    CurrentForceMinimizingAllocator,
    sagittal_allocation_matrix,
    sagittal_null_vector,
)
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_joint_reference,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


ROLLOUT_DURATION_S = 32.0


def _peak(signal: np.ndarray, time: np.ndarray, phase: np.ndarray) -> dict[str, float]:
    index = int(np.argmax(signal))
    return {
        "value": float(signal[index]),
        "wall_time_s": float(time[index]),
        "reference_phase_s": float(phase[index]),
    }


def _completion_time(time: np.ndarray, phase: np.ndarray) -> float | None:
    selected = np.flatnonzero(phase >= CONTINUOUS_TEACHING_DURATION_S - 1e-9)
    return None if not len(selected) else float(time[selected[0]])


def _allocated_slew(
    wrench_world: np.ndarray, control_dt_s: float, radius_m: float
) -> dict[str, float | int | str]:
    stride = int(round(control_dt_s / 0.001))
    sampled = np.asarray(wrench_world)[::stride]
    delta = np.diff(sampled, axis=0)
    force_step = np.linalg.norm(delta[:, :3], axis=1)
    moment_step = np.linalg.norm(delta[:, 3:], axis=1)
    equivalent_step = np.sqrt(force_step**2 + (moment_step / radius_m) ** 2)
    return {
        "update_count": int(len(delta)),
        "peak_force_step_n": float(np.max(force_step)),
        "rms_force_step_n": float(np.sqrt(np.mean(force_step**2))),
        "peak_moment_step_nm": float(np.max(moment_step)),
        "rms_moment_step_nm": float(np.sqrt(np.mean(moment_step**2))),
        "peak_force_equivalent_step_n": float(np.max(equivalent_step)),
        "rms_force_equivalent_step_n": float(
            np.sqrt(np.mean(equivalent_step**2))
        ),
        "peak_force_equivalent_rate_n_s": float(
            np.max(equivalent_step) / control_dt_s
        ),
        "rms_force_equivalent_rate_n_s": float(
            np.sqrt(np.mean(equivalent_step**2)) / control_dt_s
        ),
        "metric": "sqrt(||delta_F||^2 + ||delta_M/r_cuff||^2)",
    }


def _estimator_metrics(
    summary: dict[str, Any], time: np.ndarray, phase: np.ndarray
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("geometry", "dynamic"):
        identifier = summary[f"{name}_identifier"]
        trusted = identifier["trustworthy_time_s"]
        result[name] = {
            "trusted_wall_time_s": trusted,
            "trusted_reference_phase_s": (
                None
                if trusted is None
                else float(np.interp(float(trusted), time, phase))
            ),
            "accepted_updates": identifier["accepted_updates"],
            "rejected_updates": identifier["rejected_updates"],
        }
    result["dynamic_torque_prediction_combined_rmse_nm"] = summary[
        "dynamic_identifier"
    ]["god_view_base_model_torque_prediction_combined_rmse_nm"]
    return result


def _row(
    mode: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    surface_model: CylindricalSurfaceLoadModel,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    error = np.asarray(trace["tracking_error_deg_god_view"])
    wrench_cuff = np.asarray(trace["cuff_wrench_local_god_view"])
    force_norm = np.linalg.norm(wrench_cuff[:, :3], axis=1)
    moment_norm = np.linalg.norm(wrench_cuff[:, 3:], axis=1)
    patch_force = (
        wrench_cuff @ surface_model.minimum_norm_operator.T
    ).reshape(-1, surface_model.config.patch_count, 3)
    surface_effort = np.linalg.norm(patch_force.reshape(len(time), -1), axis=1)
    maximum_local_patch = np.max(np.linalg.norm(patch_force, axis=2), axis=1)
    residual = np.asarray(trace["allocation_equality_residual_nm"])
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    return {
        "mode": mode,
        "termination": summary["termination_reason"],
        "completed_requested_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "reference_completion_time_s": _completion_time(time, phase),
        "final_reference_phase_s": float(phase[-1]),
        "allocation_equality": {
            "peak_residual_nm": float(np.max(residual)),
            "rms_residual_nm": float(np.sqrt(np.mean(residual**2))),
        },
        "tracking": {
            "combined_rmse_deg": float(np.sqrt(np.mean(error**2))),
            "per_joint_rmse_deg": np.sqrt(np.mean(error**2, axis=0)).tolist(),
            "combined_max_abs_error_deg": float(np.max(np.abs(error))),
            "per_joint_max_abs_error_deg": np.max(np.abs(error), axis=0).tolist(),
        },
        "cuff_force": {
            "peak": _peak(force_norm, time, phase),
            "rms_n": float(np.sqrt(np.mean(force_norm**2))),
        },
        "cuff_moment": {
            "peak": _peak(moment_norm, time, phase),
            "rms_nm": float(np.sqrt(np.mean(moment_norm**2))),
        },
        "cylindrical_surface_load_proxy": {
            "peak_effort_n": float(np.max(surface_effort)),
            "rms_effort_n": float(np.sqrt(np.mean(surface_effort**2))),
            "peak_reference_phase_s": float(phase[int(np.argmax(surface_effort))]),
            "peak_local_patch_force_proxy_n": float(
                np.max(maximum_local_patch)
            ),
            "peak_local_patch_reference_phase_s": float(
                phase[int(np.argmax(maximum_local_patch))]
            ),
            "interpretation": (
                "minimum-norm equivalent cylindrical patch-force proxy; "
                "not pressure or comfort"
            ),
        },
        "wrench_slew": {
            "allocated": _allocated_slew(
                np.asarray(trace["allocated_wrench_world"]),
                HumanMPCConfig().prediction_dt_s,
                surface_model.config.radius_m,
            ),
            "measured_force_rate_peak_n_s": interaction["peak_force_rate_n_s"],
            "measured_force_rate_rms_n_s": interaction["rms_force_rate_n_s"],
            "measured_moment_rate_peak_nm_s": interaction[
                "peak_moment_rate_nm_s"
            ],
            "measured_moment_rate_rms_nm_s": interaction[
                "rms_moment_rate_nm_s"
            ],
        },
        "robot": summary["robot"],
        "estimator": _estimator_metrics(summary, time, phase),
        "safety_events": summary["events"],
        "force_gate_n": summary["force_gate_n"],
        "moment_limit_nm": summary["moment_limit_nm"],
    }


def _interpolate_vector(
    phase: np.ndarray, values: np.ndarray, query: float
) -> list[float]:
    return [
        float(np.interp(query, phase, values[:, index]))
        for index in range(values.shape[1])
    ]


def _representative_phases(
    traces: dict[str, dict[str, np.ndarray]], queries: list[float]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in queries:
        item: dict[str, Any] = {"reference_phase_s": query, "modes": {}}
        for mode, trace in traces.items():
            phase = np.asarray(trace["reference_phase_time_s"])
            sagittal = np.asarray(trace["allocated_sagittal_wrench"])
            torque = np.asarray(trace["desired_human_action_nm"])
            item["modes"][mode] = {
                "tau_h_nm": _interpolate_vector(phase, torque, query),
                "allocated_sagittal_wrench_Fx_Fz_My": _interpolate_vector(
                    phase, sagittal, query
                ),
            }
        rows.append(item)
    return rows


def _fixed_tau_reallocations(
    traces: dict[str, dict[str, np.ndarray]], queries: list[float]
) -> list[dict[str, Any]]:
    """Reallocate the baseline tau and state through both maps offline."""

    trace = traces["current_force_minimizing_allocator"]
    phase = np.asarray(trace["reference_phase_time_s"])
    q = np.radians(np.asarray(trace["human_q_deg_god_view"]))
    torque = np.asarray(trace["desired_human_action_nm"])
    human, _ = registered_cold_start_perturbed_human()
    allocators = {
        "current_force_minimizing_allocator": CurrentForceMinimizingAllocator(),
        "cuff_aware_allocator": CuffAwareSagittalAllocator(),
    }
    rows: list[dict[str, Any]] = []
    for query in queries:
        query_q = np.array(
            [np.interp(query, phase, q[:, index]) for index in range(2)]
        )
        query_tau = np.array(
            [np.interp(query, phase, torque[:, index]) for index in range(2)]
        )
        item: dict[str, Any] = {
            "reference_phase_s": query,
            "fixed_q_rad": query_q.tolist(),
            "fixed_tau_h_nm": query_tau.tolist(),
            "allocations": {},
        }
        for name, allocator in allocators.items():
            allocation = allocator.allocate(query_tau, query_q, human)
            item["allocations"][name] = {
                "sagittal_wrench_Fx_Fz_My": np.asarray(
                    allocation["sagittal_wrench"]
                ).tolist(),
                "resultant_force_n": allocation["force_norm_n"],
                "abs_physical_My_nm": abs(
                    float(np.asarray(allocation["sagittal_wrench"])[2])
                ),
                "surface_effort_proxy_n": allocation[
                    "cylindrical_surface_effort_n"
                ],
                "maximum_local_patch_force_proxy_n": allocation[
                    "maximum_local_patch_force_proxy_n"
                ],
                "equality_residual_nm": allocation["equality_residual_nm"],
            }
        rows.append(item)
    return rows


def _structural_audit() -> dict[str, Any]:
    human, metadata = registered_cold_start_perturbed_human()
    phase = np.linspace(0.0, CONTINUOUS_TEACHING_DURATION_S, 2301)
    q = np.array([continuous_teaching_joint_reference(item)[0] for item in phase])
    matrices = np.array(
        [sagittal_allocation_matrix(item, human) for item in q]
    )
    singular_values = np.linalg.svd(matrices, compute_uv=False)
    null_vectors = np.array([sagittal_null_vector(item, human) for item in q])
    return {
        "registered_human": metadata,
        "B_definition": (
            "[[ -l1*sin(q1)-sc*sin(q1-q2), "
            "l1*cos(q1)+sc*cos(q1-q2), -1 ], "
            "[ sc*sin(q1-q2), -sc*cos(q1-q2), 1 ]]"
        ),
        "wrench_definition": "w_s=[Fx,Fz,physical_My]^T",
        "rank": {
            "minimum_over_trajectory": int(
                min(np.linalg.matrix_rank(item) for item in matrices)
            ),
            "maximum_over_trajectory": int(
                max(np.linalg.matrix_rank(item) for item in matrices)
            ),
            "minimum_singular_value_over_trajectory": float(
                np.min(singular_values[:, -1])
            ),
            "nullity": 1,
        },
        "null_direction": (
            "[cos(q1), sin(q1), sc*sin(q2)]^T; scalar multiplier has N units"
        ),
        "null_moment_change_per_added_force_range_m": [
            float(np.min(null_vectors[:, 2])),
            float(np.max(null_vectors[:, 2])),
        ],
        "current_objective": "min Fx^2+Fz^2 subject to B(q)w_s=tau_h",
        "cuff_aware_objective": (
            "min Fx^2+Fz^2+||A_dagger*T_cuff_world(q)*S(q)*w_s||^2 "
            "subject to B(q)w_s=tau_h"
        ),
        "continuity_term_used": False,
    }


def _write(output_dir: Path, result: dict[str, Any]) -> None:
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 cuff allocator engineering comparison",
        "",
        "The allocator preserves the requested Human generalized torque. `A_dagger w` is not pressure.",
        "",
        "| allocator | complete | equality peak | tracking RMSE / max | force peak / RMS | moment peak / RMS | surface effort peak / RMS | local patch proxy peak |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["rows"]:
        completion = row["reference_completion_time_s"]
        lines.append(
            f'| {row["mode"]} | '
            f'{"-" if completion is None else f"{completion:.3f} s"} | '
            f'{row["allocation_equality"]["peak_residual_nm"]:.3e} Nm | '
            f'{row["tracking"]["combined_rmse_deg"]:.3f} / '
            f'{row["tracking"]["combined_max_abs_error_deg"]:.3f} deg | '
            f'{row["cuff_force"]["peak"]["value"]:.2f} / '
            f'{row["cuff_force"]["rms_n"]:.2f} N | '
            f'{row["cuff_moment"]["peak"]["value"]:.2f} / '
            f'{row["cuff_moment"]["rms_nm"]:.2f} Nm | '
            f'{row["cylindrical_surface_load_proxy"]["peak_effort_n"]:.2f} / '
            f'{row["cylindrical_surface_load_proxy"]["rms_effort_n"]:.2f} N | '
            f'{row["cylindrical_surface_load_proxy"]["peak_local_patch_force_proxy_n"]:.2f} N |'
        )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="recompute reporting from saved rollouts without rerunning",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and not args.summarize_existing:
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")

    allocators = {
        "current_force_minimizing_allocator": CurrentForceMinimizingAllocator(),
        "cuff_aware_allocator": CuffAwareSagittalAllocator(),
    }
    ideal_case = sensor_realism_cases()[0]
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    rows: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    for mode, allocator in allocators.items():
        if args.summarize_existing:
            summary = json.loads((args.output_dir / f"{mode}.json").read_text())
            with np.load(args.output_dir / f"{mode}_trace.npz") as stored:
                trace = {name: stored[name] for name in stored.files}
        else:
            execution = ReferenceExecutionLayer(
                continuous_teaching_reference, confidence_aware=True
            )
            summary, trace = run_sensor_realism_case(
                ideal_case,
                duration_s=ROLLOUT_DURATION_S,
                estimator_architecture="integral_minimal",
                result_case_name=mode,
                reference_fn=continuous_teaching_reference,
                trajectory_label="stage4_registered_continuous_high_flexion_23s",
                trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
                reference_execution=execution,
                cuff_allocator=allocator,
                mpc_factory=lambda allocator=allocator: HumanSpaceMPC(
                    HumanMPCConfig(), cuff_allocator=allocator
                ),
            )
            save_sensor_case(args.output_dir, summary, trace)
        traces[mode] = trace
        rows.append(_row(mode, summary, trace, surface_model))

    baseline_phase = np.asarray(
        traces["current_force_minimizing_allocator"]["reference_phase_time_s"]
    )
    baseline_wrench = np.asarray(
        traces["current_force_minimizing_allocator"]["cuff_wrench_local_god_view"]
    )
    baseline_surface = np.linalg.norm(
        baseline_wrench @ surface_model.minimum_norm_operator.T, axis=1
    )
    baseline_force = np.linalg.norm(baseline_wrench[:, :3], axis=1)
    representative_queries = sorted(
        {
            round(float(baseline_phase[int(np.argmax(baseline_force))]), 3),
            round(float(baseline_phase[int(np.argmax(baseline_surface))]), 3),
            13.0,
        }
    )
    current_tau = np.asarray(
        traces["current_force_minimizing_allocator"]["desired_human_action_nm"]
    )
    cuff_aware_tau = np.asarray(
        traces["cuff_aware_allocator"]["desired_human_action_nm"]
    )
    shared_samples = min(len(current_tau), len(cuff_aware_tau))
    result = {
        "evidence_category": "stage4_cuff_allocator_engineering_ab",
        "formal_experiment": False,
        "single_variable": "sagittal_rigid_cuff_allocator",
        "shared": {
            "true_human": "registered_cold_start_perturbed",
            "trajectory": "stage4_registered_continuous_high_flexion_23s",
            "estimator": "validated_integral_minimal_unchanged",
            "adaptive_mpc": "unchanged_default_HumanMPCConfig",
            "mpc_interaction_weights": {
                "resultant_force_weight": 0.0,
                "cylindrical_surface_effort_weight": 0.0,
                "wrench_slew_weight": 0.0,
            },
            "confidence_pacing": "unchanged",
            "plant": "validated_rigid_cuff_unchanged",
            "safety_limits_changed": False,
        },
        "structural_audit": _structural_audit(),
        "cuff_aware_allocator_config": (
            REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG.as_dict()
        ),
        "rows": rows,
        "representative_high_load_phases": _representative_phases(
            traces, representative_queries
        ),
        "fixed_tau_h_reallocation_at_representative_phases": (
            _fixed_tau_reallocations(traces, representative_queries)
        ),
        "maximum_time_aligned_tau_h_difference_nm": float(
            np.max(
                np.linalg.norm(
                    current_tau[:shared_samples]
                    - cuff_aware_tau[:shared_samples],
                    axis=1,
                )
            )
        ),
    }
    _write(args.output_dir, result)


if __name__ == "__main__":
    main()
