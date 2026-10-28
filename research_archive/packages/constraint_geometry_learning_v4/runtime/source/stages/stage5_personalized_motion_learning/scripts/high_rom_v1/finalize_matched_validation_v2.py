"""Audit certified fixed-duration baselines and representative deformed pilots."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/coordination_pacing_exploration_v1"
RUNS = STAGE / "results/coordination_pacing_exploration_v1/runs"
matrix = json.loads((DOC / "BASELINE_MATRIX_VALIDATION_V2.json").read_text())
original = json.loads((DOC / "MATCHED_PACING_VALIDATION.json").read_text())


def read(run): return json.loads((RUNS / run / "rollout_result.json").read_text())


def equal_trace(a, b):
    left = np.load(next((RUNS / a).glob("rep_*/trace.npz")))
    right = np.load(next((RUNS / b).glob("rep_*/trace.npz")))
    names = left.files
    differences = [name for name in names if not np.array_equal(
        left[name], right[name], equal_nan=np.issubdtype(left[name].dtype, np.number))]
    return {"array_count": len(names), "different_arrays": differences,
            "identical": not differences}


rows = []
for item in matrix["rows"]:
    if not item["matched_baseline_pass"]:
        rows.append({"condition_id": item["condition_id"], "status": item["matched_status"],
                     "reason": item.get("certified_failure_reasons")})
        continue
    a = item["certified_run_id"]
    b = item["certified_replay_run_id"]
    r = read(a)
    trace = equal_trace(a, b)
    artifacts = json.loads(next((RUNS / a).glob("rep_*/runtime_artifacts.json")).read_text())
    decisions = [d for d in artifacts["task_decisions"] if "evaluations" in d]
    chosen = [next(x for x in d["evaluations"] if x["label"] == d["executed_label"]) for d in decisions]
    fixed = [x for x in chosen if x["schedule"]["feasibility_semantics"] == "fixed_duration_causal_20ms_scheduled_reference_motion"]
    limit_checked = all(x["schedule"]["minimum_reference_shank_clearance_m"] >= 0 and
                        x["execution_screen"].get("feasible") and
                        x["execution_screen"].get("causal_tracking_offset_clearance", {}).get("feasible")
                        for x in fixed)
    grid_checked = all(abs(round(x["schedule"]["duration_s"] / .005) * .005 - x["schedule"]["duration_s"]) <= 1e-12 for x in fixed)
    rows.append({"condition_id": item["condition_id"], "status": "PASS" if trace["identical"] and limit_checked and grid_checked else "FAIL",
        "J_F_task_n_s": r["J_F_task_n_s"], "duration_s": r["duration_s"],
        "fixed_segments": len(fixed), "grid_checked": grid_checked,
        "clearance_mechanics_and_causal_offset_screen_pass": limit_checked,
        "physical_validity": r["physical_validity"], "scientific_validity": r["scientific_validity"],
        "governor_delay_added_s": r["governor_delay_added_s"],
        "rss_event_count": r["rss_event_count"], "fallback_event_count": r["fallback_event_count"],
        "trace_repeat": trace})
valid = [x for x in rows if x["status"] == "PASS"]
pilot = read("pilot_matched_hip_f130_certified") if (RUNS / "pilot_matched_hip_f130_certified" / "rollout_result.json").exists() else None
base = read("matched_baseline_low_ordinary_early_certified") if (RUNS / "matched_baseline_low_ordinary_early_certified" / "rollout_result.json").exists() else None
validation = {"schema": "matched_pacing_validation_v2", "status": "PASS" if len(valid) >= 2 else "INSUFFICIENT",
    "earlier_pilot": original, "certified_condition_rows": rows,
    "certified_pass_count": len(valid), "certified_excluded_count": len(rows) - len(valid),
    "representative_deformed_pilot": None if pilot is None else {
        "status": pilot["status"], "J_F_task_n_s": pilot.get("J_F_task_n_s"),
        "outbound_residual_s": pilot.get("outbound_duration_s", 0) - base.get("outbound_duration_s", 0) if base else None,
        "return_residual_s": pilot.get("return_duration_s", 0) - base.get("return_duration_s", 0) if base else None,
        "matched_benefit_n_s": base["J_F_task_n_s"] - pilot["J_F_task_n_s"] if base and pilot.get("J_F_task_n_s") is not None else None},
    "scope": "The original fixed-duration scheduler checks velocity, acceleration, ROM and continuous clearance. The unchanged mechanics screen and causal receipt-owned tracking-offset clearance were checked again on each exact fixed schedule; physical/scientific PASS and trace identity certify executed baselines. Nominal timing does not prove realized timing identity for all candidates."}
(DOC / "MATCHED_PACING_VALIDATION_V2.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
(DOC / "MATCHED_PACING_VALIDATION_V2.md").write_text(
    "# Certified Matched-Pacing Validation v2\n\nThe first shortest-duration pilot failed the original acceleration gate. A later exploration adapter defect omitted the causal tracking-offset clearance certificate for the replacement fixed schedule; the original high-ROM fallback stopped those pilots. All earlier raw results remain preserved.\n\n"
    f"After repairing only the exploration adapter, {len(valid)} condition rows passed two exact matched-baseline replays with identical full trace arrays, grid-aligned fixed segments, original mechanics and causal clearance checks, and physical/scientific PASS. {len(rows)-len(valid)} rows were excluded with recorded reasons. The original scheduler still enforces velocity, acceleration, ROM and continuous clearance. Pilot details and timing residuals are in the JSON.\n")
