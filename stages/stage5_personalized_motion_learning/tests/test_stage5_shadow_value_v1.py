from __future__ import annotations

import numpy as np

from traction_mpc_stage5.shadow_value import (
    FailurePenaltySpec,
    FeatureMatrix,
    fit_ridge_value_model,
    paired_ranking_metrics,
    remaining_trapezoid_return,
    trajectory_split_is_disjoint,
)


def test_remaining_return_uses_measured_force_trapezoid_and_zero_completion() -> None:
    time = np.asarray([0.0, 1.0, 2.0])
    force = np.asarray([[3.0, 4.0, 0.0]] * 3)
    result = remaining_trapezoid_return(time, force)
    np.testing.assert_allclose(result, [10.0, 5.0, 0.0])


def test_failed_episode_receives_nonzero_pessimistic_terminal_penalty() -> None:
    spec = FailurePenaltySpec()
    outbound = spec.terminal_penalty_n_s("OUTBOUND", 2.0)
    late_return = spec.terminal_penalty_n_s("RETURN", 9.9)
    assert outbound == 5600.0
    assert late_return == 2000.0
    result = remaining_trapezoid_return(
        np.asarray([0.0, 1.0]),
        np.zeros((2, 3)),
        terminal_penalty_n_s=late_return,
    )
    np.testing.assert_allclose(result, [2000.0, 2000.0])


def test_split_is_by_disjoint_complete_rollout_identity() -> None:
    assert trajectory_split_is_disjoint(
        {"train": ["a"], "validation": ["b"], "test": ["c"]}
    )
    assert not trajectory_split_is_disjoint(
        {"train": ["a"], "validation": ["a"], "test": ["c"]}
    )


def test_ood_prediction_is_nan_not_an_attractive_low_value() -> None:
    matrix = FeatureMatrix(
        np.asarray([[0.0], [1.0], [2.0], [3.0]]), ("deployable_state",)
    )
    target = np.asarray([0.0, 1.0, 2.0, 3.0])
    model = fit_ridge_value_model(
        matrix,
        target,
        np.asarray(["episode"] * 4),
        alpha=0.01,
        feature_kind="candidate",
        support_abs_z_limit=2.0,
    )
    guarded, supported, distance = model.predict(
        FeatureMatrix(np.asarray([[1.5], [100.0]]), matrix.names)
    )
    assert supported.tolist() == [True, False]
    assert np.isfinite(guarded[0])
    assert np.isnan(guarded[1])
    assert distance[1] > distance[0]


def test_action_path_ranking_is_grouped_by_matched_start_state() -> None:
    result = paired_ranking_metrics(
        predicted_n_s=np.asarray([10.0, 20.0, 5.0, 7.0]),
        observed_n_s=np.asarray([11.0, 21.0, 9.0, 6.0]),
        group_ids=np.asarray(["same-a", "same-a", "same-b", "same-b"]),
        supported=np.asarray([True, True, True, True]),
        minimum_observed_difference_n_s=1.0,
    )
    assert result["pair_count"] == 2
    assert result["correct_pair_count"] == 1
    assert result["ranking_accuracy"] == 0.5


def test_unsupported_branch_pair_is_not_ranked() -> None:
    result = paired_ranking_metrics(
        predicted_n_s=np.asarray([1.0, np.nan]),
        observed_n_s=np.asarray([5.0, 10.0]),
        group_ids=np.asarray(["anchor", "anchor"]),
        supported=np.asarray([True, False]),
        minimum_observed_difference_n_s=1.0,
    )
    assert result["pair_count"] == 0
    assert result["unsupported_pair_count"] == 1
    assert result["ranking_accuracy"] is None
