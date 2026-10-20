"""Replay every frozen condition twice, then validate common matched pacing."""
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
matrix = json.loads((DOC / "CONDITION_MATRIX.json").read_text())
pattern = {"lead": 0, "amplitude": 0.0, "peak": 0.5, "horizon": "H4",
           "synchronous": False, "return_reverse": False, "matched_duration_factor": 1.3}
official = json.loads((STAGE / "docs/zero_value_30rep_baseline_v3/PER_REPETITION_V3.json").read_text())
env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(condition, arm, run_id, pattern=None):
    result_path = RUNS / run_id / "rollout_result.json"
    if not result_path.exists():
        cmd = [sys.executable, str(RUNNER), "--condition", condition["id"], "--arm", arm,
               "--run-id", run_id]
        if pattern is not None:
            cmd += ["--pattern-json", json.dumps(pattern, separators=(",", ":"))]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
        print(json.dumps({"run_id": run_id, "exit": proc.returncode,
                          "stdout": proc.stdout.strip()[-700:], "stderr": proc.stderr[-500:]}), flush=True)
    return json.loads(result_path.read_text()) if result_path.exists() else {"status": "EXCEPTION", "failure_reason": "missing_result"}


rows = []
for condition in matrix["conditions"]:
    a = run(condition, "BASELINE", condition["baseline_run_id"])
    b = run(condition, "BASELINE", condition["baseline_replay_run_id"])
    difference = (abs(a["J_F_task_n_s"] - b["J_F_task_n_s"])
                  if a.get("J_F_task_n_s") is not None and b.get("J_F_task_n_s") is not None else None)
    official_difference = (abs(a["J_F_task_n_s"] - official[condition["checkpoint_rep"]]["J_F_task_n_s"])
                           if condition.get("checkpoint_rep") is not None and a.get("J_F_task_n_s") is not None else None)
    native_pass = (a["status"] == b["status"] == "VALID" and difference is not None and difference <= 1e-6
                   and (official_difference is None or official_difference <= 1e-6))
    matched = None
    matched_replay = None
    if native_pass:
        matched = run(condition, "MATCHED", f"matched_baseline_{condition['id']}", pattern)
        if matched["status"] == "VALID":
            matched_replay = run(condition, "MATCHED", f"matched_baseline_{condition['id']}_replay", pattern)
    matched_difference = (abs(matched["J_F_task_n_s"] - matched_replay["J_F_task_n_s"])
                          if matched is not None and matched_replay is not None and
                          matched.get("J_F_task_n_s") is not None and matched_replay.get("J_F_task_n_s") is not None else None)
    row = {"condition_id": condition["id"], "role": condition["role"],
           "native_replay_pass": native_pass, "native_baseline_J_F_task_n_s": a.get("J_F_task_n_s"),
           "native_replay_abs_error_n_s": difference, "official_abs_error_n_s": official_difference,
           "matched_baseline_pass": matched is not None and matched_replay is not None and
           matched["status"] == matched_replay["status"] == "VALID" and
           matched_difference is not None and matched_difference <= 1e-6,
           "matched_replay_abs_error_n_s": matched_difference,
           "matched_baseline_J_F_task_n_s": matched.get("J_F_task_n_s") if matched else None,
           "matched_baseline_duration_s": matched.get("duration_s") if matched else None,
           "baseline_a_status": a["status"], "baseline_b_status": b["status"],
           "matched_status": matched["status"] if matched else "NOT_RUN",
           "failure_reasons": [x.get("failure_reason") or x.get("gate_reasons") for x in (a, b, matched, matched_replay) if x is not None and x["status"] != "VALID"]}
    rows.append(row)
    save(DOC / "BASELINE_MATRIX_VALIDATION.json", {"schema": "coordination_baseline_matrix_validation_v1",
         "matched_duration_factor": 1.3, "rows": rows})
    print(json.dumps(row), flush=True)
save(DOC / "BASELINE_MATRIX_VALIDATION.json", {"schema": "coordination_baseline_matrix_validation_v1",
     "matched_duration_factor": 1.3, "rows": rows})
