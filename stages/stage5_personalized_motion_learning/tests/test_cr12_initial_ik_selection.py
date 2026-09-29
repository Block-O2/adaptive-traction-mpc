from __future__ import annotations

import numpy as np

from traction_mpc_stage5.cr12_plant import _select_initial_cr12_ik_candidate


def test_exact_tie_uses_nominal_posture_distance() -> None:
    candidates = [np.array([2.0, 0.0]), np.array([-1.0, 0.0])]
    result = _select_initial_cr12_ik_candidate(candidates, [0.3, 0.3], np.zeros(2))
    np.testing.assert_array_equal(result, candidates[1])


def test_near_tie_is_independent_of_candidate_order() -> None:
    candidates = [np.array([2.0, 0.0]), np.array([-1.0, 0.0])]
    scores = [0.3 + 2.0e-15, 0.3]
    for order in ((0, 1), (1, 0)):
        result = _select_initial_cr12_ik_candidate(
            [candidates[i] for i in order], [scores[i] for i in order], np.zeros(2)
        )
        np.testing.assert_array_equal(result, candidates[1])


def test_clear_primary_winner_is_unchanged() -> None:
    candidates = [np.array([2.0, 0.0]), np.array([-1.0, 0.0])]
    result = _select_initial_cr12_ik_candidate(candidates, [0.31, 0.3], np.zeros(2))
    np.testing.assert_array_equal(result, candidates[0])


def test_exact_secondary_tie_uses_lexicographic_branch_key() -> None:
    candidates = [np.array([1.0, 0.0]), np.array([-1.0, 0.0])]
    for order in ((0, 1), (1, 0)):
        result = _select_initial_cr12_ik_candidate(
            [candidates[i] for i in order], [0.3, 0.3], np.zeros(2)
        )
        np.testing.assert_array_equal(result, candidates[1])
