#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TASKDIR=/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1
PYTHON=/home/hank/envs/adaptive-online-rl-v1/bin/python
"$PYTHON" -u "$TASKDIR/offline_q_phase_audit_v1.py" > "$TASKDIR/output/OFFLINE_Q_PHASE_AUDIT.log" 2>&1
"$PYTHON" -u "$TASKDIR/final_verify_v2.py" 2>&1 | tee "$TASKDIR/output/FINAL_VERIFICATION_V2.log"
