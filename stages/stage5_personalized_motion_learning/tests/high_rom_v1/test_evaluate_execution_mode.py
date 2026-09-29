"""Mode boundary tests; the historical scorer itself is exercised separately."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/high_rom_v1"
sys.path.insert(0, str(SCRIPT))
spec = importlib.util.spec_from_file_location("evaluate_execution_mode", SCRIPT / "evaluate_execution_mode.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_run(tmp_path, mode="SCIENTIFIC_SIMULATION", age_ms=500.0, wrong_version=False):
    version = dict(episode_epoch="e", state_version=1, physics_step=0, sim_time_s=0.0,
                   phase_version=0, human_model_version="m", reference_version="r")
    receipt = {**version, "state_version": 2} if wrong_version else dict(version)
    request = dict(request_id=0, stage="TASK", outcome="ACTIVATED", execution_mode=mode,
                   source_simulation_version=version, receipt_simulation_version=receipt,
                   activation_simulation_version=dict(version), activation_age_ms=age_ms,
                   compute_ms=age_ms, validation_to_activation_ms=1.0)
    (tmp_path / "HIGH_ROM_CASE_RESULT.json").write_text(json.dumps(dict(status="COMPLETE", execution_mode=mode,
        scientific_host_delay_ms=age_ms, elapsed_host_s=1.0)))
    (tmp_path / "summary.json").write_text(json.dumps(dict(status="COMPLETE", execution_mode=mode,
                                                            timing=dict(requests=[request],
                                                                        all_reference_boundaries_q_dq_ddq_continuous=True))))
    (tmp_path / "runtime_artifacts.json").write_text(json.dumps(dict(execution_mode=mode,
        requests=[request], activation_validations=[dict(feasible=True, reference_continuity=True,
                                                         truth_consumed=False)],
        safe_fallback_events=[], wall_physics=dict(control_cycle_misses=0,
        command_receipts=[], catchup_intervals=[], native_states_evaluation_only=[
            dict(qpos_evaluation_only=[0.0], qvel_evaluation_only=[0.0], command_torque_nm=[0.0])]))))
    np.savez(tmp_path / "trace.npz", time_s=np.array([0.0]),
             evaluation_only_human_state_rad_rad_s=np.zeros((1, 4)),
             estimated_human_state_rad_rad_s=np.zeros((1, 4)),
             cr12_q_rad=np.zeros((1, 6)), cr12_dq_rad_s=np.zeros((1, 6)))
    return request


@pytest.mark.parametrize("mode,age,wrong,physical,expected", [
    ("SCIENTIFIC_SIMULATION", 500, False, True, "PASS"),
    ("SCIENTIFIC_SIMULATION", 2, True, True, "FAIL"),
    ("REALTIME_CHARACTERIZATION", 100, False, True, "FAIL"),
    ("REALTIME_CHARACTERIZATION", 2, False, True, "PASS"),
    ("SCIENTIFIC_SIMULATION", 500, False, False, "FAIL"),
])
def test_mode_validity_and_shared_physical_gate(tmp_path, monkeypatch, mode, age, wrong, physical, expected):
    fixture_run(tmp_path, mode, age, wrong)
    monkeypatch.setattr(module, "score", lambda *args, **kwargs: dict(pass_=False,
        conditions=dict(summary_complete=physical, force=True, plan_age=age < 100),
        maximum_plan_activation_age_ms=age))
    result = module.evaluate(tmp_path, {}, dict(plan_max_activation_age_ms=100))
    assert result["overall_result_for_mode"] == expected
    assert result["physical_task_result"]["status"] == ("PASS" if physical else "FAIL")
    assert result["wall_runtime_characterization"]["maximum_plan_source_to_activation_age_ms"] == age
    if mode == "SCIENTIFIC_SIMULATION":
        assert result["realtime_execution_validity"]["status"] == "N/A"
    else:
        assert result["scientific_validity"]["status"] == "N/A"


def test_missing_execution_mode_is_not_guessed(tmp_path, monkeypatch):
    fixture_run(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    del summary["execution_mode"]
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="execution_mode"):
        module.evaluate(tmp_path, {}, {})
