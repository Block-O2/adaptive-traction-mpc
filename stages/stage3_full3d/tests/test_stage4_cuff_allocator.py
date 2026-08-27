from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.cuff_allocator import (
    CuffAwareSagittalAllocator,
    CurrentForceMinimizingAllocator,
    sagittal_allocation_matrix,
    sagittal_null_vector,
)


def test_sagittal_allocation_matrix_matches_explicit_human_v2_formula() -> None:
    q = np.radians([48.0, 60.0])
    q1, q2 = q
    phi = q1 - q2
    l1 = HUMAN.thigh_length_m
    sc = HUMAN.sleeve_center_m
    expected = np.array(
        [
            [
                -l1 * np.sin(q1) - sc * np.sin(phi),
                l1 * np.cos(q1) + sc * np.cos(phi),
                -1.0,
            ],
            [sc * np.sin(phi), -sc * np.cos(phi), 1.0],
        ]
    )
    np.testing.assert_allclose(sagittal_allocation_matrix(q, HUMAN), expected)


def test_sagittal_allocation_has_exactly_one_null_direction() -> None:
    for q_deg in ([5.0, 10.0], [48.0, 60.0], [75.0, 90.0]):
        q = np.radians(q_deg)
        matrix = sagittal_allocation_matrix(q, HUMAN)
        null = sagittal_null_vector(q, HUMAN)
        assert np.linalg.matrix_rank(matrix) == 2
        np.testing.assert_allclose(matrix @ null, np.zeros(2), atol=1e-12)
        expected = np.array(
            [
                np.cos(q[0]),
                np.sin(q[0]),
                HUMAN.sleeve_center_m * np.sin(q[1]),
            ]
        )
        np.testing.assert_allclose(null, expected, atol=1e-12)


def test_current_allocator_minimizes_force_along_exact_feasible_line() -> None:
    q = np.radians([48.0, 60.0])
    torque = np.array([43.4, 1.0])
    current = CurrentForceMinimizingAllocator().allocate(torque, q, HUMAN)
    null = sagittal_null_vector(q, HUMAN)
    current_wrench = np.asarray(current["sagittal_wrench"])
    np.testing.assert_allclose(current_wrench[:2] @ null[:2], 0.0, atol=1e-12)
    for alpha in (-50.0, -10.0, 10.0, 50.0):
        alternative = current_wrench + alpha * null
        np.testing.assert_allclose(
            sagittal_allocation_matrix(q, HUMAN) @ alternative,
            torque,
            atol=1e-12,
        )
        assert np.linalg.norm(alternative[:2]) > current["force_norm_n"]


def test_cuff_aware_allocator_preserves_torque_and_reduces_surface_proxy() -> None:
    q = np.radians([48.0, 60.0])
    torque = np.array([43.4, 1.0])
    current = CurrentForceMinimizingAllocator().allocate(torque, q, HUMAN)
    cuff_aware = CuffAwareSagittalAllocator().allocate(torque, q, HUMAN)
    assert current["equality_residual_nm"] < 1e-12
    assert cuff_aware["equality_residual_nm"] < 1e-12
    np.testing.assert_allclose(
        sagittal_allocation_matrix(q, HUMAN)
        @ np.asarray(cuff_aware["sagittal_wrench"]),
        torque,
        atol=1e-12,
    )
    assert cuff_aware["force_norm_n"] > current["force_norm_n"]
    assert abs(cuff_aware["sagittal_wrench"][2]) < abs(
        current["sagittal_wrench"][2]
    )
    assert (
        cuff_aware["cylindrical_surface_effort_n"]
        < current["cylindrical_surface_effort_n"]
    )
    assert (
        cuff_aware["maximum_local_patch_force_proxy_n"]
        < current["maximum_local_patch_force_proxy_n"]
    )
