from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.config import STAGE5_CONFIG
from traction_mpc_stage5.safety_hooks import ExplorationSafetyObservation


def test_safety_contract_preserves_stage4_target_without_inventing_stage5_threshold() -> None:
    safety = STAGE5_CONFIG["safety"]
    assert safety["stage4_engineering_force_target_n_unchanged"] == 200.0
    assert safety["stage5_exploration_stop_threshold_n"] is None
    assert set(safety["available_existing_layers"]) == {
        "executable screening",
        "Safety Filter",
        "BRAKE",
    }


def test_observation_hook_validates_physical_signal_shapes() -> None:
    sample = ExplorationSafetyObservation(
        physical_cuff_force_n=np.zeros(3),
        physical_cuff_force_slew_n_s=np.zeros(3),
        interface_deformation_m=np.zeros(3),
        cuff_position_error_m=np.zeros(3),
        cuff_rotation_error_rad=np.zeros(3),
        executable_screening_status="AVAILABLE",
        safety_filter_status="AVAILABLE",
        brake_status="AVAILABLE",
    )
    assert sample.physical_cuff_force_n.shape == (3,)
    with pytest.raises(ValueError):
        ExplorationSafetyObservation(
            physical_cuff_force_n=np.zeros(2),
            physical_cuff_force_slew_n_s=np.zeros(3),
            interface_deformation_m=np.zeros(3),
            cuff_position_error_m=np.zeros(3),
            cuff_rotation_error_rad=np.zeros(3),
            executable_screening_status="AVAILABLE",
            safety_filter_status="AVAILABLE",
            brake_status="AVAILABLE",
        )
