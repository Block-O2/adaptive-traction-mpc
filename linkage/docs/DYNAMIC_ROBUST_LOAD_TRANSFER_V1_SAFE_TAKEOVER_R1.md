# Dynamic Robust Load Transfer V1 — R1 Safe Takeover

## Scope and evidence boundary

R1 changes only the startup handover from the actuator command already
present at `t=0` to the unchanged nominal controller. It preserves the
`[5,10] deg` start, plant-consistent initialization, registered mismatch
plants, task path, nominal controller model and gains, bed/contact model,
ROM/soft limits, `+/-200 N` component bounds, `250 N/s` maximum component
slew, `0.002 s` step, and formal rollout duration.

The 4 s results below are **startup smoke evidence only**. They are not formal
robustness results and do not replace the user-run formal experiment.

## Before R1: exact old handover

The retained corrected pre-R1 formal run is
`linkage/results/local/dynamic_robust_load_transfer_v1/20260815_161905`.
The controller was initialized with the true-plant equilibrium force, but its
first call immediately solved the unchanged nominal law and applied the
component slew box around the current command.

| Case | Initial applied force (N) | Nominal demand at `t=0` (N) | Demand minus initial (N) | First applied force (N) |
|---|---:|---:|---:|---:|
| nominal | `[-8.542671, 21.011240]` | `[-8.542671, 21.011240]` | `[0, 0]` | `[-8.542671, 21.011240]` |
| mild | `[-38.985248, 21.094014]` | `[-8.542671, 21.011240]` | `[30.442576, -0.082773]` | `[-38.485248, 20.594014]` |
| moderate | `[-58.421744, 19.504064]` | `[-8.542671, 21.011240]` | `[49.879072, 1.507177]` | `[-57.921744, 19.004064]` |
| adverse | `[-95.989639, 18.704554]` | `[-8.542671, 21.011240]` | `[87.446968, 2.306686]` | `[-95.489639, 18.204554]` |

The QP's torque and command-change terms made both applied components move by
the full `0.5 N` per `2 ms` initially. The parallel component then continued
toward the nominal equilibrium at `+250 N/s`; the perpendicular component
initially moved negative and subsequently curved back as state feedback
changed. Selected retained samples are:

| Case | Time range | Applied parallel sequence (N) | q1 maximum | q1 acceleration first negative | q1 velocity first negative | Terminal crossing |
|---|---|---|---:|---:|---:|---:|
| mild | `0:2:26 ms` | `-38.485, -37.985, ..., -31.985` | `5.000132 deg @ 10 ms` | `-3.881 deg/s^2 @ 8 ms` | `-0.02646 deg/s @ 12 ms` | `4.996613 deg @ 26 ms` |
| moderate | `0:2:26 ms` | `-57.922, -57.422, ..., -51.422` | `5.000185 deg @ 12 ms` | `-2.995 deg/s^2 @ 8 ms` | `-0.01440 deg/s @ 12 ms` | `4.996906 deg @ 26 ms` |
| adverse | `0:2:30 ms` | `-95.490, -94.990, ..., -87.990` | `5.000451 deg @ 16 ms` | `-0.904 deg/s^2 @ 12 ms` | `-0.05435 deg/s @ 18 ms` | `4.996344 deg @ 30 ms` |

The initially inward motion was only the transient response to the first force
increments. As the fixed-rate handover accumulated force error relative to
each true equilibrium, true q1 acceleration changed sign, then q1 velocity
changed sign, and the zero-clearance lower soft boundary was crossed. No
solver or initialization failure occurred.

## R1 design

The nominal controller is unchanged. Its desired and slew-limited candidate
commands now pass through `dynamic_robust_v1_safe_takeover_step` before the
plant:

```text
plant-consistent applied command
-> SAFE_HOLD
-> TAKEOVER
-> TRACKING
or bounded TAKEOVER_ABORT
```

- `SAFE_HOLD` retains the actual command already present at startup. Task
  progress continues, so the frozen path naturally leaves its initial hold and
  generates an inward reference. Handover starts only when nominal desired
  force is within the shared 10 N capture band. The band is half of the
  existing 20 N robust-entry trigger and is identical for every case.
- During `TAKEOVER`, the existing task coordinate is held by the existing
  jerk-limited progress governor. No waypoint or path value is changed.
- The nominal slew-limited force increment is checked using component scales
  `{1, 0.5, 0.25, 0.125, 0}`. Safety gain takes priority over command progress.
- One-step safety uses nominal local input sensitivity about the initial
  applied-command anchor. It does not use the nominal model's incorrect
  absolute equilibrium as an acceleration oracle. Both joints' nearest
  soft-zone margins must be non-decreasing during takeover.
- Measured margin and measured margin-direction velocity are checked every
  step. If either deteriorates, a bounded 3-by-3 one-step recovery candidate
  set chooses the maximum nominal predicted safety gain. This uses no solver,
  learned metric, estimator, uncertainty model, or case label.
- `TRACKING` is entered after 20 ms of stable safe motion when either applied
  force is within the existing one-step force-jump tolerance of demand or both
  joints have established the existing `0.25 deg` preposition tolerance as
  soft-zone clearance. In `TRACKING`, the governor is an exact bypass and the
  old nominal controller candidate is applied unchanged.
- A shared 6 s bound inherited from the existing preposition timeout returns
  `SAFE_TAKEOVER_TIMEOUT` rather than permitting an unsafe indefinite hold.
- The high-level load-transfer supervisor cannot leave
  `BED_SUPPORTED_MOTION` until startup `TRACKING` has been entered.

The runtime function accepts only applied-command history, measured `q/dq`,
measured bed torque, nominal controller outputs, nominal parameters, and fixed
configuration/safety limits. It has no true-plant, mismatch-case,
initial-admissibility, or true-equilibrium input.

Every sample records takeover mode/reason, nominal desired and candidate
forces, applied force, aggregate and per-component scales, force gap, measured
soft margins, and predicted one-step margins. The formal runner also records
tracking entry, takeover duration, failure phase, hold/scaled/full steps,
minimum scale, takeover minimum q1/margin, and minimum bed support.

## Deterministic tests

The Dynamic Robust V1 suite now contains 25 tests. The R1 additions cover:

- nominal startup reaches `TRACKING` without takeover soft/ROM events;
- mild, moderate, and adverse registered cases all reach `TRACKING`, with
  takeover-only safety checked separately from later tracking outcomes;
- an adverse zero-boundary sample is never nominally predicted to reduce q1
  margin;
- source-level absence of true-plant override/admissibility/case dependencies;
- component force bounds in all four startup cases;
- exact nominal-controller bypass after `TRACKING`;
- structured bounded timeout that holds the current applied command.

MATLAB R2025b Update 1 completed the full retained linkage suite with
`123 passed, 0 failed, 0 incomplete` in `114.2001 s`.

## Startup smoke result

The retained non-formal smoke directory is
`linkage/results/local/dynamic_robust_load_transfer_v1_startup_smoke/20260815_170442`.
The same R1 configuration was used for all four cases.

| Case | Tracking entered | Takeover time (s) | Takeover min q1 (deg) | Takeover min soft margin (deg) | Hold steps | Scaled steps | Min scale | 4 s status | Failure phase | Final s |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| nominal | yes | 0.020 | 5.000 | 0.000 | 0 | 0 | 1 | `ABORTED` (smoke cap) | `TRACKING` | 0.192749 |
| mild | yes | 3.876 | 5.000 | 0.000 | 1770 | 167 | 0 | `ABORTED` (smoke cap) | `TRACKING` | 0.104990 |
| moderate | yes | 3.074 | 5.000 | 0.000 | 1457 | 79 | 0 | `SOFT_LIMIT_VIOLATION @ 3.792 s` | `TRACKING` | 0.156077 |
| adverse | yes | 3.358 | 5.000 | 0.000 | 1596 | 82 | 0 | `SOFT_LIMIT_VIOLATION @ 3.904 s` | `TRACKING` | 0.163303 |

Peak robot-force norms were `186.374756`, `115.662028`, `151.254541`, and
`168.114675 N`; minimum bed supports were `37.812087`, `148.993225`,
`123.800428`, and `106.633421 N`, respectively. Component bounds remained
enforced.

This smoke eliminates the old 26--30 ms q1 startup boundary failure in all
registered cases and demonstrates actual entry to the unmodified tracking
path. Moderate and adverse later enter a soft zone `0.718 s` and `0.546 s`
after tracking entry. Those smoke failures are explicitly classified as
`TRACKING`, not `TAKEOVER`; they are not promoted to formal conclusions.

## Reviewed user-run formal result

The user-run formal result is retained at
`linkage/results/local/dynamic_robust_load_transfer_v1/20260815_171801`.
All four initial-admissibility reports passed, and no case had a soft-limit,
ROM, or component-force violation during `SAFE_HOLD`/`TAKEOVER`.

| Case | Takeover | Tracking entered | Final status | Failure phase | Time (s) | Final s |
|---|---:|---:|---|---|---:|---:|
| nominal | 0.020 s | yes | `TASK_COMPLETE` | `NONE` | 22.512 | 1.000000 |
| mild | 3.876 s | yes | `SOFT_LIMIT_VIOLATION` | `TRACKING` | 4.400 | 0.109981 |
| moderate | 3.074 s | yes | `SOFT_LIMIT_VIOLATION` | `TRACKING` | 3.792 | 0.156077 |
| adverse | 3.358 s | yes | `SOFT_LIMIT_VIOLATION` | `TRACKING` | 3.904 | 0.163303 |

| Case | Takeover min q1 / soft margin (deg) | Hold / scaled steps | Min scale | Peak robot norm (N) | Min / peak bed support (N) |
|---|---:|---:|---:|---:|---:|
| nominal | `5.000 / 0.000` | `0 / 0` | 1 | 186.374756 | `0 / 152.540395` |
| mild | `5.000 / 0.000` | `1770 / 167` | 0 | 115.662028 | `148.993225 / 174.721711` |
| moderate | `5.000 / 0.000` | `1457 / 79` | 0 | 151.254541 | `123.800428 / 182.959359` |
| adverse | `5.000 / 0.000` | `1596 / 82` | 0 | 168.114675 | `106.633421 / 179.819595` |

At tracking entry, the mismatch joint states and soft margins were:

| Case | q at entry (deg) | soft margins at entry (deg) |
|---|---:|---:|
| mild | `[6.145254, 15.853306]` | `[1.145254, 10.853306]` |
| moderate | `[5.393401, 13.691364]` | `[0.393401, 8.691364]` |
| adverse | `[5.399646, 13.684772]` | `[0.399646, 8.684772]` |

Mild survived `0.524 s` after takeover and then crossed the q1 lower soft
boundary at `q1=4.993849 deg`. Moderate and adverse survived `0.718 s` and
`0.546 s`, then crossed the q2 lower soft boundary at `q2=4.991170 deg` and
`4.963656 deg`. All remained in high-level `BED_SUPPORTED_MOTION`; no mismatch
case reached transfer planning.

The nominal case preserved the full state sequence and identical
`186.374756 N` peak robot-force norm. Its completion time increased from
`22.442 s` to `22.512 s` (`+0.070 s`, approximately `0.31%`) due to the explicit
startup handover.

This reviewed formal result confirms that R1 eliminates the 26--30 ms
takeover-induced q1 failure and safely enters normal tracking for all three
registered mismatch cases. The remaining failures are later
tracking/model-mismatch failures, not initialization or takeover failures.
R1 is complete. The evidence is sufficient to open a separately approved R2
Adaptive Tracking diagnosis/design task, but it does not prove adaptation can
restore feasibility: the formal logs contain strongly negative nominal and
realized dynamic margins before termination. R2 is not implemented here.
