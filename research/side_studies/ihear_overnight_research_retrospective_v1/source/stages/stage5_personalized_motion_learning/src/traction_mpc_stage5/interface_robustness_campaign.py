"""Frozen final-campaign helpers for Stage-5 Interface Robustness v1.

Everything in this module is evaluation/orchestration only.  It does not enter
the online observation, MPC, Safety Filter, BRAKE, HOLD, or plant execution
decision path.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from traction_mpc_stage3.spring_damper_interface import InterfaceParameters

from .config import STAGE5_ROOT
from .interface_robustness import ProgressiveTranslationStage5Plant
from .mechanics import STAGE5_RIGID_INTERFACE


FINAL_CAMPAIGN_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_interface_robustness_final_campaign_v1.json"
)


def load_final_campaign_spec(
    path: Path = FINAL_CAMPAIGN_CONFIG_PATH,
) -> dict[str, Any]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema") != "stage5_interface_robustness_final_campaign_v1":
        raise ValueError("unexpected final-campaign schema")
    if record.get("status") != "PREREGISTERED_NOT_AUTHORIZED":
        raise ValueError("frozen preregistration status changed")
    if record.get("controller_changes_after_development_allowed") is not False:
        raise ValueError("campaign cannot permit controller changes")
    seeds = record.get("fixed_random_seeds")
    conditions = record.get("core_box", {}).get("conditions")
    if seeds != [20260824, 20260825, 20260826]:
        raise ValueError("unexpected preregistered seed list")
    if not isinstance(conditions, list) or len(conditions) != 9:
        raise ValueError("core campaign must contain exactly nine conditions")
    if len(conditions) * len(seeds) != 27:
        raise ValueError("core campaign must contain exactly 27 episodes")
    boundaries = record.get("boundary_challenges", {}).get("conditions")
    if not isinstance(boundaries, list) or len(boundaries) != 4:
        raise ValueError("boundary campaign must contain exactly four cases")
    repeatability = record.get("repeatability", {})
    if repeatability.get("continuous_episode_count") != 30:
        raise ValueError("repeatability campaign must contain 30 episodes")
    if repeatability.get("five_second_hold_episodes") != [1, 30]:
        raise ValueError("repeatability long-HOLD episodes changed")
    return record


def scaled_interface(
    alpha_t: float,
    alpha_r: float,
    alpha_d: float,
    *,
    nominal: InterfaceParameters = STAGE5_RIGID_INTERFACE,
) -> InterfaceParameters:
    scales = np.asarray([alpha_t, alpha_r, alpha_d], dtype=float)
    if scales.shape != (3,) or not np.all(np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("interface scales must be finite and positive")
    return InterfaceParameters(
        translation_stiffness_n_m=tuple(
            float(alpha_t) * np.asarray(nominal.translation_stiffness_n_m)
        ),
        translation_damping_ns_m=tuple(
            float(alpha_d) * np.asarray(nominal.translation_damping_ns_m)
        ),
        rotation_stiffness_nm_rad=(
            float(alpha_r) * nominal.rotation_stiffness_nm_rad
        ),
        rotation_damping_nms_rad=(
            float(alpha_d) * nominal.rotation_damping_nms_rad
        ),
        rest_translation_human_m=nominal.rest_translation_human_m,
        rest_rotation_rotvec_human_rad=nominal.rest_rotation_rotvec_human_rad,
    )


def compact_score_row(
    *,
    campaign_section: str,
    condition: Mapping[str, Any],
    seed: int,
    score: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    state = score["state_estimation"]
    prediction = score["wrench_prediction_20ms"]
    physical = score["physical"]
    motion = score["motion_envelope"]
    return {
        "campaign_section": campaign_section,
        "condition": dict(condition),
        "seed": int(seed),
        "online_result": score["online_result"],
        "abort_reason": score["abort_reason"],
        "truth_complete": bool(score["evaluation_truth_complete"]),
        "accepted": bool(score["evaluation_acceptance"]),
        "false_complete": bool(score["false_complete"]),
        "silent_motion_violation": bool(score["false_negative_constraint_violation"]),
        "phase_transitions": summary.get("phase_transitions", []),
        "duration_s": float(score["duration_s"]),
        "outbound_truth_angle_error_deg": score["outbound_arrival"].get(
            "truth_abs_angle_error_deg"
        ),
        "outbound_truth_speed_deg_s": score["outbound_arrival"].get(
            "truth_abs_velocity_deg_s"
        ),
        "return_truth_angle_error_deg": score["return_arrival"].get(
            "truth_abs_angle_error_deg"
        ),
        "return_truth_speed_deg_s": score["return_arrival"].get(
            "truth_abs_velocity_deg_s"
        ),
        "continuous_goal_set_hold_s": score[
            "continuous_outbound_terminal_set"
        ]["duration_s"],
        "q_rmse_deg": state["q_error_deg"]["rmse"],
        "q_p95_abs_deg": state["q_error_deg"]["p95_abs"],
        "q_max_abs_deg": state["q_error_deg"]["max_abs"],
        "dq_rmse_deg_s": state["dq_error_deg_s"]["rmse"],
        "dq_p95_abs_deg_s": state["dq_error_deg_s"]["p95_abs"],
        "dq_max_abs_deg_s": state["dq_error_deg_s"]["max_abs"],
        "completion_q_error_max_deg": state[
            "completion_window_q_abs_error_max_deg"
        ],
        "completion_dq_error_max_deg_s": state[
            "completion_window_dq_abs_error_max_deg_s"
        ],
        "truth_peak_velocity_deg_s": motion["truth_peak_velocity_deg_s"],
        "truth_peak_acceleration_deg_s2": motion["truth_peak_acceleration_deg_s2"],
        "online_peak_velocity_deg_s": motion["online_peak_velocity_deg_s"],
        "online_peak_acceleration_deg_s2": motion[
            "online_peak_acceleration_deg_s2"
        ],
        "force_prediction_rmse_n": prediction["force_vector_error_n"]["rmse"],
        "force_prediction_p95_n": prediction["force_vector_error_n"]["p95"],
        "force_prediction_max_n": prediction["force_vector_error_n"]["max"],
        "moment_prediction_rmse_nm": prediction["moment_vector_error_nm"]["rmse"],
        "moment_prediction_p95_nm": prediction["moment_vector_error_nm"]["p95"],
        "moment_prediction_max_nm": prediction["moment_vector_error_nm"]["max"],
        "peak_force_underprediction_n": prediction[
            "peak_force_max_underprediction_n"
        ],
        "peak_physical_force_n": physical["peak_force_n"],
        "cumulative_physical_force_n_s": physical["cumulative_force_n_s"],
        "peak_physical_moment_nm": physical["peak_moment_nm"],
        "peak_interface_translation_mm": summary[
            "peak_interface_translation_mm"
        ],
        "peak_interface_rotation_deg": summary["peak_interface_rotation_deg"],
        "mpc_status_counts": score["mpc_status_counts"],
        "safety_filter_status_counts": score["safety_filter_status_counts"],
        "maximum_safety_filter_intervention_coordinate_norm": summary.get(
            "maximum_safety_filter_intervention_coordinate_norm"
        ),
        "brake_event_count": score["brake_event_count"],
        "force_gate_event_count": score["force_gate_event_count"],
        "structural_event_count": summary.get("structural_event_count", 0),
        "mujoco_warning_counts": score["mujoco_warning_counts"],
        "runtime_ms": score["runtime_ms"],
        "path_freedom": score["path_freedom"],
    }


def classify_boundary(row: Mapping[str, Any]) -> dict[str, Any]:
    """Apply only the preregistered boundary categories, without rescue."""

    if row.get("false_complete"):
        classification = "false_completion"
        acceptable = False
    elif row.get("silent_motion_violation"):
        classification = "silent_registered_constraint_violation"
        acceptable = False
    elif row.get("force_gate_event_count", 0) or row.get("structural_event_count", 0):
        classification = "detected_registered_constraint_violation"
        acceptable = False
    elif row.get("truth_complete") and row.get("accepted"):
        classification = "successful_completion"
        acceptable = True
    elif row.get("online_result") == "ABORTED":
        classification = "conservative_pre_violation_rejection_or_abort"
        acceptable = True
    else:
        classification = "false_positive_or_unusable_noncompletion"
        acceptable = False
    return {
        "classification": classification,
        "boundary_acceptable": acceptable,
        "online_abort_while_truth_safe_up_to_abort": bool(
            row.get("online_result") == "ABORTED"
            and not row.get("silent_motion_violation")
            and not row.get("force_gate_event_count", 0)
            and not row.get("structural_event_count", 0)
        ),
    }


def linear_trend(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    indices = np.arange(1, len(array) + 1, dtype=float)
    slope = float(np.polyfit(indices, array, 1)[0]) if len(array) > 1 else 0.0
    return {
        "first5_mean": float(np.mean(array[:5])),
        "last5_mean": float(np.mean(array[-5:])),
        "last5_minus_first5": float(np.mean(array[-5:]) - np.mean(array[:5])),
        "least_squares_slope_per_episode": slope,
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


__all__ = [
    "FINAL_CAMPAIGN_CONFIG_PATH",
    "ProgressiveTranslationStage5Plant",
    "classify_boundary",
    "compact_score_row",
    "linear_trend",
    "load_final_campaign_spec",
    "scaled_interface",
]
