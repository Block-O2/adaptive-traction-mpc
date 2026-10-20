"""Pure Stage-5 goal-task state machine with no controller dependency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .config import STAGE5_ROOT


JointPair = tuple[float, float]
JointBounds = tuple[tuple[float, float], tuple[float, float]]

DEFAULT_GOAL_TASK_CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_goal_task_v1.json"


class TaskPhase(str, Enum):
    """The complete Stage-5 goal-task phase vocabulary."""

    OUTBOUND = "OUTBOUND"
    HOLD = "HOLD"
    RETURN = "RETURN"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


def _joint_pair(values: Sequence[float], name: str, scale: float = 1.0) -> JointPair:
    if len(values) != 2:
        raise ValueError(f"{name} must contain q1 and q2")
    result = (scale * float(values[0]), scale * float(values[1]))
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must be finite")
    return result


def _optional_joint_pair(
    values: Sequence[float] | None,
    name: str,
    scale: float,
) -> JointPair | None:
    if values is None:
        return None
    return _joint_pair(values, name, scale)


@dataclass(frozen=True)
class GoalTaskSpec:
    """Immutable, configuration-driven task definition in SI units."""

    name: str
    start_return_target_rad: JointPair
    outbound_goal_target_rad: JointPair
    q_bounds_rad: JointBounds
    joint_angle_completion_tolerance_rad: JointPair
    joint_velocity_completion_tolerance_rad_s: JointPair
    hold_duration_s: float
    phase_timeout_s: float
    task_joint_velocity_limit_rad_s: JointPair | None = None
    task_joint_acceleration_limit_rad_s2: JointPair | None = None
    schema: str = "stage5_goal_task_v1"
    provisional_not_hardware_or_clinically_calibrated: bool = True
    source_fixture: str = ""

    def __post_init__(self) -> None:
        if self.schema != "stage5_goal_task_v1":
            raise ValueError("unexpected Stage-5 goal-task schema")
        if not self.provisional_not_hardware_or_clinically_calibrated:
            raise ValueError("Stage-5 default task must remain explicitly provisional")
        if not self.name:
            raise ValueError("task name must be non-empty")

        for joint, bounds in enumerate(self.q_bounds_rad, start=1):
            if len(bounds) != 2 or not all(math.isfinite(value) for value in bounds):
                raise ValueError(f"q{joint} bounds must be a finite lower/upper pair")
            if bounds[0] >= bounds[1]:
                raise ValueError(f"q{joint} lower bound must be less than upper bound")
            for label, target in (
                ("start/return", self.start_return_target_rad[joint - 1]),
                ("outbound goal", self.outbound_goal_target_rad[joint - 1]),
            ):
                if not bounds[0] <= target <= bounds[1]:
                    raise ValueError(f"{label} q{joint} target lies outside q bounds")

        for name, values in (
            ("joint angle completion tolerance", self.joint_angle_completion_tolerance_rad),
            (
                "joint velocity completion tolerance",
                self.joint_velocity_completion_tolerance_rad_s,
            ),
        ):
            if len(values) != 2 or not all(
                math.isfinite(value) and value > 0.0 for value in values
            ):
                raise ValueError(f"{name} must contain two finite positive values")

        if not math.isfinite(self.hold_duration_s) or self.hold_duration_s <= 0.0:
            raise ValueError("hold duration must be finite and positive")
        if not math.isfinite(self.phase_timeout_s) or self.phase_timeout_s <= 0.0:
            raise ValueError("phase timeout must be finite and positive")
        if self.phase_timeout_s < self.hold_duration_s:
            raise ValueError("phase timeout must permit the configured hold duration")

        for name, values in (
            ("task joint velocity limit", self.task_joint_velocity_limit_rad_s),
            ("task joint acceleration limit", self.task_joint_acceleration_limit_rad_s2),
        ):
            if values is not None and (
                len(values) != 2
                or not all(math.isfinite(value) and value > 0.0 for value in values)
            ):
                raise ValueError(f"{name} must be null or two finite positive values")

        if self.task_joint_velocity_limit_rad_s is not None:
            for completion, limit in zip(
                self.joint_velocity_completion_tolerance_rad_s,
                self.task_joint_velocity_limit_rad_s,
                strict=True,
            ):
                if completion > limit:
                    raise ValueError(
                        "completion velocity tolerance cannot exceed the task velocity limit"
                    )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "GoalTaskSpec":
        """Build an immutable SI-unit task from the human-readable JSON schema."""

        trajectory_contract = payload.get("trajectory_contract")
        if not isinstance(trajectory_contract, Mapping):
            raise ValueError("trajectory_contract must be present")
        forbidden_true = (
            "full_joint_trajectory_provided",
            "fixed_joint_coordination_ratio",
            "path_corridor_active",
        )
        if any(trajectory_contract.get(name) is not False for name in forbidden_true):
            raise ValueError(
                "minimal GoalTaskSpec cannot provide a full trajectory, fixed coordination "
                "ratio, or path corridor"
            )

        radians_per_degree = math.pi / 180.0
        bounds_deg = payload["q_bounds_deg"]
        if not isinstance(bounds_deg, Sequence) or len(bounds_deg) != 2:
            raise ValueError("q_bounds_deg must contain q1 and q2 bounds")
        bounds_rad: JointBounds = (
            _joint_pair(bounds_deg[0], "q1 bounds", radians_per_degree),
            _joint_pair(bounds_deg[1], "q2 bounds", radians_per_degree),
        )
        return cls(
            name=str(payload["name"]),
            start_return_target_rad=_joint_pair(
                payload["start_return_target_deg"],
                "start_return_target_deg",
                radians_per_degree,
            ),
            outbound_goal_target_rad=_joint_pair(
                payload["outbound_goal_target_deg"],
                "outbound_goal_target_deg",
                radians_per_degree,
            ),
            q_bounds_rad=bounds_rad,
            joint_angle_completion_tolerance_rad=_joint_pair(
                payload["joint_angle_completion_tolerance_deg"],
                "joint_angle_completion_tolerance_deg",
                radians_per_degree,
            ),
            joint_velocity_completion_tolerance_rad_s=_joint_pair(
                payload["joint_velocity_completion_tolerance_deg_s"],
                "joint_velocity_completion_tolerance_deg_s",
                radians_per_degree,
            ),
            hold_duration_s=float(payload["hold_duration_s"]),
            phase_timeout_s=float(payload["phase_timeout_s"]),
            task_joint_velocity_limit_rad_s=_optional_joint_pair(
                payload.get("task_joint_velocity_limit_deg_s"),
                "task_joint_velocity_limit_deg_s",
                radians_per_degree,
            ),
            task_joint_acceleration_limit_rad_s2=_optional_joint_pair(
                payload.get("task_joint_acceleration_limit_deg_s2"),
                "task_joint_acceleration_limit_deg_s2",
                radians_per_degree,
            ),
            schema=str(payload.get("schema", "")),
            provisional_not_hardware_or_clinically_calibrated=(
                payload.get("provisional_not_hardware_or_clinically_calibrated") is True
            ),
            source_fixture=str(payload.get("source_fixture", "")),
        )


@dataclass(frozen=True)
class GoalTaskState:
    """Immutable state carried between calls to :func:`transition_phase`."""

    phase: TaskPhase
    phase_elapsed_s: float
    hold_elapsed_s: float
    start_validated: bool
    outbound_hold_completed: bool
    abort_reason: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.phase_elapsed_s) or self.phase_elapsed_s < 0.0:
            raise ValueError("phase elapsed time must be finite and nonnegative")
        if not math.isfinite(self.hold_elapsed_s) or self.hold_elapsed_s < 0.0:
            raise ValueError("hold elapsed time must be finite and nonnegative")
        if self.phase is not TaskPhase.HOLD and self.hold_elapsed_s != 0.0:
            raise ValueError("hold elapsed time must be zero outside HOLD")
        if self.phase in (TaskPhase.RETURN, TaskPhase.COMPLETE) and not (
            self.start_validated and self.outbound_hold_completed
        ):
            raise ValueError("RETURN/COMPLETE requires a valid start and completed outbound hold")
        if self.phase is TaskPhase.ABORTED:
            if not self.abort_reason:
                raise ValueError("ABORTED requires a reason")
        elif self.abort_reason is not None:
            raise ValueError("abort reason is valid only in ABORTED")


@dataclass(frozen=True)
class ControllerCompletionMargin:
    """Controller-only tightening of the immutable task completion set.

    The original :class:`GoalTaskSpec` tolerances remain the task definition.
    This margin compensates conservatively for the deployable estimator's
    observed error; it never admits a state that the original task rejects.
    """

    joint_angle_margin_rad: JointPair = (0.0, 0.0)
    joint_velocity_margin_rad_s: JointPair = (0.0, 0.0)
    source_evidence: str = "none"

    def __post_init__(self) -> None:
        for name, values in (
            ("joint angle margin", self.joint_angle_margin_rad),
            ("joint velocity margin", self.joint_velocity_margin_rad_s),
        ):
            if len(values) != 2 or not all(
                math.isfinite(value) and value >= 0.0 for value in values
            ):
                raise ValueError(f"{name} must contain two finite nonnegative values")

    def tightened_tolerances(self, spec: GoalTaskSpec) -> tuple[JointPair, JointPair]:
        angle = tuple(
            tolerance - margin
            for tolerance, margin in zip(
                spec.joint_angle_completion_tolerance_rad,
                self.joint_angle_margin_rad,
                strict=True,
            )
        )
        velocity = tuple(
            tolerance - margin
            for tolerance, margin in zip(
                spec.joint_velocity_completion_tolerance_rad_s,
                self.joint_velocity_margin_rad_s,
                strict=True,
            )
        )
        if any(value <= 0.0 for value in (*angle, *velocity)):
            raise ValueError("controller completion margins must be below task tolerances")
        return angle, velocity


def load_goal_task_spec(
    path: Path = DEFAULT_GOAL_TASK_CONFIG_PATH,
) -> GoalTaskSpec:
    """Load and validate a Stage-5 task config without controller side effects."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Stage-5 task config must contain a JSON object")
    return GoalTaskSpec.from_mapping(payload)


def load_controller_completion_margin(
    path: Path = DEFAULT_GOAL_TASK_CONFIG_PATH,
) -> ControllerCompletionMargin:
    """Load the controller-only conservative margin from the task config."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    record = payload.get("controller_completion_margin")
    if not isinstance(record, Mapping):
        return ControllerCompletionMargin()
    radians_per_degree = math.pi / 180.0
    result = ControllerCompletionMargin(
        joint_angle_margin_rad=_joint_pair(
            record.get("joint_angle_margin_deg", (0.0, 0.0)),
            "controller joint angle margin",
            radians_per_degree,
        ),
        joint_velocity_margin_rad_s=_joint_pair(
            record.get("joint_velocity_margin_deg_s", (0.0, 0.0)),
            "controller joint velocity margin",
            radians_per_degree,
        ),
        source_evidence=str(record.get("source_evidence", "")),
    )
    result.tightened_tolerances(GoalTaskSpec.from_mapping(payload))
    return result


def goal_error(q_rad: Sequence[float], target_rad: Sequence[float]) -> JointPair:
    """Return target-minus-estimated-state joint error."""

    q = _joint_pair(q_rad, "q_rad")
    target = _joint_pair(target_rad, "target_rad")
    return (target[0] - q[0], target[1] - q[1])


def within_q_bounds(spec: GoalTaskSpec, q_rad: Sequence[float]) -> bool:
    q = _joint_pair(q_rad, "q_rad")
    return all(
        lower <= value <= upper
        for value, (lower, upper) in zip(q, spec.q_bounds_rad, strict=True)
    )


def at_goal(
    spec: GoalTaskSpec,
    q_rad: Sequence[float],
    dq_rad_s: Sequence[float],
    target_rad: Sequence[float],
) -> bool:
    """Test actual estimated joint position and velocity against a target set."""

    q = _joint_pair(q_rad, "q_rad")
    dq = _joint_pair(dq_rad_s, "dq_rad_s")
    error = goal_error(q, target_rad)
    return within_q_bounds(spec, q) and all(
        abs(position_error) <= angle_tolerance
        and abs(velocity) <= velocity_tolerance
        for position_error, angle_tolerance, velocity, velocity_tolerance in zip(
            error,
            spec.joint_angle_completion_tolerance_rad,
            dq,
            spec.joint_velocity_completion_tolerance_rad_s,
            strict=True,
        )
    )


def at_goal_for_online_completion(
    spec: GoalTaskSpec,
    q_rad: Sequence[float],
    dq_rad_s: Sequence[float],
    target_rad: Sequence[float],
    margin: ControllerCompletionMargin,
) -> bool:
    """Apply a controller-only conservative subset of the actual goal set."""

    q = _joint_pair(q_rad, "q_rad")
    dq = _joint_pair(dq_rad_s, "dq_rad_s")
    error = goal_error(q, target_rad)
    angle_tolerance, velocity_tolerance = margin.tightened_tolerances(spec)
    return within_q_bounds(spec, q) and all(
        abs(position_error) <= angle_limit and abs(velocity) <= velocity_limit
        for position_error, angle_limit, velocity, velocity_limit in zip(
            error,
            angle_tolerance,
            dq,
            velocity_tolerance,
            strict=True,
        )
    )


def hold_complete(spec: GoalTaskSpec, state: GoalTaskState) -> bool:
    """Report whether uninterrupted valid HOLD dwell has reached its duration."""

    return (
        state.phase is TaskPhase.HOLD
        and state.hold_elapsed_s + 1.0e-12 >= spec.hold_duration_s
    )


def phase_timed_out(spec: GoalTaskSpec, state: GoalTaskState) -> bool:
    """Test the active phase clock; terminal phases never time out."""

    return state.phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD, TaskPhase.RETURN) and (
        state.phase_elapsed_s + 1.0e-12 >= spec.phase_timeout_s
    )


def true_episode_complete(state: GoalTaskState) -> bool:
    """Require the full validated start, outbound hold, and return sequence."""

    return (
        state.phase is TaskPhase.COMPLETE
        and state.start_validated
        and state.outbound_hold_completed
        and state.abort_reason is None
    )


def abort_episode(state: GoalTaskState, reason: str) -> GoalTaskState:
    """Return an immutable terminal abort while preserving completed milestones."""

    reason = str(reason).strip()
    if not reason:
        raise ValueError("abort reason must be non-empty")
    if state.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
        return state
    return GoalTaskState(
        phase=TaskPhase.ABORTED,
        phase_elapsed_s=state.phase_elapsed_s,
        hold_elapsed_s=0.0,
        start_validated=state.start_validated,
        outbound_hold_completed=state.outbound_hold_completed,
        abort_reason=reason,
    )


def task_limit_violation(
    spec: GoalTaskSpec,
    q_rad: Sequence[float],
    dq_rad_s: Sequence[float],
    ddq_rad_s2: Sequence[float] | None = None,
    *,
    acceleration_authority_valid: bool = True,
) -> str | None:
    """Return a task-level state-limit reason, or ``None`` when valid."""

    q = _joint_pair(q_rad, "q_rad")
    dq = _joint_pair(dq_rad_s, "dq_rad_s")
    if not within_q_bounds(spec, q):
        return "Q_BOUNDS"
    if spec.task_joint_velocity_limit_rad_s is not None and any(
        abs(value) > limit
        for value, limit in zip(dq, spec.task_joint_velocity_limit_rad_s, strict=True)
    ):
        return "TASK_VELOCITY_LIMIT"
    if (
        spec.task_joint_acceleration_limit_rad_s2 is not None
        and acceleration_authority_valid
    ):
        if ddq_rad_s2 is None:
            return "MISSING_TASK_ACCELERATION"
        ddq = _joint_pair(ddq_rad_s2, "ddq_rad_s2")
        if any(
            abs(value) > limit
            for value, limit in zip(
                ddq,
                spec.task_joint_acceleration_limit_rad_s2,
                strict=True,
            )
        ):
            return "TASK_ACCELERATION_LIMIT"
    return None


def start_episode(
    spec: GoalTaskSpec,
    q_rad: Sequence[float],
    dq_rad_s: Sequence[float],
    ddq_rad_s2: Sequence[float] | None = None,
    *,
    acceleration_authority_valid: bool = True,
) -> GoalTaskState:
    """Validate the measured/estimated start set and create OUTBOUND state."""

    violation = task_limit_violation(
        spec,
        q_rad,
        dq_rad_s,
        ddq_rad_s2,
        acceleration_authority_valid=acceleration_authority_valid,
    )
    if violation is not None:
        raise ValueError(f"cannot start episode: {violation}")
    if not at_goal(spec, q_rad, dq_rad_s, spec.start_return_target_rad):
        raise ValueError("cannot start episode outside settled start/return target")
    return GoalTaskState(
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )


def transition_phase(
    spec: GoalTaskSpec,
    state: GoalTaskState,
    q_rad: Sequence[float],
    dq_rad_s: Sequence[float],
    dt_s: float,
    *,
    ddq_rad_s2: Sequence[float] | None = None,
    acceleration_authority_valid: bool = True,
    abort_reason: str | None = None,
    completion_margin: ControllerCompletionMargin | None = None,
) -> GoalTaskState:
    """Advance one task sample using only controller-available state estimates."""

    if state.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
        return state
    if not math.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("dt_s must be finite and positive")
    if abort_reason is not None:
        return abort_episode(state, abort_reason)

    margin = (
        ControllerCompletionMargin()
        if completion_margin is None
        else completion_margin
    )
    margin.tightened_tolerances(spec)

    def online_at_goal(target_rad: Sequence[float]) -> bool:
        return at_goal_for_online_completion(spec, q_rad, dq_rad_s, target_rad, margin)

    violation = task_limit_violation(
        spec,
        q_rad,
        dq_rad_s,
        ddq_rad_s2,
        acceleration_authority_valid=acceleration_authority_valid,
    )
    if violation is not None:
        return abort_episode(state, violation)

    next_phase_elapsed = state.phase_elapsed_s + dt_s
    if state.phase is TaskPhase.OUTBOUND:
        if online_at_goal(spec.outbound_goal_target_rad):
            return GoalTaskState(
                phase=TaskPhase.HOLD,
                phase_elapsed_s=0.0,
                hold_elapsed_s=0.0,
                start_validated=state.start_validated,
                outbound_hold_completed=False,
            )
        candidate = GoalTaskState(
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=next_phase_elapsed,
            hold_elapsed_s=0.0,
            start_validated=state.start_validated,
            outbound_hold_completed=False,
        )
    elif state.phase is TaskPhase.HOLD:
        next_hold_elapsed = (
            state.hold_elapsed_s + dt_s
            if online_at_goal(spec.outbound_goal_target_rad)
            else 0.0
        )
        holding = GoalTaskState(
            phase=TaskPhase.HOLD,
            phase_elapsed_s=next_phase_elapsed,
            hold_elapsed_s=next_hold_elapsed,
            start_validated=state.start_validated,
            outbound_hold_completed=False,
        )
        if hold_complete(spec, holding):
            return GoalTaskState(
                phase=TaskPhase.RETURN,
                phase_elapsed_s=0.0,
                hold_elapsed_s=0.0,
                start_validated=state.start_validated,
                outbound_hold_completed=True,
            )
        candidate = holding
    elif state.phase is TaskPhase.RETURN:
        if online_at_goal(spec.start_return_target_rad):
            return GoalTaskState(
                phase=TaskPhase.COMPLETE,
                phase_elapsed_s=0.0,
                hold_elapsed_s=0.0,
                start_validated=state.start_validated,
                outbound_hold_completed=True,
            )
        candidate = GoalTaskState(
            phase=TaskPhase.RETURN,
            phase_elapsed_s=next_phase_elapsed,
            hold_elapsed_s=0.0,
            start_validated=state.start_validated,
            outbound_hold_completed=True,
        )
    else:  # pragma: no cover - Enum exhaustiveness guard.
        raise ValueError(f"unsupported active task phase: {state.phase}")

    if phase_timed_out(spec, candidate):
        return abort_episode(candidate, f"TIMEOUT_{candidate.phase.value}")
    return candidate


def diagnostic_normalized_progress(
    spec: GoalTaskSpec,
    phase: TaskPhase,
    q_rad: Sequence[float],
) -> float | None:
    """Return path-agnostic distance progress; never use it for completion."""

    if phase is TaskPhase.ABORTED:
        return None
    if phase is TaskPhase.COMPLETE:
        return 1.0
    if phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD):
        source = spec.start_return_target_rad
        target = spec.outbound_goal_target_rad
    elif phase is TaskPhase.RETURN:
        source = spec.outbound_goal_target_rad
        target = spec.start_return_target_rad
    else:  # pragma: no cover - Enum exhaustiveness guard.
        raise ValueError(f"unsupported task phase: {phase}")

    q = _joint_pair(q_rad, "q_rad")
    spans = tuple(upper - lower for lower, upper in spec.q_bounds_rad)
    initial_distance = math.sqrt(
        sum(((target[i] - source[i]) / spans[i]) ** 2 for i in range(2))
    )
    remaining_distance = math.sqrt(
        sum(((target[i] - q[i]) / spans[i]) ** 2 for i in range(2))
    )
    if initial_distance <= 0.0:
        return 1.0
    return min(1.0, max(0.0, 1.0 - remaining_distance / initial_distance))


PROVISIONAL_LOW_MODERATE_GOAL_TASK = load_goal_task_spec()
PROVISIONAL_CONTROLLER_COMPLETION_MARGIN = load_controller_completion_margin()


__all__ = [
    "DEFAULT_GOAL_TASK_CONFIG_PATH",
    "ControllerCompletionMargin",
    "GoalTaskSpec",
    "GoalTaskState",
    "PROVISIONAL_LOW_MODERATE_GOAL_TASK",
    "PROVISIONAL_CONTROLLER_COMPLETION_MARGIN",
    "TaskPhase",
    "abort_episode",
    "at_goal",
    "at_goal_for_online_completion",
    "diagnostic_normalized_progress",
    "goal_error",
    "hold_complete",
    "load_goal_task_spec",
    "load_controller_completion_margin",
    "phase_timed_out",
    "start_episode",
    "task_limit_violation",
    "transition_phase",
    "true_episode_complete",
    "within_q_bounds",
]
