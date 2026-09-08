from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
SPEC = STAGE / "docs/PHASE3A_CORRECTED_BASELINE_P1_NEW_AB_SPEC.json"
RUNNER = STAGE / "scripts/run_phase3a_corrected_baseline_p1_new_ab.py"


def _load_runner():
    module_spec = importlib.util.spec_from_file_location("corrected_p1_ab", RUNNER)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_spec_admits_exactly_five_new_cases_and_reuses_rigid_40_80() -> None:
    spec = json.loads(SPEC.read_text())
    assert spec["max_new_runs"] == 5
    assert [
        (run["point"]["endpoint_deg"], run["arm"], run["velocity_path"])
        for run in spec["runs"]
    ] == [
        ([40, 80], "P1", "NEW"),
        ([90, 120], "rigid", "NEW"),
        ([90, 120], "P1", "NEW"),
        ([120, 120], "rigid", "NEW"),
        ([120, 120], "P1", "NEW"),
    ]
    assert all(run["point"]["endpoint_deg"] != [40, 40] for run in spec["runs"])
    assert spec["reused_rigid_40_80"]["arm"] == "rigid"
    assert spec["reused_rigid_40_80"]["velocity_path"] == "NEW"


def test_all_frozen_numerical_and_scientific_contract_values() -> None:
    spec = json.loads(SPEC.read_text())
    assert spec["physics_dt_s"] == 0.00025
    assert spec["control_substeps"] == 20
    assert spec["low_level_period_s"] == 0.005
    assert spec["measurement_update_rate_hz"] == 200.0
    assert spec["measurement_seed"] == 44104
    assert spec["velocity_feedback_gain_ns_m"] == 140.0
    assert spec["candidate"]["parameters"] == {
        "damping_ns_m": 490.68422685624563,
        "k1_n_m": 60000.0,
        "k3_n_m3": 50000000000.0,
        "kr1_nm_rad": 1800.0,
        "kr3_nm_rad3": 4000000.0,
        "rotational_damping_nms_rad": 12.447966320580795,
    }
    assert spec["endpoint_rule"]["tolerance_deg"] == 0.06896926724078867


def test_both_plant_arms_select_only_the_new_control_velocity_path() -> None:
    runner = _load_runner()
    spec = json.loads(SPEC.read_text())
    trajectory = runner.base.NormalizedTrajectory(spec["runs"][0]["point"])
    manager = runner.base.UnifiedReferenceManager(
        trajectory.reference, confidence_aware=False
    )
    rigid = runner.RigidNewPlant(runner.base.HIGH_ROM_HUMAN, spec, manager)
    p1 = runner.ProgressiveNewPlant(runner.base.HIGH_ROM_HUMAN, spec, manager)
    assert rigid.translational_velocity_feedback_source == (
        runner.ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
    )
    assert p1.translational_velocity_feedback_source == (
        runner.ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
    )
    assert rigid.model.opt.timestep == p1.model.opt.timestep == 0.00025
    assert rigid.data.eq_active[rigid.weld_id]
    assert not p1.data.eq_active[p1.weld_id]


def test_rigid_and_p1_initial_state_and_non_interface_model_are_matched() -> None:
    runner = _load_runner()
    spec = json.loads(SPEC.read_text())
    trajectory = runner.base.NormalizedTrajectory(spec["runs"][0]["point"])
    manager = runner.base.UnifiedReferenceManager(
        trajectory.reference, confidence_aware=False
    )
    rigid = runner.RigidNewPlant(runner.base.HIGH_ROM_HUMAN, spec, manager)
    p1 = runner.ProgressiveNewPlant(runner.base.HIGH_ROM_HUMAN, spec, manager)
    rigid.reset(np.radians([5.0, 10.0]))
    p1.reset(np.radians([5.0, 10.0]))
    np.testing.assert_array_equal(rigid.data.qpos, p1.data.qpos)
    np.testing.assert_array_equal(rigid.data.qvel, p1.data.qvel)
    for name in (
        "body_mass",
        "body_inertia",
        "body_pos",
        "jnt_range",
        "actuator_gainprm",
        "actuator_biasprm",
    ):
        np.testing.assert_array_equal(getattr(rigid.model, name), getattr(p1.model, name))


def test_runner_has_one_new_run_per_invocation_and_no_fallback() -> None:
    source = RUNNER.read_text()
    assert source.count("run_one(spec, completed)") == 1
    assert 'assert completed < len(spec["runs"]), "no sixth new run"' in source
    assert "PROCESSED_POSE_HISTORY_VELOCITY" not in source
    assert "all five new registered runs required" in source
    assert "REUSED_HASH_LOCKED_RIGID_NEW_BASELINE" in source


def test_physical_progress_is_separate_from_formal_classification() -> None:
    runner = _load_runner()
    trace = {
        "human_q_deg_god_view": np.array(
            [[5.0, 10.0], [40.0, 80.0], [5.1, 10.2]]
        ),
        "reference_phase_time_s": np.array([0.0, 9.0, 19.0]),
    }
    point = json.loads(SPEC.read_text())["runs"][0]["point"]
    result = runner._physical_progress(trace, point)
    assert result["outbound_percent"] == 100.0
    assert result["return_percent"] > 99.0
    assert result["target_reached_within_retained_tolerance"]
    assert not result["return_reached_within_retained_tolerance"]


def test_partial_run_directory_is_not_mistaken_for_completion(tmp_path) -> None:
    runner = _load_runner()
    spec = json.loads(SPEC.read_text())
    partial = tmp_path / spec["runs"][0]["id"]
    partial.mkdir()
    (partial / "started.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="incomplete run directory"):
        runner.completed_run_count(spec, tmp_path)
