#!/usr/bin/env bash
set -euo pipefail
cd /home/hank/coding/adaptive-traction-mpc-learning
doc=stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1
env=/home/hank/envs/adaptive-online-rl-v1
/home/hank/envs/adaptive-traction-mpc/bin/python -m venv --system-site-packages "$env"
"$env/bin/python" -m pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128 > "$doc/CUDA_INSTALL_TORCH.log" 2>&1
"$env/bin/python" -m pip install --no-cache-dir gymnasium==1.1.1 stable-baselines3==2.6.0 sb3-contrib==2.6.0 ruckig==0.12.2 > "$doc/CUDA_INSTALL_RL.log" 2>&1
"$env/bin/python" -m pip check > "$doc/CUDA_PIP_CHECK.txt"
"$env/bin/python" -m pip freeze > "$doc/RL_ENV_FREEZE.txt"
nvidia-smi > "$doc/NVIDIA_SMI.txt"
"$env/bin/python" /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_human_online_work/cuda_check.py
