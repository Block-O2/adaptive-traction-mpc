from __future__ import annotations

from dataclasses import replace

import numpy as np

from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.cuff_allocator import (
    default_engineering_cuff_allocator,
)
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
)
from traction_mpc_stage4.measurement import (
    CausalMeasurementLayer,
    sensor_realism_cases,
)
from traction_mpc_stage4.mpc import HumanSpaceMPC, NO_SAFE_ACTION, SAFE_ACTION
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
    filter_executable_command,
    filter_executable_commands_batch,
    make_stage4_executable_force_filter,
    prepare_executable_force_filter_context,
)
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant
from traction_mpc_stage4.track_brake import BRAKE, TRACK, TrackBrakeSupervisor


def _model() -> BaseParameterHumanModel:
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([HUMAN.sleeve_center_m, 0.0]),
    )
    return BaseParameterHumanModel(
        geometry=geometry,
        beta=nominal_base_parameters(HUMAN),
    )


def _fixture():
    reference = teaching_reference(4.0)
    plant = SensorBoundaryStage4Plant(HUMAN)
    truth = plant.reset(reference.q_rad)
    measurement = CausalMeasurementLayer(sensor_realism_cases()[0], truth).current
    model = _model()
    state = model.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    allocator = default_engineering_cuff_allocator()
    return plant, measurement, model, state, reference, allocator


def _context(measurement=None):
    plant, original, model, state, reference, allocator = _fixture()
    selected_measurement = original if measurement is None else measurement
    return (
        plant,
        model,
        state,
        reference,
        allocator,
        prepare_executable_force_filter_context(
            plant=plant,
            measurement=selected_measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        ),
    )


def test_safe_nominal_command_is_bitwise_unchanged() -> None:
    plant, model, state, reference, allocator, context = _context()
    action = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    result = filter_executable_command(context, action)
    assert result.status == SAFE_UNCHANGED
    assert result.lambda_value == 0.0
    assert result.intervention_coordinate_norm == 0.0
    np.testing.assert_array_equal(
        result.filtered_sagittal_wrench,
        result.nominal_sagittal_wrench,
    )
    np.testing.assert_array_equal(
        result.filtered_preview.allocation["wrench_world"],
        result.nominal_preview.allocation["wrench_world"],
    )
    np.testing.assert_array_equal(
        result.filtered_preview.command.force_total_n,
        result.nominal_preview.command.force_total_n,
    )


def test_nullspace_filter_rescues_force_and_preserves_torque() -> None:
    plant, model, state, reference, allocator, context = _context()
    action = 2.0 * model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    result = filter_executable_command(context, action)
    assert result.status == SAFE_FILTERED
    assert result.nominal_preview.command.translational_force_norm_n > 200.0
    assert result.filtered_preview.command.translational_force_norm_n < 200.0
    np.testing.assert_allclose(
        context.allocation_matrix @ result.filtered_sagittal_wrench,
        action,
        rtol=0.0,
        atol=1.0e-9,
    )
    assert result.torque_exactly_preserved
    plant.apply_executable_command(result.filtered_preview.command)
    np.testing.assert_array_equal(
        plant.last_force,
        result.filtered_preview.command.force_total_n,
    )
    np.testing.assert_array_equal(
        plant.last_moment,
        result.filtered_preview.command.moment_total_nm,
    )


def test_filter_reports_genuinely_unrecoverable_command() -> None:
    plant, measurement, model, state, reference, allocator = _fixture()
    target_velocity, _ = model.geometry.cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    unrecoverable_measurement = replace(
        measurement,
        attachment_velocity_m_s=(
            target_velocity - np.array([0.0, 2.0, 0.0])
        ),
    )
    context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=unrecoverable_measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    action = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    result = filter_executable_command(context, action)
    assert result.status == FILTER_INFEASIBLE
    assert not result.feasible
    assert result.nominal_preview.command.translational_force_norm_n > 200.0
    assert result.filtered_preview.command.translational_force_norm_n > 200.0


def test_scalar_and_batch_filter_outputs_are_exactly_equivalent() -> None:
    _, model, state, reference, _, context = _context()
    base = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    actions = np.vstack([0.5 * base, base, 2.0 * base, 10.0 * base])
    batch = filter_executable_commands_batch(context, actions)
    for index, action in enumerate(actions):
        scalar = filter_executable_command(context, action)
        assert batch.statuses[index] == scalar.status
        assert batch.lambdas[index] == scalar.lambda_value
        np.testing.assert_array_equal(
            batch.command(index).force_total_n,
            scalar.filtered_preview.command.force_total_n,
        )
        np.testing.assert_array_equal(
            batch.command(index).joint_torque_command_nm,
            scalar.filtered_preview.command.joint_torque_command_nm,
        )


def test_nominal_safe_cem_winner_is_regression_identical() -> None:
    plant, measurement, model, state, reference, allocator = _fixture()
    original = HumanSpaceMPC(cuff_allocator=allocator)
    filtered = HumanSpaceMPC(cuff_allocator=allocator)
    original_action, original_diagnostics = original.solve(
        state,
        4.0,
        lambda _: reference,
        model,
        first_action_batch_preview=make_stage4_first_action_batch_preview(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        ),
    )
    filtered_action, filtered_diagnostics = filtered.solve(
        state,
        4.0,
        lambda _: reference,
        model,
        first_action_batch_preview=make_stage4_executable_force_filter(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        ),
    )
    np.testing.assert_array_equal(filtered_action, original_action)
    assert filtered_diagnostics["objective"] == original_diagnostics["objective"]
    np.testing.assert_array_equal(
        filtered_diagnostics["selected_executable_command"]["force_total_n"],
        original_diagnostics["selected_executable_command"]["force_total_n"],
    )
    assert filtered_diagnostics["selected_safety_filter"]["status"] == (
        SAFE_UNCHANGED
    )


def _measurement_with_null_direction_feedback():
    plant, measurement, model, state, reference, allocator = _fixture()
    original_context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    direction = original_context.world_null_wrench[:3]
    target = model.geometry.cuff_pose(reference.q_rad)
    target_velocity, target_angular_velocity = model.geometry.cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    shifted = replace(
        measurement,
        attachment_position_m=(
            target.translation + (199.9 / 3000.0) * direction
        ),
        attachment_rotation_matrix=target.rotation.copy(),
        attachment_velocity_m_s=target_velocity.copy(),
        attachment_angular_velocity_rad_s=target_angular_velocity.copy(),
    )
    return plant, shifted, model, state, reference, allocator


def test_cem_rescues_nominally_rejected_candidates_and_carries_winner() -> None:
    plant, measurement, model, state, reference, allocator = (
        _measurement_with_null_direction_feedback()
    )
    safety_filter = make_stage4_executable_force_filter(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    controller = HumanSpaceMPC(cuff_allocator=allocator)
    action, diagnostics = controller.solve(
        state,
        4.0,
        lambda _: reference,
        model,
        first_action_batch_preview=safety_filter,
    )
    assert action is not None
    assert diagnostics["status"] == SAFE_ACTION
    counts = diagnostics["first_action_filter_statuses_per_iteration"]
    assert any(item.get(SAFE_FILTERED, 0) > 0 for item in counts)
    selected = safety_filter.selected_result(action)
    assert selected.feasible
    assert selected.status == SAFE_FILTERED
    assert diagnostics["selected_safety_filter"]["status"] == selected.status
    np.testing.assert_array_equal(
        diagnostics["selected_executable_command"]["force_total_n"],
        selected.filtered_preview.command.force_total_n,
    )

    supervisor = TrackBrakeSupervisor()
    decision = supervisor.command(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        track_reference=reference,
        proposed_action_nm=action,
        mpc_status=SAFE_ACTION,
        proposed_filter_result=selected,
    )
    assert decision.mode == TRACK
    np.testing.assert_array_equal(
        decision.executable_preview.command.force_total_n,
        selected.filtered_preview.command.force_total_n,
    )
    plant.apply_executable_command(decision.executable_preview.command)
    np.testing.assert_array_equal(
        plant.last_force,
        selected.filtered_preview.command.force_total_n,
    )
    runtime_decision = supervisor.command(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        track_reference=reference,
        proposed_action_nm=action,
        mpc_status=None,
    )
    assert runtime_decision.mode == TRACK
    assert runtime_decision.safety_filter["status"] == SAFE_FILTERED
    np.testing.assert_array_equal(
        runtime_decision.executable_preview.command.force_total_n,
        selected.filtered_preview.command.force_total_n,
    )


def test_zero_recoverable_cem_candidates_returns_no_safe_action_then_brake() -> None:
    plant, measurement, model, state, reference, allocator = _fixture()
    target_velocity, _ = model.geometry.cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    impossible_measurement = replace(
        measurement,
        attachment_velocity_m_s=(
            target_velocity - np.array([0.0, 2.0, 0.0])
        ),
    )
    safety_filter = make_stage4_executable_force_filter(
        plant=plant,
        measurement=impossible_measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    controller = HumanSpaceMPC(cuff_allocator=allocator)
    action, diagnostics = controller.solve(
        state,
        4.0,
        lambda _: reference,
        model,
        first_action_batch_preview=safety_filter,
    )
    assert action is None
    assert diagnostics["status"] == NO_SAFE_ACTION
    assert diagnostics["first_action_feasible_candidates_per_iteration"] == [
        0,
        0,
    ]
    assert all(
        item == {FILTER_INFEASIBLE: controller.config.candidate_count}
        for item in diagnostics["first_action_filter_statuses_per_iteration"]
    )

    supervisor = TrackBrakeSupervisor()
    decision = supervisor.command(
        plant=plant,
        measurement=impossible_measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        track_reference=reference,
        proposed_action_nm=None,
        mpc_status=NO_SAFE_ACTION,
    )
    assert decision.mode == BRAKE
    assert decision.trigger == NO_SAFE_ACTION
