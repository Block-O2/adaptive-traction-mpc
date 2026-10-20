#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TASK=/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/action_representation_switch_audit_v1
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
"$PY" -u "$TASK/preflight.py"
"$PY" -u "$TASK/offline.py"
for seed in 20261004 20261005 20261006; do
    "$PY" -u "$TASK/replay.py" "$seed"
done
"$PY" -u "$TASK/fit_delta.py"
"$PY" -u "$TASK/finish.py"
