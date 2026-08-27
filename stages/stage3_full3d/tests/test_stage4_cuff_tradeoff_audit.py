from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.cuff_allocator import (
    CurrentForceMinimizingAllocator,
    cylindrical_surface_mapping,
    sagittal_null_vector,
)
from traction_mpc_stage4.cuff_tradeoff_audit import quadratic_coefficients


def test_exact_quadratics_match_direct_metrics_along_alpha() -> None:
    q = np.radians([48.0, 60.0])
    torque = np.array([43.4, 1.0])
    allocator = CurrentForceMinimizingAllocator()
    allocation = allocator.allocate(torque, q, HUMAN)
    w0 = np.asarray(allocation["sagittal_wrench"])
    null = sagittal_null_vector(q, HUMAN)
    surface_mapping = cylindrical_surface_mapping(
        q, HUMAN, allocator.surface_model
    )
    coefficients = quadratic_coefficients(w0, null, surface_mapping)
    for alpha in (-80.0, -10.0, 0.0, 25.0, 90.0):
        wrench = w0 + alpha * null
        polynomial = np.array([alpha**2, alpha, 1.0])
        np.testing.assert_allclose(
            coefficients["force_squared"] @ polynomial,
            wrench[:2] @ wrench[:2],
        )
        np.testing.assert_allclose(
            coefficients["moment_squared"] @ polynomial,
            wrench[2] ** 2,
        )
        patch = surface_mapping @ wrench
        np.testing.assert_allclose(
            coefficients["surface_squared"] @ polynomial,
            patch @ patch,
        )


def test_minimum_force_origin_has_zero_linear_force_coefficient() -> None:
    q = np.radians([75.0, 90.0])
    torque = np.array([30.0, 6.0])
    allocator = CurrentForceMinimizingAllocator()
    allocation = allocator.allocate(torque, q, HUMAN)
    coefficients = quadratic_coefficients(
        np.asarray(allocation["sagittal_wrench"]),
        sagittal_null_vector(q, HUMAN),
        cylindrical_surface_mapping(q, HUMAN, allocator.surface_model),
    )
    np.testing.assert_allclose(coefficients["force_squared"][0], 1.0)
    np.testing.assert_allclose(coefficients["force_squared"][1], 0.0, atol=1e-12)
