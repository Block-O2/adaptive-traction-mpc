# R4 Minimal Recovery Corridor Study

## Question and boundary

R4 asks the narrow offline question left by R3C: starting from real R3C
safe-stop states, how much additional task freedom is required before a
continuous, locally dynamic, force-feasible recovery corridor exists?

R4 does not implement a recovery controller, change the estimator, rerun R3C,
or modify the plant, task path, original 10-degree tube, force bounds, bed,
Human Model V2, optimizer, or formal R3C logs. The R4 branch starts from clean
post-R3A main `f781980`; R3B and R3C controller code are not in its ancestry.
The R3C report is included only as frozen-evidence documentation plus this R4
follow-up.

## Frozen sources and anchors

The two read-only sources are:

```text
Stage 1 oracle
linkage/results/local/r3c_constraint_aware_reference_layer/
  20260816_151618/stage1_oracle/formal_oracle_gate.mat

Stage 2 adaptive
linkage/results/local/r3c_constraint_aware_reference_layer/
  20260816_152124/stage2_adaptive/formal_adaptive_results.mat
```

Their before/after SHA-256 values are respectively:

```text
32cb5b5e73a17ebea203f63e8b176ccc331a6f5c06e8a367c1950de4cd60349d
fae1e13dd28f9256a82a80ca1833eecd5591fd6406a6c91e6c19e69da7250997
```

R4 extracts first intervention, first HOLD, and terminal stop for moderate
oracle, moderate adaptive, and adverse adaptive. First intervention and
terminal stop are the six primary graph-search anchors; the three first-HOLD
states are retained as maximum-domain diagnostics.

| Case/anchor | t (s) | progress | q (deg) | dq (deg/s) | bed force (N) |
|---|---:|---:|---:|---:|---:|
| moderate oracle, first intervention | 3.978 | 0.191374 | 9.725 / 10.081 | -1.840 / -36.604 | 58.120 |
| moderate oracle, terminal | 4.006 | 0.192499 | 9.662 / 8.992 | -2.685 / -41.027 | 59.186 |
| moderate adaptive, first intervention | 3.898 | 0.162507 | 7.093 / 8.387 | 0.052 / -19.038 | 93.392 |
| moderate adaptive, terminal | 3.942 | 0.164585 | 7.080 / 7.453 | -0.683 / -23.341 | 93.749 |
| adverse adaptive, first intervention | 3.744 | 0.154333 | 6.267 / 9.994 | -3.337 / -35.274 | 115.739 |
| adverse adaptive, terminal | 3.782 | 0.155852 | 6.140 / 8.653 | -3.068 / -34.102 | 119.057 |

## Registered search

The approved freedom families are evaluated without per-case tuning:

- A, posture only: global tube caps `10, 12, 15, 20, 25, 30` degrees at the
  frozen current progress;
- B, progress only: backward progress `0, 0.01, 0.02, 0.05, 0.10, 0.15, 0.20`
  with the original 10-degree cap;
- C, combined: the full A-by-B coarse product, with Pareto selections only if
  a connected result exists.

The posture lattice is 1 degree coarse. Registered boundary refinement uses
0.5 degree posture and 0.005 progress spacing; a 0.25 degree convergence check
is available when a primary connected boundary exists. Local dynamic edges use
20 deg/s as primary and 10 deg/s as a non-near-zero sensitivity. The local
connection/edge radius is 1.5 degrees.

Every recovery point must satisfy ROM, inactive soft torque, q2 resume
clearance, componentwise +/-200 N, the current `1e-8 N m` dynamic residual
tolerance, a 0.1 s short prediction, and phase-consistent bed support when bed
credit is enabled. True physical and controller-perceived models are solved
and labeled separately. Robot-only repeats the same posture and constraints
with zero bed-torque credit.

A point is not a corridor. Geometry nodes first pass the point/transit
predicate; a frozen R3C one-step controller prediction must then connect the
real anchor to a local node. BFS only traverses locally dynamic feasible edges.
The three classifications are exactly:

```text
NO_RECOVERY_POINT_FOUND
FEASIBLE_POINT_DISCONNECTED
CONTINUOUS_RECOVERY_CORRIDOR_EXISTS
```

## Reviewed result

The reviewed output is:

```text
linkage/results/local/r4_minimal_recovery_corridor/20260817_012427
```

It contains 1,326 setting rows, 78 selected boundary rows, nine anchors, nine
required PNGs, a full MAT workspace, and before/after source hashes. No
recovery path row exists because no connected corridor was found.

### Primary moderate-oracle result

No approved freedom family produces a continuous recovery corridor at either
primary moderate-oracle anchor:

| Anchor | Family | Maximum tested freedom | Static points | Nearest point (deg) | Classification |
|---|---|---|---:|---:|---|
| first intervention | A | cap 30 | 275 | 3.272 | FEASIBLE_POINT_DISCONNECTED |
| first intervention | B | cap 10, back 0.20 | 1,588 | 3.054 | FEASIBLE_POINT_DISCONNECTED |
| first intervention | C | cap 30, back 0.20 | 6,150 | 3.042 | FEASIBLE_POINT_DISCONNECTED |
| terminal | A | cap 30 | 280 | 3.166 | FEASIBLE_POINT_DISCONNECTED |
| terminal | B | cap 10, back 0.20 | 1,591 | 3.283 | FEASIBLE_POINT_DISCONNECTED |
| terminal | C | cap 30, back 0.20 | 6,155 | 3.166 | FEASIBLE_POINT_DISCONNECTED |

Thus the minimum posture relaxation, minimum reversal, and balanced Pareto
knee are all **not found within the approved domain**. The maximum tested
values are upper bounds, not successful thresholds.

### Adaptive, model, bed, and timing comparisons

Moderate/adverse adaptive cases often have a static point much closer to the
anchor (0.235--1.113 degrees for the selected true/bed-assisted rows), but all
still have `seed_count=0`. There are 76
`FEASIBLE_POINT_DISCONNECTED` selected boundary rows and two
`NO_RECOVERY_POINT_FOUND` rows. The latter are adverse true/robot-only Family
B at first intervention and terminal. No selected boundary row is connected.

True and perceived connectivity agree everywhere: neither sees a connected
corridor. A point-level disagreement remains in those two adverse robot-only
Family-B rows: the true model finds no recovery point, while the perceived
model finds points that remain disconnected. This is controller optimism at
the point level, not a recovery claim.

Bed assistance creates additional static points, including in those adverse
Family-B settings, but it does not produce a graph seed or connected corridor.
Robot-only and bed-assisted differ in point feasibility but not in the final
connectivity conclusion. Earlier intervention also does not change the final
classification, although it preserves more predicted clearance than terminal
stop in the moderate-oracle case.

### Why the point clouds are disconnected

At the nearest true/bed-assisted static points, component force bounds and bed
support are satisfied. The existing controller can change each force component
by only `250 N/s * 0.002 s = 0.5 N` in the first step. Under that frozen slew
limit, the R3C one-step torque residual is:

| Anchor | Residual range across selected A/B/C points (N m) | Predicted q2 clearance (deg) |
|---|---:|---:|
| moderate oracle first intervention | 27.82--28.65 | 0.913 |
| moderate oracle terminal | 28.36--29.14 | -0.438 |
| moderate adaptive first intervention | 10.06--11.95 | 1.315 |
| moderate adaptive terminal | 10.46--10.63 | 0.082 |
| adverse adaptive first intervention | 5.08--5.12 | 1.456 |
| adverse adaptive terminal | 4.78--8.30 | 1.215 |

All are far above the unchanged `1e-8 N m` acceptance tolerance. The
moderate-oracle terminal prediction also violates HOLD clearance. This
explains why many static points exist but none can seed BFS. It is not a solver
failure and is not repaired by selecting the most favorable static point.

## Decision

The observed result is: **no minimum continuous recovery freedom was found
inside the approved A/B/C domain**.

R4 does not support merging R3C as a completed recovery solution, increasing
the tube alone, or allowing backward progress alone. The next decision should
separate two new questions before any implementation:

1. whether the `1e-8 N m` exact one-step residual requirement is the intended
   physical admission rule when force slew is active; and
2. if it is, whether a separately specified multi-step braking/force-ramp
   transition can create an admissible entrance without changing force, ROM,
   soft-limit, or bed constraints.

These are recommendations only. R4 changes neither residual tolerance, slew
limit, controller, nor path.

## Reproduction and artifacts

Formal offline command:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_r4_minimal_recovery_corridor"
```

The reviewed directory contains the required summary, five CSV evidence
tables, empty-header-only `recovery_paths.csv`, MAT workspace, source
manifest, config snapshot, and all nine registered PNGs. Eighteen deterministic
R4 tests cover config, frozen inputs, anchors, model selection, tube geometry,
no future progress, point/edge predicates, classification, determinism,
refinement convergence, and source immutability. The full retained regression
completed with `168/168` passing, zero failed and zero incomplete in
`230.6275 s`.
