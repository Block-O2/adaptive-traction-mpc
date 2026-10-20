#!/usr/bin/env python3
"""Audit the current CR12 MPC prediction foundation without changing control."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
import traction_mpc_stage5.goal_mpc_smoke as smoke_module
from traction_mpc_stage5.human import STAGE5_HUMAN


CONTROL_DT_S = 0.005
PREFIX_OFFSETS_S = np.asarray([0.005, 0.010, 0.015, 0.020])
SELECTED_START_TIMES_S = (0.100, 0.200, 0.260, 0.280, 0.300)
ACCELERATION_LIMITS_DEG_S2 = np.asarray([300.0, 600.0])


def _array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float).copy()


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
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported audit value {type(value)!r}")


class PredictionAuditCR12Plant(Stage5CR12SensorBoundaryPlant):
    """Append-only plant/control telemetry that never feeds back into control."""

    def __init__(self, human: Any, *, interface_parameters: Any) -> None:
        self.state_audit: list[dict[str, Any]] = []
        self.command_audit: list[dict[str, Any]] = []
        super().__init__(human, interface_parameters=interface_parameters)

    def _state_record(self, observation: Any) -> dict[str, Any]:
        return {
            "time_s": float(observation.time_s),
            "robot_q_rad": _array(observation.robot_q_rad),
            "robot_dq_rad_s": _array(observation.robot_dq_rad_s),
            "robot_cuff_position_world_m": _array(observation.attachment_position_m),
            "robot_cuff_rotation_world": _array(
                observation.attachment_rotation_matrix
            ),
            "robot_cuff_linear_velocity_world_m_s": _array(
                observation.attachment_velocity_m_s
            ),
            "robot_cuff_angular_velocity_world_rad_s": _array(
                observation.attachment_angular_velocity_rad_s
            ),
            "physical_cuff_wrench_human_site_world": np.concatenate(
                [observation.cuff_force_vector_n, observation.cuff_moment_vector_nm]
            ),
            "human_q_rad": _array(observation.human_q_rad),
            "human_dq_rad_s": _array(observation.human_dq_rad_s),
            "human_table_contact_active": bool(observation.bed_contact_count > 0),
            "human_table_contact_count": int(observation.bed_contact_count),
            "human_table_contact_force_n": float(observation.bed_force_n),
        }

    def observe(self):
        observation = super().observe()
        record = self._state_record(observation)
        if self.state_audit and math.isclose(
            self.state_audit[-1]["time_s"], record["time_s"], abs_tol=1.0e-12
        ):
            self.state_audit[-1] = record
        else:
            self.state_audit.append(record)
        return observation

    def apply_executable_command(self, preview: Any) -> None:
        self.command_audit.append(
            {
                "time_s": float(self.data.time),
                "wrench_robot_site_world": _array(preview.wrench_total_world),
                "joint_torque_command_nm": _array(preview.joint_torque_command_nm),
                "control_dt_s": float(preview.control_dt_s),
            }
        )
        super().apply_executable_command(preview)


class _CapturedPreview:
    """Transparent proxy that captures the selected prefix once Goal-MPC reads it."""

    def __init__(self, inner: Any, timestamp_s: float, capture: dict[float, Any]):
        self._inner = inner
        self._timestamp_s = float(timestamp_s)
        self._capture = capture

    def __call__(self, actions_nm: np.ndarray):
        return self._inner(actions_nm)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    @property
    def last_prediction(self):
        prediction = self._inner.last_prediction
        if prediction is not None:
            self._capture[round(self._timestamp_s, 12)] = {
                "prediction": deepcopy(prediction),
                "state_rad_rad_s": self._inner.state_rad_rad_s.copy(),
                "interface_state": deepcopy(self._inner.interface_state),
                "human_model": self._inner.human_model,
            }
        return prediction


def _last_by_time(records: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    return {round(float(record["time_s"]), 12): record for record in records}


def _orientation_error_deg(predicted: np.ndarray, actual: np.ndarray) -> float:
    return float(
        np.degrees(
            np.linalg.norm(
                Rotation.from_matrix(predicted @ actual.T).as_rotvec()
            )
        )
    )


def _predicted_cuff_state(
    state: np.ndarray,
    x: np.ndarray,
    u: np.ndarray,
    theta: np.ndarray,
    omega: np.ndarray,
    human_model: Any,
) -> dict[str, np.ndarray]:
    geometry = human_model.geometry
    human_pose = geometry.cuff_pose(state[:2])
    human_linear, human_angular = geometry.cuff_velocity(state[:2], state[2:])
    parameters = CONTROLLER_NOMINAL_INTERFACE
    relative_translation_human = (
        np.asarray(parameters.rest_translation_human_m) + x
    )
    relative_translation_world = (
        human_pose.rotation @ relative_translation_human
    )
    relative_rotation = Rotation.from_rotvec(
        np.asarray(parameters.rest_rotation_rotvec_human_rad) + theta
    ).as_matrix()
    return {
        "position_world_m": human_pose.translation + relative_translation_world,
        "rotation_world": human_pose.rotation @ relative_rotation,
        "linear_velocity_world_m_s": (
            human_linear
            + np.cross(human_angular, relative_translation_world)
            + human_pose.rotation @ u
        ),
        "angular_velocity_world_rad_s": (
            human_angular + human_pose.rotation @ omega
        ),
    }


def _predicted_physical_wrench(
    state: np.ndarray,
    x: np.ndarray,
    u: np.ndarray,
    theta: np.ndarray,
    omega: np.ndarray,
    human_model: Any,
) -> np.ndarray:
    parameters = CONTROLLER_NOMINAL_INTERFACE
    rotation = human_model.geometry.cuff_pose(state[:2]).rotation
    rest_x = np.asarray(parameters.rest_translation_human_m)
    rest_theta = np.asarray(parameters.rest_rotation_rotvec_human_rad)
    force_human = (
        np.asarray(parameters.translation_stiffness_n_m) * (x - rest_x)
        + np.asarray(parameters.translation_damping_ns_m) * u
    )
    couple_human = (
        parameters.rotation_stiffness_nm_rad * (theta - rest_theta)
        + parameters.rotation_damping_nms_rad * omega
    )
    moment_human = couple_human + np.cross(x + rest_x, force_human)
    return np.concatenate([rotation @ force_human, rotation @ moment_human])


def _state_at(
    records: dict[float, dict[str, Any]], timestamp_s: float
) -> dict[str, Any]:
    key = round(float(timestamp_s), 12)
    if key not in records:
        raise RuntimeError(f"missing plant state at {timestamp_s:.3f} s")
    return records[key]


def _trace_index(trace_time: np.ndarray, timestamp_s: float) -> int:
    index = int(np.argmin(np.abs(trace_time - timestamp_s)))
    if not np.isclose(trace_time[index], timestamp_s, atol=1.0e-10, rtol=0.0):
        raise RuntimeError(f"missing trace sample at {timestamp_s:.3f} s")
    return index


def _window_result(
    *,
    start_time_s: float,
    captured: dict[str, Any],
    states: dict[float, dict[str, Any]],
    commands: dict[float, dict[str, Any]],
    trace: dict[str, np.ndarray],
) -> dict[str, Any]:
    prediction = captured["prediction"]
    predicted_states = np.asarray(
        prediction.predicted_prefix_states_rad_rad_s[0], dtype=float
    )
    predicted_x = np.asarray(
        prediction.predicted_prefix_interface_displacement_human_m[0], dtype=float
    )
    predicted_u = np.asarray(
        prediction.predicted_prefix_interface_velocity_human_m_s[0], dtype=float
    )
    predicted_theta = np.asarray(
        prediction.predicted_prefix_interface_rotation_human_rad[0], dtype=float
    )
    predicted_omega = np.asarray(
        prediction.predicted_prefix_interface_angular_velocity_human_rad_s[0],
        dtype=float,
    )
    predicted_command = np.asarray(
        prediction.predicted_prefix_executable_wrench_world[0], dtype=float
    )
    predicted_acceleration = np.asarray(
        prediction.predicted_prefix_acceleration_rad_s2[0], dtype=float
    )
    human_model = captured["human_model"]
    initial_controller_state = np.asarray(captured["state_rad_rad_s"], dtype=float)
    start_actual = _state_at(states, start_time_s)
    trace_time = np.asarray(trace["time_s"], dtype=float)
    start_trace_index = _trace_index(trace_time, start_time_s)
    start_estimated = np.asarray(
        trace["estimated_state_rad_rad_s"][start_trace_index], dtype=float
    )

    prefix_rows = []
    for prefix_index, offset_s in enumerate(PREFIX_OFFSETS_S):
        endpoint_s = start_time_s + float(offset_s)
        actual = _state_at(states, endpoint_s)
        endpoint_trace_index = _trace_index(trace_time, endpoint_s)
        actual_estimated = np.asarray(
            trace["estimated_state_rad_rad_s"][endpoint_trace_index], dtype=float
        )
        predicted_cuff = _predicted_cuff_state(
            predicted_states[prefix_index],
            predicted_x[prefix_index],
            predicted_u[prefix_index],
            predicted_theta[prefix_index],
            predicted_omega[prefix_index],
            human_model,
        )
        predicted_wrench = _predicted_physical_wrench(
            predicted_states[prefix_index],
            predicted_x[prefix_index],
            predicted_u[prefix_index],
            predicted_theta[prefix_index],
            predicted_omega[prefix_index],
            human_model,
        )
        command_time_s = start_time_s + prefix_index * CONTROL_DT_S
        actual_command = commands[round(command_time_s, 12)][
            "wrench_robot_site_world"
        ]
        prefix_rows.append(
            {
                "offset_ms": 1000.0 * float(offset_s),
                "robot": {
                    "prediction_available": False,
                    "predicted_q_rad": None,
                    "predicted_dq_rad_s": None,
                    "actual_q_rad": actual["robot_q_rad"],
                    "actual_dq_rad_s": actual["robot_dq_rad_s"],
                    "actual_delta_q_deg_from_start": np.degrees(
                        actual["robot_q_rad"] - start_actual["robot_q_rad"]
                    ),
                    "actual_delta_dq_deg_s_from_start": np.degrees(
                        actual["robot_dq_rad_s"] - start_actual["robot_dq_rad_s"]
                    ),
                },
                "cuff": {
                    "predicted_position_world_m": predicted_cuff[
                        "position_world_m"
                    ],
                    "actual_position_world_m": actual[
                        "robot_cuff_position_world_m"
                    ],
                    "position_error_mm": 1000.0
                    * float(
                        np.linalg.norm(
                            predicted_cuff["position_world_m"]
                            - actual["robot_cuff_position_world_m"]
                        )
                    ),
                    "orientation_error_deg": _orientation_error_deg(
                        predicted_cuff["rotation_world"],
                        actual["robot_cuff_rotation_world"],
                    ),
                    "predicted_linear_velocity_world_m_s": predicted_cuff[
                        "linear_velocity_world_m_s"
                    ],
                    "actual_linear_velocity_world_m_s": actual[
                        "robot_cuff_linear_velocity_world_m_s"
                    ],
                    "linear_velocity_error_mm_s": 1000.0
                    * float(
                        np.linalg.norm(
                            predicted_cuff["linear_velocity_world_m_s"]
                            - actual["robot_cuff_linear_velocity_world_m_s"]
                        )
                    ),
                    "predicted_angular_velocity_world_rad_s": predicted_cuff[
                        "angular_velocity_world_rad_s"
                    ],
                    "actual_angular_velocity_world_rad_s": actual[
                        "robot_cuff_angular_velocity_world_rad_s"
                    ],
                    "angular_velocity_error_deg_s": float(
                        np.degrees(
                            np.linalg.norm(
                                predicted_cuff["angular_velocity_world_rad_s"]
                                - actual["robot_cuff_angular_velocity_world_rad_s"]
                            )
                        )
                    ),
                },
                "interface_wrench": {
                    "predicted_physical_human_site_world": predicted_wrench,
                    "actual_physical_human_site_world": actual[
                        "physical_cuff_wrench_human_site_world"
                    ],
                    "force_error_norm_n": float(
                        np.linalg.norm(
                            predicted_wrench[:3]
                            - actual["physical_cuff_wrench_human_site_world"][:3]
                        )
                    ),
                    "moment_error_norm_nm": float(
                        np.linalg.norm(
                            predicted_wrench[3:]
                            - actual["physical_cuff_wrench_human_site_world"][3:]
                        )
                    ),
                },
                "human": {
                    "predicted_q_rad": predicted_states[prefix_index, :2],
                    "predicted_dq_rad_s": predicted_states[prefix_index, 2:],
                    "actual_truth_q_rad": actual["human_q_rad"],
                    "actual_truth_dq_rad_s": actual["human_dq_rad_s"],
                    "actual_deployable_q_dq_rad_rad_s": actual_estimated,
                    "truth_q_error_deg": np.degrees(
                        predicted_states[prefix_index, :2]
                        - actual["human_q_rad"]
                    ),
                    "truth_dq_error_deg_s": np.degrees(
                        predicted_states[prefix_index, 2:]
                        - actual["human_dq_rad_s"]
                    ),
                },
                "contact": {
                    "prediction_representation": "ABSENT_NO_EXTERNAL_CONTACT_STATE",
                    "predicted_active": False,
                    "actual_human_table_contact_active": actual[
                        "human_table_contact_active"
                    ],
                    "actual_human_table_contact_count": actual[
                        "human_table_contact_count"
                    ],
                    "actual_human_table_contact_force_n": actual[
                        "human_table_contact_force_n"
                    ],
                },
                "command": {
                    "interval_start_time_s": command_time_s,
                    "predicted_executable_wrench_robot_site_world": (
                        predicted_command[prefix_index]
                    ),
                    "actual_executable_wrench_robot_site_world": actual_command,
                    "absolute_error": np.abs(
                        predicted_command[prefix_index] - actual_command
                    ),
                },
            }
        )

    end_actual = _state_at(states, start_time_s + 0.020)
    end_trace_index = _trace_index(trace_time, start_time_s + 0.020)
    end_estimated = np.asarray(
        trace["estimated_state_rad_rad_s"][end_trace_index], dtype=float
    )
    predicted_20ms = predicted_acceleration[-1]
    deployable_20ms = (end_estimated[2:] - start_estimated[2:]) / 0.020
    truth_20ms = (end_actual["human_dq_rad_s"] - start_actual["human_dq_rad_s"]) / 0.020
    predicted_feasible = bool(prediction.prefix_acceleration_feasible[0])
    realized_feasible = bool(
        np.all(np.abs(np.degrees(deployable_20ms)) <= ACCELERATION_LIMITS_DEG_S2)
    )
    initial_interface = captured["interface_state"]
    initial_predicted_cuff = _predicted_cuff_state(
        initial_controller_state,
        _array(initial_interface.displacement_human_m),
        _array(initial_interface.velocity_human_m_s),
        _array(initial_interface.rotation_error_human_rad),
        _array(initial_interface.angular_velocity_human_rad_s),
        human_model,
    )
    first_command = np.concatenate(
        [
            prediction.executable_batch.force_total_n[0],
            prediction.executable_batch.moment_total_nm[0],
        ]
    )
    actual_first_command = commands[round(start_time_s, 12)][
        "wrench_robot_site_world"
    ]
    return {
        "start_time_s": start_time_s,
        "region": (
            "normal_safe"
            if start_time_s in {0.100, 0.200}
            else "pre_violation"
        ),
        "initialization": {
            "prediction_uses_deployable_controller_state": True,
            "prediction_uses_mujoco_truth": False,
            "controller_state_minus_truth_deg_deg_s": np.degrees(
                initial_controller_state
                - np.concatenate(
                    [start_actual["human_q_rad"], start_actual["human_dq_rad_s"]]
                )
            ),
            "reconstructed_cuff_position_vs_actual_mm": 1000.0
            * float(
                np.linalg.norm(
                    initial_predicted_cuff["position_world_m"]
                    - start_actual["robot_cuff_position_world_m"]
                )
            ),
            "reconstructed_cuff_orientation_vs_actual_deg": (
                _orientation_error_deg(
                    initial_predicted_cuff["rotation_world"],
                    start_actual["robot_cuff_rotation_world"],
                )
            ),
        },
        "command_semantics": {
            "first_prediction_and_execution_command_identical": bool(
                np.allclose(first_command, actual_first_command, atol=1.0e-12, rtol=0.0)
            ),
            "first_command_max_abs_error": float(
                np.max(np.abs(first_command - actual_first_command))
            ),
            "prediction_prefix_offsets_ms": (1000.0 * PREFIX_OFFSETS_S),
            "execution_control_period_s": commands[round(start_time_s, 12)][
                "control_dt_s"
            ],
        },
        "prefix": prefix_rows,
        "human_acceleration_20ms_deg_s2": {
            "predicted": np.degrees(predicted_20ms),
            "realized_deployable": np.degrees(deployable_20ms),
            "realized_mujoco_truth_offline": np.degrees(truth_20ms),
            "prediction_minus_deployable": np.degrees(
                predicted_20ms - deployable_20ms
            ),
        },
        "feasibility": {
            "limits_deg_s2": ACCELERATION_LIMITS_DEG_S2,
            "predicted_feasible": predicted_feasible,
            "realized_deployable_feasible": realized_feasible,
            "classification_changed": predicted_feasible != realized_feasible,
        },
    }


def _aggregate(windows: list[dict[str, Any]]) -> dict[str, Any]:
    safe = [window for window in windows if window["region"] == "normal_safe"]
    near = [window for window in windows if window["region"] == "pre_violation"]

    def maximum(group: list[dict[str, Any]], path: tuple[str, ...]) -> float:
        values = []
        for window in group:
            for row in window["prefix"]:
                value: Any = row
                for key in path:
                    value = value[key]
                values.append(float(np.max(np.abs(np.asarray(value, dtype=float)))))
        return max(values)

    q2_errors = [
        window["human_acceleration_20ms_deg_s2"]["prediction_minus_deployable"][1]
        for window in windows
    ]
    return {
        "robot_state_prediction_available": False,
        "first_missing_stage": "A_ROBOT_JOINT_STATE_PROPAGATION",
        "safe_vs_pre_violation_max_errors": {
            "cuff_position_mm": {
                "safe": maximum(safe, ("cuff", "position_error_mm")),
                "pre_violation": maximum(near, ("cuff", "position_error_mm")),
            },
            "cuff_linear_velocity_mm_s": {
                "safe": maximum(safe, ("cuff", "linear_velocity_error_mm_s")),
                "pre_violation": maximum(
                    near, ("cuff", "linear_velocity_error_mm_s")
                ),
            },
            "physical_force_n": {
                "safe": maximum(safe, ("interface_wrench", "force_error_norm_n")),
                "pre_violation": maximum(
                    near, ("interface_wrench", "force_error_norm_n")
                ),
            },
            "human_dq_deg_s": {
                "safe": maximum(
                    safe,
                    ("human", "truth_dq_error_deg_s"),
                ),
                "pre_violation": maximum(
                    near,
                    ("human", "truth_dq_error_deg_s"),
                ),
            },
        },
        "q2_20ms_prediction_minus_deployable_deg_s2": q2_errors,
        "q2_error_signs": [int(np.sign(value)) for value in q2_errors],
        "classification_change_count": sum(
            int(window["feasibility"]["classification_changed"])
            for window in windows
        ),
        "classification_change_times_s": [
            window["start_time_s"]
            for window in windows
            if window["feasibility"]["classification_changed"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_prediction_foundation_attempt_01",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    holder: dict[str, PredictionAuditCR12Plant] = {}
    captured: dict[float, Any] = {}

    def plant_factory(parameters: Any) -> PredictionAuditCR12Plant:
        plant = PredictionAuditCR12Plant(
            STAGE5_HUMAN, interface_parameters=parameters
        )
        holder["plant"] = plant
        return plant

    original_preview_factory = smoke_module.make_interface_aware_first_action_batch_preview

    def capturing_preview_factory(*factory_args: Any, **factory_kwargs: Any):
        factory_kwargs["capture_prefix_diagnostics"] = True
        inner = original_preview_factory(*factory_args, **factory_kwargs)
        interface_state = factory_args[2]
        return _CapturedPreview(
            inner, interface_state.sample_timestamp_s, captured
        )

    smoke_module.make_interface_aware_first_action_batch_preview = (
        capturing_preview_factory
    )
    try:
        summary = smoke_module.run_goal_mpc_smoke(
            output / "rollout",
            maximum_duration_s=0.35,
            plant_factory=plant_factory,
            plant_case_name="cr12_prediction_foundation_audit",
        )
    finally:
        smoke_module.make_interface_aware_first_action_batch_preview = (
            original_preview_factory
        )

    plant = holder["plant"]
    states = _last_by_time(plant.state_audit)
    commands = _last_by_time(plant.command_audit)
    with np.load(output / "rollout" / "trace.npz") as stored:
        trace = {name: stored[name].copy() for name in stored.files}

    windows = []
    for start_time_s in SELECTED_START_TIMES_S:
        key = round(start_time_s, 12)
        if key not in captured:
            raise RuntimeError(f"missing selected prediction at {start_time_s:.3f} s")
        windows.append(
            _window_result(
                start_time_s=start_time_s,
                captured=captured[key],
                states=states,
                commands=commands,
                trace=trace,
            )
        )

    result = {
        "schema": "stage5_cr12_prediction_foundation_audit_v1",
        "evidence_category": "focused_engineering_diagnostic",
        "decision": "PV-A — ROBOT STATE PROPAGATION IS THE PRIMARY PREDICTION GAP",
        "result": {
            "task_status": summary["task_status"],
            "abort_reason": summary["abort_reason"],
            "last_time_s": float(trace["time_s"][-1]),
        },
        "scope": {
            "selected_start_times_s": SELECTED_START_TIMES_S,
            "prefix_offsets_ms": 1000.0 * PREFIX_OFFSETS_S,
            "same_rollout_control_boundary": True,
            "same_first_executable_command_verified_per_window": True,
            "mujoco_truth_offline_only": True,
            "controller_or_predictor_changed": False,
            "scientific_parameters_changed": False,
        },
        "stage_order": {
            "A_robot_joint_state": "NO_STATE_OR_PROPAGATION_IN_CURRENT_SCREEN",
            "B_cuff_kinematics": "PREDICTED_FROM_HUMAN_AND_NOMINAL_INTERFACE_WITHOUT_ROBOT_STATE",
            "C_interface_wrench": "NOMINAL_INTERFACE_RECURRENCE",
            "D_human_dynamics": "REGISTERED_HUMAN_V2_RECURRENCE",
            "E_contact_external": "NO_EXTERNAL_CONTACT_STATE",
        },
        "windows": windows,
        "aggregate": _aggregate(windows),
        "one_next_model_correction_to_test": (
            "add robot q/dq as explicit state to the existing 5/10/15/20 ms "
            "screening recurrence and propagate the already-defined torque law "
            "before deriving cuff kinematics, interface wrench, and Human response"
        ),
        "scientific_changes": {
            "controller_parameter_changed": False,
            "threshold_changed": False,
            "task_changed": False,
            "contact_model_changed": False,
            "rl_or_value_changed": False,
            "production_code_changed": False,
        },
    }
    result_file = output / "prediction_foundation_audit.json"
    result_file.write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
