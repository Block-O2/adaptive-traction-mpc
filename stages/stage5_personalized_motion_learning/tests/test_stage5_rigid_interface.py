from __future__ import annotations

import json
import math

import numpy as np
import pytest

from traction_mpc_stage5.calibration import _analytical_tables, load_candidate_config
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.plant import Stage5SpringDamperPlant


def test_candidate_damping_is_derived_from_registered_effective_mass() -> None:
    config = load_candidate_config()
    zeta = config["damping_design"]["target_zeta"]
    mass = np.asarray(config["damping_design"]["translation_effective_mass_kg"])
    for candidate in config["translation_candidates"]:
        expected = 2.0 * zeta * np.sqrt(candidate["stiffness_n_m"] * mass)
        np.testing.assert_allclose(candidate["damping_ns_m"], expected, rtol=1.0e-8)
    inertia = config["damping_design"]["rotation_effective_inertia_kg_m2"]
    for candidate in config["rotation_candidates"]:
        expected = 2.0 * zeta * math.sqrt(candidate["stiffness_nm_rad"] * inertia)
        assert candidate["damping_nms_rad"] == pytest.approx(expected, rel=1.0e-8)


def test_selected_interface_has_requested_rigid_surrogate_scale() -> None:
    np.testing.assert_allclose(STAGE5_RIGID_INTERFACE.translation_stiffness_n_m, [25000.0] * 3)
    tables = _analytical_tables(load_candidate_config())
    selected = next(item for item in tables["translation"] if item["name"] == "Kt_25k")
    assert selected["force_n_at_displacement_mm"]["1.0"] == pytest.approx(25.0)
    assert selected["deformation_mm_at_force_n"]["50.0"] == pytest.approx(2.0)
    assert selected["deformation_mm_at_stage4_gate_force_n"] == pytest.approx(8.0)
    assert STAGE5_RIGID_INTERFACE.rotation_stiffness_nm_rad == pytest.approx(320.0)
    assert STAGE5_RIGID_INTERFACE.rotation_damping_nms_rad == pytest.approx(10.02820618)
    assert 320.0 * math.radians(1.0) == pytest.approx(5.58505360638)


def test_geometry_v2_declares_v1_geometry_unchanged_and_human_passive_mechanics_hold() -> None:
    payload = json.loads(
        (STAGE5_ROOT / "configs" / "stage5_geometry_mechanics_v2.json").read_text()
    )
    assert payload["geometry_source"] == "stage5_geometry_mechanics_v1.json"
    assert payload["geometry_unchanged"] is True
    assert payload["frames_unchanged"]["cuff_fraction_from_knee"] == pytest.approx(0.72)
    assert STAGE5_HUMAN.passive_stiffness_nm_rad == (10.0, 10.0)
    assert STAGE5_HUMAN.passive_damping_nms_rad == (5.0, 5.0)
    assert payload["new_clinical_or_rl_threshold"] is None
    assert payload["plant_release"] == "Stage-5 Plant v1"


def test_selected_interface_reset_has_no_geometric_preload() -> None:
    plant = Stage5SpringDamperPlant()
    observation = plant.reset(np.radians([45.0, 84.0]))
    interface = plant._evaluate_current_interface()
    assert np.linalg.norm(interface.displacement_human_m) < 1.0e-9
    assert np.linalg.norm(interface.rotation_error_human_rad) < 1.0e-9
    assert np.linalg.norm(observation.cuff_force_vector_n) < 1.0e-5
    assert plant.warning_counts() == {}
