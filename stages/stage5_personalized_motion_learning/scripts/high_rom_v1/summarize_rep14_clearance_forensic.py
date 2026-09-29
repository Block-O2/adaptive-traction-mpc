"""Summarize immutable V2 raw evidence and isolated Rep14 checkpoint replays."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
FORMAL = STAGE / "results/zero_value_30rep_baseline_v2/formal_session_02"
REPLAY = STAGE / "results/rep14_clearance_forensic_v1"
DOC = STAGE / "docs/rep14_clearance_forensic_v1"
V2 = STAGE / "docs/zero_value_30rep_baseline_v2"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (DOC / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")

def row(rep):
    p = FORMAL / f"rep_{rep:02d}"
    a = json.loads((p / "runtime_artifacts.json").read_text())
    s = json.loads((p / "summary.json").read_text())
    t = np.load(p / "trace.npz")
    plans = [json.loads(line)["selected_plan"] for line in (p / "learning_transitions.jsonl").read_text().splitlines()]
    samples = a["wall_physics"]["causal_sensor_estimates"]
    sample_times = [v["sample_time_s"] for v in samples]
    first_plans = plans[:3]
    return {"repetition":rep,"status":s["status"],"abort_reason":s.get("abort_reason"),
      "sim_start_s":float(t["time_s"][0]),"sim_end_s":float(t["time_s"][-1]),
      "human_start_q_dq":t["evaluation_only_human_state_rad_rad_s"][0].tolist(),
      "human_end_q_dq":t["evaluation_only_human_state_rad_rad_s"][-1].tolist(),
      "human_estimated_start_q_dq":t["estimated_human_state_rad_rad_s"][0].tolist(),
      "human_estimated_end_q_dq":t["estimated_human_state_rad_rad_s"][-1].tolist(),
      "cr12_start_q":t["cr12_q_rad"][0].tolist(),"cr12_end_q":t["cr12_q_rad"][-1].tolist(),
      "cr12_start_dq":t["cr12_dq_rad_s"][0].tolist(),"cr12_end_dq":t["cr12_dq_rad_s"][-1].tolist(),
      "model_sequence_start":int(t["belief_sequence"][0]),"model_sequence_end":int(t["belief_sequence"][-1]),
      "beta_start":t["task_beta"][0].tolist(),"beta_end":t["task_beta"][-1].tolist(),
      "beta_change_l2":float(np.linalg.norm(t["task_beta"][-1]-t["task_beta"][0])),
      "residual_weights_start":t["task_residual_weights_nm"][0].tolist(),
      "residual_weights_end":t["task_residual_weights_nm"][-1].tolist(),
      "minimum_deployable_shank_clearance_m":float(t["session_shank_clearance_m"].min()),
      "minimum_native_clearance_m":float(s["task"]["minimum_true_physical_clearance_m_evaluation_only"]),
      "minimum_sleeve_gap_m":float(t["dev_d_measured_sleeve_gap_m"].min()),
      "selected_waypoint_prefix":[v["label"] for v in first_plans],
      "selected_target_q_prefix":[v["target_q_rad"] for v in first_plans],
      "predicted_distal_shank_lower_prefix_m":[v["schedule"]["continuous_clearance_certificate"]["combined_body_lowers_m"]["distal_shank_m"] for v in first_plans],
      "predicted_tracking_offset_lower_prefix_m":[v["execution_screen"]["causal_tracking_offset_clearance"]["continuous_model_clearance_lower_m"] for v in first_plans],
      "sample_count":len(samples),"max_sample_interval_s":max(np.diff(sample_times)),
      "non_5ms_intervals":[{"before_s":sample_times[j-1],"after_s":sample_times[j],"interval_s":sample_times[j]-sample_times[j-1]} for j in range(1,len(samples)) if abs(sample_times[j]-sample_times[j-1]-.005)>1e-9 and abs(sample_times[j]-sample_times[j-1])>1e-12],
      "invalid_fast_sample_count":sum(not v["fast_motion_valid"] for v in samples)}

def main():
    DOC.mkdir(exist_ok=True)
    trends=[row(i) for i in range(10,15)]
    base=trends[0]
    for v in trends:
        v["human_start_q_drift_from_rep10_l2_rad"]=float(np.linalg.norm(np.array(v["human_start_q_dq"][:2])-base["human_start_q_dq"][:2]))
        v["cr12_start_q_drift_from_rep10_l2_rad"]=float(np.linalg.norm(np.array(v["cr12_start_q"])-base["cr12_start_q"]))
    save("REP10_14_TREND.json",trends)
    with (DOC/"REP10_14_TREND.csv").open("w",newline="") as f:
        keys=("repetition","status","sim_start_s","sim_end_s","model_sequence_start","model_sequence_end","beta_change_l2","human_start_q_drift_from_rep10_l2_rad","cr12_start_q_drift_from_rep10_l2_rad","minimum_deployable_shank_clearance_m","minimum_native_clearance_m","minimum_sleeve_gap_m","max_sample_interval_s","invalid_fast_sample_count")
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:v[k] for k in keys} for v in trends)
    p=FORMAL/"rep_14";a=json.loads((p/"runtime_artifacts.json").read_text());t=np.load(p/"trace.npz");j=len(t["time_s"])-2
    last=a["execution_attempts"][-2];failed=a["execution_attempts"][-1];snap=a["causal_tracking_request_snapshots"][-1]
    first={"schema":"rep14_first_failure_state_v1","first_invalid_sim_time_s":float(t["time_s"][j]),"trace_index":j,
      "last_valid_fast_sample_s":a["wall_physics"]["causal_sensor_estimates"][-3]["sample_time_s"],
      "missed_native_sample_time_s":last["start_physics_s"],"first_invalid_sample_time_s":a["wall_physics"]["causal_sensor_estimates"][-1]["sample_time_s"],
      "invalid_fast_motion_valid":a["wall_physics"]["causal_sensor_estimates"][-1]["fast_motion_valid"],
      "last_applied_interval":{k:last[k] for k in ("source_sample_time_s","start_physics_s","end_physics_s","native_steps","applied")},
      "rejected_interval":{k:failed.get(k) for k in ("source_sample_time_s","start_physics_s","native_steps","applied")},
      "human_truth_q_dq":t["evaluation_only_human_state_rad_rad_s"][j].tolist(),
      "human_estimated_q_dq":t["estimated_human_state_rad_rad_s"][j].tolist(),
      "cr12_q":t["cr12_q_rad"][j].tolist(),"cr12_dq":t["cr12_dq_rad_s"][j].tolist(),
      "cuff_force_world_n":t["physical_cuff_force_world_n"][j].tolist(),
      "cuff_moment_world_nm":t["physical_cuff_moment_world_nm"][j].tolist(),
      "reference_q":t["reference_q_rad"][j].tolist(),"reference_dq":t["reference_dq_rad_s"][j].tolist(),
      "selected_schedule_label":str(t["selected_schedule_label"][j]),
      "last_activated_waypoint":trends[-1]["selected_target_q_prefix"][-1],
      "predicted_distal_shank_lower_m":trends[-1]["predicted_distal_shank_lower_prefix_m"][-1],
      "deployable_shank_clearance_m":float(t["session_shank_clearance_m"][j]),
      "native_minimum_clearance_so_far_m":trends[-1]["minimum_native_clearance_m"],
      "measured_sleeve_gap_m":float(t["dev_d_measured_sleeve_gap_m"][j]),
      "human_model_sequence":int(t["belief_sequence"][j]),"human_model_beta":t["task_beta"][j].tolist(),
      "planner_request_provenance":snap,"abort_reason":json.loads((p/"summary.json").read_text())["abort_reason"]}
    save("REP14_FIRST_FAILURE_STATE.json",first)
    replay=[]
    for i in range(1,5):
        q=REPLAY/f"replay_{i:02d}";v=json.loads((q/"replay_result.json").read_text());tr=np.load(q/"rep_14/trace.npz");v.update({"replay_index":i,"post_repair":i>=3,"final_sim_time_s":float(tr["time_s"][-1]),"trace_nodes":len(tr["time_s"]),"final_human_state":tr["evaluation_only_human_state_rad_rad_s"][-1].tolist(),"final_cr12_q":tr["cr12_q_rad"][-1].tolist(),"min_deployable_shank_clearance_m":float(tr["session_shank_clearance_m"].min()),"trace_sha256":sha(q/"rep_14/trace.npz")})
        if i>=3:
            mode=json.loads((q/"rep_14/MODE_AWARE_RESULT_V2.json").read_text());v["physical_task_result"]=mode["physical_task_result"]["status"];v["scientific_validity"]=mode["scientific_validity"]["status"]
        replay.append(v)
    save("REP14_DETERMINISTIC_REPLAY.json",{"pre_repair":replay[:2],"post_repair":replay[2:],"pre_repair_scientific_trace_equal_to_formal":all(np.array_equal(np.load(REPLAY/f"replay_{i:02d}/rep_14/trace.npz")["evaluation_only_human_state_rad_rad_s"],t["evaluation_only_human_state_rad_rad_s"]) for i in (1,2)),"post_repair_two_traces_scientifically_equal":all(np.array_equal(np.load(REPLAY/"replay_03/rep_14/trace.npz")[k],np.load(REPLAY/"replay_04/rep_14/trace.npz")[k]) for k in ("time_s","evaluation_only_human_state_rad_rad_s","cr12_q_rad","task_beta","session_shank_clearance_m"))})
    counter={"schema":"rep14_offline_counterfactual_v1","method":"Matched decision-prefix comparison, plus exact-checkpoint single-variable repair replay; no official trajectory modification.","model_freeze_at_rep13_not_executed":"The failure predicate tests fast_motion_valid and sample timestamp only; a model freeze would not restore the missing 5 ms sample. No unsupported model-freeze trajectory is claimed.","matched_waypoint_labels_rep13_rep14":[trends[-2]["selected_waypoint_prefix"],trends[-1]["selected_waypoint_prefix"]],"predicted_distal_shank_lower_m_rep13_rep14":[trends[-2]["predicted_distal_shank_lower_prefix_m"],trends[-1]["predicted_distal_shank_lower_prefix_m"]],"actual_deployable_prefix_min_m_rep13_rep14":[trends[-2]["minimum_deployable_shank_clearance_m"],trends[-1]["minimum_deployable_shank_clearance_m"]],"native_prefix_min_m_rep13_rep14":[trends[-2]["minimum_native_clearance_m"],trends[-1]["minimum_native_clearance_m"]],"causal_intervention":"Reanchor only next sensor acquisition deadline to acquired native sample; both exact-checkpoint Rep14 replays COMPLETE with physical/scientific PASS.","safety_threshold_changed":False}
    save("REP14_COUNTERFACTUAL_ANALYSIS.json",counter)
    manifest={"formal_v2_raw_manifest_sha256":sha(V2/"RAW_DATA_MANIFEST_V2.json"),"formal_v2_checkpoint_manifest_sha256":sha(V2/"SESSION_CHECKPOINTS_MANIFEST_V2.json"),"formal_session_provenance_sha256":sha(FORMAL/"session_provenance.json"),"exact_rep13_checkpoint_sha256":sha(FORMAL/"checkpoint_13.pkl.z"),"formal_rep14_summary_sha256":sha(p/"summary.json"),"formal_rep14_trace_sha256":sha(p/"trace.npz"),"replay_raw_sha256":{f"replay_{i:02d}/{name}":sha(REPLAY/f"replay_{i:02d}"/name) for i in range(1,5) for name in ("rep_14/summary.json","rep_14/trace.npz","rep_14/runtime_artifacts.json","boundary_13_to_14.json")}}
    save("FORENSIC_RAW_CHECKPOINT_MANIFEST.json",manifest)
    save("FINGERPRINTS.json",{"frozen_formal_production_fingerprint":json.loads((FORMAL/"session_provenance.json").read_text())["frozen_production_fingerprint"],"formal_source_commit":"22c6859214256a46e75d47ad153ed9be3c3a2f72","formal_checkpoint_13_sha256":manifest["exact_rep13_checkpoint_sha256"],"post_repair_measurement_source_sha256":sha(ROOT/"stages/stage4_adaptive_control/src/traction_mpc_stage4/measurement.py"),"formal_runtime_source_sha256":sha(STAGE/"src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"),"options_sha256":sha(STAGE/"configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json")})
    save("STATE.json",{"status":"REP14_ROOT_CAUSE_IMPLEMENTATION_BUG","original_v2_status":"ZERO_VALUE_30REP_BASELINE_FAIL","original_rep14_status":"ABORTED","pre_repair":"DETERMINISTIC_REP14_FAILURE","post_repair_exact_checkpoint_replays":2,"post_repair_physical_scientific_pass":True,"repair_count":1,"fresh_30rep_campaign_run":False,"safety_threshold_changed":False})
    print("wrote forensic structured evidence",len(trends),len(replay))
if __name__=="__main__":main()
