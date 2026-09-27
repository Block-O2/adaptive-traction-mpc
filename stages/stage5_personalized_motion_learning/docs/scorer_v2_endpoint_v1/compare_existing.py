"""Deterministic offline v1/v2 comparison on five retained high_100_sync runs."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from summarize_phase_b import score as score_v1
from score_return_endpoint_v2 import score_v2

STAGE = Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning")
BASE = STAGE / "results/runtime_gate_stability_v1/controlled_pre"
OUT = Path("/private/tmp/scorer_v2_existing")
OUT.mkdir(parents=True, exist_ok=True)
NAMES = ("p03_rss", "p04_rss", "p01_rss", "p03_c08", "p04_c08")
EXPECTED_V1 = {"p03_rss": False, "p04_rss": False, "p01_rss": True,
               "p03_c08": True, "p04_c08": True}
case_path = STAGE / "configs/high_rom_v1/high_rom_nominal_sync_100_v1.json"
case_data = json.loads(case_path.read_text())
case = {"case_key": case_data["case_key"], "physical_variant": "registered_interpolated",
        "candidate": case_data["coordination_candidate"], "path": str(case_path.resolve()),
        "sha256": hashlib.sha256(case_path.read_bytes()).hexdigest()}
contract_path = STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json"
contract = json.loads(contract_path.read_text())["scoring"]
allowed_changed = {"conditions", "true_return", "final_true_q_deg",
                   "final_true_dq_deg_s", "pass"}
new_keys = {"scorer_version", "rescore_status", "return_endpoint_provenance"}
rows = []
for name in NAMES:
    path = BASE / name
    old = score_v1(path, case, contract, goal_deg=(100., 100.), start_deg=(5., 10.))
    revised = score_v2(path, case, contract, goal_deg=(100., 100.), start_deg=(5., 10.))
    repeated = score_v2(path, case, contract, goal_deg=(100., 100.), start_deg=(5., 10.))
    if old["pass"] is not EXPECTED_V1[name]:
        raise AssertionError((name, "v1 original result drift"))
    if revised != repeated:
        raise AssertionError((name, "v2 nondeterministic"))
    if {k for k in old if old[k] != revised[k]} - allowed_changed:
        raise AssertionError((name, "non-endpoint field changed"))
    if set(revised) - set(old) != new_keys:
        raise AssertionError((name, "unexpected added fields"))
    if {k: v for k, v in old["conditions"].items() if k != "true_return"} != {
            k: v for k, v in revised["conditions"].items() if k != "true_return"}:
        raise AssertionError((name, "non-RETURN condition changed"))
    provenance = revised["return_endpoint_provenance"]
    rows.append({
        "case": name, "run": str(path),
        "scorer_v1_version": "scorer-v1-source-trace-final-row",
        "scorer_v1_sample_time_s": provenance["scorer_v1_time_s"],
        "scorer_v1_endpoint_dq_deg_s": old["final_true_dq_deg_s"],
        "scorer_v1_true_return": old["true_return"], "scorer_v1_pass": old["pass"],
        "physical_complete_commit_time_s": provenance["physical_complete_commit_time_s"],
        "scorer_v2_version": provenance["scorer_version"],
        "scorer_v2_sample_time_s": provenance["scorer_time_s"],
        "scorer_v2_endpoint_dq_deg_s": revised["final_true_dq_deg_s"],
        "scorer_v2_true_return": revised["true_return"], "scorer_v2_pass": revised["pass"],
        "other_task_safety_conditions_identical": True,
        "changed_existing_fields": sorted(k for k in old if old[k] != revised[k]),
        "rescore_status": revised["rescore_status"],
        "v1_raw_score": old, "v2_raw_score": revised,
    })
result = {"schema": "return_endpoint_scorer_v1_v2_existing_trace_comparison_v1",
          "category": "development_offline_rescore_not_qualification",
          "registered_case_sha256": case["sha256"],
          "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
          "cases": rows, "v1_pass_count": sum(x["scorer_v1_pass"] for x in rows),
          "v2_pass_count": sum(x["scorer_v2_pass"] for x in rows),
          "v1_to_v2_result_changes": sum(x["scorer_v1_pass"] != x["scorer_v2_pass"] for x in rows),
          "deterministic_repeat": True, "other_task_safety_conditions_identical": True}
(OUT / "SCORER_V1_V2_EXISTING_COMPARISON.json").write_text(json.dumps(result, indent=2) + "\n")
with (OUT / "SCORER_V1_V2_EXISTING_COMPARISON.csv").open("w", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["case", "v1_sample_s", "v1_hip_dq_deg_s", "v1_knee_dq_deg_s", "v1_pass",
                     "physical_complete_s", "v2_sample_s", "v2_hip_dq_deg_s", "v2_knee_dq_deg_s",
                     "v2_pass", "other_task_safety_identical", "rescore_status"])
    for x in rows:
        writer.writerow([x["case"], x["scorer_v1_sample_time_s"], *x["scorer_v1_endpoint_dq_deg_s"],
                         x["scorer_v1_pass"], x["physical_complete_commit_time_s"],
                         x["scorer_v2_sample_time_s"], *x["scorer_v2_endpoint_dq_deg_s"],
                         x["scorer_v2_pass"], True, x["rescore_status"]])
print(json.dumps({"cases": len(rows), "v1_pass": result["v1_pass_count"],
                  "v2_pass": result["v2_pass_count"],
                  "changes": result["v1_to_v2_result_changes"]}))
