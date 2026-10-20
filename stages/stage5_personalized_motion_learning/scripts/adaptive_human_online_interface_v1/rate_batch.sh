#!/usr/bin/env bash
set -euo pipefail
cd /home/hank/coding/adaptive-traction-mpc-learning
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
py=/home/hank/envs/adaptive-online-v1/bin/python
script=stages/stage5_personalized_motion_learning/scripts/adaptive_human_online_interface_v1/closed_loop.py
for period in .005 .01 .02 .05; do
    "$py" -u "$script" "$period" switch
done
cp -r stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1/. /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_human_online_work/output/
