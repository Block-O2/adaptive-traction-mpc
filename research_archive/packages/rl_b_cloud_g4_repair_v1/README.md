# Native MuJoCo RL-B CPU handoff

This is a disabled-by-default engineering package. It contains no expert weights,
teacher trajectories, credentials, simulator installation, or automatic cloud billing.
The 41D actor observes causal sensor/estimator/reference/task data. Its two continuous
actions specify legal progress fractions at native planner events. They are **not**
50ms decisions. The original certificate, current-state admission, 40ms bridge,
100ms lifecycle, governor, hard safety and native receipt owner remain in the source.

Use Ubuntu 24.04, Python 3.12, 16 dedicated vCPU, 64GiB RAM and 100–200GB NVMe.
No GPU is required. The default execution is one physics environment, one logical
CPU and one numerical/Torch thread. Extra vCPU are headroom; parallel scaling has
not been qualified. Three independent training seeds are reserved.

On a fresh server, a user may install the OS prerequisites explicitly:

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv libgl1 libegl1 libglfw3
bash install.sh
.venv/bin/python verify_package.py
```

The install script uses a venv, pinned Python package versions and the public
PyTorch CPU wheel index. It requires Internet access. Wheels are not included;
the Linux installation and cross-platform numeric parity must be verified there.
The local reference used Python 3.12.14, MuJoCo 3.10.0, SB3 2.6.0 and Torch 2.7.1+cpu.

First run the bounded cloud smoke (rough target 10–15 minutes; hard 14-minute cap,
actual throughput must be measured on the server). Commands never run on install:

```bash
bash smoke.sh --enable
```

It runs mathematical/TEST_ONLY tests and genuine legal hold/maximal/random tasks,
independently audits rewards, native ownership, source age, admission and bridges,
then writes an on-target content-addressed READINESS.json. PPO refuses to start
without the current source/config/runtime gate. It next performs 16 PPO decisions,
checks trained policy/Adam/RNG restoration, resumes another 16 decisions in a fresh
physical episode, and evaluates initial and final frozen policies separately.
These are mechanical checks; they cannot establish learned-policy improvement.
On any failure preserve the entire run directory and stop promotion.

After a clean cloud smoke, the user may explicitly start one Pilot seed:

```bash
.venv/bin/python resource_guard.py --out runs/pilot_guard_seed1 --seconds 21600 -- \
  .venv/bin/python train.py --enable --profile pilot --seed 20261021 --out runs/pilot_seed1
```

The Pilot template stops at the earliest of 100,000 native decisions, 100 completed
episodes, 6 hours, 20GiB output or a resource limit. At the inherited 14–23 decisions
per successful development episode, the episode cap will generally dominate, but
PPO can take a different event count or fail: measure it directly on the server.
Do not extrapolate these counts from the old 50ms prototype. Run seeds 20261022 and
20261023 sequentially only after the first Pilot is reviewed. A first exploratory
budget of 100 completed episodes per seed is already configured. Count both failed
and successful episode terminals against that budget; report task success separately.

Checkpoint/resume (replace the example checkpoint with the latest complete generation):

```bash
.venv/bin/python resource_guard.py --out runs/resume_guard_seed1 --seconds 21600 -- \
  .venv/bin/python train.py --enable --profile pilot --seed 20261021 \
  --resume runs/pilot_seed1/checkpoints/update_000005 --out runs/resumed_seed1
.venv/bin/python resource_guard.py --out runs/eval_guard_seed1 --seconds 240 -- \
  .venv/bin/python evaluate.py --enable --checkpoint runs/resumed_seed1/checkpoints/final \
  --seed 20262021 --out runs/eval_seed1
```

Checkpoint metadata is written last as the atomic generation marker. Do not use
`.writing.*` or a generation without JSON. Hash mismatch/contract mismatch refuses
restore. Resume restores policy, Adam, RNG, update/decision counts and completed
episode counts, but starts a new physics episode. The partial simulator state and
partial PPO rollout are not restored; their spent work remains in START/END/raw logs.
If interrupted, use the last complete update generation, a new output name and the
same seed/profile. Config/code changes require fresh qualification; do not edit
saved checkpoints or READINESS by hand to bypass the gate.

Full native raw is retained for both training and evaluation. Monitor disk: a Pilot
may hit its output cap before its decision/episode cap. This conservative package
stops instead of deleting failed evidence or silently switching evidence modes.
No unattended million-decision run is recommended. `future_1m` is an inactive template
with its own 5,000-episode/24-hour/40GiB limits; require Pilot/scaling/storage review first.

Resource protection reads available memory directly, checks every 0.5s, refuses to
launch below 4.25GiB, stops below 3GiB, stops sustained Linux swap growth or monitor
failure, caps wall/disk output, and kills only its own process group/Windows Job.
It never changes power, WSL memory, drivers or another user's processes. Use the
outer resource_guard command for every standalone physics/training/evaluation run.

Reward v2 retains the original progress/completion/force/motion coefficients on
successful tasks. On failure the terminal potential is zero, cancelling accrued
progress: total failure return is at most -10 (gamma=1, nonnegative costs). Low
partial JF cannot earn completion. Completion requires original full phase sequence
and causal native commit; no reward controls hard safety. Task deadlines are observed
finite-MDP terminals (`terminated=True`, `truncated=False`). Resource failures are
infrastructure exceptions, not fabricated task outcomes or successful truncations.

Qualification scope is nominal scientific simulation only. Host real-time, patient
generalization, all-action safety and PPO performance are separate research claims.
