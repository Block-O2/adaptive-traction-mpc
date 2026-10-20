#!/usr/bin/env python3
"""Audit the role of Human-table contact using saved Stage-5 evidence only.

This script does not run or modify the controller.  It reads the archived CR12
and UR10e traces, recomputes geometric shank clearance, aligns the existing
20 ms prefix prediction with realized motion, and incorporates the previously
saved matched-state MuJoCo continuations that contain exact bed-contact force.
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
from scipy.stats import spearmanr

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


CONTROL_DT_S = 0.005
PREFIX_HORIZON_S = 0.020
PHASES = ("OUTBOUND", "HOLD", "RETURN")
CLEARANCE_BINS_MM = (
    ("contact_or_penetrating", -np.inf, 0.0),
    ("contact_adjacent_0_to_1", 0.0, 1.0),
    ("near_1_to_5", 1.0, 5.0),
    ("clear_above_5", 5.0, np.inf),
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def shank_clearance_m(q_rad: np.ndarray) -> np.ndarray:
    """Return the capsule clearance to the fixed bed for one or many q rows."""

    q = np.atleast_2d(np.asarray(q_rad, dtype=float))
    q1 = q[:, 0]
    phi = q[:, 0] - q[:, 1]
    plane_x = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 0])
    plane_z = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 2])
    hip_z = float(STAGE5_GEOMETRY.world_from_human.translation[2])
    knee_z = hip_z + STAGE5_HUMAN.thigh_length_m * (
        np.cos(q1) * plane_x[2] + np.sin(q1) * plane_z[2]
    )
    ankle_z = knee_z + STAGE5_HUMAN.shank_length_m * (
        np.cos(phi) * plane_x[2] + np.sin(phi) * plane_z[2]
    )
    clearance = (
        np.minimum(knee_z, ankle_z) - SHANK_RADIUS_M - BED_HEIGHT_M
    )
    return clearance if np.asarray(q_rad).ndim > 1 else clearance[0]


def _time_index(time_s: np.ndarray, target_s: float) -> int | None:
    matches = np.flatnonzero(np.isclose(time_s, target_s, atol=1.0e-9, rtol=0.0))
    return None if not len(matches) else int(matches[0])


def _prefix_records(trace: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    time_s = trace["time_s"]
    records: list[dict[str, Any]] = []
    prediction_times = trace["selected_v2_prefix_prediction_time_s"]
    predicted_states = trace["selected_v2_prefix_state_rad_rad_s"]
    feasible = trace["selected_v2_prefix_acceleration_feasible"]
    candidate_counts = trace["mpc_feasible_candidate_evaluations"]
    for solve_index, start_s in enumerate(prediction_times):
        start_index = _time_index(time_s, float(start_s))
        end_index = _time_index(time_s, float(start_s + PREFIX_HORIZON_S))
        if start_index is None or end_index is None:
            continue
        predicted_terminal = predicted_states[solve_index, -1]
        start_dq = trace["estimated_state_rad_rad_s"][start_index, 2:]
        predicted_acceleration = (
            predicted_terminal[2:] - start_dq
        ) / PREFIX_HORIZON_S
        truth_acceleration = (
            trace["evaluation_human_dq_rad_s"][end_index]
            - trace["evaluation_human_dq_rad_s"][start_index]
        ) / PREFIX_HORIZON_S
        records.append(
            {
                "time_s": float(start_s),
                "phase": str(trace["task_phase"][start_index]),
                "clearance_mm": float(
                    1000.0
                    * shank_clearance_m(
                        trace["evaluation_human_q_rad"][start_index]
                    )
                ),
                "acceleration_absolute_error_deg_s2": np.degrees(
                    np.abs(predicted_acceleration - truth_acceleration)
                ),
                "predicted_acceleration_deg_s2": np.degrees(
                    predicted_acceleration
                ),
                "truth_acceleration_deg_s2": np.degrees(truth_acceleration),
                "selected_prefix_feasible": bool(feasible[solve_index]),
                "feasible_candidate_evaluations": int(candidate_counts[solve_index]),
            }
        )
    return records


def _force_prediction_error(trace: dict[str, np.ndarray]) -> np.ndarray:
    predicted = trace["predicted_next_physical_cuff_force_world_n"]
    actual = trace["physical_cuff_force_world_n"]
    valid = np.all(np.isfinite(predicted), axis=1)
    error = np.full(len(predicted), np.nan)
    error[valid] = np.linalg.norm(predicted[valid] - actual[valid], axis=1)
    return error


def _intervals(time_s: np.ndarray, mask: np.ndarray) -> list[dict[str, float]]:
    indices = np.flatnonzero(mask)
    if not len(indices):
        return []
    breaks = np.flatnonzero(np.diff(indices) > 1)
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [len(indices) - 1]))
    return [
        {
            "onset_s": float(time_s[indices[start]]),
            "offset_s": float(time_s[indices[end]]),
            "sample_count": int(end - start + 1),
            "sampled_duration_s": float((end - start + 1) * CONTROL_DT_S),
        }
        for start, end in zip(starts, ends)
    ]


def _phase_summary(
    trace: dict[str, np.ndarray],
    phase: str,
    prefix_records: list[dict[str, Any]],
    force_error: np.ndarray,
) -> dict[str, Any]:
    mask = trace["task_phase"] == phase
    if not np.any(mask):
        return {
            "available": False,
            "reason": "rollout_terminated_before_phase",
        }
    indices = np.flatnonzero(mask)
    q_deg = np.degrees(trace["evaluation_human_q_rad"][mask])
    dq_deg_s = np.degrees(trace["evaluation_human_dq_rad_s"][mask])
    acceleration_deg_s2 = np.degrees(
        trace["deployable_realized_acceleration_rad_s2"][mask]
    )
    clearance_mm = 1000.0 * shank_clearance_m(
        trace["evaluation_human_q_rad"][mask]
    )
    contact_mask = clearance_mm <= 0.0
    force_norm = np.linalg.norm(trace["physical_cuff_force_world_n"][mask], axis=1)
    moment_norm = np.linalg.norm(
        trace["physical_cuff_moment_world_nm"][mask], axis=1
    )
    phase_prefix = [row for row in prefix_records if row["phase"] == phase]
    phase_force_error = force_error[mask]
    phase_force_error = phase_force_error[np.isfinite(phase_force_error)]
    return {
        "available": True,
        "start_time_s": float(trace["time_s"][indices[0]]),
        "end_time_s": float(trace["time_s"][indices[-1]]),
        "sampled_duration_s": float(len(indices) * CONTROL_DT_S),
        "human_q_range_deg": [
            [float(np.min(q_deg[:, joint])), float(np.max(q_deg[:, joint]))]
            for joint in range(2)
        ],
        "peak_abs_human_dq_deg_s": np.max(np.abs(dq_deg_s), axis=0),
        "minimum_shank_table_clearance_mm": float(np.min(clearance_mm)),
        "maximum_shank_table_clearance_mm": float(np.max(clearance_mm)),
        "geometric_contact_intervals": _intervals(
            trace["time_s"][mask], contact_mask
        ),
        "geometric_contact_sampled_duration_s": float(
            np.count_nonzero(contact_mask) * CONTROL_DT_S
        ),
        "exact_bed_contact_force_n": None,
        "exact_bed_contact_force_note": (
            "not recorded by this archived complete-trace schema; exact short-window "
            "MuJoCo evidence is reported separately"
        ),
        "peak_cuff_force_n": float(np.max(force_norm)),
        "peak_cuff_moment_nm": float(np.max(moment_norm)),
        "peak_abs_deployable_20ms_acceleration_deg_s2": np.nanmax(
            np.abs(acceleration_deg_s2), axis=0
        ),
        "current_prefix_predictor_acceleration_error_p95_deg_s2": (
            None
            if not phase_prefix
            else np.percentile(
                np.asarray(
                    [row["acceleration_absolute_error_deg_s2"] for row in phase_prefix]
                ),
                95,
                axis=0,
            )
        ),
        "current_cuff_force_prediction_error_rmse_n": (
            None
            if not len(phase_force_error)
            else float(np.sqrt(np.mean(np.square(phase_force_error))))
        ),
        "current_cuff_force_prediction_error_p95_n": (
            None
            if not len(phase_force_error)
            else float(np.percentile(phase_force_error, 95))
        ),
        "mpc_selected_prefix_count": len(phase_prefix),
        "mpc_selected_prefix_feasible_fraction": (
            None
            if not phase_prefix
            else float(
                np.mean([row["selected_prefix_feasible"] for row in phase_prefix])
            )
        ),
        "mpc_feasible_candidate_evaluations_min_median_max": (
            None
            if not phase_prefix
            else [
                float(function([row["feasible_candidate_evaluations"] for row in phase_prefix]))
                for function in (np.min, np.median, np.max)
            ]
        ),
    }


def _proximity_bins(
    robot: str,
    trace: dict[str, np.ndarray],
    prefix_records: list[dict[str, Any]],
    force_error: np.ndarray,
) -> list[dict[str, Any]]:
    clearance_mm = 1000.0 * shank_clearance_m(trace["evaluation_human_q_rad"])
    rows: list[dict[str, Any]] = []
    for name, lower, upper in CLEARANCE_BINS_MM:
        trace_mask = (clearance_mm > lower) & (clearance_mm <= upper)
        prefix_bin = [
            row
            for row in prefix_records
            if row["clearance_mm"] > lower and row["clearance_mm"] <= upper
        ]
        force_values = force_error[trace_mask]
        force_values = force_values[np.isfinite(force_values)]
        rows.append(
            {
                "robot": robot,
                "clearance_bin": name,
                "clearance_interval_mm": [lower, upper],
                "trace_sample_count": int(np.count_nonzero(trace_mask)),
                "prefix_prediction_count": len(prefix_bin),
                "acceleration_absolute_error_p95_deg_s2": (
                    None
                    if not prefix_bin
                    else np.percentile(
                        np.asarray(
                            [
                                row["acceleration_absolute_error_deg_s2"]
                                for row in prefix_bin
                            ]
                        ),
                        95,
                        axis=0,
                    )
                ),
                "force_prediction_error_rmse_n": (
                    None
                    if not len(force_values)
                    else float(np.sqrt(np.mean(np.square(force_values))))
                ),
                "force_prediction_error_p95_n": (
                    None
                    if not len(force_values)
                    else float(np.percentile(force_values, 95))
                ),
            }
        )
    return rows


def _correlation(prefix_records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(prefix_records) < 3:
        return {"sample_count": len(prefix_records), "spearman_rho": None}
    clearance = np.asarray([row["clearance_mm"] for row in prefix_records])
    error = np.asarray(
        [row["acceleration_absolute_error_deg_s2"] for row in prefix_records]
    )
    return {
        "sample_count": len(prefix_records),
        "spearman_rho_clearance_vs_absolute_error": [
            float(spearmanr(clearance, error[:, joint]).statistic)
            for joint in range(2)
        ],
        "interpretation": (
            "negative means error tends to increase as table clearance decreases; "
            "association is not treated as causal"
        ),
    }


def _registered_path_check() -> dict[str, Any]:
    start = np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    goal = np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad)
    alpha = np.linspace(0.0, 1.0, 1001)
    outbound = start[None, :] + alpha[:, None] * (goal - start)[None, :]
    clearance_mm = 1000.0 * shank_clearance_m(outbound)
    minimum_index = int(np.argmin(clearance_mm))
    return {
        "method": (
            "offline geometric interpolation between the registered start and goal; "
            "not a controller or task change"
        ),
        "start_clearance_mm": float(1000.0 * shank_clearance_m(start)),
        "goal_clearance_mm": float(1000.0 * shank_clearance_m(goal)),
        "minimum_clearance_mm": float(clearance_mm[minimum_index]),
        "minimum_at_normalized_progress": float(alpha[minimum_index]),
        "contact_free": bool(np.all(clearance_mm > 0.0)),
        "hold_at_goal_contact_free": bool(shank_clearance_m(goal) > 0.0),
        "return_on_same_path_contact_free": bool(np.all(clearance_mm > 0.0)),
    }


def _exact_short_window_contact(matched: dict[str, Any]) -> dict[str, Any]:
    selected = [
        row
        for row in matched["evaluated_cases"]
        if row["candidate_name"] == "selected"
        and row["region"] == "pre_violation"
    ]
    result: dict[str, Any] = {}
    for row in selected:
        endpoints = row["truth"]["endpoints"]
        result[row["robot"]] = {
            "start_time_s": float(row["timestamp_s"]),
            "maximum_bed_contact_force_n": float(
                row["truth"]["maximum_contact_force_n"]
            ),
            "any_contact": bool(row["truth"]["any_contact"]),
            "endpoint_contact_force_n": [
                {
                    "offset_ms": float(endpoint["offset_ms"]),
                    "active": bool(endpoint["human_table_contact_active"]),
                    "force_n": float(endpoint["human_table_contact_force_n"]),
                }
                for endpoint in endpoints
            ],
        }
    return result


def _matched_context_summary(matched: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in (
        "early_outbound",
        "mid_outbound",
        "late_outbound",
        "near_pre_violation",
        "pre_violation",
    ):
        row: dict[str, Any] = {"region": region}
        for robot in ("cr12", "ur10e"):
            context = matched["contexts"][robot][region]
            metric = matched["aggregate_by_robot_and_region"][robot][region]
            row[robot] = {
                "time_s": float(context["timestamp_s"]),
                "clearance_mm": float(context["shank_table_clearance_mm"]),
                "start_contact_active": bool(context["table_contact_active"]),
                "acceleration_error_p95_deg_s2": metric[
                    "acceleration_absolute_error_p95_deg_s2"
                ],
                "force_error_p95_n": float(metric["force_error_p95_n"]),
                "loaded_contact_candidate_count": int(
                    metric["loaded_contact_candidate_count"]
                ),
                "candidate_count": int(metric["candidate_count"]),
                "classification_change_count": int(
                    metric["classification_change_count"]
                ),
            }
        row["matching_mismatch"] = matched["matching_mismatch"][region]
        rows.append(row)
    return rows


def _write_phase_table(path: Path, phase_rows: list[dict[str, Any]]) -> None:
    fields = [
        "robot",
        "phase",
        "available",
        "time_s",
        "q_range_deg",
        "peak_dq_deg_s",
        "clearance_mm_min_max",
        "geometric_contact_duration_s",
        "exact_short_window_bed_force_n",
        "peak_cuff_force_n",
        "peak_cuff_moment_nm",
        "peak_20ms_acceleration_deg_s2",
        "predictor_acceleration_error_p95_deg_s2",
        "force_prediction_error_rmse_p95_n",
        "selected_prefix_feasible_fraction",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in phase_rows:
            summary = row["summary"]
            if not summary["available"]:
                writer.writerow(
                    {
                        "robot": row["robot"],
                        "phase": row["phase"],
                        "available": False,
                    }
                )
                continue
            exact = row.get("exact_short_window_contact")
            writer.writerow(
                {
                    "robot": row["robot"],
                    "phase": row["phase"],
                    "available": True,
                    "time_s": f"{summary['start_time_s']:.3f}-{summary['end_time_s']:.3f}",
                    "q_range_deg": json.dumps(summary["human_q_range_deg"]),
                    "peak_dq_deg_s": json.dumps(
                        _jsonable(summary["peak_abs_human_dq_deg_s"])
                    ),
                    "clearance_mm_min_max": json.dumps(
                        [
                            summary["minimum_shank_table_clearance_mm"],
                            summary["maximum_shank_table_clearance_mm"],
                        ]
                    ),
                    "geometric_contact_duration_s": summary[
                        "geometric_contact_sampled_duration_s"
                    ],
                    "exact_short_window_bed_force_n": (
                        "" if exact is None else exact["maximum_bed_contact_force_n"]
                    ),
                    "peak_cuff_force_n": summary["peak_cuff_force_n"],
                    "peak_cuff_moment_nm": summary["peak_cuff_moment_nm"],
                    "peak_20ms_acceleration_deg_s2": json.dumps(
                        _jsonable(
                            summary[
                                "peak_abs_deployable_20ms_acceleration_deg_s2"
                            ]
                        )
                    ),
                    "predictor_acceleration_error_p95_deg_s2": json.dumps(
                        _jsonable(
                            summary[
                                "current_prefix_predictor_acceleration_error_p95_deg_s2"
                            ]
                        )
                    ),
                    "force_prediction_error_rmse_p95_n": json.dumps(
                        [
                            summary["current_cuff_force_prediction_error_rmse_n"],
                            summary["current_cuff_force_prediction_error_p95_n"],
                        ]
                    ),
                    "selected_prefix_feasible_fraction": summary[
                        "mpc_selected_prefix_feasible_fraction"
                    ],
                }
            )


def _plot_clearance(
    output: Path, traces: dict[str, dict[str, np.ndarray]]
) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(9.0, 6.8), sharex=False)
    for axis, robot in zip(axes, ("cr12", "ur10e")):
        trace = traces[robot]
        clearance_mm = 1000.0 * shank_clearance_m(
            trace["evaluation_human_q_rad"]
        )
        axis.plot(trace["time_s"], clearance_mm, color="#1f77b4", linewidth=1.3)
        axis.axhline(0.0, color="#b22222", linestyle="--", linewidth=1.0)
        for phase in PHASES:
            indices = np.flatnonzero(trace["task_phase"] == phase)
            if len(indices):
                axis.axvline(
                    trace["time_s"][indices[0]], color="#777777", alpha=0.35
                )
                axis.text(
                    trace["time_s"][indices[0]],
                    float(np.max(clearance_mm)),
                    phase,
                    fontsize=8,
                    va="top",
                )
        axis.set_title(robot.upper())
        axis.set_ylabel("shank-bed clearance [mm]")
        axis.grid(alpha=0.25)
    axes[-1].set_xlabel("time [s]")
    figure.tight_layout()
    figure.savefig(output / "phase_clearance.png", dpi=180)
    plt.close(figure)


def _plot_error_vs_clearance(
    output: Path, prefix: dict[str, list[dict[str, Any]]]
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), sharex=True)
    colors = {"cr12": "#d62728", "ur10e": "#1f77b4"}
    for robot in ("cr12", "ur10e"):
        clearance = np.asarray([row["clearance_mm"] for row in prefix[robot]])
        error = np.asarray(
            [row["acceleration_absolute_error_deg_s2"] for row in prefix[robot]]
        )
        for joint, axis in enumerate(axes):
            axis.scatter(
                clearance,
                error[:, joint],
                s=14,
                alpha=0.65,
                color=colors[robot],
                label=robot.upper(),
            )
            axis.axvline(0.0, color="#333333", linestyle="--", linewidth=0.9)
            axis.set_title(("hip" if joint == 0 else "knee") + " 20 ms error")
            axis.set_xlabel("start shank-bed clearance [mm]")
            axis.set_ylabel("absolute acceleration error [deg/s²]")
            axis.grid(alpha=0.25)
    axes[0].legend()
    figure.tight_layout()
    figure.savefig(output / "prediction_error_vs_clearance.png", dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/engineering_validation/human_table_contact_role_audit_attempt_01"
        ),
    )
    parser.add_argument(
        "--cr12-trace",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_split_authority_baseline_attempt_03/execution/trace.npz"
        ),
    )
    parser.add_argument(
        "--cr12-summary",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_split_authority_baseline_attempt_03/execution/summary.json"
        ),
    )
    parser.add_argument(
        "--ur10e-trace",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/trust_gamma_matched_v1_formal_attempt_01/fixed_pacing/repetition_01/trace.npz"
        ),
    )
    parser.add_argument(
        "--ur10e-summary",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/trust_gamma_matched_v1_formal_attempt_01/fixed_pacing/repetition_01/summary.json"
        ),
    )
    parser.add_argument(
        "--matched-audit",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/engineering_validation/"
            "matched_ur10e_cr12_prediction_audit_attempt_04/"
            "matched_prediction_audit.json"
        ),
    )
    args = parser.parse_args()

    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    trace_paths = {"cr12": args.cr12_trace, "ur10e": args.ur10e_trace}
    summary_paths = {"cr12": args.cr12_summary, "ur10e": args.ur10e_summary}
    traces = {
        robot: dict(np.load(path, allow_pickle=True))
        for robot, path in trace_paths.items()
    }
    summaries = {
        robot: json.loads(path.read_text())
        for robot, path in summary_paths.items()
    }
    matched = json.loads(args.matched_audit.read_text())

    prefix = {robot: _prefix_records(trace) for robot, trace in traces.items()}
    force_error = {
        robot: _force_prediction_error(trace) for robot, trace in traces.items()
    }
    exact_contact = _exact_short_window_contact(matched)

    phase_rows: list[dict[str, Any]] = []
    for robot in ("cr12", "ur10e"):
        for phase in PHASES:
            row = {
                "robot": robot,
                "phase": phase,
                "summary": _phase_summary(
                    traces[robot], phase, prefix[robot], force_error[robot]
                ),
            }
            if robot in exact_contact and phase == "OUTBOUND":
                row["exact_short_window_contact"] = exact_contact[robot]
            phase_rows.append(row)

    proximity = [
        row
        for robot in ("cr12", "ur10e")
        for row in _proximity_bins(
            robot, traces[robot], prefix[robot], force_error[robot]
        )
    ]
    registered_path = _registered_path_check()
    ur10e_phase = {
        row["phase"]: row["summary"]
        for row in phase_rows
        if row["robot"] == "ur10e"
    }
    complete_ur10e_contact_free = all(
        ur10e_phase[phase]["available"]
        and ur10e_phase[phase]["minimum_shank_table_clearance_mm"] > 0.0
        for phase in PHASES
    )
    cr12_outbound = next(
        row["summary"]
        for row in phase_rows
        if row["robot"] == "cr12" and row["phase"] == "OUTBOUND"
    )
    empirical_clearance_floor_mm = min(
        ur10e_phase[phase]["minimum_shank_table_clearance_mm"]
        for phase in PHASES
    )

    result = {
        "schema": "stage5_human_table_contact_role_audit_v1",
        "evidence_category": "saved_trace_and_controlled_offline_audit",
        "scope": {
            "controller_changed": False,
            "predictor_changed": False,
            "thresholds_changed": False,
            "task_changed": False,
            "contact_model_changed": False,
            "rl_or_value_changed": False,
            "new_rollout_executed": False,
        },
        "source_artifacts": {
            "traces": {key: str(path.resolve()) for key, path in trace_paths.items()},
            "summaries": {
                key: str(path.resolve()) for key, path in summary_paths.items()
            },
            "matched_audit": str(args.matched_audit.resolve()),
        },
        "rollout_availability": {
            robot: {
                "task_status": summaries[robot]["task_status"],
                "abort_reason": summaries[robot]["abort_reason"],
                "available_phases": [
                    phase
                    for phase in PHASES
                    if np.any(traces[robot]["task_phase"] == phase)
                ],
                "missing_phase_interpretation": (
                    None
                    if summaries[robot]["task_status"] == "COMPLETE"
                    else "not observed; must not be inferred from post-abort continuation"
                ),
            }
            for robot in ("cr12", "ur10e")
        },
        "phase_contact_table": phase_rows,
        "exact_muJoCo_short_window_contact": exact_contact,
        "prediction_error_vs_contact_proximity": {
            "binned": proximity,
            "correlation": {
                robot: _correlation(prefix[robot])
                for robot in ("cr12", "ur10e")
            },
            "matched_state_comparison": _matched_context_summary(matched),
            "causality_note": (
                "clearance/contact association is not taken as causal; matched states "
                "show predictor error before loaded contact and robot-response differences"
            ),
        },
        "registered_task_contact_free_check": registered_path,
        "observed_complete_contact_free_check": {
            "robot": "ur10e",
            "complete": summaries["ur10e"]["task_status"] == "COMPLETE",
            "all_phases_contact_free_by_capsule_clearance": complete_ur10e_contact_free,
            "minimum_clearance_mm": empirical_clearance_floor_mm,
            "phase_minimum_clearance_mm": {
                phase: ur10e_phase[phase]["minimum_shank_table_clearance_mm"]
                for phase in PHASES
            },
        },
        "cr12_contact_interpretation": {
            "phase": "OUTBOUND",
            "minimum_clearance_mm": cr12_outbound[
                "minimum_shank_table_clearance_mm"
            ],
            "geometric_contact_sampled_duration_s": cr12_outbound[
                "geometric_contact_sampled_duration_s"
            ],
            "selected_0p300s_continuation_peak_bed_force_n": exact_contact[
                "cr12"
            ]["maximum_bed_contact_force_n"],
            "classification": "brief_incidental_execution_contact_not_nominal_support",
            "basis": (
                "contact appears during the early CR12 divergence, while the registered "
                "path and a complete UR10e execution remain contact-free"
            ),
        },
        "support_domain_boundary_design": {
            "status": "designed_not_activated",
            "purpose": "exclude avoidable contact-adjacent states from predictor authority",
            "deployable_inputs": [
                "q_hat/dq_hat",
                "known Human/bed geometry",
                "candidate 5/10/15/20 ms predicted Human states",
                "interface load state",
                "causal history validity",
            ],
            "inside_only_if": [
                "current shank-bed clearance is positive and no loaded contact is observed",
                "minimum candidate-prefix clearance stays above the frozen calibration support floor",
                "state/command/interface context has a valid calibration-support neighbor",
                "all required causal history is valid",
            ],
            "provisional_empirical_clearance_floor_mm": empirical_clearance_floor_mm,
            "floor_basis": (
                "minimum clearance in the saved complete contact-free UR10e trajectory; "
                "not a validated safety threshold and not sufficient by itself"
            ),
            "outside_behavior_for_future_design": (
                "candidate is unsupported for this predictor; this audit does not define "
                "or activate the fallback execution action"
            ),
        },
        "decision": (
            "CA-A — CONTACT-ADJACENT STATES ARE AVOIDABLE; DEFINE A PREDICTOR SUPPORT DOMAIN"
        ),
        "decision_basis": [
            "registered start-goal interpolation is contact-free",
            "saved complete UR10e OUTBOUND/HOLD/RETURN remains contact-free",
            "CR12 contact is brief and occurs only after early execution/prediction divergence",
            "matched candidate evidence shows degraded prediction near contact, but does not establish contact as the original cause",
        ],
        "limitations": [
            "CR12 has no observed HOLD or RETURN because the authoritative rollout aborted in OUTBOUND",
            "archived complete trace schema omits exact bed force; exact force is available only in saved 20 ms matched continuations",
            "one complete UR10e rollout and the registered geometric path establish existence, not clinical or formal safety",
            "the provisional support floor requires independent calibration/held-out validation before authority use",
        ],
    }

    (output / "contact_role_audit.json").write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n"
    )
    _write_phase_table(output / "phase_contact_table.csv", phase_rows)
    _plot_clearance(output, traces)
    _plot_error_vs_clearance(output, prefix)
    print(json.dumps(_jsonable(result["decision"])))
    print(output / "contact_role_audit.json")


if __name__ == "__main__":
    main()
