from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.high_rom_dynamic_pilot import (
    PILOT_DURATION_S,
    pilot_trajectories,
)
from traction_mpc_stage4.high_rom_human_v2 import HIGH_ROM_HUMAN_V2
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.progress_aware_cem import (
    ProgressAwareCEMConfig,
    ProgressAwareCEMMPC,
    ProgressAwareReferenceClock,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case


def _model() -> BaseParameterHumanModel:
    human = HIGH_ROM_HUMAN_V2
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=human.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([human.sleeve_center_m, 0.0]),
    )
    return BaseParameterHumanModel(
        geometry,
        nominal_base_parameters(human),
        rom_human=human,
    )


def _clock(index: int = 0) -> ProgressAwareReferenceClock:
    trajectory = pilot_trajectories()[index]
    return ProgressAwareReferenceClock(
        trajectory.reference,
        trajectory.batched_path_kinematics,
        duration_s=PILOT_DURATION_S,
    )


def test_vectorized_high_rom_path_matches_retained_scalar_reference() -> None:
    for trajectory in pilot_trajectories():
        time = np.linspace(0.0, PILOT_DURATION_S, 101).reshape(1, -1)
        q, dq, ddq = trajectory.batched_path_kinematics(time)
        scalar = [trajectory.reference(value) for value in time[0]]
        np.testing.assert_allclose(q[0], [item.q_rad for item in scalar], atol=1e-14)
        np.testing.assert_allclose(
            dq[0], [item.dq_rad_s for item in scalar], atol=1e-14
        )
        np.testing.assert_allclose(
            ddq[0], [item.ddq_rad_s2 for item in scalar], atol=1e-14
        )


def test_batched_geometry_and_allocator_match_selected_scalar_laws() -> None:
    controller = ProgressAwareCEMMPC(_clock())
    human = _model()
    rng = np.random.default_rng(8128)
    state = np.column_stack(
        [
            rng.uniform(0.15, 1.8, 24),
            rng.uniform(0.20, 1.9, 24),
            rng.uniform(-0.4, 0.4, 24),
            rng.uniform(-0.4, 0.4, 24),
        ]
    )
    action = rng.uniform([-45.0, -20.0], [45.0, 20.0], size=(24, 2))
    position, velocity = controller._batched_position_velocity(
        state[:, :2], state[:, 2:], human
    )
    scalar_position = np.asarray(
        [human.geometry.cuff_pose(item[:2]).translation for item in state]
    )
    scalar_velocity = np.asarray(
        [human.geometry.cuff_velocity(item[:2], item[2:])[0] for item in state]
    )
    np.testing.assert_allclose(position, scalar_position, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(velocity, scalar_velocity, rtol=1e-13, atol=1e-13)

    batched_force = controller._batched_cuff_force_world(
        action, state[:, :2], human
    )
    scalar_force = np.asarray(
        [
            controller.cuff_allocator.allocate(torque, item[:2], human)[
                "wrench_world"
            ][:3]
            for torque, item in zip(action, state, strict=True)
        ]
    )
    np.testing.assert_allclose(batched_force, scalar_force, rtol=1e-12, atol=1e-12)


def test_joint_cem_keeps_frozen_population_and_predicts_its_final_action() -> None:
    clock = _clock()
    human = _model()
    controller = ProgressAwareCEMMPC(clock)
    reference = clock.reference(0.0)
    state = np.concatenate([reference.q_rad, reference.dq_rad_s])
    action, diagnostics = controller.solve(
        state, 0.0, clock.reference, human
    )
    assert diagnostics["accepted"]
    assert diagnostics["candidate_count"] == 32
    assert diagnostics["elite_count"] == 6
    assert diagnostics["optimizer_iterations"] == 2
    assert diagnostics["joint_population_not_sequential_alpha_solves"]
    assert 0.5 <= diagnostics["selected_alpha"] <= 1.0
    assert diagnostics["predicted_rom_respected"]
    assert diagnostics["predicted_total_force_gate_respected"]
    assert len(
        diagnostics["selected_first_control_interval_predicted_command_force_n"]
    ) == 4

    q_ref, dq_ref, _ = clock.candidate_reference_arrays(
        0.0, np.array([diagnostics["selected_alpha"]]), np.array([0.0])
    )
    actual_position = human.geometry.cuff_pose(state[:2]).translation
    actual_velocity = human.geometry.cuff_velocity(state[:2], state[2:])[0]
    target_position = human.geometry.cuff_pose(q_ref[0, 0]).translation
    target_velocity = human.geometry.cuff_velocity(q_ref[0, 0], dq_ref[0, 0])[0]
    feedback = np.clip(
        3000.0 * (target_position - actual_position)
        + 140.0 * (target_velocity - actual_velocity),
        -200.0,
        200.0,
    )
    feedforward = controller.cuff_allocator.allocate(
        action, state[:2], human
    )["wrench_world"][:3]
    scalar_total = float(np.linalg.norm(feedback + feedforward))
    assert diagnostics[
        "selected_first_predicted_command_force_n"
    ] == pytest.approx(scalar_total, rel=1e-12, abs=1e-12)


def test_pacing_costs_are_domain_normalized_without_tuned_weights() -> None:
    payload = ProgressAwareCEMConfig().as_dict()
    assert payload["minimum_alpha"] == pytest.approx(0.5)
    assert payload["maximum_alpha"] == pytest.approx(1.0)
    assert payload["initial_alpha_std"] == pytest.approx(0.125)
    assert payload["floor_alpha_std"] == pytest.approx(0.01)
    assert not payload["pacing_weights_tuned"]


def test_sensor_rollout_applies_selected_alpha_and_records_same_action_force() -> None:
    trajectory = pilot_trajectories()[0]
    clock = _clock()
    case = sensor_realism_cases()[2]

    def estimator_factory(measurement, q_prior):
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN_V2,
        )

    summary, trace = run_sensor_realism_case(
        case,
        duration_s=0.04,
        estimator_architecture="integral_minimal",
        true_human_override=HIGH_ROM_HUMAN_V2,
        true_metadata_override={"case": "progress_cem_integration_smoke"},
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        reference_execution=clock,
        mpc_factory=lambda: ProgressAwareCEMMPC(clock),
        estimator_factory=estimator_factory,
    )
    prediction = summary["selected_command_force_prediction"]
    assert prediction["prediction_matches_selected_final_cem_action"]
    assert prediction["sample_count"] == 2
    path_prediction = summary["selected_control_path_command_force_prediction"]
    assert path_prediction[
        "prediction_uses_selected_final_cem_action_at_each_5ms_hold_substep"
    ]
    assert path_prediction["sample_count"] == 8
    assert len(trace["mpc_selected_alpha"]) == 2
    assert np.all((trace["mpc_selected_alpha"] >= 0.5))
    assert np.all((trace["mpc_selected_alpha"] <= 1.0))
