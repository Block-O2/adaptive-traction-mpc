from __future__ import annotations

import numpy as np

from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage4.human_model import allocate_generalized_action
from traction_mpc_stage4.cuff_allocator import (
    CuffAwareSagittalAllocator,
    DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG,
)
from traction_mpc_stage4.mpc import (
    INTERACTION_AWARE_MPC_CONFIG,
    HumanMPCConfig,
    HumanSpaceMPC,
)
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case


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
    action, diagnostics = controller.solve(state, 1.2, teaching_reference, HUMAN)
    assert diagnostics["accepted"], diagnostics
    assert diagnostics["predicted_rom_respected"]
    assert diagnostics["peak_predicted_force_n"] <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-7
    assert np.all(np.isfinite(action))


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
    plain_action, plain_diagnostics = plain.solve(
        state, 1.2, teaching_reference, HUMAN
    )
    audited_action, audited_diagnostics = audited.solve(
        state, 1.2, teaching_reference, HUMAN
    )
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
    scalar_action, scalar_diagnostics = scalar.solve(
        state, 1.2, teaching_reference, human
    )
    batched_action, batched_diagnostics = batched.solve(
        state, 1.2, teaching_reference, human
    )
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
