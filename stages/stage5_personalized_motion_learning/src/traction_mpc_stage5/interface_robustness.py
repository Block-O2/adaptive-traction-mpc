"""Stage-5 interface-robustness acceptance and saved-trace scoring.

This module is evaluation-only.  It never participates in online estimation,
MPC, phase transitions, Safety Filter, BRAKE, or plant execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.spring_damper_interface import (
    AttachmentState,
    InterfaceParameters,
    InterfaceState,
)

from .baseline_replay import Stage5SensorBoundaryPlant
from .controller_interface import ControllerNominalInterfaceParameters
from .hold_stabilizer import solve_loaded_hold_equilibrium

from .config import STAGE5_ROOT


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_interface_robustness_v1.json"


class ProgressiveTranslationStage5Plant(Stage5SensorBoundaryPlant):
    """Preregistered Stage-5-only progressive translation boundary fixture.

    Rotation and damping retain the supplied Kelvin--Voigt parameters.  Only
    the translational elastic law changes to the frozen radial expression
    ``K*x*(1 + beta*(||x||/x_ref)^2)``.  This class is evaluation plant truth;
    no instance or coefficient is exposed to online controller code.
    """

    def __init__(
        self,
        human: Any,
        *,
        interface_parameters: InterfaceParameters,
        beta: float,
        x_ref_m: float,
    ) -> None:
        if not np.isfinite(beta) or beta <= 0.0:
            raise ValueError("progressive beta must be finite and positive")
        if not np.isfinite(x_ref_m) or x_ref_m <= 0.0:
            raise ValueError("progressive x_ref_m must be finite and positive")
        self.progressive_beta = float(beta)
        self.progressive_x_ref_m = float(x_ref_m)
        super().__init__(human, interface_parameters=interface_parameters)

    def _evaluate_current_interface(self) -> InterfaceState:
        return self.evaluate_progressive_interface(
            self.interface_parameters,
            self._attachment_state(self.attachment_site_id),
            self._attachment_state(self.sleeve_site_id),
            beta=self.progressive_beta,
            x_ref_m=self.progressive_x_ref_m,
        )

    @staticmethod
    def evaluate_progressive_interface(
        parameters: InterfaceParameters,
        robot: AttachmentState,
        human: AttachmentState,
        *,
        beta: float,
        x_ref_m: float,
    ) -> InterfaceState:
        r = robot.position_world_m - human.position_world_m
        rotation_human = human.rotation_world
        rest_x = np.asarray(parameters.rest_translation_human_m, dtype=float)
        x = rotation_human.T @ r - rest_x
        velocity = rotation_human.T @ (
            robot.velocity_world_m_s
            - human.velocity_world_m_s
            - np.cross(human.angular_velocity_world_rad_s, r)
        )
        rest_rotation = Rotation.from_rotvec(
            parameters.rest_rotation_rotvec_human_rad
        ).as_matrix()
        theta = Rotation.from_matrix(
            rotation_human.T @ robot.rotation_world @ rest_rotation.T
        ).as_rotvec()
        omega = rotation_human.T @ (
            robot.angular_velocity_world_rad_s
            - human.angular_velocity_world_rad_s
        )
        stiffness = np.asarray(parameters.translation_stiffness_n_m, dtype=float)
        damping = np.asarray(parameters.translation_damping_ns_m, dtype=float)
        radial_factor = 1.0 + beta * float(x @ x) / (x_ref_m * x_ref_m)
        elastic_human = stiffness * x * radial_factor
        damping_human = damping * velocity
        elastic_rotation_human = parameters.rotation_stiffness_nm_rad * theta
        damping_rotation_human = parameters.rotation_damping_nms_rad * omega
        force_world = rotation_human @ (elastic_human + damping_human)
        couple_world = rotation_human @ (
            elastic_rotation_human + damping_rotation_human
        )
        human_wrench = np.r_[force_world, couple_world + np.cross(r, force_world)]
        robot_wrench = np.r_[-force_world, -couple_world]
        elastic_energy = float(
            0.5 * x @ (stiffness * x)
            + 0.25
            * beta
            * float(x @ x)
            * float(x @ (stiffness * x))
            / (x_ref_m * x_ref_m)
            + 0.5
            * parameters.rotation_stiffness_nm_rad
            * float(theta @ theta)
        )
        dissipation = float(
            velocity @ (damping * velocity)
            + parameters.rotation_damping_nms_rad * float(omega @ omega)
        )
        power = float(
            robot_wrench
            @ np.r_[
                robot.velocity_world_m_s,
                robot.angular_velocity_world_rad_s,
            ]
            + human_wrench
            @ np.r_[
                human.velocity_world_m_s,
                human.angular_velocity_world_rad_s,
            ]
        )
        energy_rate = float(
            elastic_human @ velocity + elastic_rotation_human @ omega
        )
        return InterfaceState(
            x,
            velocity,
            theta,
            omega,
            human_wrench,
            robot_wrench,
            elastic_energy,
            dissipation,
            power,
            energy_rate,
        )

    def evaluation_loaded_initialization_interface(
        self,
        linear_truth: ControllerNominalInterfaceParameters,
        spec: Any,
        human_model: Any,
        cuff_allocator: Any,
    ) -> ControllerNominalInterfaceParameters:
        """Return the secant K producing the exact nonlinear static load.

        This is called only by the evaluation fixture before time zero.  It
        does not change or expose the controller's nominal model.
        """

        linear_equilibrium = solve_loaded_hold_equilibrium(
            spec,
            human_model,
            cuff_allocator,
            interface=linear_truth,
            target_q_rad=np.asarray(spec.start_return_target_rad, dtype=float),
        )
        force_human = (
            linear_equilibrium.human_cuff_pose_world.rotation.T
            @ linear_equilibrium.physical_human_wrench_world[:3]
        )
        base_k = np.asarray(linear_truth.translation_stiffness_n_m, dtype=float)
        if not np.allclose(base_k, base_k[0], rtol=0.0, atol=1.0e-12):
            raise ValueError("preregistered radial progressive fixture requires isotropic Kt")
        force_norm = float(np.linalg.norm(force_human))
        displacement_norm = force_norm / float(base_k[0])
        for _ in range(16):
            ratio_sq = (displacement_norm / self.progressive_x_ref_m) ** 2
            residual = (
                float(base_k[0])
                * displacement_norm
                * (1.0 + self.progressive_beta * ratio_sq)
                - force_norm
            )
            derivative = float(base_k[0]) * (
                1.0 + 3.0 * self.progressive_beta * ratio_sq
            )
            displacement_norm -= residual / derivative
        secant = float(base_k[0]) * (
            1.0
            + self.progressive_beta
            * (displacement_norm / self.progressive_x_ref_m) ** 2
        )
        return ControllerNominalInterfaceParameters(
            **{
                **vars(linear_truth),
                "model_version": (
                    f"{linear_truth.model_version}__progressive_static_fixture"
                ),
                "translation_stiffness_n_m": (secant, secant, secant),
            }
        )


def load_interface_robustness_contract(path: Path = CONFIG_PATH) -> dict[str, Any]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema") != "stage5_interface_robustness_closeout_v1":
        raise ValueError("unexpected interface-robustness schema")
    if record.get("clinical_or_hardware_safety_validation") is not False:
        raise ValueError("interface robustness is engineering evidence only")
    authority = record["control_authority"]
    forbidden = (
        "online_interface_parameter_identification_active",
        "interface_hypothesis_bank_is_control_authority",
        "human_adaptation_active",
        "value_or_rl_learning_active",
        "plant_truth_available_online",
    )
    if any(authority.get(name) is not False for name in forbidden):
        raise ValueError("forbidden online adaptation/learning/truth authority enabled")
    hard = record["registered_hard_limits_unchanged"]
    if hard["joint_velocity_deg_s"] != [45.0, 75.0]:
        raise ValueError("registered velocity limits changed")
    if hard["joint_acceleration_20ms_deg_s2"] != [300.0, 600.0]:
        raise ValueError("registered acceleration limits changed")
    if hard["physical_cuff_force_gate_n"] != 200.0:
        raise ValueError("registered physical force gate changed")
    development = record["development_v1"]
    if development["maximum_new_episodes"] != 6 or len(development["cases"]) != 6:
        raise ValueError("development budget must remain six predeclared episodes")
    if record["preregistered_final_campaign"]["authorized_to_run"] is not False:
        raise ValueError("final campaign is not authorized")
    return record


def _event_time(summary: Mapping[str, Any], phase: str) -> float | None:
    for event in summary.get("phase_transitions", []):
        if event.get("phase") == phase:
            return float(event["time_s"])
    return None


def _index_at(time_s: np.ndarray, value: float | None) -> int | None:
    if value is None or not len(time_s):
        return None
    return int(np.argmin(np.abs(time_s - value)))


def _per_joint_error_metrics(error: np.ndarray, scale: float) -> dict[str, list[float]]:
    absolute = scale * np.abs(np.asarray(error, dtype=float))
    return {
        "rmse": (scale * np.sqrt(np.mean(np.asarray(error) ** 2, axis=0))).tolist(),
        "p95_abs": np.percentile(absolute, 95, axis=0).tolist(),
        "max_abs": np.max(absolute, axis=0).tolist(),
    }


def _norm_error_metrics(error: np.ndarray) -> dict[str, float | int | None]:
    if not len(error):
        return {"count": 0, "rmse": None, "p95": None, "max": None}
    norm = np.linalg.norm(error, axis=1)
    return {
        "count": int(len(norm)),
        "rmse": float(np.sqrt(np.mean(norm**2))),
        "p95": float(np.percentile(norm, 95)),
        "max": float(np.max(norm)),
    }


def aligned_20ms_wrench_prediction(
    trace: Mapping[str, np.ndarray], horizon_s: float = 0.020
) -> dict[str, Any]:
    """Compare predicted mean wrench with mean physical wrench over the same hold."""

    required = {
        "selected_prediction_time_s",
        "selected_prediction_first_transmitted_wrench_world",
    }
    if any(name not in trace for name in required):
        return {
            "aligned_count": 0,
            "force_vector_error_n": _norm_error_metrics(np.empty((0, 3))),
            "moment_vector_error_nm": _norm_error_metrics(np.empty((0, 3))),
            "peak_force_max_underprediction_n": None,
            "peak_force_metric_available": False,
            "unavailable_reason": "saved trace did not record selected 20 ms horizon diagnostics",
        }
    prediction_time = np.asarray(trace["selected_prediction_time_s"], dtype=float)
    predicted = np.asarray(
        trace["selected_prediction_first_transmitted_wrench_world"], dtype=float
    )
    time = np.asarray(trace["time_s"], dtype=float)
    physical = np.column_stack(
        [
            np.asarray(trace["physical_cuff_force_world_n"], dtype=float),
            np.asarray(trace["physical_cuff_moment_world_nm"], dtype=float),
        ]
    )
    actual_mean: list[np.ndarray] = []
    actual_peak_force: list[float] = []
    valid_prediction: list[np.ndarray] = []
    valid_indices: list[int] = []
    for index, start in enumerate(prediction_time):
        mask = (time > start + 1.0e-12) & (time <= start + horizon_s + 1.0e-12)
        if not np.any(mask):
            continue
        actual_mean.append(np.mean(physical[mask], axis=0))
        actual_peak_force.append(float(np.max(np.linalg.norm(physical[mask, :3], axis=1))))
        valid_prediction.append(predicted[index])
        valid_indices.append(index)
    if not valid_prediction:
        return {
            "aligned_count": 0,
            "force_vector_error_n": _norm_error_metrics(np.empty((0, 3))),
            "moment_vector_error_nm": _norm_error_metrics(np.empty((0, 3))),
            "peak_force_max_underprediction_n": None,
            "peak_force_metric_available": False,
        }
    predicted_array = np.asarray(valid_prediction)
    actual_array = np.asarray(actual_mean)
    peak_key = "selected_prediction_first_hold_peak_force_n"
    peak_underprediction = None
    if peak_key in trace:
        predicted_peak = np.asarray(trace[peak_key], dtype=float)[valid_indices]
        peak_underprediction = float(
            np.max(np.maximum(np.asarray(actual_peak_force) - predicted_peak, 0.0))
        )
    return {
        "aligned_count": int(len(actual_array)),
        "force_vector_error_n": _norm_error_metrics(
            predicted_array[:, :3] - actual_array[:, :3]
        ),
        "moment_vector_error_nm": _norm_error_metrics(
            predicted_array[:, 3:] - actual_array[:, 3:]
        ),
        "peak_force_max_underprediction_n": peak_underprediction,
        "peak_force_metric_available": peak_underprediction is not None,
        "comparison_semantics": (
            "predicted mean transmitted world wrench at Human-cuff reference "
            "over 20 ms versus mean time-aligned physical wrench"
        ),
    }


def score_trace(
    summary: Mapping[str, Any],
    trace: Mapping[str, np.ndarray],
    contract: Mapping[str, Any],
    *,
    long_hold_expected: bool = False,
) -> dict[str, Any]:
    acceptance = contract["evaluation_truth_acceptance"]
    state_acceptance = contract["state_estimation_acceptance"]
    prediction_acceptance = contract["prediction_acceptance"]
    hard = contract["registered_hard_limits_unchanged"]
    time = np.asarray(trace["time_s"], dtype=float)
    q_hat = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)[:, :2]
    dq_hat = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)[:, 2:]
    q_true = np.asarray(trace["evaluation_human_q_rad"], dtype=float)
    dq_true = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    q_error = q_hat - q_true
    dq_error = dq_hat - dq_true
    q_metrics = _per_joint_error_metrics(q_error, 180.0 / np.pi)
    dq_metrics = _per_joint_error_metrics(dq_error, 180.0 / np.pi)

    hold_time = _event_time(summary, "HOLD")
    return_time = _event_time(summary, "RETURN")
    complete_time = _event_time(summary, "COMPLETE")
    hold_index = _index_at(time, hold_time)
    complete_index = _index_at(time, complete_time)
    goal = np.radians(contract["task"]["outbound_goal_target_deg"])
    start = np.radians(contract["task"]["start_return_target_deg"])
    angle_limit = np.asarray(acceptance["terminal_angle_abs_error_deg"])
    velocity_limit = np.asarray(acceptance["arrival_abs_velocity_deg_s"])

    def arrival(index: int | None, target: np.ndarray) -> dict[str, Any]:
        if index is None:
            return {"available": False, "accepted": False}
        q_error_deg = np.degrees(np.abs(q_true[index] - target))
        velocity_deg_s = np.degrees(np.abs(dq_true[index]))
        return {
            "available": True,
            "time_s": float(time[index]),
            "truth_abs_angle_error_deg": q_error_deg.tolist(),
            "truth_abs_velocity_deg_s": velocity_deg_s.tolist(),
            "accepted": bool(
                np.all(q_error_deg <= angle_limit + 1.0e-12)
                and np.all(velocity_deg_s <= velocity_limit + 1.0e-12)
            ),
        }

    outbound_arrival = arrival(hold_index, goal)
    return_arrival = arrival(complete_index, start)
    dwell_s = float(acceptance["continuous_outbound_terminal_set_s"])
    dwell_mask = (
        np.zeros(len(time), dtype=bool)
        if return_time is None
        else (time > return_time - dwell_s - 1.0e-12) & (time <= return_time + 1.0e-12)
    )
    dwell_q_ok = np.all(
        np.degrees(np.abs(q_true[dwell_mask] - goal)) <= angle_limit
    ) if np.any(dwell_mask) else False
    dwell_dq_ok = np.all(
        np.degrees(np.abs(dq_true[dwell_mask])) <= velocity_limit
    ) if np.any(dwell_mask) else False
    dwell_duration = (
        float(time[dwell_mask][-1] - time[dwell_mask][0])
        if np.count_nonzero(dwell_mask) > 1
        else 0.0
    )
    completion_window_q_error = (
        np.max(np.degrees(np.abs(q_error[dwell_mask])), axis=0).tolist()
        if np.any(dwell_mask)
        else None
    )
    completion_window_dq_error = (
        np.max(np.degrees(np.abs(dq_error[dwell_mask])), axis=0).tolist()
        if np.any(dwell_mask)
        else None
    )
    continuous_hold_ok = bool(
        dwell_duration + 0.005 >= dwell_s and dwell_q_ok and dwell_dq_ok
    )

    hold_interval = (
        np.zeros(len(time), dtype=bool)
        if hold_time is None or return_time is None
        else (time >= hold_time - 1.0e-12) & (time <= return_time + 1.0e-12)
    )
    hold_duration = 0.0 if hold_time is None or return_time is None else return_time - hold_time
    last_window_s = float(acceptance["long_hold_last_window_s"])
    last_hold_mask = hold_interval & (time >= (return_time or 0.0) - last_window_s)
    hold_p2p = (
        np.degrees(np.ptp(q_true[last_hold_mask], axis=0)).tolist()
        if np.any(last_hold_mask)
        else None
    )
    hold_quality_ok = (
        None
        if not long_hold_expected
        else bool(
            hold_duration + 0.005 >= acceptance["dedicated_long_hold_s"]
            and hold_p2p is not None
            and np.all(
                np.asarray(hold_p2p)
                <= np.asarray(
                    acceptance["long_hold_last_window_peak_to_peak_angle_deg"]
                )
            )
        )
    )

    wrench_prediction = aligned_20ms_wrench_prediction(
        trace, float(prediction_acceptance["horizon_s"])
    )
    force_prediction = wrench_prediction["force_vector_error_n"]
    moment_prediction = wrench_prediction["moment_vector_error_nm"]
    peak_under = wrench_prediction["peak_force_max_underprediction_n"]
    mean_wrench_prediction_ok = bool(
        force_prediction["rmse"] is not None
        and force_prediction["rmse"] <= prediction_acceptance["physical_force_vector_error_rmse_n"]
        and force_prediction["p95"] <= prediction_acceptance["physical_force_vector_error_p95_n"]
        and moment_prediction["rmse"] <= prediction_acceptance["physical_moment_vector_error_rmse_nm"]
        and moment_prediction["p95"] <= prediction_acceptance["physical_moment_vector_error_p95_nm"]
    )
    prediction_ok = bool(
        mean_wrench_prediction_ok
        and peak_under is not None
        and peak_under
        <= prediction_acceptance["action_hold_peak_force_max_underprediction_n"]
    )
    state_ok = bool(
        np.all(np.asarray(q_metrics["rmse"]) <= state_acceptance["q_rmse_deg"])
        and np.all(np.asarray(q_metrics["p95_abs"]) <= state_acceptance["q_abs_error_p95_deg"])
        and np.all(np.asarray(q_metrics["max_abs"]) <= state_acceptance["q_abs_error_max_deg"])
        and completion_window_q_error is not None
        and np.all(np.asarray(completion_window_q_error) <= state_acceptance["completion_window_q_abs_error_max_deg"])
        and completion_window_dq_error is not None
        and np.all(np.asarray(completion_window_dq_error) <= state_acceptance["completion_window_dq_abs_error_max_deg_s"])
    )
    truth_velocity = np.asarray(summary["peak_abs_evaluation_only_joint_velocity_deg_s"])
    truth_acceleration = np.asarray(summary["peak_abs_evaluation_only_joint_acceleration_deg_s2"])
    online_velocity = np.asarray(summary["peak_abs_estimated_joint_velocity_deg_s"])
    online_acceleration = np.asarray(summary["peak_abs_estimated_joint_acceleration_deg_s2"])
    truth_motion_ok = bool(
        np.all(truth_velocity <= hard["joint_velocity_deg_s"])
        and np.all(truth_acceleration <= hard["joint_acceleration_20ms_deg_s2"])
    )
    hard_limits_and_runtime_safety_ok = bool(
        truth_motion_ok
        and float(summary["peak_physical_cuff_force_n"]) <= hard["physical_cuff_force_gate_n"]
        and not summary.get("brake_event_count", 0)
        and not summary.get("force_gate_event_count", 0)
        and not summary.get("mujoco_warning_counts", {})
        and not summary.get("structural_event_count", 0)
    )
    online_motion_ok = bool(
        np.all(online_velocity <= hard["joint_velocity_deg_s"])
        and np.all(online_acceleration <= hard["joint_acceleration_20ms_deg_s2"])
    )
    online_complete = summary.get("task_status") == "COMPLETE"
    truth_complete = bool(
        online_complete
        and outbound_arrival["accepted"]
        and continuous_hold_ok
        and return_arrival["accepted"]
    )
    duration_limit = (
        acceptance["long_hold_episode_max_duration_s"]
        if long_hold_expected
        else acceptance["normal_episode_max_duration_s"]
    )
    duration_ok = float(summary["task_duration_s"]) <= duration_limit
    acceptance_ok = bool(
        truth_complete
        and duration_ok
        and state_ok
        and prediction_ok
        and hard_limits_and_runtime_safety_ok
        and (hold_quality_ok is not False)
    )
    return {
        "online_result": summary.get("task_status"),
        "abort_reason": summary.get("abort_reason"),
        "online_complete": online_complete,
        "evaluation_truth_complete": truth_complete,
        "evaluation_acceptance": acceptance_ok,
        "false_complete": bool(online_complete and not truth_complete),
        "false_negative_constraint_violation": bool(
            online_motion_ok and not truth_motion_ok
        ),
        "false_positive_abort": bool(
            not online_complete and hard_limits_and_runtime_safety_ok
        ),
        "initialization_failure": summary.get("abort_reason")
        == "INITIAL_CONDITION_OUTSIDE_SETTLED_START_SET",
        "outbound_arrival": outbound_arrival,
        "return_arrival": return_arrival,
        "continuous_outbound_terminal_set": {
            "duration_s": dwell_duration,
            "accepted": continuous_hold_ok,
        },
        "long_hold": {
            "expected": long_hold_expected,
            "duration_s": hold_duration,
            "last_2s_truth_angle_peak_to_peak_deg": hold_p2p,
            "accepted": hold_quality_ok,
        },
        "duration_s": float(summary["task_duration_s"]),
        "duration_limit_s": float(duration_limit),
        "duration_accepted": duration_ok,
        "state_estimation": {
            "q_error_deg": q_metrics,
            "dq_error_deg_s": dq_metrics,
            "completion_window_q_abs_error_max_deg": completion_window_q_error,
            "completion_window_dq_abs_error_max_deg_s": completion_window_dq_error,
            "accepted": state_ok,
        },
        "motion_envelope": {
            "online_peak_velocity_deg_s": online_velocity.tolist(),
            "truth_peak_velocity_deg_s": truth_velocity.tolist(),
            "online_peak_acceleration_deg_s2": online_acceleration.tolist(),
            "truth_peak_acceleration_deg_s2": truth_acceleration.tolist(),
            "online_accepted": online_motion_ok,
            "truth_accepted": truth_motion_ok,
        },
        "wrench_prediction_20ms": {
            **wrench_prediction,
            "mean_wrench_accepted": mean_wrench_prediction_ok,
            "accepted": prediction_ok,
        },
        "physical": {
            "peak_force_n": float(summary["peak_physical_cuff_force_n"]),
            "cumulative_force_n_s": float(summary["cumulative_physical_cuff_force_n_s"]),
            "peak_moment_nm": float(summary["peak_physical_cuff_moment_nm"]),
            "hard_limits_and_runtime_safety_accepted": hard_limits_and_runtime_safety_ok,
        },
        "mpc_status_counts": summary.get("mpc_status_counts", {}),
        "safety_filter_status_counts": summary.get("safety_filter_status_counts", {}),
        "brake_event_count": summary.get("brake_event_count", 0),
        "force_gate_event_count": summary.get("force_gate_event_count", 0),
        "mujoco_warning_counts": summary.get("mujoco_warning_counts", {}),
        "path_freedom": {
            "prescribed_full_q_reference_used": summary.get("prescribed_full_q_reference_used"),
            "fixed_q1_q2_coordination_ratio": summary.get("fixed_q1_q2_coordination_ratio"),
            "path_corridor_active": summary.get("path_corridor_active"),
            "maximum_normalized_progress_difference": summary.get(
                "maximum_normalized_q1_q2_progress_difference"
            ),
        },
        "runtime_ms": summary.get("mpc_runtime_ms", {}),
        "truth_used_online": False,
    }


__all__ = [
    "CONFIG_PATH",
    "ProgressiveTranslationStage5Plant",
    "aligned_20ms_wrench_prediction",
    "load_interface_robustness_contract",
    "score_trace",
]
