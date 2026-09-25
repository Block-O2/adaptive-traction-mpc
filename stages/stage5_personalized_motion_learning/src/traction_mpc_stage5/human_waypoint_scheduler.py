"""Deterministic quintic scheduling for shadow Human-waypoint execution."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage3.human import (
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
)

from .geometry import STAGE5_GEOMETRY
from .human import STAGE5_HUMAN
from .human_waypoint_shadow import (
    SCHEDULED_REFERENCE_MOTION_WINDOW_S,
    CausalScheduledReferenceMotionHistory,
    HumanWaypointCandidate,
)
from .task import GoalTaskSpec, TaskPhase


HUMAN_WAYPOINT_SCHEDULER_VERSION = (
    "human_waypoint_quintic_scheduler_reference_motion_governor_v2"
)
SCHEDULER_REFERENCE_PERIOD_S = EXECUTION_CONTROL_DT_S


def _vector(name: str, value: Any) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (2,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite two-vector")
    return result.copy()


def shank_table_clearance_m(
    q_rad: np.ndarray, human_geometry: Any = STAGE5_HUMAN
) -> np.ndarray | float:
    """Return geometric shank-capsule clearance to the existing bed plane."""

    q = np.asarray(q_rad, dtype=float)
    if q.shape[-1] != 2 or not np.all(np.isfinite(q)):
        raise ValueError("q_rad must end in a finite two-vector")
    rows = np.atleast_2d(q)
    q1 = rows[:, 0]
    phi = rows[:, 0] - rows[:, 1]
    plane_x = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 0])
    plane_z = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 2])
    hip_z = float(STAGE5_GEOMETRY.world_from_human.translation[2])
    knee_z = hip_z + float(human_geometry.thigh_length_m) * (
        np.cos(q1) * plane_x[2] + np.sin(q1) * plane_z[2]
    )
    ankle_z = knee_z + float(human_geometry.shank_length_m) * (
        np.cos(phi) * plane_x[2] + np.sin(phi) * plane_z[2]
    )
    clearance = np.minimum(knee_z, ankle_z) - SHANK_RADIUS_M - BED_HEIGHT_M
    return float(clearance[0]) if q.ndim == 1 else clearance


class WaypointGeometryInfeasible(ValueError):
    """The requested reference enters the existing contact geometry."""


@dataclass(frozen=True)
class ScheduledHumanReferenceSample:
    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    ddq_rad_s2: np.ndarray

    def __post_init__(self) -> None:
        for name in ("q_rad", "dq_rad_s", "ddq_rad_s2"):
            object.__setattr__(self, name, _vector(name, getattr(self, name)))


@dataclass(frozen=True)
class QuinticHumanWaypointSchedule:
    """One finite, immutable Human q/dq transition or registered HOLD."""

    candidate: HumanWaypointCandidate
    start_q_rad: np.ndarray
    start_dq_rad_s: np.ndarray
    duration_s: float
    coefficients: np.ndarray
    maximum_reference_velocity_rad_s: np.ndarray
    maximum_reference_acceleration_rad_s2: np.ndarray
    maximum_causal_20ms_reference_acceleration_rad_s2: np.ndarray
    maximum_nominal_tracking_acceleration_rad_s2: np.ndarray
    nominal_completion_time_s: float
    minimum_reference_shank_clearance_m: float
    feasibility_semantics: str = "legacy_reference_plus_pd_tracking_preview"
    reference_period_s: float = SCHEDULER_REFERENCE_PERIOD_S
    version: str = HUMAN_WAYPOINT_SCHEDULER_VERSION
    continuous_clearance_certificate: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_q_rad", _vector("start_q_rad", self.start_q_rad))
        object.__setattr__(
            self, "start_dq_rad_s", _vector("start_dq_rad_s", self.start_dq_rad_s)
        )
        for name in (
            "maximum_reference_velocity_rad_s",
            "maximum_reference_acceleration_rad_s2",
            "maximum_causal_20ms_reference_acceleration_rad_s2",
            "maximum_nominal_tracking_acceleration_rad_s2",
        ):
            object.__setattr__(self, name, _vector(name, getattr(self, name)))
        coefficients = np.asarray(self.coefficients, dtype=float)
        if coefficients.shape != (2, 6) or not np.all(np.isfinite(coefficients)):
            raise ValueError("coefficients must be a finite 2x6 matrix")
        object.__setattr__(self, "coefficients", coefficients.copy())
        if not math.isfinite(self.duration_s) or self.duration_s <= 0.0:
            raise ValueError("duration_s must be finite and positive")
        if not math.isfinite(self.reference_period_s) or self.reference_period_s <= 0.0:
            raise ValueError("reference_period_s must be finite and positive")
        if not math.isfinite(self.minimum_reference_shank_clearance_m):
            raise ValueError("minimum clearance must be finite")
        if not math.isfinite(self.nominal_completion_time_s) or self.nominal_completion_time_s < 0.0:
            raise ValueError("nominal completion time must be finite and nonnegative")

    def sample(self, elapsed_s: float) -> ScheduledHumanReferenceSample:
        if not math.isfinite(elapsed_s) or elapsed_s < 0.0:
            raise ValueError("elapsed_s must be finite and nonnegative")
        time_s = min(float(elapsed_s), self.duration_s)
        normalized = time_s / self.duration_s
        powers = np.asarray([normalized**index for index in range(6)])
        velocity_powers = np.asarray(
            [0.0, 1.0, 2.0 * normalized, 3.0 * normalized**2,
             4.0 * normalized**3, 5.0 * normalized**4]
        )
        acceleration_powers = np.asarray(
            [0.0, 0.0, 2.0, 6.0 * normalized, 12.0 * normalized**2,
             20.0 * normalized**3]
        )
        return ScheduledHumanReferenceSample(
            q_rad=self.coefficients @ powers,
            dq_rad_s=(self.coefficients @ velocity_powers) / self.duration_s,
            ddq_rad_s2=(self.coefficients @ acceleration_powers)
            / self.duration_s**2,
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "method": "quintic_boundary_state_interpolation",
            "phase": self.candidate.phase.value,
            "duration_s": self.duration_s,
            "reference_period_s": self.reference_period_s,
            "start_q_rad": self.start_q_rad.tolist(),
            "start_dq_rad_s": self.start_dq_rad_s.tolist(),
            "target_q_rad": self.candidate.q_waypoint_rad.tolist(),
            "target_dq_rad_s": self.candidate.dq_waypoint_rad_s.tolist(),
            "maximum_reference_velocity_rad_s": (
                self.maximum_reference_velocity_rad_s.tolist()
            ),
            "maximum_reference_acceleration_rad_s2": (
                self.maximum_reference_acceleration_rad_s2.tolist()
            ),
            "maximum_causal_20ms_reference_acceleration_rad_s2": (
                self.maximum_causal_20ms_reference_acceleration_rad_s2.tolist()
            ),
            "maximum_nominal_tracking_acceleration_rad_s2": (
                self.maximum_nominal_tracking_acceleration_rad_s2.tolist()
            ),
            "nominal_completion_time_s": self.nominal_completion_time_s,
            "minimum_reference_shank_clearance_m": (
                self.minimum_reference_shank_clearance_m
            ),
            "feasibility_semantics": self.feasibility_semantics,
            "continuous_clearance_certificate": self.continuous_clearance_certificate,
            "learned": False,
            "new_safety_margin": False,
        }


def _quintic_coefficients(
    start_q: np.ndarray,
    start_dq: np.ndarray,
    target_q: np.ndarray,
    target_dq: np.ndarray,
    duration_s: float,
) -> np.ndarray:
    coefficients = np.zeros((2, 6), dtype=float)
    coefficients[:, 0] = start_q
    coefficients[:, 1] = duration_s * start_dq
    system = np.asarray(
        [
            [1.0, 1.0, 1.0],
            [3.0, 4.0, 5.0],
            [6.0, 12.0, 20.0],
        ]
    )
    right_hand_side = np.column_stack(
        [
            target_q - coefficients[:, 0] - coefficients[:, 1],
            duration_s * target_dq - coefficients[:, 1],
            np.zeros(2),
        ]
    )
    coefficients[:, 3:] = np.linalg.solve(system, right_hand_side.T).T
    return coefficients


def _real_unit_roots(coefficients_descending: np.ndarray) -> list[float]:
    roots = np.roots(np.trim_zeros(coefficients_descending, trim="f"))
    return [
        float(root.real)
        for root in roots
        if abs(float(root.imag)) <= 1.0e-10
        and -1.0e-12 <= float(root.real) <= 1.0 + 1.0e-12
    ]


def _polynomial_extrema(coefficients: np.ndarray, duration_s: float) -> tuple[np.ndarray, np.ndarray]:
    maximum_velocity = np.zeros(2)
    maximum_acceleration = np.zeros(2)
    for joint in range(2):
        c = coefficients[joint]
        acceleration_roots = _real_unit_roots(
            np.asarray([20.0 * c[5], 12.0 * c[4], 6.0 * c[3], 2.0 * c[2]])
        )
        jerk_roots = _real_unit_roots(
            np.asarray([60.0 * c[5], 24.0 * c[4], 6.0 * c[3]])
        )
        velocity_points = np.asarray([0.0, 1.0, *acceleration_roots])
        acceleration_points = np.asarray([0.0, 1.0, *jerk_roots])
        velocity = (
            c[1]
            + 2.0 * c[2] * velocity_points
            + 3.0 * c[3] * velocity_points**2
            + 4.0 * c[4] * velocity_points**3
            + 5.0 * c[5] * velocity_points**4
        ) / duration_s
        acceleration = (
            2.0 * c[2]
            + 6.0 * c[3] * acceleration_points
            + 12.0 * c[4] * acceleration_points**2
            + 20.0 * c[5] * acceleration_points**3
        ) / duration_s**2
        maximum_velocity[joint] = float(np.max(np.abs(velocity)))
        maximum_acceleration[joint] = float(np.max(np.abs(acceleration)))
    return maximum_velocity, maximum_acceleration


def _maximum_causal_reference_acceleration(
    coefficients: np.ndarray,
    duration_s: float,
    sample_period_s: float,
) -> np.ndarray:
    """Evaluate the scheduled dq change over the shared causal 20 ms window."""

    step_count = int(math.ceil(duration_s / sample_period_s - 1.0e-12))
    times = np.minimum(
        np.arange(step_count + 1, dtype=float) * sample_period_s,
        duration_s,
    )
    normalized = times / duration_s
    velocity_powers = np.vstack(
        [
            np.zeros_like(normalized),
            np.ones_like(normalized),
            2.0 * normalized,
            3.0 * normalized**2,
            4.0 * normalized**3,
            5.0 * normalized**4,
        ]
    )
    velocity = (coefficients @ velocity_powers).T / duration_s
    history_steps = int(
        round(SCHEDULED_REFERENCE_MOTION_WINDOW_S / sample_period_s)
    )
    prefix = np.repeat(velocity[:1], history_steps, axis=0)
    extended = np.vstack([prefix, velocity])
    acceleration = (
        extended[history_steps:] - extended[:-history_steps]
    ) / SCHEDULED_REFERENCE_MOTION_WINDOW_S
    return np.max(np.abs(acceleration), axis=0)


class QuinticHumanWaypointSchedulerV1:
    """Find the shortest registered-grid quintic satisfying existing limits."""

    def __init__(
        self,
        spec: GoalTaskSpec,
        human_model: Any,
        *,
        reference_period_s: float = SCHEDULER_REFERENCE_PERIOD_S,
        human_geometry: Any = STAGE5_HUMAN,
        clearance_evaluator: Callable[[np.ndarray], np.ndarray | float] | None = None,
        clearance_source: str = "STRUCTURAL_PRIOR_STAGE5_GEOMETRY",
        preserve_task_endpoint_clearance_floor: bool = False,
        require_continuous_nonpenetrating_path: bool = False,
        use_duration_lower_bound: bool = False,
        reference_velocity_fraction: float = 1.0,
        reference_acceleration_fraction: float = 1.0,
    ) -> None:
        if not math.isfinite(reference_period_s) or reference_period_s <= 0.0:
            raise ValueError("reference_period_s must be finite and positive")
        self.spec = spec
        self.human_model = human_model
        self.human_geometry = human_geometry
        self.clearance_evaluator = clearance_evaluator
        self.clearance_source = str(clearance_source)
        self.preserve_task_endpoint_clearance_floor = bool(
            preserve_task_endpoint_clearance_floor
        )
        self.require_continuous_nonpenetrating_path = bool(
            require_continuous_nonpenetrating_path
        )
        self.use_duration_lower_bound = bool(use_duration_lower_bound)
        for name, value in (("reference_velocity_fraction", reference_velocity_fraction),
                            ("reference_acceleration_fraction", reference_acceleration_fraction)):
            if isinstance(value, bool) or not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f"{name} must be finite and in (0,1]")
            setattr(self, name, float(value))
        if self.require_continuous_nonpenetrating_path and not callable(
            getattr(clearance_evaluator, "certified_minimum", None)
        ):
            raise ValueError("strict hard-table path requires a continuous-clearance certificate")
        if not self.clearance_source:
            raise ValueError("clearance_source must be non-empty")
        self.reference_period_s = float(reference_period_s)
        self.position_gain = np.asarray(TRACKING_KP_RAD_S2_PER_RAD, dtype=float)
        self.velocity_gain = np.asarray(TRACKING_KD_RAD_S2_PER_RAD_S, dtype=float)
        self.execution_period_s = float(EXECUTION_CONTROL_DT_S)
        if not np.isclose(
            round(self.reference_period_s / self.execution_period_s)
            * self.execution_period_s,
            self.reference_period_s,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise ValueError("reference period must be divisible by execution period")

    def _clearance_m(self, q_rad: np.ndarray) -> np.ndarray | float:
        if self.clearance_evaluator is not None:
            value = self.clearance_evaluator(np.asarray(q_rad, dtype=float))
            result = np.asarray(value, dtype=float)
            expected = np.asarray(q_rad).shape[:-1]
            if result.shape != expected or not np.all(np.isfinite(result)):
                raise ValueError(
                    "session clearance evaluator must return one finite value per q sample"
                )
            return float(result) if result.ndim == 0 else result
        return shank_table_clearance_m(q_rad, self.human_geometry)

    def _expected_goal(self, phase: TaskPhase) -> np.ndarray:
        return np.asarray(
            self.spec.start_return_target_rad
            if phase is TaskPhase.RETURN
            else self.spec.outbound_goal_target_rad,
            dtype=float,
        )

    def _path_clearance_is_valid(
        self, clearance_m: np.ndarray, candidate: HumanWaypointCandidate
    ) -> bool:
        """Require nonpenetration and optionally preserve the task endpoint floor."""

        clearance = np.asarray(clearance_m, dtype=float)
        floor_m = 0.0
        if self.preserve_task_endpoint_clearance_floor:
            task_endpoints = np.vstack(
                [self.spec.start_return_target_rad, candidate.phase_goal_rad]
            )
            floor_m = float(np.min(self._clearance_m(task_endpoints)))
        if self.require_continuous_nonpenetrating_path:
            floor_m = max(0.0, floor_m)
        return bool(np.min(clearance) >= floor_m - 1.0e-12)

    def _continuous_clearance_is_valid(
        self, coefficients: np.ndarray, duration_s: float,
        candidate: HumanWaypointCandidate,
    ) -> tuple[bool, float]:
        if not self.require_continuous_nonpenetrating_path:
            return True, float("inf")
        lower = float(self.clearance_evaluator.certified_minimum(coefficients, duration_s))
        return self._path_clearance_is_valid(np.asarray([lower]), candidate), lower

    def _validate_request(
        self,
        current_q: np.ndarray,
        current_dq: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float,
    ) -> None:
        if not math.isfinite(phase_elapsed_s) or phase_elapsed_s < 0.0:
            raise ValueError("phase_elapsed_s must be finite and nonnegative")
        if phase_elapsed_s >= self.spec.phase_timeout_s:
            raise ValueError("no transition time remains in the registered phase")
        if not np.allclose(
            candidate.phase_goal_rad,
            self._expected_goal(candidate.phase),
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise ValueError("waypoint phase goal does not match the registered task")
        task_bounds = np.asarray(self.spec.q_bounds_rad, dtype=float)
        human_bounds = np.column_stack(
            [self.human_model.q_min_rad, self.human_model.q_max_rad]
        )
        for label, q in (("current state", current_q), ("target", candidate.q_waypoint_rad)):
            if np.any(q < task_bounds[:, 0]) or np.any(q > task_bounds[:, 1]):
                raise ValueError(f"{label} lies outside registered task q bounds")
            if np.any(q < human_bounds[:, 0]) or np.any(q > human_bounds[:, 1]):
                raise ValueError(f"{label} lies outside Human-model ROM")
        velocity_limit = np.asarray(self.spec.task_joint_velocity_limit_rad_s)
        if np.any(np.abs(current_dq) > velocity_limit) or np.any(
            np.abs(candidate.dq_waypoint_rad_s) > velocity_limit
        ):
            raise ValueError("boundary velocity exceeds registered task limits")

    def plan(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float = 0.0,
    ) -> QuinticHumanWaypointSchedule:
        return self._plan(
            current_q_hat_rad=current_q_hat_rad,
            current_dq_hat_rad_s=current_dq_hat_rad_s,
            candidate=candidate,
            phase_elapsed_s=phase_elapsed_s,
            use_legacy_nominal_tracking_preview=True,
        )

    def plan_reference_contract(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float = 0.0,
    ) -> QuinticHumanWaypointSchedule:
        """Plan with reference-space feasibility and no PD-motion proxy."""

        return self._plan(
            current_q_hat_rad=current_q_hat_rad,
            current_dq_hat_rad_s=current_dq_hat_rad_s,
            candidate=candidate,
            phase_elapsed_s=phase_elapsed_s,
            use_legacy_nominal_tracking_preview=False,
        )

    def plan_fixed_duration_reference_contract(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        duration_s: float,
        phase_elapsed_s: float = 0.0,
    ) -> QuinticHumanWaypointSchedule:
        """Plan one exact-duration quintic under the unified reference contract.

        This is intentionally separate from :meth:`plan_reference_contract`, which
        selects the shortest feasible registered-grid duration.  Matched-pacing
        studies use this entry point to give every coordination path the same
        terminal deceleration opportunity without changing the production
        waypoint scheduler or its execution gains.
        """

        current_q = _vector("current_q_hat_rad", current_q_hat_rad)
        current_dq = _vector("current_dq_hat_rad_s", current_dq_hat_rad_s)
        self._validate_request(current_q, current_dq, candidate, phase_elapsed_s)
        if candidate.phase is TaskPhase.HOLD:
            raise ValueError("fixed-duration transition is not used for HOLD")
        if not math.isfinite(duration_s) or duration_s <= 0.0:
            raise ValueError("duration_s must be finite and positive")
        step_count = int(round(duration_s / self.reference_period_s))
        if step_count < 1 or not np.isclose(
            step_count * self.reference_period_s,
            duration_s,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise ValueError("duration_s must lie on the registered reference grid")
        if phase_elapsed_s + duration_s > self.spec.phase_timeout_s + 1.0e-12:
            raise ValueError("fixed-duration transition exceeds registered phase timeout")

        coefficients = _quintic_coefficients(
            current_q,
            current_dq,
            candidate.q_waypoint_rad,
            candidate.dq_waypoint_rad_s,
            duration_s,
        )
        maximum_velocity, maximum_acceleration = _polynomial_extrema(
            coefficients, duration_s
        )
        maximum_causal_acceleration = _maximum_causal_reference_acceleration(
            coefficients, duration_s, self.reference_period_s
        )
        velocity_limit = np.asarray(self.spec.task_joint_velocity_limit_rad_s) * self.reference_velocity_fraction
        acceleration_limit = np.asarray(
            self.spec.task_joint_acceleration_limit_rad_s2
        ) * self.reference_acceleration_fraction
        if np.any(maximum_velocity > velocity_limit + 1.0e-12):
            raise ValueError("fixed-duration reference exceeds registered velocity limits")
        if np.any(maximum_causal_acceleration > acceleration_limit + 1.0e-12) or (
                self.reference_acceleration_fraction < 1.0
                and np.any(maximum_acceleration > acceleration_limit + 1.0e-12)):
            raise ValueError(
                "fixed-duration reference exceeds registered causal 20 ms acceleration limits"
            )

        normalized = np.arange(step_count + 1, dtype=float) / step_count
        powers = np.vstack([normalized**index for index in range(6)])
        q_samples = (coefficients @ powers).T
        task_bounds = np.asarray(self.spec.q_bounds_rad, dtype=float)
        human_bounds = np.column_stack(
            [self.human_model.q_min_rad, self.human_model.q_max_rad]
        )
        if np.any(q_samples < task_bounds[:, 0]) or np.any(
            q_samples > task_bounds[:, 1]
        ):
            raise ValueError("fixed-duration reference leaves registered task q bounds")
        if np.any(q_samples < human_bounds[:, 0]) or np.any(
            q_samples > human_bounds[:, 1]
        ):
            raise ValueError("fixed-duration reference leaves Human-model ROM")
        clearance = np.asarray(self._clearance_m(q_samples), dtype=float)
        if not self._path_clearance_is_valid(clearance, candidate):
            raise WaypointGeometryInfeasible(
                "fixed-duration reference violates the registered shank-table "
                f"clearance floor ({1000.0 * float(np.min(clearance)):.6f} mm)"
            )
        continuous_valid, continuous_lower = self._continuous_clearance_is_valid(
            coefficients, float(duration_s), candidate)
        if not continuous_valid:
            raise WaypointGeometryInfeasible(
                "fixed-duration reference violates continuous hard-table "
                f"clearance floor ({1000.0 * continuous_lower:.6f} mm)"
            )
        return QuinticHumanWaypointSchedule(
            candidate=candidate,
            start_q_rad=current_q,
            start_dq_rad_s=current_dq,
            duration_s=float(duration_s),
            coefficients=coefficients,
            maximum_reference_velocity_rad_s=maximum_velocity,
            maximum_reference_acceleration_rad_s2=maximum_acceleration,
            maximum_causal_20ms_reference_acceleration_rad_s2=(
                maximum_causal_acceleration
            ),
            maximum_nominal_tracking_acceleration_rad_s2=np.zeros(2),
            nominal_completion_time_s=float(duration_s),
            minimum_reference_shank_clearance_m=float(
                min(np.min(clearance), continuous_lower)),
            feasibility_semantics=(
                "fixed_duration_causal_20ms_scheduled_reference_motion"
            ),
            reference_period_s=self.reference_period_s,
            continuous_clearance_certificate=getattr(self.clearance_evaluator, "last_certificate", None),
        )

    def _plan(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float,
        use_legacy_nominal_tracking_preview: bool,
    ) -> QuinticHumanWaypointSchedule:
        current_q = _vector("current_q_hat_rad", current_q_hat_rad)
        current_dq = _vector("current_dq_hat_rad_s", current_dq_hat_rad_s)
        self._validate_request(current_q, current_dq, candidate, phase_elapsed_s)

        endpoint_clearance = np.asarray(
            self._clearance_m(np.vstack([current_q, candidate.q_waypoint_rad]))
        )
        if np.any(endpoint_clearance < 0.0):
            label = "current state" if endpoint_clearance[0] < 0.0 else "target waypoint"
            value = float(np.min(endpoint_clearance))
            raise WaypointGeometryInfeasible(
                f"{label} enters existing shank-table geometry ({1000.0 * value:.6f} mm)"
            )

        if candidate.phase is TaskPhase.HOLD and not getattr(self, "continuous_hold_reference", False):
            if not np.allclose(candidate.dq_waypoint_rad_s, 0.0, atol=1.0e-12):
                raise ValueError("HOLD waypoint velocity must be zero")
            angle_tolerance = np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            velocity_tolerance = np.asarray(
                self.spec.joint_velocity_completion_tolerance_rad_s
            )
            if np.any(np.abs(current_q - candidate.q_waypoint_rad) > angle_tolerance) or np.any(
                np.abs(current_dq) > velocity_tolerance
            ):
                raise ValueError("HOLD may start only inside registered completion tolerances")
            coefficients = np.zeros((2, 6))
            coefficients[:, 0] = candidate.q_waypoint_rad
            return QuinticHumanWaypointSchedule(
                candidate=candidate,
                start_q_rad=current_q,
                start_dq_rad_s=current_dq,
                duration_s=self.spec.hold_duration_s,
                coefficients=coefficients,
                maximum_reference_velocity_rad_s=np.zeros(2),
                maximum_reference_acceleration_rad_s2=np.zeros(2),
                maximum_causal_20ms_reference_acceleration_rad_s2=np.zeros(2),
                maximum_nominal_tracking_acceleration_rad_s2=np.zeros(2),
                nominal_completion_time_s=0.0,
                minimum_reference_shank_clearance_m=float(endpoint_clearance.min()),
                feasibility_semantics=(
                    "legacy_reference_plus_pd_tracking_preview"
                    if use_legacy_nominal_tracking_preview
                    else "causal_20ms_scheduled_reference_motion"
                ),
                reference_period_s=self.reference_period_s,
                continuous_clearance_certificate=(getattr(self.clearance_evaluator, "last_certificate", None)
                                                  if candidate.phase is not TaskPhase.HOLD else None),
            )

        velocity_limit = np.asarray(self.spec.task_joint_velocity_limit_rad_s) * self.reference_velocity_fraction
        acceleration_limit = np.asarray(
            self.spec.task_joint_acceleration_limit_rad_s2
        ) * self.reference_acceleration_fraction
        available_s = self.spec.phase_timeout_s - phase_elapsed_s
        # Every duration samples both boundary positions. If either boundary
        # already violates the existing path floor, no duration can succeed.
        # Keep a 1 nm *early-rejection guard* for polynomial endpoint roundoff:
        # cases inside that guard still run all original checks/tolerances.
        # HOLD above intentionally retains its original separate semantics.
        if self.preserve_task_endpoint_clearance_floor and not self._path_clearance_is_valid(
            endpoint_clearance + 1.0e-9, candidate
        ):
            raise ValueError("no quintic schedule satisfies the registered phase and motion limits")
        maximum_steps = int(math.floor(available_s / self.reference_period_s + 1.0e-12))
        first_step = 1
        if self.use_duration_lower_bound:
            # Integral |dq| bounds displacement for every valid schedule. For
            # exact rest-to-rest quintics the peak is exactly 15/8 * |dq_total|/T.
            # Skip only durations mathematically incapable of meeting the
            # unchanged velocity test; keep every subsequent original check.
            delta = np.abs(candidate.q_waypoint_rad - current_q)
            # dq(1/2)=15/8*delta/T - 7/16*(dq0+dq1). Triangle
            # inequality yields a necessary bound even for moving endpoints,
            # including tiny nonzero roundoff in an emitted terminal velocity.
            midpoint_bound = 1.875 * delta / (velocity_limit + 1.0e-12
                + .4375 * np.abs(current_dq + candidate.dq_waypoint_rad_s))
            lower_s = float(np.max(np.maximum(delta/(velocity_limit+1e-12), midpoint_bound)))
            if use_legacy_nominal_tracking_preview or self.reference_acceleration_fraction < 1.0:
                # Necessary acceleration inequalities at the two extrema of
                # rest-to-rest progress. They remain valid for arbitrary
                # endpoint velocities by the triangle inequality:
                # |A*delta_q| <= a_limit*T^2 + |B*v0+C*v1|*T.
                # This only prunes durations that the original instantaneous
                # acceleration check below must reject; it does not replace it.
                for u in ((3.-math.sqrt(3.))/6., (3.+math.sqrt(3.))/6.):
                    aa = 60*u-180*u*u+120*u*u*u
                    bb = -36*u+96*u*u-60*u*u*u
                    cc = -24*u+84*u*u-60*u*u*u
                    distance = abs(aa)*delta
                    velocity_term = np.abs(bb*current_dq+cc*candidate.dq_waypoint_rad_s)
                    denominator = np.sqrt(velocity_term**2+4*(acceleration_limit+1e-12)*distance)+velocity_term
                    necessary = np.divide(2*distance, denominator, out=np.zeros(2), where=denominator>0.)
                    lower_s = max(lower_s, float(np.max(necessary)))
            first_step = max(1, int(math.ceil(lower_s / self.reference_period_s - 1.0e-9)))
        if candidate.phase is TaskPhase.HOLD:
            # The opt-in moving HOLD still spans at least the original dwell.
            # Completion itself remains measured-state based in the task clock.
            first_step = max(first_step, int(math.ceil(self.spec.hold_duration_s / self.reference_period_s)))
        for step_count in range(first_step, maximum_steps + 1):
            duration_s = step_count * self.reference_period_s
            coefficients = _quintic_coefficients(
                current_q,
                current_dq,
                candidate.q_waypoint_rad,
                candidate.dq_waypoint_rad_s,
                duration_s,
            )
            maximum_velocity, maximum_acceleration = _polynomial_extrema(
                coefficients, duration_s
            )
            maximum_causal_acceleration = _maximum_causal_reference_acceleration(
                coefficients, duration_s, self.reference_period_s
            )
            if np.any(maximum_velocity > velocity_limit + 1.0e-12) or np.any(
                maximum_causal_acceleration > acceleration_limit + 1.0e-12
            ) or (
                (use_legacy_nominal_tracking_preview or self.reference_acceleration_fraction < 1.0)
                and np.any(maximum_acceleration > acceleration_limit + 1.0e-12)
            ):
                continue
            samples = []
            for sample_index in range(step_count + 1):
                normalized = sample_index / step_count
                powers = np.asarray([normalized**index for index in range(6)])
                samples.append(coefficients @ powers)
            q_samples = np.asarray(samples)
            task_bounds = np.asarray(self.spec.q_bounds_rad, dtype=float)
            if np.any(q_samples < task_bounds[:, 0]) or np.any(
                q_samples > task_bounds[:, 1]
            ):
                continue
            clearance = np.asarray(self._clearance_m(q_samples), dtype=float)
            if not self._path_clearance_is_valid(clearance, candidate):
                continue
            continuous_valid, continuous_lower = self._continuous_clearance_is_valid(
                coefficients, duration_s, candidate)
            if not continuous_valid:
                continue
            if use_legacy_nominal_tracking_preview:
                nominal = self._nominal_tracking_check(
                    coefficients=coefficients,
                    duration_s=duration_s,
                    current_q=current_q,
                    current_dq=current_dq,
                    candidate=candidate,
                    available_s=available_s,
                )
                if nominal is None:
                    continue
                (
                    nominal_maximum_acceleration,
                    nominal_completion_time,
                    nominal_clearance,
                ) = nominal
                semantics = "legacy_reference_plus_pd_tracking_preview"
            else:
                nominal_maximum_acceleration = np.zeros(2)
                nominal_completion_time = duration_s
                nominal_clearance = float(np.min(clearance))
                semantics = "causal_20ms_scheduled_reference_motion"
            return QuinticHumanWaypointSchedule(
                candidate=candidate,
                start_q_rad=current_q,
                start_dq_rad_s=current_dq,
                duration_s=duration_s,
                coefficients=coefficients,
                maximum_reference_velocity_rad_s=maximum_velocity,
                maximum_reference_acceleration_rad_s2=maximum_acceleration,
                maximum_causal_20ms_reference_acceleration_rad_s2=(
                    maximum_causal_acceleration
                ),
                maximum_nominal_tracking_acceleration_rad_s2=(
                    nominal_maximum_acceleration
                ),
                nominal_completion_time_s=nominal_completion_time,
                minimum_reference_shank_clearance_m=float(
                    min(np.min(clearance), nominal_clearance, continuous_lower)
                ),
                feasibility_semantics=semantics,
                reference_period_s=self.reference_period_s,
                continuous_clearance_certificate=getattr(self.clearance_evaluator, "last_certificate", None),
            )
        raise ValueError("no quintic schedule satisfies the registered phase and motion limits")

    def start_session(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float = 0.0,
    ) -> QuinticHumanWaypointSchedulerSession:
        """Create one finite path with causal execution-semantic progress gating."""

        schedule = self.plan(
            current_q_hat_rad=current_q_hat_rad,
            current_dq_hat_rad_s=current_dq_hat_rad_s,
            candidate=candidate,
            phase_elapsed_s=phase_elapsed_s,
        )
        return QuinticHumanWaypointSchedulerSession(
            scheduler=self,
            schedule=schedule,
            phase_start_elapsed_s=phase_elapsed_s,
        )

    def start_reference_contract_session(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        candidate: HumanWaypointCandidate,
        phase_elapsed_s: float = 0.0,
    ) -> QuinticHumanWaypointSchedulerSession:
        schedule = self.plan_reference_contract(
            current_q_hat_rad=current_q_hat_rad,
            current_dq_hat_rad_s=current_dq_hat_rad_s,
            candidate=candidate,
            phase_elapsed_s=phase_elapsed_s,
        )
        return QuinticHumanWaypointSchedulerSession(
            scheduler=self,
            schedule=schedule,
            phase_start_elapsed_s=phase_elapsed_s,
        )

    def _nominal_tracking_check(
        self,
        *,
        coefficients: np.ndarray,
        duration_s: float,
        current_q: np.ndarray,
        current_dq: np.ndarray,
        candidate: HumanWaypointCandidate,
        available_s: float,
    ) -> tuple[np.ndarray, float, float] | None:
        """Check the unchanged Human PD execution semantics without robot prediction."""

        velocity_limit = np.asarray(self.spec.task_joint_velocity_limit_rad_s)
        acceleration_limit = np.asarray(
            self.spec.task_joint_acceleration_limit_rad_s2
        )
        q_bounds = np.asarray(self.spec.q_bounds_rad, dtype=float)
        angle_tolerance = np.asarray(self.spec.joint_angle_completion_tolerance_rad)
        velocity_tolerance = np.asarray(
            self.spec.joint_velocity_completion_tolerance_rad_s
        )
        q = current_q.copy()
        dq = current_dq.copy()
        maximum_acceleration = np.zeros(2)
        minimum_clearance = float(self._clearance_m(q))
        step_count = int(math.floor(available_s / self.execution_period_s + 1.0e-12))
        for step in range(step_count + 1):
            elapsed_s = step * self.execution_period_s
            reference_time_s = min(
                duration_s,
                math.floor((elapsed_s + 1.0e-12) / self.reference_period_s)
                * self.reference_period_s,
            )
            normalized = reference_time_s / duration_s
            powers = np.asarray([normalized**index for index in range(6)])
            velocity_powers = np.asarray(
                [
                    0.0,
                    1.0,
                    2.0 * normalized,
                    3.0 * normalized**2,
                    4.0 * normalized**3,
                    5.0 * normalized**4,
                ]
            )
            q_reference = coefficients @ powers
            dq_reference = (coefficients @ velocity_powers) / duration_s
            acceleration = self.position_gain * (q_reference - q) + self.velocity_gain * (
                dq_reference - dq
            )
            maximum_acceleration = np.maximum(
                maximum_acceleration, np.abs(acceleration)
            )
            if np.any(np.abs(acceleration) > acceleration_limit + 1.0e-12):
                return None
            if elapsed_s + 1.0e-12 >= duration_s and np.all(
                np.abs(q - candidate.q_waypoint_rad) <= angle_tolerance
            ) and np.all(np.abs(dq - candidate.dq_waypoint_rad_s) <= velocity_tolerance):
                return maximum_acceleration, elapsed_s, minimum_clearance
            if step == step_count:
                break
            q = (
                q
                + self.execution_period_s * dq
                + 0.5 * self.execution_period_s**2 * acceleration
            )
            dq = dq + self.execution_period_s * acceleration
            if np.any(q < q_bounds[:, 0]) or np.any(q > q_bounds[:, 1]):
                return None
            if np.any(np.abs(dq) > velocity_limit + 1.0e-12):
                return None
            clearance = float(self._clearance_m(q))
            minimum_clearance = min(minimum_clearance, clearance)
            if clearance < 0.0:
                return None
        return None


class QuinticHumanWaypointSchedulerSession:
    """Mutable progress state for one deterministic quintic waypoint transition."""

    def __init__(
        self,
        *,
        scheduler: QuinticHumanWaypointSchedulerV1,
        schedule: QuinticHumanWaypointSchedule,
        phase_start_elapsed_s: float,
    ) -> None:
        self.scheduler = scheduler
        self.schedule = schedule
        self.phase_start_elapsed_s = float(phase_start_elapsed_s)
        self.progress_s = 0.0
        self.update_count = 0
        self.regression_count = 0
        self.maximum_reference_motion_acceleration_rad_s2 = np.zeros(2)
        self.reference_motion_history = CausalScheduledReferenceMotionHistory(
            sample_period_s=self.scheduler.reference_period_s,
            window_s=SCHEDULED_REFERENCE_MOTION_WINDOW_S,
        )
        self.diagnostic_events: list[dict[str, Any]] = []

    def advance(
        self,
        *,
        current_q_hat_rad: np.ndarray,
        current_dq_hat_rad_s: np.ndarray,
        phase_elapsed_s: float,
    ) -> ScheduledHumanReferenceSample:
        current_q = _vector("current_q_hat_rad", current_q_hat_rad)
        current_dq = _vector("current_dq_hat_rad_s", current_dq_hat_rad_s)
        if not math.isfinite(phase_elapsed_s) or phase_elapsed_s < 0.0:
            raise ValueError("phase_elapsed_s must be finite and nonnegative")
        if phase_elapsed_s >= self.scheduler.spec.phase_timeout_s:
            raise ValueError("scheduled transition exceeded registered phase timeout")

        previous_progress = self.progress_s
        proposed_progress = min(
            self.schedule.duration_s,
            previous_progress + self.scheduler.reference_period_s,
        )
        grid_count = int(
            math.floor(
                proposed_progress / self.scheduler.execution_period_s + 1.0e-12
            )
        )
        progress_candidates = [
            index * self.scheduler.execution_period_s
            for index in range(grid_count + 1)
        ]
        if not np.isclose(
            progress_candidates[-1], proposed_progress, atol=1.0e-12, rtol=0.0
        ):
            progress_candidates.append(proposed_progress)
        acceleration_limit = np.asarray(
            self.scheduler.spec.task_joint_acceleration_limit_rad_s2
        )
        proposed_sample = self.schedule.sample(proposed_progress)
        current_progress_sample = self.schedule.sample(previous_progress)
        history_status = self.reference_motion_history.status(phase_elapsed_s)
        history_valid = history_status.valid
        selected_progress: float | None = None
        selected_sample: ScheduledHumanReferenceSample | None = None
        selected_acceleration: np.ndarray | None = None
        rejected_candidate_count = 0
        proposed_acceleration: np.ndarray | None = None
        current_progress_acceleration: np.ndarray | None = None
        history_q: np.ndarray | None = None
        history_dq: np.ndarray | None = None
        if history_valid:
            assert history_status.anchor_q_rad is not None
            assert history_status.anchor_dq_rad_s is not None
            history_q = history_status.anchor_q_rad
            history_dq = history_status.anchor_dq_rad_s
            proposed_acceleration = self.reference_motion_history.acceleration_rad_s2(
                proposed_sample.dq_rad_s, history_status
            )
            current_progress_acceleration = (
                self.reference_motion_history.acceleration_rad_s2(
                    current_progress_sample.dq_rad_s, history_status
                )
            )
            for progress_s in reversed(progress_candidates):
                sample = self.schedule.sample(progress_s)
                acceleration = self.reference_motion_history.acceleration_rad_s2(
                    sample.dq_rad_s, history_status
                )
                if np.all(np.abs(acceleration) <= acceleration_limit + 1.0e-12):
                    selected_progress = progress_s
                    selected_sample = sample
                    selected_acceleration = acceleration
                    break
                rejected_candidate_count += 1
        else:
            selected_progress = previous_progress
            selected_sample = current_progress_sample
        if selected_sample is None or selected_progress is None or selected_acceleration is None:
            if history_valid:
                raise ValueError(
                    "no point on the scheduled path satisfies the causal 20 ms "
                    "reference-motion acceleration limits"
                )
        rollback = selected_progress + 1.0e-12 < previous_progress
        blocked = selected_progress + 1.0e-12 < proposed_progress
        if rollback:
            self.regression_count += 1
        self.progress_s = selected_progress
        self.update_count += 1
        if selected_acceleration is not None:
            self.maximum_reference_motion_acceleration_rad_s2 = np.maximum(
                self.maximum_reference_motion_acceleration_rad_s2,
                np.abs(selected_acceleration),
            )
        self.reference_motion_history.commit(
            phase_elapsed_s,
            selected_sample.q_rad,
            selected_sample.dq_rad_s,
        )
        self.diagnostic_events.append(
            {
                "event_index": self.update_count - 1,
                "phase_elapsed_s": float(phase_elapsed_s),
                "current_q_hat_rad": current_q.copy(),
                "current_dq_hat_rad_s": current_dq.copy(),
                "previous_progress_s": float(previous_progress),
                "nominal_next_progress_s": float(proposed_progress),
                "accepted_progress_s": float(selected_progress),
                "blocked": bool(blocked),
                "rollback": bool(rollback),
                "held": bool(
                    blocked
                    and np.isclose(
                        selected_progress,
                        previous_progress,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "criterion": "causal_20ms_scheduled_reference_motion",
                "reference_history_valid": history_valid,
                "reference_history_coverage_s": history_status.coverage_s,
                "reference_history_window_s": SCHEDULED_REFERENCE_MOTION_WINDOW_S,
                "reference_history_sample_count": history_status.sample_count,
                "reference_history_max_gap_s": history_status.maximum_gap_s,
                "reference_history_contiguous": history_status.contiguous,
                "reference_history_q_rad": (
                    None if history_q is None else history_q.copy()
                ),
                "reference_history_dq_rad_s": (
                    None if history_dq is None else history_dq.copy()
                ),
                "acceleration_limit_rad_s2": acceleration_limit.copy(),
                "proposed_q_reference_rad": proposed_sample.q_rad.copy(),
                "proposed_dq_reference_rad_s": proposed_sample.dq_rad_s.copy(),
                "proposed_reference_motion_acceleration_rad_s2": (
                    None
                    if proposed_acceleration is None
                    else proposed_acceleration.copy()
                ),
                "proposed_violating_joints": (
                    []
                    if proposed_acceleration is None
                    else np.flatnonzero(
                        np.abs(proposed_acceleration)
                        > acceleration_limit + 1.0e-12
                    ).tolist()
                ),
                "current_progress_q_reference_rad": (
                    current_progress_sample.q_rad.copy()
                ),
                "current_progress_dq_reference_rad_s": (
                    current_progress_sample.dq_rad_s.copy()
                ),
                "current_progress_reference_motion_acceleration_rad_s2": (
                    None
                    if current_progress_acceleration is None
                    else current_progress_acceleration.copy()
                ),
                "current_progress_feasible": (
                    None
                    if current_progress_acceleration is None
                    else bool(
                        np.all(
                            np.abs(current_progress_acceleration)
                            <= acceleration_limit + 1.0e-12
                        )
                    )
                ),
                "accepted_q_reference_rad": selected_sample.q_rad.copy(),
                "accepted_dq_reference_rad_s": selected_sample.dq_rad_s.copy(),
                "accepted_reference_motion_acceleration_rad_s2": (
                    None
                    if selected_acceleration is None
                    else selected_acceleration.copy()
                ),
                "rejected_candidate_count": int(rejected_candidate_count),
            }
        )
        return selected_sample

    def record(self) -> dict[str, Any]:
        return {
            "schedule": self.schedule.record(),
            "progress_s": self.progress_s,
            "progress_fraction": self.progress_s / self.schedule.duration_s,
            "update_count": self.update_count,
            "regression_count": self.regression_count,
            "blocked_progress_count": int(
                sum(bool(event["blocked"]) for event in self.diagnostic_events)
            ),
            "history_invalid_hold_count": int(
                sum(
                    not bool(event["reference_history_valid"])
                    for event in self.diagnostic_events
                )
            ),
            "maximum_reference_motion_acceleration_rad_s2": (
                self.maximum_reference_motion_acceleration_rad_s2.tolist()
            ),
        }


__all__ = [
    "HUMAN_WAYPOINT_SCHEDULER_VERSION",
    "SCHEDULER_REFERENCE_PERIOD_S",
    "SCHEDULED_REFERENCE_MOTION_WINDOW_S",
    "QuinticHumanWaypointSchedule",
    "QuinticHumanWaypointSchedulerV1",
    "QuinticHumanWaypointSchedulerSession",
    "ScheduledHumanReferenceSample",
    "WaypointGeometryInfeasible",
    "shank_table_clearance_m",
]
