#!/usr/bin/env python3
"""Audit complete post-abort response shapes without defining a hard gate."""

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
BENIGN_AUDIT = (
    RESULTS
    / "transition_response_shadow_v2_audit_20260918_attempt_07"
    / "transition_response_shadow_v2_audit.json"
)


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


def _diagnostic_case(directory: Path, name: str, role: str) -> dict[str, Any]:
    directory = directory.resolve()
    artifact = _read(directory / "diagnostic_post_abort_continuation.json")
    response_artifact = artifact["continuation"]["transition_response_shadow_v2"]
    event = response_artifact["events"][0]
    truth = artifact["offline_evaluation_only_mujoco_truth"]
    rows = []
    for index, (sample, truth_sample) in enumerate(
        zip(event["samples"], truth, strict=True)
    ):
        fast = np.degrees(
            np.asarray(sample["fast_motion_5ms_acceleration_rad_s2"], dtype=float)
        )
        human = np.degrees(
            np.asarray(
                sample["human_motion_20ms_acceleration_rad_s2"], dtype=float
            )
        )
        truth_qacc = np.degrees(
            np.asarray(truth_sample["mujoco_human_qacc_rad_s2"], dtype=float)
        )
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
                    float(human[0])
                    if sample["human_motion_20ms_valid"]
                    else None
                ),
                "human_20ms_q2_deg_s2": (
                    float(human[1])
                    if sample["human_motion_20ms_valid"]
                    else None
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
    fast_abs = np.asarray(
        [abs(row["fast_5ms_q2_deg_s2"]) for row in rows], dtype=float
    )
    return {
        "name": name,
        "role": role,
        "source": str(directory.relative_to(STAGE5_ROOT)),
        "response_context": "authoritative acceleration abort; frozen last command",
        "authoritative_abort_reason": artifact["authoritative_abort"]["reason"],
        "authoritative_abort_time_s": artifact["authoritative_abort"]["timestamp_s"],
        "response_complete_0_to_20ms": event["complete_0_to_20ms"],
        "snapshot_digest": artifact["snapshot"]["decision_state_sha256"],
        "exact_duration_verified": artifact["continuation"][
            "exact_duration_verified"
        ],
        "response": rows,
        "shape_features": event["response_shape_features"],
        "fast_q2_shape_summary": {
            "abs_trajectory_deg_s2": fast_abs.tolist(),
            "final_minus_initial_abs_deg_s2": float(fast_abs[-1] - fast_abs[0]),
            "peak_elapsed_ms": float(rows[int(np.argmax(fast_abs))]["elapsed_ms"]),
            "all_successive_abs_deltas_nonpositive": bool(
                np.all(np.diff(fast_abs) <= 0.0)
            ),
        },
    }


def _benign_cases() -> list[dict[str, Any]]:
    prior = _read(BENIGN_AUDIT)
    selected = {
        "nominal_torque_smoke",
        "human_nominal_negative_control",
        "human_damping_plus_20pct_negative_control",
    }
    result = []
    for case in prior["cases"]:
        if case["name"] not in selected:
            continue
        result.append(
            {
                "name": case["name"],
                "role": "matched_benign_control",
                "source": case["source"],
                "response_context": "retained V2 command-event response",
                "authoritative_abort_reason": None,
                "authoritative_abort_time_s": None,
                "response_complete_0_to_20ms": case[
                    "response_complete_0_to_20ms"
                ],
                "snapshot_digest": None,
                "exact_duration_verified": case[
                    "response_complete_0_to_20ms"
                ],
                "response": case["response"],
                "shape_features": None,
                "fast_q2_shape_summary": {
                    "abs_trajectory_deg_s2": [
                        abs(row["fast_5ms_q2_deg_s2"])
                        for row in case["response"]
                        if row["fast_5ms_q2_deg_s2"] is not None
                    ],
                    "source_is_prior_v2_audit": True,
                },
            }
        )
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
        (
            "offline_mujoco_instantaneous_q2_deg_s2",
            "MuJoCo instantaneous offline only",
            ":",
        ),
    ):
        if any(row.get(name) is not None for row in rows):
            axes[0].plot(elapsed, series(name), style, marker="o", label=label)
    axes[0].set_ylabel("q2 accel\n[deg/s²]")
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


def _write_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    response_fields = sorted(
        {
            key
            for case in cases
            for row in case["response"]
            for key in row
        }
    )
    fields = ["case", "role", "response_context"] + response_fields
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            for row in case["response"]:
                writer.writerow(
                    {
                        "case": case["name"],
                        "role": case["role"],
                        "response_context": case["response_context"],
                        **row,
                    }
                )


def _authority_invariance(cases_dir: Path) -> dict[str, Any]:
    comparisons = {
        "cr12_baseline": RESULTS
        / "cr12_transition_response_shadow_v2_20260918_attempt_05"
        / "execution",
        "low_low_high": RESULTS
        / "transition_response_shadow_v2_minimum_cases_20260918_attempt_03"
        / "low_low_high_torque_smoke",
    }
    result = {}
    for name, old_dir in comparisons.items():
        new_dir = cases_dir / name
        with np.load(old_dir / "trace.npz", allow_pickle=False) as left, np.load(
            new_dir / "trace.npz", allow_pickle=False
        ) as right:
            common = sorted(set(left.files) & set(right.files))
            differences = []
            for field in common:
                equal = (
                    np.array_equal(left[field], right[field])
                    if left[field].dtype.kind in "OUS"
                    else np.array_equal(left[field], right[field], equal_nan=True)
                )
                if not equal:
                    differences.append(field)
        old_summary = _read(old_dir / "summary.json")
        new_summary = _read(new_dir / "summary.json")
        authority_fields = (
            "task_status",
            "abort_reason",
            "task_duration_s",
            "mpc_status_counts",
            "safety_filter_status_counts",
            "brake_event_count",
            "force_gate_event_count",
        )
        result[name] = {
            "common_trace_field_count": len(common),
            "all_common_trace_fields_bitwise_identical": not differences,
            "nonidentical_common_trace_fields": differences,
            "summary_authority_fields_equal": {
                field: old_summary[field] == new_summary[field]
                for field in authority_fields
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=RESULTS / "diagnostic_continuation_cases_20260918_attempt_02",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS / "diagnostic_continuation_audit",
    )
    args = parser.parse_args()
    args.cases_dir = args.cases_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cases = [
        _diagnostic_case(args.cases_dir / name, name, role)
        for name, role in (
            ("cr12_baseline", "genuine_short_execution_interface_transient"),
            ("kt_1p3", "genuine_short_execution_interface_transient"),
            ("low_low_high", "genuine_short_execution_interface_transient"),
            ("stiffness_plus_15pct", "model_induced_false_alarm"),
            ("mass_plus_8pct", "model_induced_false_alarm"),
        )
    ]
    cases.extend(_benign_cases())
    for case in cases:
        case["plot"] = f"{case['name']}_response.png"
        _plot(args.output_dir / case["plot"], case)

    by_name = {case["name"]: case for case in cases}
    payload = {
        "schema": "stage5_diagnostic_post_abort_continuation_audit_v1",
        "evidence_category": "diagnostic_engineering_smoke_plus_retained_controls",
        "conclusion": "DC-B — PARTIAL SEPARATION; MORE EVIDENCE NEEDED",
        "abort_authority_changed": False,
        "hard_threshold_registered": False,
        "scientific_parameters_changed": False,
        "diagnostic_clone_policy": "FROZEN_LAST_EXECUTABLE_COMMAND",
        "authority_invariance": _authority_invariance(args.cases_dir),
        "complete_post_abort_windows": sum(
            case["response_complete_0_to_20ms"]
            for case in cases
            if case["authoritative_abort_reason"] == "TASK_ACCELERATION_LIMIT"
        ),
        "findings": {
            "old_false_alarm_shapes": {
                name: by_name[name]["fast_q2_shape_summary"]
                for name in ("stiffness_plus_15pct", "mass_plus_8pct")
            },
            "short_transient_shapes": {
                name: by_name[name]["fast_q2_shape_summary"]
                for name in ("cr12_baseline", "kt_1p3", "low_low_high")
            },
            "partial_separation": (
                "CR12 and Kt=1.3 rebound after an early drop, whereas both old "
                "Human-mismatch false alarms decay strongly over the frozen-command "
                "window."
            ),
            "overlap_prevents_authority_design": (
                "low_low_high also decays monotonically, and Kt=1.3 overlaps the "
                "stiffness false alarm in fast-acceleration magnitude and endpoint; "
                "retained benign controls are command-event rather than matched "
                "non-abort frozen-command windows."
            ),
            "command_and_torque_slew_after_abort": (
                "Both are zero after +5 ms by construction because the clone holds "
                "the last command; they document isolation but cannot separate classes."
            ),
            "next_implementation_recommendation": (
                "Add one shadow-only, context-matched non-abort trigger that clones "
                "the same frozen-command 20 ms response at near-limit events; do not "
                "grant authority or add thresholds."
            ),
        },
        "cases": cases,
    }
    _write(
        args.output_dir / "diagnostic_continuation_audit.json",
        payload,
    )
    _write_csv(args.output_dir / "response_matrix.csv", cases)
    print(args.output_dir)


if __name__ == "__main__":
    main()
