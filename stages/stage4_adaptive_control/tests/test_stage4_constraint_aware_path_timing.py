from __future__ import annotations

import numpy as np

from traction_mpc_stage4.constraint_aware_path_timing import (
    ConstraintAwarePathTiming,
    PathTimingConfig,
    evidence_derived_common_reserve,
    nominal_high_rom_population_prior_model,
)
from traction_mpc_stage4.high_rom_dynamic_pilot import pilot_trajectories


def _trajectory(name: str):
    return next(item for item in pilot_trajectories() if item.name == name)


def test_common_reserve_is_ceiling_of_worst_same_action_residual() -> None:
    reserve = evidence_derived_common_reserve(
        [69.66357032578831, 46.52120167289699]
    )
    assert reserve == 70.0
    assert PathTimingConfig(prediction_reserve_n=reserve).planning_force_budget_n == 130.0


def test_feasible_nominal_clock_is_not_slowed_or_retuned() -> None:
    trajectory = _trajectory("aggressive_both_120_120")
    planner = ConstraintAwarePathTiming(
        trajectory,
        nominal_high_rom_population_prior_model(),
        config=PathTimingConfig(phase_step_s=0.1),
    )
    assert np.allclose(planner.phase_rate, 1.0)
    assert np.isclose(planner.duration_s, 23.0)
    assert np.max(planner.predicted_force_n) <= 130.0


def test_reference_uses_chain_rule_at_nominal_speed() -> None:
    trajectory = _trajectory("hip_dominant_100_60")
    planner = ConstraintAwarePathTiming(
        trajectory,
        nominal_high_rom_population_prior_model(),
        config=PathTimingConfig(phase_step_s=0.1),
    )
    for time_s in (0.5, 4.2, 13.5, 17.0, 22.5):
        expected = trajectory.reference(time_s)
        actual = planner.reference(time_s)
        assert np.array_equal(actual.q_rad, expected.q_rad)
        assert np.array_equal(actual.dq_rad_s, expected.dq_rad_s)
        assert np.array_equal(actual.ddq_rad_s2, expected.ddq_rad_s2)
        assert np.array_equal(
            actual.world_from_cuff.translation,
            expected.world_from_cuff.translation,
        )
