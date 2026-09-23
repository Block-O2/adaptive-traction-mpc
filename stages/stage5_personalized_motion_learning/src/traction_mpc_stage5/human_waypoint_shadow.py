"""Shadow-only Human-waypoint contract for the existing Stage-5 execution path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc_stage3.human import (
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
)
from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage3.reference import CuffPoseReference

from .goal_mpc import _model_inverse_dynamics
from .hold_stabilizer import (
    LoadedHoldEquilibrium,
    filter_stage5_executable_action_with_pose,
    solve_loaded_hold_equilibrium,
)
from .loaded_execution import (
    Stage5LoadedExecutionTarget,
    loaded_execution_target_from_equilibrium,
)
from .task import GoalTaskSpec, TaskPhase
from .task_observation import ControllerTaskObservation


HUMAN_WAYPOINT_SHADOW_CONTRACT_VERSION = (
    "human_waypoint_mpc_shadow_contract_20ms_motion_v2"
)
SCHEDULED_REFERENCE_MOTION_WINDOW_S = 0.020


def _vector(name: str, value: Any, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {length}-vector")
    return result.copy()


@dataclass(frozen=True)
class ScheduledReferenceHistoryStatus:
    """Validity and causal 20 ms anchor for one scheduled-reference decision."""

    valid: bool
    contiguous: bool
    coverage_s: float
    sample_count: int
    maximum_gap_s: float | None
    anchor_q_rad: np.ndarray | None
    anchor_dq_rad_s: np.ndarray | None


class CausalScheduledReferenceMotionHistory:
    """Shared causal reference-history contract for governor and execution mapping."""

    def __init__(self, *, sample_period_s: float, window_s: float = 0.020) -> None:
        if not np.isfinite(sample_period_s) or sample_period_s <= 0.0:
            raise ValueError("sample_period_s must be finite and positive")
        if not np.isfinite(window_s) or window_s <= 0.0:
            raise ValueError("window_s must be finite and positive")
        self.sample_period_s = float(sample_period_s)
        self.window_s = float(window_s)
        self.samples: list[tuple[float, np.ndarray, np.ndarray]] = []

    def _interpolate(self, timestamp_s: float) -> tuple[np.ndarray, np.ndarray] | None:
        if not self.samples:
            return None
        tolerance = 1.0e-12
        first_time, first_q, first_dq = self.samples[0]
        if timestamp_s < first_time - tolerance:
            return None
        if np.isclose(timestamp_s, first_time, atol=tolerance, rtol=0.0):
            return first_q.copy(), first_dq.copy()
        for left, right in zip(self.samples[:-1], self.samples[1:]):
            left_time, left_q, left_dq = left
            right_time, right_q, right_dq = right
            if timestamp_s > right_time + tolerance:
                continue
            if np.isclose(timestamp_s, right_time, atol=tolerance, rtol=0.0):
                return right_q.copy(), right_dq.copy()
            span_s = right_time - left_time
            if span_s <= 0.0:
                raise RuntimeError("scheduled-reference history timestamps must increase")
            fraction = (timestamp_s - left_time) / span_s
            return (
                left_q + fraction * (right_q - left_q),
                left_dq + fraction * (right_dq - left_dq),
            )
        return None

    def status(self, timestamp_s: float) -> ScheduledReferenceHistoryStatus:
        if not np.isfinite(timestamp_s) or timestamp_s < 0.0:
            raise ValueError("scheduled-reference timestamp must be finite and nonnegative")
        target_s = timestamp_s - self.window_s
        anchor = self._interpolate(target_s)
        coverage_s = 0.0 if not self.samples else timestamp_s - self.samples[0][0]
        window_samples = [
            item for item in self.samples if item[0] + 1.0e-12 >= target_s
        ]
        times = np.asarray([item[0] for item in window_samples], dtype=float)
        maximum_gap_s = (
            None if len(times) < 2 else float(np.max(np.diff(times)))
        )
        required_prior_samples = int(round(self.window_s / self.sample_period_s))
        contiguous = bool(
            len(times) >= required_prior_samples
            and times[0] <= target_s + 1.0e-12
            and timestamp_s - times[-1] <= self.sample_period_s + 1.0e-12
            and maximum_gap_s is not None
            and maximum_gap_s <= self.sample_period_s + 1.0e-12
        )
        valid = bool(
            coverage_s + 1.0e-12 >= self.window_s
            and anchor is not None
            and contiguous
        )
        return ScheduledReferenceHistoryStatus(
            valid=valid,
            contiguous=contiguous,
            coverage_s=float(max(0.0, coverage_s)),
            sample_count=len(window_samples),
            maximum_gap_s=maximum_gap_s,
            anchor_q_rad=None if anchor is None else anchor[0],
            anchor_dq_rad_s=None if anchor is None else anchor[1],
        )

    def acceleration_rad_s2(
        self, dq_reference_rad_s: np.ndarray, status: ScheduledReferenceHistoryStatus
    ) -> np.ndarray:
        if not status.valid or status.anchor_dq_rad_s is None:
            raise ValueError("full causal scheduled-reference history is required")
        return (
            _vector("dq_reference_rad_s", dq_reference_rad_s, 2)
            - status.anchor_dq_rad_s
        ) / self.window_s

    def commit(
        self, timestamp_s: float, q_reference_rad: np.ndarray, dq_reference_rad_s: np.ndarray
    ) -> None:
        q_reference = _vector("q_reference_rad", q_reference_rad, 2)
        dq_reference = _vector("dq_reference_rad_s", dq_reference_rad_s, 2)
        if self.samples and np.isclose(
            timestamp_s, self.samples[-1][0], atol=1.0e-12, rtol=0.0
        ):
            if np.allclose(
                q_reference, self.samples[-1][1], atol=1.0e-12, rtol=0.0
            ) and np.allclose(
                dq_reference,
                self.samples[-1][2],
                atol=1.0e-12,
                rtol=0.0,
            ):
                return
            raise ValueError(
                "duplicate scheduled-reference timestamp changed the reference"
            )
        if self.samples and timestamp_s < self.samples[-1][0]:
            raise ValueError("scheduled-reference timestamps must increase")
        self.samples.append(
            (
                float(timestamp_s),
                q_reference,
                dq_reference,
            )
        )

    def last_reference(self) -> tuple[np.ndarray, np.ndarray] | None:
        if not self.samples:
            return None
        _, q_reference, dq_reference = self.samples[-1]
        return q_reference.copy(), dq_reference.copy()


@dataclass(frozen=True)
class HumanWaypointCandidate:
    """One high-level Human state target and its registered task context."""

    label: str
    phase: TaskPhase
    phase_goal_rad: np.ndarray
    q_waypoint_rad: np.ndarray
    dq_waypoint_rad_s: np.ndarray

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("waypoint label must be non-empty")
        if self.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
            raise ValueError("waypoint phase must be executable")
        for name, length in (
            ("phase_goal_rad", 2),
            ("q_waypoint_rad", 2),
            ("dq_waypoint_rad_s", 2),
        ):
            object.__setattr__(self, name, _vector(name, getattr(self, name), length))


@dataclass(frozen=True)
class MappedHumanWaypoint:
    """Deterministic Human waypoint to loaded cuff-reference mapping."""

    candidate: HumanWaypointCandidate
    human_cuff_position_world_m: np.ndarray
    human_cuff_rotation_world: np.ndarray
    human_cuff_linear_velocity_world_m_s: np.ndarray
    human_cuff_angular_velocity_world_rad_s: np.ndarray
    equilibrium: LoadedHoldEquilibrium
    reference: CuffPoseReference
    execution_target: Stage5LoadedExecutionTarget
    version: str = HUMAN_WAYPOINT_SHADOW_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name, length in (
            ("human_cuff_position_world_m", 3),
            ("human_cuff_linear_velocity_world_m_s", 3),
            ("human_cuff_angular_velocity_world_rad_s", 3),
        ):
            object.__setattr__(self, name, _vector(name, getattr(self, name), length))
        rotation = np.asarray(self.human_cuff_rotation_world, dtype=float)
        if rotation.shape != (3, 3) or not np.all(np.isfinite(rotation)):
            raise ValueError("human_cuff_rotation_world must be a finite 3x3 matrix")
        object.__setattr__(self, "human_cuff_rotation_world", rotation.copy())


@dataclass(frozen=True)
class HumanWaypointShadowCommand:
    """One command produced without a short-horizon execution prediction."""

    mapped_waypoint: MappedHumanWaypoint
    desired_human_acceleration_rad_s2: np.ndarray
    generalized_action_nm: np.ndarray
    acceleration_margin_rad_s2: np.ndarray
    motion_envelope_acceleration_rad_s2: np.ndarray
    motion_envelope_history_valid: bool
    motion_envelope_hold: bool
    pd_request_limit_exceeded_diagnostic: bool
    filter_result: Any
    short_horizon_predictor_used: bool = False
    production_authority: bool = False
    shadow_only: bool = True

    def __post_init__(self) -> None:
        for name in (
            "desired_human_acceleration_rad_s2",
            "generalized_action_nm",
            "acceleration_margin_rad_s2",
            "motion_envelope_acceleration_rad_s2",
        ):
            object.__setattr__(self, name, _vector(name, getattr(self, name), 2))
        if self.short_horizon_predictor_used or self.production_authority:
            raise ValueError("Human waypoint V1 must remain shadow-only")
        if not self.shadow_only:
            raise ValueError("Human waypoint V1 must remain shadow-only")


class HumanWaypointMPCShadowContractV1:
    """Map Human q/dq waypoints into the unchanged loaded CR12 command path."""

    def __init__(
        self,
        spec: GoalTaskSpec,
        human_model: Any,
        cuff_allocator: Any,
    ) -> None:
        self.spec = spec
        self.human_model = human_model
        self.cuff_allocator = cuff_allocator
        self.position_gain = np.asarray(TRACKING_KP_RAD_S2_PER_RAD, dtype=float)
        self.velocity_gain = np.asarray(TRACKING_KD_RAD_S2_PER_RAD_S, dtype=float)
        self.reference_motion_history = CausalScheduledReferenceMotionHistory(
            sample_period_s=EXECUTION_CONTROL_DT_S,
            window_s=SCHEDULED_REFERENCE_MOTION_WINDOW_S,
        )

    def _expected_phase_goal(self, phase: TaskPhase) -> np.ndarray:
        return np.asarray(
            self.spec.start_return_target_rad
            if phase is TaskPhase.RETURN
            else self.spec.outbound_goal_target_rad,
            dtype=float,
        )

    def _validate_candidate(self, candidate: HumanWaypointCandidate) -> None:
        expected_goal = self._expected_phase_goal(candidate.phase)
        if not np.allclose(
            candidate.phase_goal_rad, expected_goal, atol=1.0e-12, rtol=0.0
        ):
            raise ValueError("waypoint phase goal does not match the registered task")
        q = candidate.q_waypoint_rad
        task_bounds = np.asarray(self.spec.q_bounds_rad, dtype=float)
        human_bounds = np.column_stack(
            [self.human_model.q_min_rad, self.human_model.q_max_rad]
        )
        if np.any(q < task_bounds[:, 0]) or np.any(q > task_bounds[:, 1]):
            raise ValueError("waypoint lies outside registered task q bounds")
        if np.any(q < human_bounds[:, 0]) or np.any(q > human_bounds[:, 1]):
            raise ValueError("waypoint lies outside Human-model ROM")
        if self.spec.task_joint_velocity_limit_rad_s is not None:
            velocity_limit = np.asarray(
                self.spec.task_joint_velocity_limit_rad_s, dtype=float
            )
            if np.any(np.abs(candidate.dq_waypoint_rad_s) > velocity_limit):
                raise ValueError("waypoint velocity exceeds registered task limits")
        if candidate.phase is TaskPhase.OUTBOUND:
            phase_origin = np.asarray(self.spec.start_return_target_rad, dtype=float)
        elif candidate.phase is TaskPhase.RETURN:
            phase_origin = np.asarray(self.spec.outbound_goal_target_rad, dtype=float)
        else:
            phase_origin = None
        if phase_origin is not None:
            phase_axis = expected_goal - phase_origin
            candidate_axis = candidate.q_waypoint_rad - phase_origin
            inside_phase_origin_tolerance = bool(
                np.all(
                    np.abs(candidate_axis)
                    <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
                    + 1.0e-12
                )
            )
            if (
                float(phase_axis @ candidate_axis) < -1.0e-12
                and not inside_phase_origin_tolerance
            ):
                raise ValueError("waypoint moves away from the registered phase goal")

    def prepare(self, candidate: HumanWaypointCandidate) -> MappedHumanWaypoint:
        """Map one valid Human waypoint using only registered geometry/models."""

        self._validate_candidate(candidate)
        geometry = self.human_model.geometry
        human_pose = geometry.cuff_pose(candidate.q_waypoint_rad)
        human_linear, human_angular = geometry.cuff_velocity(
            candidate.q_waypoint_rad, candidate.dq_waypoint_rad_s
        )
        equilibrium = solve_loaded_hold_equilibrium(
            self.spec,
            self.human_model,
            self.cuff_allocator,
            target_q_rad=candidate.q_waypoint_rad,
            target_dq_rad_s=candidate.dq_waypoint_rad_s,
        )
        if not np.allclose(
            human_pose.translation,
            equilibrium.human_cuff_pose_world.translation,
            atol=1.0e-12,
            rtol=0.0,
        ) or not np.allclose(
            human_pose.rotation,
            equilibrium.human_cuff_pose_world.rotation,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise RuntimeError("loaded mapping changed the registered Human cuff pose")
        execution_target = loaded_execution_target_from_equilibrium(
            equilibrium, self.human_model
        )
        return MappedHumanWaypoint(
            candidate=candidate,
            human_cuff_position_world_m=human_pose.translation,
            human_cuff_rotation_world=human_pose.rotation,
            human_cuff_linear_velocity_world_m_s=human_linear,
            human_cuff_angular_velocity_world_rad_s=human_angular,
            equilibrium=equilibrium,
            reference=equilibrium.low_level_reference,
            execution_target=execution_target,
        )

    def command(
        self,
        *,
        plant: Any,
        measurement: Any,
        observation: ControllerTaskObservation,
        interface_state: Any,
        mapped_waypoint: MappedHumanWaypoint,
    ) -> HumanWaypointShadowCommand:
        """Use existing Human tracking and loaded execution, with no predictor."""

        candidate = mapped_waypoint.candidate
        state = observation.as_array()
        desired_acceleration = (
            self.position_gain * (candidate.q_waypoint_rad - state[:2])
            + self.velocity_gain * (candidate.dq_waypoint_rad_s - state[2:])
        )
        timestamp_s = float(observation.sample_timestamp_s)
        history_status = self.reference_motion_history.status(timestamp_s)
        prior_reference = self.reference_motion_history.last_reference()
        if prior_reference is None:
            motion_envelope_hold = bool(
                np.allclose(
                    candidate.q_waypoint_rad,
                    state[:2],
                    atol=1.0e-12,
                    rtol=0.0,
                )
                and np.allclose(
                    candidate.dq_waypoint_rad_s,
                    state[2:],
                    atol=1.0e-12,
                    rtol=0.0,
                )
            )
        else:
            motion_envelope_hold = bool(
                np.allclose(
                    candidate.q_waypoint_rad,
                    prior_reference[0],
                    atol=1.0e-12,
                    rtol=0.0,
                )
                and np.allclose(
                    candidate.dq_waypoint_rad_s,
                    prior_reference[1],
                    atol=1.0e-12,
                    rtol=0.0,
                )
            )
        if not history_status.valid and not motion_envelope_hold:
            raise ValueError(
                "waypoint motion-envelope history is invalid and progress is not held"
            )
        if self.spec.task_joint_acceleration_limit_rad_s2 is None:
            acceleration_margin = np.full(2, np.inf)
            motion_envelope_acceleration = np.zeros(2)
        else:
            limit = np.asarray(
                self.spec.task_joint_acceleration_limit_rad_s2, dtype=float
            )
            if history_status.valid:
                motion_envelope_acceleration = (
                    self.reference_motion_history.acceleration_rad_s2(
                        candidate.dq_waypoint_rad_s, history_status
                    )
                )
                acceleration_margin = limit - np.abs(motion_envelope_acceleration)
            elif motion_envelope_hold:
                motion_envelope_acceleration = np.zeros(2)
                acceleration_margin = np.zeros(2)
            if history_status.valid and np.any(acceleration_margin < -1.0e-12):
                raise ValueError(
                    "waypoint scheduled 20 ms motion exceeds registered acceleration limits"
                )
        pd_request_limit_exceeded = bool(
            self.spec.task_joint_acceleration_limit_rad_s2 is not None
            and np.any(
                np.abs(desired_acceleration)
                > np.asarray(
                    self.spec.task_joint_acceleration_limit_rad_s2, dtype=float
                )
                + 1.0e-12
            )
        )
        action = _model_inverse_dynamics(
            state[:2], state[2:], desired_acceleration, self.human_model
        )
        filter_result = filter_stage5_executable_action_with_pose(
            plant=plant,
            measurement=measurement,
            observation=observation,
            interface_state=interface_state,
            human_model=self.human_model,
            cuff_allocator=self.cuff_allocator,
            action_nm=action,
            reference=mapped_waypoint.reference,
            execution_target=mapped_waypoint.execution_target,
        )
        self.reference_motion_history.commit(
            timestamp_s,
            candidate.q_waypoint_rad,
            candidate.dq_waypoint_rad_s,
        )
        return HumanWaypointShadowCommand(
            mapped_waypoint=mapped_waypoint,
            desired_human_acceleration_rad_s2=desired_acceleration,
            generalized_action_nm=action,
            acceleration_margin_rad_s2=acceleration_margin,
            motion_envelope_acceleration_rad_s2=motion_envelope_acceleration,
            motion_envelope_history_valid=history_status.valid,
            motion_envelope_hold=motion_envelope_hold,
            pd_request_limit_exceeded_diagnostic=pd_request_limit_exceeded,
            filter_result=filter_result,
        )

    def contract_record(self) -> dict[str, Any]:
        return {
            "version": HUMAN_WAYPOINT_SHADOW_CONTRACT_VERSION,
            "input": [
                "deployable_human_q_hat_dq_hat",
                "registered_task_phase_and_goal",
                "candidate_human_q_dq_waypoint",
            ],
            "mapping": [
                "registered_human_cuff_geometry",
                "existing_loaded_interface_equilibrium",
                "existing_loaded_cuff_pose_twist_execution_reference",
                "existing_safety_filter_and_track_brake_execution",
            ],
            "existing_tracking_gains_reused": {
                "kp_rad_s2_per_rad": self.position_gain.tolist(),
                "kd_rad_s2_per_rad_s": self.velocity_gain.tolist(),
            },
            "acceleration_rejection_semantics": (
                "causal_20ms_scheduled_reference_motion_with_full_history"
            ),
            "invalid_history_behavior": "held_reference_only_otherwise_reject",
            "pd_acceleration_request_role": (
                "inverse_dynamics_execution_input_and_diagnostic_not_motion_envelope_gate"
            ),
            "short_horizon_robot_interface_predictor_used": False,
            "new_robot_controller_added": False,
            "gains_tuned": False,
            "shadow_only": True,
            "production_authority": False,
        }


__all__ = [
    "HUMAN_WAYPOINT_SHADOW_CONTRACT_VERSION",
    "SCHEDULED_REFERENCE_MOTION_WINDOW_S",
    "CausalScheduledReferenceMotionHistory",
    "HumanWaypointCandidate",
    "HumanWaypointMPCShadowContractV1",
    "HumanWaypointShadowCommand",
    "MappedHumanWaypoint",
    "ScheduledReferenceHistoryStatus",
]
