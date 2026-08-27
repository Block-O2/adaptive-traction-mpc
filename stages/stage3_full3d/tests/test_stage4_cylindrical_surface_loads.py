from __future__ import annotations

import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    SHANK_RADIUS_M,
    SLEEVE_OUTER_RADIUS_M,
    build_coupled_model_xml,
)
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
    build_rigid_cylindrical_surface_model_xml,
)


def test_registered_grid_has_four_axial_by_four_circumferential_patches() -> None:
    config = CylindricalSurfaceConfig(0.080)
    assert config.patch_count == 16
    np.testing.assert_allclose(config.axial_offsets_m, [-0.03, -0.01, 0.01, 0.03])
    np.testing.assert_allclose(
        np.degrees(config.circumferential_angles_rad), [0.0, 90.0, 180.0, 270.0]
    )
    positions = config.patch_positions_grid_cuff_m
    assert positions.shape == (4, 4, 3)
    np.testing.assert_allclose(
        np.linalg.norm(positions[:, :, 1:], axis=2), SHANK_RADIUS_M
    )
    np.testing.assert_allclose(
        np.mean(config.patch_positions_cuff_m, axis=0), 0.0, atol=1e-15
    )


def test_cylindrical_wrench_map_is_full_rank_with_expected_nullity() -> None:
    model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    assert model.wrench_map.shape == (6, 48)
    assert model.rank == 6
    assert model.nullity == 42


def test_full_six_dimensional_wrench_is_reproduced_including_axial_moment() -> None:
    model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    requested = np.array([31.0, -17.0, 23.0, 4.5, 21.0, -8.0])
    result = model.decompose(requested)
    np.testing.assert_allclose(result.reproduced_wrench_cuff, requested, atol=1e-12)
    np.testing.assert_allclose(result.residual_wrench_cuff, 0.0, atol=1e-12)


def test_uniform_minimum_norm_solution_matches_symmetric_closed_form() -> None:
    config = CylindricalSurfaceConfig(0.100)
    model = CylindricalSurfaceLoadModel(config)
    wrench = np.array([20.0, 12.0, -8.0, 3.0, 25.0, -10.0])
    positions = config.patch_positions_cuff_m
    moment_information = sum(
        float(position @ position) * np.eye(3) - np.outer(position, position)
        for position in positions
    )
    beta = np.linalg.solve(moment_information, wrench[3:])
    expected = wrench[:3] / config.patch_count + np.cross(beta, positions)
    result = model.decompose(wrench)
    np.testing.assert_allclose(result.patch_forces_cuff_n, expected, atol=1e-12)


def test_solution_is_minimum_norm_in_the_42_dimensional_nullspace() -> None:
    model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    result = model.decompose(np.array([8.0, -4.0, 5.0, 2.0, 18.0, 7.0]))
    _, _, right_vectors = np.linalg.svd(model.wrench_map, full_matrices=True)
    null_vector = right_vectors[model.rank]
    base = result.patch_forces_cuff_n.reshape(-1)
    alternative = base + 10.0 * null_vector
    np.testing.assert_allclose(
        model.wrench_map @ alternative,
        model.wrench_map @ base,
        atol=1e-12,
    )
    assert np.linalg.norm(alternative) > np.linalg.norm(base)


def test_sagittal_moment_local_force_decreases_with_cuff_length() -> None:
    moment_nm = 24.823115031721663
    maxima = []
    for length_m in (0.060, 0.080, 0.100, 0.120):
        model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(length_m))
        forces = model.decompose(
            np.array([0.0, 0.0, 0.0, 0.0, moment_nm, 0.0])
        ).patch_forces_cuff_n
        maxima.append(float(np.max(np.linalg.norm(forces, axis=1))))
    assert all(
        left > right
        for left, right in zip(maxima[:-1], maxima[1:], strict=True)
    )


def test_visual_cylinder_retains_rigid_weld_and_no_dynamic_change() -> None:
    config = CylindricalSurfaceConfig(0.120)
    xml = build_rigid_cylindrical_surface_model_xml(config=config)
    root = ET.fromstring(xml)
    welds = root.findall(".//equality/weld")
    assert [weld.get("name") for weld in welds] == ["sleeve_connection"]
    assert root.findall(".//equality/connect") == []
    visual = root.find(".//geom[@name='sleeve_geom']")
    assert visual is not None
    coordinates = np.fromstring(visual.get("fromto", ""), sep=" ")
    np.testing.assert_allclose(coordinates[3] - coordinates[0], config.cuff_length_m)
    assert float(visual.get("size", "nan")) == SLEEVE_OUTER_RADIUS_M
    assert visual.get("contype") == "0"
    assert visual.get("conaffinity") == "0"

    baseline = mujoco.MjModel.from_xml_string(build_coupled_model_xml())
    cylindrical = mujoco.MjModel.from_xml_string(xml)
    for name in (
        "body_mass",
        "body_inertia",
        "body_ipos",
        "body_iquat",
        "dof_damping",
        "dof_armature",
        "dof_frictionloss",
        "jnt_range",
        "actuator_gear",
        "actuator_forcerange",
        "eq_data",
        "qpos0",
    ):
        np.testing.assert_array_equal(getattr(cylindrical, name), getattr(baseline, name))
