#!/usr/bin/env python3
"""Context-matched audit of Stage-5 TransitionResponseShadowV2 evidence."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audit_stage5_split_acceleration_monitor_v1 import (
    LIMIT_DEG_S2,
    SAMPLE_PERIOD_S,
    _event_index,
    _feature_series,
    _fixed_window,
    _replay,
)
from traction_mpc_stage5.config import STAGE5_ROOT


RESULTS_ROOT = STAGE5_ROOT / "results"
RESPONSE_STEPS = 4


@dataclass(frozen=True)
class CaseSpec:
    name: str
    relative_directory: str
    event_selection: str
    evidence_class: str
    context_source: str = "historical_scheduler_inference"


CASES = (
    CaseSpec(
        "human_stiffness_plus_15pct",
        "human_id_confidence_pacing_v1_attempt_01/stiffness_plus_15pct/episode_01",
        "current_monitor",
        "old_model_induced_false_alarm",
    ),
    CaseSpec(
        "human_mass_plus_8pct",
        "human_id_confidence_pacing_v1_attempt_01/mass_plus_8pct/episode_01",
        "current_monitor",
        "old_model_induced_false_alarm",
    ),
    CaseSpec(
        "human_mixed_effective_scales",
        "human_id_confidence_pacing_v1_attempt_01/mixed_effective_scales/episode_01",
        "current_monitor",
        "old_model_induced_false_alarm",
    ),
    CaseSpec(
        "interface_kt_0p7",
        "interface_mismatch_v1_attempt03/kt_0p7",
        "truth_20ms",
        "true_20ms_human_motion_violation",
    ),
    CaseSpec(
        "interface_low_low_high_historical",
        "acceleration_semantics_v2_targeted_attempt_02/low_low_high/seed_20260824",
        "truth_5ms",
        "genuine_short_execution_interface_transient",
    ),
    CaseSpec(
        "interface_kt_1p3_historical",
        "interface_mismatch_v1_attempt03/kt_1p3",
        "current_monitor",
        "genuine_short_execution_interface_transient",
    ),
    CaseSpec(
        "pb_d_knee_biased",
        "posture_benefit_v1_formal_attempt_01/early_outbound/seed_20260919/knee_biased",
        "current_monitor",
        "old_model_induced_false_alarm",
    ),
    CaseSpec(
        "cr12_baseline_v2",
        "cr12_transition_response_shadow_v2_20260918_attempt_05/execution",
        "current_monitor",
        "genuine_short_execution_interface_transient",
        "online_transition_response_shadow_v2",
    ),
    CaseSpec(
        "human_nominal_negative_control",
        "human_id_confidence_pacing_v1_attempt_01/nominal/episode_01",
        "current_near_limit",
        "benign_command_response",
    ),
    CaseSpec(
        "human_damping_plus_20pct_negative_control",
        "human_id_confidence_pacing_v1_attempt_01/damping_plus_20pct/episode_01",
        "current_near_limit",
        "benign_command_response",
    ),
    CaseSpec(
        "nominal_torque_smoke",
        "transition_response_shadow_v2_minimum_cases_20260918_attempt_03/nominal_torque_smoke",
        "fast_peak",
        "benign_command_response",
        "online_transition_response_shadow_v2",
    ),
    CaseSpec(
        "low_low_high_torque_smoke",
        "transition_response_shadow_v2_minimum_cases_20260918_attempt_03/low_low_high_torque_smoke",
        "truth_5ms",
        "genuine_short_execution_interface_transient",
        "online_transition_response_shadow_v2",
    ),
    CaseSpec(
        "kt_1p3_current_torque_smoke",
        "transition_response_shadow_v2_minimum_cases_20260918_attempt_03/kt_1p3_torque_smoke",
        "truth_5ms",
        "genuine_short_execution_interface_transient",
        "online_transition_response_shadow_v2",
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_trace(directory: Path) -> dict[str, np.ndarray]:
    with np.load(directory / "trace.npz", allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _finite(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _select_event(
    selection: str,
    current_deg_s2: np.ndarray,
    truth_5ms_deg_s2: np.ndarray,
    truth_20ms_deg_s2: np.ndarray,
    replay: dict[str, np.ndarray],
) -> int:
    if selection == "fast_peak":
        values = np.abs(np.degrees(replay["fast_acceleration"][:, 1]))
        return int(np.nanargmax(values))
    return _event_index(
        selection, current_deg_s2, truth_5ms_deg_s2, truth_20ms_deg_s2
    )


def _online_context(directory: Path, anchor_time_s: float) -> dict[str, Any] | None:
    path = directory / "transition_response_shadow_v2.json"
    if not path.exists():
        return None
    artifact = _read_json(path)
    matches = [
        event
        for event in artifact["events"]
        if np.isclose(
            event["event_timestamp_s"], anchor_time_s, atol=1.0e-10, rtol=0.0
        )
        and "MPC_COMMAND_UPDATE" in event["labels"]
    ]
    if not matches:
        return None
    event = matches[0]
    return {
        "labels": event["labels"],
        "metadata": event["metadata"],
        "online_complete_0_to_20ms": event["complete_0_to_20ms"],
        "online_sample_count": event["sample_count"],
    }


def _row_value(values: np.ndarray, index: int) -> float | None:
    return _finite(values[index])


def _audit_case(spec: CaseSpec, output_dir: Path) -> dict[str, Any]:
    directory = RESULTS_ROOT / spec.relative_directory
    trace = _load_trace(directory)
    replay = _replay(trace)
    features = _feature_series(replay)
    time = np.asarray(trace["time_s"], dtype=float)
    truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    truth_5ms = np.degrees(_fixed_window(time, truth_dq, 1))
    truth_20ms = np.degrees(_fixed_window(time, truth_dq, 4))
    current = np.degrees(trace["deployable_realized_acceleration_rad_s2"])
    event_index = _select_event(
        spec.event_selection, current, truth_5ms, truth_20ms, replay
    )
    anchor_index = event_index - event_index % RESPONSE_STEPS
    response_indices = np.arange(
        anchor_index, min(anchor_index + RESPONSE_STEPS + 1, len(time))
    )
    elapsed_ms = 1000.0 * (time[response_indices] - time[anchor_index])
    complete = bool(
        len(response_indices) == RESPONSE_STEPS + 1
        and np.isclose(elapsed_ms[-1], 20.0, atol=1.0e-8, rtol=0.0)
    )
    torque_available = bool(
        np.all(replay["robot_torque_available"][response_indices])
    )
    online_context = _online_context(directory, float(time[anchor_index]))
    context = (
        online_context
        if online_context is not None
        else {
            "labels": ["MPC_COMMAND_UPDATE_INFERRED_20MS_SCHEDULER"],
            "metadata": {
                "task_phase": str(trace["task_phase"][anchor_index]),
                "scheduler_period_s": 0.020,
                "inference_uses_only_saved_execution_time_and_phase": True,
            },
            "online_complete_0_to_20ms": None,
            "online_sample_count": None,
        }
    )

    response_rows = []
    for index, elapsed in zip(response_indices, elapsed_ms, strict=True):
        response_rows.append(
            {
                "elapsed_ms": float(elapsed),
                "sample_timestamp_s": float(time[index]),
                "current_model_q2_deg_s2": float(current[index, 1]),
                "human_20ms_q2_deg_s2": (
                    float(np.degrees(replay["human_acceleration"][index, 1]))
                    if replay["human_valid"][index]
                    else None
                ),
                "fast_5ms_q2_deg_s2": (
                    float(np.degrees(replay["fast_acceleration"][index, 1]))
                    if replay["fast_valid"][index]
                    else None
                ),
                "truth_5ms_q2_deg_s2": _row_value(truth_5ms[:, 1], index),
                "truth_20ms_q2_deg_s2": _row_value(truth_20ms[:, 1], index),
                **{name: _row_value(values, index) for name, values in features.items()},
            }
        )

    _plot_response(output_dir / f"{spec.name}_response.png", spec, response_rows)
    truth_short_violation = bool(
        np.any(
            np.all(np.isfinite(truth_5ms), axis=1)
            & np.any(np.abs(truth_5ms) > LIMIT_DEG_S2, axis=1)
        )
    )
    return {
        "name": spec.name,
        "source": str(directory.relative_to(STAGE5_ROOT)),
        "evidence_class": spec.evidence_class,
        "context_source": spec.context_source,
        "selected_event_timestamp_s": float(time[event_index]),
        "command_event_anchor_timestamp_s": float(time[anchor_index]),
        "event_elapsed_from_command_update_ms": float(
            1000.0 * (time[event_index] - time[anchor_index])
        ),
        "response_complete_0_to_20ms": complete,
        "response_sample_count": len(response_rows),
        "torque_available_for_full_response": torque_available,
        "truth_short_violation_present_anywhere": truth_short_violation,
        "context": context,
        "response": response_rows,
        "plot": f"{spec.name}_response.png",
    }


def _plot_response(path: Path, spec: CaseSpec, rows: list[dict[str, Any]]) -> None:
    elapsed = np.asarray([row["elapsed_ms"] for row in rows], dtype=float)

    def values(name: str) -> np.ndarray:
        return np.asarray(
            [np.nan if row[name] is None else row[name] for row in rows],
            dtype=float,
        )

    fig, axes = plt.subplots(5, 1, figsize=(9.5, 12.0), sharex=True)
    for name, label, style in (
        ("current_model_q2_deg_s2", "current model", "-"),
        ("human_20ms_q2_deg_s2", "Human 20 ms", "-"),
        ("fast_5ms_q2_deg_s2", "motion 5 ms", "-"),
        ("truth_5ms_q2_deg_s2", "truth 5 ms", ":"),
        ("truth_20ms_q2_deg_s2", "truth 20 ms", "--"),
    ):
        axes[0].plot(elapsed, values(name), style, marker="o", label=label)
    axes[0].axhline(600.0, color="black", linestyle="--", linewidth=0.7)
    axes[0].axhline(-600.0, color="black", linestyle="--", linewidth=0.7)
    axes[0].set_ylabel("q2 accel\n[deg/s²]")
    axes[0].legend(fontsize=7, ncol=3)

    pairs = (
        ("cuff_force_norm_n", "cuff_force_slew_norm_n_s", "cuff force", "N", "N/s"),
        (
            "interface_translation_norm_mm",
            "interface_translation_rate_norm_mm_s",
            "interface translation",
            "mm",
            "mm/s",
        ),
        (
            "command_moment_norm_nm",
            "command_moment_slew_norm_nm_s",
            "command moment",
            "Nm",
            "Nm/s",
        ),
        (
            "robot_joint_torque_norm_nm",
            "robot_joint_torque_slew_norm_nm_s",
            "robot torque",
            "Nm",
            "Nm/s",
        ),
    )
    for axis, (value_name, rate_name, label, unit, rate_unit) in zip(
        axes[1:], pairs, strict=True
    ):
        twin = axis.twinx()
        axis.plot(elapsed, values(value_name), "o-", color="tab:blue", label="norm")
        twin.plot(
            elapsed, values(rate_name), "o-", color="tab:orange", label="slew/rate"
        )
        axis.set_ylabel(f"{label}\n[{unit}]", color="tab:blue")
        twin.set_ylabel(f"[{rate_unit}]", color="tab:orange")
        axis.grid(alpha=0.25)
    axes[-1].set_xlabel("causal response after command update [ms]")
    fig.suptitle(f"{spec.name}: {spec.evidence_class}")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _class_coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    classes = sorted({row["evidence_class"] for row in cases})
    return {
        name: {
            "case_count": len(selected := [r for r in cases if r["evidence_class"] == name]),
            "complete_20ms_response_count": sum(
                r["response_complete_0_to_20ms"] for r in selected
            ),
            "full_response_with_torque_count": sum(
                r["response_complete_0_to_20ms"]
                and r["torque_available_for_full_response"]
                for r in selected
            ),
        }
        for name in classes
    }


def _write_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    fields = [
        "case",
        "evidence_class",
        "response_complete_0_to_20ms",
        "torque_available_for_full_response",
        "command_event_anchor_timestamp_s",
        "selected_event_timestamp_s",
        "elapsed_ms",
        "sample_timestamp_s",
        "current_model_q2_deg_s2",
        "human_20ms_q2_deg_s2",
        "fast_5ms_q2_deg_s2",
        "truth_5ms_q2_deg_s2",
        "truth_20ms_q2_deg_s2",
        "abs_fast_q2_acceleration_deg_s2",
        "cuff_force_norm_n",
        "cuff_force_slew_norm_n_s",
        "cuff_moment_norm_nm",
        "cuff_moment_slew_norm_nm_s",
        "interface_translation_norm_mm",
        "interface_translation_rate_norm_mm_s",
        "interface_rotation_norm_deg",
        "interface_rotation_rate_norm_deg_s",
        "command_force_norm_n",
        "command_force_slew_norm_n_s",
        "command_moment_norm_nm",
        "command_moment_slew_norm_nm_s",
        "robot_joint_torque_norm_nm",
        "robot_joint_torque_slew_norm_nm_s",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            for response in case["response"]:
                writer.writerow(
                    {
                        "case": case["name"],
                        "evidence_class": case["evidence_class"],
                        "response_complete_0_to_20ms": case[
                            "response_complete_0_to_20ms"
                        ],
                        "torque_available_for_full_response": case[
                            "torque_available_for_full_response"
                        ],
                        "command_event_anchor_timestamp_s": case[
                            "command_event_anchor_timestamp_s"
                        ],
                        "selected_event_timestamp_s": case[
                            "selected_event_timestamp_s"
                        ],
                        **response,
                    }
                )


def _cr12_authority_invariance() -> dict[str, Any]:
    old_directory = RESULTS_ROOT / "cr12_split_monitor_shadow_20260918_attempt_02/execution"
    new_directory = RESULTS_ROOT / "cr12_transition_response_shadow_v2_20260918_attempt_05/execution"
    old_trace = _load_trace(old_directory)
    new_trace = _load_trace(new_directory)
    common = sorted(set(old_trace) & set(new_trace))

    def equal(left: np.ndarray, right: np.ndarray) -> bool:
        if left.dtype.kind in "OUS":
            return bool(np.array_equal(left, right))
        return bool(np.array_equal(left, right, equal_nan=True))

    nonidentical = [
        name for name in common if not equal(old_trace[name], new_trace[name])
    ]
    old_summary = _read_json(old_directory / "summary.json")
    new_summary = _read_json(new_directory / "summary.json")
    authority_fields = (
        "task_status",
        "abort_reason",
        "task_duration_s",
        "mpc_status_counts",
        "safety_filter_status_counts",
        "brake_event_count",
        "force_gate_event_count",
        "peak_abs_estimated_joint_acceleration_deg_s2",
        "peak_abs_evaluation_only_joint_acceleration_deg_s2",
    )
    return {
        "common_trace_field_count": len(common),
        "all_common_trace_fields_bitwise_identical": not nonidentical,
        "nonidentical_common_trace_fields": nonidentical,
        "summary_authority_fields_equal": {
            name: old_summary[name] == new_summary[name] for name in authority_fields
        },
        "existing_abort_preserved": bool(
            new_summary["task_status"] == "ABORTED"
            and new_summary["abort_reason"] == "TASK_ACCELERATION_LIMIT"
            and np.isclose(new_summary["task_duration_s"], 0.315)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_ROOT / "transition_response_shadow_v2_audit",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = [_audit_case(spec, args.output_dir) for spec in CASES]
    coverage = _class_coverage(cases)
    by_name = {row["name"]: row for row in cases}
    nominal_profile = by_name["nominal_torque_smoke"]["response"]
    kt_1p3_profile = by_name["kt_1p3_current_torque_smoke"]["response"]
    shape_example = {
        "benign_nominal_abs_fast_q2_deg_s2": [
            abs(row["fast_5ms_q2_deg_s2"]) for row in nominal_profile
        ],
        "true_kt_1p3_abs_fast_q2_deg_s2": [
            abs(row["fast_5ms_q2_deg_s2"]) for row in kt_1p3_profile
        ],
        "benign_nominal_pattern": "large +5 ms response followed by decay",
        "true_kt_1p3_pattern": "delayed growth through +15 and +20 ms",
        "peak_torque_slew_is_not_separating": bool(
            max(
                row["robot_joint_torque_slew_norm_nm_s"]
                for row in nominal_profile
                if row["robot_joint_torque_slew_norm_nm_s"] is not None
            )
            > max(
                row["robot_joint_torque_slew_norm_nm_s"]
                for row in kt_1p3_profile
                if row["robot_joint_torque_slew_norm_nm_s"] is not None
            )
        ),
    }
    payload = {
        "schema": "stage5_transition_response_shadow_v2_audit",
        "evidence_category": "saved_trace_diagnostic_plus_minimum_engineering_smoke",
        "conclusion": (
            "TR-B — USEFUL TRANSIENT SIGNATURE EXISTS, MORE EVIDENCE NEEDED"
        ),
        "shadow_only": True,
        "abort_authority_changed": False,
        "hard_threshold_registered": False,
        "cr12_authority_invariance": _cr12_authority_invariance(),
        "response_window_ms": [0.0, 5.0, 10.0, 15.0, 20.0],
        "class_coverage": coverage,
        "reliability_findings": {
            "context_matched_full_positive_windows_available": (
                coverage["genuine_short_execution_interface_transient"][
                    "complete_20ms_response_count"
                ]
            ),
            "context_matched_full_positive_windows_with_torque": (
                coverage["genuine_short_execution_interface_transient"][
                    "full_response_with_torque_count"
                ]
            ),
            "kt_1p3_short_truth_violation_reproduced_in_current_torque_smoke": True,
            "historical_kt_1p3_event_time_reproduced_exactly": False,
            "reason_no_hard_gate": (
                "only one genuine-short-transient and one benign command case have "
                "complete torque-bearing 20 ms trajectories; low_low_high, CR12, the "
                "historical Kt=1.3 event, and all old model false alarms are truncated "
                "by existing authority before a full post-event response is available"
            ),
            "context_matched_shape_example": shape_example,
            "useful_signatures": [
                "event-aligned cuff wrench slew trajectory",
                "interface translation-rate trajectory",
                "command moment magnitude and slew trajectory",
                "robot torque magnitude and slew where retained",
            ],
        },
        "cases": cases,
    }
    (args.output_dir / "transition_response_shadow_v2_audit.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.output_dir / "response_matrix.csv", cases)
    print(args.output_dir)


if __name__ == "__main__":
    main()
