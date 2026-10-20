"""Preserve earlier pilot records and repeat matched baselines with full causal clearance."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/coordination_pacing_exploration_v1"
RUNS = STAGE / "results/coordination_pacing_exploration_v1/runs"
RUNNER = Path(__file__).with_name("run_coordination_rollout_v1.py")
original = json.loads((DOC / "BASELINE_MATRIX_VALIDATION.json").read_text())
pattern = {"lead": 0, "amplitude": 0.0, "peak": 0.5, "horizon": "H4",
           "synchronous": False, "return_reverse": False, "matched_duration_factor": 1.3}
env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def save(value):
    (DOC / "BASELINE_MATRIX_VALIDATION_V2.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(ident, run_id):
    path = RUNS / run_id / "rollout_result.json"
    if not path.exists():
        proc = subprocess.run([sys.executable, str(RUNNER), "--condition", ident,
            "--arm", "MATCHED", "--run-id", run_id,
            "--pattern-json", json.dumps(pattern, separators=(",", ":"))],
            env=env, capture_output=True, text=True, timeout=180)
        print(json.dumps({"run_id": run_id, "exit": proc.returncode,
                          "stdout": proc.stdout.strip()[-700:], "stderr": proc.stderr[-700:]}), flush=True)
    return json.loads(path.read_text()) if path.exists() else {"status": "EXCEPTION", "failure_reason": "missing result"}


rows = []
for item in original["rows"]:
    row = dict(item)
    row["earlier_matched_status"] = row["matched_status"]
    row["earlier_matched_screen_limitation"] = "fixed-schedule causal tracking-offset clearance certificate absent from exploration adapter; earlier run retained as pilot, excluded from formal baseline"
    row["matched_baseline_pass"] = False
    row["matched_baseline_J_F_task_n_s"] = None
    row["matched_baseline_duration_s"] = None
    row["matched_replay_abs_error_n_s"] = None
    if row["native_replay_pass"]:
        ident = row["condition_id"]
        a = run(ident, f"matched_baseline_{ident}_certified")
        b = run(ident, f"matched_baseline_{ident}_certified_replay") if a["status"] == "VALID" else None
        difference = (abs(a["J_F_task_n_s"] - b["J_F_task_n_s"])
                      if b is not None and b.get("J_F_task_n_s") is not None else None)
        row.update(matched_baseline_pass=a["status"] == "VALID" and b is not None and b["status"] == "VALID" and difference is not None and difference <= 1e-6,
                   matched_baseline_J_F_task_n_s=a.get("J_F_task_n_s"),
                   matched_baseline_duration_s=a.get("duration_s"),
                   matched_replay_abs_error_n_s=difference,
                   matched_status=a["status"],
                   certified_run_id=f"matched_baseline_{ident}_certified",
                   certified_replay_run_id=f"matched_baseline_{ident}_certified_replay",
                   certified_failure_reasons=[x.get("failure_reason") or x.get("abort_reason") for x in (a, b) if x is not None and x["status"] != "VALID"])
    rows.append(row)
    save({"schema": "coordination_baseline_matrix_validation_v2", "status": "IN_PROGRESS",
          "repair": "recompute causal tracking-offset clearance on exact fixed polynomial; no production/safety change",
          "matched_duration_factor": 1.3, "rows": rows})
    print(json.dumps(row), flush=True)
save({"schema": "coordination_baseline_matrix_validation_v2", "status": "COMPLETE",
      "repair": "recompute causal tracking-offset clearance on exact fixed polynomial; no production/safety change",
      "matched_duration_factor": 1.3, "rows": rows})
