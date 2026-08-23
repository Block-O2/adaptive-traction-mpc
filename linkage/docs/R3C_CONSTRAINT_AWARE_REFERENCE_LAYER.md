# R3C Constraint-Aware Reference Layer

## Scope and scientific boundary

R3C asks whether a transparent reference/safety layer can prevent the
moderate/adverse q2 lower-soft-boundary failures diagnosed by R3A, including
when online identification is late or accepts no update. It does not claim a
control-barrier-function, NMPC, stability proof, or formal safety guarantee.

The branch `agent/r3c-constraint-aware-reference-layer` starts at clean
post-R3A main commit `f781980`. It intentionally does not inherit the R3B
recontact controller from Draft PR #17 because R3B was classified `R3B_FAIL`.
R3C therefore changes only the optional progress/reference safety layer and
its logging/artifacts. It does not change Windowed NLS, Human V2, the nominal
path, the 10 degree tube, the componentwise +/-200 N force bounds, the bed
model, hip calibration, mismatch cases, or the existing tracking controller.

## Implemented hierarchy

The optional layer implements:

```text
NORMAL -> SLOWDOWN -> HOLD -> RECOVERY_REFERENCE -> NORMAL
```

- `NORMAL` leaves the existing reference/controller unchanged.
- `SLOWDOWN` continuously scales task progress with a bounded quintic
  `0 <= alpha <= 1`.
- `HOLD` sets progress scaling to zero.
- `RECOVERY_REFERENCE` may rate-limit a selected reference away from the q2
  lower boundary, but only inside the existing tube and only when its bounded
  force/residual prediction is feasible.
- If no such candidate exists, the run terminates as `TASK_INFEASIBLE`; it is
  not labeled task success or safe recovery.

The plant state is never clipped and the reference is never teleported. q2
lower/upper prediction is always monitored. q1 soft/ROM clearance is logged
and a predicted q1 crossing is monitored, but the positive engineering buffer
is not applied to q1 because the frozen nominal task endpoint itself lies on
the q1 soft-zone boundary.

## Engineering buffers

The existing Human V2 soft zone is 5 degrees. One fixed, case-independent
primary configuration derives:

| Quantity | Definition | Value |
|---|---:|---:|
| warning buffer | 0.20 x existing soft-zone width | 1.0 deg |
| hold buffer | 0.50 x warning | 0.5 deg |
| resume buffer | 1.50 x warning | 1.5 deg |
| prediction horizon | 10 x existing 0.01 s supervisor period | 0.1 s |
| recovery timeout | existing takeover recovery timeout | 2.0 s |
| candidate spacing | fixed posture-search spacing | 1.0 deg |
| reference rate cap | 10 deg tube / 0.5 s transfer duration | 20 deg/s |

These are engineering controller buffers, not clinical distances. They are
not tuned per case and do not establish a formal safety guarantee.

## Tests and smoke

Thirteen R3C tests cover explicit buffer derivation, no false intervention in
a comfortable state, predictive slowdown, bounded/continuous scaling, hold,
no-safe-candidate classification, resume hysteresis, tube/ROM-bounded recovery
candidates, hard force bounds, no plant-state clipping, nominal-model
ownership, unchanged estimator configuration, and unchanged task/constraint
configuration.

The final full retained regression completed with `163/163` passing, zero
failed and zero incomplete. The primary result remains the pre-registered
warning fraction 0.20. The corrected final smoke directory is:

```text
linkage/results/local/r3c_constraint_aware_reference_layer_smoke/20260816_150643
```

All sensitivity cases were retained:

| warning fraction | classification | duration (s) | progress | min q2 clearance (deg) |
|---:|---|---:|---:|---:|
| 0.15 | TASK_INFEASIBLE | 4.008 | 0.192624 | 3.90959 |
| 0.20 | TASK_INFEASIBLE | 4.006 | 0.192499 | 3.99249 |
| 0.25 | TASK_INFEASIBLE | 4.004 | 0.192374 | 4.07472 |

An earlier smoke `20260816_145720` exposed an implementation false positive:
the initial q1 soft-zone boundary was incorrectly treated as the q2 buffered
clearance. That output is retained. The signal attribution was corrected
without changing any buffer value or frozen scientific parameter.

## Formal Stage 1: oracle capability gate

The reviewed Stage 1 directory is:

```text
linkage/results/local/r3c_constraint_aware_reference_layer/
  20260816_151618/stage1_oracle
```

| Case | Classification | Duration (s) | Progress | Min q2 clearance (deg) | Soft / ROM / force violations | Intervention |
|---|---|---:|---:|---:|---:|---|
| nominal oracle | TASK_COMPLETE | 22.512 | 1.000000 | 5.00000 | 0 / 0 / 0 | SLOWDOWN, 1.852 s |
| moderate oracle | TASK_INFEASIBLE | 4.006 | 0.192499 | 3.99249 | 0 / 0 / 0 | SLOWDOWN -> HOLD, 0.030 s |
| adverse oracle | TASK_INFEASIBLE | 3.418 | 0.155749 | 2.99180 | 0 / 0 / 0 | SLOWDOWN -> HOLD, 0.040 s |

The Stage 1 gate permitted Stage 2 because nominal still completed and
moderate terminated before soft, ROM, or force-bound violation. This is a
capability gate, not a claim that moderate/adverse completed or became
feasible.

An earlier formal directory `20260816_150149` is also retained. Its first
implementation applied the q2 positive buffer to the frozen q1 endpoint and
therefore regressed nominal to `TASK_INFEASIBLE`. The original erroneous gate
flag was not overwritten; `reviewed_stage1_gate.txt` records that the run did
not permit Stage 2. No adaptive Stage 2 was launched from that run.

## Formal Stage 2: unchanged Windowed-NLS adaptive cases

The reviewed Stage 2 directory is:

```text
linkage/results/local/r3c_constraint_aware_reference_layer/
  20260816_152124/stage2_adaptive
```

| Case | Classification | Duration (s) | Progress | Min q2 clearance (deg) | Soft / ROM / force violations | ID accepted / rejected / failed | Parameter error |
|---|---|---:|---:|---:|---:|---:|---:|
| nominal | TASK_COMPLETE | 22.512 | 1.000000 | 5.00000 | 0 / 0 / 0 | 18 / 4 / 0 | 0 -> 0 |
| mild | RECONTACT_FAILED | 25.280 | 0.754685 | 4.53690 | 0 / 0 / 0 | 13 / 12 / 0 | 0.750 -> 0.131815 |
| moderate | TASK_INFEASIBLE | 3.942 | 0.164585 | 2.45330 | 0 / 0 / 0 | 1 / 2 / 0 | 0.888819 -> 0.435890 |
| adverse | TASK_INFEASIBLE | 3.782 | 0.155852 | 3.65273 | 0 / 0 / 0 | 0 / 3 / 0 | 1.322876 -> 1.322876 |

The estimator configuration and runtime ownership are unchanged. In
particular, adverse protection occurs with zero accepted updates and a nominal
controller model, so the intervention does not depend on successful online
identification.

## Frozen R2B comparison

R2B moderate ended `SOFT_LIMIT_VIOLATION` at 4.028 s, progress 0.170483,
with minimum q2 soft clearance -0.04229 degrees. R3C adaptive moderate instead
ends `TASK_INFEASIBLE` at 3.942 s, progress 0.164585, with +2.45330 degrees
clearance and no soft/ROM/force violation.

R2B adverse ended `SOFT_LIMIT_VIOLATION` at 3.904 s, progress 0.163303,
with minimum q2 clearance -0.03634 degrees and zero accepted updates. R3C
adaptive adverse ends `TASK_INFEASIBLE` at 3.782 s, progress 0.155852, with
+3.65273 degrees clearance, again with zero accepted updates.

Therefore R3C prevents the observed boundary violations by stopping earlier;
it does not improve survival or task progress. No formal case enters
`RECOVERY_REFERENCE`: all candidate searches reject the local recovery set on
the unchanged force/residual constraints. The experiment finds no recoverable
path inside the existing tube for moderate or adverse.

Nominal completion time/progress and mild classification/progress/parameter
error are identical to frozen R2B. Both show finite SLOWDOWN intervals, but no
net completion or endpoint regression. Mild still fails the unchanged
recontact threshold because R3C intentionally does not include R3B.

## Artifacts and review correction

Synchronized 180-frame GIFs were generated and visually checked for moderate
oracle, moderate adaptive, and adverse adaptive. Each contains the mechanism,
q/references, q2 clearance, safety alpha/state, robot force, progress, and
accepted-identifier markers. Required case figures and cross-case comparisons
are present under the reviewed formal directories.

The original `case_metrics.csv` defined `max_reference_deviation` as existing
governed-reference minus nominal-path deviation. That is not R3C-induced
recovery deviation. The formal MAT files and original CSVs remain unchanged.
Because every formal case has `recovery_count=0`, the correct R3C recovery
reference deviation is exactly zero. Non-overwriting corrected tables are
stored as `reviewed_case_metrics.csv`; cleaned comparison figures are under
`stage2_adaptive/reviewed_artifacts/`. Source logging now measures the R3C
override relative to the pre-safety base reference.

## Reproduction commands

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_r3c_constraint_aware_reference_layer_smoke"

/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_r3c_constraint_aware_reference_layer_oracle_gate"

/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_r3c_constraint_aware_reference_layer_adaptive"

/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_linkage_tests"
```

The local warning that `/Users/hankli/Documents/MATLAB` is inaccessible did
not affect the runs.

## Scientific classification and next priority

R3C is classified **PARTIAL**:

- it protects moderate oracle, moderate adaptive, and adverse adaptive from
  the observed q2 soft-boundary violation;
- adverse protection works with zero accepted identifier updates;
- nominal and mild final outcomes are preserved;
- it does not improve survival/progress, execute a successful recovery, or
  prove task feasibility or formal safety.

The checkpoint should remain a Draft PR rather than be merged as a completed
safety/recovery solution. Reduced-order identification cannot solve the
oracle-level infeasibility shown here, and additional uncertainty tightening
would make this already conservative stop earlier. The next supported priority
is architecture/task modification that creates a force-feasible path or
recovery posture inside the physical constraints; formal uncertainty-aware
tightening can be reconsidered after such a path exists. Reduced-order ID
remains a separate offline estimator question.

## R4 offline follow-up

R4 subsequently audited the frozen R3C Stage 1/2 MAT files without importing
the R3C controller implementation or rerunning a closed loop. The reviewed R4
directory is:

```text
linkage/results/local/r4_minimal_recovery_corridor/20260817_012427
```

R4 found many static recovery points, but no dynamically connected entry from
any of the six primary first-intervention/terminal states. Across posture-only
caps through 30 degrees, backward progress through 0.20, and their full coarse
Cartesian product, every primary true/perceived and bed-assisted/robot-only
case had `seed_count=0`. The classifications are therefore
`FEASIBLE_POINT_DISCONNECTED`, except two adverse true/robot-only
backward-only boundaries where no recovery point was found at all.

At the nearest true/bed-assisted static points, force components remain within
+/-200 N, but the frozen slew-limited R3C one-step controller produces
approximately 4.78--29.14 N m torque residual versus the unchanged `1e-8 N m`
acceptance tolerance. Moderate-oracle terminal also predicts q2 clearance
below the HOLD requirement. R4 therefore strengthens the R3C interpretation:
the failure is not merely an insufficient 10-degree search tube. Within the
approved freedom domain, extra posture/progress freedom does not create a
continuous admissible entrance under the current one-step force/slew/residual
contract. See
[R4_MINIMAL_RECOVERY_CORRIDOR.md](R4_MINIMAL_RECOVERY_CORRIDOR.md).
