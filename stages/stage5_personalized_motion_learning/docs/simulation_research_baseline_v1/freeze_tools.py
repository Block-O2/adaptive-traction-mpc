"""Evidence-only preregistration and scoring for the simulation research baseline."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = Path(__file__).resolve().parent
BASE = STAGE / "docs/learning_baseline_v1"
sys.path[:0] = [str(STAGE / "scripts/high_rom_v1"), str(STAGE / "docs/waypoint_smoothness_v1")]
from score_return_endpoint_v2 import score_v2
from runtime_benchmark import case_timing
from analyze_repair import inspect

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
def check_source():
    original = read(BASE / "LEARNING_BASELINE_SOURCE_FINGERPRINTS.json")
    mapping = original["source_config_scoring_sha256"]
    drift = [rel for rel, expected in mapping.items()
             if not (ROOT / rel).is_file() or sha(ROOT / rel) != expected]
    if drift: raise RuntimeError(f"frozen 178-file drift: {drift[:10]}")
    return hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def manifests():
    rep = read(BASE / "ORIGINAL_RSS_FUNCTIONAL_FREEZE.json")["case_payloads"]
    low = read(STAGE / "docs/high_rom_runtime_v1/CANDIDATE08_LOW23_PLAN.json")["rows"]
    high = read(STAGE / "docs/high_rom_runtime_v1/CANDIDATE08_FINAL26_PLAN.json")["rows"]
    rows8 = [{"id": key, "plant": value["plant"], "case": value["case_path"],
              "case_sha256": value["case_sha256"]} for key, value in rep.items()]
    rows49 = low + high
    assert len(rows8) == 8 and len(rows49) == 49
    assert len({r["id"] for r in rows8}) == 8 and len({r["id"] for r in rows49}) == 49
    for row in rows8 + rows49:
        if sha(ROOT / row["case"]) != row["case_sha256"]:
            raise RuntimeError("case drift: " + row["id"])
    return rows8, rows49
def prepare():
    source = check_source()
    rows8, rows49 = manifests()
    if (STAGE / "src/traction_mpc_stage5/full3d_adaptive_integration_v1/prepared_activation.py").exists():
        raise RuntimeError("failed split-revalidation module present")
    baseline = {"schema":"simulation_research_baseline_preregistration_v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "source_fingerprint":source, "source_file_count":178,
        "branch":"codex/adaptive-traction-learning-baseline",
        "head":"5d977ab321af72d4ddb8fef919449c37ad67a4f9",
        "representative":rows8, "development49":rows49,
        "scorer":"scorer-v2-return-physical-commit",
        "functional_rule":"COMPLETE, all frozen scorer-v2 task/safety conditions, actual registered RETURN, zero stale activation",
        "representative_smoothness_rule":"frozen protocol-v4: high-ROM reference near-stop <=0.175s; low ordinary <=0.150s; low near upper <=0.190s; C2 switch continuity",
        "development_smoothness_rule":"record near-stop and C2; any obvious >=0.350s intermediate stop/restart triggers failure audit; no post-hoc redefinition",
        "runtime_rule":"characterization only; retain 55ms activation and 11.82% historical limitations; original >=100ms stale activation remains blocker"}
    save(DOC / "PREREGISTRATION.json", baseline)
    save(DOC / "SOURCE_FINGERPRINTS.json", {
        "source_fingerprint":source, "source_file_count":178,
        "source_map":read(BASE / "LEARNING_BASELINE_SOURCE_FINGERPRINTS.json")["source_config_scoring_sha256"],
        "preregistration_sha256":sha(DOC / "PREREGISTRATION.json")})
    save(DOC / "STATE.json", {"status":"PREPARED","source_fingerprint":source,
        "representative_completed":[],"development_completed":[],
        "next_action":"run frozen representative cases once each"})
    print(json.dumps({"source_fingerprint":source,"representative":8,"development":49}))
def score_one(stage, case_id):
    source = check_source()
    frozen = read(DOC / "PREREGISTRATION.json")
    if source != frozen["source_fingerprint"]: raise RuntimeError("source changed after freeze")
    rows = frozen["representative" if stage == "representative" else "development49"]
    row = next(r for r in rows if r["id"] == case_id)
    case_path = ROOT / row["case"]
    if sha(case_path) != row["case_sha256"]: raise RuntimeError("case drift")
    output = STAGE / "results/simulation_research_baseline_v1" / stage / case_id
    launch_path = output / "HIGH_ROM_CASE_RESULT.json"
    if not launch_path.exists(): raise RuntimeError("run result missing")
    launch = read(launch_path)
    result = {"id":case_id, "stage":stage, "plant":row["plant"], "case":row["case"],
              "case_sha256":row["case_sha256"], "source_fingerprint":source,
              "output":str(output),"run_status":launch["status"],"abort_reason":launch.get("abort_reason"),
              "elapsed_host_s":launch.get("elapsed_host_s"),"runtime_sha256":launch.get("runtime_sha256")}
    if launch["status"] != "COMPLETE":
        result.update(pass_all=False,classification="TASK_LOGIC_FAILURE_OR_ENVIRONMENT",
                      scoring_error="runner not COMPLETE")
    else:
        case = read(case_path)
        descriptor = {"case_key":case["case_key"],"physical_variant":case.get("physical_variant", "original_low_rom" if row["plant"]=="low_rom" else "registered_interpolated"),
                      "candidate":case.get("coordination_candidate","original_low_rom"),
                      "path":row["case"],"sha256":row["case_sha256"]}
        contract = read(STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json")["scoring"]
        try:
            scored = score_v2(output, descriptor, contract,
                              goal_deg=case["task"]["goal_deg"],start_deg=case["task"]["start_deg"])
            smooth, _ = inspect(output)
            timing = case_timing({"id":case_id,"plant":row["plant"],
                                  "case":row["case"].removeprefix("stages/stage5_personalized_motion_learning/")}, output)
            jumps = {k:smooth[k] for k in ("exact_switch_max_q_jump_deg",
                                           "exact_switch_max_dq_jump_deg_s",
                                           "exact_switch_max_ddq_jump_deg_s2")}
            c2 = all(abs(v) <= 1e-6 for v in jumps.values())
            stop = smooth["non_task_reference_near_stop_longest_s"]
            if stage == "representative":
                cap = 0.15 if case_id == "low_ordinary" else 0.19 if case_id == "low_near_upper" else 0.175
                smooth_pass = bool(stop <= cap + 1e-9 and c2)
            else:
                # 0.350s is the pre-repair, observed reference stop, used only as a regression trigger.
                smooth_pass = bool(stop < 0.350 and c2)
            expired = timing["expired_activated"]
            result.update(pass_all=bool(scored["pass"] and smooth_pass and expired==0),
                          task_safety_pass=bool(scored["pass"]),
                          failed_conditions=[k for k,v in scored["conditions"].items() if not v],
                          scorer_version=scored["scorer_version"],
                          true_goal_dwell_s=scored["true_goal_continuous_dwell_s"],
                          true_return=scored["true_return"],
                          final_true_q_deg=scored["final_true_q_deg"],
                          final_true_dq_deg_s=scored["final_true_dq_deg_s"],
                          peak_force_n=scored["peak_force_n"],peak_moment_nm=scored["peak_moment_nm"],
                          minimum_session_clearance_m=scored["minimum_session_shank_clearance_m"],
                          reference_near_stop_s=stop,
                          actual_near_stop_s=smooth["non_task_actual_near_stop_longest_s"],
                          c2_switch_jump=jumps, smoothness_pass=smooth_pass,
                          planning_compute_ms=timing["planning_compute_ms"],
                          sample_to_activation_ms=timing["sample_to_activation_ms"],
                          control_miss_ratio=timing["control_cycle_miss_ratio"],
                          longest_consecutive_control_misses=timing["longest_consecutive_control_misses"],
                          stale_activated=expired,request_outcomes=timing["request_outcomes"])
            if not result["pass_all"]:
                result["classification"] = ("STALE_PLAN_FAILURE" if expired else
                  "SAFETY_OR_TASK_FAILURE" if not scored["pass"] else "SMOOTHNESS_REGRESSION")
        except Exception as exc:
            result.update(pass_all=False,classification="SCORER_LOGGING_EVIDENCE_FAILURE",
                          scoring_error=f"{type(exc).__name__}: {exc}")
    dest=DOC / "cases" / stage / (case_id+".json")
    if dest.exists(): raise RuntimeError("would overwrite preserved score")
    save(dest,result)
    update(stage)
    print(json.dumps({"id":case_id,"pass_all":result["pass_all"],
                      "classification":result.get("classification"),"runtime_p95":result.get("sample_to_activation_ms",{}).get("p95")}))
def update(stage):
    frozen=read(DOC/"PREREGISTRATION.json")
    rows=frozen["representative" if stage=="representative" else "development49"]
    results=[read(DOC/"cases"/stage/(r["id"]+".json")) for r in rows
             if (DOC/"cases"/stage/(r["id"]+".json")).exists()]
    out={"schema":"simulation_research_baseline_"+stage+"_v1",
         "source_fingerprint":frozen["source_fingerprint"],
         "denominator":len(rows),"completed":len(results),
         "passed":sum(bool(r["pass_all"]) for r in results),
         "remaining":[r["id"] for r in rows if not (DOC/"cases"/stage/(r["id"]+".json")).exists()],
         "rows":results}
    save(DOC/(stage.upper()+"_RESULTS.json"),out)
    with (DOC/(stage.upper()+"_RESULTS.csv")).open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["id","plant","run_status","pass_all","classification",
            "true_goal_dwell_s","true_return","reference_near_stop_s","actual_near_stop_s",
            "peak_force_n","peak_moment_nm","minimum_session_clearance_m",
            "stale_activated","control_miss_ratio","elapsed_host_s"])
        writer.writeheader()
        for r in results:writer.writerow({k:r.get(k) for k in writer.fieldnames})
    state=read(DOC/"STATE.json")
    state[stage+"_completed"]=[r["id"] for r in results]
    state["status"]=stage.upper()+"_IN_PROGRESS"
    state["next_action"]="check quota and frozen source, then run next registered case"
    save(DOC/"STATE.json",state)
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("prepare")
    q=sub.add_parser("score");q.add_argument("--stage",choices=("representative","development49"),required=True);q.add_argument("--id",required=True)
    a=p.parse_args()
    prepare() if a.command=="prepare" else score_one(a.stage,a.id)
if __name__=="__main__":main()
