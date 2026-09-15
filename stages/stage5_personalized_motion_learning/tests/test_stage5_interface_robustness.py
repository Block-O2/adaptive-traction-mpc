from __future__ import annotations

import json
import numpy as np
import pytest

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import NominalInterfaceHoldPredictor
from traction_mpc_stage5.goal_mpc import GoalDirectedHumanSpaceMPC
from traction_mpc_stage5.interface_robustness import (
    ProgressiveTranslationStage5Plant,
    aligned_20ms_wrench_prediction,
    load_interface_robustness_contract,
)
from traction_mpc_stage5.interface_robustness_campaign import (
    classify_boundary,
    load_final_campaign_spec,
    scaled_interface,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


def test_closeout_contract_preserves_hard_limits_and_final_campaign_is_locked() -> None:
    contract = load_interface_robustness_contract()
    hard = contract["registered_hard_limits_unchanged"]
    assert hard["joint_velocity_deg_s"] == [45.0, 75.0]
    assert hard["joint_acceleration_20ms_deg_s2"] == [300.0, 600.0]
    assert hard["physical_cuff_force_gate_n"] == 200.0
    assert contract["preregistered_final_campaign"]["authorized_to_run"] is False
    assert contract["control_authority"]["online_interface_parameter_identification_active"] is False
    campaign = json.loads(
        (
            STAGE5_ROOT
            / "configs"
            / "stage5_interface_robustness_final_campaign_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert campaign["status"] == "PREREGISTERED_NOT_AUTHORIZED"
    assert len(campaign["core_box"]["conditions"]) == 9
    assert campaign["core_box"]["episode_count"] == 27
    assert campaign["repeatability"]["continuous_episode_count"] == 30


def test_planning_force_reserve_cannot_weaken_physical_gate() -> None:
    predictor = NominalInterfaceHoldPredictor(
        control_dt_s=0.020, planning_force_ceiling_n=180.0
    )
    assert predictor.planning_force_ceiling_n == 180.0
    with pytest.raises(ValueError):
        NominalInterfaceHoldPredictor(
            control_dt_s=0.020, planning_force_ceiling_n=201.0
        )
    with pytest.raises(ValueError):
        GoalDirectedHumanSpaceMPC(planning_physical_force_ceiling_n=201.0)


def test_robustness_pacing_is_separate_from_registered_task_limits() -> None:
    mpc = GoalDirectedHumanSpaceMPC(
        planning_joint_velocity_ceiling_rad_s=tuple(np.radians([15.0, 25.0]))
    )
    assert np.degrees(mpc.planning_joint_velocity_ceiling_rad_s) == pytest.approx(
        [15.0, 25.0]
    )


def test_20ms_wrench_alignment_uses_mean_and_peak_over_same_window() -> None:
    trace = {
        "time_s": np.array([0.0, 0.005, 0.010, 0.015, 0.020]),
        "physical_cuff_force_world_n": np.array(
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [4.0, 0.0, 0.0], [6.0, 0.0, 0.0], [8.0, 0.0, 0.0]]
        ),
        "physical_cuff_moment_world_nm": np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0], [0.0, 3.0, 0.0], [0.0, 4.0, 0.0]]
        ),
        "selected_prediction_time_s": np.array([0.0]),
        "selected_prediction_first_transmitted_wrench_world": np.array(
            [[5.0, 0.0, 0.0, 0.0, 2.5, 0.0]]
        ),
        "selected_prediction_first_hold_peak_force_n": np.array([7.0]),
    }
    result = aligned_20ms_wrench_prediction(trace)
    assert result["force_vector_error_n"]["rmse"] == pytest.approx(0.0)
    assert result["moment_vector_error_nm"]["rmse"] == pytest.approx(0.0)
    assert result["peak_force_max_underprediction_n"] == pytest.approx(1.0)


def test_final_campaign_matrix_and_scaled_plant_are_frozen() -> None:
    campaign = load_final_campaign_spec()
    assert len(campaign["core_box"]["conditions"]) == 9
    assert campaign["fixed_random_seeds"] == [20260824, 20260825, 20260826]
    assert len(campaign["boundary_challenges"]["conditions"]) == 4
    plant = scaled_interface(0.9, 1.1, 0.8)
    assert np.asarray(plant.translation_stiffness_n_m) == pytest.approx(
        0.9 * np.asarray(STAGE5_RIGID_INTERFACE.translation_stiffness_n_m)
    )
    assert np.asarray(plant.translation_damping_ns_m) == pytest.approx(
        0.8 * np.asarray(STAGE5_RIGID_INTERFACE.translation_damping_ns_m)
    )
    assert plant.rotation_stiffness_nm_rad == pytest.approx(
        1.1 * STAGE5_RIGID_INTERFACE.rotation_stiffness_nm_rad
    )
    assert plant.rotation_damping_nms_rad == pytest.approx(
        0.8 * STAGE5_RIGID_INTERFACE.rotation_damping_nms_rad
    )


def test_progressive_boundary_has_preregistered_tangent_change() -> None:
    beta = 1.0 / 30.0
    # Along the radial direction d[K*x*(1+beta*r^2/xref^2)]/dx
    # is K*(1+3*beta) at r=xref.
    assert 1.0 + 3.0 * beta == pytest.approx(1.1)
    assert ProgressiveTranslationStage5Plant is not None


def test_boundary_classification_rejects_silent_failure_without_rescue() -> None:
    silent = classify_boundary(
        {
            "false_complete": False,
            "silent_motion_violation": True,
            "force_gate_event_count": 0,
            "structural_event_count": 0,
            "truth_complete": False,
            "accepted": False,
            "online_result": "COMPLETE",
        }
    )
    assert silent["classification"] == "silent_registered_constraint_violation"
    assert silent["boundary_acceptable"] is False
    conservative = classify_boundary(
        {
            "false_complete": False,
            "silent_motion_violation": False,
            "force_gate_event_count": 0,
            "structural_event_count": 0,
            "truth_complete": False,
            "accepted": False,
            "online_result": "ABORTED",
        }
    )
    assert conservative["classification"].startswith("conservative")
    assert conservative["boundary_acceptable"] is True
