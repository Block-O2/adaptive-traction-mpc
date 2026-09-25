"""Focused DEV-D geometry/reference tests; no hidden physical case in control."""
from __future__ import annotations

import numpy as np
from dataclasses import replace
import pytest

from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import (
    CombinedRigidTableClearanceV1, RigidTableReferenceEnvelopeV1,
    choose_feedback_commissioning_target,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import (
    SessionClearanceContract, nominal_control_geometry, nominal_control_model,
)
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1, WaypointGeometryInfeasible,
    _quintic_coefficients,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from traction_mpc_stage5.task import TaskPhase
from traction_mpc_stage3.coupled import (
    BED_HEIGHT_M, SHANK_RADIUS_M, THIGH_RADIUS_M,
    SLEEVE_HALF_LENGTH_M, SLEEVE_OUTER_RADIUS_M,
)
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY


def test_old_commissioning_segment_is_rejected_without_hidden_geometry() -> None:
    envelope = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    start, unsafe = np.radians([[14.0, 19.0], [9.0, 27.0]])
    result = envelope.check_quintic(
        _quintic_coefficients(start, np.zeros(2), unsafe, np.zeros(2), 1.5), 1.5)
    assert not result["feasible"]
    assert result["minimum_sampled_m"]["distal_shank_m"] < -0.05
    assert result["minimum_sampled_m"]["sleeve_m"] < -0.03


def test_feedback_projection_preserves_knee_excursion_and_path_feasibility() -> None:
    envelope = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    previous, unsafe = np.radians([[14.0, 19.0], [9.0, 27.0]])
    output = choose_feedback_commissioning_target(
        envelope=envelope, reference_origin_q_rad=previous,
        estimated_current_q_rad=previous,
        prescribed_previous_q_rad=previous,
        prescribed_next_q_rad=unsafe, q_bounds_rad=spec.q_bounds_rad,
        velocity_limits_rad_s=spec.task_joint_velocity_limit_rad_s,
        acceleration_limits_rad_s2=spec.task_joint_acceleration_limit_rad_s2,
        duration_s=1.5, final_return=False)
    assert output["feasible"]
    assert output["target_q_rad"][0] > unsafe[0]
    assert np.isclose(output["target_q_rad"][1], unsafe[1])
    assert output["path"]["feasible"]
    assert any(not attempt["feasible"] for attempt in output["attempts"])


def test_causal_pose_anchor_and_existing_shank_limit_are_retained() -> None:
    original = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    q = np.radians([5.0, 10.0])
    point = original.cuff_centers(q)[0]
    anchored = original.anchored_to_observation(q, point + np.array([0.0, 0.0, 0.002]))
    assert np.isclose(anchored.cuff_centers(q)[0, 2], point[2] + 0.002)
    combined = CombinedRigidTableClearanceV1(SessionClearanceContract(anchored.geometry), anchored)
    assert combined.evaluate(q) <= SessionClearanceContract(anchored.geometry).evaluate(q)
    assert combined.record()["hidden_geometry_consumed"] is False


def test_direct_measured_sleeve_gap_uses_pose_not_estimated_q() -> None:
    envelope = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    rotation = np.eye(3)
    center = np.array([0.7, 0.0, 0.012 + 0.058 + 0.0001])
    assert np.isclose(envelope.measured_sleeve_gap(center, rotation), 0.0001)


def test_control_effective_fit_cannot_reinterpret_fixed_hip_installation() -> None:
    nominal = nominal_control_geometry()
    shifted = replace(nominal, origin_world_m=nominal.origin_world_m
                      + np.array([0.0, 0.0, -0.003]))
    envelope = RigidTableReferenceEnvelopeV1(shifted)
    q = np.radians([[5.0, 10.0], [14.0, 19.0]])
    assert np.allclose(envelope.margins(q)["proximal_thigh_m"], 0.0001)


def test_prior_supported_lift_does_not_worsen_conservative_shank_contact() -> None:
    envelope = RigidTableReferenceEnvelopeV1(
        nominal_control_geometry(), shank_length_upper_m=0.60)
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start, target = np.radians([[5.0, 10.0], [14.0, 19.0]])
    assert envelope.margins(start)["distal_shank_m"][0] < 0
    output = choose_feedback_commissioning_target(
        envelope=envelope, reference_origin_q_rad=start,
        estimated_current_q_rad=start,
        prescribed_previous_q_rad=start, prescribed_next_q_rad=target,
        q_bounds_rad=spec.q_bounds_rad,
        velocity_limits_rad_s=spec.task_joint_velocity_limit_rad_s,
        acceleration_limits_rad_s2=spec.task_joint_acceleration_limit_rad_s2,
        duration_s=1.5, final_return=False)
    assert output["feasible"]
    assert output["path"]["conservative_nonworsening_shank_escape"]


def test_vertical_only_margin_optimization_is_numerically_equivalent() -> None:
    """Compare against the previous full-3D vector construction, not a label."""
    envelope = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    q = np.radians(np.column_stack([
        np.linspace(0.0, 75.0, 257), np.linspace(2.0, 92.0, 257)]))
    for geometry in (envelope.geometry,
                     replace(envelope.geometry, origin_world_m=
                             envelope.geometry.origin_world_m + np.array([0.0, 0.0, -0.003]))):
        g = geometry
        phi = q[:, 0] - q[:, 1]
        hip = (g.origin_world_m[None, :] + g.hip_plane_m[0] * g.plane_x_world[None, :]
               + g.hip_plane_m[1] * g.plane_z_world[None, :])
        thigh_dir = (np.cos(q[:, 0, None]) * g.plane_x_world[None, :]
                      + np.sin(q[:, 0, None]) * g.plane_z_world[None, :])
        shank_dir = (np.cos(phi[:, None]) * g.plane_x_world[None, :]
                     + np.sin(phi[:, None]) * g.plane_z_world[None, :])
        knee = hip + g.thigh_length_m * thigh_dir
        ankle = knee + envelope.shank_length_upper_m * shank_dir
        cuff = knee + g.cuff_distance_m * shank_dir
        sleeve_a = cuff - SLEEVE_HALF_LENGTH_M * shank_dir
        sleeve_b = cuff + SLEEVE_HALF_LENGTH_M * shank_dir
        bar_a = cuff - STAGE5_GEOMETRY.cuff_bar_length_m / 2 * shank_dir
        bar_b = cuff + STAGE5_GEOMETRY.cuff_bar_length_m / 2 * shank_dir

        def cylinder(a: np.ndarray, b: np.ndarray, axis: np.ndarray, radius: float) -> np.ndarray:
            return (np.minimum(a[:, 2], b[:, 2])
                    - radius * np.sqrt(np.maximum(0.0, 1.0 - axis[:, 2] ** 2))
                    - BED_HEIGHT_M)

        cuff_frame_z = (-np.sin(phi[:, None]) * g.plane_x_world[None, :]
                        + np.cos(phi[:, None]) * g.plane_z_world[None, :])
        cuff_frame_y = np.cross(cuff_frame_z, shank_dir)
        axes = np.stack([shank_dir, cuff_frame_y, cuff_frame_z], axis=2)
        tool = STAGE5_GEOMETRY.end_effector_from_cuff
        t = np.asarray(tool.translation)
        e_to_c = np.einsum("nij,j->ni", axes @ np.asarray(tool.rotation).T, t)
        flange = cuff - e_to_c
        length = max(0.0, float(np.linalg.norm(t)) - SLEEVE_OUTER_RADIUS_M)
        connector = flange + length / np.linalg.norm(t) * e_to_c
        expected = {
            "proximal_thigh_m": np.full(len(q), 0.0001),
            "distal_shank_m": (np.minimum(knee[:, 2], ankle[:, 2])
                                - SHANK_RADIUS_M - BED_HEIGHT_M - 0.001),
            "sleeve_m": cylinder(sleeve_a, sleeve_b, shank_dir, SLEEVE_OUTER_RADIUS_M),
            "cuff_bar_m": cylinder(bar_a, bar_b, shank_dir,
                                   STAGE5_GEOMETRY.cuff_bar_radius_m),
            "cuff_adapter_m": cylinder(flange, connector,
                                        e_to_c / np.linalg.norm(t), 0.018),
        }
        obtained = replace(envelope, geometry=geometry).margins(q)
        assert set(obtained) == set(expected)
        for name in expected:
            assert np.allclose(obtained[name], expected[name], atol=1e-12, rtol=0), name


def test_strict_scheduler_rejects_negative_goal_floor_and_intercell_certificate() -> None:
    model = nominal_control_model()
    envelope = RigidTableReferenceEnvelopeV1(model.geometry)
    combined = CombinedRigidTableClearanceV1(SessionClearanceContract(model.geometry), envelope)
    scheduler = QuinticHumanWaypointSchedulerV1(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, model, reference_period_s=0.005,
        clearance_evaluator=combined, preserve_task_endpoint_clearance_floor=True,
        require_continuous_nonpenetrating_path=True)
    candidate = HumanWaypointCandidate(
        label="strict_floor", phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.radians([5.0, 13.0]),
        q_waypoint_rad=np.radians([7.0, 11.0]),
        dq_waypoint_rad_s=np.zeros(2))
    assert not scheduler._path_clearance_is_valid(np.asarray([-0.0001]), candidate)
    assert scheduler._path_clearance_is_valid(np.asarray([0.0001]), candidate)
    with pytest.raises(ValueError, match="continuous-clearance certificate"):
        QuinticHumanWaypointSchedulerV1(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK, model,
            clearance_evaluator=combined.evaluate,
            require_continuous_nonpenetrating_path=True)
    c = _quintic_coefficients(np.radians([7.0, 11.0]), np.zeros(2),
                              np.radians([8.0, 12.0]), np.zeros(2), 1.0)
    expected = min(envelope.check_quintic(c, 1.0)["conservative_continuous_lower_m"].values())
    assert np.isclose(combined.certified_minimum(c, 1.0), expected)


def test_strict_scheduler_uses_continuous_certificate_in_fixed_duration_path() -> None:
    class SamplePositiveButContinuousNegative:
        def __call__(self, q: np.ndarray) -> np.ndarray | float:
            rows = np.asarray(q)
            return 0.01 if rows.ndim == 1 else np.full(len(rows), 0.01)

        def certified_minimum(self, coefficients: np.ndarray, duration_s: float) -> float:
            return -0.001

    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec, nominal_control_model(), reference_period_s=0.005,
        clearance_evaluator=SamplePositiveButContinuousNegative(),
        require_continuous_nonpenetrating_path=True)
    candidate = HumanWaypointCandidate(
        label="intersample", phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([8.0, 12.0]), dq_waypoint_rad_s=np.zeros(2))
    with pytest.raises(WaypointGeometryInfeasible, match="continuous hard-table"):
        scheduler.plan_fixed_duration_reference_contract(
            current_q_hat_rad=np.radians([7.0, 11.0]),
            current_dq_hat_rad_s=np.zeros(2), candidate=candidate,
            duration_s=1.0, phase_elapsed_s=0.0)
