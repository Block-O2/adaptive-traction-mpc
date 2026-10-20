#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TASKDIR=/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1
PYTHON=/home/hank/envs/adaptive-online-rl-v1/bin/python
"$PYTHON" -u "$TASKDIR/resume_a_guardfix_v2.py" 2>&1 | tee "$TASKDIR/output/RESUME_A_GUARDFIX_V2.log"
"$PYTHON" -u "$TASKDIR/settling_audit.py"
"$PYTHON" -u "$TASKDIR/finish.py" 2>&1 | tee "$TASKDIR/output/FINISH.log"
