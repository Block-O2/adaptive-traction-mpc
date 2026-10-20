"""Stage-5-only goal-directed adapter around the retained Human-space CEM MPC."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
)
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff
from traction_mpc_stage4.human_model import inverse_dynamics, step_dynamics
from traction_mpc_stage4.mpc import (
    FirstActionBatchPreview,
    FirstActionPreview,
    HumanMPCConfig,
    HumanSpaceMPC,
)

from .loaded_execution import future_loaded_command_wrench_batch
from .task import GoalTaskSpec, GoalTaskState, TaskPhase
from .task_observation import ControllerTaskObservation


@dataclass(frozen=True)
class GoalMPCObjective:
    """Minimal untuned goal objective layered on inherited MPC scales/weights."""

    stage_target_distance_weight: float = 1.0
    terminal_target_error_weight: float = 1.0
    terminal_velocity_error_weight: float = 1.0
    hold_set_violation_weight: float = 1.0
    hold_inside_regulation_weight: float = 0.05
    hold_physical_force_weight: float = 0.01
    learned_terminal_value: float = 0.0

    def __post_init__(self) -> None:
        weights = (
            self.stage_target_distance_weight,
            self.terminal_target_error_weight,
            self.terminal_velocity_error_weight,
            self.hold_set_violation_weight,
            self.hold_inside_regulation_weight,
            self.hold_physical_force_weight,
        )
        if any(not np.isfinite(value) or value < 0.0 for value in weights):
            raise ValueError("goal objective weights must be finite and nonnegative")
        if self.learned_terminal_value != 0.0:
            raise ValueError("the first Goal-MPC version requires V_terminal = 0")


@dataclass(frozen=True)
class GoalMPCSeedPacing:
    """Independent-joint seed pace copied from the legacy low/moderate fixture."""

    maximum_velocity_rad_s: tuple[float, float] = tuple(
        np.radians([9.75, 17.25])
    )
    maximum_acceleration_rad_s2: tuple[float, float] = tuple(
        np.radians([12.0089, 21.2465])
    )

    def __post_init__(self) -> None:
        for name, values in (
            ("maximum velocity", self.maximum_velocity_rad_s),
            ("maximum acceleration", self.maximum_acceleration_rad_s2),
        ):
            if len(values) != 2 or not all(
                np.isfinite(value) and value > 0.0 for value in values
            ):
                raise ValueError(f"seed {name} must contain two finite positive values")


@dataclass(frozen=True)
class SupportCenteredMotionConfig:
    """Provisional CEM scale for increments about inverse-dynamics support.

    The registered task acceleration envelope is the hard authority.  These
    values only set the sampling scale and are deliberately much smaller than
    the inherited absolute-action exploration of (10, 5) Nm.
    """

    exploration_std_nm: tuple[float, float] = (1.50, 1.00)
    exploration_std_floor_nm: tuple[float, float] = (0.30, 0.20)

    def __post_init__(self) -> None:
        for name, values in (
            ("motion exploration standard deviation", self.exploration_std_nm),
            ("motion exploration floor", self.exploration_std_floor_nm),
        ):
            array = np.asarray(values, dtype=float)
            if array.shape != (2,) or np.any(array <= 0.0) or not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must be a finite positive two-vector")
        if np.any(
            np.asarray(self.exploration_std_floor_nm)
            > np.asarray(self.exploration_std_nm)
        ):
            raise ValueError("motion exploration floor cannot exceed its initial scale")


def support_action(
    estimated_state: np.ndarray,
    human_model: Any,
) -> np.ndarray:
    """Instantaneous control-effective support from deployable q/dq only."""

    state = np.asarray(estimated_state, dtype=float)
    if state.shape != (4,) or not np.all(np.isfinite(state)):
        raise ValueError("support_action requires one finite Human state[4]")
    return _model_inverse_dynamics(
        state[:2], state[2:], np.zeros(2), human_model
    )


class _SupportCenteredScalarPreview:
    """Translate one CEM motion increment into the total executable action."""

    def __init__(self, preview: FirstActionPreview, support_nm: np.ndarray) -> None:
        self.preview = preview
        self.support_nm = np.asarray(support_nm, dtype=float).copy()

    def __call__(self, increment_nm: np.ndarray):
        return self.preview(self.support_nm + np.asarray(increment_nm, dtype=float))


class _SupportCenteredBatchPreview:
    """Keep Stage-5 screening total-action based while CEM samples increments."""

    def __init__(
        self,
        preview: FirstActionBatchPreview,
        support_nm: np.ndarray,
        support_provider: Any,
    ) -> None:
        self.preview = preview
        self.support_nm = np.asarray(support_nm, dtype=float).copy()
        self.support_provider = support_provider
        configure_prefix = getattr(preview, "configure_prefix_screening", None)
        if configure_prefix is not None:
            owner = getattr(support_provider, "__self__", None)
            continuous_dynamics = getattr(
                owner, "_batched_base_continuous_dynamics", None
            )
            if continuous_dynamics is None:
                raise AttributeError("Goal-MPC has no batched Human dynamics")
            configure_prefix(
                support_provider=support_provider,
                human_continuous_dynamics=continuous_dynamics,
                future_command_resolver=self._future_command_wrench,
            )

    def __call__(self, increments_nm: np.ndarray):
        increments = np.asarray(increments_nm, dtype=float)
        return self.preview(increments + self.support_nm)

    def effective_generalized_action_nm(self, increments_nm: np.ndarray) -> np.ndarray:
        total = np.asarray(increments_nm, dtype=float) + self.support_nm
        mapper = getattr(self.preview, "effective_generalized_action_nm", None)
        return total if mapper is None else np.asarray(mapper(total), dtype=float)

    def rollout_horizon(
        self,
        initial_human_state: np.ndarray,
        increment_sequences_nm: np.ndarray,
        batched_human_step: Any,
    ):
        rollout = getattr(self.preview, "rollout_horizon", None)
        if rollout is None:
            raise AttributeError("wrapped preview has no full-horizon rollout")
        return rollout(
            initial_human_state,
            increment_sequences_nm,
            batched_human_step,
            action_resolver=self.support_provider,
            future_command_resolver=self._future_command_wrench,
            initial_support_nm=self.support_nm,
        )

    def _future_command_wrench(
        self,
        states: np.ndarray,
        total_actions_nm: np.ndarray,
        requested_human_wrenches_world: np.ndarray,
        *,
        interface_displacement_human_m: np.ndarray,
        interface_velocity_human_m_s: np.ndarray,
        interface_rotation_human_rad: np.ndarray,
        interface_angular_velocity_human_rad_s: np.ndarray,
        human_rotation_world: np.ndarray,
        support_human_wrenches_world: np.ndarray | None = None,
    ) -> np.ndarray:
        """Use the unified loaded execution law for future horizon steps."""

        owner = getattr(getattr(self.preview, "rollout_horizon", None), "__self__", None)
        if owner is None:
            raise AttributeError("wrapped preview has no interface rollout owner")
        del total_actions_nm
        state = np.asarray(states, dtype=float)
        requested = np.asarray(requested_human_wrenches_world, dtype=float)
        if support_human_wrenches_world is None:
            support = np.asarray(self.support_provider(state), dtype=float)
            jacobian, _ = owner._geometry_batch(
                state[:, :2], owner.human_model.geometry
            )
            support_wrench = owner._allocate_with_jacobian_batch(support, jacobian)
        else:
            support_wrench = np.asarray(
                support_human_wrenches_world, dtype=float
            )
        return future_loaded_command_wrench_batch(
            states=state,
            total_human_cuff_wrenches_world=requested,
            support_human_cuff_wrenches_world=support_wrench,
            interface_displacement_human_m=interface_displacement_human_m,
            interface_velocity_human_m_s=interface_velocity_human_m_s,
            interface_rotation_human_rad=interface_rotation_human_rad,
            interface_angular_velocity_human_rad_s=(
                interface_angular_velocity_human_rad_s
            ),
            human_rotation_world=human_rotation_world,
            interface=owner.predictor.parameters,
        )

    def _allocate_varying_q_batch(
        self, total_actions_nm: np.ndarray, q_rad: np.ndarray
    ) -> np.ndarray:
        owner = getattr(getattr(self.preview, "rollout_horizon", None), "__self__", None)
        allocator = getattr(owner, "_allocate_varying_q_batch", None)
        if allocator is None:
            raise AttributeError("wrapped preview has no batched varying-q allocator")
        return np.asarray(allocator(total_actions_nm, q_rad), dtype=float)


class _AnchoredMotionIncrementRNG:
    """Inject the three required deterministic CEM initialization anchors."""

    def __init__(
        self,
        rng: np.random.Generator,
        continuation_sequence_nm: np.ndarray,
    ) -> None:
        self.rng = rng
        self.continuation_sequence_nm = np.asarray(
            continuation_sequence_nm, dtype=float
        ).copy()

    def normal(self, loc: Any, scale: Any, size: Any = None) -> np.ndarray:
        samples = np.asarray(self.rng.normal(loc, scale, size=size), dtype=float)
        # The parent solver overwrites candidate 0 with its independently paced
        # motion seed after sampling.  Reserve candidates 1 and 2 here.
        if samples.ndim == 3 and samples.shape[0] >= 3:
            samples[1] = 0.0  # exact support-only / zero-motion candidate
            samples[2] = self.continuation_sequence_nm
        return samples


@dataclass(frozen=True)
class GoalCandidateEvaluation:
    """Audit result for one manually supplied goal-MPC candidate sequence."""

    total_cost: float
    minimum_constraint_margin: float
    predicted_states: np.ndarray | None
    cost_terms: dict[str, float]

    @property
    def feasible(self) -> bool:
        return bool(
            self.predicted_states is not None
            and self.minimum_constraint_margin >= -1.0e-9
        )


def phase_target(spec: GoalTaskSpec, task_state: GoalTaskState) -> np.ndarray:
    """Return the active state target without constructing a time trajectory."""

    if task_state.phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD):
        return np.asarray(spec.outbound_goal_target_rad, dtype=float)
    if task_state.phase is TaskPhase.RETURN:
        return np.asarray(spec.start_return_target_rad, dtype=float)
    raise ValueError("terminal task phases do not have an MPC target")


def _model_step(
    state: np.ndarray,
    action_nm: np.ndarray,
    dt_s: float,
    human_model: Any,
) -> np.ndarray:
    if hasattr(human_model, "step_dynamics"):
        return np.asarray(
            human_model.step_dynamics(state, action_nm, dt_s), dtype=float
        )
    return np.asarray(step_dynamics(state, action_nm, dt_s, human_model), dtype=float)


def _model_inverse_dynamics(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    ddq_rad_s2: np.ndarray,
    human_model: Any,
) -> np.ndarray:
    if hasattr(human_model, "inverse_dynamics"):
        return np.asarray(
            human_model.inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2), dtype=float
        )
    return np.asarray(
        inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2, human_model), dtype=float
    )


def local_command_reference(
    estimated_state: np.ndarray,
    action_nm: np.ndarray,
    human_model: Any,
    *,
    control_dt_s: float = EXECUTION_CONTROL_DT_S,
) -> CuffPoseReference:
    """Anchor low-level pose/twist while the selected cuff wrench drives motion.

    The Human-only predictor does not contain Plant-v1 cuff deformation. Using
    its next Human state as a simultaneous robot pose target would create a
    second motion authority and pull the compliant cuff ahead of the shank.
    """

    state = np.asarray(estimated_state, dtype=float)
    action = np.asarray(action_nm, dtype=float)
    if state.shape != (4,) or action.shape != (2,):
        raise ValueError("local command reference requires state[4] and action[2]")
    if not np.all(np.isfinite(state)) or not np.all(np.isfinite(action)):
        raise ValueError("local command reference inputs must be finite")
    if not np.isfinite(control_dt_s) or control_dt_s <= 0.0:
        raise ValueError("control_dt_s must be finite and positive")
    pose = (
        human_model.geometry.cuff_pose(state[:2])
        if hasattr(human_model, "geometry")
        else _world_from_cuff(state[:2])
    )
    return CuffPoseReference(
        q_rad=state[:2].copy(),
        dq_rad_s=state[2:].copy(),
        ddq_rad_s2=np.zeros(2),
        world_from_cuff=pose,
    )


class GoalDirectedHumanSpaceMPC(HumanSpaceMPC):
    """CEM MPC with state-goal cost and no episode-long q reference."""

    def __init__(
        self,
        config: HumanMPCConfig = HumanMPCConfig(),
        *,
        objective: GoalMPCObjective = GoalMPCObjective(),
        seed_pacing: GoalMPCSeedPacing = GoalMPCSeedPacing(),
        motion_config: SupportCenteredMotionConfig = SupportCenteredMotionConfig(),
        cuff_allocator: Any | None = None,
        implementation: str = "batched",
        record_timing_breakdown: bool = True,
        planning_physical_force_ceiling_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N,
        planning_joint_velocity_ceiling_rad_s: tuple[float, float] | None = None,
    ) -> None:
        super().__init__(
            config,
            cuff_allocator=cuff_allocator,
            candidate_audit_solve_indices=frozenset(),
            implementation=implementation,
            record_timing_breakdown=record_timing_breakdown,
        )
        self.goal_objective = objective
        self.seed_pacing = seed_pacing
        self.motion_config = motion_config
        self.planning_physical_force_ceiling_n = float(
            planning_physical_force_ceiling_n
        )
        if (
            not np.isfinite(self.planning_physical_force_ceiling_n)
            or self.planning_physical_force_ceiling_n <= 0.0
            or self.planning_physical_force_ceiling_n
            > CUFF_TRANSLATIONAL_FORCE_GATE_N
        ):
            raise ValueError(
                "planning physical-force ceiling must be positive and no greater "
                "than the unchanged engineering gate"
            )
        if planning_joint_velocity_ceiling_rad_s is None:
            self.planning_joint_velocity_ceiling_rad_s = None
        else:
            pacing = np.asarray(planning_joint_velocity_ceiling_rad_s, dtype=float)
            if pacing.shape != (2,) or np.any(pacing <= 0.0) or not np.all(
                np.isfinite(pacing)
            ):
                raise ValueError("planning velocity ceiling must be a positive pair")
            self.planning_joint_velocity_ceiling_rad_s = tuple(
                float(value) for value in pacing
            )
        self._active_spec: GoalTaskSpec | None = None
        self._active_task_state: GoalTaskState | None = None
        self._active_target_rad: np.ndarray | None = None
        self._last_phase: TaskPhase | None = None
        self.last_predicted_states: np.ndarray | None = None
        self._first_action_effective_map: Any | None = None
        self._full_horizon_interface_rollout: Any | None = None
        self._population_constraint_audit: list[dict[str, Any]] = []
        self._active_human_model: Any | None = None
        self._current_support_nm = np.zeros(2)
        self.last_total_action_nm = np.zeros(2)
        self.last_motion_increment_nm = np.zeros(2)
        # Diagnostic-only record of the feasible population member with the
        # largest hard-constraint margin.  It does not participate in control
        # unless an explicitly enabled retention policy is added later.
        self.last_safest_feasible_sequence: np.ndarray | None = None
        self.last_safest_feasible_margin = float("-inf")
        self._solve_safest_feasible_sequence: np.ndarray | None = None
        self._solve_safest_feasible_margin = float("-inf")
        self._solve_horizon_timing_s: dict[str, float] = {}
        # Disabled in production; the prefix-runtime audit enables this on
        # frozen snapshots to compare every evaluated population quantity.
        self._runtime_equivalence_population_audit = False
        self._runtime_equivalence_population_records: list[dict[str, Any]] = []

    def reset(self) -> None:
        super().reset()
        self._active_spec = None
        self._active_task_state = None
        self._active_target_rad = None
        self._last_phase = None
        self.last_predicted_states = None
        self._first_action_effective_map = None
        self._full_horizon_interface_rollout = None
        self._population_constraint_audit = []
        self._active_human_model = None
        self._current_support_nm = np.zeros(2)
        self.last_total_action_nm = np.zeros(2)
        self.last_motion_increment_nm = np.zeros(2)
        self.last_safest_feasible_sequence = None
        self.last_safest_feasible_margin = float("-inf")
        self._solve_safest_feasible_sequence = None
        self._solve_safest_feasible_margin = float("-inf")
        self._solve_horizon_timing_s = {}
        self._runtime_equivalence_population_records = []

    def _support_action_batch(self, states: np.ndarray) -> np.ndarray:
        """Vectorized qdd=0 inverse dynamics for the fixed Stage-5 model."""

        human = self._active_human_model
        if human is None:
            raise RuntimeError("support model has not been bound")
        state = np.asarray(states, dtype=float)
        if state.shape[-1] != 4 or not np.all(np.isfinite(state)):
            raise ValueError("support batch requires finite Human states[...,4]")
        if hasattr(human, "beta") and hasattr(human, "rom_human"):
            x = state
            q1 = x[..., 0]
            q2 = x[..., 1]
            dq1 = x[..., 2]
            dq2 = x[..., 3]
            phi = q1 - q2
            beta = np.asarray(human.beta, dtype=float)
            support = np.empty(x.shape[:-1] + (2,), dtype=float)
            support[..., 0] = (
                beta[2] * np.sin(q2) * (-2.0 * dq1 * dq2 + dq2**2)
                + beta[3] * np.cos(q1)
                + beta[4] * np.cos(phi)
                + beta[5] * q1
                - beta[7]
                + beta[9] * dq1
            )
            support[..., 1] = (
                beta[2] * np.sin(q2) * dq1**2
                - beta[4] * np.cos(phi)
                + beta[6] * q2
                - beta[8]
                + beta[10] * dq2
            )
            support -= self._batched_soft_limit_torque(
                x[..., :2], x[..., 2:], human.rom_human
            )
            return support
        flat = state.reshape(-1, 4)
        support = np.asarray(
            [support_action(item, human) for item in flat], dtype=float
        )
        return support.reshape(state.shape[:-1] + (2,))

    def synchronize_executed_total_action(
        self,
        total_action_nm: np.ndarray,
        observation: ControllerTaskObservation,
        human_model: Any,
    ) -> None:
        """Synchronize the increment slew state after a non-MPC HOLD command."""

        total = np.asarray(total_action_nm, dtype=float)
        if total.shape != (2,) or not np.all(np.isfinite(total)):
            raise ValueError("executed total action must be a finite two-vector")
        support = support_action(observation.as_array(), human_model)
        self.last_action = total - support
        self.last_total_action_nm = total.copy()
        self.last_motion_increment_nm = self.last_action.copy()
        self.last_sequence = None

    def synchronize_control_model_transition(
        self,
        total_action_nm: np.ndarray,
        observation: ControllerTaskObservation,
        successor_human_model: Any,
    ) -> None:
        """Keep the executed command while invalidating model-specific plans."""

        self.synchronize_executed_total_action(
            total_action_nm, observation, successor_human_model
        )
        self.last_predicted_states = None
        self.last_safest_feasible_sequence = None
        self.last_safest_feasible_margin = float("-inf")
        self._solve_safest_feasible_sequence = None
        self._solve_safest_feasible_margin = float("-inf")

    def _dynamics_sequence(self, sequence: np.ndarray) -> np.ndarray:
        """Convert scalar-path increments to total actions about local support."""

        increments = np.asarray(sequence, dtype=float)
        human = self._active_human_model
        if human is None:
            raise RuntimeError("support model has not been bound")
        # Scalar fallback cannot reuse the coupled batch rollout.  Use the
        # current support for its first action; later support is rebuilt by the
        # dedicated scalar rollout in _evaluate_goal_sequence.
        dynamics_sequence = increments + self._current_support_nm
        if self._first_action_effective_map is not None:
            mapped = np.asarray(
                self._first_action_effective_map(dynamics_sequence[:1]), dtype=float
            )
            if mapped.shape != (1, 2) or not np.all(np.isfinite(mapped)):
                raise ValueError("first-action interface map returned invalid actions")
            dynamics_sequence[0] = mapped[0]
        return dynamics_sequence

    def _total_actions_for_states(
        self,
        initial_state: np.ndarray,
        increments: np.ndarray,
        predicted_states: np.ndarray,
    ) -> np.ndarray:
        before = np.vstack(
            [np.asarray(initial_state, dtype=float), np.asarray(predicted_states)[:-1]]
        )
        return self._support_action_batch(before) + np.asarray(increments, dtype=float)

    def _set_problem(
        self,
        spec: GoalTaskSpec,
        task_state: GoalTaskState,
    ) -> None:
        if task_state.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
            raise ValueError("cannot solve Goal-MPC for a terminal task phase")
        if self._last_phase is not None and task_state.phase is not self._last_phase:
            # A phase target switch invalidates only the old warm-start sequence.
            # Keep last_action so the inherited action-slew term remains causal.
            self.last_sequence = None
        self._active_spec = spec
        self._active_task_state = task_state
        self._active_target_rad = phase_target(spec, task_state)
        self._last_phase = task_state.phase

    def _require_problem(self) -> tuple[GoalTaskSpec, np.ndarray]:
        if self._active_spec is None or self._active_target_rad is None:
            raise RuntimeError("Goal-MPC task problem has not been bound")
        return self._active_spec, self._active_target_rad

    def _require_phase(self) -> TaskPhase:
        if self._active_task_state is None:
            raise RuntimeError("Goal-MPC task phase has not been bound")
        return self._active_task_state.phase

    def _reference_arrays(self, time_s: float, reference_fn: Any):
        """Supply a constant goal set to the inherited seed, never a time reference."""

        del time_s, reference_fn
        _, target = self._require_problem()
        q_target = np.broadcast_to(target, (self.config.horizon_steps, 2)).copy()
        zeros = np.zeros_like(q_target)
        return q_target, zeros, zeros.copy()

    def _seed_sequence(
        self,
        state: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        ddq_ref: np.ndarray,
        human: Any,
    ) -> np.ndarray:
        """Build an independently paced goal seed, not a sampled q(t) trajectory."""

        del q_ref, dq_ref, ddq_ref
        spec, target = self._require_problem()
        predicted = np.asarray(state, dtype=float).copy()
        increments = []
        dt = self.config.prediction_dt_s
        for _ in range(self.config.horizon_steps):
            desired_acceleration = (
                -TRACKING_KP_RAD_S2_PER_RAD * (predicted[:2] - target)
                - TRACKING_KD_RAD_S2_PER_RAD_S * predicted[2:]
            )
            acceleration_limit = np.asarray(
                self.seed_pacing.maximum_acceleration_rad_s2, dtype=float
            )
            desired_acceleration = np.clip(
                desired_acceleration, -acceleration_limit, acceleration_limit
            )
            velocity_limit = np.asarray(
                self.seed_pacing.maximum_velocity_rad_s, dtype=float
            )
            desired_acceleration = np.clip(
                desired_acceleration,
                (-velocity_limit - predicted[2:]) / dt,
                (velocity_limit - predicted[2:]) / dt,
            )
            support = _model_inverse_dynamics(
                predicted[:2], predicted[2:], np.zeros(2), human
            )
            total_action = _model_inverse_dynamics(
                predicted[:2], predicted[2:], desired_acceleration, human
            )
            increments.append(total_action - support)
            predicted = _model_step(predicted, total_action, dt, human)
        heuristic = np.asarray(increments)
        if self.last_sequence is None:
            return heuristic
        warm = np.vstack([self.last_sequence[1:], self.last_sequence[-1]])
        return 0.35 * warm + 0.65 * heuristic

    @staticmethod
    def _forbidden_prescribed_reference(_: float) -> CuffPoseReference:
        raise RuntimeError("Stage-5 Goal-MPC must not query a prescribed q(t) reference")

    def _goal_cost_terms(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        predicted_states: np.ndarray,
        human: Any,
    ) -> tuple[dict[str, float], np.ndarray]:
        _, target = self._require_problem()
        q_error = (predicted_states[:, :2] - target) / self.q_scale
        phase = self._require_phase()
        spec, _ = self._require_problem()
        angle_tolerance = np.asarray(spec.joint_angle_completion_tolerance_rad)
        velocity_tolerance = np.asarray(
            spec.joint_velocity_completion_tolerance_rad_s
        )
        hold_q_normalized = (predicted_states[:, :2] - target) / angle_tolerance
        hold_dq_normalized = predicted_states[:, 2:] / velocity_tolerance
        hold_violation = np.maximum(np.abs(hold_q_normalized) - 1.0, 0.0)
        hold_velocity_violation = np.maximum(
            np.abs(hold_dq_normalized) - 1.0, 0.0
        )
        terminal_q_error = q_error[-1]
        terminal_dq_error = predicted_states[-1, 2:] / self.dq_scale
        previous = np.vstack([self.last_action, sequence[:-1]])
        interaction, allocations = self._interaction_cost_terms(
            state, sequence, predicted_states, human
        )
        force_norm = np.asarray(
            [float(allocation["force_norm_n"]) for allocation in allocations]
        )
        terms = {
            "stage_target_distance": float(
                (0.0 if phase is TaskPhase.HOLD else self.goal_objective.stage_target_distance_weight)
                * np.sum(q_error**2)
            ),
            "hold_set_violation": float(
                self.goal_objective.hold_set_violation_weight
                * (np.sum(hold_violation**2) + np.sum(hold_velocity_violation**2))
                if phase is TaskPhase.HOLD
                else 0.0
            ),
            "hold_inside_regulation": float(
                self.goal_objective.hold_inside_regulation_weight
                * (np.sum(hold_q_normalized**2) + np.sum(hold_dq_normalized**2))
                if phase is TaskPhase.HOLD
                else 0.0
            ),
            "terminal_target_error": float(
                (0.0 if phase is TaskPhase.HOLD else self.goal_objective.terminal_target_error_weight)
                * np.sum(terminal_q_error**2)
            ),
            "terminal_velocity_error": float(
                (0.0 if phase is TaskPhase.HOLD else self.goal_objective.terminal_velocity_error_weight)
                * np.sum(terminal_dq_error**2)
            ),
            "action_effort": float(
                self.config.action_weight * np.sum((sequence / self.action_scale) ** 2)
            ),
            "action_slew": float(
                self.config.action_rate_weight
                * np.sum(((sequence - previous) / self.rate_scale) ** 2)
            ),
            "resultant_force": float(interaction["resultant_force_cost"]),
            "cylindrical_surface_effort": float(
                interaction["cylindrical_surface_effort_cost"]
            ),
            "wrench_slew": float(interaction["wrench_slew_cost"]),
            "hold_physical_force": float(
                self.goal_objective.hold_physical_force_weight
                * np.sum((force_norm / CUFF_TRANSLATIONAL_FORCE_GATE_N) ** 2)
                if phase is TaskPhase.HOLD
                else 0.0
            ),
            "learned_terminal_value": 0.0,
        }
        return terms, force_norm

    def _interaction_cost_terms(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        predicted_states: np.ndarray,
        human: Any,
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        """Avoid repeated scalar allocation in v1.3 post-solve diagnostics."""

        rollout = self._full_horizon_interface_rollout
        owner = getattr(rollout, "__self__", None)
        total_actions = self._total_actions_for_states(
            state, sequence, predicted_states
        )
        if owner is None or self.config.interaction_aware:
            return super()._interaction_cost_terms(
                state, total_actions, predicted_states, human
            )
        wrenches = owner._allocate_varying_q_batch(
            total_actions,
            np.asarray(predicted_states, dtype=float)[:, :2],
        )
        force_squared = float(np.sum(wrenches[:, :3] ** 2))
        normalization_squared = self.config.interaction_force_normalization_n**2
        allocations = [
            {
                "wrench_world": wrench.copy(),
                "force_norm_n": float(np.linalg.norm(wrench[:3])),
            }
            for wrench in wrenches
        ]
        return (
            {
                "resultant_force_cost": 0.0,
                "cylindrical_surface_effort_cost": 0.0,
                "wrench_slew_cost": 0.0,
                "normalized_resultant_force_squared_sum": (
                    force_squared / normalization_squared
                ),
                "normalized_cylindrical_surface_effort_squared_sum": 0.0,
                "normalized_wrench_slew_squared_sum": 0.0,
            },
            allocations,
        )

    def _constraint_margin(
        self,
        state: np.ndarray,
        predicted_states: np.ndarray,
        force_norm_n: np.ndarray,
        human: Any,
    ) -> float:
        spec, _ = self._require_problem()
        q = predicted_states[:, :2]
        margins = [
            (q - np.asarray(human.q_min_rad)).reshape(-1),
            (np.asarray(human.q_max_rad) - q).reshape(-1),
            (q - np.asarray([item[0] for item in spec.q_bounds_rad])).reshape(-1),
            (np.asarray([item[1] for item in spec.q_bounds_rad]) - q).reshape(-1),
            self.planning_physical_force_ceiling_n - force_norm_n,
        ]
        if spec.task_joint_velocity_limit_rad_s is not None:
            velocity_limit = np.asarray(spec.task_joint_velocity_limit_rad_s)
            margins.append((velocity_limit - np.abs(predicted_states[:, 2:])).reshape(-1))
        if self.planning_joint_velocity_ceiling_rad_s is not None:
            pacing_limit = np.asarray(self.planning_joint_velocity_ceiling_rad_s)
            margins.append(
                (pacing_limit - np.abs(predicted_states[:, 2:])).reshape(-1)
            )
        if spec.task_joint_acceleration_limit_rad_s2 is not None:
            velocity = np.vstack([state[2:], predicted_states[:, 2:]])
            acceleration = np.diff(velocity, axis=0) / self.config.prediction_dt_s
            acceleration_limit = np.asarray(spec.task_joint_acceleration_limit_rad_s2)
            margins.append((acceleration_limit - np.abs(acceleration)).reshape(-1))
        if self._require_phase() is TaskPhase.HOLD:
            _, target = self._require_problem()
            margins.extend(
                [
                    (
                        np.asarray(spec.joint_angle_completion_tolerance_rad)
                        - np.abs(q - target)
                    ).reshape(-1),
                    (
                        np.asarray(spec.joint_velocity_completion_tolerance_rad_s)
                        - np.abs(predicted_states[:, 2:])
                    ).reshape(-1),
                ]
            )
        return float(np.min(np.concatenate(margins)))

    def _evaluate_goal_sequence(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        human: Any,
    ) -> GoalCandidateEvaluation:
        shape = (self.config.horizon_steps, 2)
        candidate = np.asarray(sequence, dtype=float).reshape(shape)
        if not np.all(np.isfinite(candidate)) or np.max(np.abs(candidate)) > 1.0e6:
            return GoalCandidateEvaluation(1.0e30, -1.0e6, None, {})
        try:
            with np.errstate(over="raise", invalid="raise"):
                current = np.asarray(state, dtype=float).copy()
                states = np.empty((self.config.horizon_steps, 4), dtype=float)
                for index, increment in enumerate(candidate):
                    total_action = support_action(current, human) + increment
                    if index == 0 and self._first_action_effective_map is not None:
                        total_action = np.asarray(
                            self._first_action_effective_map(
                                increment[np.newaxis, :]
                            ),
                            dtype=float,
                        )[0]
                    current = _model_step(
                        current, total_action, self.config.prediction_dt_s, human
                    )
                    states[index] = current
                terms, force_norm = self._goal_cost_terms(
                    np.asarray(state, dtype=float), candidate, states, human
                )
                margin = self._constraint_margin(state, states, force_norm, human)
        except (ValueError, RuntimeError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return GoalCandidateEvaluation(1.0e30, -1.0e6, None, {})
        if not np.all(np.isfinite(states)) or np.max(np.abs(states)) > 1.0e6:
            return GoalCandidateEvaluation(1.0e30, -1.0e6, None, {})
        total = float(sum(terms.values()))
        return GoalCandidateEvaluation(total, margin, states, terms)

    def _evaluate_sequence(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        human: Any,
        *,
        previous_action: np.ndarray | None = None,
    ) -> tuple[float, float, np.ndarray | None]:
        del q_ref, dq_ref
        if previous_action is not None:
            raise ValueError("Goal-MPC uses its causal retained last_action")
        result = self._evaluate_goal_sequence(state, sequence, human)
        return result.total_cost, result.minimum_constraint_margin, result.predicted_states

    def _evaluate_population(
        self,
        state: np.ndarray,
        candidates: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        human: Any,
    ) -> list[tuple[float, float, np.ndarray | None]]:
        del q_ref, dq_ref
        if not self._can_use_batched_population(human):
            return [
                (
                    result.total_cost,
                    result.minimum_constraint_margin,
                    result.predicted_states,
                )
                for result in (
                    self._evaluate_goal_sequence(state, candidate, human)
                    for candidate in candidates
                )
            ]

        candidate = np.asarray(candidates, dtype=float)
        count = candidate.shape[0]
        section_start = perf_counter() if self.record_timing_breakdown else 0.0
        dynamics_candidate = candidate.copy()
        if (
            self._full_horizon_interface_rollout is None
            and self._first_action_effective_map is not None
        ):
            mapped = np.asarray(
                self._first_action_effective_map(candidate[:, 0, :]), dtype=float
            )
            if mapped.shape != (count, 2) or not np.all(np.isfinite(mapped)):
                raise ValueError("first-action interface map returned invalid batch")
            dynamics_candidate[:, 0, :] = mapped
        try:
            with np.errstate(over="raise", invalid="raise"):
                if self._full_horizon_interface_rollout is not None:
                    coupled = self._full_horizon_interface_rollout(
                        np.asarray(state, dtype=float),
                        candidate,
                        self._batched_base_step,
                    )
                    predicted = coupled.predicted_human_states
                    force_norm = coupled.predicted_peak_force_n
                    allocated_force_norm = coupled.allocated_force_norm_n
                    coupled_timing = getattr(coupled, "timing_s", None)
                    if self.record_timing_breakdown and coupled_timing is not None:
                        for name, value in coupled_timing.items():
                            self._solve_horizon_timing_s[name] = (
                                self._solve_horizon_timing_s.get(name, 0.0)
                                + float(value)
                            )
                else:
                    states = np.empty(
                        (count, self.config.horizon_steps + 1, 4), dtype=float
                    )
                    states[:, 0, :] = np.asarray(state, dtype=float)
                    for step in range(self.config.horizon_steps):
                        states[:, step + 1, :] = self._batched_base_step(
                            states[:, step, :], dynamics_candidate[:, step, :], human
                        )
                    predicted = states[:, 1:, :]
                    force_norm = self._batched_cuff_force_norm(
                        candidate, predicted[..., :2], human
                    )
                    allocated_force_norm = force_norm
                rollout_runtime_s = (
                    perf_counter() - section_start
                    if self.record_timing_breakdown
                    else 0.0
                )
        except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return [
                (
                    result.total_cost,
                    result.minimum_constraint_margin,
                    result.predicted_states,
                )
                for result in (
                    self._evaluate_goal_sequence(state, item, human)
                    for item in candidate
                )
            ]

        section_start = perf_counter() if self.record_timing_breakdown else 0.0
        spec, target = self._require_problem()
        phase = self._require_phase()
        q_error = (predicted[..., :2] - target) / self.q_scale
        stage = (
            self.goal_objective.stage_target_distance_weight
            * np.sum(q_error**2, axis=(1, 2))
            if phase is not TaskPhase.HOLD
            else np.zeros(count)
        )
        angle_tolerance = np.asarray(spec.joint_angle_completion_tolerance_rad)
        velocity_tolerance = np.asarray(
            spec.joint_velocity_completion_tolerance_rad_s
        )
        hold_q = (predicted[..., :2] - target) / angle_tolerance
        hold_dq = predicted[..., 2:] / velocity_tolerance
        hold_violation = (
            self.goal_objective.hold_set_violation_weight
            * (
                np.sum(np.maximum(np.abs(hold_q) - 1.0, 0.0) ** 2, axis=(1, 2))
                + np.sum(np.maximum(np.abs(hold_dq) - 1.0, 0.0) ** 2, axis=(1, 2))
            )
            if phase is TaskPhase.HOLD
            else np.zeros(count)
        )
        hold_regulation = (
            self.goal_objective.hold_inside_regulation_weight
            * (np.sum(hold_q**2, axis=(1, 2)) + np.sum(hold_dq**2, axis=(1, 2)))
            if phase is TaskPhase.HOLD
            else np.zeros(count)
        )
        terminal_q = (0.0 if phase is TaskPhase.HOLD else self.goal_objective.terminal_target_error_weight) * np.sum(
            q_error[:, -1, :] ** 2, axis=1
        )
        terminal_dq = (0.0 if phase is TaskPhase.HOLD else self.goal_objective.terminal_velocity_error_weight) * np.sum(
            (predicted[:, -1, 2:] / self.dq_scale) ** 2, axis=1
        )
        effort = self.config.action_weight * np.sum(
            (candidate / self.action_scale) ** 2, axis=(1, 2)
        )
        delta = np.empty_like(candidate)
        delta[:, 0, :] = candidate[:, 0, :] - self.last_action
        delta[:, 1:, :] = candidate[:, 1:, :] - candidate[:, :-1, :]
        slew = self.config.action_rate_weight * np.sum(
            (delta / self.rate_scale) ** 2, axis=(1, 2)
        )
        hold_force = (
            self.goal_objective.hold_physical_force_weight
            * np.sum((force_norm / CUFF_TRANSLATIONAL_FORCE_GATE_N) ** 2, axis=1)
            if phase is TaskPhase.HOLD
            else np.zeros(count)
        )
        cost = (
            stage
            + hold_violation
            + hold_regulation
            + hold_force
            + terminal_q
            + terminal_dq
            + effort
            + slew
        )

        q = predicted[..., :2]
        component_margins = {
            "human_q_lower_rad": np.min(
                q - np.asarray(human.q_min_rad), axis=(1, 2)
            ),
            "human_q_upper_rad": np.min(
                np.asarray(human.q_max_rad) - q, axis=(1, 2)
            ),
            "task_q_lower_rad": np.min(
                q - np.asarray([item[0] for item in spec.q_bounds_rad]),
                axis=(1, 2),
            ),
            "task_q_upper_rad": np.min(
                np.asarray([item[1] for item in spec.q_bounds_rad]) - q,
                axis=(1, 2),
            ),
            "physical_force_n": np.min(
                self.planning_physical_force_ceiling_n - force_norm, axis=1
            ),
            "allocated_force_n": np.min(
                CUFF_TRANSLATIONAL_FORCE_GATE_N - allocated_force_norm, axis=1
            ),
        }
        safety_margin_parts = [
            values[:, None] for values in component_margins.values()
        ]
        if spec.task_joint_velocity_limit_rad_s is not None:
            limit = np.asarray(spec.task_joint_velocity_limit_rad_s)
            velocity_margin = np.min(
                limit - np.abs(predicted[..., 2:]), axis=(1, 2)
            )
            component_margins["task_velocity_rad_s"] = velocity_margin
            safety_margin_parts.append(velocity_margin[:, None])
        if self.planning_joint_velocity_ceiling_rad_s is not None:
            pacing_limit = np.asarray(self.planning_joint_velocity_ceiling_rad_s)
            pacing_margin = np.min(
                pacing_limit - np.abs(predicted[..., 2:]), axis=(1, 2)
            )
            component_margins["planning_velocity_rad_s"] = pacing_margin
            safety_margin_parts.append(pacing_margin[:, None])
        if spec.task_joint_acceleration_limit_rad_s2 is not None:
            velocity = np.concatenate(
                [
                    np.broadcast_to(np.asarray(state)[2:], (count, 1, 2)),
                    predicted[..., 2:],
                ],
                axis=1,
            )
            acceleration = np.diff(velocity, axis=1) / self.config.prediction_dt_s
            limit = np.asarray(spec.task_joint_acceleration_limit_rad_s2)
            acceleration_margin = np.min(
                limit - np.abs(acceleration), axis=(1, 2)
            )
            component_margins["task_acceleration_rad_s2"] = acceleration_margin
            safety_margin_parts.append(acceleration_margin[:, None])
        safety_margin = np.min(
            np.concatenate(safety_margin_parts, axis=1), axis=1
        )
        hold_margin: np.ndarray | None = None
        hold_set_enforced = False
        if phase is TaskPhase.HOLD:
            hold_margin = np.min(
                np.concatenate(
                    [
                        (
                            np.asarray(spec.joint_angle_completion_tolerance_rad)
                            - np.abs(q - target)
                        ).reshape(count, -1),
                        (
                            np.asarray(spec.joint_velocity_completion_tolerance_rad_s)
                            - np.abs(predicted[..., 2:])
                        ).reshape(count, -1),
                    ],
                    axis=1,
                ),
                axis=1,
            )
            # The completion set is enforced whenever the sampled population
            # contains a plant/task-safe sequence that remains inside it.  If
            # stored interface energy makes the set temporarily unreachable,
            # keep the safety constraints hard and let the normalized set-
            # violation cost select a recovery sequence instead of declaring
            # NO_SAFE_ACTION. GoalTaskState alone owns the continuous timer.
            hold_set_enforced = bool(
                np.any((safety_margin >= -1.0e-9) & (hold_margin >= -1.0e-9))
            )
        margin = (
            np.minimum(safety_margin, hold_margin)
            if hold_set_enforced and hold_margin is not None
            else safety_margin
        )
        audit_record = {
            "phase": phase.value,
            "candidate_count": int(count),
            "best_safety_margin": float(np.max(safety_margin)),
            "best_component_margin": {
                name: float(np.max(values))
                for name, values in component_margins.items()
            },
            "component_feasible_candidate_count": {
                name: int(np.count_nonzero(values >= -1.0e-9))
                for name, values in component_margins.items()
            },
        }
        if phase is TaskPhase.HOLD:
            hold_component_margins = {
                "hold_angle_rad": np.min(
                    np.asarray(spec.joint_angle_completion_tolerance_rad)
                    - np.abs(q - target),
                    axis=(1, 2),
                ),
                "hold_velocity_rad_s": np.min(
                    np.asarray(spec.joint_velocity_completion_tolerance_rad_s)
                    - np.abs(predicted[..., 2:]),
                    axis=(1, 2),
                ),
                "physical_force_n": np.min(
                    CUFF_TRANSLATIONAL_FORCE_GATE_N - force_norm, axis=1
                ),
                "allocated_force_n": np.min(
                    CUFF_TRANSLATIONAL_FORCE_GATE_N - allocated_force_norm,
                    axis=1,
                ),
            }
            audit_record.update(
                {
                    "best_combined_margin": float(np.max(margin)),
                    "best_raw_hold_margin": float(np.max(hold_margin)),
                    "hold_set_enforced": hold_set_enforced,
                    "recovery_fallback_active": not hold_set_enforced,
                }
            )
            audit_record["best_component_margin"].update(
                {
                    name: float(np.max(values))
                    for name, values in hold_component_margins.items()
                }
            )
            audit_record["component_feasible_candidate_count"].update(
                {
                    name: int(np.count_nonzero(values >= -1.0e-9))
                    for name, values in hold_component_margins.items()
                }
            )
        self._population_constraint_audit.append(audit_record)
        valid = (
            np.all(np.isfinite(predicted), axis=(1, 2))
            & np.all(np.isfinite(force_norm), axis=1)
            & np.all(np.isfinite(allocated_force_norm), axis=1)
            & np.isfinite(cost)
        )
        if self.record_timing_breakdown:
            self._last_population_timing_s = {
                "dynamics_propagation": rollout_runtime_s,
                "cuff_constraint_allocation": 0.0,
                "cost_constraint_evaluation": perf_counter() - section_start,
            }
        results = [
            (
                float(cost[index]) if valid[index] else 1.0e30,
                float(margin[index]) if valid[index] else -1.0e6,
                predicted[index] if valid[index] else None,
            )
            for index in range(count)
        ]
        if self._runtime_equivalence_population_audit:
            self._runtime_equivalence_population_records.append(
                {
                    "candidates_nm": candidate.copy(),
                    "cost": np.asarray(
                        [evaluation[0] for evaluation in results], dtype=float
                    ),
                    "margin": np.asarray(
                        [evaluation[1] for evaluation in results], dtype=float
                    ),
                    "predicted_states": predicted.copy(),
                    "force_norm_n": force_norm.copy(),
                    "allocated_force_norm_n": allocated_force_norm.copy(),
                }
            )
        for index, evaluation in enumerate(results):
            candidate_margin = float(evaluation[1])
            if (
                evaluation[2] is not None
                and candidate_margin >= -1.0e-9
                and candidate_margin > self._solve_safest_feasible_margin
            ):
                self._solve_safest_feasible_margin = candidate_margin
                self._solve_safest_feasible_sequence = candidate[index].copy()
        return results

    def audit_candidate_sequences_with_preview(
        self,
        observation: ControllerTaskObservation,
        task_state: GoalTaskState,
        spec: GoalTaskSpec,
        human_model: Any,
        sequences_nm: dict[str, np.ndarray],
        *,
        first_action_batch_preview: FirstActionBatchPreview,
    ) -> dict[str, dict[str, Any]]:
        """Revalidate named increment sequences using production semantics.

        This is intentionally a diagnostic API: it neither samples candidates
        nor updates the retained action/sequence/RNG state.
        """

        self._set_problem(spec, task_state)
        self._population_constraint_audit = []
        if self._runtime_equivalence_population_audit:
            self._runtime_equivalence_population_records = []
        state = observation.as_array()
        self._active_human_model = human_model
        self._current_support_nm = support_action(state, human_model)
        batch_preview = _SupportCenteredBatchPreview(
            first_action_batch_preview,
            self._current_support_nm,
            self._support_action_batch,
        )
        self._first_action_effective_map = getattr(
            batch_preview, "effective_generalized_action_nm", None
        )
        self._full_horizon_interface_rollout = getattr(
            batch_preview, "rollout_horizon", None
        )
        previous_population_audit = self._population_constraint_audit
        previous_safest_sequence = self._solve_safest_feasible_sequence
        previous_safest_margin = self._solve_safest_feasible_margin
        output: dict[str, dict[str, Any]] = {}
        try:
            for name, raw_sequence in sequences_nm.items():
                sequence = np.asarray(raw_sequence, dtype=float)
                expected_shape = (self.config.horizon_steps, 2)
                if sequence.shape != expected_shape or not np.all(np.isfinite(sequence)):
                    raise ValueError(
                        f"candidate {name!r} must be finite with shape {expected_shape}"
                    )
                first = batch_preview(sequence[0][np.newaxis, :])
                first_feasible = bool(np.asarray(first.feasible, dtype=bool)[0])
                filter_status = getattr(first, "filter_status", None)
                first_command = first.command(0)
                self._population_constraint_audit = []
                self._solve_safest_feasible_sequence = None
                self._solve_safest_feasible_margin = float("-inf")
                if first_feasible:
                    evaluation = self._evaluate_population(
                        state,
                        sequence[np.newaxis, ...],
                        np.empty((0, 2)),
                        np.empty((0, 2)),
                        human_model,
                    )[0]
                    population = dict(self._population_constraint_audit[-1])
                else:
                    evaluation = (1.0e30, -1.0e6, None)
                    population = {}
                predicted = evaluation[2]
                first_velocity_violation_step = None
                first_acceleration_violation_step = None
                peak_velocity = None
                peak_acceleration = None
                if predicted is not None:
                    predicted_velocity = np.asarray(predicted[:, 2:], dtype=float)
                    velocity_limit = spec.task_joint_velocity_limit_rad_s
                    if velocity_limit is not None:
                        velocity_excess = np.any(
                            np.abs(predicted_velocity)
                            > np.asarray(velocity_limit, dtype=float) + 1.0e-9,
                            axis=1,
                        )
                        violation = np.flatnonzero(velocity_excess)
                        if len(violation):
                            first_velocity_violation_step = int(violation[0] + 1)
                    acceleration = np.diff(
                        np.vstack([state[2:], predicted_velocity]), axis=0
                    ) / self.config.prediction_dt_s
                    acceleration_limit = spec.task_joint_acceleration_limit_rad_s2
                    if acceleration_limit is not None:
                        acceleration_excess = np.any(
                            np.abs(acceleration)
                            > np.asarray(acceleration_limit, dtype=float) + 1.0e-9,
                            axis=1,
                        )
                        violation = np.flatnonzero(acceleration_excess)
                        if len(violation):
                            first_acceleration_violation_step = int(violation[0] + 1)
                    peak_velocity = np.max(np.abs(predicted_velocity), axis=0).tolist()
                    peak_acceleration = np.max(np.abs(acceleration), axis=0).tolist()
                output[name] = {
                    "first_action_executable": first_feasible,
                    "first_action_filter_status": (
                        None
                        if filter_status is None
                        else str(np.asarray(filter_status)[0])
                    ),
                    "first_action_force_margin_n": float(
                        first_command.margin_to_force_gate_n
                    ),
                    "first_action_predicted_physical_force_margin_n": float(
                        np.asarray(
                            first.margin_to_physical_force_gate_n, dtype=float
                        )[0]
                    ),
                    "feasible": bool(
                        first_feasible
                        and predicted is not None
                        and float(evaluation[1]) >= -1.0e-9
                    ),
                    "total_cost": float(evaluation[0]),
                    "minimum_constraint_margin": float(evaluation[1]),
                    "constraint_components": population.get(
                        "best_component_margin", {}
                    ),
                    "first_velocity_violation_step": first_velocity_violation_step,
                    "first_acceleration_violation_step": (
                        first_acceleration_violation_step
                    ),
                    "peak_abs_velocity_rad_s": peak_velocity,
                    "peak_abs_acceleration_rad_s2": peak_acceleration,
                    "terminal_state_rad_rad_s": (
                        None
                        if predicted is None
                        else np.asarray(predicted[-1], dtype=float).tolist()
                    ),
                }
        finally:
            self._population_constraint_audit = previous_population_audit
            self._solve_safest_feasible_sequence = previous_safest_sequence
            self._solve_safest_feasible_margin = previous_safest_margin
            self._first_action_effective_map = None
            self._full_horizon_interface_rollout = None
            self._active_human_model = None
        return output

    def evaluate_candidate_sequence(
        self,
        observation: ControllerTaskObservation,
        task_state: GoalTaskState,
        spec: GoalTaskSpec,
        human_model: Any,
        sequence_nm: np.ndarray,
    ) -> GoalCandidateEvaluation:
        """Evaluate a supplied candidate for tests/audits without CEM sampling."""

        self._set_problem(spec, task_state)
        self._population_constraint_audit = []
        self._active_human_model = human_model
        try:
            return self._evaluate_goal_sequence(
                observation.as_array(), np.asarray(sequence_nm, dtype=float), human_model
            )
        finally:
            self._active_human_model = None

    def build_deterministic_continuations(
        self,
        observation: ControllerTaskObservation,
        task_state: GoalTaskState,
        spec: GoalTaskSpec,
        human_model: Any,
        *,
        previous_selected_sequence_nm: np.ndarray | None,
        previous_safest_sequence_nm: np.ndarray | None = None,
    ) -> dict[str, np.ndarray]:
        """Construct general, state-based continuations for failure diagnosis."""

        self._set_problem(spec, task_state)
        state = observation.as_array()
        horizon = self.config.horizon_steps
        candidates: dict[str, np.ndarray] = {
            "support_only": np.zeros((horizon, 2), dtype=float)
        }
        if previous_selected_sequence_nm is not None:
            previous = np.asarray(previous_selected_sequence_nm, dtype=float)
            candidates["shifted_previous_selected"] = np.vstack(
                [previous[1:], previous[-1]]
            )
        if previous_safest_sequence_nm is not None:
            previous = np.asarray(previous_safest_sequence_nm, dtype=float)
            candidates["shifted_previous_safest"] = np.vstack(
                [previous[1:], previous[-1]]
            )

        predicted = state.copy()
        braking: list[np.ndarray] = []
        acceleration_limit = (
            np.asarray(spec.task_joint_acceleration_limit_rad_s2, dtype=float)
            if spec.task_joint_acceleration_limit_rad_s2 is not None
            else np.full(2, np.inf)
        )
        dt = self.config.prediction_dt_s
        for _ in range(horizon):
            desired_acceleration = np.clip(
                -predicted[2:] / dt,
                -acceleration_limit,
                acceleration_limit,
            )
            support = _model_inverse_dynamics(
                predicted[:2], predicted[2:], np.zeros(2), human_model
            )
            total = _model_inverse_dynamics(
                predicted[:2], predicted[2:], desired_acceleration, human_model
            )
            braking.append(total - support)
            predicted = _model_step(predicted, total, dt, human_model)
        candidates["model_based_braking"] = np.asarray(braking)

        self._active_human_model = human_model
        try:
            target = phase_target(spec, task_state)
            q_ref = np.broadcast_to(target, (horizon, 2)).copy()
            zeros = np.zeros_like(q_ref)
            candidates["smooth_conservative_goal_progress"] = self._seed_sequence(
                state, q_ref, zeros, zeros, human_model
            )
        finally:
            self._active_human_model = None
        return candidates

    def solve_goal(
        self,
        observation: ControllerTaskObservation,
        task_state: GoalTaskState,
        spec: GoalTaskSpec,
        human_model: Any,
        *,
        first_action_preview: FirstActionPreview | None = None,
        first_action_batch_preview: FirstActionBatchPreview | None = None,
    ) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Solve the active state-goal problem with V_terminal fixed to zero."""

        self._set_problem(spec, task_state)
        self._population_constraint_audit = []
        state = observation.as_array()
        self._active_human_model = human_model
        self._current_support_nm = support_action(state, human_model)
        self._solve_safest_feasible_sequence = None
        self._solve_safest_feasible_margin = float("-inf")
        self._solve_horizon_timing_s = {}
        if self.last_sequence is None:
            continuation = np.broadcast_to(
                self.last_action,
                (self.config.horizon_steps, 2),
            ).copy()
        else:
            continuation = np.vstack(
                [self.last_sequence[1:], self.last_sequence[-1]]
            )
        scalar_preview = (
            None
            if first_action_preview is None
            else _SupportCenteredScalarPreview(
                first_action_preview, self._current_support_nm
            )
        )
        batch_preview = (
            None
            if first_action_batch_preview is None
            else _SupportCenteredBatchPreview(
                first_action_batch_preview,
                self._current_support_nm,
                self._support_action_batch,
            )
        )
        self._first_action_effective_map = (
            None
            if batch_preview is None
            else getattr(
                batch_preview,
                "effective_generalized_action_nm",
                None,
            )
        )
        self._full_horizon_interface_rollout = (
            None
            if batch_preview is None
            else getattr(batch_preview, "rollout_horizon", None)
        )
        original_config = self.config
        original_rng = self.rng
        self.config = replace(
            original_config,
            exploration_std_nm=self.motion_config.exploration_std_nm,
            exploration_std_floor_nm=self.motion_config.exploration_std_floor_nm,
        )
        self.rng = _AnchoredMotionIncrementRNG(original_rng, continuation)
        try:
            increment, diagnostics = super().solve(
                state,
                observation.controller_timestamp_s,
                self._forbidden_prescribed_reference,
                human_model,
                first_action_preview=scalar_preview,
                first_action_batch_preview=batch_preview,
            )
        finally:
            self.config = original_config
            self.rng = original_rng
            self._first_action_effective_map = None
            self._full_horizon_interface_rollout = None
            self._active_human_model = None
        action = (
            None
            if increment is None
            else self._current_support_nm + np.asarray(increment, dtype=float)
        )
        if increment is not None:
            self.last_motion_increment_nm = np.asarray(increment, dtype=float).copy()
            self.last_total_action_nm = np.asarray(action, dtype=float).copy()
            if self._solve_safest_feasible_sequence is not None:
                self.last_safest_feasible_sequence = (
                    self._solve_safest_feasible_sequence.copy()
                )
                self.last_safest_feasible_margin = float(
                    self._solve_safest_feasible_margin
                )
        # The parent solve already evaluates the selected sequence.  Goal-MPC
        # v1 repeated the complete horizon solely to populate diagnostics,
        # adding duplicate dynamics/allocation work to every hot-loop solve.
        self.last_predicted_states = None
        diagnostics.update(
            {
                "controller": "stage5_support_centered_goal_mpc_v1",
                "task_phase": task_state.phase.value,
                "phase_target_rad": phase_target(spec, task_state).tolist(),
                "observation_source": observation.source,
                "observation_age_s": observation.age_s,
                "human_model_version": observation.human_model_version,
                "prescribed_full_q_reference_used": False,
                "fixed_q1_q2_coordination_ratio": False,
                "path_corridor_active": False,
                "learned_terminal_value": 0.0,
                "action_parameterization": "u_total = u_support + delta_u_motion",
                "support_action_nm": self._current_support_nm.tolist(),
                "selected_motion_increment_nm": (
                    None
                    if increment is None
                    else np.asarray(increment, dtype=float).tolist()
                ),
                "selected_total_action_nm": (
                    None if action is None else np.asarray(action, dtype=float).tolist()
                ),
                "support_source": (
                    "inverse_dynamics(q_hat,dq_hat,qdd=0,fixed_human_model)"
                ),
                "cem_initialization_anchors": {
                    "independently_paced_motion_seed": True,
                    "support_only_zero_motion_increment": True,
                    "smooth_executed_command_continuation": True,
                },
                "motion_sampling_scale_nm": {
                    "initial_std": list(self.motion_config.exploration_std_nm),
                    "floor_std": list(
                        self.motion_config.exploration_std_floor_nm
                    ),
                    "provisional": True,
                },
                "hold_population_constraint_audit": list(
                    self._population_constraint_audit
                ),
                "seed_pacing": {
                    "source": "legacy_low_moderate_fixture_peak_dq_ddq",
                    "maximum_velocity_deg_s": np.degrees(
                        self.seed_pacing.maximum_velocity_rad_s
                    ).tolist(),
                    "maximum_acceleration_deg_s2": np.degrees(
                        self.seed_pacing.maximum_acceleration_rad_s2
                    ).tolist(),
                    "constraint": False,
                },
                "interface_robustness_planning": {
                    "physical_force_ceiling_n": (
                        self.planning_physical_force_ceiling_n
                    ),
                    "physical_force_reserve_to_200n_gate_n": (
                        CUFF_TRANSLATIONAL_FORCE_GATE_N
                        - self.planning_physical_force_ceiling_n
                    ),
                    "joint_velocity_ceiling_deg_s": (
                        None
                        if self.planning_joint_velocity_ceiling_rad_s is None
                        else np.degrees(
                            self.planning_joint_velocity_ceiling_rad_s
                        ).tolist()
                    ),
                    "registered_physical_velocity_limits_unchanged": True,
                },
                "selected_goal_cost_terms": {
                    "status": "not_recomputed_in_hot_loop_v1.1"
                },
                "first_prediction_action_semantics": (
                    "nominal mean transmitted Human generalized input over action hold"
                    if first_action_batch_preview is not None
                    and hasattr(
                        first_action_batch_preview,
                        "effective_generalized_action_nm",
                    )
                    else "requested Human generalized action"
                ),
                "first_action_acceleration_semantics": (
                    "cumulative deployable-model dq change at 5/10/15/20 ms; "
                    "all registered joint limits hard"
                    if first_action_batch_preview is not None
                    and getattr(
                        first_action_batch_preview,
                        "acceleration_limits_rad_s2",
                        None,
                    )
                    is not None
                    else "legacy full 20 ms horizon-grid acceleration only"
                ),
                "objective_contract": {
                    "stage_target_distance": (
                        "sum_k ||(q_k-q_phase_target)/inherited_q_scale||^2"
                    ),
                    "terminal_target_error": (
                        "||(q_H-q_phase_target)/inherited_q_scale||^2"
                    ),
                    "terminal_velocity_error": "||dq_H/inherited_dq_scale||^2",
                    "hold_admissible_set": (
                        "sampled-feasible predicted |q-q_goal| and |dq| within "
                        "GoalTaskSpec tolerances, with safety-hard recovery fallback"
                    ),
                    "hold_set_violation": "squared normalized excess outside set",
                    "hold_inside_regulation": "modest normalized q/dq regulation",
                    "action_effort": (
                        "unchanged inherited weight/scale applied to delta_u_motion"
                    ),
                    "action_slew": (
                        "unchanged inherited weight/scale applied to delta_u_motion slew"
                    ),
                    "optional_cuff_terms": (
                        "unchanged inherited resultant/surface/wrench-slew terms"
                    ),
                    "learned_terminal_value": 0.0,
                },
            }
        )
        if self.record_timing_breakdown:
            timing_output = diagnostics.get("implementation_timing_ms", {})
            timing_output.update(
                {
                    f"stage5_{name}": 1000.0 * value
                    for name, value in self._solve_horizon_timing_s.items()
                }
            )
            diagnostics["implementation_timing_ms"] = timing_output
        self.last_diagnostics = dict(diagnostics)
        return action, diagnostics


__all__ = [
    "GoalCandidateEvaluation",
    "GoalDirectedHumanSpaceMPC",
    "GoalMPCObjective",
    "GoalMPCSeedPacing",
    "SupportCenteredMotionConfig",
    "local_command_reference",
    "phase_target",
    "support_action",
]
