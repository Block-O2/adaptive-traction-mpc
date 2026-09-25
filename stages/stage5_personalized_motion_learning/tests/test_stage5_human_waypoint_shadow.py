from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_shadow import (
    CausalScheduledReferenceMotionHistory,
    HumanWaypointCandidate,
    HumanWaypointMPCShadowContractV1,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def _contract() -> HumanWaypointMPCShadowContractV1:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5CR12SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad))
    estimator = FixedStage5Estimator(
        truth.attachment_position_m,
        truth.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    return HumanWaypointMPCShadowContractV1(
        spec, estimator.model, default_engineering_cuff_allocator()
    )


def test_waypoint_mapping_is_deterministic_and_uses_registered_geometry() -> None:
    contract = _contract()
    spec = contract.spec
    candidate = HumanWaypointCandidate(
        label="balanced_outbound",
        phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([6.0, 11.5]),
        dq_waypoint_rad_s=np.zeros(2),
    )

    first = contract.prepare(candidate)
    second = contract.prepare(candidate)
    expected = contract.human_model.geometry.cuff_pose(candidate.q_waypoint_rad)

    assert np.array_equal(
        first.reference.world_from_cuff.translation,
        second.reference.world_from_cuff.translation,
    )
    assert np.allclose(first.human_cuff_position_world_m, expected.translation)
    assert np.allclose(first.human_cuff_rotation_world, expected.rotation)
    assert first.execution_target.q_rad.tolist() == pytest.approx(
        candidate.q_waypoint_rad.tolist()
    )
    assert contract.contract_record()[
        "short_horizon_robot_interface_predictor_used"
    ] is False


def test_waypoint_contract_rejects_wrong_phase_goal() -> None:
    contract = _contract()
    spec = contract.spec
    candidate = HumanWaypointCandidate(
        label="wrong_goal",
        phase=TaskPhase.RETURN,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([6.0, 11.0]),
        dq_waypoint_rad_s=np.zeros(2),
    )

    with pytest.raises(ValueError, match="phase goal"):
        contract.prepare(candidate)


def test_waypoint_contract_rejects_out_of_envelope_velocity() -> None:
    contract = _contract()
    spec = contract.spec
    limit = np.asarray(spec.task_joint_velocity_limit_rad_s)
    candidate = HumanWaypointCandidate(
        label="too_fast",
        phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([6.0, 11.0]),
        dq_waypoint_rad_s=np.asarray([limit[0] * 1.01, 0.0]),
    )

    with pytest.raises(ValueError, match="velocity"):
        contract.prepare(candidate)


def test_return_phase_allows_origin_hold_inside_existing_completion_tolerance() -> None:
    contract = _contract()
    spec = contract.spec
    candidate = HumanWaypointCandidate(
        label="return_transition_hold",
        phase=TaskPhase.RETURN,
        phase_goal_rad=np.asarray(spec.start_return_target_rad),
        q_waypoint_rad=np.radians([19.99, 35.02]),
        dq_waypoint_rad_s=np.zeros(2),
    )

    mapped = contract.prepare(candidate)
    assert mapped.candidate.q_waypoint_rad.tolist() == pytest.approx(
        candidate.q_waypoint_rad
    )


def test_return_phase_still_rejects_motion_away_beyond_existing_tolerance() -> None:
    contract = _contract()
    spec = contract.spec
    candidate = HumanWaypointCandidate(
        label="return_moves_away",
        phase=TaskPhase.RETURN,
        phase_goal_rad=np.asarray(spec.start_return_target_rad),
        q_waypoint_rad=np.radians([20.0, 36.5]),
        dq_waypoint_rad_s=np.zeros(2),
    )

    with pytest.raises(ValueError, match="moves away"):
        contract.prepare(candidate)


def test_shared_reference_motion_history_requires_full_contiguous_20ms() -> None:
    history = CausalScheduledReferenceMotionHistory(sample_period_s=0.005)
    q_reference = np.radians([5.0, 10.0])
    for timestamp_s, dq_deg_s in (
        (0.000, (0.0, 0.0)),
        (0.005, (0.5, 1.0)),
        (0.010, (1.0, 2.0)),
        (0.015, (1.5, 3.0)),
    ):
        history.commit(timestamp_s, q_reference, np.radians(dq_deg_s))

    status = history.status(0.020)
    assert status.valid
    assert status.contiguous
    assert status.coverage_s == pytest.approx(0.020)
    acceleration = history.acceleration_rad_s2(
        np.radians([2.0, 4.0]), status
    )
    assert np.degrees(acceleration).tolist() == pytest.approx([100.0, 200.0])


def test_shared_reference_motion_history_rejects_gap() -> None:
    history = CausalScheduledReferenceMotionHistory(sample_period_s=0.005)
    q_reference = np.radians([5.0, 10.0])
    for timestamp_s in (0.000, 0.005, 0.010):
        history.commit(timestamp_s, q_reference, np.zeros(2))

    status = history.status(0.020)
    assert not status.valid
    assert not status.contiguous
    with pytest.raises(ValueError, match="full causal"):
        history.acceleration_rad_s2(np.zeros(2), status)


def test_shared_reference_motion_history_allows_idempotent_same_timestamp() -> None:
    history = CausalScheduledReferenceMotionHistory(sample_period_s=0.005)
    q_reference = np.radians([5.0, 10.0])
    history.commit(0.0, q_reference, np.zeros(2))
    history.commit(0.0, q_reference, np.zeros(2))
    assert len(history.samples) == 1
    with pytest.raises(ValueError, match="duplicate"):
        history.commit(0.0, q_reference + 0.001, np.zeros(2))


def test_contract_records_pd_request_as_diagnostic_not_envelope_gate() -> None:
    record = _contract().contract_record()
    assert record["acceleration_rejection_semantics"] == (
        "causal_20ms_scheduled_reference_motion_with_full_history"
    )
    assert record["invalid_history_behavior"] == (
        "held_reference_only_otherwise_reject"
    )
    assert record["pd_acceleration_request_role"] == (
        "inverse_dynamics_execution_input_and_diagnostic_not_motion_envelope_gate"
    )
