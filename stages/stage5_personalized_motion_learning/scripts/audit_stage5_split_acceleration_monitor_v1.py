#!/usr/bin/env python3
"""Replay and audit SplitAccelerationMonitorV1 on retained Stage-5 traces."""

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

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.split_acceleration_monitor import (
    SplitAccelerationMonitorV1,
)


RESULTS_ROOT = STAGE5_ROOT / "results"
LIMIT_DEG_S2 = np.array([300.0, 600.0])
SAMPLE_PERIOD_S = 0.005


@dataclass(frozen=True)
class CaseSpec:
    name: str
    relative_directory: str
    event_selection: str
    short_transient_role: str


CASES = (
    CaseSpec(
        "human_stiffness_plus_15pct",
        "human_id_confidence_pacing_v1_attempt_01/"
        "stiffness_plus_15pct/episode_01",
        "current_monitor",
        "benign_motion_at_event",
    ),
    CaseSpec(
        "human_mass_plus_8pct",
        "human_id_confidence_pacing_v1_attempt_01/mass_plus_8pct/episode_01",
        "current_monitor",
        "benign_motion_at_event",
    ),
    CaseSpec(
        "human_mixed_effective_scales",
        "human_id_confidence_pacing_v1_attempt_01/"
        "mixed_effective_scales/episode_01",
        "current_monitor",
        "benign_motion_at_event",
    ),
    CaseSpec(
        "interface_kt_0p7",
        "interface_mismatch_v1_attempt03/kt_0p7",
        "truth_20ms",
        "true_20ms_motion_not_short_transient_at_event",
    ),
    CaseSpec(
        "interface_low_low_high",
        "acceleration_semantics_v2_targeted_attempt_02/low_low_high/"
        "seed_20260824",
        "truth_5ms",
        "true_short_transient",
    ),
    CaseSpec(
        "interface_kt_1p3",
        "interface_mismatch_v1_attempt03/kt_1p3",
        "current_monitor",
        "true_short_transient",
    ),
    CaseSpec(
        "posture_benefit_early_outbound_20260919_knee_biased",
        "posture_benefit_v1_formal_attempt_01/early_outbound/"
        "seed_20260919/knee_biased",
        "current_monitor",
        "benign_motion_at_event",
    ),
    CaseSpec(
        "cr12_provisional_cuff_baseline",
        "cr12_split_monitor_shadow_20260918_attempt_02/execution",
        "current_monitor",
        "true_short_transient",
    ),
    CaseSpec(
        "human_nominal_negative_control",
        "human_id_confidence_pacing_v1_attempt_01/nominal/episode_01",
        "current_near_limit",
        "benign_negative_control",
    ),
    CaseSpec(
        "human_damping_plus_20pct_negative_control",
        "human_id_confidence_pacing_v1_attempt_01/"
        "damping_plus_20pct/episode_01",
        "current_near_limit",
        "benign_negative_control",
    ),
)


def _fixed_window(time_s: np.ndarray, velocity: np.ndarray, steps: int) -> np.ndarray:
    result = np.full_like(velocity, np.nan, dtype=float)
    if len(time_s) <= steps:
        return result
    duration = time_s[steps:] - time_s[:-steps]
    expected = SAMPLE_PERIOD_S * steps
    if not np.allclose(duration, expected, atol=1.0e-10, rtol=0.0):
        raise ValueError("saved trace does not provide exact 5 ms samples")
    result[steps:] = (velocity[steps:] - velocity[:-steps]) / expected
    return result


def _over_limit(values_deg_s2: np.ndarray) -> np.ndarray:
    return np.any(np.abs(values_deg_s2) > LIMIT_DEG_S2, axis=-1)


def _first_over(values_deg_s2: np.ndarray) -> int:
    available = np.all(np.isfinite(values_deg_s2), axis=1)
    indices = np.flatnonzero(available & _over_limit(np.nan_to_num(values_deg_s2)))
    if not len(indices):
        raise ValueError("requested event is absent")
    return int(indices[0])


def _event_index(
    selection: str,
    current_deg_s2: np.ndarray,
    truth_5ms_deg_s2: np.ndarray,
    truth_20ms_deg_s2: np.ndarray,
) -> int:
    if selection == "current_monitor":
        return _first_over(current_deg_s2)
    if selection == "truth_5ms":
        return _first_over(truth_5ms_deg_s2)
    if selection == "truth_20ms":
        return _first_over(truth_20ms_deg_s2)
    if selection == "current_near_limit":
        normalized = np.abs(current_deg_s2) / LIMIT_DEG_S2
        return int(np.argmax(np.max(normalized, axis=1)))
    raise ValueError(f"unsupported event selection: {selection}")


def _norm_rows(values: np.ndarray, component: slice | None = None) -> np.ndarray:
    selected = values if component is None else values[:, component]
    return np.linalg.norm(selected, axis=1)


def _finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _replay(trace: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    monitor = SplitAccelerationMonitorV1()
    rows = []
    torque_trace = trace.get("shadow_robot_joint_torque_command_nm")
    torque_available_trace = trace.get("shadow_robot_joint_torque_available")
    measured_force = trace.get(
        "deployable_measured_cuff_force_world_n",
        trace["physical_cuff_force_world_n"],
    )
    measured_moment = trace.get(
        "deployable_measured_cuff_moment_world_nm",
        trace["physical_cuff_moment_world_nm"],
    )
    for index, timestamp in enumerate(trace["time_s"]):
        torque = None
        if torque_trace is not None and (
            torque_available_trace is None or bool(torque_available_trace[index])
        ):
            torque = torque_trace[index]
        rows.append(
            monitor.update(
                sample_timestamp_s=float(timestamp),
                estimated_dq_rad_s=trace["estimated_state_rad_rad_s"][index, 2:],
                cuff_force_world_n=measured_force[index],
                cuff_moment_world_nm=measured_moment[index],
                interface_translation_human_m=trace[
                    "estimated_interface_translation_human_m"
                ][index],
                interface_velocity_human_m_s=trace[
                    "estimated_interface_velocity_human_m_s"
                ][index],
                interface_rotation_human_rad=trace[
                    "estimated_interface_rotation_human_rad"
                ][index],
                interface_angular_velocity_human_rad_s=trace[
                    "estimated_interface_angular_velocity_human_rad_s"
                ][index],
                command_wrench_world=trace["executed_command_wrench_world"][index],
                robot_joint_torque_command_nm=torque,
            )
        )
    return {
        "human_acceleration": np.asarray(
            [row.human_motion_acceleration_rad_s2 for row in rows]
        ),
        "human_valid": np.asarray([row.human_motion_valid for row in rows]),
        "human_coverage": np.asarray(
            [row.human_motion_history_coverage_s for row in rows]
        ),
        "human_sample_count": np.asarray(
            [row.human_motion_history_sample_count for row in rows]
        ),
        "fast_acceleration": np.asarray(
            [row.fast_motion_acceleration_rad_s2 for row in rows]
        ),
        "fast_valid": np.asarray([row.fast_motion_valid for row in rows]),
        "fast_interval": np.asarray(
            [row.fast_alignment_interval_s for row in rows]
        ),
        "cuff_wrench": np.asarray([row.cuff_wrench_world for row in rows]),
        "cuff_slew": np.asarray(
            [row.cuff_wrench_slew_world_per_s for row in rows]
        ),
        "interface_translation": np.asarray(
            [row.interface_translation_human_m for row in rows]
        ),
        "interface_velocity": np.asarray(
            [row.interface_velocity_human_m_s for row in rows]
        ),
        "interface_rotation": np.asarray(
            [row.interface_rotation_human_rad for row in rows]
        ),
        "interface_angular_velocity": np.asarray(
            [row.interface_angular_velocity_human_rad_s for row in rows]
        ),
        "command_wrench": np.asarray([row.command_wrench_world for row in rows]),
        "command_slew": np.asarray(
            [row.command_wrench_slew_world_per_s for row in rows]
        ),
        "robot_torque": np.asarray(
            [row.robot_joint_torque_command_nm for row in rows]
        ),
        "robot_torque_slew": np.asarray(
            [row.robot_joint_torque_slew_nm_s for row in rows]
        ),
        "robot_torque_available": np.asarray(
            [row.robot_joint_torque_available for row in rows]
        ),
        "robot_torque_slew_valid": np.asarray(
            [row.robot_joint_torque_slew_valid for row in rows]
        ),
    }


def _load_case(spec: CaseSpec) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    directory = RESULTS_ROOT / spec.relative_directory
    with np.load(directory / "trace.npz", allow_pickle=False) as archive:
        trace = {name: archive[name] for name in archive.files}
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    return trace, summary


def _feature_series(replay: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "abs_fast_q2_acceleration_deg_s2": np.abs(
            np.degrees(replay["fast_acceleration"][:, 1])
        ),
        "cuff_force_norm_n": _norm_rows(replay["cuff_wrench"], slice(0, 3)),
        "cuff_force_slew_norm_n_s": _norm_rows(replay["cuff_slew"], slice(0, 3)),
        "cuff_moment_norm_nm": _norm_rows(replay["cuff_wrench"], slice(3, 6)),
        "cuff_moment_slew_norm_nm_s": _norm_rows(
            replay["cuff_slew"], slice(3, 6)
        ),
        "interface_translation_norm_mm": (
            1000.0 * _norm_rows(replay["interface_translation"])
        ),
        "interface_translation_rate_norm_mm_s": (
            1000.0 * _norm_rows(replay["interface_velocity"])
        ),
        "interface_rotation_norm_deg": np.degrees(
            _norm_rows(replay["interface_rotation"])
        ),
        "interface_rotation_rate_norm_deg_s": np.degrees(
            _norm_rows(replay["interface_angular_velocity"])
        ),
        "command_force_norm_n": _norm_rows(
            replay["command_wrench"], slice(0, 3)
        ),
        "command_force_slew_norm_n_s": _norm_rows(
            replay["command_slew"], slice(0, 3)
        ),
        "command_moment_norm_nm": _norm_rows(
            replay["command_wrench"], slice(3, 6)
        ),
        "command_moment_slew_norm_nm_s": _norm_rows(
            replay["command_slew"], slice(3, 6)
        ),
        "robot_joint_torque_norm_nm": _norm_rows(replay["robot_torque"]),
        "robot_joint_torque_slew_norm_nm_s": _norm_rows(
            replay["robot_torque_slew"]
        ),
    }


def _plot_event(
    output_path: Path,
    spec: CaseSpec,
    trace: dict[str, np.ndarray],
    replay: dict[str, np.ndarray],
    truth_5ms: np.ndarray,
    truth_20ms: np.ndarray,
    event_index: int,
) -> None:
    time = np.asarray(trace["time_s"], dtype=float)
    event_time = float(time[event_index])
    mask = (time >= event_time - 0.060 - 1.0e-12) & (
        time <= event_time + 0.020 + 1.0e-12
    )
    relative_ms = 1000.0 * (time[mask] - event_time)
    current = np.degrees(trace["deployable_realized_acceleration_rad_s2"])
    features = _feature_series(replay)

    fig, axes = plt.subplots(8, 1, figsize=(11.0, 19.0), sharex=True)
    axes[0].plot(relative_ms, current[mask, 1], label="current model q2", linewidth=1.5)
    axes[0].plot(
        relative_ms,
        np.degrees(replay["human_acceleration"][mask, 1]),
        label="shadow motion 20 ms",
    )
    axes[0].plot(
        relative_ms,
        np.degrees(replay["fast_acceleration"][mask, 1]),
        label="shadow motion 5 ms",
    )
    axes[0].plot(relative_ms, truth_20ms[mask, 1], "--", label="truth 20 ms")
    axes[0].plot(relative_ms, truth_5ms[mask, 1], ":", label="truth 5 ms")
    axes[0].axhline(600.0, color="black", linestyle="--", linewidth=0.8)
    axes[0].axhline(-600.0, color="black", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("q2 accel\n[deg/s²]")
    axes[0].legend(fontsize=7, ncol=3)

    paired_channels = (
        (1, "cuff_force_norm_n", "cuff_force_slew_norm_n_s", "cuff force", "N", "N/s"),
        (2, "cuff_moment_norm_nm", "cuff_moment_slew_norm_nm_s", "cuff moment", "Nm", "Nm/s"),
        (
            3,
            "interface_translation_norm_mm",
            "interface_translation_rate_norm_mm_s",
            "interface translation",
            "mm",
            "mm/s",
        ),
        (
            4,
            "interface_rotation_norm_deg",
            "interface_rotation_rate_norm_deg_s",
            "interface rotation",
            "deg",
            "deg/s",
        ),
        (5, "command_force_norm_n", "command_force_slew_norm_n_s", "command force", "N", "N/s"),
        (
            6,
            "command_moment_norm_nm",
            "command_moment_slew_norm_nm_s",
            "command moment",
            "Nm",
            "Nm/s",
        ),
        (
            7,
            "robot_joint_torque_norm_nm",
            "robot_joint_torque_slew_norm_nm_s",
            "robot torque",
            "Nm",
            "Nm/s",
        ),
    )
    for axis_index, value_key, rate_key, label, value_unit, rate_unit in paired_channels:
        axis = axes[axis_index]
        rate_axis = axis.twinx()
        axis.plot(
            relative_ms,
            features[value_key][mask],
            color="tab:blue",
            label=f"{label} norm",
        )
        rate_axis.plot(
            relative_ms,
            features[rate_key][mask],
            color="tab:orange",
            label=f"{label} slew/rate",
        )
        axis.set_ylabel(f"norm\n[{value_unit}]", color="tab:blue")
        rate_axis.set_ylabel(f"slew/rate\n[{rate_unit}]", color="tab:orange")
        axis.tick_params(axis="y", labelcolor="tab:blue")
        rate_axis.tick_params(axis="y", labelcolor="tab:orange")
        axis.legend(loc="upper left", fontsize=7)
        rate_axis.legend(loc="upper right", fontsize=7)

    torque = features["robot_joint_torque_slew_norm_nm_s"]
    if not np.any(np.isfinite(torque[mask])):
        axes[7].text(
            0.5,
            0.5,
            "historical torque trace unavailable",
            ha="center",
            va="center",
            transform=axes[7].transAxes,
        )
    axes[7].set_xlabel("time relative to selected event [ms]")
    for axis in axes:
        axis.axvline(0.0, color="tab:red", linewidth=1.0)
        axis.grid(alpha=0.25)
    fig.suptitle(f"{spec.name}: {spec.short_transient_role}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=170)
    plt.close(fig)


def audit_case(spec: CaseSpec, output_dir: Path) -> dict[str, Any]:
    trace, summary = _load_case(spec)
    replay = _replay(trace)
    time = np.asarray(trace["time_s"], dtype=float)
    truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    truth_5ms = np.degrees(_fixed_window(time, truth_dq, 1))
    truth_20ms = np.degrees(_fixed_window(time, truth_dq, 4))
    current = np.degrees(trace["deployable_realized_acceleration_rad_s2"])
    event_index = _event_index(
        spec.event_selection, current, truth_5ms, truth_20ms
    )
    features = _feature_series(replay)
    event_time = float(time[event_index])
    local_mask = (time >= event_time - 0.020 - 1.0e-12) & (
        time <= event_time + 0.020 + 1.0e-12
    )
    event_features = {
        name: _finite_or_none(values[event_index])
        for name, values in features.items()
    }
    local_peaks = {
        name: (
            _finite_or_none(np.nanmax(values[local_mask]))
            if np.any(np.isfinite(values[local_mask]))
            else None
        )
        for name, values in features.items()
    }
    torque_available = bool(replay["robot_torque_available"][event_index])
    human_error_deg_s2 = np.degrees(replay["human_acceleration"])[
        replay["human_valid"]
    ] - truth_20ms[replay["human_valid"]]
    alignment = {
        "trace_lengths_equal": all(
            len(values) == len(time) for values in replay.values()
        ),
        "all_valid_fast_intervals_are_5ms": bool(
            np.allclose(
                replay["fast_interval"][replay["fast_valid"]],
                SAMPLE_PERIOD_S,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "all_valid_human_samples_have_full_20ms_coverage": bool(
            np.allclose(
                replay["human_coverage"][replay["human_valid"]],
                0.020,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "command_wrench_exactly_replayed": bool(
            np.array_equal(
                replay["command_wrench"], trace["executed_command_wrench_world"]
            )
        ),
        "online_shadow_trace_exactly_replayed": None,
    }
    if "shadow_human_motion_acceleration_rad_s2" in trace:
        online_fields = {
            "human_acceleration": "shadow_human_motion_acceleration_rad_s2",
            "human_valid": "shadow_human_motion_valid",
            "human_coverage": "shadow_human_motion_history_coverage_s",
            "fast_acceleration": "shadow_fast_motion_acceleration_rad_s2",
            "fast_valid": "shadow_fast_motion_valid",
            "cuff_wrench": "shadow_cuff_wrench_world",
            "cuff_slew": "shadow_cuff_wrench_slew_world_per_s",
            "command_wrench": "shadow_command_wrench_world",
            "command_slew": "shadow_command_wrench_slew_world_per_s",
            "robot_torque": "shadow_robot_joint_torque_command_nm",
            "robot_torque_slew": "shadow_robot_joint_torque_slew_nm_s",
        }
        exact = True
        for replay_name, trace_name in online_fields.items():
            exact = exact and np.array_equal(
                replay[replay_name], trace[trace_name], equal_nan=True
            )
        alignment["online_shadow_trace_exactly_replayed"] = exact

    plot_name = f"{spec.name}_event_window.png"
    _plot_event(
        output_dir / plot_name,
        spec,
        trace,
        replay,
        truth_5ms,
        truth_20ms,
        event_index,
    )
    return {
        "name": spec.name,
        "trace_path": str(
            (RESULTS_ROOT / spec.relative_directory / "trace.npz").relative_to(
                STAGE5_ROOT
            )
        ),
        "plot": plot_name,
        "event_selection": spec.event_selection,
        "short_transient_role": spec.short_transient_role,
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "event": {
            "timestamp_s": event_time,
            "current_model_acceleration_deg_s2": current[event_index].tolist(),
            "shadow_human_20ms_acceleration_deg_s2": (
                None
                if not replay["human_valid"][event_index]
                else np.degrees(replay["human_acceleration"][event_index]).tolist()
            ),
            "shadow_human_20ms_valid": bool(replay["human_valid"][event_index]),
            "shadow_human_20ms_coverage_s": float(
                replay["human_coverage"][event_index]
            ),
            "shadow_fast_5ms_acceleration_deg_s2": (
                None
                if not replay["fast_valid"][event_index]
                else np.degrees(replay["fast_acceleration"][event_index]).tolist()
            ),
            "truth_20ms_acceleration_deg_s2": (
                None
                if not np.all(np.isfinite(truth_20ms[event_index]))
                else truth_20ms[event_index].tolist()
            ),
            "truth_5ms_acceleration_deg_s2": (
                None
                if not np.all(np.isfinite(truth_5ms[event_index]))
                else truth_5ms[event_index].tolist()
            ),
            "features": event_features,
            "local_plus_minus_20ms_feature_peaks": local_peaks,
            "robot_joint_torque_available": torque_available,
            "robot_joint_torque_command_nm": (
                replay["robot_torque"][event_index].tolist()
                if torque_available
                else None
            ),
        },
        "alignment_checks": alignment,
        "whole_trace_human_channel": {
            "valid_sample_count": int(np.count_nonzero(replay["human_valid"])),
            "rmse_deg_s2": (
                np.sqrt(np.mean(human_error_deg_s2**2, axis=0)).tolist()
                if len(human_error_deg_s2)
                else None
            ),
            "peak_abs_error_deg_s2": (
                np.max(np.abs(human_error_deg_s2), axis=0).tolist()
                if len(human_error_deg_s2)
                else None
            ),
            "false_positive_samples": int(
                np.count_nonzero(
                    _over_limit(
                        np.degrees(replay["human_acceleration"])[
                            replay["human_valid"]
                        ]
                    )
                    & ~_over_limit(truth_20ms[replay["human_valid"]])
                )
            ),
            "false_negative_samples": int(
                np.count_nonzero(
                    ~_over_limit(
                        np.degrees(replay["human_acceleration"])[
                            replay["human_valid"]
                        ]
                    )
                    & _over_limit(truth_20ms[replay["human_valid"]])
                )
            ),
            "true_positive_samples": int(
                np.count_nonzero(
                    _over_limit(
                        np.degrees(replay["human_acceleration"])[
                            replay["human_valid"]
                        ]
                    )
                    & _over_limit(truth_20ms[replay["human_valid"]])
                )
            ),
        },
    }


def _cr12_authority_invariance() -> dict[str, Any]:
    old_directory = (
        RESULTS_ROOT
        / "cr12_provisional_cuff_baseline_20260918_attempt_02"
        / "execution"
    )
    new_directory = (
        RESULTS_ROOT / "cr12_split_monitor_shadow_20260918_attempt_02" / "execution"
    )
    with np.load(old_directory / "trace.npz", allow_pickle=False) as old_archive:
        old_trace = {name: old_archive[name] for name in old_archive.files}
    with np.load(new_directory / "trace.npz", allow_pickle=False) as new_archive:
        new_trace = {name: new_archive[name] for name in new_archive.files}
    common = sorted(set(old_trace) & set(new_trace))
    changed = []
    for name in common:
        old = old_trace[name]
        new = new_trace[name]
        equal = (
            np.array_equal(old, new, equal_nan=True)
            if np.issubdtype(old.dtype, np.number)
            else np.array_equal(old, new)
        )
        if not equal:
            changed.append(name)
    old_summary = json.loads((old_directory / "summary.json").read_text())
    new_summary = json.loads((new_directory / "summary.json").read_text())
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
        "old_trace": str((old_directory / "trace.npz").relative_to(STAGE5_ROOT)),
        "new_trace": str((new_directory / "trace.npz").relative_to(STAGE5_ROOT)),
        "common_trace_field_count": len(common),
        "nonidentical_common_trace_fields": changed,
        "all_common_trace_fields_bitwise_identical": not changed,
        "summary_authority_fields_equal": {
            name: old_summary[name] == new_summary[name] for name in authority_fields
        },
        "existing_abort_preserved": bool(
            new_summary["task_status"] == "ABORTED"
            and new_summary["abort_reason"] == "TASK_ACCELERATION_LIMIT"
        ),
    }


def _separation(cases: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    true_cases = [
        row for row in cases if row["short_transient_role"] == "true_short_transient"
    ]
    benign_cases = [
        row for row in cases if row["short_transient_role"] != "true_short_transient"
    ]
    feature_names = list(true_cases[0]["event"][scope])
    rows = []
    for name in feature_names:
        true_values = [row["event"][scope][name] for row in true_cases]
        benign_values = [row["event"][scope][name] for row in benign_cases]
        true_finite = [float(value) for value in true_values if value is not None]
        benign_finite = [float(value) for value in benign_values if value is not None]
        if len(true_finite) != len(true_cases) or not benign_finite:
            rows.append(
                {
                    "feature": name,
                    "all_cases_available": False,
                    "strict_selected_case_separation": None,
                }
            )
            continue
        minimum_true = min(true_finite)
        maximum_benign = max(benign_finite)
        rows.append(
            {
                "feature": name,
                "all_cases_available": True,
                "minimum_true_short_transient": minimum_true,
                "maximum_benign": maximum_benign,
                "minimum_true_minus_maximum_benign": minimum_true - maximum_benign,
                "strict_selected_case_separation": bool(
                    minimum_true > maximum_benign
                ),
            }
        )
    return rows


def _write_csv(output_path: Path, cases: list[dict[str, Any]]) -> None:
    feature_names = list(cases[0]["event"]["features"])
    fieldnames = [
        "name",
        "timestamp_s",
        "short_transient_role",
        "current_q2_deg_s2",
        "human_20ms_q2_deg_s2",
        "truth_20ms_q2_deg_s2",
        "fast_5ms_q2_deg_s2",
        "truth_5ms_q2_deg_s2",
        *feature_names,
        "robot_joint_torque_available",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in cases:
            event = row["event"]
            human = event["shadow_human_20ms_acceleration_deg_s2"]
            truth_20ms = event["truth_20ms_acceleration_deg_s2"]
            fast = event["shadow_fast_5ms_acceleration_deg_s2"]
            truth_5ms = event["truth_5ms_acceleration_deg_s2"]
            record = {
                "name": row["name"],
                "timestamp_s": event["timestamp_s"],
                "short_transient_role": row["short_transient_role"],
                "current_q2_deg_s2": event["current_model_acceleration_deg_s2"][1],
                "human_20ms_q2_deg_s2": None if human is None else human[1],
                "truth_20ms_q2_deg_s2": (
                    None if truth_20ms is None else truth_20ms[1]
                ),
                "fast_5ms_q2_deg_s2": None if fast is None else fast[1],
                "truth_5ms_q2_deg_s2": None if truth_5ms is None else truth_5ms[1],
                "robot_joint_torque_available": event[
                    "robot_joint_torque_available"
                ],
            }
            record.update(event["features"])
            writer.writerow(record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_ROOT / "split_acceleration_monitor_v1_audit",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cases = [audit_case(spec, args.output_dir) for spec in CASES]
    payload = {
        "schema": "stage5_split_acceleration_monitor_v1_audit",
        "evidence_category": "diagnostic_saved_trace_replay_plus_cr12_smoke",
        "shadow_only": True,
        "abort_authority_changed": False,
        "hard_transient_threshold_registered": False,
        "registered_human_motion_limit_deg_s2": LIMIT_DEG_S2.tolist(),
        "cases": cases,
        "event_point_feature_separation": _separation(cases, "features"),
        "local_plus_minus_20ms_peak_separation": _separation(
            cases, "local_plus_minus_20ms_feature_peaks"
        ),
        "cr12_authority_invariance": _cr12_authority_invariance(),
    }
    (args.output_dir / "split_acceleration_monitor_v1_audit.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(args.output_dir / "diagnostic_matrix.csv", cases)
    print(args.output_dir)


if __name__ == "__main__":
    main()
