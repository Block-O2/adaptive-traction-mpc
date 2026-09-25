"""Local diagnostic evidence checks; require the preserved DEV-B artifacts."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
RESULTS=ROOT/"results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3"
CASES=["balanced_near_upper_current_rom_r01","balanced_ordinary_r01","balanced_middle_r01","development_nominal"]


@pytest.mark.parametrize("key",CASES)
def test_matching_checkpoint_and_historical_replay(key):
    manifest=json.loads((RESULTS/key/"capture_manifest.json").read_text())
    for field in ["historical_truth_max_abs_delta","historical_robot_q_max_abs_delta",
                  "historical_estimate_max_abs_delta","historical_beta_max_abs_delta"]:
        assert manifest[field]==0.0
    path=RESULTS/key/"analysis_0200ms"
    clone=json.loads((path/"clone_validation.json").read_text())
    assert clone["duplicate_physics_exact"] and clone["initial_hash_equal"]
    assert clone["max_q_delta_rad"]==0.0
    replay=json.loads((path/"historical_replay_validation.json").read_text())
    assert replay["max_abs_command_difference_nm"]<1e-7
    assert replay["max_abs_state_difference_rad_rad_s"]<1e-9


@pytest.mark.parametrize("key",CASES)
def test_chain_closure_and_same_timestamp_execution(key):
    a=json.loads((RESULTS/key/"analysis_0200ms/algebra.json").read_text())
    assert a["production_command_max_abs_difference_nm"]<1e-10
    old=a["records"]["old_model_old_estimate"]
    new=a["records"]["new_model_new_estimate"]
    assert old["timestamp_s"]==new["timestamp_s"]
    assert np.array_equal(old["command"]["robot_attachment_jacobian"],new["command"]["robot_attachment_jacobian"])
    assert np.max(np.abs(a["commissioning_vs_active_recovery_context_torque_delta_nm"]))<1e-10
    for r in a["records"].values():
        parts=r["robot_torque_components"]
        total=sum(np.array(v) for k,v in parts.items() if k!="sum_error_nm")
        assert np.max(np.abs(total-r["command"]["joint_torque_command_nm"]))<1e-10


@pytest.mark.parametrize("key",CASES)
def test_physical_interval_accounting_and_firewall(key):
    p=RESULTS/key/"analysis_0200ms"
    for name in ["activated_model","retained_model","diagnostic_action_transfer_100ms"]:
        b=json.loads((p/(name+".json")).read_text())
        assert not b["truth_consumed_by_branch_control"]
        assert b["beta_residual_updates"]==0
        assert b["planner_age_at_capture_s"]<=0.100
        assert len(b["physics"])==20*len(b["records"])+1
        time=np.array([x["time_s"] for x in b["physics"]])
        assert np.all(np.diff(time)>0)
        assert abs(time[-1]-time[0]-b["duration_s"])<1e-12


def test_production_dependencies_unchanged_since_capture():
    manifest=json.loads((RESULTS/CASES[0]/"capture_manifest.json").read_text())
    repo=ROOT.parents[1]
    checked=0
    for name,digest in manifest["source_sha256"].items():
        if "/src/" in name:
            assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest,name
            checked+=1
    assert checked>20


@pytest.mark.parametrize("arm",["production_replay","action_transfer_100ms"])
def test_complete_recovery_counterfactual_match_and_failure_preserved(arm):
    path=RESULTS.parent/"full_recovery_v3"/arm
    matched=json.loads((path/"matched_checkpoint_validation.json").read_text())
    assert matched["integration_state_max_abs_delta"]==0
    assert matched["qacc_warmstart_max_abs_delta"]==0
    excluded={"supervisor_pickle_equal","supervisor_complete_value_equal"}
    assert all(value for key,value in matched.items() if key.endswith("equal") and key not in excluded)
    assert matched["excluded_nondeterministic_metadata_paths"]==[
        "computation_ms","last_safety_filter/computation_ms"]
    result=json.loads((path/"recovery_result.json").read_text())
    assert not result["model_laws_changed"]
    assert not result["recovery"]["succeeded"]
    assert result["recovery"]["abort_reason"]=="ACTIVE_RECOVERY_TIMEOUT"
    assert len(result["commands"])==1810
    assert abs(result["recovery"]["duration_s"]-9.055)<1e-9
    assert all(x["actual_compute_ms"]<=100 for x in result["planner_timing"])
    if arm=="production_replay":
        replay=json.loads((path/"historical_replay_validation.json").read_text())
        assert replay=={"matched_intervals":1810,"maximum_command_difference_nm":0.0,"same_abort_reason":True}


def test_contact_load_accounting_keeps_cuff_and_bed_distinct():
    evidence=json.loads((RESULTS.parent/"contact_load_probe_v1.json").read_text())
    for item in evidence.values():
        assert np.max(np.abs(item["equation_balance_nm"]))<1e-12
        assert np.array_equal(item["human_actuator_nm"],[0,0])
        contact=np.sum([x["generalized_human_nm"] for x in item["contacts"]],axis=0) if item["contacts"] else np.zeros(2)
        assert np.allclose(contact,item["human_contact_generalized_input_nm"],atol=1e-12,rtol=0)
        for model in item["models"].values():
            assert np.allclose(np.array(model["minus_cuff_nm"])-model["minus_cuff_and_contact_nm"],contact,atol=1e-12,rtol=0)
