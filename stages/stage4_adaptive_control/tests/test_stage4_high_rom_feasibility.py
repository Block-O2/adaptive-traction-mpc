from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.high_rom_feasibility import (
    bed_clearances,
    coordinate_description,
    current_rom_valid,
    grid_values_deg,
    human_landmarks,
    static_torque_requirements,
)


def test_high_rom_coordinates_match_frozen_kinematic_chain() -> None:
    description = coordinate_description()
    assert description["absolute_thigh_angle"] == "q1 above world +X"
    assert description["absolute_shank_angle"] == "q1-q2 above world +X"
    landmarks = human_landmarks(np.radians([90.0, 90.0]))
    np.testing.assert_allclose(
        landmarks["knee"], [0.0, 0.0, 0.062 + HUMAN.thigh_length_m], atol=1e-12
    )
    np.testing.assert_allclose(
        landmarks["cuff"],
        [HUMAN.sleeve_center_m, 0.0, 0.062 + HUMAN.thigh_length_m],
        atol=1e-12,
    )


def test_rom_status_is_separate_from_extended_geometry() -> None:
    assert current_rom_valid(np.radians([80.0, 100.0]))
    assert not current_rom_valid(np.radians([90.0, 90.0]))
    assert not current_rom_valid(np.radians([80.0, 120.0]))
    assert min(bed_clearances(np.radians([90.0, 90.0])).values()) >= -1e-12


def test_conditional_static_torque_removes_only_soft_limit_term() -> None:
    q = np.radians([90.0, 120.0])
    torque = static_torque_requirements(q)
    np.testing.assert_allclose(
        torque["current_nm"],
        torque["without_soft_limit_nm"] - torque["soft_limit_rhs_nm"],
        atol=1e-12,
    )
    assert np.linalg.norm(torque["soft_limit_rhs_nm"]) > np.linalg.norm(
        torque["without_soft_limit_nm"]
    )


def test_grid_is_broad_and_refined_at_high_rom() -> None:
    values = grid_values_deg()
    assert values[0] == 0.0 and values[-1] == 120.0
    assert {85.0, 95.0, 105.0, 115.0} <= set(values)
