"""Matched short-branch intervention and complete Stage-5 runtime snapshots.

The snapshot stores MuJoCo integration state separately from the controller
graph.  Plant truth is used only to restore the simulated world; it is never
placed in the deployable branch record or used to choose a branch.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import hashlib
import pickle
from typing import Any, Mapping

import mujoco
import numpy as np

from .task import GoalTaskState, TaskPhase


class BranchCoordination(str, Enum):
    HIP_LEADING = "hip_leading"
    BALANCED = "balanced"
    KNEE_LEADING = "knee_leading"


@dataclass(frozen=True)
class ShortBranchSpec:
    anchor_name: str
    phase: TaskPhase
    minimum_progress: float
    duration_s: float
    hip_bias_nm: float
    knee_bias_nm: float
    coordination: BranchCoordination

    def __post_init__(self) -> None:
        if not self.anchor_name:
            raise ValueError("branch anchor name must be non-empty")
        if self.phase not in (TaskPhase.OUTBOUND, TaskPhase.RETURN):
            raise ValueError("v1 matched branches are valid only in moving phases")
        if not 0.0 < self.minimum_progress < 1.0:
            raise ValueError("anchor progress must lie strictly inside the phase")
        if not np.isfinite(self.duration_s) or self.duration_s <= 0.0:
            raise ValueError("short-branch duration must be finite and positive")
        if (
            not np.isfinite(self.hip_bias_nm)
            or not np.isfinite(self.knee_bias_nm)
            or self.hip_bias_nm <= 0.0
            or self.knee_bias_nm <= 0.0
        ):
            raise ValueError("branch bias magnitudes must be finite and positive")

    def action_bias_nm(self) -> np.ndarray:
        if self.coordination is BranchCoordination.BALANCED:
            return np.zeros(2)
        phase_direction = 1.0 if self.phase is TaskPhase.OUTBOUND else -1.0
        hip_leading = phase_direction * np.asarray(
            [self.hip_bias_nm, -self.knee_bias_nm], dtype=float
        )
        return (
            hip_leading
            if self.coordination is BranchCoordination.HIP_LEADING
            else -hip_leading
        )


@dataclass(frozen=True)
class PlantSnapshot:
    integration_state: np.ndarray
    auxiliary_state: dict[str, Any]


@dataclass(frozen=True)
class Stage5RuntimeSnapshot:
    plant: PlantSnapshot
    controller_graph: dict[str, Any]
    runtime_state: dict[str, Any]
    deployable_start: dict[str, Any]
    decision_state_sha256: str


def _copy_array(value: Any) -> np.ndarray:
    return np.asarray(value).copy()


def capture_plant_snapshot(plant: Any) -> PlantSnapshot:
    state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
    state = np.empty(mujoco.mj_stateSize(plant.model, state_spec), dtype=float)
    mujoco.mj_getState(plant.model, plant.data, state, state_spec)

    def robot_state(attribute: str) -> np.ndarray | None:
        robot = getattr(plant, attribute, None)
        if robot is None:
            return None
        result = np.empty(
            mujoco.mj_stateSize(robot.model, state_spec), dtype=float
        )
        mujoco.mj_getState(robot.model, robot.data, result, state_spec)
        return result

    auxiliary = {
        "neutral_robot_q": _copy_array(plant.neutral_robot_q),
        "last_joint_torque": _copy_array(plant.last_joint_torque),
        "last_unclipped_joint_torque": _copy_array(
            plant.last_unclipped_joint_torque
        ),
        "last_force": _copy_array(plant.last_force),
        "last_moment": _copy_array(plant.last_moment),
        "interface_generalized_force": _copy_array(
            plant.interface_generalized_force
        ),
        "interface_history": deepcopy(getattr(plant, "interface_history", [])),
        "last_robot_control_velocity_snapshot": deepcopy(
            getattr(plant, "last_robot_control_velocity_snapshot", None)
        ),
        "measured_robot_model_integration_state": robot_state(
            "_measured_robot_model"
        ),
        "control_velocity_robot_model_integration_state": robot_state(
            "_control_velocity_robot_model"
        ),
        "ik_robot_model_integration_state": robot_state("_ik_robot"),
    }
    return PlantSnapshot(state.copy(), auxiliary)


def restore_plant_snapshot(plant: Any, snapshot: PlantSnapshot) -> None:
    state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
    expected = mujoco.mj_stateSize(plant.model, state_spec)
    if snapshot.integration_state.shape != (expected,):
        raise ValueError("MuJoCo integration snapshot shape changed")
    mujoco.mj_setState(
        plant.model,
        plant.data,
        np.asarray(snapshot.integration_state, dtype=float),
        state_spec,
    )
    auxiliary = snapshot.auxiliary_state
    for name in (
        "neutral_robot_q",
        "last_joint_torque",
        "last_unclipped_joint_torque",
        "last_force",
        "last_moment",
        "interface_generalized_force",
    ):
        target = getattr(plant, name)
        target[...] = np.asarray(auxiliary[name], dtype=target.dtype)
    plant.interface_history = deepcopy(auxiliary["interface_history"])
    plant.last_robot_control_velocity_snapshot = deepcopy(
        auxiliary["last_robot_control_velocity_snapshot"]
    )
    for attribute, state_name in (
        ("_measured_robot_model", "measured_robot_model_integration_state"),
        (
            "_control_velocity_robot_model",
            "control_velocity_robot_model_integration_state",
        ),
        ("_ik_robot", "ik_robot_model_integration_state"),
    ):
        robot = getattr(plant, attribute, None)
        robot_state = auxiliary[state_name]
        if robot is not None and robot_state is not None:
            mujoco.mj_setState(
                robot.model,
                robot.data,
                np.asarray(robot_state, dtype=float),
                state_spec,
            )
            mujoco.mj_forward(robot.model, robot.data)


def _decision_projection(value: Any, *, _seen: set[int] | None = None) -> Any:
    """Remove wall-clock diagnostics while retaining decision-relevant state."""

    if _seen is None:
        _seen = set()
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (float, np.floating)):
        return float(value)
    if isinstance(value, np.ndarray):
        return (str(value.dtype), tuple(value.shape), value.tobytes())
    if isinstance(value, Enum):
        return (value.__class__.__name__, value.value)
    if isinstance(value, np.random.Generator):
        return _decision_projection(value.bit_generator.state, _seen=_seen)
    identity = id(value)
    if identity in _seen:
        return ("cycle", value.__class__.__name__)
    if isinstance(value, Mapping):
        _seen.add(identity)
        result = tuple(
            (str(key), _decision_projection(item, _seen=_seen))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not any(
                token in str(key).lower()
                for token in ("runtime", "timing", "computation", "profile")
            )
        )
        _seen.remove(identity)
        return result
    if isinstance(value, (list, tuple)):
        _seen.add(identity)
        result = tuple(_decision_projection(item, _seen=_seen) for item in value)
        _seen.remove(identity)
        return result
    if hasattr(value, "__dict__"):
        _seen.add(identity)
        result = (
            value.__class__.__qualname__,
            _decision_projection(vars(value), _seen=_seen),
        )
        _seen.remove(identity)
        return result
    if callable(value):
        return ("callable", getattr(value, "__qualname__", repr(value)))
    return (value.__class__.__qualname__, repr(value))


def decision_state_digest(
    plant: PlantSnapshot,
    controller_graph: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(plant.integration_state, dtype="<f8").tobytes())
    projected = _decision_projection(
        {
            "plant_auxiliary": plant.auxiliary_state,
            "controller_graph": controller_graph,
            "runtime_state": runtime_state,
        }
    )
    digest.update(pickle.dumps(projected, protocol=5))
    return digest.hexdigest()


def capture_runtime_snapshot(
    *,
    plant: Any,
    controller_graph: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
    deployable_start: Mapping[str, Any],
) -> Stage5RuntimeSnapshot:
    plant_snapshot = capture_plant_snapshot(plant)
    graph = deepcopy(dict(controller_graph))
    runtime = deepcopy(dict(runtime_state))
    deployable = deepcopy(dict(deployable_start))
    digest = decision_state_digest(plant_snapshot, graph, runtime)
    return Stage5RuntimeSnapshot(
        plant=plant_snapshot,
        controller_graph=graph,
        runtime_state=runtime,
        deployable_start=deployable,
        decision_state_sha256=digest,
    )


def restore_runtime_snapshot(
    plant: Any, snapshot: Stage5RuntimeSnapshot
) -> tuple[dict[str, Any], dict[str, Any]]:
    restore_plant_snapshot(plant, snapshot.plant)
    graph = deepcopy(snapshot.controller_graph)
    runtime = deepcopy(snapshot.runtime_state)
    observed = decision_state_digest(
        capture_plant_snapshot(plant), graph, runtime
    )
    if observed != snapshot.decision_state_sha256:
        raise RuntimeError("snapshot restore did not reproduce decision state")
    return graph, runtime


class MatchedBranchIntervention:
    """One preregistered short coordination bias with snapshot evidence."""

    intervention_kind = "short_action_bias"

    def __init__(self, spec: ShortBranchSpec) -> None:
        self.spec = spec
        self.snapshot: Stage5RuntimeSnapshot | None = None
        self.activation_time_s: float | None = None
        self.bias_solve_times_s: list[float] = []
        self.commanded_biases_nm: list[np.ndarray] = []
        self.prefix_feasible: list[bool] = []

    def should_capture(
        self,
        *,
        phase: TaskPhase,
        progress: float | None,
        high_level_cycle: bool,
    ) -> bool:
        return bool(
            self.snapshot is None
            and high_level_cycle
            and phase is self.spec.phase
            and progress is not None
            and progress >= self.spec.minimum_progress
        )

    def register_snapshot(
        self, snapshot: Stage5RuntimeSnapshot, episode_time_s: float
    ) -> None:
        if self.snapshot is not None:
            raise RuntimeError("matched branch snapshot already captured")
        self.snapshot = snapshot
        self.activation_time_s = float(episode_time_s)

    def active(self, episode_time_s: float, phase: TaskPhase) -> bool:
        if self.activation_time_s is None or phase is not self.spec.phase:
            return False
        elapsed = float(episode_time_s) - self.activation_time_s
        return -1.0e-12 <= elapsed < self.spec.duration_s - 1.0e-12

    def apply(
        self,
        action_nm: np.ndarray,
        *,
        episode_time_s: float,
        phase: TaskPhase,
        prefix_feasible: bool,
    ) -> np.ndarray:
        action = np.asarray(action_nm, dtype=float)
        if not self.active(episode_time_s, phase):
            return action.copy()
        bias = self.spec.action_bias_nm()
        self.bias_solve_times_s.append(float(episode_time_s))
        self.commanded_biases_nm.append(bias.copy())
        self.prefix_feasible.append(bool(prefix_feasible))
        if not prefix_feasible:
            raise RuntimeError("preregistered branch bias is prefix-infeasible")
        return action + bias

    def candidate_action(
        self,
        action_nm: np.ndarray,
        *,
        episode_time_s: float,
        phase: TaskPhase,
    ) -> np.ndarray:
        """Return the preregistered candidate without recording its execution."""

        action = np.asarray(action_nm, dtype=float)
        if not self.active(episode_time_s, phase):
            return action.copy()
        return action + self.spec.action_bias_nm()

    def planning_spec(
        self,
        task: Any,
        *,
        episode_time_s: float,
        phase: TaskPhase,
        q_rad: np.ndarray | None = None,
    ) -> Any:
        """Retain the original goal; v1 branches perturb only total action."""

        del episode_time_s, phase, q_rad
        return task

    def consume_goal_transition(self) -> bool:
        return False

    def report(self) -> dict[str, Any]:
        return {
            "intervention_kind": self.intervention_kind,
            "anchor_name": self.spec.anchor_name,
            "phase": self.spec.phase.value,
            "minimum_progress": self.spec.minimum_progress,
            "coordination": self.spec.coordination.value,
            "duration_s": self.spec.duration_s,
            "registered_action_bias_nm": self.spec.action_bias_nm().tolist(),
            "snapshot_captured": self.snapshot is not None,
            "activation_time_s": self.activation_time_s,
            "decision_state_sha256": (
                None
                if self.snapshot is None
                else self.snapshot.decision_state_sha256
            ),
            "deployable_start": (
                None if self.snapshot is None else self.snapshot.deployable_start
            ),
            "biased_solve_count": len(self.bias_solve_times_s),
            "biased_solve_times_s": self.bias_solve_times_s,
            "all_biased_prefixes_feasible": bool(
                self.prefix_feasible and all(self.prefix_feasible)
            ),
            "control_authority_after_short_branch": "same_frozen_baseline_goal_mpc",
        }


def task_state_record(state: GoalTaskState) -> dict[str, Any]:
    return {
        "phase": state.phase.value,
        "phase_elapsed_s": state.phase_elapsed_s,
        "hold_elapsed_s": state.hold_elapsed_s,
        "start_validated": state.start_validated,
        "outbound_hold_completed": state.outbound_hold_completed,
        "abort_reason": state.abort_reason,
    }


__all__ = [
    "BranchCoordination",
    "MatchedBranchIntervention",
    "PlantSnapshot",
    "ShortBranchSpec",
    "Stage5RuntimeSnapshot",
    "capture_plant_snapshot",
    "capture_runtime_snapshot",
    "decision_state_digest",
    "restore_plant_snapshot",
    "restore_runtime_snapshot",
    "task_state_record",
]
