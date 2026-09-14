# Goal-MPC v1.3 structural HOLD engineering report

Evidence category: **engineering smoke only**. This is not formal evidence or
a scientific PASS/FAIL decision. Stage 3, Stage 4, Plant v1, controller nominal
interface parameters, the 200 N engineering gate, Safety Filter/BRAKE, Human
model, CEM horizon/candidates/iterations, and `V_terminal=0` are unchanged. No
learning, full joint trajectory, coordination ratio, or path corridor is used.

## Structural changes

- The controller-nominal translational and rotational interface states are now
  propagated through every one of the 15 MPC steps for the full candidate
  population. Requested cuff wrench, interface displacement/velocity,
  rotational error/angular velocity, transmitted mean physical wrench, and
  sampled peak force/moment are retained at every step. The transmitted wrench,
  rather than the requested Human action, drives the next Human state.
- Candidate allocation and interface propagation are vectorized across all 32
  candidates; only the fixed 15-step horizon loop remains in Python. The dense
  0.25 ms first-action screen is retained, while later diagonal spring-damper
  steps use their exact constant-drive transition and three peak samples.
- Both distinct force checks are preserved: physical transmitted force and the
  allocator-request force must remain below the unchanged 200 N simulation
  engineering gate. Omitting the second check caused the retained
  `matched_01` deterministic supervisor inconsistency and was corrected before
  the primary smoke.
- HOLD uses the `GoalTaskSpec` 1 deg joint-angle and 2 deg/s joint-velocity set.
  If the sampled population contains a plant/task-safe sequence that remains
  in the set, out-of-set candidates are rejected. If none exists, plant/task
  safety remains hard and the existing normalized set-violation term chooses a
  recovery sequence instead of returning `NO_SAFE_ACTION`. Only
  `GoalTaskState` owns set membership and the continuous 0.5 s timer.
- The retained modest in-set terms are: set violation `1.0`, normalized in-set
  regulation `0.05`, and normalized physical-force cost `0.01`. These are not
  increased after the failed smoke.

## Matched 20 deg / 35 deg episode

Primary retained output: `results/goal_mpc_v13/matched_03/`.

The episode reached `OUTBOUND -> HOLD` at 2.080 s, but never reached RETURN or
COMPLETE. It terminated at 12.085 s with `TIMEOUT_HOLD`. The longest continuous
true HOLD-set interval was 0.005 s; only 1 of 2001 HOLD samples simultaneously
satisfied angle and velocity tolerances. HOLD q ranged from
`(10.871, 6.572) deg` to `(19.593, 34.893) deg`; HOLD dq RMS was
`(4.351, 8.702) deg/s` and peak absolute dq was `(15.822, 30.660) deg/s`.

Peak/cumulative physical cuff force was `173.252 N / 1110.703 N s`; peak cuff
moment was `24.967 Nm`. There was no force-gate event, BRAKE, Safety-Filter
intervention, MPC failure, structural event, nonfinite state, or MuJoCo
warning. All 605 solves returned `SAFE_ACTION`.

Human-state q RMSE was `0.00824/0.01763 deg`; dq RMSE was
`0.3732/0.6743 deg/s`. Physical-force vector prediction RMSE/p95/max was
`5.713/12.230/47.185 N`, and force-norm prediction RMSE/p95/max was
`3.771/8.118/37.133 N`. Mean/p95/max MPC runtime was
`22.061/23.857/40.377 ms`, so the around/below-20-ms target was not met. No
horizon or candidate reduction was made.

Path freedom remains structural and observed: there is no reference trajectory,
ratio, or corridor, and maximum normalized q1/q2 progress difference was
`0.817`.

## Evidence-supported blocker

The first hard-set attempt (`matched_02`) found 62 executable-screen-feasible
first actions but no full-horizon HOLD-set-feasible sequence. Best physical and
allocated force margins were still 93.31 N and 96.05 N; the limiting velocity
and angle margins were -0.1146 rad/s and -0.00274 rad. This justified the
sampled-feasibility recovery semantics, but recovery still timed out.

A default-off selected-horizon diagnostic time-aligned prediction with actual
execution. Over HOLD, the 20 ms prediction had q RMSE `0.022/0.094 deg` but dq
RMSE `1.063/5.787 deg/s`; available 300 ms comparisons grew to q RMSE
`2.108/2.922 deg` and dq RMSE `13.640/19.154 deg/s`. The first-step mean wrench
itself matched the following 20 ms physical mean with force/moment vector RMSE
`2.561 N / 0.254 Nm`.

The decisive offline check mapped the measured physical wrench to generalized
Human input. Driving the unchanged fixed Human model with that measured 20 ms
mean input predicted the next state with q RMSE `0.0071/0.0120 deg` and dq RMSE
`0.256/0.266 deg/s`, while the nominal-interface predicted generalized input
differed by `4.98/1.94 Nm`. The blocker is therefore the simple nominal
constant-drive interface surrogate's omission of future executable robot
command and low-level position/velocity-feedback evolution. It is not the
Human model, state estimator, HOLD threshold, force gate, or Safety Filter.

Matched Goal-MPC is **not ready** for interface-mismatch testing. The next
separately approved structural step is a controller-deployable future execution
model that propagates the robot command/feedback state coupled to the nominal
interface; no weight/threshold change or learner is justified by this result.
