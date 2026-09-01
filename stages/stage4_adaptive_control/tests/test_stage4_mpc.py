from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.executable_command import (
    prepare_executable_command_context,
    preview_executable_command,
    preview_executable_commands_batch,
)
from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage4.human_model import allocate_generalized_action
from traction_mpc_stage4.cuff_allocator import (
    CuffAwareSagittalAllocator,
    DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG,
    default_engineering_cuff_allocator,
)
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
    make_stage4_first_action_preview,
    preview_stage4_executable_command,
)
from traction_mpc_stage4.mpc import (
    INTERACTION_AWARE_MPC_CONFIG,
    NO_SAFE_ACTION,
    SAFE_ACTION,
    HumanMPCConfig,
    HumanSpaceMPC,
)
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    OneShotHumanEstimatorV2,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)


def _base_parameter_model() -> BaseParameterHumanModel:
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([HUMAN.sleeve_center_m, 0.0]),
    )
    return BaseParameterHumanModel(geometry, nominal_base_parameters(HUMAN))


def _first_action_preview(
    controller: HumanSpaceMPC,
    state: np.ndarray,
    human: object,
    *,
    target_position_m: np.ndarray | None = None,
):
    target_position = (
        np.zeros(3)
        if target_position_m is None
        else np.asarray(target_position_m, dtype=float)
    )

    def preview(action: np.ndarray):
        allocation = controller.cuff_allocator.allocate(action, state[:2], human)
        return preview_executable_command(
            attachment_position_m=np.zeros(3),
            attachment_rotation_matrix=np.eye(3),
            attachment_velocity_m_s=np.zeros(3),
            attachment_angular_velocity_rad_s=np.zeros(3),
            robot_q_rad=np.zeros(6),
            robot_dq_rad_s=np.zeros(6),
            neutral_robot_q_rad=np.zeros(6),
            target_position_m=target_position,
            target_velocity_m_s=np.zeros(3),
            target_rotation_matrix=np.eye(3),
            target_angular_velocity_rad_s=np.zeros(3),
            allocator_wrench_world=np.asarray(allocation["wrench_world"]),
            robot_attachment_jacobian=np.eye(6),
            bias_torque_nm=np.zeros(6),
            torque_limits_nm=np.full(6, 1.0e6),
        )

    return preview


def _first_action_batch_preview(
    controller: HumanSpaceMPC,
    state: np.ndarray,
    human: object,
    *,
    target_position_m: np.ndarray | None = None,
):
    target_position = (
        np.zeros(3)
        if target_position_m is None
        else np.asarray(target_position_m, dtype=float)
    )
    context = prepare_executable_command_context(
        attachment_position_m=np.zeros(3),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.zeros(3),
        attachment_angular_velocity_rad_s=np.zeros(3),
        robot_q_rad=np.zeros(6),
        robot_dq_rad_s=np.zeros(6),
        neutral_robot_q_rad=np.zeros(6),
        target_position_m=target_position,
        target_velocity_m_s=np.zeros(3),
        target_rotation_matrix=np.eye(3),
        target_angular_velocity_rad_s=np.zeros(3),
        robot_attachment_jacobian=np.eye(6),
        bias_torque_nm=np.zeros(6),
        torque_limits_nm=np.full(6, 1.0e6),
    )

    def preview(actions: np.ndarray):
        wrenches = controller.cuff_allocator.allocate_wrenches_batch(
            actions, state[:2], human
        )
        return preview_executable_commands_batch(context, wrenches)

    return preview


def _solve(
    controller: HumanSpaceMPC,
    state: np.ndarray,
    time_s: float,
    reference_fn,
    human: object,
):
    return controller.solve(
        state,
        time_s,
        reference_fn,
        human,
        first_action_preview=_first_action_preview(controller, state, human),
    )


def _solve_batch(
    controller: HumanSpaceMPC,
    state: np.ndarray,
    time_s: float,
    reference_fn,
    human: object,
    *,
    target_position_m: np.ndarray | None = None,
):
    return controller.solve(
        state,
        time_s,
        reference_fn,
        human,
        first_action_batch_preview=_first_action_batch_preview(
            controller,
            state,
            human,
            target_position_m=target_position_m,
        ),
    )


def test_cuff_allocation_recovers_generalized_action_without_moment_clipping() -> None:
    q = np.radians([30.0, 50.0])
    action = np.array([45.0, -12.0])
    allocation = allocate_generalized_action(action, q, HUMAN)
    assert allocation["allocation_residual_nm"] < 1e-12
    assert allocation["force_norm_n"] < CUFF_TRANSLATIONAL_FORCE_GATE_N


def test_human_space_mpc_returns_feasible_action() -> None:
    controller = HumanSpaceMPC(HumanMPCConfig(horizon_steps=5, candidate_count=32))
    reference = teaching_reference(1.2)
    state = np.concatenate([reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s])
    action, diagnostics = _solve(
        controller, state, 1.2, teaching_reference, HUMAN
    )
    assert action is not None
    assert diagnostics["accepted"], diagnostics
    assert diagnostics["predicted_rom_respected"]
    assert diagnostics["peak_predicted_force_n"] <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-7
    assert np.all(np.isfinite(action))


def test_nominal_safe_winner_matches_accepted_phase1_result() -> None:
    controller = HumanSpaceMPC()
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    action, diagnostics = _solve(
        controller, state, 1.2, teaching_reference, HUMAN
    )
    assert action is not None
    assert diagnostics["status"] == SAFE_ACTION
    np.testing.assert_allclose(
        action,
        [39.51736342655231, -7.2376318646729585],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert diagnostics["objective"] == 0.4047604529018036
    assert diagnostics["first_action_feasible_candidates_per_iteration"] == [
        32,
        32,
    ]


@pytest.mark.parametrize(
    "target_position_m",
    (
        np.zeros(3),
        np.array([0.0, 190.0 / 3000.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
    ),
    ids=("nominal", "partially-infeasible", "zero-safe"),
)
def test_scalar_and_batch_preview_match_candidate_by_candidate(
    target_position_m: np.ndarray,
) -> None:
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    controller = HumanSpaceMPC()
    actions = np.random.default_rng(20260824).normal(
        0.0, [35.0, 22.0], size=(32, 2)
    )
    scalar_preview = _first_action_preview(
        controller,
        state,
        HUMAN,
        target_position_m=target_position_m,
    )
    batch = _first_action_batch_preview(
        controller,
        state,
        HUMAN,
        target_position_m=target_position_m,
    )(actions)
    scalar = [scalar_preview(action) for action in actions]
    for name in (
        "force_position_n",
        "force_velocity_n",
        "force_allocator_n",
        "force_total_n",
    ):
        np.testing.assert_allclose(
            getattr(batch, name),
            np.asarray([getattr(command, name) for command in scalar]),
            rtol=0.0,
            atol=1.0e-13,
        )
    np.testing.assert_array_equal(
        batch.feasible,
        np.asarray([command.feasible for command in scalar]),
    )
    np.testing.assert_allclose(
        batch.translational_force_norm_n,
        [command.translational_force_norm_n for command in scalar],
        rtol=0.0,
        atol=1.0e-13,
    )


@pytest.mark.parametrize(
    "target_position_m",
    (
        np.zeros(3),
        np.array([0.0, 190.0 / 3000.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
    ),
    ids=("nominal", "partially-infeasible", "zero-safe"),
)
def test_scalar_and_batch_screening_preserve_cem_result(
    target_position_m: np.ndarray,
) -> None:
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    scalar = HumanSpaceMPC()
    batch = HumanSpaceMPC()
    scalar_action, scalar_diagnostics = scalar.solve(
        state,
        1.2,
        teaching_reference,
        HUMAN,
        first_action_preview=_first_action_preview(
            scalar,
            state,
            HUMAN,
            target_position_m=target_position_m,
        ),
    )
    batch_action, batch_diagnostics = _solve_batch(
        batch,
        state,
        1.2,
        teaching_reference,
        HUMAN,
        target_position_m=target_position_m,
    )
    assert batch_diagnostics["status"] == scalar_diagnostics["status"]
    assert batch_diagnostics[
        "first_action_feasible_candidates_per_iteration"
    ] == scalar_diagnostics["first_action_feasible_candidates_per_iteration"]
    assert batch_diagnostics[
        "first_action_feasible_candidate_evaluations"
    ] == scalar_diagnostics["first_action_feasible_candidate_evaluations"]
    if scalar_action is None:
        assert batch_action is None
        assert np.isinf(batch_diagnostics["objective"])
        assert np.isinf(scalar_diagnostics["objective"])
        return
    assert batch_action is not None
    np.testing.assert_array_equal(batch_action, scalar_action)
    assert batch_diagnostics["objective"] == scalar_diagnostics["objective"]
    for key in (
        "force_position_n",
        "force_velocity_n",
        "force_allocator_n",
        "force_total_n",
    ):
        np.testing.assert_allclose(
            batch_diagnostics["selected_executable_command"][key],
            scalar_diagnostics["selected_executable_command"][key],
            rtol=0.0,
            atol=1.0e-13,
        )


def test_executable_screen_removes_unsafe_candidates_and_selects_safe_alternative() -> None:
    controller = HumanSpaceMPC()
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    preview = _first_action_preview(
        controller,
        state,
        HUMAN,
        target_position_m=np.array([0.0, 190.0 / 3000.0, 0.0]),
    )
    action, diagnostics = controller.solve(
        state,
        1.2,
        teaching_reference,
        HUMAN,
        first_action_preview=preview,
    )
    assert action is not None
    assert diagnostics["status"] == SAFE_ACTION
    counts = diagnostics["first_action_feasible_candidates_per_iteration"]
    assert all(0 < count < controller.config.candidate_count for count in counts)
    assert diagnostics["selected_executable_force_norm_n"] <= 200.0 + 1.0e-9
    assert diagnostics["selected_executable_force_margin_n"] >= -1.0e-9
    np.testing.assert_allclose(
        diagnostics["selected_executable_command"]["force_total_n"],
        preview(action).force_total_n,
    )


def test_no_safe_action_returns_none_without_fallback_or_state_update() -> None:
    controller = HumanSpaceMPC()
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    action, diagnostics = controller.solve(
        state,
        1.2,
        teaching_reference,
        HUMAN,
        first_action_preview=_first_action_preview(
            controller,
            state,
            HUMAN,
            target_position_m=np.array([0.0, 1.0, 0.0]),
        ),
    )
    assert action is None
    assert diagnostics["status"] == NO_SAFE_ACTION
    assert diagnostics["first_action_feasible_candidate_evaluations"] == 0
    assert diagnostics["first_action_feasible_candidates_per_iteration"] == [0, 0]
    assert diagnostics["selected_executable_command"] is None
    assert controller.last_sequence is None
    np.testing.assert_array_equal(controller.last_action, np.zeros(2))


def test_selected_preview_equals_actual_first_interval_execution_force() -> None:
    reference = teaching_reference(0.0)
    plant = SensorBoundaryStage4Plant(HUMAN)
    truth = plant.reset(reference.q_rad)
    measurement = CausalMeasurementLayer(sensor_realism_cases()[0], truth).current
    estimator = OneShotHumanEstimatorV2(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        reference.q_rad,
    )
    state = estimator.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    allocator = default_engineering_cuff_allocator()
    controller = HumanSpaceMPC(cuff_allocator=allocator)
    preview = make_stage4_first_action_batch_preview(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=estimator.model,
        cuff_allocator=allocator,
        reference=reference,
    )
    action, diagnostics = controller.solve(
        state,
        0.0,
        teaching_reference,
        estimator.model,
        first_action_batch_preview=preview,
    )
    assert action is not None and diagnostics["status"] == SAFE_ACTION
    actual = preview_stage4_executable_command(
        plant=plant,
        measurement=measurement,
        action_nm=action,
        estimated_state=state,
        human_model=estimator.model,
        cuff_allocator=allocator,
        reference=reference,
    ).command
    np.testing.assert_array_equal(
        diagnostics["selected_executable_command"]["force_total_n"],
        actual.force_total_n,
    )
    assert diagnostics["selected_executable_force_norm_n"] == (
        actual.translational_force_norm_n
    )
    plant.apply_executable_command(actual)
    np.testing.assert_array_equal(plant.last_force, actual.force_total_n)


def test_default_engineering_allocator_is_frozen_one_to_one() -> None:
    controller = HumanSpaceMPC()
    assert isinstance(controller.cuff_allocator, CuffAwareSagittalAllocator)
    assert controller.uses_default_engineering_cuff_allocator
    assert DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.resultant_force_weight == 1.0
    assert (
        DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.cylindrical_surface_effort_weight
        == 1.0
    )
    assert DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.wrench_continuity_weight == 0.0


def test_candidate_audit_capture_does_not_change_cem_action_or_objective() -> None:
    config = HumanMPCConfig(horizon_steps=5, candidate_count=16)
    plain = HumanSpaceMPC(config)
    audited = HumanSpaceMPC(config, candidate_audit_solve_indices=frozenset({0}))
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    plain_action, plain_diagnostics = _solve(
        plain,
        state, 1.2, teaching_reference, HUMAN
    )
    audited_action, audited_diagnostics = _solve(
        audited,
        state, 1.2, teaching_reference, HUMAN
    )
    assert plain_action is not None and audited_action is not None
    np.testing.assert_allclose(audited_action, plain_action)
    np.testing.assert_allclose(
        audited_diagnostics["objective"], plain_diagnostics["objective"]
    )
    assert len(audited.candidate_audit_history) == 1
    assert len(audited.candidate_audit_history[0]["candidates"]) == 32


def test_interaction_extension_is_explicit_and_baseline_defaults_to_zero() -> None:
    baseline = HumanMPCConfig()
    assert not baseline.interaction_aware
    assert baseline.resultant_force_weight == 0.0
    assert baseline.cylindrical_surface_effort_weight == 0.0
    assert baseline.wrench_slew_weight == 0.0

    registered = INTERACTION_AWARE_MPC_CONFIG
    assert registered.interaction_aware
    contract = registered.objective_contract()
    assert contract["raw_shear_comfort_metric_used"] is False
    assert "not pressure" in contract["surface_proxy_interpretation"]
    assert contract["weights"] == {
        "action_weight": 2.0e-3,
        "action_rate_weight": 5.0e-3,
        "resultant_force_weight": 0.10,
        "cylindrical_surface_effort_weight": 0.05,
        "wrench_slew_weight": 0.05,
    }


def test_interaction_terms_penalize_equivalent_load_and_wrench_slew() -> None:
    controller = HumanSpaceMPC(INTERACTION_AWARE_MPC_CONFIG)
    q = np.radians([30.0, 50.0])
    state = np.concatenate([q, np.zeros(2)])
    predicted = np.repeat(state[np.newaxis, :], 3, axis=0)
    constant = np.repeat(np.array([[45.0, -12.0]]), 3, axis=0)
    alternating = np.array([[45.0, -12.0], [-45.0, 12.0], [45.0, -12.0]])
    constant_terms, _ = controller._interaction_cost_terms(
        state, constant, predicted, HUMAN
    )
    alternating_terms, _ = controller._interaction_cost_terms(
        state, alternating, predicted, HUMAN
    )
    assert constant_terms["resultant_force_cost"] > 0.0
    assert constant_terms["cylindrical_surface_effort_cost"] > 0.0
    assert constant_terms["wrench_slew_cost"] > 0.0
    assert (
        alternating_terms["wrench_slew_cost"]
        > constant_terms["wrench_slew_cost"]
    )


def test_batched_rk4_and_cuff_allocation_match_scalar_reference() -> None:
    controller = HumanSpaceMPC(implementation="batched")
    human = _base_parameter_model()
    rng = np.random.default_rng(314159)
    state = np.column_stack(
        [
            rng.uniform(0.15, 1.10, 24),
            rng.uniform(0.20, 1.45, 24),
            rng.uniform(-0.4, 0.4, 24),
            rng.uniform(-0.4, 0.4, 24),
        ]
    )
    action = rng.uniform([-45.0, -20.0], [45.0, 20.0], size=(24, 2))
    scalar_next = np.asarray(
        [
            human.step_dynamics(item, torque, controller.config.prediction_dt_s)
            for item, torque in zip(state, action, strict=True)
        ]
    )
    batched_next = controller._batched_base_step(state, action, human)
    np.testing.assert_allclose(batched_next, scalar_next, rtol=1e-13, atol=1e-13)

    scalar_force = np.asarray(
        [
            controller.cuff_allocator.allocate(torque, item[:2], human)[
                "force_norm_n"
            ]
            for item, torque in zip(state, action, strict=True)
        ]
    )
    batched_force = controller._batched_cuff_force_norm(action, state[:, :2], human)
    np.testing.assert_allclose(batched_force, scalar_force, rtol=1e-12, atol=1e-12)


def test_batched_is_default_and_scalar_remains_available() -> None:
    assert HumanSpaceMPC().implementation == "batched"
    assert HumanSpaceMPC(implementation="scalar").implementation == "scalar"


def test_batched_cem_preserves_population_elites_action_cost_and_wrench() -> None:
    human = _base_parameter_model()
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    scalar = HumanSpaceMPC(
        implementation="scalar", candidate_audit_solve_indices=frozenset({0})
    )
    batched = HumanSpaceMPC(
        implementation="batched", candidate_audit_solve_indices=frozenset({0})
    )
    scalar_action, scalar_diagnostics = _solve(
        scalar,
        state, 1.2, teaching_reference, human
    )
    batched_action, batched_diagnostics = _solve(
        batched,
        state, 1.2, teaching_reference, human
    )
    assert scalar_action is not None and batched_action is not None
    np.testing.assert_allclose(batched_action, scalar_action, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(
        batched_diagnostics["objective"],
        scalar_diagnostics["objective"],
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        batched_diagnostics["minimum_constraint_margin"],
        scalar_diagnostics["minimum_constraint_margin"],
        rtol=0.0,
        atol=1e-12,
    )
    scalar_audit = scalar.candidate_audit_history[0]
    batched_audit = batched.candidate_audit_history[0]
    np.testing.assert_allclose(
        [item["sequence_nm"] for item in batched_audit["candidates"]],
        [item["sequence_nm"] for item in scalar_audit["candidates"]],
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        [item["actual_total_objective"] for item in batched_audit["candidates"]],
        [item["actual_total_objective"] for item in scalar_audit["candidates"]],
        rtol=1e-12,
        atol=1e-12,
    )
    assert [
        item["elite_indices"] for item in batched_audit["cem_iterations"]
    ] == [item["elite_indices"] for item in scalar_audit["cem_iterations"]]
    np.testing.assert_allclose(
        [item["updated_mean_nm"] for item in batched_audit["cem_iterations"]],
        [item["updated_mean_nm"] for item in scalar_audit["cem_iterations"]],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        batched.last_sequence,
        scalar.last_sequence,
        rtol=0.0,
        atol=1e-12,
    )
    q_ref, dq_ref, _ = scalar._reference_arrays(1.2, teaching_reference)
    scalar_evaluation = scalar._evaluate_sequence(
        state, scalar.last_sequence, q_ref, dq_ref, human
    )
    batched_evaluation = batched._evaluate_sequence(
        state, batched.last_sequence, q_ref, dq_ref, human
    )
    np.testing.assert_allclose(
        batched_evaluation[2], scalar_evaluation[2], rtol=0.0, atol=1e-12
    )
    scalar_allocation = scalar.cuff_allocator.allocate(
        scalar_action, state[:2], human
    )
    batched_allocation = batched.cuff_allocator.allocate(
        batched_action, state[:2], human
    )
    np.testing.assert_allclose(
        batched_allocation["wrench_world"],
        scalar_allocation["wrench_world"],
        rtol=0.0,
        atol=1e-12,
    )


def test_batched_mpc_short_closed_loop_matches_scalar_and_safety_events() -> None:
    case = sensor_realism_cases()[0]
    outputs = []
    for implementation in ("scalar", "batched"):
        summary, trace = run_sensor_realism_case(
            case,
            duration_s=0.12,
            estimator_architecture="integral_minimal",
            result_case_name=f"equivalence_{implementation}",
            mpc_factory=lambda name=implementation: HumanSpaceMPC(
                implementation=name
            ),
        )
        outputs.append((summary, trace))
    scalar_summary, scalar_trace = outputs[0]
    batched_summary, batched_trace = outputs[1]
    for key in (
        "desired_human_action_nm",
        "allocated_wrench_world",
        "human_q_deg_god_view",
        "robot_torque_nm",
        "reference_phase_time_s",
    ):
        np.testing.assert_allclose(
            batched_trace[key], scalar_trace[key], rtol=1e-11, atol=1e-11
        )
    assert batched_summary["termination_reason"] == scalar_summary[
        "termination_reason"
    ]
    assert batched_summary["events"] == scalar_summary["events"]
