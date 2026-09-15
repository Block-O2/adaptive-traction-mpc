from __future__ import annotations

import numpy as np

from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.interface_mismatch import (
    InterfaceMismatchCase,
    compact_startup_abort,
    expanded_matrix_rows,
    interface_record,
    load_and_validate_config,
    scaled_plant_truth,
    unique_cases,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


def test_interface_mismatch_config_locks_checkpoint_nominal_parameters() -> None:
    config = load_and_validate_config()
    assert config["controller_nominal_interface"] == interface_record(
        CONTROLLER_NOMINAL_INTERFACE
    )
    assert config["plant_truth_base_interface"] == interface_record(
        STAGE5_RIGID_INTERFACE
    )
    assert not config["hardware_calibrated_uncertainty_bounds"]
    assert not config["controller_retuning_allowed"]
    assert config["initial_condition_policy"] == {
        "shared_human_q_dq": True,
        "shared_required_static_support_wrench": True,
        "plant_truth_sets_evaluation_fixture_robot_side_equilibrium_pose": True,
        "controller_receives_plant_truth_parameters": False,
    }
    assert config["shared_checkpoint_settings"] == {
        "task": "provisional_low_moderate_outbound_hold_return",
        "random_seed": 20260824,
        "prediction_dt_s": 0.02,
        "horizon_steps": 15,
        "candidate_count": 32,
        "elite_count": 6,
        "cem_iterations": 2,
    }


def test_one_factor_scaling_changes_only_the_requested_plant_truth_terms() -> None:
    nominal = interface_record(STAGE5_RIGID_INTERFACE)
    kt = interface_record(scaled_plant_truth("translation_stiffness", 0.7))
    kr = interface_record(scaled_plant_truth("rotation_stiffness", 1.3))
    damping = interface_record(
        scaled_plant_truth("translation_and_rotation_damping", 0.7)
    )
    np.testing.assert_allclose(
        kt["translation_stiffness_n_m"],
        0.7 * np.asarray(nominal["translation_stiffness_n_m"]),
    )
    assert kt["translation_damping_ns_m"] == nominal["translation_damping_ns_m"]
    assert kt["rotation_stiffness_nm_rad"] == nominal["rotation_stiffness_nm_rad"]
    assert kt["rotation_damping_nms_rad"] == nominal["rotation_damping_nms_rad"]

    assert kr["translation_stiffness_n_m"] == nominal["translation_stiffness_n_m"]
    assert kr["translation_damping_ns_m"] == nominal["translation_damping_ns_m"]
    assert kr["rotation_stiffness_nm_rad"] == 1.3 * nominal["rotation_stiffness_nm_rad"]
    assert kr["rotation_damping_nms_rad"] == nominal["rotation_damping_nms_rad"]

    assert damping["translation_stiffness_n_m"] == nominal["translation_stiffness_n_m"]
    np.testing.assert_allclose(
        damping["translation_damping_ns_m"],
        0.7 * np.asarray(nominal["translation_damping_ns_m"]),
    )
    assert damping["rotation_stiffness_nm_rad"] == nominal["rotation_stiffness_nm_rad"]
    assert damping["rotation_damping_nms_rad"] == 0.7 * nominal["rotation_damping_nms_rad"]


def test_sweep_has_seven_unique_runs_and_nine_reported_matrix_cells() -> None:
    cases = unique_cases()
    assert len(cases) == 7
    assert len({case.name for case in cases}) == 7
    rows = expanded_matrix_rows()
    assert len(rows) == 9
    nominal_rows = [row for row in rows if row["scale"] == 1.0]
    assert len(nominal_rows) == 3
    assert {row["source_case"] for row in nominal_rows} == {"nominal_1p0"}


def test_startup_rejection_is_preserved_as_an_aborted_zero_solve_cell() -> None:
    case = InterfaceMismatchCase(
        "kt_0p7",
        "translation_stiffness",
        0.7,
        scaled_plant_truth("translation_stiffness", 0.7),
    )
    diagnostics = {
        "abort_reason": "INITIAL_CONDITION_OUTSIDE_SETTLED_START_SET",
        "validation_error": "cannot start episode outside settled start/return target",
        "time_s": 0.0,
        "estimated_q_rad": [0.01, -0.02],
        "estimated_dq_rad_s": [0.0, 0.0],
        "truth_q_rad": [0.0, 0.0],
        "truth_dq_rad_s": [0.0, 0.0],
        "deployable_acceleration_rad_s2": [0.0, 0.0],
        "truth_acceleration_rad_s2": [0.0, 0.0],
        "physical_force_world_n": [10.0, 0.0, 0.0],
        "physical_moment_world_nm": [0.0, 0.0, 2.0],
        "truth_interface_translation_human_m": [0.001, 0.0, 0.0],
        "truth_interface_rotation_human_rad": [0.0, 0.0, 0.01],
        "estimated_interface_translation_human_m": [0.0007, 0.0, 0.0],
        "estimated_interface_rotation_human_rad": [0.0, 0.0, 0.01],
        "task_velocity_limit_rad_s": np.radians([45.0, 75.0]).tolist(),
        "task_acceleration_limit_rad_s2": np.radians([300.0, 600.0]).tolist(),
        "mujoco_warning_counts": {},
    }
    cell = compact_startup_abort(case, diagnostics)
    assert cell["task_status"] == "ABORTED"
    assert cell["mpc_status_counts"] == {"SAFE_ACTION": 0, "NO_SAFE_ACTION": 0}
    assert cell["cumulative_physical_force_n_s"] == 0.0
