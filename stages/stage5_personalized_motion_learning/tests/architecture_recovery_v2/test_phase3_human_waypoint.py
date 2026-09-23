from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row, nominal_base_parameters
from traction_mpc_stage5.architecture_recovery_v2.effective_model import (
    EffectiveGeometryFit,
    build_planar_geometry,
)
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    StateResidualHumanModel,
)
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import (
    AdaptiveHumanBeliefV22,
    AdaptiveHumanWaypointHWMPCV22,
    AdaptiveMechanicsScreenV22,
    EventDrivenAdaptiveHWMPCV22,
    StateResidualBeliefUpdaterV22,
)
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def _geometry():
    return build_planar_geometry(
        EffectiveGeometryFit(
            hip_xz_m=np.array([0.0, 0.062]),
            thigh_length_m=0.437,
            knee_to_cuff_m=0.288,
            residual_rms_m=0.0,
            maximum_residual_m=0.0,
            condition_number=1.0,
            sample_count=100,
            angular_span_rad=1.0,
            accepted=True,
            reason="accepted_test_fixture",
        )
    )


def _belief(sequence: int = 7, weight_scale: float = 0.0) -> AdaptiveHumanBeliefV22:
    weights = np.zeros((2, 5))
    weights[:, 0] = weight_scale
    return AdaptiveHumanBeliefV22(
        geometry=_geometry(),
        beta=nominal_base_parameters(),
        state_residual_weights_nm=weights,
        sequence=sequence,
        dynamics_sample_count=120,
        accepted_beta_update_count=4,
        residual_update_count=80,
    )


def _planner(belief: AdaptiveHumanBeliefV22) -> AdaptiveHumanWaypointHWMPCV22:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    scheduler = QuinticHumanWaypointSchedulerV1(spec, belief.human_model())
    return AdaptiveHumanWaypointHWMPCV22(
        HumanWaypointFeedbackMPCV1(spec, scheduler)
    )


def test_belief_updater_consumes_deployable_dynamics_and_builds_frozen_v22_model() -> None:
    updater = StateResidualBeliefUpdaterV22(_geometry())
    q = np.radians([20.0, 35.0])
    dq = np.zeros(2)
    ddq = np.radians([2.0, -3.0])
    residual = np.array([1.5, -0.75])
    torque = dynamic_regressor_row(q, dq, ddq) @ nominal_base_parameters() + residual

    result = updater.observe_dynamics(
        q_rad=q,
        dq_rad_s=dq,
        ddq_rad_s2=ddq,
        applied_generalized_torque_nm=torque,
    )
    belief = updater.snapshot()

    assert result["accepted_for_belief"]
    assert belief.sequence == 1
    assert belief.residual_update_count == 1
    assert np.linalg.norm(belief.state_residual_weights_nm) > 0.0
    assert isinstance(belief.human_model(), StateResidualHumanModel)
    belief_record = belief.value_state_record()
    geometry_record = belief_record["effective_geometry"]
    assert belief_record["deployable_truth_consumed"] is False
    assert not any("truth" in key for key in geometry_record)
    assert geometry_record["hip_plane_m"] == pytest.approx(
        belief.geometry.hip_plane_m
    )
    assert geometry_record["thigh_length_m"] == pytest.approx(
        belief.geometry.thigh_length_m
    )
    assert geometry_record["knee_to_cuff_in_cuff_m"] == pytest.approx(
        belief.geometry.knee_to_cuff_in_cuff_m
    )
    assert updater.record()["hidden_oracle_inputs"] == []


def test_adaptive_belief_drives_scheduler_and_candidate_mechanics_screen() -> None:
    belief = _belief(weight_scale=2.0)
    adaptive = _planner(belief)
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad)
    state = np.concatenate([start, np.zeros(2)])

    decision = adaptive.decide(
        belief=belief,
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=spec.phase_timeout_s,
    )

    assert isinstance(adaptive.planner.scheduler.human_model, StateResidualHumanModel)
    assert adaptive.belief_sequences_used == [belief.sequence]
    assert decision.executed.execution_screen["belief_sequence"] == belief.sequence
    assert decision.executed.execution_screen["peak_state_residual_nm"] > 0.0
    assert decision.executed.execution_screen["deployable_truth_consumed"] is False
    assert adaptive.record()["old_robot_interface_predictor_used"] is False
    assert adaptive.record()["fixed_r_or_path_template_used"] is False


def test_clean_value_hook_can_rank_feasible_waypoints_without_training() -> None:
    belief = _belief()
    adaptive = _planner(belief)
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad)
    state = np.concatenate([start, np.zeros(2)])
    seen: list[tuple[int, str]] = []

    def value(belief_record, candidate):
        assert len(belief_record["current_deployable_state_rad_rad_s"]) == 4
        assert belief_record["phase"] == "OUTBOUND"
        seen.append((belief_record["sequence"], candidate.label))
        return -10.0 if candidate.label.endswith("00") else 0.0

    decision = adaptive.decide(
        belief=belief,
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=spec.phase_timeout_s,
        value_evaluator=value,
    )
    record = adaptive.record()

    assert decision.greedy.label.endswith("00")
    assert seen and {sequence for sequence, _ in seen} == {belief.sequence}
    assert decision.value_hook_configured
    assert record["value_hook_signature"] == "V(state_or_belief, candidate_next_waypoint)"
    assert record["value_or_rl_training_performed"] is False
    assert record["planner"]["value_hook"]["nonzero_evaluation_count"] == 1


def test_value_hook_rejects_nonfinite_cost() -> None:
    belief = _belief()
    adaptive = _planner(belief)
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad)
    state = np.concatenate([start, np.zeros(2)])

    with pytest.raises(ValueError, match="finite scalar"):
        adaptive.decide(
            belief=belief,
            current_deployable_state=state,
            current_reference_state=state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.0,
            phase_remaining_s=spec.phase_timeout_s,
            value_evaluator=lambda _belief, _candidate: float("nan"),
        )


def test_event_driven_phase_transitions_follow_actual_arrival_hold_and_return() -> None:
    spec = replace(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        hold_duration_s=0.02,
        phase_timeout_s=5.0,
    )
    belief = _belief()
    scheduler = QuinticHumanWaypointSchedulerV1(spec, belief.human_model())
    adaptive = AdaptiveHumanWaypointHWMPCV22(
        HumanWaypointFeedbackMPCV1(spec, scheduler)
    )
    controller = EventDrivenAdaptiveHWMPCV22(spec, adaptive)
    start = np.asarray(spec.start_return_target_rad)
    goal = np.asarray(spec.outbound_goal_target_rad)
    start_state = np.concatenate([start, np.zeros(2)])
    goal_state = np.concatenate([goal, np.zeros(2)])
    controller.start(start, np.zeros(2))

    still_outbound = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=start_state,
        current_reference_state=start_state,
        dt_s=2.2,
    )
    assert still_outbound.task_state.phase is TaskPhase.OUTBOUND

    arrived = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.005,
    )
    assert arrived.task_state.phase is TaskPhase.HOLD

    controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.01,
    )
    returning = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.01,
    )
    assert returning.task_state.phase is TaskPhase.RETURN

    completed = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=start_state,
        current_reference_state=start_state,
        dt_s=0.005,
    )
    assert completed.task_state.phase is TaskPhase.COMPLETE
    assert completed.decision is None
    record = controller.record()
    assert record["absolute_matched_pacing_phase_switches_used"] is False
    assert [row["to"] for row in record["transition_log"]] == [
        "OUTBOUND",
        "HOLD",
        "RETURN",
        "COMPLETE",
    ]
    assert record["pending_learning_record"] is None
    assert len(record["learning_records"]) == 4
    required = set(record["learning_record_contract"])
    for transition in record["learning_records"]:
        assert required <= set(transition)
        assert transition["status"] == "FINALIZED"
        assert transition["provenance"]["deployable_truth_consumed"] is False
        assert transition["provenance"]["value_or_rl_training_performed"] is False
        assert transition["local_cost"]["total"] is not None
    assert record["learning_records"][-1]["completion"]["task_complete"]
    assert record["learning_records"][-1]["next_observation"]["task_phase"] == "COMPLETE"


def test_hold_dwell_resets_after_one_invalid_state_sample() -> None:
    spec = replace(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        hold_duration_s=0.02,
        phase_timeout_s=5.0,
    )
    belief = _belief()
    controller = EventDrivenAdaptiveHWMPCV22(spec, _planner(belief))
    start = np.asarray(spec.start_return_target_rad)
    goal = np.asarray(spec.outbound_goal_target_rad)
    start_state = np.concatenate([start, np.zeros(2)])
    goal_state = np.concatenate([goal, np.zeros(2)])
    controller.start(start, np.zeros(2))
    controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.005,
    )
    first_dwell = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.01,
    )
    assert first_dwell.task_state.hold_elapsed_s == pytest.approx(0.01)
    invalid = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=start_state,
        current_reference_state=goal_state,
        dt_s=0.005,
    )
    assert invalid.task_state.phase is TaskPhase.HOLD
    assert invalid.task_state.hold_elapsed_s == 0.0
    restarted = controller.observe_and_plan(
        belief=belief,
        current_deployable_state=goal_state,
        current_reference_state=goal_state,
        dt_s=0.01,
    )
    assert restarted.task_state.phase is TaskPhase.HOLD
    assert restarted.task_state.hold_elapsed_s == pytest.approx(0.01)


def test_adaptive_mechanics_rejection_changes_selected_waypoint() -> None:
    belief = _belief(weight_scale=0.2)
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad)
    state = np.concatenate([start, np.zeros(2)])
    permissive = _planner(belief)
    baseline = permissive.decide(
        belief=belief,
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=spec.phase_timeout_s,
    )
    evaluated = [
        item for item in baseline.evaluations if item.execution_screen.get("evaluated")
    ]
    force_by_label = {
        item.label: float(item.execution_screen["peak_force_n"]) for item in evaluated
    }
    greedy_force = force_by_label[baseline.greedy.label]
    minimum_force = min(force_by_label.values())
    assert minimum_force < greedy_force
    constrained = AdaptiveHumanWaypointHWMPCV22(
        HumanWaypointFeedbackMPCV1(
            spec, QuinticHumanWaypointSchedulerV1(spec, belief.human_model())
        ),
        AdaptiveMechanicsScreenV22(
            force_limit_n=0.5 * (minimum_force + greedy_force),
            moment_limit_nm=60.0,
        ),
    )
    screened = constrained.decide(
        belief=belief,
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=spec.phase_timeout_s,
    )

    rejected = [item for item in screened.evaluations if not item.feasible]
    assert any(
        item.rejection_reason == "adaptive_model_mechanics_limit" for item in rejected
    )
    assert screened.greedy.label != baseline.greedy.label
    assert screened.executed.execution_screen["feasible"] is True
