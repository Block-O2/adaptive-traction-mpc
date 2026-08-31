"""Pre-rollout F_cmd(alpha) audit using exact fixed-clock replay states."""

from __future__ import annotations

from typing import Any

import numpy as np

from .closed_loop_force_pacing import (
    ClosedLoopForcePacingConfig,
    FixedClockForceCurveAuditor,
)
from .high_rom_dynamic_pilot import HighROMPilotTrajectory, compact_run_metrics
from .high_rom_human_v2 import HIGH_ROM_HUMAN_V2
from .measurement import MeasurementCase
from .mpc import HumanSpaceMPC
from .online_trust import OnlineSingleChallengerTrustEstimator
from .sensor_realism import run_sensor_realism_case


def run_fixed_clock_force_curve_audit(
    measurement_case: MeasurementCase,
    trajectory: HighROMPilotTrajectory,
    *,
    gate_time_s: float,
    config: ClosedLoopForcePacingConfig = ClosedLoopForcePacingConfig(),
) -> tuple[dict[str, Any], dict[str, np.ndarray], FixedClockForceCurveAuditor]:
    audit_start = max(0.0, float(gate_time_s) - 1.20)
    auditor = FixedClockForceCurveAuditor(
        trajectory,
        audit_start_s=audit_start,
        audit_stop_s=float(gate_time_s),
        audit_period_s=0.10,
        config=config,
    )

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=measurement_case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN_V2,
        )

    summary, trace = run_sensor_realism_case(
        measurement_case,
        duration_s=23.0,
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__fixed_clock_force_alpha_audit",
        true_human_override=HIGH_ROM_HUMAN_V2,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_v2",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        reference_execution=auditor,
        reference_completion_phase_s=23.0,
        mpc_factory=lambda: HumanSpaceMPC(),
        estimator_factory=estimator_factory,
    )
    metrics = compact_run_metrics(
        summary,
        trace,
        controller_id="fixed_mpc_force_alpha_audit_no_pacing",
        trajectory=trajectory,
    )
    metrics["diagnostic_compute"] = summary["computational_cost"]
    metrics["force_curve_audit"] = summary["reference_execution"]
    return metrics, trace, auditor


def _rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    def average_rank(values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=float)
        order = np.argsort(raw, kind="mergesort")
        ranked = np.empty(len(raw), dtype=float)
        start = 0
        while start < len(raw):
            stop = start + 1
            while stop < len(raw) and raw[order[stop]] == raw[order[start]]:
                stop += 1
            ranked[order[start:stop]] = 0.5 * (start + stop - 1)
            start = stop
        return ranked

    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    if np.ptp(y_array) <= 1e-12:
        return 1.0
    x_rank = average_rank(x_array)
    y_rank = average_rank(y_array)
    return float(np.corrcoef(x_rank, y_rank)[0, 1])


def analyze_force_curves(
    runs: list[tuple[str, float, dict[str, np.ndarray], FixedClockForceCurveAuditor]],
    *,
    preserved_same_action_max_error_n: float,
) -> dict[str, Any]:
    all_records: list[dict[str, Any]] = []
    maximum_underprediction = 0.0
    for trajectory_name, gate_time, trace, auditor in runs:
        command_time = np.asarray(trace["commanded_force_time_s"], dtype=float)
        command_force = np.asarray(
            trace["commanded_translational_force_norm_n"], dtype=float
        )
        for record in auditor.records:
            time_s = float(record["wall_time_s"])
            alpha = np.asarray(record["alpha"], dtype=float)
            predicted = np.asarray(record["peak_force_n"], dtype=float)
            future = (
                (command_time >= time_s - 1e-12)
                & (command_time <= time_s + 0.30 + 1e-12)
            )
            actual_peak = (
                float(np.max(command_force[future])) if np.any(future) else None
            )
            underprediction = (
                max(0.0, actual_peak - float(predicted[-1]))
                if actual_peak is not None
                else 0.0
            )
            maximum_underprediction = max(maximum_underprediction, underprediction)
            difference = np.diff(predicted)
            slope = difference / np.diff(alpha)
            all_records.append(
                {
                    "trajectory": trajectory_name,
                    "gate_time_s": gate_time,
                    "wall_time_s": time_s,
                    "lead_to_gate_s": float(gate_time - time_s),
                    "estimated_state": record["estimated_state"],
                    "tracking_error_deg": record["tracking_error_deg"],
                    "selected_first_action_nm": record["selected_first_action_nm"],
                    "alpha": record["alpha"],
                    "peak_force_n": record["peak_force_n"],
                    "peak_offset_s": record["peak_offset_s"],
                    "alpha_half_to_one_force_change_n": float(
                        predicted[-1] - predicted[0]
                    ),
                    "nondecreasing_step_fraction": float(
                        np.mean(difference >= -1e-9)
                    ),
                    "maximum_downward_step_n": float(
                        max(0.0, -np.min(difference))
                    ),
                    "spearman_rank_correlation": _rank_correlation(alpha, predicted),
                    "maximum_adjacent_slope_change_n_per_alpha": float(
                        np.max(np.abs(np.diff(slope)))
                    ),
                    "predicted_alpha_one_peak_n": float(predicted[-1]),
                    "actual_next_0p3s_peak_n": actual_peak,
                    "positive_underprediction_n": underprediction,
                    "curve_evaluation_latency_ms": record[
                        "evaluation_latency_ms"
                    ],
                }
            )

    common_reserve = float(
        np.ceil(max(maximum_underprediction, preserved_same_action_max_error_n) - 1e-12)
    )
    monotonic_records = []
    for record in all_records:
        alpha = np.asarray(record["alpha"], dtype=float)
        robust = np.asarray(record["peak_force_n"], dtype=float) + common_reserve
        feasible = robust <= 200.0 + 1e-9
        feasible_indices = np.flatnonzero(feasible)
        if len(feasible_indices):
            last = int(feasible_indices[-1])
            alpha_safe = float(alpha[last])
            if last < len(alpha) - 1 and robust[last + 1] > 200.0:
                fraction = (200.0 - robust[last]) / (
                    robust[last + 1] - robust[last]
                )
                alpha_safe += float(fraction * (alpha[last + 1] - alpha[last]))
        else:
            alpha_safe = None
        contiguous = bool(
            not len(feasible_indices)
            or np.array_equal(feasible_indices, np.arange(feasible_indices[-1] + 1))
        )
        required_slowdown = (
            max(0.0, 1.0 - alpha_safe) if alpha_safe is not None else None
        )
        record["robust"] = {
            "common_reserve_n": common_reserve,
            "alpha_one_force_n": float(robust[-1]),
            "alpha_min_force_n": float(robust[0]),
            "maximum_safe_alpha_grid_interpolated": alpha_safe,
            "feasible_set_contiguous_from_alpha_min": contiguous,
            "required_slowdown_time_at_1_per_s": required_slowdown,
            "lead_sufficient_for_rate_limit": bool(
                alpha_safe is not None
                and record["lead_to_gate_s"] >= required_slowdown + 0.02
            ),
        }
        force_span = float(
            np.ptp(np.asarray(record["peak_force_n"], dtype=float))
        )
        effectively_flat = force_span <= 1.0
        monotonic_records.append(
            contiguous
            and (
                effectively_flat
                or (
                    record["alpha_half_to_one_force_change_n"] >= -1.0
                    and record["nondecreasing_step_fraction"] >= 0.98
                )
            )
        )
        record["effectively_force_insensitive_over_alpha_domain"] = (
            effectively_flat
        )

    earliest_actionable: dict[str, Any] = {}
    for trajectory_name in sorted({item["trajectory"] for item in all_records}):
        candidates = [
            item for item in all_records
            if item["trajectory"] == trajectory_name
            and item["robust"]["maximum_safe_alpha_grid_interpolated"] is not None
            and item["robust"]["maximum_safe_alpha_grid_interpolated"] < 1.0 - 1e-9
        ]
        earliest_actionable[trajectory_name] = (
            min(candidates, key=lambda item: item["wall_time_s"])
            if candidates
            else None
        )

    early_enough = all(
        item is not None and item["robust"]["lead_sufficient_for_rate_limit"]
        for item in earliest_actionable.values()
    )
    alpha_min_feasible_near_gate = all(
        any(
            item["robust"]["maximum_safe_alpha_grid_interpolated"] is not None
            for item in all_records
            if item["trajectory"] == trajectory_name
            and item["lead_to_gate_s"] <= 0.30 + 1e-12
        )
        for trajectory_name in earliest_actionable
    )
    return {
        "schema_version": "high_rom_final_selected_action_force_alpha_audit_v1",
        "predictor": {
            "horizon_s": 0.30,
            "low_level_substep_s": 0.005,
            "uses_current_estimated_q_dq": True,
            "uses_current_tracking_error": True,
            "uses_future_time_warped_reference": True,
            "uses_final_selected_mpc_sequence": True,
            "uses_seed_sequence": False,
            "includes_rigid_cuff_feedforward": True,
            "includes_exact_cartesian_feedback_and_component_clip": True,
            "additional_mpc_solves_per_alpha": 0,
        },
        "residual_bound": {
            "maximum_observed_positive_0p3s_peak_underprediction_n": maximum_underprediction,
            "preserved_same_final_action_max_error_n": preserved_same_action_max_error_n,
            "common_reserve_n": common_reserve,
            "trajectory_specific_margin": False,
        },
        "audit_criteria": {
            "effectively_flat_curve_range_n": 1.0,
            "maximum_allowed_net_reverse_change_n": 1.0,
            "minimum_nondecreasing_step_fraction": 0.98,
            "spearman_is_reported_but_not_used_for_flat_tied_curves": True,
            "rationale": "1 N equals two force-noise standard deviations in the frozen measurement case; flat curves are treated as monotonic but not speed-controllable",
        },
        "records": all_records,
        "earliest_actionable": earliest_actionable,
        "decision": {
            "all_curves_sufficiently_monotonic": bool(all(monotonic_records)),
            "both_paths_have_rate_limit_lead": bool(early_enough),
            "alpha_minimum_feasible_within_0p3s_of_gate": bool(
                alpha_min_feasible_near_gate
            ),
            "step_1_passed": bool(
                all(monotonic_records)
                and early_enough
                and alpha_min_feasible_near_gate
            ),
        },
    }
