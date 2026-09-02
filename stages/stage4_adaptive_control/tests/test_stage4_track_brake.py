from __future__ import annotations

from dataclasses import replace

import numpy as np

from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.measurement import (
    CausalMeasurementLayer,
    sensor_realism_cases,
)
from traction_mpc_stage4.mpc import NO_SAFE_ACTION, SAFE_ACTION
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.safety_filter import FILTER_INFEASIBLE, SAFE_UNCHANGED
from traction_mpc_stage4.track_brake import (
    BRAKE,
    BRAKE_INFEASIBLE,
    SAFE_BRAKE,
    TRACK,
    TrackBrakeConfig,
    TrackBrakeSupervisor,
)


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
    return plant, measurement, model, state, reference


def test_track_safe_action_is_executed_without_changing_normal_mode() -> None:
    plant, measurement, model, state, reference = _fixture()
    allocator = default_engineering_cuff_allocator()
    action = model.inverse_dynamics(state[:2], state[2:], reference.ddq_rad_s2)
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
    )
    assert decision.mode == TRACK
    assert decision.status == SAFE_ACTION
    assert decision.executable_preview is not None
    assert decision.executable_preview.command.feasible
    assert decision.safety_filter["status"] == SAFE_UNCHANGED
    assert decision.safety_filter["lambda"] == 0.0
    np.testing.assert_array_equal(decision.action_nm, action)


def test_unsafe_track_preview_enters_brake_and_preview_equals_execution() -> None:
    plant, measurement, model, state, reference = _fixture()
    allocator = default_engineering_cuff_allocator()
    unsafe = 10.0 * model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    supervisor = TrackBrakeSupervisor()
    decision = supervisor.command(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        track_reference=reference,
        proposed_action_nm=unsafe,
        mpc_status=SAFE_ACTION,
    )
    assert decision.mode == BRAKE
    assert decision.status == SAFE_BRAKE
    assert decision.trigger == FILTER_INFEASIBLE
    assert decision.executable_preview is not None
    assert decision.executable_preview.command.feasible
    plant.apply_executable_command(decision.executable_preview.command)
    np.testing.assert_array_equal(
        plant.last_force,
        decision.executable_preview.command.force_total_n,
    )


def test_no_safe_action_enters_brake_without_substituting_mpc_action() -> None:
    plant, measurement, model, state, reference = _fixture()
    supervisor = TrackBrakeSupervisor()
    decision = supervisor.command(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=default_engineering_cuff_allocator(),
        track_reference=reference,
        proposed_action_nm=None,
        mpc_status=NO_SAFE_ACTION,
    )
    assert decision.mode == BRAKE
    assert decision.status == SAFE_BRAKE
    assert decision.trigger == NO_SAFE_ACTION
    assert decision.action_nm is not None


def test_brake_reference_is_continuous_and_respects_rate_change_limits() -> None:
    plant, measurement, model, state, reference = _fixture()
    config = TrackBrakeConfig()
    supervisor = TrackBrakeSupervisor(config)
    decisions = [
        supervisor.command(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=default_engineering_cuff_allocator(),
            track_reference=reference,
            proposed_action_nm=None,
            mpc_status=NO_SAFE_ACTION,
        )
    ]
    for _ in range(20):
        decisions.append(
            supervisor.command(
                plant=plant,
                measurement=measurement,
                estimated_state=state,
                human_model=model,
                cuff_allocator=default_engineering_cuff_allocator(),
                track_reference=reference,
                proposed_action_nm=None,
                mpc_status=None,
            )
        )
    assert all(decision.status == SAFE_BRAKE for decision in decisions)
    references = [decision.reference for decision in decisions]
    assert all(brake_reference is not None for brake_reference in references)
    np.testing.assert_array_equal(references[0].q_rad, reference.q_rad)
    np.testing.assert_array_equal(references[0].dq_rad_s, reference.dq_rad_s)
    accelerations = np.asarray(
        [brake_reference.ddq_rad_s2 for brake_reference in references]
    )
    assert np.max(np.abs(accelerations)) <= (
        config.maximum_reference_deceleration_rad_s2 + 1.0e-12
    )
    assert np.max(np.abs(np.diff(accelerations, axis=0))) <= (
        config.maximum_reference_jerk_rad_s3 * config.control_dt_s + 1.0e-12
    )


class _ZeroAllocator:
    def allocate(self, action_nm, q_rad, human_model):
        del action_nm, q_rad, human_model
        return {
            "force_norm_n": 0.0,
            "wrench_world": np.zeros(6),
        }


def test_brake_infeasible_is_terminal_and_has_no_command_fallback() -> None:
    plant, measurement, model, state, reference = _fixture()
    target = model.geometry.cuff_pose(reference.q_rad).translation
    impossible_measurement = replace(
        measurement,
        attachment_position_m=target - np.array([1.0, 0.0, 1.0]),
    )
    supervisor = TrackBrakeSupervisor()
    decision = supervisor.command(
        plant=plant,
        measurement=impossible_measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=_ZeroAllocator(),
        track_reference=reference,
        proposed_action_nm=None,
        mpc_status=NO_SAFE_ACTION,
    )
    assert decision.mode == BRAKE
    assert decision.status == BRAKE_INFEASIBLE
    assert decision.terminate
    assert decision.action_nm is None
    assert decision.reference is None
    assert decision.executable_preview is None
    assert decision.feasible_candidate_count == 0


def test_short_nominal_runner_keeps_one_mpc_solve_per_track_cycle() -> None:
    supervisor = TrackBrakeSupervisor()
    summary, _ = run_sensor_realism_case(
        sensor_realism_cases()[0],
        duration_s=0.04,
        track_brake_supervisor=supervisor,
    )
    assert summary["termination_reason"] == "completed"
    assert supervisor.mode == TRACK
    assert supervisor.track_mpc_solve_count == 2
    assert summary["mpc"]["solve_count"] == 2
    assert supervisor.brake_cycle_count == 0
