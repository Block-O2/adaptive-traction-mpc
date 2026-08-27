from __future__ import annotations

import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import build_coupled_model_xml
from traction_mpc_stage4.surface_loads import (
    ACHIEVABLE_WRENCH_ROWS,
    FiniteSurfaceConfig,
    FiniteSurfaceLoadModel,
    build_rigid_finite_surface_model_xml,
)


def test_collinear_patch_wrench_map_has_rank_five_and_no_axial_moment() -> None:
    model = FiniteSurfaceLoadModel(FiniteSurfaceConfig(0.080))
    assert model.rank == 5
    assert model.nullity == 7
    np.testing.assert_array_equal(model.wrench_map[3], np.zeros(12))


def test_decomposition_exactly_reproduces_achievable_wrench_only() -> None:
    model = FiniteSurfaceLoadModel(FiniteSurfaceConfig(0.080))
    requested = np.array([31.0, -17.0, 23.0, 4.5, 21.0, -8.0])
    result = model.decompose(requested)
    np.testing.assert_allclose(
        result.reproduced_wrench_cuff[ACHIEVABLE_WRENCH_ROWS],
        requested[ACHIEVABLE_WRENCH_ROWS],
        atol=1e-12,
    )
    np.testing.assert_allclose(result.reproduced_wrench_cuff[3], 0.0, atol=1e-14)
    np.testing.assert_allclose(
        result.residual_wrench_cuff,
        [0.0, 0.0, 0.0, 4.5, 0.0, 0.0],
        atol=1e-12,
    )


def test_uniform_minimum_norm_solution_matches_closed_form() -> None:
    config = FiniteSurfaceConfig(0.100)
    model = FiniteSurfaceLoadModel(config)
    wrench = np.array([20.0, 12.0, -8.0, 0.0, 25.0, -10.0])
    result = model.decompose(wrench)
    offsets = config.patch_offsets_m
    offset_energy = float(offsets @ offsets)
    expected = np.zeros((4, 3))
    expected[:, 0] = wrench[0] / 4.0
    expected[:, 1] = wrench[1] / 4.0 + offsets * wrench[5] / offset_energy
    expected[:, 2] = wrench[2] / 4.0 - offsets * wrench[4] / offset_energy
    np.testing.assert_allclose(result.patch_forces_cuff_n, expected, atol=1e-12)


def test_solution_is_minimum_norm_among_equivalent_patch_loads() -> None:
    model = FiniteSurfaceLoadModel(FiniteSurfaceConfig(0.080))
    result = model.decompose(np.array([8.0, -4.0, 5.0, 0.0, 18.0, 7.0]))
    _, _, right_vectors = np.linalg.svd(model.achievable_map, full_matrices=True)
    null_vector = right_vectors[model.rank]
    base = result.patch_forces_cuff_n.reshape(-1)
    alternative = base + 10.0 * null_vector
    np.testing.assert_allclose(
        model.achievable_map @ alternative,
        model.achievable_map @ base,
        atol=1e-12,
    )
    assert np.linalg.norm(alternative) > np.linalg.norm(base)


def test_pure_sagittal_moment_outer_patch_force_scales_as_inverse_length() -> None:
    moment_nm = 24.823115031721663
    observed = []
    for length_m in (0.060, 0.080, 0.100, 0.120):
        model = FiniteSurfaceLoadModel(FiniteSurfaceConfig(length_m))
        forces = model.decompose(
            np.array([0.0, 0.0, 0.0, 0.0, moment_nm, 0.0])
        ).patch_forces_cuff_n
        outer_force = float(np.linalg.norm(forces[0]))
        np.testing.assert_allclose(outer_force, 1.2 * moment_nm / length_m)
        observed.append(outer_force)
    np.testing.assert_allclose(
        np.asarray(observed) * np.array([0.060, 0.080, 0.100, 0.120]),
        1.2 * moment_nm,
    )


def test_visual_length_changes_without_replacing_the_validated_rigid_weld() -> None:
    config = FiniteSurfaceConfig(0.120)
    root = ET.fromstring(build_rigid_finite_surface_model_xml(config=config))
    welds = root.findall(".//equality/weld")
    assert [weld.get("name") for weld in welds] == ["sleeve_connection"]
    assert root.findall(".//equality/connect") == []
    visual = root.find(".//geom[@name='sleeve_geom']")
    assert visual is not None
    coordinates = np.fromstring(visual.get("fromto", ""), sep=" ")
    np.testing.assert_allclose(coordinates[3] - coordinates[0], config.cuff_length_m)
    assert visual.get("contype") == "0"
    assert visual.get("conaffinity") == "0"


def test_visual_length_does_not_change_model_dynamics_or_equality_data() -> None:
    baseline = mujoco.MjModel.from_xml_string(build_coupled_model_xml())
    finite_surface = mujoco.MjModel.from_xml_string(
        build_rigid_finite_surface_model_xml(config=FiniteSurfaceConfig(0.060))
    )
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
        np.testing.assert_array_equal(getattr(finite_surface, name), getattr(baseline, name))
