# R3B Recontact Margin Controller

## Purpose and isolated boundary

R3B asks whether the return controller can deliberately establish positive bed
contact reserve instead of accepting the first nonzero contact or settling just
below the existing stable-contact threshold. It is an isolated recontact and
load-return policy experiment built on the merged R3A checkpoint.

R3B does not change Windowed NLS, its gates or cadence, Human Model V2, the
nominal rehabilitation path, the 10 degree tube, the +/-200 N component box,
the bed model or hip calibration, uncertainty cases, the 2 N stable-contact
threshold, the 0.5 s dwell, or the 8 s recontact timeout. The single primary
engineering reserve is 1 N, giving a 3 N contact-force target. Neither value is
a clinical threshold. No reserve sensitivity was used to select a favorable
result.

## Controller extension

The R3B path is enabled only by an explicit configuration flag. The frozen R2B
path remains the default. During `RECONTACT`, the extension:

1. measures total bed force, minimum gap, gap velocity, penetration, joint
   state, reference deviation, robot force, and force slew;
2. computes the error to the fixed 3 N engineering target;
3. estimates the local two-joint bed-force gradient using the current
   controller model and the unchanged bed abstraction;
4. applies a least-norm reference correction limited to 0.5 degree/s;
5. confines the command to the existing local tube, ROM, and inactive
   soft-zone region;
6. permits `LOAD_RETURN` only after measured force is within 0.05 N of the
   3 N target, contact margin is nonnegative, absolute gap velocity is at most
   1 mm/s, penetration is at most 5 mm, and the unchanged 0.5 s dwell is met.

The controller never clips the plant state, changes the bed force, relaxes the
force box, or teleports the reference. Excess penetration or an 8 N recontact
force spike terminates recontact rather than hiding the condition.

## Mechanical smoke

The fixed 16.5 s mild-oracle smoke is retained at:

```text
linkage/results/local/r3b_recontact_margin_controller_smoke/20260816_141417
```

It exercises 1.390 s of the new `RECONTACT` path before the deliberate smoke
cap. Bed force reaches 2.85988 N, maximum penetration is 0.9477 mm, and maximum
reference deviation is 2.1739 degrees. The cap classification is `ABORTED` and
is mechanical smoke evidence only. It was not used to tune the reserve,
reference rate, or acceptance tolerance.

## Formal experiment

The reviewed fixed three-case output is:

```text
linkage/results/local/r3b_recontact_margin_controller/20260816_141525
```

Only nominal adaptive, mild adaptive, and mild oracle were run. Moderate and
adverse were not run. The frozen R2B and R2A formal MAT files were loaded only
for post-hoc comparison figures.

| Metric | Nominal adaptive | Mild adaptive | Mild oracle |
|---|---:|---:|---:|
| Classification | `RECONTACT_FAILED` | `TASK_COMPLETE` | `RECONTACT_FAILED` |
| Duration (s) | 23.116 | 25.148 | 23.114 |
| Final progress | 0.750060 | 1.000000 | 0.750060 |
| First-contact time (s) | 14.504 | 16.498 | 14.502 |
| First-contact force (N) | 0.2382 | 0.9320 | 0.2436 |
| Closing velocity at first contact (mm/s) | 4.171 | 16.075 | 3.999 |
| First reserve-stable force (N) | not reached | 2.9525 | not reached |
| Controlled-contact peak bed force (N) | 2.8475 | 3.3323 | 2.8599 |
| Late RECONTACT plateau (N) | 2.6441 | still building before transition | 2.6573 |
| Controlled-contact maximum penetration (mm) | 0.9436 | 1.1105 | 0.9477 |
| Contact chatter transitions | 0 | 0 | 0 |
| RECONTACT duration (s) | 8.004 | 1.046 | 8.004 |
| LOAD_RETURN completed | no | yes | no |
| Peak robot component (N) | 185.950 | 200.000 | 200.000 |
| ROM violations | 0 | 0 | 0 |
| Soft-limit active samples | 0 | 490 | 0 |
| Accepted/rejected/failed identifier solves | 13/10/0 | 20/5/0 | 0/0/0 |

The first-contact force is the first positive unilateral contact sample, not a
claim of stable contact. The controlled-contact penetration and bed-force
columns stop at the end of `LOAD_RETURN`; subsequent ordinary fully
bed-supported return reaches the much larger frozen bed loads and is reported
separately in `reviewed_case_metrics.csv`.

## Failure diagnosis

Nominal and mild oracle converge to steady, chatter-free plateaus below the
3 N target. At both endpoints the controller command is:

```text
q_command = [20.61573, 43.16410] deg
offset from local path = [-1.5, +1.5] deg
local tube = [+/-1.5, +/-1.5] deg
```

The force gradient remains finite (`[-245.30, 0] N/rad`), the command is not
blocked by the soft zone, and the force slope over the final second is
numerically zero. The command cannot move farther in the force-increasing
direction because it has reached the existing local tube boundary. Therefore
the fixed 3 N reserve is not attainable at this return location for nominal or
oracle under the unchanged tube. Waiting longer would not address the plateau.

Mild adaptive crosses the target and completes load return, but this does not
establish a robust recontact solution. Its altered physical parameters provide
enough support under the same bounded reference action while nominal and
oracle do not. It also records 490 soft-limit-active samples, 489 during
`BED_SUPPORTED_RETURN`, with minimum soft-zone clearance
`-0.0001555 deg`. This is a material regression against the frozen nominal/mild
no-soft-sample requirement even though it is shallow and causes no ROM
violation. No controller retuning or result deletion was performed after this
observation.

## Classification and decision

R3B is classified **R3B_FAIL**:

- nominal materially regresses from frozen `TASK_COMPLETE` to
  `RECONTACT_FAILED`;
- frozen mild oracle materially regresses from completion to
  `RECONTACT_FAILED`;
- mild adaptive completes, but the success is case-dependent and is followed
  by new soft-zone activation;
- the new policy does not introduce chatter, excessive controlled-contact
  penetration, ROM violation, or component-force violation;
- the failure is caused by a contact-reserve target that is infeasible inside
  the existing local tube for nominal/oracle, not by insufficient timeout.

The R3B branch and Draft PR are retained as negative evidence and must not be
merged. Per the registered stacking rule, R3C must start from clean post-R3A
`main`, not from R3B.

## Artifacts and review correction

Each formal case contains the legacy synchronized trajectory GIF plus
`r3b_recontact_margin.gif`, result MAT, and controller diagnostics. The root
contains the five required comparison figures, formal MAT, CSV, and summary.

The initial generated `case_metrics.csv` defined its peak bed force and
penetration window through the end of the entire trajectory. That combined
controlled recontact with the later high-load fully bed-supported return. The
raw trajectories were correct and were not rerun. The reporting definition was
corrected offline in `reviewed_case_metrics.csv` and `review_summary.txt`, with
formal MAT byte count and modification time verified unchanged. The tracked
metric helper now uses only first contact through the end of `LOAD_RETURN` for
controlled-contact extrema and records global extrema separately.

## Validation

- targeted R3B tests: 12 deterministic tests;
- tests cover the unchanged threshold/timeout/bounds, target construction,
  force-increasing direction, rate limit, tube/ROM/soft-zone containment,
  reserve dwell, baseline dwell compatibility, unsafe penetration handling,
  unchanged estimator configuration, absence of plant-state clipping, and
  controlled-versus-global metric scope;
- formal reserve sensitivity: not run;
- formal moderate/adverse cases: not run;
- no formal result was overwritten or removed.
- complete retained linkage regression: `162/162` passed, zero failed and
  zero incomplete in `237.4918 s` under MATLAB R2025b Update 1.
