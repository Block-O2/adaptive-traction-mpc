"""Phase-3 adapter from the frozen V2.2 belief to Human-waypoint HWMPC.

The adapter is intentionally small.  It keeps the recovered state-residual
model, the existing direct-Delta-q waypoint planner, and the existing
event-driven task state machine separated by explicit records.  No hidden
simulation setup is accepted by any public API in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Sequence

import numpy as np

from traction_mpc_stage3.human import HUMAN, soft_limit_torque
from traction_mpc_stage4.estimator_v2 import (
    PlanarCuffGeometry,
    dynamic_regressor_row,
)

from ..human_waypoint_feedback_mpc import (
    HumanWaypointFeedbackDecisionV1,
    HumanWaypointFeedbackMPCV1,
)
from ..human_waypoint_scheduler import (
    HumanWaypointCandidate,
    QuinticHumanWaypointSchedule,
)
from ..task import (
    GoalTaskSpec,
    GoalTaskState,
    TaskPhase,
    start_episode,
    transition_phase,
)
from .effective_model import (
    EffectiveGeometryFit,
    OnlineEffectiveDynamicsIdentifier,
    build_planar_geometry,
)
from .functional_benchmark import (
    StateResidualHumanModel,
    _update_state_residual_weights,
)


PHASE3_HUMAN_WAYPOINT_VERSION = "architecture_recovery_v2_2_phase3_hwmpc_v1"


def _finite_array(name: str, value: Any, shape: tuple[int, ...]) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result.copy()


@dataclass(frozen=True)
class AdaptiveHumanBeliefV22:
    """Control-sufficient deployable belief consumed by waypoint planning."""

    geometry: PlanarCuffGeometry
    beta: np.ndarray
    state_residual_weights_nm: np.ndarray
    sequence: int
    dynamics_sample_count: int
    accepted_beta_update_count: int
    residual_update_count: int
    geometry_source: str = "ONLINE_ESTIMATED"
    dynamics_source: str = "ONLINE_ESTIMATED"
    residual_source: str = "ONLINE_ESTIMATED"
    deployable_truth_consumed: bool = False
    residual_limit_nm: float = 12.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "beta", _finite_array("beta", self.beta, (11,)))
        object.__setattr__(
            self,
            "state_residual_weights_nm",
            _finite_array(
                "state_residual_weights_nm", self.state_residual_weights_nm, (2, 5)
            ),
        )
        for name in (
            "sequence",
            "dynamics_sample_count",
            "accepted_beta_update_count",
            "residual_update_count",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.deployable_truth_consumed:
            raise ValueError("deployable V2.2 belief must not consume hidden truth")
        if not math.isfinite(self.residual_limit_nm) or self.residual_limit_nm <= 0.0:
            raise ValueError("residual_limit_nm must be finite and positive")
        if any(
            source not in {"ONLINE_ESTIMATED", "CALIBRATED", "STRUCTURAL_PRIOR", "FIXED_NOMINAL"}
            for source in (
                self.geometry_source,
                self.dynamics_source,
                self.residual_source,
            )
        ):
            raise ValueError("belief sources must be deployable provenance categories")

    def human_model(self) -> StateResidualHumanModel:
        return StateResidualHumanModel(
            self.geometry,
            self.beta.copy(),
            HUMAN,
            residual_weights_nm=self.state_residual_weights_nm.copy(),
            residual_limit_nm=float(self.residual_limit_nm),
        )

    def value_state_record(self) -> dict[str, Any]:
        """Learning-ready state/belief payload with no hidden/evaluation fields."""

        return {
            "schema": "adaptive_human_belief_v22",
            "sequence": self.sequence,
            "beta": self.beta.tolist(),
            "state_residual_weights_nm": self.state_residual_weights_nm.tolist(),
            "residual_limit_nm": self.residual_limit_nm,
            "effective_geometry": {
                "origin_world_m": np.asarray(self.geometry.origin_world_m).tolist(),
                "plane_x_world": np.asarray(self.geometry.plane_x_world).tolist(),
                "joint_axis_world": np.asarray(
                    self.geometry.joint_axis_world
                ).tolist(),
                "plane_z_world": np.asarray(self.geometry.plane_z_world).tolist(),
                "hip_plane_m": np.asarray(self.geometry.hip_plane_m).tolist(),
                "thigh_length_m": float(self.geometry.thigh_length_m),
                "knee_to_cuff_in_cuff_m": np.asarray(
                    self.geometry.knee_to_cuff_in_cuff_m
                ).tolist(),
            },
            "geometry_source": self.geometry_source,
            "dynamics_source": self.dynamics_source,
            "residual_source": self.residual_source,
            "dynamics_sample_count": self.dynamics_sample_count,
            "accepted_beta_update_count": self.accepted_beta_update_count,
            "residual_update_count": self.residual_update_count,
            "deployable_truth_consumed": False,
        }


class StateResidualBeliefUpdaterV22:
    """Causal adapter around the frozen V2.2 beta and normalized-LMS updates."""

    def __init__(
        self,
        geometry: PlanarCuffGeometry,
        *,
        initial_beta: Sequence[float] | None = None,
        residual_alpha: float = 0.20,
        residual_limit_nm: float = 12.0,
    ) -> None:
        self.geometry = geometry
        self.dynamics = OnlineEffectiveDynamicsIdentifier()
        if initial_beta is not None:
            self.dynamics.beta = _finite_array("initial_beta", initial_beta, (11,))
        self.residual_alpha = float(residual_alpha)
        self.residual_limit_nm = float(residual_limit_nm)
        if not 0.0 < self.residual_alpha <= 1.0:
            raise ValueError("residual_alpha must lie in (0, 1]")
        if not math.isfinite(self.residual_limit_nm) or self.residual_limit_nm <= 0.0:
            raise ValueError("residual_limit_nm must be finite and positive")
        self.weights_nm = np.zeros((2, 5))
        self.sequence = 0
        self.residual_update_count = 0
        self.excluded_soft_limit_sample_count = 0
        self.coefficient_projection_count = 0
        self.observed_output_cap_count = 0

    @classmethod
    def from_accepted_geometry_fit(
        cls, fit: EffectiveGeometryFit, **kwargs: Any
    ) -> "StateResidualBeliefUpdaterV22":
        return cls(build_planar_geometry(fit), **kwargs)

    def observe_dynamics(
        self,
        *,
        q_rad: Sequence[float],
        dq_rad_s: Sequence[float],
        ddq_rad_s2: Sequence[float],
        applied_generalized_torque_nm: Sequence[float],
    ) -> dict[str, Any]:
        q = _finite_array("q_rad", q_rad, (2,))
        dq = _finite_array("dq_rad_s", dq_rad_s, (2,))
        ddq = _finite_array("ddq_rad_s2", ddq_rad_s2, (2,))
        torque = _finite_array(
            "applied_generalized_torque_nm", applied_generalized_torque_nm, (2,)
        )
        if np.linalg.norm(soft_limit_torque(q, dq, HUMAN)) > 1.0e-8:
            self.excluded_soft_limit_sample_count += 1
            return {
                "accepted_for_belief": False,
                "reason": "nonlinear_soft_limit_layer_not_in_base_regressor",
            }
        beta_diagnostics = self.dynamics.observe(q, dq, ddq, torque)
        residual_sample = torque - dynamic_regressor_row(q, dq, ddq) @ self.dynamics.beta
        self.weights_nm, projection, output_cap = _update_state_residual_weights(
            self.weights_nm,
            np.concatenate([q, dq]),
            residual_sample,
            self.residual_alpha,
            self.residual_limit_nm,
        )
        self.sequence += 1
        self.residual_update_count += 1
        self.coefficient_projection_count += int(projection)
        self.observed_output_cap_count += int(output_cap)
        return {
            "accepted_for_belief": True,
            "sequence": self.sequence,
            "beta_update": dict(beta_diagnostics),
            "residual_sample_nm": residual_sample.tolist(),
            "coefficient_projection_hit": projection,
            "observed_output_cap_hit": output_cap,
        }

    def snapshot(self) -> AdaptiveHumanBeliefV22:
        return AdaptiveHumanBeliefV22(
            geometry=self.geometry,
            beta=self.dynamics.beta.copy(),
            state_residual_weights_nm=self.weights_nm.copy(),
            sequence=self.sequence,
            dynamics_sample_count=len(self.dynamics.rows),
            accepted_beta_update_count=self.dynamics.accepted_updates,
            residual_update_count=self.residual_update_count,
            residual_limit_nm=self.residual_limit_nm,
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": PHASE3_HUMAN_WAYPOINT_VERSION,
            "observation_inputs": [
                "q_hat_rad",
                "dq_hat_rad_s",
                "ddq_hat_rad_s2",
                "applied_generalized_torque_nm",
            ],
            "hidden_oracle_inputs": [],
            "frozen_state_residual_alpha": self.residual_alpha,
            "frozen_residual_limit_nm": self.residual_limit_nm,
            "sequence": self.sequence,
            "residual_update_count": self.residual_update_count,
            "excluded_soft_limit_sample_count": self.excluded_soft_limit_sample_count,
            "coefficient_projection_count": self.coefficient_projection_count,
            "observed_output_cap_count": self.observed_output_cap_count,
        }


@dataclass(frozen=True)
class AdaptiveMechanicsScreenV22:
    force_limit_n: float = 200.0
    moment_limit_nm: float = 60.0
    sample_count: int = 21

    def __post_init__(self) -> None:
        if not math.isfinite(self.force_limit_n) or self.force_limit_n <= 0.0:
            raise ValueError("force_limit_n must be finite and positive")
        if not math.isfinite(self.moment_limit_nm) or self.moment_limit_nm <= 0.0:
            raise ValueError("moment_limit_nm must be finite and positive")
        if self.sample_count < 3:
            raise ValueError("sample_count must be at least three")

    def evaluate(
        self,
        belief: AdaptiveHumanBeliefV22,
        candidate: HumanWaypointCandidate,
        schedule: QuinticHumanWaypointSchedule,
    ) -> dict[str, Any]:
        model = belief.human_model()
        peak_force = 0.0
        peak_moment = 0.0
        peak_residual = 0.0
        finite = True
        for elapsed in np.linspace(0.0, schedule.duration_s, self.sample_count):
            sample = schedule.sample(float(elapsed))
            action = model.inverse_dynamics(
                sample.q_rad, sample.dq_rad_s, sample.ddq_rad_s2
            )
            allocation = model.allocate_generalized_action(action, sample.q_rad)
            force = float(np.linalg.norm(allocation["force_world_n"]))
            moment = float(np.linalg.norm(np.asarray(allocation["wrench_world"])[3:]))
            residual = float(
                np.max(
                    np.abs(
                        model.state_residual_nm(
                            np.concatenate([sample.q_rad, sample.dq_rad_s])
                        )
                    )
                )
            )
            finite &= bool(np.all(np.isfinite(action)) and np.isfinite(force + moment))
            peak_force = max(peak_force, force)
            peak_moment = max(peak_moment, moment)
            peak_residual = max(peak_residual, residual)
        feasible = bool(
            finite
            and peak_force <= self.force_limit_n + 1.0e-9
            and peak_moment <= self.moment_limit_nm + 1.0e-9
        )
        return {
            "evaluated": True,
            "feasible": feasible,
            "rejection_reason": None if feasible else "adaptive_model_mechanics_limit",
            "belief_sequence": belief.sequence,
            "candidate_label": candidate.label,
            "model": "frozen_v2_2_state_residual_human_model",
            "sample_count": self.sample_count,
            "peak_force_n": peak_force,
            "peak_moment_nm": peak_moment,
            "peak_state_residual_nm": peak_residual,
            "force_limit_n": self.force_limit_n,
            "moment_limit_nm": self.moment_limit_nm,
            "deployable_truth_consumed": False,
        }


class AdaptiveHumanWaypointHWMPCV22:
    """Use the recovered belief in scheduling and deterministic mechanics screens."""

    def __init__(
        self,
        planner: HumanWaypointFeedbackMPCV1,
        mechanics_screen: AdaptiveMechanicsScreenV22 | None = None,
    ) -> None:
        self.planner = planner
        self.mechanics_screen = mechanics_screen or AdaptiveMechanicsScreenV22()
        self.belief_sequences_used: list[int] = []

    def decide(
        self,
        *,
        belief: AdaptiveHumanBeliefV22,
        current_deployable_state: Sequence[float],
        current_reference_state: Sequence[float],
        phase: TaskPhase,
        phase_elapsed_s: float,
        phase_remaining_s: float,
        exploration_rank: int = 0,
        value_evaluator: Callable[[Any, HumanWaypointCandidate], float] | None = None,
    ) -> HumanWaypointFeedbackDecisionV1:
        model = belief.human_model()
        self.planner.scheduler.human_model = model
        deployable_state = _finite_array(
            "current_deployable_state", current_deployable_state, (4,)
        )
        reference_state = _finite_array(
            "current_reference_state", current_reference_state, (4,)
        )
        value_context = belief.value_state_record()
        value_context.update(
            {
                "current_deployable_state_rad_rad_s": deployable_state.tolist(),
                "current_reference_state_rad_rad_s": reference_state.tolist(),
                "phase": phase.value,
            }
        )

        def screen(
            candidate: HumanWaypointCandidate,
            schedule: QuinticHumanWaypointSchedule,
        ) -> dict[str, Any]:
            return self.mechanics_screen.evaluate(belief, candidate, schedule)

        decision = self.planner.decide(
            current_deployable_state=deployable_state,
            current_reference_state=reference_state,
            phase=phase,
            phase_elapsed_s=phase_elapsed_s,
            phase_remaining_s=phase_remaining_s,
            exploration_rank=exploration_rank,
            execution_feasibility_checker=screen,
            value_state_or_belief=value_context,
            candidate_value_evaluator=value_evaluator,
        )
        self.belief_sequences_used.append(belief.sequence)
        return decision

    def record(self) -> dict[str, Any]:
        return {
            "version": PHASE3_HUMAN_WAYPOINT_VERSION,
            "pipeline": [
                "fresh_deployable_state_and_history",
                "frozen_v2_2_adaptive_belief",
                "state_feedback_human_waypoint_candidates",
                "adaptive_model_mechanics_screen",
                "deterministic_cost_plus_optional_value_hook",
                "smooth_reference_execution",
                "fresh_feedback_and_replan",
            ],
            "belief_sequences_used": list(self.belief_sequences_used),
            "fixed_r_or_path_template_used": False,
            "old_robot_interface_predictor_used": False,
            "adaptive_model_use": (
                "candidate inverse dynamics and generalized-wrench mechanics screen"
            ),
            "scheduler_human_model_use": "registered Human ROM bounds only",
            "scheduler_clearance_geometry_source": "STRUCTURAL_PRIOR_STAGE5_GEOMETRY",
            "scheduler_clearance_geometry_adaptive": False,
            "value_hook_signature": "V(state_or_belief, candidate_next_waypoint)",
            "value_hook_default": 0.0,
            "value_or_rl_training_performed": False,
            "planner": self.planner.record(),
        }


@dataclass(frozen=True)
class Phase3ControlStepV22:
    task_state: GoalTaskState
    decision: HumanWaypointFeedbackDecisionV1 | None
    phase_changed: bool


class EventDrivenAdaptiveHWMPCV22:
    """Production-shape event-driven task/HWMPC interface.

    State events own phase transitions.  Time is used only for dwell duration,
    planning cadence supplied by the caller, and timeout protection.
    """

    def __init__(self, spec: GoalTaskSpec, planner: AdaptiveHumanWaypointHWMPCV22):
        self.spec = spec
        self.planner = planner
        self.task_state: GoalTaskState | None = None
        self.transition_log: list[dict[str, Any]] = []
        self.learning_records: list[dict[str, Any]] = []
        self.pending_learning_record: dict[str, Any] | None = None

    def start(
        self, q_rad: Sequence[float], dq_rad_s: Sequence[float]
    ) -> GoalTaskState:
        self.task_state = start_episode(
            self.spec,
            q_rad,
            dq_rad_s,
            acceleration_authority_valid=False,
        )
        self.transition_log = [
            {"from": None, "to": TaskPhase.OUTBOUND.value, "trigger": "settled_start"}
        ]
        self.learning_records = []
        self.pending_learning_record = None
        return self.task_state

    def _finalize_pending_learning_record(
        self,
        *,
        next_deployable_state: np.ndarray,
        next_reference_state: np.ndarray,
        next_task_state: GoalTaskState,
    ) -> None:
        if self.pending_learning_record is None:
            return
        finalized = dict(self.pending_learning_record)
        finalized.update(
            {
                "status": "FINALIZED",
                "next_observation": {
                    "deployable_state_rad_rad_s": next_deployable_state.tolist(),
                    "reference_state_rad_rad_s": next_reference_state.tolist(),
                    "task_phase": next_task_state.phase.value,
                    "phase_elapsed_s": next_task_state.phase_elapsed_s,
                    "hold_elapsed_s": next_task_state.hold_elapsed_s,
                },
                "completion": {
                    "task_complete": next_task_state.phase is TaskPhase.COMPLETE,
                    "task_aborted": next_task_state.phase is TaskPhase.ABORTED,
                    "phase_changed": (
                        next_task_state.phase.value
                        != self.pending_learning_record["observation"]["task_phase"]
                    ),
                    "abort_reason": next_task_state.abort_reason,
                },
            }
        )
        self.learning_records.append(finalized)
        self.pending_learning_record = None

    def _start_pending_learning_record(
        self,
        *,
        belief: AdaptiveHumanBeliefV22,
        deployable_state: np.ndarray,
        reference_state: np.ndarray,
        decision: HumanWaypointFeedbackDecisionV1,
    ) -> None:
        if self.pending_learning_record is not None:
            raise RuntimeError("previous learning transition has not been finalized")
        executed = decision.executed
        self.pending_learning_record = {
            "schema": "phase3_human_waypoint_transition_v1",
            "status": "PENDING_NEXT_OBSERVATION",
            "transition_index": len(self.learning_records),
            "observation": {
                "deployable_state_rad_rad_s": deployable_state.tolist(),
                "reference_state_rad_rad_s": reference_state.tolist(),
                "task_phase": decision.phase.value,
                "phase_elapsed_s": decision.phase_elapsed_s,
            },
            "adaptive_state": belief.value_state_record(),
            "candidates": [evaluation.record() for evaluation in decision.evaluations],
            "selected_waypoint": {
                "greedy_label": decision.greedy.label,
                "target_q_rad": decision.greedy.target_q_rad.tolist(),
            },
            "executed_waypoint": {
                "label": executed.label,
                "delta_q_rad": executed.proposed_delta_q_rad.tolist(),
                "target_q_rad": executed.target_q_rad.tolist(),
                "selection_mode": decision.selection_mode,
                "exploration_rank": decision.exploration_rank,
            },
            "local_cost": {
                "total": executed.total_cost,
                "terms": dict(executed.cost_terms),
            },
            "provenance": {
                "phase3_version": PHASE3_HUMAN_WAYPOINT_VERSION,
                "belief_schema": "adaptive_human_belief_v22",
                "belief_sequence": belief.sequence,
                "adaptive_model": "frozen_v2_2_state_residual_human_model",
                "candidate_generation": "direct_delta_q_lattice_from_fresh_deployable_state",
                "mechanics_screen": "adaptive_model_deterministic_schedule_screen_v1",
                "value_hook_configured": decision.value_hook_configured,
                "deployable_truth_consumed": False,
                "value_or_rl_training_performed": False,
            },
        }

    def observe_and_plan(
        self,
        *,
        belief: AdaptiveHumanBeliefV22,
        current_deployable_state: Sequence[float],
        current_reference_state: Sequence[float],
        dt_s: float,
        exploration_rank: int = 0,
        value_evaluator: Callable[[Any, HumanWaypointCandidate], float] | None = None,
    ) -> Phase3ControlStepV22:
        if self.task_state is None:
            raise ValueError("event-driven task must be started from the settled start set")
        state = _finite_array(
            "current_deployable_state", current_deployable_state, (4,)
        )
        reference_state = _finite_array(
            "current_reference_state", current_reference_state, (4,)
        )
        previous = self.task_state
        updated = transition_phase(
            self.spec,
            previous,
            state[:2],
            state[2:],
            dt_s,
            acceleration_authority_valid=False,
        )
        phase_changed = updated.phase is not previous.phase
        if phase_changed:
            self.transition_log.append(
                {
                    "from": previous.phase.value,
                    "to": updated.phase.value,
                    "trigger": (
                        "actual_arrival_and_settling"
                        if previous.phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN)
                        else "continuous_valid_hold_dwell"
                    ),
                }
            )
            self.planner.planner.reset_phase()
        self.task_state = updated
        self._finalize_pending_learning_record(
            next_deployable_state=state,
            next_reference_state=reference_state,
            next_task_state=updated,
        )
        if updated.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
            return Phase3ControlStepV22(updated, None, phase_changed)
        remaining = self.spec.phase_timeout_s - updated.phase_elapsed_s
        if remaining <= 0.0:  # transition_phase should already have aborted.
            raise RuntimeError("active phase has no remaining timeout budget")
        decision = self.planner.decide(
            belief=belief,
            current_deployable_state=state,
            current_reference_state=reference_state,
            phase=updated.phase,
            phase_elapsed_s=updated.phase_elapsed_s,
            phase_remaining_s=remaining,
            exploration_rank=exploration_rank,
            value_evaluator=value_evaluator,
        )
        self._start_pending_learning_record(
            belief=belief,
            deployable_state=state,
            reference_state=reference_state,
            decision=decision,
        )
        return Phase3ControlStepV22(updated, decision, phase_changed)

    def record(self) -> dict[str, Any]:
        return {
            "version": PHASE3_HUMAN_WAYPOINT_VERSION,
            "phase_transition_owner": "deployable_state_events",
            "hold_begins": "actual_outbound_arrival_and_settling",
            "return_ends": "actual_start_return_arrival_and_settling",
            "time_roles": [
                "reference_duration",
                "update_cadence",
                "continuous_hold_dwell",
                "runtime_measurement",
                "timeout_protection",
            ],
            "absolute_matched_pacing_phase_switches_used": False,
            "task_acceleration_completion_authority": "not_available_at_interface",
            "transition_log": list(self.transition_log),
            "learning_record_contract": [
                "observation",
                "adaptive_state",
                "candidates",
                "selected_waypoint",
                "executed_waypoint",
                "next_observation",
                "local_cost",
                "completion",
                "provenance",
            ],
            "learning_records": list(self.learning_records),
            "pending_learning_record": self.pending_learning_record,
            "planner": self.planner.record(),
        }


__all__ = [
    "PHASE3_HUMAN_WAYPOINT_VERSION",
    "AdaptiveHumanBeliefV22",
    "AdaptiveHumanWaypointHWMPCV22",
    "AdaptiveMechanicsScreenV22",
    "EventDrivenAdaptiveHWMPCV22",
    "Phase3ControlStepV22",
    "StateResidualBeliefUpdaterV22",
]
