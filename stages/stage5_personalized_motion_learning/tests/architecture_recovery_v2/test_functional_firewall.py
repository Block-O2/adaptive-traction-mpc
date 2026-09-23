from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as benchmark
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS,
    BOUNDED_KNEE_LEAD_PROFILE,
    CONTROLLER_RANDOM_SEED,
    HiddenSetup,
    TaskSpec,
    _nominal_geometry_from_first_pose,
    _inside_registered_rom,
    _inside_commissioning_consistency_envelope,
    _preview,
    _probe_wrench,
    _wrench_to_generalized,
    make_task_reference,
    make_benchmark_case,
    run_closed_loop_case,
)


def test_hidden_setup_and_allowed_task_input_are_separate_types() -> None:
    setup, task = make_benchmark_case(1101)
    assert isinstance(setup, HiddenSetup)
    assert isinstance(task, TaskSpec)
    hidden_fields = {field.name for field in fields(HiddenSetup)}
    assert {"task_id", "goal_q_rad", "duration_s"}.isdisjoint(hidden_fields)
    assert CONTROLLER_RANDOM_SEED == 20260824
    assert setup.seed != CONTROLLER_RANDOM_SEED


def test_task_randomness_is_independent_of_hidden_setup_randomness() -> None:
    setup_a, task_a = make_benchmark_case(1101, task_seed=2101)
    setup_b, task_b = make_benchmark_case(1101, task_seed=2102)
    assert setup_a.evaluation_record() == setup_b.evaluation_record()
    assert task_a.record() != task_b.record()


def test_task_profile_can_be_preregistered_independently_of_task_seed() -> None:
    _, task = make_benchmark_case(
        1101, task_seed=2101, task_profile="two_rate", high_rom=True
    )
    assert task.task_id == "two_rate"
    assert task.high_rom


def test_bed_feasible_generator_conditions_reference_without_exposing_truth() -> None:
    setup, task = make_benchmark_case(
        3101,
        task_seed=4101,
        task_profile="hip_lead",
        domain={"minimum_reference_clearance_m": 0.01},
    )
    assert setup.generation_min_reference_clearance_m is not None
    assert setup.generation_min_reference_clearance_m >= 0.01
    assert "generation_min_reference_clearance_m" not in task.record()
    assert setup.generation_dynamic_force_peak_n is not None
    assert setup.generation_dynamic_moment_peak_nm is not None
    assert (
        setup.evaluation_record()["generation_reference_basis"]
        == "pre_probe_hidden_initial_state_evaluation_only"
    )
    assert "generation_rejection_counts" not in task.record()


def test_bounded_knee_lead_has_versioned_nonzero_lead_and_exact_reverse() -> None:
    setup, task = make_benchmark_case(
        51001,
        task_seed=61001,
        task_profile=BOUNDED_KNEE_LEAD_PROFILE,
    )
    reference = make_task_reference(
        setup.initial_q_rad,
        task.goal_q_rad,
        task.task_id,
        task.duration_s,
        setup.geometry,
    )
    outbound = 0.40 * task.duration_s
    hold = 0.12 * task.duration_s
    midpoint = setup.initial_q_rad + BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS * (
        task.goal_q_rad - setup.initial_q_rad
    )
    outbound_midpoint = reference(outbound * 0.52)
    return_midpoint = reference(outbound + hold + 0.40 * task.duration_s * 0.48)
    assert np.allclose(outbound_midpoint.q_rad, midpoint)
    assert np.allclose(return_midpoint.q_rad, midpoint)
    assert BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS[1] > BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS[0]
    assert np.allclose(outbound_midpoint.dq_rad_s, 0.0)
    assert np.allclose(return_midpoint.dq_rad_s, 0.0)


def test_executable_preview_allocates_at_current_estimated_q() -> None:
    class RecordingModel:
        def __init__(self) -> None:
            self.received_q: np.ndarray | None = None

        def allocate_generalized_action(
            self, action_nm: np.ndarray, q_rad: np.ndarray
        ) -> dict[str, np.ndarray]:
            self.received_q = np.asarray(q_rad, dtype=float).copy()
            return {
                "force_world_n": np.zeros(3),
                "wrench_world": np.zeros(6),
            }

    model = RecordingModel()
    q = np.radians([31.0, 47.0])
    preview = _preview(np.zeros(2), model, q, 0.02)  # type: ignore[arg-type]
    assert preview.control_dt_s == 0.02
    assert np.array_equal(model.received_q, q)
    assert preview.feasible


def test_residual_bias_model_requires_extra_commanded_torque() -> None:
    setup, _ = make_benchmark_case(1101, task_seed=2101)
    physical_beta = setup.beta.copy()
    base = benchmark.BaseParameterHumanModel(
        setup.geometry, physical_beta, setup.human
    )
    bias = np.array([2.5, -1.5])
    model = benchmark._base_model_with_residual_bias(
        setup.geometry, physical_beta, bias
    )
    state = np.concatenate([setup.initial_q_rad, np.zeros(2)])
    hold_without_bias = base.inverse_dynamics(
        state[:2], state[2:], np.zeros(2)
    )
    derivative = model.continuous_dynamics(state, hold_without_bias + bias)
    np.testing.assert_allclose(derivative, 0.0, atol=1.0e-10)
    np.testing.assert_array_equal(physical_beta, setup.beta)


def test_residual_bias_update_is_bounded_finite_and_nonmutating() -> None:
    previous = np.array([1.0, -2.0])
    sample = np.array([101.0, -102.0])
    previous_before = previous.copy()
    sample_before = sample.copy()
    updated, cap_hit = benchmark._update_task_residual_bias(
        previous, sample, alpha=0.2, limit_nm=12.0
    )
    np.testing.assert_array_equal(previous, previous_before)
    np.testing.assert_array_equal(sample, sample_before)
    np.testing.assert_allclose(updated, [12.0, -12.0])
    assert cap_hit
    assert np.all(np.isfinite(updated))
    assert np.max(np.abs(updated)) <= 12.0


def test_state_residual_features_are_fixed_bounded_and_state_only() -> None:
    state = np.array([*np.radians([40.0, 50.0]), 100.0, -100.0])
    features = benchmark._state_residual_features(state)
    assert features.shape == (5,)
    assert features[0] == 1.0
    assert np.max(np.abs(features[1:])) < 1.0
    batched = benchmark._state_residual_features(np.vstack([state, state]))
    np.testing.assert_allclose(batched, np.vstack([features, features]))


def test_state_residual_nlms_is_bounded_finite_and_nonmutating() -> None:
    weights = np.zeros((2, 5))
    state = np.array([*np.radians([40.0, 50.0]), 0.2, -0.3])
    sample = np.array([100.0, -100.0])
    weights_before = weights.copy()
    sample_before = sample.copy()
    updated, projection_hit, output_cap_hit = benchmark._update_state_residual_weights(
        weights, state, sample, alpha=0.2, limit_nm=12.0
    )
    np.testing.assert_array_equal(weights, weights_before)
    np.testing.assert_array_equal(sample, sample_before)
    assert updated.shape == (2, 5)
    assert np.all(np.isfinite(updated))
    assert np.max(np.linalg.norm(updated, axis=1)) <= 12.0 + 1.0e-12
    model_prediction = np.clip(
        updated @ benchmark._state_residual_features(state), -12.0, 12.0
    )
    assert np.max(np.abs(model_prediction)) <= 12.0 + 1.0e-12
    assert projection_hit or output_cap_hit


def test_state_residual_intercept_only_update_equals_v21_ewma() -> None:
    state = np.array([*np.radians([40.0, 50.0]), 0.0, 0.0])
    weights = np.zeros((2, 5))
    weights[:, 0] = np.array([1.0, -2.0])
    sample = np.array([3.0, 4.0])
    updated, projection_hit, output_cap_hit = (
        benchmark._update_state_residual_weights(
            weights, state, sample, alpha=0.2, limit_nm=12.0
        )
    )
    ewma, ewma_cap_hit = benchmark._update_task_residual_bias(
        weights[:, 0], sample, alpha=0.2, limit_nm=12.0
    )
    np.testing.assert_allclose(updated[:, 0], ewma)
    np.testing.assert_allclose(updated[:, 1:], 0.0)
    assert not projection_hit
    assert output_cap_hit == ewma_cap_hit


def test_zero_state_residual_exactly_reproduces_base_model() -> None:
    setup, _ = make_benchmark_case(1101, task_seed=2101)
    base = benchmark.BaseParameterHumanModel(
        setup.geometry, setup.beta, setup.human
    )
    residual = benchmark.StateResidualHumanModel(
        setup.geometry, setup.beta, setup.human, np.zeros((2, 5)), 12.0
    )
    state = np.array([*np.radians([42.0, 53.0]), 0.2, -0.1])
    action = np.array([7.0, 1.0])
    np.testing.assert_array_equal(
        residual.inverse_dynamics(state[:2], state[2:], np.zeros(2)),
        base.inverse_dynamics(state[:2], state[2:], np.zeros(2)),
    )
    np.testing.assert_array_equal(
        residual.continuous_dynamics(state, action),
        base.continuous_dynamics(state, action),
    )


def test_state_residual_update_affects_only_next_model_instance() -> None:
    setup, _ = make_benchmark_case(1101, task_seed=2101)
    state = np.array([*np.radians([40.0, 50.0]), 0.0, 0.0])
    before = benchmark.StateResidualHumanModel(
        setup.geometry, setup.beta, setup.human, np.zeros((2, 5)), 12.0
    )
    updated, _, _ = benchmark._update_state_residual_weights(
        before.residual_weights_nm,
        state,
        np.array([2.0, -3.0]),
        alpha=0.2,
        limit_nm=12.0,
    )
    after = benchmark.StateResidualHumanModel(
        setup.geometry, setup.beta, setup.human, updated, 12.0
    )
    np.testing.assert_array_equal(before.state_residual_nm(state), np.zeros(2))
    assert np.linalg.norm(after.state_residual_nm(state)) > 0.0


def test_state_residual_batched_mpc_matches_model_continuous_dynamics() -> None:
    setup, _ = make_benchmark_case(1101, task_seed=2101)
    weights = np.array(
        [[1.0, 0.3, -0.2, 0.4, 0.1], [-0.7, 0.2, 0.3, -0.1, 0.5]]
    )
    model = benchmark.StateResidualHumanModel(
        setup.geometry, setup.beta, setup.human, weights, 12.0
    )
    mpc = benchmark.StateResidualHumanSpaceMPC(implementation="batched")
    states = np.vstack(
        [
            np.concatenate([setup.initial_q_rad, np.zeros(2)]),
            np.array([*np.radians([42.0, 53.0]), 0.2, -0.1]),
        ]
    )
    actions = np.array([[4.0, -2.0], [7.0, 1.0]])
    batched = mpc._batched_base_continuous_dynamics(states, actions, model)
    scalar = np.vstack(
        [model.continuous_dynamics(state, action) for state, action in zip(states, actions)]
    )
    np.testing.assert_allclose(batched, scalar, rtol=1.0e-12, atol=1.0e-12)


def test_positive_state_residual_requires_positive_inverse_torque_and_reduces_forward_acceleration() -> None:
    setup, _ = make_benchmark_case(1101, task_seed=2101)
    weights = np.zeros((2, 5))
    weights[:, 0] = np.array([2.0, 1.0])
    base = benchmark.BaseParameterHumanModel(
        setup.geometry, setup.beta, setup.human
    )
    residual = benchmark.StateResidualHumanModel(
        setup.geometry, setup.beta, setup.human, weights, 12.0
    )
    state = np.array([*np.radians([40.0, 50.0]), 0.0, 0.0])
    zero_acceleration = np.zeros(2)
    base_hold = base.inverse_dynamics(state[:2], state[2:], zero_acceleration)
    residual_hold = residual.inverse_dynamics(
        state[:2], state[2:], zero_acceleration
    )
    np.testing.assert_allclose(residual_hold - base_hold, [2.0, 1.0])
    expected_correction = -np.linalg.solve(
        base.mass_matrix(state[:2]), np.array([2.0, 1.0])
    )
    np.testing.assert_allclose(
        residual.continuous_dynamics(state, base_hold)[2:],
        expected_correction,
    )


def test_residual_layer_is_disabled_for_nonadaptive_comparison_arms() -> None:
    assert benchmark._arm_uses_task_residual("adaptive")
    assert benchmark._arm_uses_task_residual("adaptive_state_residual")
    assert benchmark._arm_updates_task_beta("adaptive_state_residual")
    assert benchmark._arm_uses_task_residual("adaptive_phase_banked_residual")
    assert benchmark._arm_uses_task_residual("commissioning_beta_residual")
    assert not benchmark._arm_updates_task_beta("commissioning_beta_residual")
    assert benchmark._arm_updates_task_beta("adaptive")
    assert benchmark._arm_uses_task_residual("wrong_geometry_adaptive_dynamics")
    for arm in (
        "oracle",
        "commissioning_only_dynamics",
        "fixed_nominal",
        "no_dynamics_adaptation",
    ):
        assert not benchmark._arm_uses_task_residual(arm)  # type: ignore[arg-type]


def test_known_reference_phase_selector_has_no_learned_threshold() -> None:
    duration = 10.0
    assert benchmark._task_reference_phase("coordinated", duration, 4.0) == "outbound"
    assert benchmark._task_reference_phase("coordinated", duration, 4.01) == "hold"
    assert benchmark._task_reference_phase("coordinated", duration, 5.2) == "hold"
    assert benchmark._task_reference_phase("coordinated", duration, 5.21) == "return"
    assert benchmark._task_reference_phase("two_rate", duration, 4.6) == "outbound"
    assert benchmark._task_reference_phase("two_rate", duration, 4.61) == "hold"
    assert benchmark._task_reference_phase("two_rate", duration, 5.4) == "hold"
    assert benchmark._task_reference_phase("two_rate", duration, 5.41) == "return"


def test_phase_banked_residual_records_three_bounded_causal_banks() -> None:
    setup, task = make_benchmark_case(
        312001, task_seed=322001, task_profile="coordinated"
    )
    row = run_closed_loop_case(
        setup,
        task,
        "adaptive_phase_banked_residual",
        task_residual_bias_alpha=0.2,
        task_residual_bias_limit_nm=12.0,
    )
    assert row["task_residual_bias_representation"] == "known_reference_phase_banks_v1"
    assert set(row["task_residual_bias_phase_banks_final_nm"]) == {
        "outbound",
        "hold",
        "return",
    }
    assert row["task_residual_bias_update_count"] > 0
    assert row["task_residual_bias_finite"]
    assert row["task_residual_bias_within_limit"]
    assert row["task_residual_bias_cap_hit_count"] == 0


def test_commissioning_beta_residual_never_refits_beta_during_task() -> None:
    setup, task = make_benchmark_case(
        312002, task_seed=322002, task_profile="coordinated"
    )
    row = run_closed_loop_case(
        setup,
        task,
        "commissioning_beta_residual",
        task_residual_bias_alpha=0.2,
        task_residual_bias_limit_nm=12.0,
    )
    assert not row["task_beta_updates_enabled_for_arm"]
    assert row["task_beta_update_attempt_count"] == 0
    assert row["task_beta_accepted_update_count"] == 0
    assert row["task_residual_bias_update_count"] > 0
    assert row["task_residual_bias_finite"]
    assert row["task_residual_bias_within_limit"]


def test_adaptive_state_residual_uses_nlms_and_continual_beta() -> None:
    setup, task = make_benchmark_case(
        312003, task_seed=322003, task_profile="coordinated"
    )
    row = run_closed_loop_case(
        setup,
        task,
        "adaptive_state_residual",
        task_residual_bias_alpha=0.2,
        task_residual_bias_limit_nm=12.0,
    )
    assert row["task_residual_bias_representation"] == "bounded_linear_state_nlms_v1"
    assert row["task_beta_updates_enabled_for_arm"]
    assert row["task_beta_update_attempt_count"] > 0
    assert row["task_residual_bias_update_count"] > 0
    assert row["task_residual_bias_finite"]
    assert row["task_residual_bias_within_limit"]
    weights = np.asarray(row["task_state_residual_weights_final_nm"])
    assert weights.shape == (2, 5)
    assert np.max(np.linalg.norm(weights, axis=1)) <= 12.0 + 1.0e-12
    assert row["task_state_residual_velocity_scale_rad_s"] == 1.0
    assert row["task_state_residual_prediction_dynamics_component_evaluation_count"] > 0
    assert row["task_state_residual_chosen_rollout_component_evaluation_count"] > 0


def test_expected_git_status_seal_fails_closed() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "architecture_recovery_v2"
        / "run_functional_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("v2_campaign_runner", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    status = " M AGENTS.md\n?? stages/stage5_personalized_motion_learning/"
    digest = hashlib.sha256(status.encode("utf-8")).hexdigest()
    assert runner.validate_expected_git_status(
        {"expected_git_status_sha256": digest}, status
    ) == digest
    with pytest.raises(RuntimeError, match="sealed expected_git_status_sha256"):
        runner.validate_expected_git_status(
            {"expected_git_status_sha256": "0" * 64}, status
        )


def test_expected_source_seal_fails_closed(tmp_path: Path) -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "architecture_recovery_v2"
        / "run_functional_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("v2_campaign_runner_seal", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    source = tmp_path / "source.py"
    source.write_text("frozen\n")
    seal = tmp_path / "seal.json"
    seal.write_text(
        '{"files":{"'
        + str(source)
        + '":"'
        + hashlib.sha256(source.read_bytes()).hexdigest()
        + '"}}'
    )
    record = runner.validate_expected_source_seal(
        {"expected_source_seal_path": str(seal)}
    )
    assert record["files"][str(source)] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    source.write_text("drifted\n")
    with pytest.raises(RuntimeError, match="pre-run source seal mismatch"):
        runner.validate_expected_source_seal(
            {"expected_source_seal_path": str(seal)}
        )


def test_state_residual_development_gate_evaluator_is_fail_closed() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "architecture_recovery_v2"
        / "run_functional_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("v2_campaign_runner_gate", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    keys = [[index, index + 100] for index in range(24)]

    def arm(median: float, p95: float, completion: float = 1.0) -> dict[str, object]:
        return {
            "case_count": 24,
            "unique_case_key_count": 24,
            "case_keys": keys,
            "tracking_metric_count": 24,
            "full_horizon_metric_count": 24,
            "completion_rate": completion,
            "tracking_rmse_deg_median": median,
            "tracking_rmse_deg_p95": p95,
            "full_episode_force_peak_n_max": 120.0,
            "full_episode_moment_peak_nm_max": 30.0,
            "clearance_evaluated_count": 24,
            "post_probe_constructed_reference_clearance_evaluated_count": 24,
            "rom_violation_samples": 0,
            "probe_rom_violation_count": 0,
            "probe_clearance_violation_count": 0,
            "table_clearance_violation_samples": 0,
            "post_probe_constructed_reference_clearance_violation_count": 0,
            "probe_consistency_abort_count": 0,
            "probe_settle_timeout_count": 0,
            "solver_failure_count": 0,
            "safety_abort_count": 0,
            "estimated_rom_supervisor_abort_count": 0,
        }

    summary = {
        "by_arm": {
            "adaptive_state_residual": arm(0.40, 0.70),
            "adaptive": arm(0.50, 0.80),
            "commissioning_only_dynamics": arm(0.60, 1.00),
            "oracle": arm(0.35, 0.60),
        }
    }
    rows = []
    telemetry = {
        "task_residual_bias_peak_abs_nm": 2.0,
        "task_residual_bias_max_step_nm": 0.2,
        "task_residual_bias_total_variation_l1_nm": 3.0,
        "task_residual_bias_sign_reversal_count": 1,
        "task_state_residual_weight_peak_l2_nm": 2.0,
        "task_state_residual_weight_max_component_step_nm": 0.2,
        "task_state_residual_weight_total_variation_l1_nm": 4.0,
        "task_state_residual_coefficient_projection_hit_count": 0,
        "task_state_residual_observed_output_cap_hit_count": 0,
        "task_state_residual_prediction_dynamics_component_evaluation_count": 10,
        "task_state_residual_prediction_dynamics_component_cap_hit_count": 0,
        "task_state_residual_chosen_rollout_component_evaluation_count": 10,
        "task_state_residual_chosen_rollout_component_cap_hit_count": 0,
    }
    for _ in range(24):
        rows.append(
            {
                "arm": "adaptive_state_residual",
                **telemetry,
                "task_state_residual_weights_finite": True,
                "task_state_residual_weights_within_l2_projection_limit": True,
                "task_residual_bias_finite": True,
                "task_residual_bias_within_limit": True,
                "task_state_residual_feature_names": [
                    "constant",
                    "q1_rom",
                    "q2_rom",
                    "dq1_bounded",
                    "dq2_bounded",
                ],
                "task_state_residual_velocity_scale_rad_s": 1.0,
                "task_beta_updates_enabled_for_arm": True,
                "truth_firewall": {"deployable_truth_consumed": False},
            }
        )
    gates = {
        "expected_case_count_per_arm": 24,
        "expected_arms": [
            "oracle",
            "adaptive",
            "adaptive_state_residual",
            "commissioning_only_dynamics",
        ],
        "candidate_completion_rate_minimum": 0.9,
        "candidate_tracking_rmse_deg_median_maximum": 3.0,
        "candidate_tracking_rmse_deg_p95_maximum": 5.0,
        "force_peak_n_maximum": 200.0,
        "moment_peak_nm_maximum": 60.0,
        "candidate_vs_commissioning_median_improvement_fraction_minimum": 0.2,
        "candidate_vs_commissioning_completion_rate_margin_minimum": 0.25,
        "candidate_minus_oracle_median_gap_deg_maximum": 2.5,
        "residual_output_abs_nm_maximum": 12.0,
        "state_residual_velocity_scale_rad_s": 1.0,
    }
    result = runner.evaluate_state_residual_development_gates(summary, rows, gates)
    assert result["passed"]
    summary["by_arm"]["adaptive_state_residual"]["tracking_rmse_deg_p95"] = 0.9
    failed = runner.evaluate_state_residual_development_gates(summary, rows, gates)
    assert not failed["passed"]
    assert not failed["checks"]["candidate_p95_no_worse_than_v21"]


def test_formal_gate_evaluator_can_select_frozen_candidate_arm() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "architecture_recovery_v2"
        / "run_functional_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("v2_campaign_runner_formal", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    root = Path(__file__).resolve().parents[4]
    result = json.loads(
        (
            root
            / "stages/stage5_personalized_motion_learning/results/architecture_recovery_v2/phase2_v21/formal_unknown_setup_task_v21/result.json"
        ).read_text()
    )
    config = json.loads(
        (
            root
            / "stages/stage5_personalized_motion_learning/configs/architecture_recovery_v2/phase2_v21/formal_unknown_setup_task_v21.json"
        ).read_text()
    )
    baseline = runner.evaluate_gates(result["summary"], config["gates"])
    result["summary"]["by_arm"]["adaptive_state_residual"] = dict(
        result["summary"]["by_arm"]["adaptive"]
    )
    candidate_gates = dict(config["gates"])
    candidate_gates["candidate_arm"] = "adaptive_state_residual"
    candidate_gates["residual_output_abs_nm_maximum"] = 12.0
    candidate_gates["state_residual_velocity_scale_rad_s"] = 1.0
    candidate_gates["expected_arms"] = [
        "adaptive_state_residual" if name == "adaptive" else name
        for name in candidate_gates["expected_arms"]
    ]
    development = json.loads(
        (
            root
            / "stages/stage5_personalized_motion_learning/results/architecture_recovery_v2/phase2_recovery/state_residual_dev_v1/result.json"
        ).read_text()
    )
    candidate_rows = [
        row
        for row in development["rows"]
        if row["arm"] == "adaptive_state_residual"
    ]
    selected = runner.evaluate_gates(
        result["summary"], candidate_gates, candidate_rows
    )
    assert selected["candidate_arm"] == "adaptive_state_residual"
    for key, value in baseline["checks"].items():
        assert selected["checks"][key] == value
    assert all(
        value
        for key, value in selected["checks"].items()
        if key.startswith("adaptive_state_residual_")
    )


def test_registered_rom_supervisor_rejects_nonfinite_and_outside_angles() -> None:
    assert _inside_registered_rom(np.radians([40.0, 50.0]))
    assert not _inside_registered_rom(np.radians([-0.01, 50.0]))
    assert not _inside_registered_rom(np.radians([40.0, 100.01]))
    assert not _inside_registered_rom(np.array([math.nan, 0.0]))


def test_commissioning_consistency_abort_applies_no_wrench(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup, task = make_benchmark_case(1101, task_seed=2101)
    setup = replace(setup, initial_q_rad=np.radians([80.0, 0.0]))

    def forbidden_wrench(*args: object, **kwargs: object) -> tuple[np.ndarray, float]:
        raise AssertionError("probe wrench must not be evaluated after causal abort")

    monkeypatch.setattr(benchmark, "_probe_wrench", forbidden_wrench)
    row = run_closed_loop_case(setup, task, "adaptive")
    assert row["termination_reason"] == "probe_consistency_envelope_abort"
    assert row["probe_consistency_abort_count"] == 1
    assert row["probe_force_peak_n"] == 0.0


def test_commissioning_envelope_is_not_mislabeled_as_exact_rom() -> None:
    assert _inside_commissioning_consistency_envelope(np.radians([-1.0, 0.0]))
    assert not _inside_commissioning_consistency_envelope(np.radians([-6.0, 0.0]))


@pytest.mark.parametrize(
    ("arm", "residual_alpha"),
    [("adaptive", None), ("adaptive", 0.2), ("adaptive_state_residual", 0.2)],
)
def test_positive_post_probe_clearance_audit_cannot_change_adaptive_result(
    monkeypatch: pytest.MonkeyPatch,
    arm: benchmark.Arm,
    residual_alpha: float | None,
) -> None:
    setup, task = make_benchmark_case(
        111002,
        task_seed=121002,
        task_profile="coordinated",
        high_rom=True,
        domain={
            "minimum_reference_clearance_m": 0.025,
            "generation_static_force_peak_n_maximum": 150.0,
            "generation_static_moment_peak_nm_maximum": 45.0,
        },
    )

    monkeypatch.setattr(
        benchmark,
        "_minimum_hidden_clearance_for_constructed_reference_evaluation_only",
        lambda *args, **kwargs: 0.08,
    )
    lower_audit = run_closed_loop_case(
        setup, task, arm, task_residual_bias_alpha=residual_alpha
    )
    monkeypatch.setattr(
        benchmark,
        "_minimum_hidden_clearance_for_constructed_reference_evaluation_only",
        lambda *args, **kwargs: 0.18,
    )
    higher_audit = run_closed_loop_case(
        setup, task, arm, task_residual_bias_alpha=residual_alpha
    )

    assert lower_audit[
        "post_probe_constructed_reference_min_clearance_m_evaluation_only"
    ] == pytest.approx(0.08)
    assert higher_audit[
        "post_probe_constructed_reference_min_clearance_m_evaluation_only"
    ] == pytest.approx(0.18)
    behavior_keys = (
        "completed",
        "termination_reason",
        "sample_count",
        "q_tracking_rmse_deg",
        "q_tracking_max_abs_deg",
        "dq_tracking_rmse_deg_s",
        "hold_entry_0p5s_q_tracking_rmse_deg",
        "return_entry_0p5s_q_tracking_rmse_deg",
        "final_q_error_deg",
        "final_dq_deg_s",
        "force_peak_n",
        "moment_peak_nm",
        "solver_failure_count",
        "safety_abort_count",
        "estimated_rom_supervisor_abort_count",
        "dynamics_adaptation",
        "dynamics_update_trace",
        "accepted_dynamic_update_times_s",
        "task_residual_bias_final_nm",
        "task_residual_bias_peak_abs_nm",
        "task_residual_bias_cap_hit_count",
        "task_residual_bias_update_count",
        "task_residual_bias_max_step_nm",
        "task_residual_bias_total_variation_l1_nm",
        "task_residual_bias_sign_reversal_count",
        "task_residual_bias_representation",
        "task_residual_bias_phase_banks_final_nm",
        "task_state_residual_weights_final_nm",
        "task_state_residual_coefficient_projection_hit_count",
        "task_state_residual_observed_output_cap_hit_count",
        "task_state_residual_prediction_dynamics_component_cap_hit_count",
        "task_state_residual_chosen_rollout_component_cap_hit_count",
    )
    assert {key: lower_audit[key] for key in behavior_keys} == {
        key: higher_audit[key] for key in behavior_keys
    }


def test_probe_orientation_feedback_matches_generalized_wrench_sign() -> None:
    position = np.array([0.65, 0.20])
    phi = math.radians(-8.0)
    geometry = _nominal_geometry_from_first_pose(position, phi)
    start_q = geometry.estimate_q(
        np.array([position[0], 0.0, position[1]]),
        np.array(
            [
                [math.cos(phi), 0.0, -math.sin(phi)],
                [0.0, 1.0, 0.0],
                [math.sin(phi), 0.0, math.cos(phi)],
            ]
        ),
    )
    time_s = 3.625
    duration_s = 8.0
    entry_duration = 0.35 * duration_s
    excitation_duration = 0.45 * duration_s
    normalized = (time_s - entry_duration) / excitation_duration
    phase = 2.0 * math.pi * normalized
    phase_rate = 2.0 * math.pi / excitation_duration
    window = math.sin(math.pi * normalized) ** 2
    window_rate = (
        math.pi * math.sin(2.0 * math.pi * normalized) / excitation_duration
    )
    target_q = start_q + np.radians([20.0, 20.0]) + np.radians(
        [
            8.0 * math.sin(phase) * window,
            7.0 * math.sin(2.0 * phase) * window,
        ]
    )
    target_phi_error = float(target_q[0] - target_q[1] - phi)
    target_dq = np.radians(
        [
            8.0
            * (
                math.cos(phase) * phase_rate * window
                + math.sin(phase) * window_rate
            ),
            7.0
            * (
                math.cos(2.0 * phase) * 2.0 * phase_rate * window
                + math.sin(2.0 * phase) * window_rate
            ),
        ]
    )
    target_phi_dot_error = float(target_dq[0] - target_dq[1])
    orientation_feedback = 70.0 * target_phi_error + 6.0 * target_phi_dot_error
    _, moment = _probe_wrench(
        time_s,
        position,
        phi,
        np.zeros(2),
        0.0,
        geometry,
        start_q,
        duration_s,
    )
    assert moment * orientation_feedback < 0.0
    torque = _wrench_to_generalized(geometry, start_q, np.zeros(2), moment)
    assert float(np.array([1.0, -1.0]) @ torque) * orientation_feedback > 0.0
