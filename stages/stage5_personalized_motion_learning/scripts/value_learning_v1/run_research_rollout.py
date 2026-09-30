"""Versioned research wrapper copied from frozen coordination runner; production unchanged."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in (
    "stages/stage5_personalized_motion_learning/src",
    "stages/stage4_adaptive_control/src",
    "stages/stage3_full3d/src",
    "stages/stage5_personalized_motion_learning/scripts/high_rom_v1",
):
    sys.path.insert(0, str(ROOT / relative))

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import (
    run_executed_case, advance_inter_rep_boundary, _jsonable,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import zero_value_decision_rows
from zero_value_30rep_checkpoint import load_checkpoint
from baseline_accounting_v2 import task_wrench_cost
from baseline_acceptance_v2 import assess
from evaluate_execution_mode import evaluate
from summarize_phase_b import DOC as PHASE_DOC

DOC = STAGE / "docs/coordination_pacing_exploration_v1"
OLD_RUNS = STAGE / "results/coordination_pacing_exploration_v1/runs"
RUNS = STAGE / "results/value_learning_research_v1/runs"
SESSION_CONTEXT = None
SOURCE_CHECKPOINT_SPEC = None
LAST_CAPTURE = None
OPTIONS = STAGE / "configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json"
CPBASE = STAGE / "results/zero_value_30rep_baseline_v3/formal_session_01"
CPDOC = STAGE / "docs/zero_value_30rep_baseline_v3"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n")


def source_context(condition):
    if SESSION_CONTEXT is not None:
        return SESSION_CONTEXT, None
    if SOURCE_CHECKPOINT_SPEC is not None:
        cp = SOURCE_CHECKPOINT_SPEC
        context, rows = load_checkpoint(Path(cp["absolute_path"]), cp["sha256"], cp["provenance_sha256"])
        boundary = advance_inter_rep_boundary(context, max_wait_s=2.0)
        return context, {"checkpoint": cp, "boundary": boundary}
    cp_rep = condition.get("checkpoint_rep")
    if cp_rep is None:
        return {}, None
    entry = next(x for x in json.loads((CPDOC / "SESSION_CHECKPOINTS_MANIFEST_V3.json").read_text())
                 if x["repetition_index"] == cp_rep)
    cp = CPBASE / entry["path"]
    if sha(cp) != entry["sha256"] or sha(CPBASE / "session_provenance.json") != entry["provenance_sha256"]:
        raise RuntimeError("frozen source checkpoint or provenance hash mismatch")
    context, rows = load_checkpoint(cp, entry["sha256"], entry["provenance_sha256"])
    if len(rows) != cp_rep:
        raise RuntimeError("checkpoint repetition mismatch")
    boundary = advance_inter_rep_boundary(context, max_wait_s=2.0)
    return context, {"checkpoint": entry, "boundary": boundary}


def baseline_plan(artifact):
    grouped = {"OUTBOUND": [], "RETURN": []}
    for decision in artifact["task_decisions"]:
        phase = decision["phase"]
        if phase not in grouped or "evaluations" not in decision:
            continue
        chosen = next(x for x in decision["evaluations"] if x["label"] == decision["executed_label"])
        grouped[phase].append({
            "target_q_rad": chosen["target_q_rad"],
            "duration_s": chosen["schedule"]["duration_s"],
            "phase_elapsed_s": decision["phase_elapsed_s"],
            "target_dq_rad_s": chosen["schedule"]["target_dq_rad_s"],
        })
    return grouped


def trace_metrics(trace, case):
    mask = trace["stage"] == "TASK"
    t = np.asarray(trace["time_s"][mask], dtype=float)
    phase = np.asarray(trace["task_phase"][mask])
    force = np.linalg.norm(np.asarray(trace["physical_cuff_force_world_n"][mask]), axis=1)
    q = np.asarray(trace["evaluation_only_human_state_rad_rad_s"][mask])[:, :2]
    dq = np.asarray(trace["evaluation_only_human_state_rad_rad_s"][mask])[:, 2:]
    ddq = np.asarray(trace["actual_human_acceleration_rad_s2"][mask])
    dt = np.diff(t)
    if not len(dt) or np.max(np.abs(dt - .005)) > 1e-9:
        raise ValueError("nonregistered task trace grid")
    costs = force[:-1] * dt
    def cost(sel): return float(np.sum(costs[sel]))
    start = np.radians(case["task"]["start_deg"])
    goal = np.radians(case["task"]["goal_deg"])
    lead = {}
    for label, origin, target in (("OUTBOUND", start, goal), ("RETURN", goal, start)):
        selected = phase == label
        progress = (q[selected] - origin) / (target - origin)
        difference = progress[:, 0] - progress[:, 1]
        lead[label] = {"mean_normalized_hip_minus_knee": float(np.mean(difference)),
                       "peak_abs_normalized_lead": float(np.max(np.abs(difference)))} if len(difference) else None
    return {
        "mean_force_n": float(np.mean(force[:-1])),
        "rms_force_n": float(np.sqrt(np.mean(force[:-1] ** 2))),
        "peak_force_n": float(np.max(force)),
        "duration_s": float(np.sum(dt)),
        "outbound_duration_s": float(np.sum(phase[:-1] == "OUTBOUND") * .005),
        "return_duration_s": float(np.sum(phase[:-1] == "RETURN") * .005),
        "cost_0p5_n_s": cost((t[:-1] - t[0]) < .5 - 1e-10),
        "cost_1p5_n_s": cost((t[:-1] - t[0]) < 1.5 - 1e-10),
        "cost_outbound_n_s": cost(phase[:-1] == "OUTBOUND"),
        "cost_full_n_s": float(np.sum(costs)),
        "q_range_rad": (np.max(q, axis=0) - np.min(q, axis=0)).tolist(),
        "dq_rms_rad_s": np.sqrt(np.mean(dq ** 2, axis=0)).tolist(),
        "ddq_rms_rad_s2": np.sqrt(np.mean(ddq ** 2, axis=0)).tolist(),
        "actual_path_q_rad": q[::20].tolist(),
        "actual_path_time_s": (t[::20] - t[0]).tolist(),
        "coordination_lead_metrics": lead,
    }


def run(condition_id, arm, pattern, run_id):
    global SOURCE_CHECKPOINT_SPEC
    SOURCE_CHECKPOINT_SPEC = None if pattern is None else pattern.get("source_checkpoint")
    if pattern and pattern.get("capture_snapshot_dir"):
        os.environ["VALUE_LATENCY_SNAPSHOT_DIR"] = pattern["capture_snapshot_dir"]
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(key) != "1":
            raise RuntimeError(f"{key} must be one")
    matrix = json.loads((DOC / "CONDITION_MATRIX.json").read_text())
    condition = next(x for x in matrix["conditions"] if x["id"] == condition_id)
    case_path = ROOT / condition["case_path"]
    if sha(case_path) != condition["case_sha256"] or sha(OPTIONS) != matrix["options_sha256"]:
        raise RuntimeError("frozen case/options hash mismatch")
    case = json.loads(case_path.read_text())
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=False)
    rep = int(condition.get("checkpoint_rep") or 0) + 1
    rep_dir = out / f"rep_{rep:02d}"
    record = {
        "schema": "value_learning_research_rollout_v1", "condition_id": condition_id,
        "arm": arm, "pattern": pattern, "run_id": run_id, "status": "RUNNING",
        "case_path": condition["case_path"], "case_sha256": condition["case_sha256"],
        "options_sha256": matrix["options_sha256"], "execution_mode": "SCIENTIFIC_SIMULATION",
        "command": sys.argv, "host": platform.node(), "python": sys.version,
        "research_source_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted((STAGE / "scripts/value_learning_v1").glob("*.py"))},
        "source_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
    }
    save(out / "rollout_result.json", record)
    started = time.monotonic()
    try:
        context, source = source_context(condition)
        if source is not None:
            record["source_checkpoint_sha256"] = source["checkpoint"]["sha256"]
            record["boundary_before_J_F_n_s"] = float(source["boundary"]["cost"]["J_F_n_s"])
            save(out / "boundary_before.json", source["boundary"])
        if pattern is not None:
            import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime
            from research_adapter import (
                ResearchPlanner, SPEC_ENV, snapshot_research_task_call,
            )
            reference = json.loads((OLD_RUNS / condition["baseline_run_id"] / "rollout_result.json").read_text())
            if reference["status"] != "VALID":
                raise RuntimeError("condition baseline is not valid")
            os.environ[SPEC_ENV] = json.dumps({**pattern, "arm": arm,
                                               "baseline_waypoints": reference["baseline_waypoints"]}, sort_keys=True)
            runtime.TerminalSetHumanWaypointPlannerV1 = ResearchPlanner
            runtime.snapshot_task_call = snapshot_research_task_call
        capture = {}
        global LAST_CAPTURE
        LAST_CAPTURE = capture
        summary = run_executed_case(
            rep_dir, qualification_case=case, qualification_arm="continual_adaptive",
            simulate_planning_latency=True, formal_qualification=False,
            dev_a_recovery=True, dev_c_bumpless_transfer=False,
            dev_d_rigid_table_reference=True,
            autonomous_recovery_options=json.loads(OPTIONS.read_text()),
            task_timeout_s=30.0, runtime_capture=capture,
            execution_mode="SCIENTIFIC_SIMULATION", scientific_host_delay_s=0.0,
            session_context=context,
        )
        save(rep_dir / "HIGH_ROM_CASE_RESULT.json", {
            "schema": "high_rom_v1_development_case_result", "case_key": case["case_key"],
            "case_sha256": sha(case_path), "options_sha256": sha(OPTIONS),
            "execution_mode": "SCIENTIFIC_SIMULATION", "scientific_host_delay_ms": 0.0,
            "plant_mode": "low_rom" if "research_model" not in case else "research_model",
            "session_id": run_id, "repetition_index": rep, "command": sys.argv,
            "status": summary["status"], "abort_reason": summary.get("abort_reason"),
            "elapsed_host_s": time.monotonic() - started,
        })
        score_case = {"case_key": case["case_key"], "physical_variant": case["cell"]["family"],
                      "candidate": case.get("coordination_candidate", "low_rom_registered"),
                      "path": condition["case_path"], "sha256": sha(case_path)}
        mode = evaluate(rep_dir, score_case,
                        json.loads((PHASE_DOC / "PHASE_B_MATRIX.json").read_text())["scoring"],
                        goal_deg=case["task"]["goal_deg"], start_deg=case["task"]["start_deg"])
        save(rep_dir / "MODE_AWARE_RESULT_V2.json", mode)
        artifact = json.loads((rep_dir / "runtime_artifacts.json").read_text())
        trace = np.load(rep_dir / "trace.npz")
        record.update(run_status=summary["status"], abort_reason=summary.get("abort_reason"),
                      physical_validity=mode["physical_task_result"]["status"],
                      scientific_validity=mode["scientific_validity"]["status"],
                      minimum_clearance_m=summary["task"].get("minimum_session_clearance_m_deployable"),
                      governor_delay_added_s=float(sum(x.get("delay_added_s", 0.0) for x in artifact.get("reference_governor_records", []))),
                      governor_max_single_deferral_s=float(max((x.get("delay_added_s", 0.0) for x in artifact.get("reference_governor_records", [])), default=0.0)),
                      governor_delay_semantics="sum of recorded per-cycle desired-minus-selected progress; not an additive contribution to task duration",
                      governor_delay_event_count=len(artifact.get("reference_governor_records", [])),
                      rss_event_count=len(artifact.get("rolling_splice_events", [])),
                      fallback_event_count=len(artifact.get("safe_fallback_events", [])),
                      terminal_commit_attempt_count=len(artifact.get("return_commit_attempts", [])),
                      decision_count=len(summary["decisions"]))
        if summary["status"] != "COMPLETE":
            reason = str(summary.get("abort_reason") or "")
            record.update(status="INFEASIBLE" if any(s in reason for s in
                          ("RESEARCH_INFEASIBLE", "COORDINATION_INFEASIBLE", "MATCHED_PACING_INFEASIBLE", "NO_FEASIBLE_WAYPOINT")) else "INVALID",
                          failure_reason=reason)
        else:
            costs = task_wrench_cost(trace, trace["stage"] == "TASK")
            acceptance = assess(summary, mode, artifact, costs, zero_value_decision_rows(summary["decisions"]))
            metrics = trace_metrics(trace, case)
            bootstrap_cost = float(capture["runtime"].get("fresh_track_bootstrap", {}).get("cost", {}).get("J_F_n_s", 0.0))
            record.update(status="VALID" if acceptance["overall_baseline_scientific_result"] == "PASS" else "INVALID",
                          gate_reasons=acceptance["gate_reasons"], J_F_task_n_s=costs["J_F_n_s"],
                          J_F_session_n_s=costs["J_F_n_s"] + float(record.get("boundary_before_J_F_n_s", 0.0)) + bootstrap_cost,
                          fresh_track_bootstrap_J_F_n_s=bootstrap_cost,
                          moment_integral_nm_s=costs["moment_integral_nm_s"],
                          moment_peak_nm=costs["peak_moment_nm"], **metrics)
        record["baseline_waypoints"] = baseline_plan(artifact) if pattern is None else None
        record["planned_segments"] = baseline_plan(artifact)
        realized = {"OUTBOUND": [], "RETURN": []}
        for phase_name in realized:
            decisions = [d for d in artifact.get("task_decisions", []) if d.get("phase") == phase_name and "evaluations" in d]
            end = record.get("outbound_duration_s" if phase_name == "OUTBOUND" else "return_duration_s")
            for i, decision in enumerate(decisions):
                next_elapsed = decisions[i + 1]["phase_elapsed_s"] if i + 1 < len(decisions) else end
                realized[phase_name].append(None if next_elapsed is None else float(next_elapsed - decision["phase_elapsed_s"]))
        record["realized_segments_s"] = realized
        record["duration_search_count"] = sum(
            bool(x.get("execution_screen", {}).get("duration_search_used"))
            for d in artifact.get("task_decisions", []) for x in d.get("evaluations", [])
            if x.get("label") == d.get("executed_label"))
        record["raw_files_sha256"] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*"))
                                      if p.is_file() and p.name != "rollout_result.json"}
    except BaseException as error:
        record.update(status="EXCEPTION", failure_reason=f"{type(error).__name__}:{error}",
                      traceback=traceback.format_exc()[-10000:])
    finally:
        record["elapsed_host_s"] = time.monotonic() - started
        save(out / "rollout_result.json", record)
    print(json.dumps({k: record.get(k) for k in ("run_id", "status", "J_F_task_n_s", "duration_s", "failure_reason", "gate_reasons", "elapsed_host_s")}), flush=True)

    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--arm", choices=("BASELINE", "NATIVE", "MATCHED"), required=True)
    parser.add_argument("--pattern-json")
    parser.add_argument("--pattern-file", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.pattern_json is not None and args.pattern_file is not None:
        parser.error("provide only one pattern source")
    pattern = json.loads(args.pattern_file.read_text()) if args.pattern_file else (None if args.pattern_json is None else json.loads(args.pattern_json))
    run(args.condition, args.arm, pattern, args.run_id)
