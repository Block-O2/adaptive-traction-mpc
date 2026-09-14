from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE4_P1_INTERFACE, STAGE5_STIFF_INTERFACE
from traction_mpc_stage5.validation import _static_mechanics


def test_stage5_interface_is_four_times_stiffer_with_consistent_damping_scaling() -> None:
    old_k = np.asarray(STAGE4_P1_INTERFACE.translation_stiffness_n_m)
    new_k = np.asarray(STAGE5_STIFF_INTERFACE.translation_stiffness_n_m)
    old_d = np.asarray(STAGE4_P1_INTERFACE.translation_damping_ns_m)
    new_d = np.asarray(STAGE5_STIFF_INTERFACE.translation_damping_ns_m)
    np.testing.assert_allclose(new_k / old_k, 4.0)
    np.testing.assert_allclose(new_d / old_d, 2.0)
    assert STAGE5_STIFF_INTERFACE.rotation_stiffness_nm_rad / STAGE4_P1_INTERFACE.rotation_stiffness_nm_rad == 4.0
    assert STAGE5_STIFF_INTERFACE.rotation_damping_nms_rad / STAGE4_P1_INTERFACE.rotation_damping_nms_rad == 2.0


def test_small_perturbation_force_and_deformation_scale() -> None:
    old = _static_mechanics(STAGE4_P1_INTERFACE)
    new = _static_mechanics(STAGE5_STIFF_INTERFACE)
    assert old["force_norm_from_1mm_x_perturbation_n"] == pytest.approx(0.5)
    assert new["force_norm_from_1mm_x_perturbation_n"] == pytest.approx(2.0)
    assert old["static_deformation_mm_at_force_n"]["50.0"] == pytest.approx([100.0] * 3)
    assert new["static_deformation_mm_at_force_n"]["50.0"] == pytest.approx([25.0] * 3)


def test_human_joint_passive_mechanics_are_not_conflated_with_interface_stiffness() -> None:
    assert STAGE5_HUMAN.passive_stiffness_nm_rad == HUMAN.passive_stiffness_nm_rad == (10.0, 10.0)
    assert STAGE5_HUMAN.passive_damping_nms_rad == HUMAN.passive_damping_nms_rad == (5.0, 5.0)
