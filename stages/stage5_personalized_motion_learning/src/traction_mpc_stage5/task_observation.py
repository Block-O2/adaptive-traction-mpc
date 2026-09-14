"""Stage-5 task-observation timestamp/value contract.

The direct robot-pose helper is retained only to reproduce the Goal-MPC v1
audit. Goal-MPC v1.1 control constructs this contract through the independent
interface-aware Human-state observer in ``controller_interface.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np


DEPLOYABLE_ESTIMATOR_Q_DQ = "deployable_estimator_geometry_from_cuff_pose_twist"


@dataclass(frozen=True)
class TaskObservationContract:
    """Timestamp contract for states consumed by the 50 Hz goal MPC."""

    maximum_staleness_s: float = 0.020
    timestamp_tolerance_s: float = 1.0e-9
    source: str = DEPLOYABLE_ESTIMATOR_Q_DQ

    def __post_init__(self) -> None:
        if not math.isfinite(self.maximum_staleness_s) or self.maximum_staleness_s < 0.0:
            raise ValueError("maximum staleness must be finite and nonnegative")
        if not math.isfinite(self.timestamp_tolerance_s) or self.timestamp_tolerance_s < 0.0:
            raise ValueError("timestamp tolerance must be finite and nonnegative")
        if not self.source:
            raise ValueError("observation source must be non-empty")


@dataclass(frozen=True)
class ControllerTaskObservation:
    """Immutable estimated Human state and causal timing metadata."""

    state_rad_rad_s: tuple[float, float, float, float]
    sample_timestamp_s: float
    controller_timestamp_s: float
    source: str
    human_model_version: str

    def __post_init__(self) -> None:
        if len(self.state_rad_rad_s) != 4 or not all(
            math.isfinite(value) for value in self.state_rad_rad_s
        ):
            raise ValueError("task observation state must be a finite q1/q2/dq1/dq2 tuple")
        if (
            not math.isfinite(self.sample_timestamp_s)
            or not math.isfinite(self.controller_timestamp_s)
            or self.sample_timestamp_s < 0.0
            or self.controller_timestamp_s < 0.0
        ):
            raise ValueError("task observation timestamps must be finite and nonnegative")
        if not self.source or not self.human_model_version:
            raise ValueError("task observation source and Human-model version are required")

    @property
    def age_s(self) -> float:
        return self.controller_timestamp_s - self.sample_timestamp_s

    def as_array(self) -> np.ndarray:
        return np.asarray(self.state_rad_rad_s, dtype=float)


DEFAULT_TASK_OBSERVATION_CONTRACT = TaskObservationContract()


def make_task_observation(
    state_rad_rad_s: Sequence[float],
    *,
    sample_timestamp_s: float,
    controller_timestamp_s: float,
    human_model_version: str,
    contract: TaskObservationContract = DEFAULT_TASK_OBSERVATION_CONTRACT,
) -> ControllerTaskObservation:
    """Validate a state already produced by the deployable estimator path."""

    state = np.asarray(state_rad_rad_s, dtype=float)
    if state.shape != (4,) or not np.all(np.isfinite(state)):
        raise ValueError("estimated Human state must be a finite four-vector")
    sample = float(sample_timestamp_s)
    controller = float(controller_timestamp_s)
    age = controller - sample
    tolerance = contract.timestamp_tolerance_s
    if age < -tolerance:
        raise ValueError("task observation sample timestamp is in the future")
    if age > contract.maximum_staleness_s + tolerance:
        raise ValueError(
            f"task observation is stale: age={age:.9g}s, "
            f"limit={contract.maximum_staleness_s:.9g}s"
        )
    return ControllerTaskObservation(
        state_rad_rad_s=tuple(float(value) for value in state),
        sample_timestamp_s=sample,
        controller_timestamp_s=controller,
        source=contract.source,
        human_model_version=str(human_model_version),
    )


def task_observation_from_deployable_estimator_path(
    measurement: Any,
    human_model: Any,
    *,
    human_model_version: str,
    contract: TaskObservationContract = DEFAULT_TASK_OBSERVATION_CONTRACT,
) -> ControllerTaskObservation:
    """Retained v1 robot-side estimator helper for regression/audit replay only."""

    geometry = human_model.geometry
    state = geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    return make_task_observation(
        state,
        sample_timestamp_s=measurement.sample_time_s,
        controller_timestamp_s=measurement.arrival_time_s,
        human_model_version=human_model_version,
        contract=contract,
    )


__all__ = [
    "ControllerTaskObservation",
    "DEFAULT_TASK_OBSERVATION_CONTRACT",
    "DEPLOYABLE_ESTIMATOR_Q_DQ",
    "TaskObservationContract",
    "make_task_observation",
    "task_observation_from_deployable_estimator_path",
]
