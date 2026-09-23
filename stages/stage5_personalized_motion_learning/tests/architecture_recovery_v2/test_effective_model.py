from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from traction_mpc_stage5.architecture_recovery_v2 import effective_model
from traction_mpc_stage5.architecture_recovery_v2.effective_model import (
    OnlineEffectiveDynamicsIdentifier,
    build_planar_geometry,
    fit_effective_geometry,
)


def test_geometry_fit_recovers_control_effective_tuple_not_l2_or_fraction() -> None:
    hip = np.array([0.07, 0.10])
    l1 = 0.46
    l2 = 0.42
    cuff_fraction = 0.64
    sc = l2 * cuff_fraction
    q1 = np.radians(np.linspace(8.0, 58.0, 180))
    q2 = np.radians(18.0 + 10.0 * np.sin(np.linspace(0.0, 2.2, len(q1))))
    phi = q1 - q2
    position = (
        hip
        + l1 * np.column_stack([np.cos(q1), np.sin(q1)])
        + sc * np.column_stack([np.cos(phi), np.sin(phi)])
    )

    fit = fit_effective_geometry(position, phi)
    assert fit.accepted, fit.record()
    np.testing.assert_allclose(fit.hip_xz_m, hip, atol=2.0e-3)
    assert abs(fit.thigh_length_m - l1) < 2.0e-3
    assert abs(fit.knee_to_cuff_m - sc) < 2.0e-3
    assert "L2" in fit.record()["representation"]

    geometry = build_planar_geometry(fit)
    recovered = geometry.estimate_q(
        np.array([position[-1, 0], 0.0, position[-1, 1]]),
        np.array(
            [
                [np.cos(phi[-1]), 0.0, -np.sin(phi[-1])],
                [0.0, 1.0, 0.0],
                [np.sin(phi[-1]), 0.0, np.cos(phi[-1])],
            ]
        ),
    )
    np.testing.assert_allclose(recovered, [q1[-1], q2[-1]], atol=4.0e-3)


def test_dynamics_identifier_uses_only_regressor_and_applied_torque() -> None:
    rng = np.random.default_rng(7)
    truth = nominal_base_parameters() * np.array(
        [1.12, 0.91, 1.08, 1.06, 0.94, 1.18, 0.86, 1.05, 0.92, 1.10, 0.89]
    )
    identifier = OnlineEffectiveDynamicsIdentifier(
        minimum_samples=40, update_interval=10, smoothing_alpha=0.5
    )
    prior_error = np.linalg.norm(identifier.beta - truth)
    for _ in range(220):
        q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
        dq = rng.uniform(-0.8, 0.8, size=2)
        ddq = rng.uniform(-2.0, 2.0, size=2)
        row = dynamic_regressor_row(q, dq, ddq)
        identifier.observe(q, dq, ddq, row @ truth)
    assert identifier.accepted_updates > 0
    assert np.linalg.norm(identifier.beta - truth) < prior_error
    assert identifier.record()["truth_consumed"] is False
    assert identifier.record()["minimum_mass_matrix_eigenvalue_required"] == 0.03


def test_task_recency_window_is_causal_bounded_and_keeps_current_beta() -> None:
    rng = np.random.default_rng(11)
    identifier = OnlineEffectiveDynamicsIdentifier(
        minimum_samples=40, update_interval=10, smoothing_alpha=0.5
    )
    truth = nominal_base_parameters() * 1.05
    for _ in range(120):
        q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
        dq = rng.uniform(-0.8, 0.8, size=2)
        ddq = rng.uniform(-2.0, 2.0, size=2)
        row = dynamic_regressor_row(q, dq, ddq)
        identifier.observe(q, dq, ddq, row @ truth)
    beta_before = identifier.beta.copy()

    identifier.enable_recency_window(60)
    np.testing.assert_array_equal(identifier.beta, beta_before)
    assert len(identifier.rows) == 60
    for _ in range(25):
        q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
        dq = rng.uniform(-0.8, 0.8, size=2)
        ddq = rng.uniform(-2.0, 2.0, size=2)
        row = dynamic_regressor_row(q, dq, ddq)
        identifier.observe(q, dq, ddq, row @ truth)
    assert len(identifier.rows) == 60
    assert len(identifier.targets) == 60
    assert identifier.record()["maximum_history_samples"] == 60


def test_bound_limited_dimension_is_frozen_before_conditional_refit() -> None:
    rng = np.random.default_rng(19)
    prior = nominal_base_parameters()
    truth = prior * np.array(
        [1.10, 0.92, 1.07, 1.08, 0.91, 1.16, 0.88, 1.0, 0.90, 1.12, 0.87]
    )
    # Force rho1 beyond the registered identification box while leaving the
    # remaining control-effective dimensions informative.
    truth[7] = -6.0
    identifier = OnlineEffectiveDynamicsIdentifier(
        minimum_samples=40, update_interval=10, smoothing_alpha=0.5
    )
    for _ in range(300):
        q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
        dq = rng.uniform(-0.8, 0.8, size=2)
        ddq = rng.uniform(-2.0, 2.0, size=2)
        row = dynamic_regressor_row(q, dq, ddq)
        identifier.observe(q, dq, ddq, row @ truth)
    diagnostics = identifier.record()["last_attempt_diagnostics"]
    assert identifier.accepted_updates > 0
    assert "rho1_stiffness_rest_combination" in diagnostics[
        "frozen_bound_parameter_names"
    ]
    assert identifier.beta[7] == prior[7]
    assert diagnostics["trusted_candidate_residual_rms_nm"] <= (
        diagnostics["old_residual_rms_nm"] + 0.02
    )


def test_below_floor_inertia_is_frozen_while_other_terms_are_refit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(29)
    prior = nominal_base_parameters()
    truth = prior.copy()
    truth[3:] *= np.array([1.06, 0.95, 1.08, 0.93, 1.04, 0.96, 1.07, 0.94])
    identifier = OnlineEffectiveDynamicsIdentifier(
        minimum_samples=40,
        update_interval=40,
        smoothing_alpha=0.5,
    )
    for _ in range(39):
        q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
        dq = rng.uniform(-0.8, 0.8, size=2)
        ddq = rng.uniform(-2.0, 2.0, size=2)
        row = dynamic_regressor_row(q, dq, ddq)
        identifier.rows.append(row)
        identifier.targets.append(row @ truth)

    bad = truth.copy()
    bad[:3] = prior[:3] * np.array([0.60, 1.40, 1.60])

    class Solution:
        def __init__(self, x: np.ndarray) -> None:
            self.x = x
            self.success = True

    def forced_solver(
        matrix: np.ndarray,
        target: np.ndarray,
        *,
        bounds: tuple[np.ndarray, np.ndarray],
        method: str,
        lsmr_tol: str,
    ) -> Solution:
        del target, method, lsmr_tol
        column_count = matrix.shape[1]
        if column_count == len(prior):
            return Solution((bad - prior) / identifier.span)
        assert column_count == len(prior) - 3
        return Solution((truth[3:] - prior[3:]) / identifier.span[3:])

    monkeypatch.setattr(effective_model, "lsq_linear", forced_solver)
    q = rng.uniform(np.radians([7.0, 12.0]), np.radians([72.0, 92.0]))
    dq = rng.uniform(-0.8, 0.8, size=2)
    ddq = rng.uniform(-2.0, 2.0, size=2)
    row = dynamic_regressor_row(q, dq, ddq)
    diagnostics = identifier.observe(
        q,
        dq,
        ddq,
        row @ truth,
    )

    assert diagnostics["accepted"], diagnostics
    assert diagnostics["frozen_mass_margin_parameter_names"] == list(
        DYNAMIC_BASE_PARAMETER_NAMES[:3]
    )
    np.testing.assert_array_equal(identifier.beta[:3], prior[:3])
    assert np.linalg.norm(identifier.beta[3:] - prior[3:]) > 0.0
    assert diagnostics["minimum_mass_matrix_eigenvalue"] >= 0.03
