from __future__ import annotations

import numpy as np

from traction_mpc_stage4.evaluation import (
    Stage4CoupledPlant,
    reconstructed_wrench_human_input_nm,
    run_stage4_case,
)
from traction_mpc_stage4.human_model import registered_moderate_human


def test_registered_moderate_reset_uses_true_sleeve_geometry() -> None:
    human, _ = registered_moderate_human()
    plant = Stage4CoupledPlant(human)
    observation = plant.reset(np.radians([5.0, 10.0]))
    assert observation.weld_position_error_m < 1e-9
    assert observation.weld_rotation_error_rad < 1e-9


def test_short_nominal_fixed_mpc_run_is_finite() -> None:
    summary, trace = run_stage4_case(controller_kind="fixed", true_case="nominal", duration_s=0.10)
    assert summary["completed"]
    assert summary["events"]["mujoco_warning_counts"] == {}
    assert summary["events"]["unintended_contact_pairs"] == []
    assert all(np.all(np.isfinite(value)) for value in trace.values())


def test_reconstructed_wrench_virtual_work_matches_nominal_plant_mapping() -> None:
    plant = Stage4CoupledPlant()
    plant.reset(np.radians([20.0, 45.0]))
    for _ in range(3):
        observation = plant.step()
    mapped = reconstructed_wrench_human_input_nm(
        observation.human_q_rad,
        observation.cuff_force_vector_n,
        observation.cuff_moment_vector_nm,
    )
    np.testing.assert_allclose(mapped, observation.human_wrench_torque_nm, rtol=5e-5, atol=1e-2)
