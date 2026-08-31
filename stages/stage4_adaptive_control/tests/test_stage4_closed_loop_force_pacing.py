from __future__ import annotations

import numpy as np

from traction_mpc_stage4.closed_loop_force_pacing import (
    ClosedLoopForcePacingConfig,
    FinalSelectedCommandForcePredictor,
    _position_velocity,
)
from traction_mpc_stage4.constraint_aware_path_timing import (
    nominal_high_rom_population_prior_model,
)
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.high_rom_dynamic_pilot import INITIAL_Q_DEG, pilot_trajectories
from traction_mpc_stage4.force_pacing_audit import _rank_correlation


def _trajectory(name: str):
    return next(item for item in pilot_trajectories() if item.name == name)


def test_vectorized_cuff_kinematics_matches_geometry() -> None:
    model = nominal_high_rom_population_prior_model()
    q = np.radians([[5.0, 10.0], [60.0, 80.0], [100.0, 60.0]])
    dq = np.radians([[1.0, -2.0], [4.0, 3.0], [-1.0, 5.0]])
    position, velocity = _position_velocity(q, dq, model)
    for index in range(len(q)):
        expected_position = model.geometry.cuff_pose(q[index]).translation
        expected_velocity = model.geometry.cuff_velocity(q[index], dq[index])[0]
        assert np.allclose(position[index], expected_position, atol=1e-12)
        assert np.allclose(velocity[index], expected_velocity, atol=1e-12)


def test_continuous_alpha_curve_uses_one_fixed_selected_sequence() -> None:
    trajectory = _trajectory("aggressive_both_120_120")
    model = nominal_high_rom_population_prior_model()
    predictor = FinalSelectedCommandForcePredictor(trajectory)
    alpha = np.linspace(0.5, 1.0, 51)
    result = predictor.evaluate(
        wall_time_s=6.0,
        phase_now_s=6.0,
        current_alpha=1.0,
        alpha_target=alpha,
        state=np.concatenate([np.radians(INITIAL_Q_DEG), np.zeros(2)]),
        selected_sequence=np.zeros((15, 2)),
        model=model,
        allocator=default_engineering_cuff_allocator(),
        prediction_dt_s=0.02,
    )
    assert np.array_equal(result["alpha"], alpha)
    assert np.asarray(result["force_path_n"]).shape == (51, 60)
    assert np.all(np.isfinite(result["peak_force_n"]))
    assert float(result["evaluation_latency_ms"]) >= 0.0


def test_candidate_clock_applies_chain_rule_speed() -> None:
    trajectory = _trajectory("hip_dominant_100_60")
    config = ClosedLoopForcePacingConfig()
    predictor = FinalSelectedCommandForcePredictor(trajectory, config=config)
    offsets = np.array([0.0, 0.1, 0.3, 0.6])
    phase, speed, rate = predictor._candidate_clock(
        7.0, 1.0, np.array([0.5, 1.0]), offsets
    )
    assert np.allclose(speed[1], 1.0)
    assert np.allclose(phase[1], 7.0 + offsets)
    assert np.allclose(speed[0], [1.0, 0.9, 0.7, 0.5])
    assert np.allclose(rate[:, 0], [-1.0, 0.0])


def test_rank_correlation_handles_flat_force_curve_as_monotonic() -> None:
    alpha = np.linspace(0.5, 1.0, 101)
    assert _rank_correlation(alpha, np.ones_like(alpha)) == 1.0
    assert _rank_correlation(alpha, alpha) > 0.999999
    assert _rank_correlation(alpha, -alpha) < -0.999999
