"""Read-only lead-time audit of preserved High-ROM fixed-clock evidence.

This script does not execute the controller.  It combines the preserved
corrected-pilot gate metrics with the previously saved 100 ms diagnostic
records of the final selected CEM action.  Fields that were not persisted are
reported as unavailable rather than reconstructed from future information.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = (
    REPOSITORY_ROOT
    / "stages/stage4_adaptive_control/results/high_rom_feasibility"
)
CORRECTED_PILOT = (
    RESULTS_DIR
    / "post_jacobian_corrected_pilot/high_rom_dynamic_pilot_corrected.json"
)
FORCE_ALPHA_AUDIT = (
    RESULTS_DIR / "receding_horizon_force_pacing/f_cmd_alpha_audit.json"
)
OUTPUT_JSON = RESULTS_DIR / "action_switch_predictability_audit.json"
OUTPUT_PLOT = RESULTS_DIR / "action_switch_predictability_timeline.png"

TRAJECTORIES = {
    "hip_dominant_100_60": (100.0, 60.0),
    "aggressive_both_120_120": (120.0, 120.0),
}
LEAD_TIMES_S = (0.10, 0.20, 0.30, 0.50)
INITIAL_Q_DEG = np.array([5.0, 10.0], dtype=float)
OUTBOUND_START_S = 1.0
TARGET_REACHED_S = 13.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reference(endpoint_deg: tuple[float, float], time_s: float) -> tuple[np.ndarray, ...]:
    """Frozen outbound quintic reference used by the corrected pilot."""

    q0 = INITIAL_Q_DEG
    target = np.asarray(endpoint_deg, dtype=float)
    if time_s <= OUTBOUND_START_S:
        return q0.copy(), np.zeros(2), np.zeros(2)
    duration = TARGET_REACHED_S - OUTBOUND_START_S
    x = float(np.clip((time_s - OUTBOUND_START_S) / duration, 0.0, 1.0))
    progress = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
    velocity = 30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4
    acceleration = 60.0 * x - 180.0 * x**2 + 120.0 * x**3
    delta = target - q0
    return (
        q0 + delta * progress,
        delta * velocity / duration,
        delta * acceleration / duration**2,
    )


def _round_list(values: np.ndarray, digits: int = 6) -> list[float]:
    return [round(float(value), digits) for value in values]


def _run_by_trajectory(corrected: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [
        run
        for run in corrected["runs"]
        if run["trajectory"] == name and run["controller"] == "fixed_mpc_prior_only"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one corrected Fixed MPC run for {name}")
    return matches[0]


def _timeline_record(
    record: dict[str, Any], endpoint_deg: tuple[float, float], previous_action: np.ndarray | None
) -> dict[str, Any]:
    q_ref, dq_ref, ddq_ref = _reference(endpoint_deg, float(record["wall_time_s"]))
    state = np.asarray(record["estimated_state"], dtype=float)
    action = np.asarray(record["selected_first_action_nm"], dtype=float)
    action_delta = None if previous_action is None else float(np.linalg.norm(action - previous_action))
    predicted = float(record["predicted_alpha_one_peak_n"])
    return {
        "wall_time_s": round(float(record["wall_time_s"]), 6),
        "lead_to_gate_s": round(float(record["lead_to_gate_s"]), 6),
        "estimated_q_deg": _round_list(np.degrees(state[:2])),
        "estimated_dq_deg_s": _round_list(np.degrees(state[2:])),
        "q_tracking_error_deg": _round_list(np.asarray(record["tracking_error_deg"])),
        "q_tracking_error_norm_deg": round(
            float(np.linalg.norm(record["tracking_error_deg"])), 6
        ),
        "dq_tracking_error_deg_s": _round_list(dq_ref - np.degrees(state[2:])),
        "dq_tracking_error_norm_deg_s": round(
            float(np.linalg.norm(dq_ref - np.degrees(state[2:]))), 6
        ),
        "reference_q_deg": _round_list(q_ref),
        "reference_dq_deg_s": _round_list(dq_ref),
        "reference_ddq_deg_s2": _round_list(ddq_ref),
        "reference_ddq_norm_deg_s2": round(float(np.linalg.norm(ddq_ref)), 6),
        "cem_winner_first_action_nm": _round_list(action),
        "cem_winner_first_action_norm_nm": round(float(np.linalg.norm(action)), 6),
        "winner_first_action_change_from_previous_100ms_record_nm": (
            None if action_delta is None else round(action_delta, 6)
        ),
        "predicted_selected_sequence_force_peak_n": round(predicted, 6),
        "predicted_selected_sequence_force_margin_n": round(200.0 - predicted, 6),
        "actual_next_0p3s_peak_n_outcome_only": round(
            float(record["actual_next_0p3s_peak_n"]), 6
        ),
        "direct_causal_200n_warning": bool(predicted >= 200.0),
    }


def _nearest(records: list[dict[str, Any]], lead_s: float) -> dict[str, Any]:
    return min(records, key=lambda item: abs(float(item["lead_to_gate_s"]) - lead_s))


def _plot(timelines: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(11.0, 8.2), sharex="col")
    titles = {
        "hip_dominant_100_60": "100 deg / 60 deg",
        "aggressive_both_120_120": "120 deg / 120 deg",
    }
    for column, name in enumerate(TRAJECTORIES):
        records = timelines[name]["records"]
        lead = np.array([item["lead_to_gate_s"] for item in records])
        predicted = np.array(
            [item["predicted_selected_sequence_force_peak_n"] for item in records]
        )
        future = np.array([item["actual_next_0p3s_peak_n_outcome_only"] for item in records])
        action_norm = np.array([item["cem_winner_first_action_norm_nm"] for item in records])
        action_change = np.array(
            [
                np.nan
                if item["winner_first_action_change_from_previous_100ms_record_nm"] is None
                else item["winner_first_action_change_from_previous_100ms_record_nm"]
                for item in records
            ]
        )
        q_error = np.array([item["q_tracking_error_norm_deg"] for item in records])
        dq_error = np.array([item["dq_tracking_error_norm_deg_s"] for item in records])

        axes[0, column].plot(lead, predicted, "o-", label="causal selected-sequence prediction")
        axes[0, column].plot(lead, future, "s--", label="next-0.3 s outcome (not predictor)")
        axes[0, column].axhline(200.0, color="crimson", linestyle=":", label="200 N gate")
        axes[0, column].set_title(titles[name])
        axes[0, column].set_ylabel("force (N)")
        axes[0, column].grid(alpha=0.25)

        axes[1, column].plot(lead, action_norm, "o-", label="winner first-action norm")
        axes[1, column].plot(lead, action_change, "s--", label="change from prior saved record")
        axes[1, column].set_ylabel("torque metric (Nm)")
        axes[1, column].grid(alpha=0.25)

        axes[2, column].plot(lead, q_error, "o-", label="q error norm (deg)")
        axes[2, column].plot(lead, dq_error, "s--", label="dq error norm (deg/s)")
        axes[2, column].set_ylabel("tracking error")
        axes[2, column].set_xlabel("time before force gate (s)")
        axes[2, column].grid(alpha=0.25)
        for row in range(3):
            axes[row, column].invert_xaxis()
            axes[row, column].legend(fontsize=7, loc="best")

    fig.suptitle(
        "High-ROM pre-gate evidence (preserved 100 ms records; 20 ms CEM trace unavailable)",
        fontsize=11,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.965))
    fig.savefig(OUTPUT_PLOT, dpi=150)
    plt.close(fig)


def main() -> None:
    corrected = json.loads(CORRECTED_PILOT.read_text(encoding="utf-8"))
    force_audit = json.loads(FORCE_ALPHA_AUDIT.read_text(encoding="utf-8"))

    timelines: dict[str, Any] = {}
    force_decomposition: dict[str, Any] = {}
    lead_time_audit: dict[str, Any] = {}

    for name, endpoint in TRAJECTORIES.items():
        source_records = sorted(
            [item for item in force_audit["records"] if item["trajectory"] == name],
            key=lambda item: float(item["wall_time_s"]),
        )
        previous: np.ndarray | None = None
        records: list[dict[str, Any]] = []
        for source in source_records:
            records.append(_timeline_record(source, endpoint, previous))
            previous = np.asarray(source["selected_first_action_nm"], dtype=float)

        run = _run_by_trajectory(corrected, name)
        gate_force = float(run["commanded_force_gate"]["peak_attempt_n"])
        timelines[name] = {
            "endpoint_deg": list(endpoint),
            "gate_time_s": float(run["completed_duration_s"]),
            "available_period_s": 0.1,
            "available_record_count": len(records),
            "records": records,
        }
        force_decomposition[name] = {
            "final_low_level_translational_command_attempt_n": gate_force,
            "gate_margin_n": 200.0 - gate_force,
            "rigid_cuff_allocator_feedforward_contribution": {
                "status": "MISSING",
                "reason": "not persisted in corrected fixed-clock trace or 100 ms diagnostic records",
            },
            "cartesian_position_feedback_contribution": {
                "status": "MISSING",
                "reason": "not persisted as a separate vector or norm",
            },
            "cartesian_velocity_feedback_contribution": {
                "status": "MISSING",
                "reason": "not persisted as a separate vector or norm",
            },
            "decomposition_identity_verifiable": False,
            "note": "The preserved total gate attempt is exact; component attribution cannot be reconstructed without the missing per-cycle vectors and current allocation state.",
        }

        lead_rows = []
        for requested_lead in LEAD_TIMES_S:
            selected = _nearest(records, requested_lead)
            lead_rows.append(
                {
                    "requested_lead_s": requested_lead,
                    "available_record_lead_s": selected["lead_to_gate_s"],
                    "causal_inputs_at_t": {
                        key: selected[key]
                        for key in (
                            "q_tracking_error_norm_deg",
                            "dq_tracking_error_norm_deg_s",
                            "reference_ddq_norm_deg_s2",
                            "cem_winner_first_action_norm_nm",
                            "winner_first_action_change_from_previous_100ms_record_nm",
                            "predicted_selected_sequence_force_peak_n",
                            "predicted_selected_sequence_force_margin_n",
                        )
                    },
                    "direct_200n_rule_warns": selected["direct_causal_200n_warning"],
                    "known_later_gate_event_outcome_only": True,
                }
            )
        lead_time_audit[name] = lead_rows

    training_records = timelines["hip_dominant_100_60"]["records"]
    held_out_records = timelines["aggressive_both_120_120"]["records"]
    train_underprediction = max(
        float(item["positive_underprediction_n"])
        for item in force_audit["records"]
        if item["trajectory"] == "hip_dominant_100_60"
    )
    train_reserve = float(math.ceil(train_underprediction))

    def warning_summary(records: list[dict[str, Any]], reserve_n: float = 0.0) -> dict[str, Any]:
        warnings = [
            item
            for item in records
            if item["predicted_selected_sequence_force_peak_n"] + reserve_n >= 200.0
        ]
        return {
            "warning_record_count": len(warnings),
            "record_count": len(records),
            "earliest_warning_lead_s": (
                None if not warnings else max(item["lead_to_gate_s"] for item in warnings)
            ),
            "latest_pre_gate_record_lead_s": min(item["lead_to_gate_s"] for item in records),
        }

    payload = {
        "schema_version": "high_rom_action_switch_predictability_audit_v1",
        "evidence_category": "diagnostic_read_only_preserved_evidence",
        "scope": {
            "new_controller_rollouts_run": False,
            "controller_or_scientific_parameters_changed": False,
            "measurement_seed": 44104,
            "trajectories": list(TRAJECTORIES),
        },
        "source_evidence": {
            "corrected_fixed_clock_pilot": {
                "path": str(CORRECTED_PILOT.relative_to(REPOSITORY_ROOT)),
                "sha256": _sha256(CORRECTED_PILOT),
            },
            "preserved_final_selected_action_diagnostic": {
                "path": str(FORCE_ALPHA_AUDIT.relative_to(REPOSITORY_ROOT)),
                "sha256": _sha256(FORCE_ALPHA_AUDIT),
            },
        },
        "sampling_limit": {
            "requested_cycle_period_s": 0.02,
            "finest_preserved_pre_gate_diagnostic_period_s": 0.1,
            "full_20ms_timeline_available": False,
            "consequence": "Sub-100 ms onset, per-cycle CEM internals, and exact warning time cannot be recovered from preserved evidence.",
        },
        "field_availability": {
            "final_low_level_command_force": "PARTIAL: exact gate attempt and 100 ms selected-sequence horizon peaks; no per-20 ms executed series",
            "allocator_feedforward_contribution": "MISSING",
            "cartesian_position_feedback_contribution": "MISSING",
            "cartesian_velocity_feedback_contribution": "MISSING",
            "q_tracking_error": "PRESENT at 100 ms diagnostic states",
            "dq_tracking_error": "DERIVED CAUSALLY from saved estimated dq and frozen reference at 100 ms states",
            "reference_q_dq_ddq": "DERIVED CAUSALLY from frozen quintic reference and saved wall time",
            "cem_winner_action": "PARTIAL: first action only at 100 ms diagnostic states",
            "predicted_winner_force_margin": "PRESENT at 100 ms diagnostic states",
            "cem_best_cost": "MISSING",
            "elite_cost_spread_or_variance": "MISSING",
            "winner_change": "PARTIAL: first-action change over 100 ms, not 20 ms",
            "candidate_rejection_statistics": "MISSING per cycle; aggregate fixed runs recorded zero solver failures",
        },
        "force_spike_decomposition": force_decomposition,
        "timelines": timelines,
        "lead_time_audit": lead_time_audit,
        "held_out_evaluation": {
            "training_trajectory": "hip_dominant_100_60",
            "held_out_trajectory": "aggressive_both_120_120",
            "physically_interpretable_rule": "warn when the final-selected-sequence predicted translational command peak is at least 200 N",
            "rule_fitted": False,
            "training_result": warning_summary(training_records),
            "held_out_result": warning_summary(held_out_records),
            "residual_reserve_sensitivity": {
                "reserve_calibrated_on_training_trajectory_n": train_reserve,
                "held_out_result": warning_summary(held_out_records, train_reserve),
                "interpretation": "The reserve warns across most of the gate-selected 1.2 s window, but no unaffected negative window was preserved, so specificity and useful localization cannot be established. It is a conservative alarm, not validated pacing predictability.",
            },
            "why_no_small_regression": "Only one positive gate event per trajectory and no 20 ms negative-control window were preserved; fitting would be in-sample event-window leakage rather than held-out evidence.",
        },
        "warning_time": {
            "direct_predictor_observed": "100/60 first crosses only on the gate record; 120/120 remains below 200 N at the final saved record 0.09 s before the gate",
            "maximum_supported_common_warning_s": "less than 0.10 s; exact 20 ms onset is unavailable",
            "minimum_useful_for_existing_rate_limit_s": {
                "ten_percent_speed_reduction": 0.1,
                "full_reduction_from_alpha_1_to_0p5": 0.5,
                "basis": "preserved common alpha slowdown limit of 1.0 per second",
            },
            "comparison": "The supported warning is shorter than even a 10 percent smooth speed reduction and far shorter than reaching alpha=0.5.",
        },
        "decision": {
            "classification": "TOO-LATE / CONTROLLER-INTERNAL",
            "pacing_development_should_continue": False,
            "observations": [
                "Selected-sequence force margin does not shrink monotonically before either gate.",
                "Tracking error, reference acceleration, and saved winner-action norm do not provide a common monotonic precursor.",
                "For 100/60 the saved winner first-action norm jumps from 20.24 to 58.05 Nm on the gate record, while predicted force jumps from 113.51 to 212.81 N.",
                "For 120/120 the last saved pre-gate prediction is 98.24 N at 0.09 s lead; the gate action and CEM internals were not persisted.",
            ],
            "next_controller_side_questions": [
                "Make final low-level translational command force a feasibility constraint for the exact final selected MPC action path.",
                "Instrument whether a force-safe CEM candidate exists and define an explicit HOLD/safe fallback when none exists instead of applying an over-limit fallback.",
                "Persist 20 ms winner sequence, best/elite costs, candidate rejection counts, and force-component vectors to localize action-switch discontinuity before redesign.",
            ],
        },
    }

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _plot(timelines)


if __name__ == "__main__":
    main()
