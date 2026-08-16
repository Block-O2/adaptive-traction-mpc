# Dynamic Robust Load Transfer V1 — R2A Oracle Model Feasibility Gate

## Purpose

R2A asks one diagnostic question: if the existing tracking controller had
perfect knowledge of the fixed true plant parameters, would the unchanged
task, reference, controller, limits, safety manager, and R1 Safe Takeover be
dynamically feasible for the nominal, mild, moderate, and adverse plants?

This is an **ORACLE diagnostic only**. It is an upper-bound experiment, not a
deployable controller and not evidence that online adaptation will reproduce
the result. A real estimator would add delay, noise, bias, finite excitation,
uncertainty, and parameter-update transients.

## Parameter separation and oracle definition

The case runner constructs three explicit parameter roles:

- `nominal`: unchanged task, calibration, registered uncertainty set, static
  robust supervisor, posture selection, and reference-plan baseline;
- `plant`: true parameters used by physical bed contact and RK4 plant
  dynamics;
- `controller_model`: fixed parameters used by the existing robot tracking
  controller, its dynamic-margin prediction, and the R1 local predictor that
  already shares the controller model.

The ordinary Dynamic V1 call defaults `controller_model = nominal`, preserving
the reviewed R1 path. The dedicated R2A runner constructs exactly:

| Case | True plant | Fixed controller model |
|---|---|---|
| nominal | nominal | nominal |
| oracle mild | mild | mild |
| oracle moderate | moderate | moderate |
| oracle adverse | adverse | adverse |

The substitution occurs once at the runner boundary. `theta_model` is fixed
from `t=0` through the end of the rollout. There is no estimator, Windowed NLS,
recursive identification, filter-based parameter augmentation, uncertainty
tightening, robust MPC, CBF, adaptive gain, or online update.

The oracle case builder is not called by the controller or safety manager.
The runtime manager continues to receive only its existing boolean/margin
signals. The R1 governor still receives applied-command history, measured
`q/dq`, measured bed torque, controller candidates, its existing controller
model, and fixed limits. It receives no case label or parameter override.

## Preserved experiment conditions

R2A does not change the physical initial state, plant-consistent initial
command, R1 algorithm, reference trajectory, task definition, controller
structure or gains, force bounds, ROM or soft limits, bed/contact mechanics,
`dt`, force slew, takeover rules, 60 s formal cap, mismatch definitions,
stopping rules, or safety manager. It does not move the initial posture away
from `[5,10] deg`, relax a constraint, slow the reference, reduce mismatch, or
modify the true plant.

R1 remains active for every case. Perfect model knowledge does not bypass
`SAFE_HOLD -> TAKEOVER -> TRACKING`; any natural change in takeover duration is
part of the diagnostic result.

## Recorded evidence

The dedicated runner writes a new timestamped directory below:

```text
linkage/results/local/dynamic_robust_load_transfer_v1_oracle_model_r2a/
```

It preserves the complete result structs and both full parameter structs in
`formal_oracle_results.mat`, and writes parameter JSON plus an ordered numeric
parameter-distance check to `case_metrics.csv`. The mild, moderate, and adverse
oracle mismatch norms must be exactly zero.

Per case, the record includes final status/reason, duration and completion
time, final progress, takeover/tracking entry and tracking survival, failure
phase, joint extrema, minimum ROM and soft-limit margins, peak soft-limit
torque, component and vector force peaks, component-bound margin, bed-support
minimum/peak, transfer entry, completion, state sequence, controller-model and
realized dynamic margins, and their samplewise gap.

## Deterministic tests

Seven R2A tests cover:

- exact nominal-path equivalence with an implicit versus explicit nominal
  controller model;
- exact mild, moderate, and adverse oracle mappings;
- no controller-model mutation during a rollout;
- preserved R1 initialization and `TAKEOVER -> TRACKING` traversal in all four
  oracle cases, with takeover safety checks;
- source-level absence of oracle case construction and parameter overrides
  from runtime controller/supervisor modules.

The Dynamic Robust V1 target suite passed `32/32` in `93.8958 s` in MATLAB
R2025b Update 1. The complete retained linkage suite passed `130/130` in
`169.6577 s`. No formal scientific rollout was run by Codex.

## Existing nominal-model comparison

The reviewed R1 formal source is
`linkage/results/local/dynamic_robust_load_transfer_v1/20260815_171801`.

| Case | Nominal-model result | Tracking survival | Final progress | Transfer |
|---|---|---:|---:|---:|
| mild | `SOFT_LIMIT_VIOLATION @ 4.400 s`, q1 lower | 0.524 s | 0.109981 | no |
| moderate | `SOFT_LIMIT_VIOLATION @ 3.792 s`, q2 lower | 0.718 s | 0.156077 | no |
| adverse | `SOFT_LIMIT_VIOLATION @ 3.904 s`, q2 lower | 0.546 s | 0.163303 | no |

## Formal results

The reviewed user-run formal directory is
`linkage/results/local/dynamic_robust_load_transfer_v1_oracle_model_r2a/20260815_174540`.
All four initial-admissibility reports passed. Every case completed R1 in
`0.020 s`, with first logged `TRACKING` sample at `0.018 s`, zero takeover
soft-limit activation, and zero takeover ROM violation. All controller-model
and true-plant parameter distances were exactly zero, and no parameter update
occurred.

| Case | Final status | Time (s) | Tracking survival (s) | Final s | Transfer | Completion |
|---|---|---:|---:|---:|---:|---:|
| nominal | `TASK_COMPLETE` | 22.512 | 22.492 | 1.000000 | yes, 4.568 s | yes |
| oracle mild | `TASK_COMPLETE` | 22.510 | 22.490 | 1.000000 | yes, 4.568 s | yes |
| oracle moderate | `SOFT_LIMIT_VIOLATION`, q2 lower | 4.088 | 4.068 | 0.198249 | no | no |
| oracle adverse | `SOFT_LIMIT_VIOLATION`, q2 lower | 3.510 | 3.490 | 0.162124 | no | no |

Nominal and oracle mild traversed the complete sequence through transfer,
liftoff, suspended motion, recontact, load return, and task completion.
Moderate and adverse remained in `BED_SUPPORTED_MOTION`. Their terminal q2
values were `4.964800` and `4.946308 deg`, giving minimum soft-zone margins of
`-0.035200` and `-0.053692 deg`. Each had one soft-limit-active sample, peak
soft torques of only `1.08573e-4` and `1.82574e-4 N m`, and zero ROM-violation
samples.

| Case | q1 range (deg) | q2 range (deg) | Peak component / norm (N) | Min force margin (N) | Min / peak bed (N) |
|---|---:|---:|---:|---:|---:|
| nominal | 5.000 / 45.000 | 10.000 / 84.000 | 185.950 / 186.375 | 14.050 | 0 / 152.540 |
| oracle mild | 5.000 / 45.000 | 10.000 / 84.000 | 200.000 / 200.435 | 0 | 0 / 152.540 |
| oracle moderate | 5.000 / 9.788 | 4.965 / 15.971 | 200.000 / 203.385 | 0 | 56.806 / 152.540 |
| oracle adverse | 5.000 / 6.897 | 4.946 / 12.764 | 200.000 / 202.358 | 0 | 96.892 / 152.540 |

The force constraint is a component box, so vector norms slightly above
`200 N` are not violations. Mild, moderate, and adverse reached but did not
exceed the `+/-200 N` component bound. Their force-saturation fractions were
`0.003376`, `0.229829`, and `0.155467`, respectively.

Compared with the nominal-model Stage 2 result, oracle mild changed from a
q1-lower failure after `0.524 s` of tracking to full completion. Oracle
moderate increased tracking survival from `0.718` to `4.068 s` and progress
from `0.156077` to `0.198249`, but still failed at the q2 lower soft boundary.
Oracle adverse increased tracking survival from `0.546` to `3.490 s`; its
progress remained essentially unchanged (`0.163303` to `0.162124`) and it
also failed at the q2 lower boundary. Its absolute termination time became
earlier because oracle R1 takeover took only `0.020 s`, rather than `3.358 s`;
tracking survival is the phase-aligned comparison.

## Dynamic-margin interpretation

R2A evaluates the existing metric without redesign. In an oracle case the
controller-model and realized diagnostic calls use identical parameters and
the same state/reference sample, so their reported values should coincide.
The reviewed run confirms exact equality: the maximum and RMS model-realized
margin gaps are zero in all four cases. Minimum shared margins nevertheless
remain strongly negative: `-115.898`, `-146.225`, `-525.982`, and
`-582.789 N` for nominal through adverse.

The metric definition explains why this is not a model-mismatch residual. It
computes the force needed for the commanded acceleration under a robot-only
dynamic balance and does not subtract measured bed torque, whereas the actual
bed-supported controller does take its configured bed credit. It is also a
global minimum over the rollout, not only a transfer-entry sample. Nominal and
oracle mild complete despite a negative global minimum. The metric remains
useful as a robot-only demand diagnostic, but its sign must not be interpreted
as parameter mismatch or, by itself, as whole-task infeasibility.

## R2 decision gate

The reviewed result is **Case B — partial oracle improvement**. Exact model
knowledge changes mild from an early tracking failure to full task completion
and increases moderate/adverse phase-aligned tracking survival by factors of
approximately `5.67` and `6.39`. Model mismatch therefore materially affects
the existing failures, so a separately approved R2B Windowed-NLS Adaptive
Tracking task is scientifically justified as the next adaptation diagnostic.

Accurate dynamics alone is not sufficient across the full registered
envelope: moderate and adverse still reach the q2 soft boundary while the
parallel component is saturated, and neither reaches transfer. R2B cannot be
expected to equal the oracle because of identification delay, noise, bias,
finite excitation, uncertainty, and update transients. Later constraint/safety
robustness or feasibility work will probably still be necessary, but R2A does
not select or implement it.

Even substantial success establishes only an oracle upper bound. R2A stops
after reporting evidence and does not start R2B, R3, a new controller, or a
reference redesign.

## Formal command reserved for the user

From the repository root:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_dynamic_robust_load_transfer_v1_oracle_model"
```
