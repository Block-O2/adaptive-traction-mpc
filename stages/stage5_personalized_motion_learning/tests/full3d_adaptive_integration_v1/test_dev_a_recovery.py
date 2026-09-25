"""DEV-A startup/lifecycle semantics, without changing registered task gates."""

import numpy as np
import pytest

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage5.full3d_adaptive_integration_v1.dev_a_recovery import RobotCuffPoseBridge
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import nominal_control_model
from traction_mpc_stage5.human_waypoint_shadow import (
    HumanWaypointCandidate,
    HumanWaypointMPCShadowContractV1,
    WaypointExecutionContext,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def test_startup_support_does_not_inherit_outbound_progress_rule() -> None:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    contract = HumanWaypointMPCShadowContractV1(
        spec, nominal_control_model(), default_engineering_cuff_allocator()
    )
    behind_start = np.radians([3.5, 8.5])
    common = dict(
        label="same_physical_support",
        phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=behind_start,
        dq_waypoint_rad_s=np.zeros(2),
    )
    with pytest.raises(ValueError, match="away from the registered phase goal"):
        contract.prepare(HumanWaypointCandidate(**common))
    mapped = contract.prepare(HumanWaypointCandidate(
        **common, execution_context=WaypointExecutionContext.STARTUP_SUPPORT
    ))
    assert np.allclose(mapped.candidate.q_waypoint_rad, behind_start)


def test_non_task_context_keeps_physical_bounds() -> None:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    contract = HumanWaypointMPCShadowContractV1(
        spec, nominal_control_model(), default_engineering_cuff_allocator()
    )
    candidate = HumanWaypointCandidate(
        label="invalid_support", phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([-1.0, 8.0]), dq_waypoint_rad_s=np.zeros(2),
        execution_context=WaypointExecutionContext.STARTUP_SUPPORT,
    )
    with pytest.raises(ValueError, match="task q bounds"):
        contract.prepare(candidate)


def test_robot_pose_bridge_has_exact_pose_and_zero_twist_endpoints() -> None:
    old = RigidTransform(np.eye(3), np.array([0.7, 0.0, 0.1]))
    new = RigidTransform(np.eye(3), np.array([0.717, 0.0, 0.102]))
    bridge = RobotCuffPoseBridge(old, new, 1.5)
    endpoints = bridge.endpoint_jumps()
    assert max(endpoints.values()) < 1.0e-12
    halfway, linear, angular = bridge.sample(0.75)
    assert np.allclose(halfway.translation, 0.5 * (old.translation + new.translation))
    assert np.linalg.norm(linear) > 0.0
    assert np.allclose(angular, 0.0)
