"""Identification-only physically coupled cuff-interface predictor v2.

This module is deliberately disconnected from Goal-MPC.  Unlike the retained
control-grade oscillator, it propagates robot and Human cuff motion separately
and recomputes the Kelvin--Voigt load from their relative kinematics.  The
existing windowed estimator is reused through predictor-method substitution;
its fit, embargo, validation, regularization, and trust semantics are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from .controller_interface import CONTROLLER_NOMINAL_INTERFACE
from .config import STAGE5_ROOT
from .interface_identification import (
    InterfaceIdentificationSeries,
    InterfaceParameterScales,
    WindowedInterfacePredictionErrorIdentifier,
    _finite_vector,
)
from .loaded_execution import human_cuff_wrench_to_robot_cuff_command


CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_interface_identification_predictor_v2.json"
)


@dataclass(frozen=True)
class IdentificationPhysicalPredictorV2Config:
    """Fixed reduced robot-side approximation; not an interface parameter."""

    robot_effective_mass_world_kg: tuple[float, float, float] = (
        1.65879917,
        1.97072401,
        1.63691911,
    )
    robot_effective_inertia_world_kg_m2: tuple[float, float, float] = (
        0.1087423433337209,
        0.1087423433337209,
        0.1087423433337209,
    )
    integration_substep_s: float = 0.00025
    model_version: str = "stage5_identification_physical_predictor_v2"

    def __post_init__(self) -> None:
        for name in (
            "robot_effective_mass_world_kg",
            "robot_effective_inertia_world_kg_m2",
        ):
            values = np.asarray(getattr(self, name), dtype=float)
            if values.shape != (3,) or not np.all(np.isfinite(values)) or np.any(values <= 0):
                raise ValueError(f"{name} must contain three positive values")
        if not np.isfinite(self.integration_substep_s) or self.integration_substep_s <= 0:
            raise ValueError("integration_substep_s must be finite and positive")
        if not self.model_version:
            raise ValueError("model_version must be non-empty")


def load_identification_physical_predictor_v2_config(
    path: Path = CONFIG_PATH,
) -> IdentificationPhysicalPredictorV2Config:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_interface_identification_predictor_v2":
        raise ValueError("unexpected identification physical predictor schema")
    if payload.get("connected_to_control") is not False:
        raise ValueError("identification predictor v2 must remain outside control")
    return IdentificationPhysicalPredictorV2Config(
        robot_effective_mass_world_kg=tuple(
            float(value) for value in payload["robot_effective_mass_world_kg"]
        ),
        robot_effective_inertia_world_kg_m2=tuple(
            float(value)
            for value in payload["robot_effective_inertia_world_kg_m2"]
        ),
        integration_substep_s=float(payload["integration_substep_s"]),
        model_version=str(payload["model_version"]),
    )


@dataclass(frozen=True)
class IdentificationPhysicalRolloutV2:
    deployable_measurements: np.ndarray
    human_state: np.ndarray
    interface_state: np.ndarray
    robot_position_world_m: np.ndarray
    robot_rotation_world: np.ndarray
    robot_linear_velocity_world_m_s: np.ndarray
    robot_angular_velocity_world_rad_s: np.ndarray
    physical_wrench_human_site_world: np.ndarray
    robot_net_drive_wrench_world: np.ndarray


class IdentificationPhysicalPredictorV2:
    """Reduced coupled robot/Human predictor with physical Kelvin--Voigt K/D."""

    def __init__(
        self,
        human_model: Any,
        *,
        config: IdentificationPhysicalPredictorV2Config | None = None,
    ) -> None:
        self.human_model = human_model
        self.config = (
            load_identification_physical_predictor_v2_config()
            if config is None
            else config
        )

    def _state_to_robot(
        self, state: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        qdq = state[:4]
        x, relative_velocity, theta, relative_omega = np.split(state[4:], 4)
        human_pose = self.human_model.geometry.cuff_pose(qdq[:2])
        human_linear, human_angular = self.human_model.geometry.cuff_velocity(
            qdq[:2], qdq[2:]
        )
        lever_world = human_pose.rotation @ x
        return (
            human_pose.translation + lever_world,
            human_pose.rotation @ Rotation.from_rotvec(theta).as_matrix(),
            human_linear
            + np.cross(human_angular, lever_world)
            + human_pose.rotation @ relative_velocity,
            human_angular + human_pose.rotation @ relative_omega,
        )

    def _constitutive_wrench(
        self,
        qdq: np.ndarray,
        interface_state: np.ndarray,
        parameters: InterfaceParameterScales,
    ) -> np.ndarray:
        interface = parameters.scaled_parameters(CONTROLLER_NOMINAL_INTERFACE)
        x, relative_velocity, theta, relative_omega = np.split(interface_state, 4)
        rest_x = np.asarray(interface.rest_translation_human_m)
        rest_theta = np.asarray(interface.rest_rotation_rotvec_human_rad)
        force_human = (
            np.asarray(interface.translation_stiffness_n_m) * (x - rest_x)
            + np.asarray(interface.translation_damping_ns_m) * relative_velocity
        )
        couple_human = (
            interface.rotation_stiffness_nm_rad * (theta - rest_theta)
            + interface.rotation_damping_nms_rad * relative_omega
        )
        moment_human = couple_human + np.cross(x, force_human)
        rotation = self.human_model.geometry.cuff_pose(qdq[:2]).rotation
        return np.r_[rotation @ force_human, rotation @ moment_human]

    def measurement_from_state(
        self,
        parameters: InterfaceParameterScales,
        state: np.ndarray,
    ) -> np.ndarray:
        joint_state = _finite_vector(state, (16,), "physical predictor v2 state")
        robot_position, robot_rotation, robot_linear, robot_angular = (
            self._state_to_robot(joint_state)
        )
        wrench = self._constitutive_wrench(
            joint_state[:4], joint_state[4:], parameters
        )
        return np.r_[
            robot_position,
            Rotation.from_matrix(robot_rotation).as_rotvec(),
            robot_linear,
            robot_angular,
            wrench,
        ]

    def _relative_state(
        self,
        qdq: np.ndarray,
        robot_position: np.ndarray,
        robot_rotation: np.ndarray,
        robot_linear: np.ndarray,
        robot_angular: np.ndarray,
    ) -> np.ndarray:
        human_pose = self.human_model.geometry.cuff_pose(qdq[:2])
        human_linear, human_angular = self.human_model.geometry.cuff_velocity(
            qdq[:2], qdq[2:]
        )
        lever_world = robot_position - human_pose.translation
        x = human_pose.rotation.T @ lever_world
        relative_velocity = human_pose.rotation.T @ (
            robot_linear - human_linear - np.cross(human_angular, lever_world)
        )
        theta = Rotation.from_matrix(
            human_pose.rotation.T @ robot_rotation
        ).as_rotvec()
        relative_omega = human_pose.rotation.T @ (robot_angular - human_angular)
        return np.r_[x, relative_velocity, theta, relative_omega]

    def predict_rollout(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> IdentificationPhysicalRolloutV2:
        state = _finite_vector(initial_state, (16,), "physical predictor v2 state")
        if start_index < 0 or start_index + step_count >= len(series.time_s):
            raise ValueError("prediction window is outside the saved series")
        qdq = state[:4].copy()
        interface_state = state[4:].copy()
        robot_position, robot_rotation, robot_linear, robot_angular = (
            self._state_to_robot(state)
        )
        mass = np.asarray(self.config.robot_effective_mass_world_kg)
        inertia = np.asarray(self.config.robot_effective_inertia_world_kg_m2)

        outputs = []
        human_states = []
        interface_states = []
        robot_positions = []
        robot_rotations = []
        robot_linears = []
        robot_angulars = []
        physical_wrenches = []
        net_drives = []
        for offset in range(step_count):
            sample_index = start_index + offset + 1
            interval = float(
                series.time_s[sample_index] - series.time_s[sample_index - 1]
            )
            ratio = interval / self.config.integration_substep_s
            substeps = int(round(ratio))
            if substeps < 1 or not np.isclose(ratio, substeps, atol=1.0e-9):
                raise ValueError("v2 integration substep must divide every sample interval")
            dt_s = interval / substeps
            command = np.asarray(series.executed_wrench_world[sample_index], dtype=float)
            net_drive = np.zeros(6)
            for _ in range(substeps):
                wrench_human = self._constitutive_wrench(
                    qdq, interface_state, parameters
                )
                robot_from_human = robot_position - self.human_model.geometry.cuff_pose(
                    qdq[:2]
                ).translation
                wrench_robot_reference = human_cuff_wrench_to_robot_cuff_command(
                    wrench_human, robot_from_human
                )
                generalized_input = (
                    self.human_model.geometry.generalized_input_from_wrench(
                        qdq[:2], wrench_human[:3], wrench_human[3:]
                    )
                )
                qdq = self.human_model.step_dynamics(qdq, generalized_input, dt_s)

                net_drive = command - wrench_robot_reference
                robot_linear = robot_linear + dt_s * net_drive[:3] / mass
                robot_angular = robot_angular + dt_s * net_drive[3:] / inertia
                robot_position = robot_position + dt_s * robot_linear
                robot_rotation = (
                    Rotation.from_rotvec(dt_s * robot_angular).as_matrix()
                    @ robot_rotation
                )
                interface_state = self._relative_state(
                    qdq,
                    robot_position,
                    robot_rotation,
                    robot_linear,
                    robot_angular,
                )
            joint_state = np.r_[qdq, interface_state]
            output = self.measurement_from_state(parameters, joint_state)
            outputs.append(output)
            human_states.append(qdq.copy())
            interface_states.append(interface_state.copy())
            robot_positions.append(robot_position.copy())
            robot_rotations.append(robot_rotation.copy())
            robot_linears.append(robot_linear.copy())
            robot_angulars.append(robot_angular.copy())
            physical_wrenches.append(output[12:].copy())
            net_drives.append(net_drive.copy())
        return IdentificationPhysicalRolloutV2(
            deployable_measurements=np.asarray(outputs),
            human_state=np.asarray(human_states),
            interface_state=np.asarray(interface_states),
            robot_position_world_m=np.asarray(robot_positions),
            robot_rotation_world=np.asarray(robot_rotations),
            robot_linear_velocity_world_m_s=np.asarray(robot_linears),
            robot_angular_velocity_world_rad_s=np.asarray(robot_angulars),
            physical_wrench_human_site_world=np.asarray(physical_wrenches),
            robot_net_drive_wrench_world=np.asarray(net_drives),
        )

    def predict_measurements(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> np.ndarray:
        return self.predict_rollout(
            series, start_index, step_count, parameters, initial_state
        ).deployable_measurements


class PhysicalInterfaceIdentifierV2(WindowedInterfacePredictionErrorIdentifier):
    """Existing estimator with only its identification prediction model replaced."""

    def __init__(self, *args: Any, predictor_config: IdentificationPhysicalPredictorV2Config | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.physical_predictor = IdentificationPhysicalPredictorV2(
            self.human_model, config=predictor_config
        )

    def measurement_from_state(
        self, parameters: InterfaceParameterScales, state: np.ndarray
    ) -> np.ndarray:
        return self.physical_predictor.measurement_from_state(parameters, state)

    def predict_rollout(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> IdentificationPhysicalRolloutV2:
        return self.physical_predictor.predict_rollout(
            series, start_index, step_count, parameters, initial_state
        )

    def predict_measurements(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> np.ndarray:
        return self.physical_predictor.predict_measurements(
            series, start_index, step_count, parameters, initial_state
        )


__all__ = [
    "IdentificationPhysicalPredictorV2",
    "IdentificationPhysicalPredictorV2Config",
    "IdentificationPhysicalRolloutV2",
    "PhysicalInterfaceIdentifierV2",
    "load_identification_physical_predictor_v2_config",
]
