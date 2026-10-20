#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TASKDIR=/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/bc_reproduction_gate_v1
PYTHON=/home/hank/envs/adaptive-online-rl-v1/bin/python
mkdir -p "$TASKDIR/output"
exec > >(tee -a "$TASKDIR/output/FORMAL_RUN.log") 2>&1
"$PYTHON" -m compileall -q "$TASKDIR"
"$PYTHON" -u "$TASKDIR/preflight.py"
"$PYTHON" -u "$TASKDIR/teacher.py"
"$PYTHON" -u "$TASKDIR/train.py"
if "$PYTHON" -c 'import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if len(r)==3 and all(x["offline_pass"] for x in r) else 1)' "$TASKDIR/output/OFFLINE_RESULTS.json"; then
    for seed in 20261004 20261005 20261006; do
        "$PYTHON" -u "$TASKDIR/evaluate.py" "$seed" formal
    done
    "$PYTHON" -u "$TASKDIR/diagnose.py"
    if "$PYTHON" -c 'import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if r["replay_required"] else 1)' "$TASKDIR/output/BEST_SELECTION.json"; then
        seed=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["seed"])' "$TASKDIR/output/BEST_SELECTION.json")
        "$PYTHON" -u "$TASKDIR/evaluate.py" "$seed" confirmation
    fi
fi
"$PYTHON" -u "$TASKDIR/finish.py"
