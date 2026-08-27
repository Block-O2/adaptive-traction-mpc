#!/usr/bin/env python3
"""Run one registered CEM versus CEM-plus-local-refinement engineering A/B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.cuff_allocator import DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG
from traction_mpc_stage4.hybrid_optimizer import (
    HybridHumanSpaceMPC,
    SmoothTemporalRefinementConfig,
)
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.mpc import INTERACTION_AWARE_MPC_CONFIG, HumanSpaceMPC
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


ROLLOUT_DURATION_S = 32.0


class RecordingCEM(HumanSpaceMPC):
    def __init__(self) -> None:
        super().__init__(INTERACTION_AWARE_MPC_CONFIG)
        self.diagnostic_history: list[dict[str, Any]] = []

    def solve(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        action, diagnostics = super().solve(*args, **kwargs)
        self.diagnostic_history.append(diagnostics)
        return action, diagnostics


class RecordingHybrid(HybridHumanSpaceMPC):
    def __init__(self) -> None:
        super().__init__(INTERACTION_AWARE_MPC_CONFIG)
        self.diagnostic_history: list[dict[str, Any]] = []

    def solve(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        action, diagnostics = super().solve(*args, **kwargs)
        self.diagnostic_history.append(diagnostics)
        return action, diagnostics


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


def _distribution(values: np.ndarray) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
        "maximum": float(np.max(array)),
    }


def _estimator(
    summary: dict[str, Any], time: np.ndarray, phase: np.ndarray
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("geometry", "dynamic"):
        item = summary[f"{name}_identifier"]
        trusted = item["trustworthy_time_s"]
        result[name] = {
            "trusted_wall_time_s": trusted,
            "trusted_reference_phase_s": (
                None
                if trusted is None
                else float(np.interp(float(trusted), time, phase))
            ),
            "accepted_updates": item["accepted_updates"],
            "rejected_updates": item["rejected_updates"],
        }
    result["dynamic_torque_prediction_combined_rmse_nm"] = summary[
        "dynamic_identifier"
    ]["god_view_base_model_torque_prediction_combined_rmse_nm"]
    return result


def _optimizer_metrics(
    history: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, Any]:
    objectives = np.asarray([item["objective"] for item in history], dtype=float)
    global_objectives = np.asarray(
        [item["global_cem_objective"] for item in history], dtype=float
    )
    global_runtime = np.asarray(
        [item["global_stage_runtime_ms"] for item in history], dtype=float
    )
    local_runtime = np.asarray(
        [item["local_stage_runtime_ms"] for item in history], dtype=float
    )
    accepted = np.asarray(
        [item["local_refinement"]["accepted"] for item in history], dtype=bool
    )
    improvements = global_objectives - objectives
    relative = np.divide(
        improvements,
        global_objectives,
        out=np.zeros_like(improvements),
        where=np.isfinite(global_objectives) & (global_objectives != 0.0),
    )
    if np.any(objectives > global_objectives + 1e-10):
        raise RuntimeError("local refinement worsened the selected CEM objective")
    return {
        "solve_count": len(history),
        "objective": _distribution(objectives),
        "global_cem_objective": _distribution(global_objectives),
        "local_refinement": {
            "accepted_call_count": int(np.sum(accepted)),
            "accepted_call_fraction": float(np.mean(accepted)),
            "mean_relative_objective_improvement_all_calls": float(np.mean(relative)),
            "mean_relative_objective_improvement_accepted_calls": (
                float(np.mean(relative[accepted])) if np.any(accepted) else 0.0
            ),
            "maximum_relative_objective_improvement": float(np.max(relative)),
            "candidate_evaluations_per_call": int(
                max(
                    item["local_refinement"]["candidate_evaluations"]
                    for item in history
                )
            ),
        },
        "runtime_ms_per_call": {
            "external_total": {
                "mean": summary["computational_cost"]["mpc_mean_ms"],
                "p95": summary["computational_cost"]["mpc_p95_ms"],
            },
            "instrumented_global_cem": _distribution(global_runtime),
            "instrumented_local_refinement": _distribution(local_runtime),
            "mpc_period_ms": 1000.0 * INTERACTION_AWARE_MPC_CONFIG.prediction_dt_s,
        },
    }


def _row(
    mode: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    history: list[dict[str, Any]],
    surface_model: CylindricalSurfaceLoadModel,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    tracking = np.asarray(trace["tracking_error_deg_god_view"])
    wrench = np.asarray(trace["cuff_wrench_local_god_view"])
    force = np.linalg.norm(wrench[:, :3], axis=1)
    moment = np.linalg.norm(wrench[:, 3:], axis=1)
    surface = np.linalg.norm(wrench @ surface_model.minimum_norm_operator.T, axis=1)
    return {
        "mode": mode,
        "termination": summary["termination_reason"],
        "mechanically_completed_requested_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "reference_completion_time_s": _completion_time(time, phase),
        "final_reference_phase_s": float(phase[-1]),
        "tracking": {
            "combined_rmse_deg": float(np.sqrt(np.mean(tracking**2))),
            "combined_max_abs_error_deg": float(np.max(np.abs(tracking))),
            "per_joint_rmse_deg": np.sqrt(np.mean(tracking**2, axis=0)).tolist(),
            "per_joint_max_abs_error_deg": np.max(np.abs(tracking), axis=0).tolist(),
        },
        "cuff_force": {
            "peak": _peak(force, time, phase),
            "rms_n": float(np.sqrt(np.mean(force**2))),
        },
        "cuff_moment": {
            "peak": _peak(moment, time, phase),
            "rms_nm": float(np.sqrt(np.mean(moment**2))),
        },
        "cylindrical_surface_proxy": {
            "peak": _peak(surface, time, phase),
            "rms_n": float(np.sqrt(np.mean(surface**2))),
            "definition": "||A_dagger*w_cuff||_2",
            "interpretation": (
                "minimum-norm equivalent cylindrical surface-load effort proxy; "
                "not pressure or a comfort metric"
            ),
        },
        "optimizer": _optimizer_metrics(history, summary),
        "robot": summary["robot"],
        "estimator": _estimator(summary, time, phase),
        "confidence_pacing": summary.get("reference_execution"),
        "safety_events": summary["events"],
        "force_gate_n": summary["force_gate_n"],
        "moment_limit_nm": summary["moment_limit_nm"],
    }


def _phase_matched_metrics(
    traces: dict[str, dict[str, np.ndarray]],
    surface_model: CylindricalSurfaceLoadModel,
) -> dict[str, Any]:
    final_phase = min(
        float(np.asarray(trace["reference_phase_time_s"])[-1])
        for trace in traces.values()
    )
    phase_grid = np.linspace(0.0, final_phase, int(round(1000.0 * final_phase)) + 1)
    modes: dict[str, Any] = {}
    for mode, trace in traces.items():
        phase = np.asarray(trace["reference_phase_time_s"], dtype=float)

        def interpolate(values: np.ndarray) -> np.ndarray:
            array = np.asarray(values, dtype=float)
            if array.ndim == 1:
                return np.interp(phase_grid, phase, array)
            return np.column_stack(
                [np.interp(phase_grid, phase, array[:, index]) for index in range(array.shape[1])]
            )

        tracking = interpolate(trace["tracking_error_deg_god_view"])
        wrench = interpolate(trace["cuff_wrench_local_god_view"])
        force = np.linalg.norm(wrench[:, :3], axis=1)
        moment = np.linalg.norm(wrench[:, 3:], axis=1)
        surface = np.linalg.norm(wrench @ surface_model.minimum_norm_operator.T, axis=1)
        robot_torque = interpolate(trace["robot_torque_nm"])
        robot_velocity = np.degrees(interpolate(trace["robot_dq_rad_s"]))
        raw_mask = phase <= final_phase + 1e-9
        raw_tracking = np.asarray(trace["tracking_error_deg_god_view"])[raw_mask]
        raw_wrench = np.asarray(trace["cuff_wrench_local_god_view"])[raw_mask]
        raw_force = np.linalg.norm(raw_wrench[:, :3], axis=1)
        raw_moment = np.linalg.norm(raw_wrench[:, 3:], axis=1)
        raw_surface = np.linalg.norm(
            raw_wrench @ surface_model.minimum_norm_operator.T, axis=1
        )
        raw_robot_torque = np.asarray(trace["robot_torque_nm"])[raw_mask]
        raw_robot_velocity = np.degrees(
            np.asarray(trace["robot_dq_rad_s"])[raw_mask]
        )
        modes[mode] = {
            "tracking_combined_rmse_deg": float(np.sqrt(np.mean(tracking**2))),
            "tracking_combined_max_abs_error_deg": float(
                np.max(np.abs(raw_tracking))
            ),
            "cuff_force_peak_n": float(np.max(raw_force)),
            "cuff_force_rms_n": float(np.sqrt(np.mean(force**2))),
            "cuff_moment_peak_nm": float(np.max(raw_moment)),
            "cuff_moment_rms_nm": float(np.sqrt(np.mean(moment**2))),
            "cylindrical_surface_proxy_peak_n": float(np.max(raw_surface)),
            "cylindrical_surface_proxy_rms_n": float(np.sqrt(np.mean(surface**2))),
            "robot_peak_abs_torque_nm": np.max(
                np.abs(raw_robot_torque), axis=0
            ).tolist(),
            "robot_rms_torque_nm": np.sqrt(np.mean(robot_torque**2, axis=0)).tolist(),
            "robot_peak_abs_velocity_deg_s": np.max(
                np.abs(raw_robot_velocity), axis=0
            ).tolist(),
            "robot_rms_velocity_deg_s": np.sqrt(
                np.mean(robot_velocity**2, axis=0)
            ).tolist(),
        }
    return {
        "common_reference_phase_interval_s": [0.0, final_phase],
        "uniform_phase_grid_step_s": (
            float(phase_grid[1] - phase_grid[0]) if len(phase_grid) > 1 else 0.0
        ),
        "purpose": "descriptive phase-matched reporting; not an acceptance threshold",
        "modes": modes,
    }


def _write_summary(output_dir: Path, comparison: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 hybrid MPC engineering A/B",
        "",
        "One registered engineering A/B. No post-result tuning was performed.",
        "",
        "| mode | completion | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS | objective mean | local accept | MPC mean/p95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["rows"]:
        completion = row["reference_completion_time_s"]
        optimizer = row["optimizer"]
        lines.append(
            f'| {row["mode"]} | '
            f'{"-" if completion is None else f"{completion:.3f} s"} | '
            f'{row["tracking"]["combined_rmse_deg"]:.3f}/'
            f'{row["tracking"]["combined_max_abs_error_deg"]:.3f} deg | '
            f'{row["cuff_force"]["peak"]["value"]:.2f}/'
            f'{row["cuff_force"]["rms_n"]:.2f} N | '
            f'{row["cuff_moment"]["peak"]["value"]:.2f}/'
            f'{row["cuff_moment"]["rms_nm"]:.2f} Nm | '
            f'{row["cylindrical_surface_proxy"]["peak"]["value"]:.2f}/'
            f'{row["cylindrical_surface_proxy"]["rms_n"]:.2f} N | '
            f'{optimizer["objective"]["mean"]:.3f} | '
            f'{optimizer["local_refinement"]["accepted_call_count"]}/'
            f'{optimizer["solve_count"]} | '
            f'{optimizer["runtime_ms_per_call"]["external_total"]["mean"]:.1f}/'
            f'{optimizer["runtime_ms_per_call"]["external_total"]["p95"]:.1f} ms |'
        )
    matched = comparison.get("common_phase_comparison")
    if matched is not None:
        lines.extend(
            [
                "",
                f'Phase-matched descriptive interval: 0-{matched["common_reference_phase_interval_s"][1]:.3f} s.',
                "",
                "| mode | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for mode, item in matched["modes"].items():
            lines.append(
                f'| {mode} | {item["tracking_combined_rmse_deg"]:.3f}/'
                f'{item["tracking_combined_max_abs_error_deg"]:.3f} deg | '
                f'{item["cuff_force_peak_n"]:.2f}/{item["cuff_force_rms_n"]:.2f} N | '
                f'{item["cuff_moment_peak_nm"]:.2f}/{item["cuff_moment_rms_nm"]:.2f} Nm | '
                f'{item["cylindrical_surface_proxy_peak_n"]:.2f}/'
                f'{item["cylindrical_surface_proxy_rms_n"]:.2f} N |'
            )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summarize-existing", action="store_true")
    args = parser.parse_args()
    if args.summarize_existing:
        comparison = json.loads(
            (args.output_dir / "comparison_summary.json").read_text(encoding="utf-8")
        )
        stored_traces: dict[str, dict[str, np.ndarray]] = {}
        for mode in ("existing_cem", "cem_plus_smooth_local_refinement"):
            with np.load(args.output_dir / f"{mode}_trace.npz") as stored:
                stored_traces[mode] = {name: stored[name] for name in stored.files}
        surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
        comparison["common_phase_comparison"] = _phase_matched_metrics(
            stored_traces, surface_model
        )
        (args.output_dir / "comparison_summary.json").write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_summary(args.output_dir, comparison)
        return
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    ideal_case = sensor_realism_cases()[0]
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    controllers: dict[str, RecordingCEM | RecordingHybrid] = {}
    traces: dict[str, dict[str, np.ndarray]] = {}
    rows: list[dict[str, Any]] = []
    for mode, controller_type in (
        ("existing_cem", RecordingCEM),
        ("cem_plus_smooth_local_refinement", RecordingHybrid),
    ):
        def factory(
            controller_type: type[RecordingCEM] | type[RecordingHybrid] = controller_type,
            mode: str = mode,
        ) -> RecordingCEM | RecordingHybrid:
            controller = controller_type()
            controllers[mode] = controller
            return controller

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
            mpc_factory=factory,
        )
        save_sensor_case(args.output_dir, summary, trace)
        traces[mode] = trace
        rows.append(
            _row(
                mode,
                summary,
                trace,
                controllers[mode].diagnostic_history,
                surface_model,
            )
        )

    if rows[0]["force_gate_n"] != rows[1]["force_gate_n"]:
        raise RuntimeError("A/B changed the force safety limit")
    if rows[0]["moment_limit_nm"] != rows[1]["moment_limit_nm"]:
        raise RuntimeError("A/B changed the moment safety limit")
    comparison = {
        "evidence_category": "stage4_hybrid_optimizer_registered_engineering_ab",
        "formal_experiment": False,
        "single_variable": "post_cem_smooth_temporal_local_refinement",
        "shared": {
            "global_cem": "unchanged",
            "mpc_objective": INTERACTION_AWARE_MPC_CONFIG.objective_contract(),
            "allocator": DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.as_dict(),
            "estimator": "validated_integral_minimal_unchanged",
            "confidence_pacing": "split_confidence_execution_unchanged",
            "plant": "validated_rigid_cuff_unchanged",
            "trajectory": "stage4_registered_continuous_high_flexion_23s",
            "true_human": "registered_cold_start_perturbed",
            "measurement_case": "ideal_200hz",
            "rollout_duration_s": ROLLOUT_DURATION_S,
            "safety_limits_changed": False,
        },
        "local_refinement": SmoothTemporalRefinementConfig().as_dict(
            INTERACTION_AWARE_MPC_CONFIG
        ),
        "tracking_corridor_or_tube_added": False,
        "post_result_tuning": False,
        "rows": rows,
        "common_phase_comparison": _phase_matched_metrics(traces, surface_model),
    }
    (args.output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, comparison)


if __name__ == "__main__":
    main()
