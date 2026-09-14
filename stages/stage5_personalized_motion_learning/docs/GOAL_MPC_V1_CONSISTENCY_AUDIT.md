# Stage-5 Goal-MPC v1 Prediction-Execution Consistency Audit

## Scope

This is a focused engineering audit of the saved
`goal_mpc_smoke_v1/attempt_02` force-gate failure. It does not change the
controller, Plant v1, estimator, safety logic, horizon, candidates, weights,
or task. It adds no learning. MuJoCo Human state and Human-side cuff state are
used only in the explicitly offline audit namespace.

The primary trace SHA-256 is
`e48c1b745b889439425b2e8b3338e1464b487c1e4b263c42d6cadc955c6ee270`.
Because that trace did not contain intermediate execution terms, one targeted
0.215 s replay applied only its saved 5 ms action sequence through the
unchanged Plant-v1 execution chain. The replay reproduced every saved
estimated-state sample, physical-force vector, physical-moment vector, and
Human truth sample exactly.

## 1. Synchronized state discrepancy

The controller estimate and evaluation Human truth already share the same 5 ms
sample times. Their synchronized errors are:

| time [s] | q1 error [deg] | q2 error [deg] | dq1 error [deg/s] | dq2 error [deg/s] | translation deformation [mm] | rotation deformation [deg] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0.050 | 2.289 | 4.959 | 25.298 | 64.266 | 5.643 | 2.683 |
| 0.100 | 3.259 | 7.424 | 17.922 | 43.541 | 7.001 | 4.166 |
| 0.150 | 2.993 | 7.378 | 3.732 | 9.542 | 5.405 | 4.387 |
| 0.200 | 2.858 | 6.774 | -1.041 | -8.295 | 6.417 | 3.920 |
| **0.215** | **2.936** | **6.928** | **3.757** | **9.420** | **7.361** | **3.995** |

Over the full saved trace, raw q RMSE is `(2.688, 6.287) deg`; raw dq RMSE is
`(25.638, 56.339) deg/s`. The dq maxima occur earlier in the transient, so
comparing only separate peak estimates and truth would obscure the mechanism.

### Offline correction hypotheses

These substitutions are diagnostic counterfactuals, not controller inputs.
They mix robot-side and Human-side site quantities only to localize the error;
their effects are not assumed additive.

| estimator input hypothesis | q RMSE [deg] | dq RMSE [deg/s] | interpretation |
|---|---:|---:|---|
| robot-side position/rotation/twist | 2.688 / 6.287 | 25.638 / 56.339 | deployed smoke observation |
| Human translation/twist only | 2.192 / 5.795 | 19.612 / 50.680 | translation explains a smaller common-angle part |
| Human rotation/angular twist only | 0.498 / 0.498 | 8.318 / 8.476 | relative rotation explains most q2 and dq discrepancy |
| full Human-side pose/twist | < 7e-15 | < 1.1e-13 | registered geometry exactly reconstructs simulated Human state |

Plant-v1 peak relative translation/rotation are 7.509 mm and 4.651 deg. At
abort they are `(-7.136, -0.025, 1.809) mm` and
`(-0.035, 3.992, 0.160) deg` in the Human cuff frame.

The smoke sensor case has zero latency, zero observation age, preprocessing
disabled, and direct 200 Hz site twist. Therefore the 8 Hz/120 ms history path
does not contribute. Forward geometry applied to the Human-side site has peak
position/rotation residuals of `2.24e-16 m / 7.97e-17 rad`; no simulated
geometry or `T_EC` mapping error is supported. The root cause is instead a
deterministic semantic mismatch: the deployable estimator interprets the
robot-side compliant cuff pose/twist as the Human-side shank state.

![Synchronized state errors](../results/goal_mpc_consistency_audit_v1/state_error_time.png)

## 2. Synchronized force/execution discrepancy

The final command at 0.210 s and its physical effect at 0.215 s are:

| chain quantity | synchronized observation |
|---|---:|
| Human MPC action request | `(25.662, 22.099) Nm` |
| allocator wrench request | force 187.820 N; moment 26.350 Nm |
| robot position feedback | 11.771 N |
| robot velocity feedback | 2.195 N |
| executable total force | 196.387 N; 3.613 N gate margin |
| Safety Filter | `SAFE_UNCHANGED`, zero intervention |
| interface translation / rotation | 7.361 mm / 3.995 deg |
| interface spring force `Kx` | 184.036 N |
| interface damping force `Dv` | 20.802 N |
| physical `Kx + Dv` | **201.533 N** |

The component norms do not add algebraically; the saved vectors satisfy the
Kelvin-Voigt force identity to `2.84e-14 N`. Physical moment also equals
rotation spring + rotation damping + force transport to `3.55e-15 Nm`.

The allocator term, not robot feedback, dominates the executable request.
There is no translational feedback clipping at any sample. Joint-torque
clipping occurs transiently earlier (maximum norm 1.998 Nm) but is zero over
the final gate-forming intervals and is not the abort mechanism.

### Comparison with the old Stage-4 mismatch

Under the attempt-02 ideal measurement case, the registered raw robot
joint/Jacobian velocity and the direct site velocity give a maximum equivalent
140 Ns/m feedback difference of only `2.54e-14 N`. The old history-derived
83.14/135.49 N feedback mechanism is therefore not reproduced.

The remaining force gap is also not mysterious simulator residual physics.
Plant v1 explicitly generates it from its deterministic Kelvin-Voigt state.
It is **unmodeled by the Human-only MPC and next-command screening**, which
check the current executable force but do not propagate the next compliant
interface state.

![Synchronized force decomposition](../results/goal_mpc_consistency_audit_v1/force_decomposition_time.png)

## 3. Runtime profile

All cases retain the 15-step, 20 ms horizon, 32 candidates, two CEM
iterations, and six elites. Timings are five post-warmup desktop repetitions;
they are diagnostic rather than hard-real-time qualification.

| path | wall mean / p95 [ms] | first-action screening [ms] | population evaluation [ms] |
|---|---:|---:|---:|
| current batched population + scalar screening | 35.079 / 35.767 | 22.392 | 6.364 |
| diagnostic scalar population + scalar screening | 205.760 / 206.763 | 21.920 | 177.320 |
| offline batch-screening hypothesis | 12.414 / 12.484 | 0.216 | 6.181 |

This reproduces the saved 36.686 ms mean scale and confirms that Human
dynamics population rollout is batched. The dominant avoidable cost is scalar
first-action screening: one profiled solve performs 65 scalar previews,
repeating allocation, cuff geometry, robot Jacobian/velocity reconstruction,
and command-context preparation. The profile records 97 allocator calls and
289 `cuff_pose` calls because parent and Stage-5 selected-sequence diagnostics
also repeat rollout/allocation work after CEM.

The existing batch preview is an evidence-supported optimization because the
Goal-MPC local q/dq target is candidate-invariant; only allocator wrench varies
by candidate. The 12.4 ms result is an offline timing hypothesis, not a
promoted controller change.

Wall time is not used by this smoke's simulation clock. Plant time advances
only through 20 fixed 0.25 ms substeps per 5 ms command, and MPC updates are
scheduled every four simulated control cycles. The 36.7 ms wall overrun does
not lengthen the simulated action hold, although it would miss a real 20 ms
deadline.

## Evidence-supported root causes and minimal v1.1 fixes

Root causes:

1. Robot-side cuff pose/twist is not Human-side cuff state under finite
   Plant-v1 compliance.
2. Human-only prediction and instantaneous screening omit the deterministic
   cuff-interface transition that produces the next physical force.
3. Scalar candidate screening and repeated post-solve diagnostics dominate
   runtime.

Minimal work before Goal-MPC v1.1:

1. Define a controller-deployable Human-side observation or explicit
   cuff-relative state estimate without using simulator truth.
2. Add the deterministic Plant-v1 interface transition to horizon/screening,
   or validate a conservative next-step physical-force margin.
3. Use existing batch first-action preview for the candidate-invariant local
   target and eliminate duplicate hot-loop diagnostics without changing the
   horizon/candidate budget.
4. Repeat the focused smoke and verify completion, physical force, state
   consistency, and sub-20-ms throughput before considering value learning.

No residual learner is justified by this audit. Plausible later learning
targets are hardware-calibrated cuff/tissue parameter uncertainty and any
remaining Human/interface discrepancy demonstrated after deterministic sensor
semantics and interface prediction are corrected.

## Reproduction

```bash
MPLCONFIGDIR=/tmp/stage5_goal_mpc_audit_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_goal_mpc_prediction_execution.py
```
