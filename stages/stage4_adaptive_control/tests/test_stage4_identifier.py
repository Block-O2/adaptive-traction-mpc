from __future__ import annotations

import numpy as np

from traction_mpc_stage4.human_model import parameterized_human, step_dynamics
from traction_mpc_stage4.identifier import ESTIMATED_PARAMETER_NAMES, IdentifierConfig, WindowedHumanNLS


def test_windowed_nls_uses_last_valid_model_when_unexcited() -> None:
    config = IdentifierConfig(window_size=20, minimum_samples=10, update_interval=10, max_nfev=20)
    identifier = WindowedHumanNLS(config)
    state = np.radians([5.0, 10.0, 0.0, 0.0])
    action = np.zeros(2)
    for _ in range(10):
        identifier.add_transition(state, action, state)
    assert not identifier.last_diagnostics["accepted"]
    assert identifier.last_diagnostics["last_valid_fallback_used"]
    assert identifier.parameter_estimate()["mass_scale"] == 1.0


def test_windowed_nls_accepts_bounded_update_on_excited_exact_replay() -> None:
    config = IdentifierConfig(window_size=60, minimum_samples=40, update_interval=40, max_nfev=60)
    identifier = WindowedHumanNLS(config)
    true_theta = np.array([1.05, 1.10, np.radians(-2.0)])
    true_human = parameterized_human(true_theta, ESTIMATED_PARAMETER_NAMES)
    rng = np.random.default_rng(7)
    state = np.radians([25.0, 45.0, 4.0, -3.0])
    for _ in range(40):
        action = np.array([40.0, -8.0]) + rng.normal(0.0, [5.0, 2.0])
        next_state = step_dynamics(state, action, config.sample_dt_s, true_human)
        identifier.add_transition(state, action, next_state)
        state = next_state
    assert identifier.last_diagnostics["accepted"]
    estimate = identifier.parameter_estimate()
    assert 1.0 < estimate["mass_scale"] <= 1.0 + 0.05 * (1.20 - 0.85) + 1e-12
    assert estimate["stiffness_scale"] >= 1.0


def test_windowed_nls_rejects_bed_contaminated_window() -> None:
    config = IdentifierConfig(window_size=20, minimum_samples=10, update_interval=10)
    identifier = WindowedHumanNLS(config)
    state = np.radians([25.0, 45.0, 1.0, -1.0])
    for _ in range(10):
        next_state = step_dynamics(
            state,
            np.array([40.0, -8.0]),
            config.sample_dt_s,
            parameterized_human(np.array([1.0, 1.0, 0.0]), ESTIMATED_PARAMETER_NAMES),
        )
        identifier.add_transition(
            state,
            np.tile([40.0, -8.0], (4, 1)),
            next_state,
            bed_contact_fraction=0.10,
        )
        state = next_state
    assert identifier.last_diagnostics["reason"] == "bed_contact_contaminated_window"
    assert identifier.last_diagnostics["last_valid_fallback_used"]
