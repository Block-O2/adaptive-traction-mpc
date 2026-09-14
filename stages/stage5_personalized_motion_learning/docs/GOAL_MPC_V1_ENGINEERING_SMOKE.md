# Stage-5 Goal-MPC v1 Engineering Smoke

## Scope and evidence status

This is engineering/smoke evidence only. It is not a formal experiment and no
scientific PASS/FAIL label is assigned. `Stage-5 Plant v1`, the inherited
Human-space CEM settings, fixed Human control model, allocator, executable
screening, Safety Filter, BRAKE, 0.25 ms physics timestep, and 5 ms execution
period remain unchanged. No RL or terminal-value learning is active.

The final saved attempt is `results/goal_mpc_smoke_v1/attempt_02`. Attempt 01
is preserved; its dynamics and termination are identical, but its initial
summary associated terminal error with the return target after the state had
already changed to `ABORTED`. Attempt 02 corrects that reporting-only issue and
associates terminal error with the active `OUTBOUND` goal.

## Frozen controller-facing task observation

`ControllerTaskObservation` uses the existing deployable non-UKF Stage-4 path:
the published Human model geometry maps measured cuff pose and twist to
`[q1, q2, dq1, dq2]`. Inputs come from `ControllerMeasurement`; MuJoCo Human
state is absent. The immutable record carries sample time, controller arrival
time, source, and fixed Human-model version.

- future timestamps are rejected;
- age is `arrival_time - sample_time`;
- the maximum accepted age is 20 ms, one existing Goal-MPC update period;
- stale/nonfinite states fail explicitly;
- the smoke used ideal 200 Hz measurements with maximum observed age 0 ms.

The fixed control model is `stage5_fixed_registered_human_v1`. MuJoCo Human
state appears only in the separately labeled offline evaluation trace.

## Goal-MPC v1 formulation

For phase target `q_g`, inherited scales `s_q`, `s_dq`, candidate sequence
`u_0...u_(H-1)`, and predicted Human states, the implemented scalar objective
is

`sum_k ||(q_k-q_g)/s_q||^2`

`+ ||(q_H-q_g)/s_q||^2 + ||dq_H/s_dq||^2`

`+ 0.002 sum_k ||u_k/s_u||^2`

`+ 0.005 sum_k ||(u_k-u_(k-1))/s_du||^2`

`+ optional inherited cuff-interaction terms + V_terminal`.

For this smoke the inherited cuff-interaction weights remain zero and
`V_terminal = 0`. No `q_ref(t)`, `dq_ref(t)`, `ddq_ref(t)`, coordination ratio,
or path corridor is accepted by the Stage-5 `solve_goal` API. The active target
is `(20 deg, 35 deg)` in `OUTBOUND/HOLD` and `(5 deg, 10 deg)` in `RETURN`.

The inherited 15-step, 20 ms Human prediction, 32 candidates, two CEM
iterations, six elites, RNG seed, action scales, action/action-slew weights,
allocator, and force gate are unchanged. The seed independently limits each
joint using the peak velocity/acceleration of the old low/moderate fixture
(`9.75/17.25 deg/s`, `12.0089/21.2465 deg/s^2`). This seed pacing replaces the
reference-dependent seed only; it is not a hard constraint or fixed `q1/q2`
ratio, and CEM remains free to depart from it.

Predicted constraints retain Human ROM, the configurable task ROM, optional
task velocity/acceleration limits, finite-state requirements, and the existing
200 N allocated-force gate. Every first action passes the existing executable
command screening. The selected action then passes through the unchanged
Safety Filter/BRAKE supervisor.

Because the Human-only predictor omits Plant-v1 cuff deformation, the robot
pose/twist command is anchored to the current deployable cuff-derived state;
the selected generalized cuff wrench is the motion authority. Using the next
Human-only predicted state as a simultaneous robot pose target was rejected in
a temporary diagnostic because it pulled the cuff ahead of the shank.

## Saved smoke result

Command:

```bash
MPLCONFIGDIR=/tmp/stage5_goal_mpc_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_goal_mpc_smoke.py \
  --output-dir stages/stage5_personalized_motion_learning/results/goal_mpc_smoke_v1/attempt_02 \
  --maximum-duration-s 30.5
```

Observed result:

| Quantity | Observation |
|---|---:|
| task transition | `OUTBOUND -> ABORTED` |
| termination | `PHYSICAL_CUFF_FORCE_GATE` at 0.215 s |
| peak / cumulative physical cuff force | 201.533 N / 32.464 N s |
| peak physical cuff moment | 30.277 Nm |
| estimated terminal error to outbound goal | `(-5.596 deg, -3.354 deg)` |
| evaluation-only terminal error to outbound goal | `(-8.533 deg, -10.282 deg)` |
| minimum estimated outbound goal-error norm | 7.036 deg |
| peak estimated joint speed | `(64.969, 160.534) deg/s` |
| peak evaluation-only joint speed | `(49.156, 124.763) deg/s` |
| MPC solves / failures | 11 / 0 |
| MPC runtime mean / p95 / max | 36.686 / 37.400 / 37.424 ms |
| MPC status | 11 `SAFE_ACTION` |
| Safety Filter | 43 `SAFE_UNCHANGED`, zero intervention |
| BRAKE / structural events | 0 / 0 |
| MuJoCo warnings | none |

The episode did not reach HOLD, RETURN, or COMPLETE. This unfavorable result is
retained rather than tuned away. All 11 solves returned, but the observed
36.686 ms mean and 37.400 ms p95 solve times exceed the current 20 ms MPC
update period, so real-time throughput is also unresolved.

## Diagnosis and blocker

The fresh observation and solver completed mechanically. The primary blocker
is the unregistered speed/time tradeoff in the goal objective: with no approved
task velocity/acceleration limits and no progress-time tradeoff, target-distance
minimization drives actions toward the existing force boundary. The Human-only
0.3 s prediction also omits the Plant-v1 cuff-interface state, while executable
screening bounds the current command rather than the next physical interface
transient. Consequently an action can be reported `SAFE_ACTION` and
`SAFE_UNCHANGED` immediately before physical force crosses 200 N.

Before adding a learned terminal value, an approved next spec must choose at
least one of:

1. explicit task velocity/acceleration/time limits or a registered progress-time
   objective; and
2. a cuff-interface-aware short-horizon constraint/predictor or a validated
   conservative execution margin.

The deployable cuff-derived `q/dq` transient under finite compliance also needs
validation before using it for hard speed/acceleration aborts. The solver path
must additionally meet, or be reconciled with, the 20 ms update budget.
Learned value must not be used to mask these model, constraint, and runtime
gaps.
