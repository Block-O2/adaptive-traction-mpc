from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage4.statistical_trust import (
    PRIMARY_STATISTICAL_L4,
    StatisticalL4Config,
    paired_difference_bounds,
    paired_promotion_evidence,
)
from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.measurement import ControllerMeasurement, sensor_realism_cases
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case


def test_single_challenger_alpha_spending_is_anytime_and_telescoping() -> None:
    assert PRIMARY_STATISTICAL_L4.scheduled_looks == (8, 12, 16)
    assert PRIMARY_STATISTICAL_L4.challenger_family_alpha(0) == pytest.approx(
        0.05 / 2.0
    )
    assert PRIMARY_STATISTICAL_L4.per_reference_per_look_alpha(0) == pytest.approx(
        0.05 / (2.0 * 2.0 * 3.0)
    )
    spent = sum(
        PRIMARY_STATISTICAL_L4.challenger_family_alpha(index)
        for index in range(10000)
    )
    assert spent < 0.05
    assert spent == pytest.approx(0.05, rel=1e-4)


def test_promotion_requires_supported_improvement_over_both_references() -> None:
    candidate = np.zeros(8)
    prior = np.ones(8)
    last = np.ones(8)
    evidence = paired_promotion_evidence(
        candidate,
        prior,
        last,
        config=PRIMARY_STATISTICAL_L4,
    )
    assert evidence["promotion_supported"]
    assert evidence["against_population_prior"]["upper_bound_nms2"] < 0.0
    assert evidence["against_last_valid"]["upper_bound_nms2"] < 0.0

    not_better_than_last = paired_promotion_evidence(
        candidate,
        prior,
        -np.ones(8),
        config=PRIMARY_STATISTICAL_L4,
    )
    assert not not_better_than_last["promotion_supported"]
    assert not_better_than_last[
        "statistically_worse_than_at_least_one_reference"
    ]


def test_hac_uses_block_series_and_inflates_for_positive_serial_correlation() -> None:
    values = np.array([-2.0, -1.8, -1.6, -1.4, 1.4, 1.6, 1.8, 2.0])
    independent = StatisticalL4Config(name="lag0", hac_lag_blocks=0)
    correlated = StatisticalL4Config(name="lag2", hac_lag_blocks=2)
    iid_like = paired_difference_bounds(values, config=independent)
    hac = paired_difference_bounds(values, config=correlated)
    assert hac["sample_unit"] == "nonoverlapping_clean_integral_block"
    assert hac["standard_error_nms2"] > iid_like["standard_error_nms2"]


def test_moving_block_bootstrap_is_deterministic_and_contiguous_block_based() -> None:
    config = StatisticalL4Config(
        name="bootstrap",
        method="moving_block_bootstrap",
        bootstrap_block_length=2,
        bootstrap_replicates=2000,
        bootstrap_seed=123,
    )
    values = np.array([-1.0, -0.8, -0.9, -0.7, -0.6, -0.5, -0.4, -0.3])
    first = paired_difference_bounds(values, config=config, seed_offset=9)
    second = paired_difference_bounds(values, config=config, seed_offset=9)
    assert first == second
    assert first["bootstrap_block_length"] == 2
    assert first["bootstrap_replicates"] == 2000


def test_evidence_is_only_evaluated_at_pre_registered_looks() -> None:
    with pytest.raises(ValueError, match="scheduled look"):
        paired_difference_bounds(
            np.zeros(9),
            config=PRIMARY_STATISTICAL_L4,
        )


def test_challenger_stream_has_no_task_length_dependent_index_ceiling() -> None:
    evidence = paired_difference_bounds(
        -np.ones(8),
        config=PRIMARY_STATISTICAL_L4,
        challenger_index=100,
    )
    assert evidence["challenger_index"] == 100
    assert evidence["challenger_family_alpha"] == pytest.approx(
        0.05 / (101.0 * 102.0)
    )


def test_negative_challenger_index_is_invalid() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        paired_difference_bounds(
            -np.ones(8),
            config=PRIMARY_STATISTICAL_L4,
            challenger_index=-1,
        )


def test_online_prior_only_adapter_smoke_keeps_population_prior_control() -> None:
    case = sensor_realism_cases()[0]

    def factory(measurement, q_prior):
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
        )

    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    summary, trace = run_sensor_realism_case(
        case,
        duration_s=0.10,
        estimator_architecture="integral_minimal",
        result_case_name="single_challenger_prior_only_smoke",
        reference_execution=execution,
        estimator_factory=factory,
    )
    trust = summary["hierarchical_trust"]
    assert summary["termination_reason"] == "completed"
    assert trust["counts"]["control_promotions"] == 0
    assert trust["superseded_count"] == 0
    assert trust["race_state_count"] == 0
    beta = np.asarray(trace["dynamic_base_estimate"])
    assert np.allclose(beta, beta[0])


def test_online_qualification_applies_only_in_trusted_adaptive_arm(
    monkeypatch,
) -> None:
    measurement = ControllerMeasurement(
        arrival_time_s=0.0,
        sample_time_s=0.0,
        robot_q_rad=np.zeros(6),
        robot_dq_rad_s=np.zeros(6),
        attachment_position_m=np.array([0.3, 0.0, 0.8]),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.zeros(3),
        attachment_angular_velocity_rad_s=np.zeros(3),
        cuff_force_vector_n=np.zeros(3),
        cuff_moment_vector_nm=np.zeros(3),
        new_sample=True,
    )
    q_prior = cold_start_teaching_reference(0.0).q_rad
    estimators = [
        OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=sensor_realism_cases()[0],
            apply_qualified_model=apply,
        )
        for apply in (False, True)
    ]
    prior = estimators[0].dynamic_identifier.population_prior.copy()
    proposed = 0.90 * prior
    regressor = np.zeros((2, len(prior)))
    regressor[:, :2] = np.eye(2)
    target = regressor @ proposed
    blocks = [
        {
            "start_time_s": 1.0 + 0.5 * index,
            "end_time_s": 1.5 + 0.5 * index,
            "regressor": regressor,
            "target": target,
        }
        for index in range(8)
    ]
    monkeypatch.setattr(
        "traction_mpc_stage4.online_trust._validation_blocks",
        lambda *args, **kwargs: blocks,
    )
    for estimator in estimators:
        estimator.active_challenger = {
            "challenger_index": 0,
            "fit_end_time_s": 0.0,
            "minimum_validation_ready_time_s": 0.0,
            "reference_incumbent_epoch": 0,
            "reference_incumbent_beta": prior.tolist(),
            "proposed_model_beta": proposed.tolist(),
            "training_valid_measurement_count": 0,
            "evaluated_look_block_counts": [],
            "evidence_history": [],
            "status": "pending_statistical_evidence",
            "applied_to_control": False,
        }
        estimator.challengers.append(estimator.active_challenger)
        estimator._resolve_challenger(5.0)
        assert estimator.active_challenger is None
        assert estimator.dynamic_identifier.trustworthy_time_s == 5.0

    assert np.allclose(estimators[0].control_beta, prior)
    assert estimators[0].trust_summary()["counts"]["control_promotions"] == 0
    assert np.allclose(estimators[1].control_beta, proposed)
    assert estimators[1].trust_summary()["counts"]["control_promotions"] == 1
