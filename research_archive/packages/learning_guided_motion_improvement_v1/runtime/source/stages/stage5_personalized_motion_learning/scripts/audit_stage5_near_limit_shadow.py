#!/usr/bin/env python3
"""Audit context-matched near-limit diagnostic continuations.

This is an offline, shadow-only comparison.  It deliberately does not fit or
register a classifier, threshold, or control action.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT


RESULTS = STAGE5_ROOT / "results"
JOINT_ACCELERATION_LIMIT_DEG_S2 = np.asarray([300.0, 600.0])


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _norm(vector: Any, start: int = 0, stop: int | None = None) -> float | None:
    values = np.asarray(vector, dtype=float)[start:stop]
    return float(np.linalg.norm(values)) if np.all(np.isfinite(values)) else None


def _window_rows(window: dict[str, Any]) -> list[dict[str, float | None]]:
    event = window["continuation"]["transition_response_shadow_v2"]["events"][0]
    truth = window["offline_evaluation_only_mujoco_truth"]
    rows: list[dict[str, float | None]] = []
    previous_truth_dq: np.ndarray | None = None
    for sample, truth_sample in zip(event["samples"], truth, strict=True):
        fast = np.degrees(
            np.asarray(sample["fast_motion_5ms_acceleration_rad_s2"], dtype=float)
        )
        human = np.degrees(
            np.asarray(sample["human_motion_20ms_acceleration_rad_s2"], dtype=float)
        )
        truth_qacc = np.degrees(
            np.asarray(truth_sample["mujoco_human_qacc_rad_s2"], dtype=float)
        )
        truth_dq = np.asarray(truth_sample["human_dq_rad_s"], dtype=float)
        truth_5ms = (
            None
            if previous_truth_dq is None
            else np.degrees((truth_dq - previous_truth_dq) / 0.005)
        )
        previous_truth_dq = truth_dq
        cuff = sample["cuff_wrench_world"]
        cuff_slew = sample["cuff_wrench_slew_world_per_s"]
        command = sample["command_wrench_world"]
        command_slew = sample["command_wrench_slew_world_per_s"]
        rows.append(
            {
                "elapsed_ms": 1000.0 * sample["response_elapsed_s"],
                "fast_5ms_q1_deg_s2": (
                    float(fast[0]) if sample["fast_motion_5ms_valid"] else None
                ),
                "fast_5ms_q2_deg_s2": (
                    float(fast[1]) if sample["fast_motion_5ms_valid"] else None
                ),
                "human_20ms_q1_deg_s2": (
                    float(human[0]) if sample["human_motion_20ms_valid"] else None
                ),
                "human_20ms_q2_deg_s2": (
                    float(human[1]) if sample["human_motion_20ms_valid"] else None
                ),
                "offline_truth_5ms_q1_deg_s2": (
                    None if truth_5ms is None else float(truth_5ms[0])
                ),
                "offline_truth_5ms_q2_deg_s2": (
                    None if truth_5ms is None else float(truth_5ms[1])
                ),
                "offline_mujoco_instantaneous_q1_deg_s2": float(truth_qacc[0]),
                "offline_mujoco_instantaneous_q2_deg_s2": float(truth_qacc[1]),
                "cuff_force_norm_n": _norm(cuff, 0, 3),
                "cuff_force_slew_norm_n_s": _norm(cuff_slew, 0, 3),
                "cuff_moment_norm_nm": _norm(cuff, 3, 6),
                "cuff_moment_slew_norm_nm_s": _norm(cuff_slew, 3, 6),
                "interface_translation_norm_mm": 1000.0
                * _norm(sample["interface_translation_human_m"]),
                "interface_translation_rate_norm_mm_s": 1000.0
                * _norm(sample["interface_velocity_human_m_s"]),
                "interface_rotation_norm_deg": float(
                    np.degrees(_norm(sample["interface_rotation_human_rad"]))
                ),
                "interface_rotation_rate_norm_deg_s": float(
                    np.degrees(
                        _norm(sample["interface_angular_velocity_human_rad_s"])
                    )
                ),
                "command_force_norm_n": _norm(command, 0, 3),
                "command_force_slew_norm_n_s": _norm(command_slew, 0, 3),
                "command_moment_norm_nm": _norm(command, 3, 6),
                "command_moment_slew_norm_nm_s": _norm(command_slew, 3, 6),
                "robot_joint_torque_norm_nm": _norm(
                    sample["robot_joint_torque_command_nm"]
                ),
                "robot_joint_torque_slew_norm_nm_s": _norm(
                    sample["robot_joint_torque_slew_nm_s"]
                ),
            }
        )
    return rows


def _normalized_shape(rows: list[dict[str, float | None]], field: str) -> list[float]:
    values = np.asarray([row[field] for row in rows], dtype=float)
    peak = float(np.max(np.abs(values)))
    return (values / peak).tolist() if peak > 0.0 else np.zeros_like(values).tolist()


def _shape_summary(rows: list[dict[str, float | None]]) -> dict[str, Any]:
    q2 = np.asarray([row["fast_5ms_q2_deg_s2"] for row in rows], dtype=float)
    q2_abs = np.abs(q2)
    initial = float(q2_abs[0])
    return {
        "signed_fast_q2_trajectory_deg_s2": q2.tolist(),
        "signed_fast_q2_normalized_shape": _normalized_shape(
            rows, "fast_5ms_q2_deg_s2"
        ),
        "final_to_initial_abs_ratio": (
            float(q2_abs[-1] / initial) if initial > 0.0 else None
        ),
        "peak_to_initial_abs_ratio": (
            float(np.max(q2_abs) / initial) if initial > 0.0 else None
        ),
        "peak_elapsed_ms": float(rows[int(np.argmax(q2_abs))]["elapsed_ms"]),
        "successive_abs_deltas_deg_s2": np.diff(q2_abs).tolist(),
        "all_successive_abs_deltas_nonpositive": bool(np.all(np.diff(q2_abs) <= 0.0)),
        "sign_reversal_present": bool(np.any(np.signbit(q2[1:]) != np.signbit(q2[:-1]))),
    }


def _truth_summary(rows: list[dict[str, float | None]]) -> dict[str, Any]:
    intervals = np.asarray(
        [
            [row["offline_truth_5ms_q1_deg_s2"], row["offline_truth_5ms_q2_deg_s2"]]
            for row in rows[1:]
        ],
        dtype=float,
    )
    maximum = np.max(np.abs(intervals), axis=0)
    return {
        "offline_only_5ms_interval_acceleration_deg_s2": intervals.tolist(),
        "maximum_absolute_deg_s2": maximum.tolist(),
        "all_intervals_below_existing_300_600_boundary": bool(
            np.all(maximum < JOINT_ACCELERATION_LIMIT_DEG_S2)
        ),
    }


def _near_limit_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    summary = _read(cases_dir / "near_limit_cases_summary.json")
    roles = {row["case"]: row["role"] for row in summary["cases"]}
    for case_name in sorted(roles):
        artifact_path = cases_dir / case_name / "near_limit_diagnostic_continuations.json"
        artifact = _read(artifact_path)
        for window in artifact["windows"]:
            trigger = window["trigger"]
            metadata = trigger["metadata"]
            rows = _window_rows(window)
            offset = int(metadata["mpc_cycle_offset"])
            name = f"{case_name}__mpc_offset_{offset}"
            cases.append(
                {
                    "name": name,
                    "base_case": case_name,
                    "role": roles[case_name],
                    "source": str(artifact_path.relative_to(STAGE5_ROOT)),
                    "trigger_kind": trigger["kind"],
                    "trigger_timestamp_s": trigger["timestamp_s"],
                    "task_phase": metadata["task_phase"],
                    "support_load_state": metadata["support_load_state"],
                    "interface_load_state": metadata["interface_load_state"],
                    "mpc_cycle_offset": offset,
                    "elapsed_since_mpc_update_ms": metadata[
                        "elapsed_since_mpc_update_ms"
                    ],
                    "boundary_proximity": metadata["actual_boundary_proximity"],
                    "registered_limit_deg_s2": metadata[
                        "registered_limit_deg_s2"
                    ],
                    "complete_0_to_20ms": window["continuation"][
                        "transition_response_shadow_v2"
                    ]["events"][0]["complete_0_to_20ms"],
                    "snapshot_digest": window["snapshot"]["decision_state_sha256"],
                    "response": rows,
                    "shape": _shape_summary(rows),
                    "offline_truth": _truth_summary(rows),
                }
            )
    return cases


def _post_abort_cases(cases_dir: Path) -> list[dict[str, Any]]:
    roles = {
        "cr12_baseline": "genuine_short_execution_interface_transient",
        "kt_1p3": "genuine_short_execution_interface_transient",
        "low_low_high": "genuine_short_execution_interface_transient",
        "stiffness_plus_15pct": "model_induced_false_alarm",
        "mass_plus_8pct": "model_induced_false_alarm",
    }
    cases: list[dict[str, Any]] = []
    for case_name, role in roles.items():
        artifact_path = cases_dir / case_name / "diagnostic_post_abort_continuation.json"
        window = _read(artifact_path)
        abort = window["authoritative_abort"]
        rows = _window_rows(window)
        offset = int(round(float(abort["timestamp_s"]) / 0.005)) % 4
        cases.append(
            {
                "name": f"{case_name}__abort",
                "base_case": case_name,
                "role": role,
                "source": str(artifact_path.relative_to(STAGE5_ROOT)),
                "trigger_kind": "ACCELERATION_MONITOR_ABORT",
                "trigger_timestamp_s": abort["timestamp_s"],
                "task_phase": "OUTBOUND",
                "support_load_state": "LOADED_TRACK",
                "interface_load_state": "LOADED",
                "mpc_cycle_offset": offset,
                "elapsed_since_mpc_update_ms": 5.0 * offset,
                "boundary_proximity": None,
                "registered_limit_deg_s2": [300.0, 600.0],
                "complete_0_to_20ms": window["continuation"][
                    "transition_response_shadow_v2"
                ]["events"][0]["complete_0_to_20ms"],
                "snapshot_digest": window["snapshot"]["decision_state_sha256"],
                "response": rows,
                "shape": _shape_summary(rows),
                "offline_truth": _truth_summary(rows),
            }
        )
    return cases


def _trajectory_distance(left: list[float], right: list[float]) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(left) - np.asarray(right)))))


def _context_matches(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positives = [
        case
        for case in cases
        if case["role"] == "genuine_short_execution_interface_transient"
    ]
    comparators = [
        case
        for case in cases
        if case["role"]
        in {
            "benign_near_limit",
            "benign_comparable_command_load_context",
            "human_mismatch_nonabort_state",
            "model_induced_false_alarm",
        }
    ]
    rows = []
    for positive in positives:
        matched = [
            candidate
            for candidate in comparators
            if candidate["task_phase"] == positive["task_phase"]
            and candidate["support_load_state"] == positive["support_load_state"]
            and candidate["interface_load_state"] == positive["interface_load_state"]
            and candidate["mpc_cycle_offset"] == positive["mpc_cycle_offset"]
        ]
        for candidate in matched:
            rows.append(
                {
                    "positive": positive["name"],
                    "comparator": candidate["name"],
                    "comparator_role": candidate["role"],
                    "context": {
                        "task_phase": positive["task_phase"],
                        "support_load_state": positive["support_load_state"],
                        "interface_load_state": positive["interface_load_state"],
                        "mpc_cycle_offset": positive["mpc_cycle_offset"],
                    },
                    "signed_normalized_fast_q2_shape_rms_distance": _trajectory_distance(
                        positive["shape"]["signed_fast_q2_normalized_shape"],
                        candidate["shape"]["signed_fast_q2_normalized_shape"],
                    ),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["positive"],
            row["signed_normalized_fast_q2_shape_rms_distance"],
        ),
    )


def _feature_ranges(cases: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "fast_5ms_q2_deg_s2",
        "human_20ms_q2_deg_s2",
        "cuff_force_slew_norm_n_s",
        "cuff_moment_slew_norm_nm_s",
        "interface_translation_rate_norm_mm_s",
        "interface_rotation_rate_norm_deg_s",
        "command_force_slew_norm_n_s",
        "command_moment_slew_norm_nm_s",
        "robot_joint_torque_slew_norm_nm_s",
    )
    result: dict[str, Any] = {}
    for role in sorted({case["role"] for case in cases}):
        role_cases = [case for case in cases if case["role"] == role]
        result[role] = {}
        for field in fields:
            peaks = [
                max(
                    abs(float(row[field]))
                    for row in case["response"]
                    if row[field] is not None
                )
                for case in role_cases
            ]
            result[role][field] = {
                "minimum_case_peak": min(peaks),
                "maximum_case_peak": max(peaks),
            }
    return result


def _authority_invariance(cases_dir: Path) -> dict[str, Any]:
    collection = _read(cases_dir / "near_limit_cases_summary.json")
    result: dict[str, Any] = {}
    authority_fields = (
        "task_status",
        "abort_reason",
        "task_duration_s",
        "mpc_status_counts",
        "safety_filter_status_counts",
        "brake_event_count",
        "force_gate_event_count",
    )
    for case in collection["cases"]:
        source = STAGE5_ROOT / case["selection_source"]
        output = STAGE5_ROOT / case["output"]
        with np.load(source / "trace.npz", allow_pickle=False) as left, np.load(
            output / "trace.npz", allow_pickle=False
        ) as right:
            common = sorted(set(left.files) & set(right.files))
            differences = []
            maximum_absolute_difference = 0.0
            for field in common:
                equal = (
                    np.array_equal(left[field], right[field])
                    if left[field].dtype.kind in "OUS"
                    else np.array_equal(left[field], right[field], equal_nan=True)
                )
                if not equal:
                    differences.append(field)
                    if left[field].dtype.kind not in "OUS":
                        maximum_absolute_difference = max(
                            maximum_absolute_difference,
                            float(np.nanmax(np.abs(left[field] - right[field]))),
                        )
        left_summary = _read(source / "summary.json")
        right_summary = _read(output / "summary.json")
        result[case["case"]] = {
            "common_trace_field_count": len(common),
            "all_common_trace_fields_bitwise_identical": not differences,
            "nonidentical_common_trace_fields": differences,
            "maximum_absolute_numeric_difference": maximum_absolute_difference,
            "all_common_trace_fields_equal_within_1e_12": bool(
                maximum_absolute_difference <= 1e-12
                and all(
                    left_summary.get(field) == right_summary.get(field)
                    for field in authority_fields
                )
            ),
            "summary_authority_fields_equal": {
                field: left_summary[field] == right_summary[field]
                for field in authority_fields
            },
        }
    return result


def _plot(path: Path, case: dict[str, Any]) -> None:
    rows = case["response"]
    elapsed = np.asarray([row["elapsed_ms"] for row in rows], dtype=float)

    def series(name: str) -> np.ndarray:
        return np.asarray(
            [np.nan if row.get(name) is None else row[name] for row in rows],
            dtype=float,
        )

    fig, axes = plt.subplots(5, 1, figsize=(9.5, 12.0), sharex=True)
    for name, label, style in (
        ("fast_5ms_q1_deg_s2", "deployable 5 ms q1", "-"),
        ("fast_5ms_q2_deg_s2", "deployable 5 ms q2", "-"),
        ("human_20ms_q1_deg_s2", "deployable Human 20 ms q1", "--"),
        ("human_20ms_q2_deg_s2", "deployable Human 20 ms q2", "--"),
        ("offline_truth_5ms_q2_deg_s2", "MuJoCo 5 ms offline only", ":"),
    ):
        if any(row.get(name) is not None for row in rows):
            axes[0].plot(elapsed, series(name), style, marker="o", label=label)
    axes[0].axhline(600.0, color="0.6", linewidth=0.8)
    axes[0].axhline(-600.0, color="0.6", linewidth=0.8)
    axes[0].set_ylabel("acceleration\n[deg/s²]")
    axes[0].legend(fontsize=7)

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
    for axis, (value, rate, label, unit, rate_unit) in zip(
        axes[1:], pairs, strict=True
    ):
        twin = axis.twinx()
        axis.plot(elapsed, series(value), "o-", color="tab:blue")
        twin.plot(elapsed, series(rate), "o-", color="tab:orange")
        axis.set_ylabel(f"{label}\n[{unit}]", color="tab:blue")
        twin.set_ylabel(f"[{rate_unit}]", color="tab:orange")
        axis.grid(alpha=0.25)
    axes[-1].set_xlabel("causal response elapsed [ms]")
    fig.suptitle(f"{case['name']}: {case['role']}")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _write_matrix(path: Path, cases: list[dict[str, Any]]) -> None:
    response_fields = sorted(
        {key for case in cases for row in case["response"] for key in row}
    )
    fields = [
        "case",
        "base_case",
        "role",
        "trigger_kind",
        "task_phase",
        "support_load_state",
        "interface_load_state",
        "mpc_cycle_offset",
        "boundary_proximity",
    ] + response_fields
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            for row in case["response"]:
                writer.writerow({key: case.get(key) for key in fields} | row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--near-limit-cases-dir",
        type=Path,
        default=RESULTS / "near_limit_shadow_cases_20260918_attempt_01",
    )
    parser.add_argument(
        "--post-abort-cases-dir",
        type=Path,
        default=RESULTS / "diagnostic_continuation_cases_20260918_attempt_02",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS / "near_limit_shadow_audit",
    )
    args = parser.parse_args()
    args.near_limit_cases_dir = args.near_limit_cases_dir.resolve()
    args.post_abort_cases_dir = args.post_abort_cases_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    near_limit = _near_limit_cases(args.near_limit_cases_dir)
    post_abort = _post_abort_cases(args.post_abort_cases_dir)
    cases = near_limit + post_abort
    for case in cases:
        case["plot"] = f"{case['name']}_response.png"
        _plot(args.output_dir / case["plot"], case)

    matches = _context_matches(cases)
    nearest = {}
    for positive in sorted({row["positive"] for row in matches}):
        candidates = [row for row in matches if row["positive"] == positive]
        nearest[positive] = min(
            candidates,
            key=lambda row: row["signed_normalized_fast_q2_shape_rms_distance"],
        )

    payload = {
        "schema": "stage5_near_limit_shadow_audit_v1",
        "evidence_category": "shadow_only_engineering_diagnostic",
        "conclusion": (
            "NL-C — CURRENT DEPLOYABLE SIGNALS CANNOT RELIABLY SEPARATE FAST "
            "TRANSIENTS"
        ),
        "shadow_only": True,
        "abort_authority_changed": False,
        "threshold_changed": False,
        "hard_threshold_registered": False,
        "controller_semantics_changed": False,
        "scientific_parameters_changed": False,
        "near_limit_window_count": len(near_limit),
        "complete_near_limit_window_count": sum(
            case["complete_0_to_20ms"] for case in near_limit
        ),
        "all_near_limit_offline_truth_5ms_intervals_below_existing_boundary": all(
            case["offline_truth"][
                "all_intervals_below_existing_300_600_boundary"
            ]
            for case in near_limit
        ),
        "authority_invariance": _authority_invariance(
            args.near_limit_cases_dir
        ),
        "context_matched_shape_comparisons": matches,
        "nearest_context_matched_comparator_by_fast_q2_shape": nearest,
        "peak_feature_ranges_by_role": _feature_ranges(cases),
        "findings": {
            "benign_near_limit_response": (
                "Benign and non-abort windows include monotonic decay, an early "
                "rebound, and a sign reversal under identical frozen-command policy."
            ),
            "genuine_short_transient": (
                "CR12 and Kt=1.3 show non-monotonic fast acceleration, but "
                "low_low_high shows a strongly decaying response that closely "
                "matches benign damping and nominal-torque response shapes."
            ),
            "model_induced_false_alarm": (
                "The old Human-mismatch abort windows decay; nearby non-abort "
                "windows in the same cases also decay or reverse sign, so trend "
                "alone does not identify monitor semantics."
            ),
            "slew_channels": (
                "Command and torque slew fall to zero after +5 ms by frozen-command "
                "construction. Cuff/interface magnitudes and slews overlap across "
                "roles and do not provide a unique context-invariant separator."
            ),
            "why_no_stage5_hard_gate": (
                "The finite evidence contains a genuine labeled transient with a "
                "benign-like decaying response and benign windows with rebound/sign "
                "reversal. A single deployable Stage-5 rule would therefore create "
                "known ambiguity rather than a supported authority contract."
            ),
            "exactly_one_next_implementation": (
                "Delegate 5 ms execution/interface transient protection to the "
                "lower-level robot and force/torque safety layer, where actuator- "
                "and sensor-rate limits are available; retain the deployable 20 ms "
                "Human-motion envelope and contextual supervision in Stage-5. This "
                "audit does not define or activate a lower-level threshold."
            ),
        },
        "cases": cases,
    }
    _write(args.output_dir / "near_limit_shadow_audit.json", payload)
    _write_matrix(args.output_dir / "response_matrix.csv", cases)
    _write(args.output_dir / "context_matched_shape_comparisons.json", matches)
    print(args.output_dir)


if __name__ == "__main__":
    main()
