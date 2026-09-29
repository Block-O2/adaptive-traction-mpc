"""Pure state and accounting helpers for the zero-value continuous session."""
from __future__ import annotations

from typing import Any

import numpy as np


# Only these objects may cross an episode boundary. A new controller/task
# runtime is built around them for every repetition.
PERSISTENT_RUNTIME_FIELDS = (
    "plant",
    "measurement_layer",
    "observer",
    "allocator",
    "last_command",
    "last_command_robot_position_m",
    "last_command_source_sample_s",
    "last_command_receipt_physics_s",
    "startup_alignment",
    "startup_alignment_active",
    "startup_alignment_record",
    "command_response_history",
)
REQUIRED_PERSISTENT_FIELDS = (
    "plant",
    "measurement_layer",
    "observer",
    "allocator",
    "last_command",
    "last_command_robot_position_m",
    "last_command_source_sample_s",
    "last_command_receipt_physics_s",
)
FORBIDDEN_TRANSIENT_FIELDS = (
    "plan_lifecycle",
    "wall_session",
    "task_decisions",
    "trace",
    "future_handoff_bridges",
    "rolling_splice_events",
    "plan_to_activate",
    "activation_validator",
    "actual_activation_hook",
    "reference_progress_commit",
    "return_projection_finalization",
    "return_projection_guards",
    "reference_governor_records",
    "true_physics_monitor",
    "sensor_task_clock",
    "task_phase_version",
)


def carryover_runtime_fields(previous: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_PERSISTENT_FIELDS if key not in previous]
    if missing:
        raise ValueError(f"missing persistent session state: {missing}")
    carried = {key: previous[key] for key in PERSISTENT_RUNTIME_FIELDS if key in previous}
    assert not set(carried).intersection(FORBIDDEN_TRANSIENT_FIELDS)
    return carried


def integrate_measured_wrench(
    time_s: np.ndarray, force_world_n: np.ndarray, moment_world_nm: np.ndarray
) -> dict[str, float]:
    """Left Riemann sum over executed simulation-time intervals.

    The final boundary sample has no following physical interval and contributes
    no cost. Inputs must be measured cuff/interface wrenches at task boundaries.
    """
    time = np.asarray(time_s, dtype=float)
    force = np.asarray(force_world_n, dtype=float)
    moment = np.asarray(moment_world_nm, dtype=float)
    if time.ndim != 1 or force.shape != (len(time), 3) or moment.shape != (len(time), 3):
        raise ValueError("wrench trace dimensions do not match task boundaries")
    if len(time) < 2 or not all(np.all(np.isfinite(x)) for x in (time, force, moment)):
        raise ValueError("wrench trace is too short or nonfinite")
    dt = np.diff(time)
    if np.any(dt <= 0):
        raise ValueError("simulation time must increase at every boundary")
    force_norm = np.linalg.norm(force, axis=1)
    moment_norm = np.linalg.norm(moment, axis=1)
    return {
        "J_F_n_s": float(np.dot(force_norm[:-1], dt)),
        "moment_integral_nm_s": float(np.dot(moment_norm[:-1], dt)),
        "peak_force_n": float(force_norm.max()),
        "peak_moment_nm": float(moment_norm.max()),
        "sample_count": int(len(time)),
        "interval_count": int(len(dt)),
    }


def zero_value_decision_rows(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, decision in enumerate(decisions):
        value_hook = decision.get("value_hook_numeric_value")
        if (type(value_hook) not in (int, float) or value_hook != 0.0
                or decision.get("value_hook_configured") is not False):
            raise ValueError(f"nonzero value hook at decision {index}")
        candidates = []
        for evaluation in decision["evaluations"]:
            if (not isinstance(evaluation.get("cost_terms"), dict)
                    or "total_cost" not in evaluation
                    or type(evaluation.get("feasible")) is not bool
                    or not isinstance(evaluation.get("execution_screen"), dict)
                    or type(evaluation["execution_screen"].get("evaluated")) is not bool):
                raise ValueError(f"missing candidate score status at decision {index}")
            terms = evaluation["cost_terms"]
            future_value = terms.get("future_value")
            scored = future_value is not None
            total_cost = evaluation["total_cost"]
            if scored and (type(future_value) not in (int, float)
                           or not np.isfinite(future_value) or future_value != 0.0):
                raise ValueError(f"nonzero learned value at decision {index}")
            if not scored and (total_cost is not None or evaluation["feasible"]
                               or evaluation["execution_screen"]["evaluated"]
                               or not evaluation.get("rejection_reason")
                               or any(value is not None for value in terms.values())):
                raise ValueError(f"malformed unscored candidate at decision {index}")
            if scored and total_cost is not None and (
                    type(total_cost) not in (int, float) or not np.isfinite(total_cost)):
                raise ValueError(f"invalid candidate score at decision {index}")
            if scored and total_cost is None and (
                    evaluation["feasible"] or not evaluation.get("rejection_reason")):
                raise ValueError(f"missing candidate score at decision {index}")
            candidates.append({
                "label": evaluation["label"],
                "feasible": evaluation["feasible"],
                "evaluated": scored,
                "execution_screen_evaluated": evaluation["execution_screen"]["evaluated"],
                "short_term_total_cost": total_cost,
                "short_term_cost_terms": {key: value for key, value in terms.items()
                                          if key != "future_value"},
                "learned_value": 0.0,
            })
        rows.append({
            "decision_index": index,
            "phase": decision["phase"],
            "candidate_set": candidates,
            "baseline_selected_waypoint": decision.get("greedy_label"),
            "executed_waypoint": decision.get("executed_label"),
            "selected_action_provenance": "existing_baseline_waypoint_policy",
            "selection_mode": decision.get("selection_mode"),
            "learned_value": 0.0,
            "RL": "OFF",
        })
    return rows
