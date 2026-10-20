"""Deployable-only posture/interaction audit for saved Stage-5 trajectories."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


DEPLOYABLE_FIELDS = (
    "time_s",
    "estimated_state_rad_rad_s",
    "task_phase",
    "diagnostic_progress",
    "deployable_measured_cuff_force_world_n",
    "deployable_measured_cuff_moment_world_nm",
    "deployable_measured_generalized_input_nm",
    "support_generalized_action_nm",
    "motion_increment_generalized_action_nm",
    "executed_generalized_action_nm",
    "progress_pacing_gamma",
    "control_human_model_version",
)


def load_deployable_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as loaded:
        missing = sorted(set(DEPLOYABLE_FIELDS) - set(loaded.files))
        if missing:
            raise ValueError(f"deployable trace fields missing: {missing}")
        return {name: loaded[name].copy() for name in DEPLOYABLE_FIELDS}


def high_level_indices(time_s: np.ndarray, sample_period_s: float) -> np.ndarray:
    time = np.asarray(time_s, dtype=float)
    if time.ndim != 1 or not len(time):
        raise ValueError("time_s must be a nonempty vector")
    if not np.isfinite(sample_period_s) or sample_period_s <= 0.0:
        raise ValueError("sample period must be finite and positive")
    relative = (time - time[0]) / sample_period_s
    return np.flatnonzero(np.isclose(relative, np.rint(relative), atol=1.0e-7))


def interaction_arrays(trace: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    return {
        "q_rad": state[:, :2],
        "dq_rad_s": state[:, 2:],
        "force_norm_n": np.linalg.norm(
            trace["deployable_measured_cuff_force_world_n"], axis=1
        ),
        "moment_norm_nm": np.linalg.norm(
            trace["deployable_measured_cuff_moment_world_nm"], axis=1
        ),
        "generalized_input_nm": np.asarray(
            trace["deployable_measured_generalized_input_nm"], dtype=float
        ),
        "generalized_input_norm_nm": np.linalg.norm(
            trace["deployable_measured_generalized_input_nm"], axis=1
        ),
        "support_action_nm": np.asarray(
            trace["support_generalized_action_nm"], dtype=float
        ),
        "support_norm_nm": np.linalg.norm(
            trace["support_generalized_action_nm"], axis=1
        ),
        "motion_action_nm": np.asarray(
            trace["motion_increment_generalized_action_nm"], dtype=float
        ),
        "motion_norm_nm": np.linalg.norm(
            trace["motion_increment_generalized_action_nm"], axis=1
        ),
        "total_action_nm": np.asarray(
            trace["executed_generalized_action_nm"], dtype=float
        ),
    }


def representative_state_rows(
    traces: Iterable[tuple[int, dict[str, np.ndarray]]],
    specifications: list[dict[str, Any]],
    *,
    sample_period_s: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed, trace in traces:
        arrays = interaction_arrays(trace)
        high_level = high_level_indices(trace["time_s"], sample_period_s)
        phase = np.asarray(trace["task_phase"], dtype=str)
        progress = np.asarray(trace["diagnostic_progress"], dtype=float)
        for spec in specifications:
            phase_indices = high_level[phase[high_level] == str(spec["phase"])]
            if not len(phase_indices):
                raise ValueError(
                    f"reference trace seed {seed} lacks phase {spec['phase']}"
                )
            if "target_progress" in spec:
                finite = phase_indices[np.isfinite(progress[phase_indices])]
                index = int(
                    finite[
                        np.argmin(
                            np.abs(progress[finite] - float(spec["target_progress"]))
                        )
                    ]
                )
            else:
                fraction = float(spec["target_phase_fraction"])
                index = int(
                    phase_indices[
                        round(fraction * max(0, len(phase_indices) - 1))
                    ]
                )
            rows.append(
                {
                    "state_name": str(spec["name"]),
                    "seed": int(seed),
                    "time_s": float(trace["time_s"][index]),
                    "task_phase": str(phase[index]),
                    "diagnostic_progress": (
                        None
                        if not np.isfinite(progress[index])
                        else float(progress[index])
                    ),
                    "q_deg": np.degrees(arrays["q_rad"][index]).tolist(),
                    "dq_deg_s": np.degrees(arrays["dq_rad_s"][index]).tolist(),
                    "measured_cuff_force_norm_n": float(
                        arrays["force_norm_n"][index]
                    ),
                    "measured_cuff_moment_norm_nm": float(
                        arrays["moment_norm_nm"][index]
                    ),
                    "measured_generalized_human_input_nm": arrays[
                        "generalized_input_nm"
                    ][index].tolist(),
                    "measured_generalized_human_input_norm_nm": float(
                        arrays["generalized_input_norm_nm"][index]
                    ),
                    "support_generalized_action_nm": arrays[
                        "support_action_nm"
                    ][index].tolist(),
                    "support_norm_nm": float(arrays["support_norm_nm"][index]),
                    "motion_increment_generalized_action_nm": arrays[
                        "motion_action_nm"
                    ][index].tolist(),
                    "motion_increment_norm_nm": float(
                        arrays["motion_norm_nm"][index]
                    ),
                    "executed_generalized_action_nm": arrays[
                        "total_action_nm"
                    ][index].tolist(),
                }
            )
    return rows


def build_supported_grid(
    samples: dict[str, np.ndarray],
    *,
    q1_edges_deg: np.ndarray,
    q2_edges_deg: np.ndarray,
    minimum_samples: int,
    minimum_unique_seeds: int,
) -> dict[str, np.ndarray]:
    q_deg = np.degrees(np.asarray(samples["q_rad"], dtype=float))
    seeds = np.asarray(samples["seed"], dtype=int)
    shape = (len(q1_edges_deg) - 1, len(q2_edges_deg) - 1)
    q1_bin = np.digitize(q_deg[:, 0], q1_edges_deg) - 1
    q2_bin = np.digitize(q_deg[:, 1], q2_edges_deg) - 1
    valid_bin = (
        (q1_bin >= 0)
        & (q1_bin < shape[0])
        & (q2_bin >= 0)
        & (q2_bin < shape[1])
    )
    result: dict[str, np.ndarray] = {
        "q1_edges_deg": np.asarray(q1_edges_deg, dtype=float),
        "q2_edges_deg": np.asarray(q2_edges_deg, dtype=float),
        "sample_count": np.zeros(shape, dtype=int),
        "unique_seed_count": np.zeros(shape, dtype=int),
    }
    value_names = (
        "force_norm_n",
        "moment_norm_nm",
        "generalized_input_norm_nm",
        "support_norm_nm",
        "motion_norm_nm",
    )
    for name in value_names:
        result[name] = np.full(shape, np.nan)
    for i in range(shape[0]):
        for j in range(shape[1]):
            selected = valid_bin & (q1_bin == i) & (q2_bin == j)
            count = int(np.count_nonzero(selected))
            unique = int(len(np.unique(seeds[selected])))
            result["sample_count"][i, j] = count
            result["unique_seed_count"][i, j] = unique
            if count < minimum_samples or unique < minimum_unique_seeds:
                continue
            for name in value_names:
                result[name][i, j] = float(
                    np.median(np.asarray(samples[name], dtype=float)[selected])
                )
    return result


def concatenate_reference_samples(
    traces: Iterable[tuple[int, dict[str, np.ndarray]]],
    *,
    sample_period_s: float,
) -> dict[str, np.ndarray]:
    blocks: dict[str, list[np.ndarray]] = {
        "q_rad": [],
        "dq_rad_s": [],
        "force_norm_n": [],
        "moment_norm_nm": [],
        "generalized_input_norm_nm": [],
        "support_norm_nm": [],
        "motion_norm_nm": [],
        "seed": [],
        "phase": [],
        "progress": [],
    }
    for seed, trace in traces:
        selected = high_level_indices(trace["time_s"], sample_period_s)
        arrays = interaction_arrays(trace)
        for name in (
            "q_rad",
            "dq_rad_s",
            "force_norm_n",
            "moment_norm_nm",
            "generalized_input_norm_nm",
            "support_norm_nm",
            "motion_norm_nm",
        ):
            blocks[name].append(arrays[name][selected])
        blocks["seed"].append(np.full(len(selected), seed, dtype=int))
        blocks["phase"].append(np.asarray(trace["task_phase"], dtype=str)[selected])
        blocks["progress"].append(
            np.asarray(trace["diagnostic_progress"], dtype=float)[selected]
        )
    return {name: np.concatenate(values, axis=0) for name, values in blocks.items()}


def _time_mean(values: np.ndarray, time_s: np.ndarray) -> float:
    duration = float(time_s[-1] - time_s[0])
    if duration <= 0.0:
        raise ValueError("matched local interval has nonpositive duration")
    return float(np.trapezoid(values, time_s) / duration)


def matched_local_row(
    trace: dict[str, np.ndarray],
    source_row: dict[str, Any],
    *,
    duration_s: float,
    start_rad: np.ndarray,
    goal_rad: np.ndarray,
) -> dict[str, Any]:
    arrays = interaction_arrays(trace)
    time = np.asarray(trace["time_s"], dtype=float)
    start_time = float(source_row["starting_deployable_state"]["episode_time_s"])
    selected = np.flatnonzero(
        (time >= start_time - 1.0e-12)
        & (time <= start_time + duration_s + 1.0e-12)
    )
    if len(selected) < 2:
        raise ValueError("matched local interval is absent from trace")
    local_time = time[selected]
    observed_duration = float(local_time[-1] - local_time[0])
    q = arrays["q_rad"][selected]
    task_coordinate = (q - start_rad) / (goal_rad - start_rad)
    force = arrays["force_norm_n"][selected]
    moment = arrays["moment_norm_nm"][selected]
    generalized = arrays["generalized_input_nm"][selected]
    generalized_norm = arrays["generalized_input_norm_nm"][selected]
    future = np.flatnonzero(time >= start_time - 1.0e-12)
    future_time = time[future]
    future_generalized_norm = arrays["generalized_input_norm_nm"][future]
    safety = source_row["safety_events"]
    envelope = source_row["motion_envelope"]
    return {
        "anchor_name": source_row["anchor_name"],
        "seed": int(source_row["cem_seed"]),
        "branch": source_row["coordination"],
        "decision_state_sha256": source_row["decision_state_sha256"],
        "task_phase": source_row["starting_deployable_state"]["task"]["phase"],
        "start_q_deg": np.degrees(q[0]).tolist(),
        "terminal_q_deg": np.degrees(q[-1]).tolist(),
        "actual_delta_q_deg": np.degrees(q[-1] - q[0]).tolist(),
        "registered_short_motion_delta_q_deg": source_row["short_motion"][
            "delta_q_deg"
        ],
        "terminal_task_coordinate_difference": float(
            task_coordinate[-1, 0] - task_coordinate[-1, 1]
        ),
        "observed_duration_s": observed_duration,
        "measured_force_integral_n_s": float(
            np.trapezoid(force, local_time)
        ),
        "mean_measured_force_n": _time_mean(force, local_time),
        "peak_measured_force_n": float(np.max(force)),
        "mean_measured_moment_nm": _time_mean(moment, local_time),
        "peak_measured_moment_nm": float(np.max(moment)),
        "generalized_human_effort_integral_nm_s": float(
            np.trapezoid(generalized_norm, local_time)
        ),
        "mean_generalized_human_effort_norm_nm": _time_mean(
            generalized_norm, local_time
        ),
        "mean_abs_generalized_human_input_nm": np.mean(
            np.abs(generalized), axis=0
        ).tolist(),
        "mean_support_norm_nm": _time_mean(
            arrays["support_norm_nm"][selected], local_time
        ),
        "mean_motion_increment_norm_nm": _time_mean(
            arrays["motion_norm_nm"][selected], local_time
        ),
        "complete_q1_q2_path_artifact": source_row["complete_q1_q2_path"][
            "artifact"
        ],
        "remaining_task_duration_s": float(
            source_row["remaining_task_duration_s"]
        ),
        "future_cumulative_measured_cuff_force_n_s": float(
            source_row["future_cumulative_measured_cuff_force_n_s"]
        ),
        "future_mean_measured_cuff_force_n": float(
            source_row["future_mean_measured_cuff_force_n"]
        ),
        "future_peak_measured_cuff_force_n": float(
            source_row["future_peak_measured_cuff_force_n"]
        ),
        "future_peak_measured_cuff_moment_nm": float(
            source_row["future_peak_measured_cuff_moment_nm"]
        ),
        "future_generalized_human_effort_integral_nm_s": float(
            np.trapezoid(future_generalized_norm, future_time)
        ),
        "future_mean_generalized_human_effort_norm_nm": _time_mean(
            future_generalized_norm, future_time
        ),
        "mpc_failure_count": int(safety["mpc_failure_count"]),
        "force_gate_event_count": int(safety["force_gate_event_count"]),
        "brake_event_count": int(safety["brake_event_count"]),
        "structural_event_count": int(safety["structural_event_count"]),
        "maximum_safety_filter_intervention_coordinate_norm": float(
            safety["maximum_safety_filter_intervention_coordinate_norm"]
        ),
        "estimated_velocity_satisfied": bool(
            envelope["estimated_velocity_satisfied"]
        ),
        "deployable_realized_acceleration_satisfied": bool(
            envelope["deployable_realized_acceleration_satisfied"]
        ),
        "task_complete": bool(source_row["task_complete"]),
        "safety_valid": bool(source_row["safety_valid"]),
        "prefix_feasible": bool(
            source_row["short_motion"]["all_biased_prefixes_feasible"]
        ),
    }


def summarize_matched_groups(
    rows: list[dict[str, Any]],
    *,
    branch_order: list[str],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    keys = sorted({(row["anchor_name"], row["seed"]) for row in rows})
    for anchor, seed in keys:
        group = sorted(
            [
                row
                for row in rows
                if row["anchor_name"] == anchor and row["seed"] == seed
            ],
            key=lambda row: branch_order.index(row["branch"]),
        )
        force = np.asarray([row["mean_measured_force_n"] for row in group])
        moment = np.asarray([row["mean_measured_moment_nm"] for row in group])
        effort = np.asarray(
            [row["mean_generalized_human_effort_norm_nm"] for row in group]
        )
        durations = np.asarray([row["observed_duration_s"] for row in group])
        posture = np.asarray(
            [row["terminal_task_coordinate_difference"] for row in group]
        )
        summaries.append(
            {
                "anchor_name": anchor,
                "seed": seed,
                "branch_count": len(group),
                "same_start_digest": len(
                    {row["decision_state_sha256"] for row in group}
                )
                == 1,
                "local_duration_range_s": float(np.ptp(durations)),
                "posture_coordinate_range": float(np.ptp(posture)),
                "low_force_branch": group[int(np.argmin(force))]["branch"],
                "mean_force_range_n": float(np.ptp(force)),
                "mean_force_separation_fraction": float(
                    np.ptp(force) / np.mean(force)
                ),
                "mean_moment_range_nm": float(np.ptp(moment)),
                "mean_generalized_effort_range_nm": float(np.ptp(effort)),
                "all_complete_safe_feasible": all(
                    row["task_complete"]
                    and row["safety_valid"]
                    and row["prefix_feasible"]
                    for row in group
                ),
            }
        )
    return summaries


def decide_landscape(
    group_summaries: list[dict[str, Any]],
    *,
    validity: bool,
    meaningful_fraction: float,
    flat_fraction: float,
    repeat_count: int,
) -> dict[str, Any]:
    anchors = sorted({row["anchor_name"] for row in group_summaries})
    repeatability: dict[str, Any] = {}
    for anchor in anchors:
        names = [
            row["low_force_branch"]
            for row in group_summaries
            if row["anchor_name"] == anchor
        ]
        counts = Counter(names)
        repeatability[anchor] = {
            "low_force_branch_counts": dict(sorted(counts.items())),
            "repeatable": bool(counts and max(counts.values()) >= repeat_count),
        }
    all_timing_matched = bool(group_summaries) and all(
        row["local_duration_range_s"] <= 1.0e-10 for row in group_summaries
    )
    valid = bool(validity and all_timing_matched)
    meaningful_by_anchor = {
        anchor: sum(
            row["mean_force_separation_fraction"] >= meaningful_fraction
            for row in group_summaries
            if row["anchor_name"] == anchor
        )
        >= repeat_count
        for anchor in anchors
    }
    max_separation = max(
        (row["mean_force_separation_fraction"] for row in group_summaries),
        default=float("nan"),
    )
    any_repeatable = any(
        item["repeatable"] for item in repeatability.values()
    )
    if not valid:
        decision = "LF-D"
        label = "EXPERIMENT INVALID / INSUFFICIENT"
    elif anchors and all(meaningful_by_anchor.values()) and all(
        item["repeatable"] for item in repeatability.values()
    ):
        decision = "LF-A"
        label = "MEANINGFUL POSTURE-DEPENDENT FORCE LANDSCAPE CONFIRMED"
    elif max_separation <= flat_fraction and not any_repeatable:
        decision = "LF-C"
        label = "CURRENT TOTAL-FORCE OBJECTIVE IS ESSENTIALLY FLAT OVER USEFUL POSTURES"
    else:
        decision = "LF-B"
        label = "POSTURE EFFECT EXISTS BUT IS TOO SMALL / INCONSISTENT"
    return {
        "decision": decision,
        "decision_label": label,
        "validity_gate_passed": valid,
        "local_timing_matched": all_timing_matched,
        "maximum_local_mean_force_separation_fraction": max_separation,
        "meaningful_by_anchor": meaningful_by_anchor,
        "low_force_branch_repeatability": repeatability,
    }


__all__ = [
    "DEPLOYABLE_FIELDS",
    "build_supported_grid",
    "concatenate_reference_samples",
    "decide_landscape",
    "high_level_indices",
    "interaction_arrays",
    "load_deployable_trace",
    "matched_local_row",
    "representative_state_rows",
    "summarize_matched_groups",
]
