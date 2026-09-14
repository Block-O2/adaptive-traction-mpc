# Stage-5 unified loaded execution authority

## Scope

This checkpoint removes the deterministic loaded/unloaded cuff-reference
conflict without changing the Goal-MPC action space, CEM configuration, costs,
Plant v1, motion envelope, HOLD gains, Safety Filter/BRAKE state machine, or
the 200 N simulation engineering gate.  It contains no learning or interface
mismatch experiment.

## Unified execution contract

`loaded_execution.py` is now the single Stage-5 authority.  Its immutable data
contract separates:

- `CuffPoseStateWorld(HUMAN_CUFF_SITE)`: deployable estimated Human cuff pose
  and twist;
- `CuffPoseStateWorld(ROBOT_CUFF_SITE)`: measured or explicitly targeted robot
  cuff pose and twist;
- `Stage5LoadedExecutionTarget`: nominal interface translation/rotation,
  support wrench about the Human cuff, and equivalent robot-site command
  wrench;
- `Stage5LoadedExecutionContext`: one timestamp-aligned observation,
  interface estimate, measured robot state, loaded target, low-level command
  context, and Safety Filter context.

The Human allocator continues to solve for physical wrench
`W_H=[F,M_H]` about the Human sleeve site.  Before robot realization it is
moved to the robot attachment reference point:

```text
r = p_R - p_H
W_R,command = [F, M_H - r x F].
```

The corresponding 6x6 reference-point transform is also applied to the
Safety Filter's sagittal world mapping and null-wrench direction.  Human
generalized-torque preservation therefore remains evaluated with the original
Human-site allocation matrix, while executable force/moment and robot torque
use the robot-site command wrench.

The same target/context is used by:

- Goal-MPC first-action batch preview;
- every normal TRACK execution passed into the inherited supervisor;
- Stage-5's loaded BRAKE preview adapter if BRAKE candidates are required;
- HOLD and Goal/HOLD/RETURN handoffs;
- diagnostic first-action prediction;
- the vectorized future-horizon command resolver.

The future resolver reconstructs the candidate's predicted robot cuff state
from Human state plus nominal interface `x,u,theta,omega`, transforms the total
Human-site wrench at that reference point, and applies the same loaded support
pose/twist feedback convention.  It does not call the Stage-4 unloaded
`geometry.cuff_pose(reference.q)` adapter.

The historical offline `goal_mpc_consistency_audit.py` intentionally retains
the old adapter solely to reproduce the saved pre-fix attempt-02 evidence; it
is not imported by the live Stage-5 Goal/HOLD execution path.

`tau_total = tau_support + delta_tau_motion` remains unchanged.  The
decomposition is still only the CEM parameterization; all allocation,
screening, interface prediction, and execution receive the total input.

## A. Loaded support-only check

The branch starts at the matched nominal loaded equilibrium
`q=[5,10] deg`, `dq=[0,0]`, with
`tau_support=[40.5175946,-7.5784183] Nm`.  The exact snapshot hash is
`c11f0cbc33a5611fcf9a1d193bb206d1d5185d13e25630b05890c4f41bbbea24`.

| Quantity | 5 ms | 20 ms | 50 ms |
|---|---:|---:|---:|
| q drift (deg) | `[-1.07e-14,-3.73e-14]` | `[-1.21e-13,-3.66e-13]` | `[-6.96e-13,-1.85e-12]` |
| dq drift (deg/s) | `[-3.49e-12,-1.17e-11]` | `[-1.12e-11,-3.08e-11]` | `[-2.63e-11,-6.48e-11]` |
| actual Human input (Nm) | `[40.5175946,-7.5784183]` | `[40.5175946,-7.5784183]` | `[40.5175946,-7.5784183]` |

The initial robot feedback force is below `7e-13 N` per component and feedback
moment below `6e-14 Nm` per component.  Loaded target versus actually consumed
target is `0 mm / 0 deg`.  The physical Human-site wrench remains
approximately `[-31.060,0,72.967,0,12.615,0]` throughout.  The old unloading
terms `[3.727,0,-8.756] N` and `My=-4.731 Nm` are absent.

## B. Same-snapshot paired increments

All entries are paired differences from support-only.  Wrenches are
`[Fx,Fz,My]`; Human quantities are `[q1,q2]`.  The first-instant feedback
difference is numerical zero in all four branches.

| Branch | delta Human-site allocation | delta robot-site executable | delta physical wrench at 5 / 20 / 50 ms |
|---|---|---|---|
| `+delta_tau1` | `[-0.675,+1.090,+0.296]` | `[-0.675,+1.090,+0.297]` | `[-0.847,+0.412,+0.120] / [-1.107,+0.664,+0.164] / [-1.387,+0.790,+0.270]` |
| `-delta_tau1` | `[+0.675,-1.090,-0.296]` | `[+0.675,-1.090,-0.297]` | `[+0.847,-0.412,-0.120] / [+1.112,-0.664,-0.165] / [+1.389,-0.795,-0.272]` |
| `+delta_tau2` | `[-1.559,+1.012,+0.752]` | `[-1.559,+1.012,+0.755]` | `[-1.988,+0.713,+0.281] / [-2.746,+1.289,+0.394] / [-3.620,+1.614,+0.659]` |
| `-delta_tau2` | `[+1.559,-1.012,-0.752]` | `[+1.559,-1.012,-0.755]` | `[+1.988,-0.713,-0.281] / [+2.765,-1.288,-0.396] / [+3.645,-1.617,-0.666]` |

| Branch | delta actual Human input at 5 / 20 / 50 ms (Nm) | delta dq at 5 / 20 / 50 ms (deg/s) | delta ddq at 5 / 20 / 50 ms (deg/s2) |
|---|---|---|---|
| `+delta_tau1` | `[+0.189,+0.022] / [+0.330,+0.002] / [+0.319,+0.081]` | `[+0.053,+0.160] / [+0.268,+0.591] / [+0.668,+1.284]` | `[+10.52,+31.93] / [+14.36,+24.55] / [+13.29,+24.63]` |
| `-delta_tau1` | `[-0.189,-0.022] / [-0.329,-0.002] / [-0.321,-0.081]` | `[-0.053,-0.160] / [-0.270,-0.596] / [-0.661,-1.269]` | `[-10.52,-31.93] / [-14.27,-24.26] / [-11.12,-19.91]` |
| `+delta_tau2` | `[+0.260,+0.127] / [+0.572,+0.095] / [+0.550,+0.299]` | `[+0.125,+0.440] / [+0.602,+1.667] / [+1.459,+3.594]` | `[+24.95,+88.03] / [+32.17,+73.10] / [+27.88,+65.05]` |
| `-delta_tau2` | `[-0.259,-0.127] / [-0.570,-0.097] / [-0.546,-0.303]` | `[-0.125,-0.440] / [-0.611,-1.688] / [-1.468,-3.616]` | `[-24.95,-88.04] / [-31.82,-71.94] / [-25.15,-59.30]` |

The requested positive and negative increments produce paired opposite actual
Human-input, velocity, and acceleration responses at every sampled time.  The
coupled Human dynamics mean a single-joint torque increment need not move only
one joint.  The direction check passes without assuming decoupled motion.

Machine-readable evidence is retained at
`results/loaded_execution_authority_v1/targeted_consistency/`.

## Matched full episode

Because A/B passed, one matched engineering episode was run and retained at
`results/loaded_execution_authority_v1/matched_attempt_01/`.

Observed result: `OUTBOUND -> ABORTED` at `0.045 s` with
`TASK_ACCELERATION_LIMIT`; HOLD and RETURN were not reached.

| Metric | Observed |
|---|---:|
| estimated peak velocity | `[3.285,7.967] deg/s` |
| estimated peak acceleration | `[247.12,665.71] deg/s2` |
| evaluation-only peak acceleration | `[166.98,511.41] deg/s2` |
| registered acceleration limit | `[300,600] deg/s2` |
| peak / cumulative physical cuff force | `91.955 N / 3.76182 Ns` |
| peak physical cuff moment | `15.0006 Nm` |
| peak interface translation / rotation | `3.395 mm / 2.389 deg` |
| q estimation peak error | `[0.0093,0.0206] deg` |
| dq estimation peak error | `[0.378,0.754] deg/s` |
| force norm prediction RMSE / max | `0.561 / 1.287 N` |
| Goal-MPC runtime mean / p95 / max | `24.768 / 26.322 / 26.365 ms` |

All nine executed Safety Filter results were `SAFE_UNCHANGED`.  Force-gate,
BRAKE, structural, and MuJoCo-warning counts were zero.  No full prescribed
trajectory, q1/q2 ratio, or path corridor was introduced.

The abort is not the old loaded/unloaded authority failure: at 50 ms the
support-only branch is stationary to numerical precision, and the full-run
force prediction error is small.  The event occurs on the 40--45 ms command
interval.  Evaluation-only q2 acceleration is `511.41 deg/s2` (inside the
600 limit), while the deployable-estimator 5 ms velocity difference is
`665.71 deg/s2`.  Goal-MPC constrains its 20 ms predicted-state finite
difference, but `GoalTaskState` enforces a 5 ms online estimated derivative.
That prediction/execution-timebase plus estimator-derivative discrepancy is
the next deterministic blocker.  This checkpoint does not change the motion
envelope, estimator, cost, or sampling to make the episode pass.
