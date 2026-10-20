"""Resumable preregistered coarse/refinement/validation coordination campaign."""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/coordination_pacing_exploration_v1"
RUNS = STAGE / "results/coordination_pacing_exploration_v1/runs"
RUNNER = Path(__file__).with_name("run_coordination_rollout_v1.py")
MATRIX = json.loads((DOC / "CONDITION_MATRIX.json").read_text())
BASE = json.loads((DOC / "BASELINE_MATRIX_VALIDATION_V2.json").read_text())
PASS = {r["condition_id"] for r in BASE["rows"] if r["native_replay_pass"] and r["matched_baseline_pass"]}
ELIGIBLE = [c for c in MATRIX["conditions"] if c["id"] in PASS]
START = min((RUNS / MATRIX["conditions"][0]["baseline_run_id"] / "rollout_result.json").stat().st_mtime, time.time())
DEADLINE = START + 8 * 3600
ENV = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temp.replace(path)


def pattern_key(p):
    return (p["lead"], p["amplitude"], p["peak"], p["horizon"],
            p["synchronous"], p["return_reverse"])


def coarse_patterns():
    result = []
    peaks = (.3, .5, .7)
    for h, horizon in enumerate(("H1", "H3", "H4")):
        for a, amplitude in enumerate((.02, .06, .12, .18)):
            for l, lead in enumerate((-1, 1)):
                result.append({"lead": lead, "amplitude": amplitude,
                               "peak": peaks[(h + a + l) % 3], "horizon": horizon,
                               "synchronous": False, "return_reverse": bool(horizon == "H4" and (a + l) % 2),
                               "matched_duration_factor": 1.3})
    for l, lead in enumerate((-1, 1)):
        result.append({"lead": lead, "amplitude": .06,
                       "peak": peaks[l], "horizon": "H2",
                       "synchronous": False, "return_reverse": False,
                       "matched_duration_factor": 1.3})
    result.append({"lead": 0, "amplitude": 0.0, "peak": .5,
                   "horizon": "H4", "synchronous": True,
                   "return_reverse": False, "matched_duration_factor": 1.3})
    assert len(result) == 27 and len({pattern_key(x) for x in result}) == 27
    return result


def make_entries(stage, patterns, conditions):
    entries = []
    for c in conditions:
        for pidx, p in enumerate(patterns):
            for arm in ("NATIVE", "MATCHED"):
                entries.append({"stage": stage, "condition_id": c["id"],
                                "condition_role": c["role"], "arm": arm, "pattern": p,
                                "run_id": f"{stage.lower()}_{c['id']}_{pidx:03d}_{arm.lower()}"})
    return entries


def freeze_plan(name, entries, details=None):
    path = DOC / name
    if not path.exists():
        save(path, {"schema": "coordination_pacing_formal_plan_v1",
                    "status": "FROZEN_BEFORE_STAGE", "entries": entries,
                    "formal_attempts": len(entries), "details": details or {},
                    "source_contract": "COORDINATION_PACING_EXPLORATION_CONTRACT_V2.json"})
    return json.loads(path.read_text())["entries"]


def all_entries():
    entries = []
    for name in ("COARSE_PLAN.json", "REFINEMENT_PLAN.json", "CROSS_CONDITION_PLAN.json"):
        p = DOC / name
        if p.exists(): entries += json.loads(p.read_text())["entries"]
    return entries


def rows():
    output = []
    for entry in all_entries():
        path = RUNS / entry["run_id"] / "rollout_result.json"
        if not path.exists(): continue
        r = json.loads(path.read_text())
        native = RUNS / f"baseline_{entry['condition_id']}_a" / "rollout_result.json"
        matched = RUNS / f"matched_baseline_{entry['condition_id']}_certified" / "rollout_result.json"
        baseline = json.loads((native if entry["arm"] == "NATIVE" else matched).read_text())
        benefit = baseline.get("J_F_task_n_s") - r["J_F_task_n_s"] if r.get("status") == "VALID" else None
        residual = {phase: r.get(key, 0) - baseline.get(key, 0)
                    for phase, key in (("OUTBOUND", "outbound_duration_s"), ("RETURN", "return_duration_s"))} if r.get("status") == "VALID" else None
        equal_segments = all(len(r.get("planned_segments", {}).get(p, [])) ==
                             len(baseline.get("planned_segments", {}).get(p, []))
                             for p in ("OUTBOUND", "RETURN")) if r.get("status") == "VALID" else None
        timing_isolated = (entry["arm"] == "MATCHED" and r.get("status") == "VALID"
                           and equal_segments and all(abs(x) <= .025 + 1e-9 for x in residual.values()))
        output.append({**entry, "lead": entry["pattern"]["lead"],
                       "amplitude": entry["pattern"]["amplitude"],
                       "peak": entry["pattern"]["peak"],
                       "horizon": entry["pattern"]["horizon"],
                       "return_reverse": entry["pattern"]["return_reverse"],
                       "synchronous": entry["pattern"]["synchronous"],
                       "status": r["status"], "failure_reason": r.get("failure_reason") or r.get("abort_reason"),
                       "J_F_task_n_s": r.get("J_F_task_n_s"), "J_F_session_n_s": r.get("J_F_session_n_s"),
                       "baseline_J_F_task_n_s": baseline.get("J_F_task_n_s"), "benefit_n_s": benefit,
                       "duration_s": r.get("duration_s"), "baseline_duration_s": baseline.get("duration_s"),
                       "duration_change_s": r.get("duration_s") - baseline.get("duration_s") if benefit is not None else None,
                       "outbound_duration_s": r.get("outbound_duration_s"), "return_duration_s": r.get("return_duration_s"),
                       "phase_timing_residual_s": residual, "equal_segment_count": equal_segments,
                       "timing_isolated": timing_isolated, "mean_force_n": r.get("mean_force_n"),
                       "rms_force_n": r.get("rms_force_n"), "peak_force_n": r.get("peak_force_n"),
                       "moment_integral_nm_s": r.get("moment_integral_nm_s"), "moment_peak_nm": r.get("moment_peak_nm"),
                       "minimum_clearance_m": r.get("minimum_clearance_m"),
                       "governor_delay_added_s": r.get("governor_delay_added_s"),
                       "duration_search_count": r.get("duration_search_count"),
                       "rss_event_count": r.get("rss_event_count"), "fallback_event_count": r.get("fallback_event_count"),
                       "coordination_lead_metrics": r.get("coordination_lead_metrics"),
                       "cost_0p5_n_s": r.get("cost_0p5_n_s"), "cost_1p5_n_s": r.get("cost_1p5_n_s"),
                       "cost_outbound_n_s": r.get("cost_outbound_n_s"),
                       "short_benefit_0p5_n_s": baseline.get("cost_0p5_n_s", 0) - r["cost_0p5_n_s"] if benefit is not None else None,
                       "short_benefit_1p5_n_s": baseline.get("cost_1p5_n_s", 0) - r["cost_1p5_n_s"] if benefit is not None else None,
                       "outbound_benefit_n_s": baseline.get("cost_outbound_n_s", 0) - r["cost_outbound_n_s"] if benefit is not None else None,
                       "elapsed_host_s": r.get("elapsed_host_s")})
    return output


def persist(stage):
    data = rows()
    save(DOC / "ALL_COORDINATION_ROLLOUTS.json", data)
    if data:
        with (DOC / "ALL_COORDINATION_ROLLOUTS.csv").open("w", newline="") as stream:
            columns = [k for k in data[0] if k not in ("pattern", "phase_timing_residual_s", "coordination_lead_metrics")]
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for row in data:
                writer.writerow({k: row.get(k) for k in columns})
    counts = Counter(x["status"] for x in data)
    state = {"schema": "coordination_pacing_state_v1", "status": "RUNNING",
             "phase": stage, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
             "campaign_start_utc": datetime.fromtimestamp(START, timezone.utc).isoformat(),
             "formal_attempts": len(data), "valid": counts["VALID"],
             "infeasible": counts["INFEASIBLE"], "invalid": counts["INVALID"],
             "exception": counts["EXCEPTION"], "last_run_id": data[-1]["run_id"] if data else None,
             "source_commit": MATRIX["source_commit"], "branch": "codex/coordination-pacing-exploration-v1",
             "repair_cycles_used": 3, "next_action": "resume campaign script from frozen plans"}
    save(DOC / "STATE.json", state)
    snapshot = {"stage": stage, "attempts": len(data), "counts": counts,
                "best_matched_timing_isolated_n_s": max((x["benefit_n_s"] for x in data if x["timing_isolated"]), default=None),
                "best_native_n_s": max((x["benefit_n_s"] for x in data if x["arm"] == "NATIVE" and x["status"] == "VALID"), default=None)}
    save(DOC / "CURRENT_ANALYSIS_SNAPSHOT.json", snapshot)
    save(DOC / "RAW_DATA_MANIFEST.json", {"schema": "coordination_raw_manifest_v1",
        "rollouts": [{"run_id": x["run_id"], "result_sha256": hashlib.sha256(
            (RUNS / x["run_id"] / "rollout_result.json").read_bytes()).hexdigest()}
            for x in data], "raw_artifact_hashes_within_each_result": True})
    print(json.dumps({"progress": state, "snapshot": snapshot}, default=dict), flush=True)


def execute(stage, entries):
    count = len(rows())
    for e in entries:
        path = RUNS / e["run_id"] / "rollout_result.json"
        if path.exists(): continue
        if time.time() >= DEADLINE:
            persist(stage)
            return False
        command = [sys.executable, str(RUNNER), "--condition", e["condition_id"],
                   "--arm", e["arm"], "--run-id", e["run_id"],
                   "--pattern-json", json.dumps(e["pattern"], separators=(",", ":"))]
        try:
            result = subprocess.run(command, env=ENV, capture_output=True, text=True, timeout=180)
            if result.returncode != 0 or not path.exists():
                print(json.dumps({"infrastructure_failure": e["run_id"], "exit": result.returncode,
                                  "stderr": result.stderr[-1000:], "stdout": result.stdout[-1000:]}), flush=True)
        except subprocess.TimeoutExpired as error:
            print(json.dumps({"infrastructure_timeout": e["run_id"], "error": str(error)}), flush=True)
        count += 1
        if count % 50 == 0:
            persist(stage)
    persist(stage)
    return True


def choose_refinement():
    source = [x for x in rows() if x["stage"] == "COARSE" and x["condition_role"] == "discovery"]
    coarse = [x for x in source if x["status"] == "VALID" and not x["synchronous"]]
    matched = sorted((x for x in coarse if x["timing_isolated"]), key=lambda x: -x["benefit_n_s"])
    native = sorted((x for x in coarse if x["arm"] == "NATIVE"), key=lambda x: -x["benefit_n_s"])
    seeds = []
    def add(row, reason):
        if row is not None and pattern_key(row["pattern"]) not in {pattern_key(x[0]["pattern"]) for x in seeds}:
            seeds.append((row, reason))
    add(matched[0] if matched else None, "best_timing_isolated_matched")
    add(native[0] if native else None, "best_native")
    grouped = defaultdict(list)
    for x in matched: grouped[pattern_key(x)].append(x)
    consistent = [v for v in grouped.values() if len({x["condition_id"] for x in v}) >= 2 and all(x["benefit_n_s"] > 0 for x in v)]
    if consistent:
        add(max(consistent, key=lambda v: sum(x["benefit_n_s"] for x in v) / len(v))[0], "consistent_positive_across_conditions")
    switches = [v for v in grouped.values() if any(x["benefit_n_s"] > 0 for x in v) and any(x["benefit_n_s"] < 0 for x in v)]
    if switches:
        add(max(switches, key=lambda v: max(x["benefit_n_s"] for x in v) - min(x["benefit_n_s"] for x in v))[0], "benefit_sign_switch_across_conditions")
    boundary = defaultdict(list)
    for x in source:
        if not x["synchronous"]: boundary[pattern_key(x)].append(x)
    boundary_groups = [v for v in boundary.values() if any(x["status"] == "VALID" for x in v) and
                       any(x["status"] == "INFEASIBLE" for x in v)]
    if boundary_groups:
        group = max(boundary_groups, key=lambda v: (v[0]["amplitude"], len(v)))
        add(next(x for x in group if x["status"] == "VALID"), "cross_condition_feasibility_boundary")
    conflicts = [x for x in matched if x["short_benefit_1p5_n_s"] * x["benefit_n_s"] < 0]
    if conflicts:
        add(max(conflicts, key=lambda x: abs(x["benefit_n_s"] - x["short_benefit_1p5_n_s"])), "short_full_credit_conflict")
    add(min(coarse, key=lambda x: abs(x["benefit_n_s"])) if coarse else None, "near_neutral")
    add(min(coarse, key=lambda x: x["benefit_n_s"]) if coarse else None, "safe_worse")
    for row in matched + native:
        if len(seeds) >= 8: break
        add(row, "promising_fallback")
    selection = []
    audit = []
    for row, reason in seeds[:8]:
        p = dict(row["pattern"])
        p["amplitude"] = round(min(.2, max(.005, p["amplitude"] + (.015 if p["amplitude"] < .12 else -.015))), 3)
        p["peak"] = {.3: .5, .5: .7, .7: .3}[p["peak"]]
        selection.append(p)
        audit.append({"source_run_id": row["run_id"], "reason": reason,
                      "source_benefit_n_s": row["benefit_n_s"], "variant": p})
    selection_path = DOC / "REFINEMENT_SELECTION.json"
    selection_record = {"schema": "coordination_refinement_selection_v1",
                        "source": "discovery-role coarse attempts only", "selected": audit}
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection_record:
            raise RuntimeError("frozen refinement selection changed")
    else:
        save(selection_path, selection_record)
    return selection


def choose_validation():
    data = [x for x in rows() if x["stage"] in ("COARSE", "REFINEMENT") and x["status"] == "VALID"]
    matched = [x for x in data if x["timing_isolated"]]
    native = [x for x in data if x["arm"] == "NATIVE"]
    selected = []
    for group in (sorted(matched, key=lambda x: -x["benefit_n_s"])[:1],
                  sorted(native, key=lambda x: -x["benefit_n_s"])[:1],
                  sorted(data, key=lambda x: abs(x["benefit_n_s"]))[:1],
                  sorted(data, key=lambda x: x["benefit_n_s"])[:1]):
        for x in group:
            p = x["pattern"]
            if pattern_key(p) not in {pattern_key(q) for q in selected}: selected.append(p)
    for lead in (1, -1):
        for x in sorted(data, key=lambda x: -x["benefit_n_s"]):
            p = x["pattern"]
            if p["lead"] == lead and pattern_key(p) not in {pattern_key(q) for q in selected}:
                selected.append(p); break
    sync = next(x for x in coarse_patterns() if x["synchronous"])
    if pattern_key(sync) not in {pattern_key(q) for q in selected}: selected.append(sync)
    return selected[:7]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop-after-coarse", action="store_true")
    args = parser.parse_args()
    if not ELIGIBLE:
        raise RuntimeError("systemic baseline failure")
    discovery = [c for c in ELIGIBLE if c["role"] != "validation"]
    validation = [c for c in ELIGIBLE if c["role"] == "validation"]
    coarse = freeze_plan("COARSE_PLAN.json", make_entries("COARSE", coarse_patterns(), discovery),
                         {"patterns": len(coarse_patterns()), "eligible_conditions": [x["id"] for x in discovery]})
    if not execute("COARSE", coarse): return
    if args.stop_after_coarse: return
    refinement = freeze_plan("REFINEMENT_PLAN.json", make_entries("REFINEMENT", choose_refinement(), discovery),
                             {"selection": "derived from discovery-role coarse results only"})
    if not execute("REFINEMENT", refinement): return
    cross = freeze_plan("CROSS_CONDITION_PLAN.json", make_entries("VALIDATION", choose_validation(), validation),
                        {"selection": "frozen before validation-role outcomes inspected"})
    execute("VALIDATION", cross)


if __name__ == "__main__": main()
