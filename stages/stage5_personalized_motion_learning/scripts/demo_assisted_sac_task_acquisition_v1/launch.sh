#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TASKDIR=/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1
PYTHON=/home/hank/envs/adaptive-online-rl-v1/bin/python
"$PYTHON" -u "$TASKDIR/run_paired.py" 2>&1 | tee "$TASKDIR/output/FORMAL_RUN.log"
"$PYTHON" -u "$TASKDIR/finish.py" 2>&1 | tee "$TASKDIR/output/FINISH.log"
