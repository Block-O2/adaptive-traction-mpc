"""Offline constraint-aware time parameterization for Stage-4 High-ROM paths.

The planner time-warps an existing geometric reference.  It does not alter the
MPC, CEM, estimator, allocator, or the independent 200 N execution gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference, HIP_HEIGHT_M, _world_from_cuff

from .cuff_allocator import default_engineering_cuff_allocator
from .estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from .high_rom_dynamic_pilot import PILOT_DURATION_S, HighROMPilotTrajectory
from .high_rom_human_v2 import HIGH_ROM_HUMAN_V2


@dataclass(frozen=True)
class PathTimingConfig:
    """Common, evidence-derived planning settings for both pilot paths."""

    phase_step_s: float = 0.02
    maximum_phase_rate: float = 1.0
    maximum_slowdown_rate_per_s: float = 1.0
    maximum_speedup_rate_per_s: float = 0.25
    force_gate_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N
    prediction_reserve_n: float = 70.0

    @property
    def planning_force_budget_n(self) -> float:
        return self.force_gate_n - self.prediction_reserve_n

    def as_dict(self) -> dict[str, float]:
        payload = asdict(self)
        payload["planning_force_budget_n"] = self.planning_force_budget_n
        return payload


def evidence_derived_common_reserve(
    corrected_same_action_prediction_errors_n: list[float],
) -> float:
    """Round the worst preserved same-action error upward to a whole newton."""

    values = np.asarray(corrected_same_action_prediction_errors_n, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("prediction-error evidence must be a finite nonempty vector")
    if np.any(values < 0.0):
        raise ValueError("absolute prediction errors must be nonnegative")
    return float(math.ceil(float(np.max(values)) - 1e-12))


def nominal_high_rom_population_prior_model() -> BaseParameterHumanModel:
    """Return the Fixed-MPC population prior in the nominal sagittal frame."""

    human = HIGH_ROM_HUMAN_V2
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=human.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([human.sleeve_center_m, 0.0]),
    )
    return BaseParameterHumanModel(
        geometry=geometry,
        beta=nominal_base_parameters(human),
        rom_human=human,
    )


def _force_for_phase_dynamics(
    trajectory: HighROMPilotTrajectory,
    phase_s: float,
    phase_rate_squared: float,
    phase_rate_squared_derivative: float,
    model: Any,
    allocator: Any,
) -> tuple[float, float]:
    """Return force/moment for x=s_dot^2 and u=dx/ds.

    q_dot = q_s sqrt(x), q_ddot = q_ss x + 0.5 q_s u.
    """

    q, q_s, q_ss = trajectory.batched_path_kinematics(
        np.asarray([phase_s], dtype=float)
    )
    x = max(float(phase_rate_squared), 0.0)
    u = float(phase_rate_squared_derivative)
    dq = q_s[0] * math.sqrt(x)
    ddq = q_ss[0] * x + 0.5 * q_s[0] * u
    action = model.inverse_dynamics(q[0], dq, ddq)
    allocation = allocator.allocate(action, q[0], model)
    return (
        float(allocation["force_norm_n"]),
        float(abs(allocation["sagittal_wrench"][2])),
    )


class ConstraintAwarePathTiming:
    """One-time forward/backward phase-rate envelope with force hard rejection."""

    def __init__(
        self,
        trajectory: HighROMPilotTrajectory,
        model: Any,
        *,
        allocator: Any | None = None,
        config: PathTimingConfig = PathTimingConfig(),
    ) -> None:
        self.trajectory = trajectory
        self.model = model
        self.allocator = (
            default_engineering_cuff_allocator() if allocator is None else allocator
        )
        self.config = config
        self._plan()

    def _force_interval(self, phase_s: float, x: float) -> tuple[float, float]:
        """Admissible u=dx/ds interval from force and common rate bounds."""

        q, q_s, q_ss = self.trajectory.batched_path_kinematics(
            np.asarray([phase_s], dtype=float)
        )
        dq = q_s[0] * math.sqrt(max(x, 0.0))
        base_ddq = q_ss[0] * x
        base_action = self.model.inverse_dynamics(q[0], dq, base_ddq)
        unit_action = self.model.inverse_dynamics(
            q[0], dq, base_ddq + 0.5 * q_s[0]
        )
        base_force = np.asarray(
            self.allocator.allocate(base_action, q[0], self.model)["force_world_n"],
            dtype=float,
        )
        unit_force = np.asarray(
            self.allocator.allocate(unit_action, q[0], self.model)["force_world_n"],
            dtype=float,
        )
        slope = unit_force - base_force
        budget = self.config.planning_force_budget_n
        quadratic = float(slope @ slope)
        linear = float(2.0 * base_force @ slope)
        constant = float(base_force @ base_force - budget**2)
        if quadratic <= 1e-18:
            if constant > 1e-10:
                return math.inf, -math.inf
            force_lower, force_upper = -math.inf, math.inf
        else:
            discriminant = linear**2 - 4.0 * quadratic * constant
            if discriminant < -1e-9:
                return math.inf, -math.inf
            root = math.sqrt(max(discriminant, 0.0))
            force_lower = (-linear - root) / (2.0 * quadratic)
            force_upper = (-linear + root) / (2.0 * quadratic)
        # Since x=s_dot^2, s_ddot=0.5 dx/ds.  These are the unchanged
        # Stage-4 governor slowdown/recovery rate limits, reused only to keep
        # the offline clock smooth and common across paths.
        rate_lower = -2.0 * self.config.maximum_slowdown_rate_per_s
        rate_upper = 2.0 * self.config.maximum_speedup_rate_per_s
        return max(force_lower, rate_lower), min(force_upper, rate_upper)

    def _pointwise_speed_cap(self, phase_s: float) -> float:
        maximum = self.config.maximum_phase_rate**2
        maximum_interval = self._force_interval(phase_s, maximum)
        if maximum_interval[0] <= maximum_interval[1]:
            return maximum
        candidates = np.linspace(0.0, maximum, 101)
        feasible = []
        for value in candidates:
            interval = self._force_interval(phase_s, float(value))
            if interval[0] <= interval[1]:
                feasible.append(float(value))
        if not feasible:
            raise RuntimeError(
                f"no force-feasible path speed at phase {phase_s:.6f} s"
            )
        lower = float(max(feasible))
        if lower >= maximum - 1e-12:
            return maximum
        upper = min(lower + maximum / 100.0, maximum)
        for _ in range(20):
            middle = 0.5 * (lower + upper)
            interval = self._force_interval(phase_s, middle)
            if interval[0] <= interval[1]:
                lower = middle
            else:
                upper = middle
        return lower

    def _plan(self) -> None:
        started = perf_counter()
        count = int(round(PILOT_DURATION_S / self.config.phase_step_s)) + 1
        phase = np.linspace(0.0, PILOT_DURATION_S, count)
        ds = float(phase[1] - phase[0])
        q, _, _ = self.trajectory.batched_path_kinematics(phase)
        q_min = np.asarray(self.model.q_min_rad)
        q_max = np.asarray(self.model.q_max_rad)
        if np.any(q < q_min - 1e-12) or np.any(q > q_max + 1e-12):
            raise RuntimeError("geometric path leaves the current Human V2 ROM")

        maximum_x = self.config.maximum_phase_rate**2
        nominal_intervals = [self._force_interval(s, maximum_x) for s in phase]
        self.nominal_clock_is_optimal = all(
            lower <= 0.0 <= upper for lower, upper in nominal_intervals
        )
        if self.nominal_clock_is_optimal:
            # The lexicographic optimum is exactly the original clock: it is
            # feasible and no admissible profile can progress faster than one.
            x = np.full_like(phase, maximum_x)
        else:
            # A small directed acyclic speed grid is the discrete equivalent of
            # a forward/backward reachability envelope.  Edges are hard-rejected
            # by the force and phase-acceleration intervals; elapsed time is the
            # only primary objective.
            levels = np.linspace(0.0, maximum_x, 401)
            roots = np.sqrt(levels)
            costs = np.full(len(levels), math.inf)
            costs[-1] = 0.0
            predecessors = np.full((len(phase), len(levels)), -1, dtype=np.int16)
            tolerance = 1e-10
            for index in range(len(phase) - 1):
                next_costs = np.full(len(levels), math.inf)
                finite = np.flatnonzero(np.isfinite(costs))
                for source in finite:
                    xi = float(levels[source])
                    lower, upper = self._force_interval(phase[index], xi)
                    if lower > upper:
                        continue
                    minimum_next = max(0.0, xi + lower * ds)
                    maximum_next = min(maximum_x, xi + upper * ds)
                    first = int(np.searchsorted(levels, minimum_next - tolerance))
                    stop = int(np.searchsorted(levels, maximum_next + tolerance, side="right"))
                    for destination in range(first, stop):
                        denominator = roots[source] + roots[destination]
                        if denominator <= 1e-12:
                            continue
                        elapsed = 2.0 * ds / denominator
                        candidate_cost = costs[source] + elapsed
                        if candidate_cost < next_costs[destination] - 1e-12:
                            next_costs[destination] = candidate_cost
                            predecessors[index + 1, destination] = source
                costs = next_costs
                if not np.any(np.isfinite(costs)):
                    raise RuntimeError(
                        f"no forward/backward feasible speed envelope at phase "
                        f"{phase[index + 1]:.6f} s"
                    )
            terminal = int(np.argmin(costs))
            if not np.isfinite(costs[terminal]):
                raise RuntimeError("no complete force-feasible path timing exists")
            indices = np.empty(len(phase), dtype=int)
            indices[-1] = terminal
            for index in range(len(phase) - 1, 0, -1):
                indices[index - 1] = predecessors[index, indices[index]]
                if indices[index - 1] < 0:
                    raise RuntimeError("path timing predecessor chain is incomplete")
            x = levels[indices]
        x = np.clip(x, 1e-8, maximum_x)
        alpha = np.sqrt(x)
        wall = np.zeros_like(phase)
        wall[1:] = np.cumsum(2.0 * ds / (alpha[:-1] + alpha[1:]))
        u = np.empty_like(x)
        u[:-1] = np.diff(x) / ds
        u[-1] = u[-2]

        force = np.empty_like(phase)
        moment = np.empty_like(phase)
        for index, (s, xi, ui) in enumerate(zip(phase, x, u, strict=True)):
            force[index], moment[index] = _force_for_phase_dynamics(
                self.trajectory, s, xi, ui, self.model, self.allocator
            )
        if float(np.max(force)) > self.config.planning_force_budget_n + 1e-6:
            raise RuntimeError("final path timing violates its planning force budget")

        self.phase_grid_s = phase
        self.wall_grid_s = wall
        self.phase_rate_squared = x
        self.phase_rate = alpha
        self.phase_acceleration = 0.5 * u
        self.predicted_force_n = force
        self.predicted_moment_nm = moment
        self.planning_latency_s = perf_counter() - started

    @property
    def duration_s(self) -> float:
        return float(self.wall_grid_s[-1])

    def _state(self, wall_time_s: float) -> tuple[float, float, float]:
        time = float(np.clip(wall_time_s, 0.0, self.duration_s))
        if self.nominal_clock_is_optimal:
            # Preserve the frozen reference bit-for-bit.  Even roundoff-scale
            # interpolation changes can alter discrete CEM elite ordering.
            return time, 1.0, 0.0
        phase = float(np.interp(time, self.wall_grid_s, self.phase_grid_s))
        x = float(np.interp(phase, self.phase_grid_s, self.phase_rate_squared))
        u = float(np.interp(phase, self.phase_grid_s, 2.0 * self.phase_acceleration))
        return phase, math.sqrt(max(x, 0.0)), 0.5 * u

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        if self.nominal_clock_is_optimal:
            return self.trajectory.reference(wall_time_s)
        phase, phase_rate, phase_acceleration = self._state(wall_time_s)
        base = self.trajectory.reference(phase)
        dq = base.dq_rad_s * phase_rate
        ddq = (
            base.ddq_rad_s2 * phase_rate**2
            + base.dq_rad_s * phase_acceleration
        )
        return CuffPoseReference(base.q_rad, dq, ddq, _world_from_cuff(base.q_rad))

    def status(self, wall_time_s: float) -> dict[str, float]:
        phase, alpha, acceleration = self._state(wall_time_s)
        predicted = float(
            np.interp(phase, self.phase_grid_s, self.predicted_force_n)
        )
        return {
            "reference_phase_time_s": phase,
            "speed_scale": alpha,
            "speed_scale_rate_per_s": acceleration,
            "force_speed_scale": alpha,
            "force_speed_target_scale": alpha,
            "governor_predicted_peak_command_force_n": predicted,
            "geometry_confidence": 0.0,
            "dynamic_confidence": 0.0,
            "combined_confidence": 0.0,
            "geometry_model_confidence": 0.0,
            "dynamic_model_confidence": 0.0,
            "combined_model_confidence_raw": 0.0,
            "filtered_model_confidence": 0.0,
            "execution_confidence_high": 0.0,
            "geometry_information_confidence": 0.0,
            "dynamic_information_confidence": 0.0,
            "combined_information_confidence": 0.0,
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        phase, alpha, acceleration = self._state(wall_time_s)
        return {
            "mode": "offline_constraint_aware_path_time_parameterization",
            "config": self.config.as_dict(),
            "planning_latency_ms": 1000.0 * self.planning_latency_s,
            "planned_duration_s": self.duration_s,
            "nominal_duration_s": PILOT_DURATION_S,
            "final_status": {
                "wall_time_s": float(wall_time_s),
                "reference_phase_time_s": phase,
                "speed_scale": alpha,
                "speed_scale_rate_per_s": acceleration,
            },
            "planned_alpha_mean": float(
                np.trapz(self.phase_rate, self.wall_grid_s) / self.duration_s
            ),
            "planned_alpha_minimum": float(np.min(self.phase_rate)),
            "planned_alpha_maximum": float(np.max(self.phase_rate)),
            "planned_time_below_nominal_s": float(
                np.trapz(
                    (self.phase_rate < 1.0 - 1e-9).astype(float),
                    self.wall_grid_s,
                )
            ),
            "predicted_force_peak_n": float(np.max(self.predicted_force_n)),
            "predicted_moment_peak_nm": float(np.max(self.predicted_moment_nm)),
            "hard_constraints": {
                "force_budget_respected": bool(
                    np.max(self.predicted_force_n)
                    <= self.config.planning_force_budget_n + 1e-6
                ),
                "rom_respected": True,
                "robot_path_pre_audit_reused": True,
            },
            "chain_rule": (
                "qdot=q_s*sdot; qddot=q_ss*sdot^2+q_s*sddot"
            ),
            "online_replanning": False,
            "mpc_modified": False,
            "identity_clock_bypass_active": self.nominal_clock_is_optimal,
        }
