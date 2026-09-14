# Stage-5 loaded-equilibrium and local HOLD engineering report

Evidence category: engineering smoke only. This work changes no Stage-3/4
source, Plant-v1 parameter, MPC weight, force gate, Safety Filter, BRAKE, Human
model, task tolerance, or learning behavior.

## Loaded equilibrium at 20 deg / 35 deg

The fixed registered Human model requires generalized input
`[41.0370809, -2.9848287] Nm` at `q=[20,35] deg`, `dq=ddq=0`. The allocator and
nominal Plant-v1 interface close this equilibrium with Human cuff wrench
`[-81.3413444, 0, 63.0840660, 0, 8.5229644, 0]` in world units (N, Nm), whose
force norm is `102.9374383 N`.

The corresponding controller-nominal interface strain in the Human cuff frame
is `[-3.7958825, 0, 1.5952736] mm` and `[0, 1.5260309, 0] deg`. The Human cuff
position is `[0.689248105, 0, 0.136740249] m`; the robot cuff position is
`[0.685994451, 0, 0.139263612] m`. The robot cuff orientation is a
`16.5260309 deg` world-y rotation. At exact equilibrium, the executable
decomposition is allocator force `[-81.3413444,0,63.0840660] N`, position and
velocity feedback approximately zero, allocator moment `[0,8.5229644,0] Nm`,
orientation and angular-velocity feedback approximately zero, and no robot
joint-torque clipping. Nonzero supporting effort and nonzero interface strain
are therefore part of the nominal equilibrium rather than regulation error.

## Local controller

`LoadedEquilibriumHoldStabilizer` applies deterministic Human-space computed
torque around the loaded equilibrium:

`ddq_cmd = -Kp (q_hat-q_goal) - Kd dq_hat`

followed by fixed-model inverse dynamics. It reuses the registered Stage-3
Human tracking acceleration gains (`Kp=[180,140]`, `Kd=[28,22]`) rather than
adding HOLD-cost tuning. The supporting generalized input is inverse-dynamics
feedforward. The only online inputs are the causal deployable Human state and
nominal interface-state estimates. A Stage-5 execution adapter supplies the
single loaded robot cuff-pose reference to the existing allocator, executable
command logic, Safety Filter, and TRACK/BRAKE supervisor.

For MPC arrival, `BumplessLoadedHoldHandoff` constructs the first local pose
reference so its allocator plus low-level feedback exactly reproduces the
previous executable wrench, then uses a provisional 0.10 s quintic pose blend
to the loaded-equilibrium robot pose. This is a pose-authority transfer, not a
second simultaneous pose authority or a new HOLD gain.

## Local perturbation smoke

The retained primary output is `results/local_hold_v1/attempt_06`. Exact
equilibrium remained in the task set for 2.000 s. The combined perturbation was
`q=[+1.25,-1.40] deg`, `dq=[+3.0,-3.5] deg/s`, translation
`[+0.25,0,-0.20] mm`, and rotation `[0,+0.15,0] deg`. It recovered permanently
into the completion set after 0.225 s. It then achieved each requested
continuous 0.5/2/5/10 s HOLD interval. The common
peak force, moment, translation, and rotation were respectively `110.405 N`,
`10.442 Nm`, `4.405 mm`, and `1.685 deg`. The 10 s cumulative force was
`1052.626 N s`, including the 0.225 s recovery. Terminal q error was approximately
`[-0.000095,-0.000010] deg` and terminal dq was numerical zero.

Across all seven local cases there was no 200 N gate event, BRAKE, Safety
Filter intervention, or MuJoCo warning. Combined-case controller plus safety
runtime was about `0.47--0.48 ms` mean and `0.55--0.56 ms` p95.

## Actual Goal-MPC arrival handoff

The retained primary output is `results/local_hold_v1/goal_mpc_handoff_02`.
Unchanged Goal-MPC entered HOLD at 2.080 s. The first local executable command
jump was `1.42e-13 N` and `8.88e-16 Nm`. The local controller recovered
permanently into the completion set after 0.290 s, then maintained a true
continuous 0.500 s HOLD; `GoalTaskState` entered RETURN at 2.865 s, where the
smoke intentionally stopped without exercising or redesigning RETURN.

During the handoff/HOLD interval, peak force was `111.514 N`, cumulative force
was `80.984 N s`, peak moment was `9.282 Nm`, peak translation was `4.415 mm`,
and peak rotation was `1.639 deg`. State-estimation RMSE was
`q=[0.00124,0.00274] deg` and `dq=[0.0649,0.1060] deg/s`; terminal error was
`q=[-0.000101,-0.000372] deg`, `dq=[0.00498,0.00593] deg/s`. Local stabilizer
plus safety runtime was `0.507 ms` mean, `0.563 ms` p95. No force-gate, BRAKE,
Safety Filter intervention, structural event, or MuJoCo warning occurred.

## Commands

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_local_hold_validation.py \
  --output-dir stages/stage5_personalized_motion_learning/results/local_hold_v1/attempt_06

PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_goal_mpc_hold_handoff.py \
  --output-dir stages/stage5_personalized_motion_learning/results/local_hold_v1/goal_mpc_handoff_02
```

The local HOLD blocker is mechanically resolved for this matched 20/35 deg
smoke. The subsequent complete-episode checkpoint is recorded separately in
`GOAL_MPC_COMPLETE_V1_ENGINEERING_REPORT.md`; interface mismatch and learning
remain outside this local-validation artifact.
