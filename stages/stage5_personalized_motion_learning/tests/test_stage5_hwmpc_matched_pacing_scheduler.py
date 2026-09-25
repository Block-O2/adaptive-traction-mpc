import json

import numpy as np
import pytest

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase
from validate_stage5_hwmpc_matched_pacing_scheduler import audit_v1


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_hwmpc_matched_pacing_scheduler_v2.json"


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


def test_v2_config_freezes_one_common_terminal_block_without_scope_changes() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["status"] == "FROZEN_AFTER_V1_SCHEDULE_AUDIT_BEFORE_V2_EXECUTION"
    assert config["coordination"]["frozen_support_interval"] == [-0.24, 0.55]
    pacing = config["matched_pacing"]
    assert pacing["terminal_block_start_s"] == 1.5
    assert pacing["terminal_transition_duration_s"] == 0.4
    assert pacing["terminal_settle_duration_s"] == 0.3
    assert (
        pacing["terminal_block_start_s"]
        + pacing["terminal_transition_duration_s"]
        + pacing["terminal_settle_duration_s"]
        == pytest.approx(pacing["outbound_duration_s"])
    )
    assert all(value is False for value in config["scope"].values())


def test_v1_audit_recovers_terminal_completion_exit_and_nonidentical_targets() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload = json.loads(
        (STAGE5_ROOT.parents[1] / config["audit_source"]["artifact"])
        .read_text(encoding="utf-8")
    )
    audit = {row["coordination_r"]: row for row in audit_v1(payload)}

    assert audit[0.25]["phases"]["RETURN"]["entered_then_exited_completion_set"]
    assert audit[0.4]["phases"]["RETURN"]["entered_then_exited_completion_set"]
    assert not audit[0.25]["phases"]["RETURN"]["inside_at_fixed_boundary"]
    assert not audit[0.4]["phases"]["RETURN"]["inside_at_fixed_boundary"]
    assert any(
        row["phases"]["RETURN"]["exact_q_goal_zero_velocity_reference_onset_s"]
        is None
        for row in audit.values()
    )


def test_fixed_duration_reference_reaches_exact_boundary_state_with_existing_limits() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    goal = np.asarray(spec.start_return_target_rad)
    candidate = HumanWaypointCandidate(
        label="fixed_return_terminal",
        phase=TaskPhase.RETURN,
        phase_goal_rad=goal,
        q_waypoint_rad=goal,
        dq_waypoint_rad_s=np.zeros(2),
    )
    schedule = scheduler.plan_fixed_duration_reference_contract(
        current_q_hat_rad=np.radians([8.0, 15.0]),
        current_dq_hat_rad_s=np.radians([-8.0, -12.0]),
        candidate=candidate,
        duration_s=0.4,
        phase_elapsed_s=1.5,
    )
    endpoint = schedule.sample(0.4)

    assert endpoint.q_rad.tolist() == pytest.approx(goal)
    assert endpoint.dq_rad_s.tolist() == pytest.approx([0.0, 0.0], abs=1.0e-12)
    assert np.all(
        schedule.maximum_reference_velocity_rad_s
        <= np.asarray(spec.task_joint_velocity_limit_rad_s) + 1.0e-12
    )
    assert np.all(
        schedule.maximum_causal_20ms_reference_acceleration_rad_s2
        <= np.asarray(spec.task_joint_acceleration_limit_rad_s2) + 1.0e-12
    )
    assert schedule.minimum_reference_shank_clearance_m >= 0.0
