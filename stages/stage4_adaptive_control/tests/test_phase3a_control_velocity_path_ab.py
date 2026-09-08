from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
SPEC = STAGE / "docs/PHASE3A_CONTROL_VELOCITY_PATH_AB_SPEC.json"
RUNNER = STAGE / "scripts/run_phase3a_control_velocity_path_ab.py"


def _load_runner():
    module_spec = importlib.util.spec_from_file_location("control_velocity_ab", RUNNER)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_spec_admits_only_registered_old_new_40_40_and_40_80_runs() -> None:
    spec = json.loads(SPEC.read_text())
    assert spec["max_runs"] == 4
    assert [
        (run["point"]["endpoint_deg"], run["velocity_path"], run["arm"])
        for run in spec["runs"]
    ] == [
        ([40, 40], "OLD", "rigid"),
        ([40, 40], "NEW", "rigid"),
        ([40, 80], "OLD", "rigid"),
        ([40, 80], "NEW", "rigid"),
    ]
    assert "90" not in " ".join(run["id"] for run in spec["runs"])
    assert "120" not in " ".join(run["id"] for run in spec["runs"])
    assert spec["physics_dt_s"] == 0.00025
    assert spec["low_level_period_s"] == 0.005
    assert spec["measurement_update_rate_hz"] == 200.0
    assert spec["measurement_seed"] == 44104


def test_old_new_plant_selection_changes_only_velocity_measurement_source() -> None:
    runner = _load_runner()
    source = RUNNER.read_text()
    assert "PROCESSED_POSE_HISTORY_VELOCITY" in source
    assert "ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY" in source
    assert "translational_velocity_feedback_source=source" in source
    assert "self.model.opt.timestep = spec[\"physics_dt_s\"]" in source
    assert "freeze_control_geometry=True" in source
    assert runner.ROOT.name == "control_velocity_path_ab_20260908_v1"


def test_runner_executes_at_most_one_registered_case_per_invocation() -> None:
    source = RUNNER.read_text()
    assert source.count("run_one(spec, completed)") == 1
    assert "assert completed < len(spec[\"runs\"]), \"no fifth run\"" in source
    assert "all four registered runs are required" in source

