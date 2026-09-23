from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from export_stage5_hwmpc_state_feedback_dataset_v1 import export_dataset
from validate_stage5_hwmpc_state_triggered_terminal_v1 import _diagnostic_rows


def _scheduler() -> QuinticHumanWaypointSchedulerV1:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5CR12SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad))
    estimator = FixedStage5Estimator(
        truth.attachment_position_m,
        truth.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    return QuinticHumanWaypointSchedulerV1(spec, estimator.model)


def test_feedback_candidates_are_direct_two_joint_increments_not_fixed_r() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    planner = HumanWaypointFeedbackMPCV1(spec, scheduler)
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    span = np.asarray(spec.outbound_goal_target_rad, dtype=float) - start

    actions = planner.candidate_actions(start, TaskPhase.OUTBOUND)
    normalized = np.asarray(actions) / span

    assert len(actions) >= 6
    assert any(not np.isclose(row[0], row[1]) for row in normalized)
    assert planner.record()["fixed_r_or_path_template_used"] is False
    assert planner.record()["return_replays_outbound_path"] is False


def test_feedback_decision_uses_fresh_state_and_preserves_reference_boundary() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    state_a = np.concatenate([start, np.zeros(2)])
    state_b = state_a.copy()
    state_b[:2] += np.radians([0.3, 0.5])
    state_b[2:] = np.radians([0.4, 0.8])

    decision_a = HumanWaypointFeedbackMPCV1(spec, scheduler).decide(
        current_deployable_state=state_a,
        current_reference_state=state_a,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=1.5,
    )
    decision_b = HumanWaypointFeedbackMPCV1(spec, scheduler).decide(
        current_deployable_state=state_b,
        current_reference_state=state_a,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=1.5,
    )

    assert not np.allclose(
        decision_a.executed.target_q_rad,
        decision_b.executed.target_q_rad,
        atol=1.0e-12,
        rtol=0.0,
    )
    assert decision_b.executed.schedule is not None
    initial = decision_b.executed.schedule.sample(0.0)
    assert initial.q_rad.tolist() == pytest.approx(state_a[:2])
    assert initial.dq_rad_s.tolist() == pytest.approx(state_a[2:])


def test_feedback_planner_checks_entire_segment_and_remaining_time() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    state = np.concatenate([start, np.zeros(2)])
    planner = HumanWaypointFeedbackMPCV1(spec, scheduler)

    decision = planner.decide(
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=1.5,
    )
    schedule = decision.executed.schedule
    assert schedule is not None
    assert schedule.minimum_reference_shank_clearance_m >= 0.0
    assert np.all(
        schedule.maximum_causal_20ms_reference_acceleration_rad_s2
        <= np.asarray(spec.task_joint_acceleration_limit_rad_s2) + 1.0e-12
    )

    with pytest.raises(ValueError, match="no feasible candidate"):
        HumanWaypointFeedbackMPCV1(spec, scheduler).decide(
            current_deployable_state=state,
            current_reference_state=state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=1.499,
            phase_remaining_s=0.001,
        )


def test_bounded_exploration_only_changes_rank_within_feasible_set() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    state = np.concatenate([start, np.zeros(2)])
    planner = HumanWaypointFeedbackMPCV1(spec, scheduler)

    decision = planner.decide(
        current_deployable_state=state,
        current_reference_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=1.5,
        exploration_rank=2,
    )

    assert decision.executed.feasible
    assert decision.exploration_rank <= 2
    assert decision.selection_mode == "bounded_top_k_exploration"
    assert decision.greedy.total_cost <= decision.executed.total_cost
    assert planner.record()["force_or_value_objective_used"] is False


def test_learning_export_retains_failed_rollout_without_low_cost_success_label(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "transitions.jsonl"
    source.write_text(
        json.dumps(
            {
                "schema": "stage5_hwmpc_state_feedback_validation_v1",
                "episodes": [
                    {
                        "completed": False,
                        "interaction": {"integral_cuff_force_n_s": 1.5},
                        "metrics": {"termination_reason": None},
                        "controller": {
                            "boundary_checks": [
                                {
                                    "phase": "OUTBOUND",
                                    "inside_existing_completion_criteria": False,
                                }
                            ],
                            "learning_records": [
                                {"phase": "OUTBOUND", "next_observation_rad_rad_s": [0, 0, 0, 0]}
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = export_dataset(source, output)
    row = json.loads(output.read_text(encoding="utf-8"))

    assert summary["failure_rows_retained"]
    assert not row["rollout_completed"]
    assert not row["cost_eligible_as_completed_success"]
    assert row["rollout_rejection_or_stop_reason"].startswith(
        "TERMINAL_COMPLETION_CRITERION_FAILED"
    )


def test_terminal_closeout_freezes_one_reserve_change_and_new_seeds() -> None:
    root = Path("stages/stage5_personalized_motion_learning/configs")
    base = json.loads((root / "stage5_hwmpc_state_feedback_v1.json").read_text())
    closeout = json.loads((root / "stage5_hwmpc_terminal_closeout_v1.json").read_text())

    before = base["matched_pacing"]
    after = closeout["matched_pacing"]
    assert closeout["diagnosis"]["classification"] == "TC-C"
    assert after["terminal_block_start_s"] == pytest.approx(1.4)
    assert after["terminal_transition_duration_s"] == pytest.approx(
        before["terminal_transition_duration_s"]
    )
    assert after["terminal_settle_duration_s"] == pytest.approx(0.4)
    assert (
        after["terminal_block_start_s"]
        + after["terminal_transition_duration_s"]
        + after["terminal_settle_duration_s"]
    ) == pytest.approx(after["outbound_duration_s"])
    assert closeout["action_contract"] == base["action_contract"]
    regression_seeds = {
        row["seed"] for row in closeout["bounded_test_budget"]["regression_episodes"]
    }
    fresh_seeds = {
        row["seed"]
        for row in closeout["bounded_test_budget"]["fresh_validation_episodes"]
    }
    assert len(fresh_seeds) == 5
    assert regression_seeds.isdisjoint(fresh_seeds)


def test_learning_export_marks_completed_unsafe_rollout_ineligible(
    tmp_path: Path,
) -> None:
    source = tmp_path / "closeout.json"
    output = tmp_path / "transitions.jsonl"
    source.write_text(
        json.dumps(
            {
                "schema": "stage5_hwmpc_terminal_closeout_validation_v1",
                "episodes": [
                    {
                        "completed": True,
                        "motion_and_execution_contract_passed": False,
                        "interaction": {"integral_cuff_force_n_s": 2.0},
                        "metrics": {"termination_reason": None},
                        "controller": {
                            "boundary_checks": [
                                {
                                    "phase": "RETURN",
                                    "inside_existing_completion_criteria": True,
                                }
                            ],
                            "learning_records": [
                                {"phase": "RETURN", "next_observation_rad_rad_s": [0, 0, 0, 0]}
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = export_dataset(source, output)
    row = json.loads(output.read_text(encoding="utf-8"))

    assert row["rollout_completed"]
    assert not row["rollout_motion_and_execution_contract_passed"]
    assert not row["cost_eligible_as_completed_success"]
    assert summary["ineligible_success_row_count"] == 1


def test_prechange_reference_trigger_separability_matches_retained_evidence() -> None:
    path = Path(
        "stages/stage5_personalized_motion_learning/results/engineering_validation/"
        "hwmpc_terminal_closeout_v1_attempt_01/terminal_closeout_validation.json"
    )
    source = json.loads(path.read_text(encoding="utf-8"))
    rows = _diagnostic_rows(source)
    by_key = {(row["episode"], row["phase"]): row for row in rows}

    assert by_key[("explore_seed_101", "OUTBOUND")][
        "active_reference_segment_complete"
    ]
    assert by_key[("explore_seed_101", "RETURN")][
        "active_reference_segment_complete"
    ]
    assert not by_key[("explore_seed_307", "RETURN")][
        "active_reference_segment_complete"
    ]
    assert by_key[("fresh_explore_seed_607", "RETURN")][
        "active_reference_segment_complete"
    ]
    assert by_key[("fresh_explore_seed_607", "RETURN")][
        "fixed_1p4_handoff_contact"
    ]
    assert not by_key[("fresh_explore_seed_811", "RETURN")][
        "active_reference_segment_complete"
    ]


def test_state_trigger_config_keeps_original_fallback_and_fresh_budget_conditional() -> None:
    path = Path(
        "stages/stage5_personalized_motion_learning/configs/"
        "stage5_hwmpc_state_triggered_terminal_v1.json"
    )
    config = json.loads(path.read_text(encoding="utf-8"))
    rule = config["single_rule"]
    budget = config["bounded_test_budget"]

    assert rule["early_eligibility_start_s"] == pytest.approx(1.4)
    assert rule["fallback_handoff_s"] == pytest.approx(1.5)
    assert config["matched_pacing"]["terminal_block_start_s"] == pytest.approx(1.5)
    assert budget["fresh_runs_only_if_retained_classification_is_ST_A"]
    assert len(budget["conditional_fresh_validation_episodes"]) == 5
