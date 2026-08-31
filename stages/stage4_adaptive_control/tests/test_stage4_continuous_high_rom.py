from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage3.cuff_adapter import CUFF_ADAPTER
from traction_mpc_stage3.frames import ATTACHMENT_FROM_CUFF
from traction_mpc_stage4.continuous_high_rom import run_continuous_path_audit


def test_adapter_dimensions_are_derived_from_committed_geometry() -> None:
    assert CUFF_ADAPTER.wrist_extent_toward_cuff_from_attachment_m == pytest.approx(
        0.069
    )
    assert CUFF_ADAPTER.modeled_cuff_shell_allowance_m == pytest.approx(0.013)
    assert CUFF_ADAPTER.cuff_center_standoff_m == pytest.approx(0.140)
    assert CUFF_ADAPTER.connector_length_to_cuff_surface_m == pytest.approx(0.082)
    np.testing.assert_allclose(
        ATTACHMENT_FROM_CUFF.translation,
        [0.0, CUFF_ADAPTER.cuff_center_standoff_m, 0.0],
    )


def test_adapter_cuff_site_preserves_the_rigid_weld() -> None:
    plant = CoupledUR10eHumanV2()
    observation = plant.reset(np.radians([5.0, 10.0]))
    assert observation.weld_position_error_m < 1e-10
    assert observation.weld_rotation_error_rad < 1e-10
    assert plant.model.geom(plant.adapter_geom_id).name == "cuff_adapter_geom"


def test_short_dense_audit_removes_overlap_but_retains_bed_finding() -> None:
    result = run_continuous_path_audit(sample_count=7)
    assert result["initial_exact_ik_branch_count"] >= 2
    for path in result["paths"].values():
        assert path["ik_completed"]
        assert path["minimum_clearance_by_domain_m"]["robot_human_m"] > 0.0
        assert path["minimum_clearance_by_domain_m"]["adapter_human_m"] == pytest.approx(
            0.013, abs=1e-9
        )
        assert path["conditional_quasistatic"]["peak_cuff_force_n"] < 200.0
        assert path["collision_intervals"]["robot_bed_m"]
        assert not path["strict_continuous_path_feasible"]

