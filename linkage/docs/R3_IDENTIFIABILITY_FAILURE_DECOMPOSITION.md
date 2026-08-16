# R3A Identifiability and Failure-Mode Decomposition

## Purpose and boundary

R3A is an offline diagnostic of the reviewed R1, R2A, and R2B formal logs. It
asks three separate questions:

1. Which combinations of the seven R2B mismatch coordinates are informed by
   the naturally collected windows, and when does that information appear?
2. Is the moderate failure primarily delayed/inexact identification, a
   controller-model effect, or a remaining constraint/feasibility boundary?
3. Is the mild `RECONTACT_FAILED` endpoint caused by contact chatter, a
   closing transient that only needs more time, or a stable but insufficient
   return/contact equilibrium?

The analysis does not run a new closed-loop trajectory, implement an R3
controller, change Windowed NLS, add deliberate excitation, change the
reference, change any force/ROM/soft limit, or change the bed, Human Model V2,
supervisor, optimizer, or stopping rules. EKF/UKF, robust loss, safety filters,
and controller retuning are decision candidates only; none is implemented.

## Frozen inputs and retained output

The reviewed source artifacts are:

```text
R1  linkage/results/local/dynamic_robust_load_transfer_v1/
    20260815_171801/formal_results.mat
R2A linkage/results/local/dynamic_robust_load_transfer_v1_oracle_model_r2a/
    20260815_174540/formal_oracle_results.mat
R2B linkage/results/local/dynamic_robust_load_transfer_v1_adaptive_tracking_r2b/
    20260816_083505/formal_adaptive_results.mat
```

The reviewed R3A directory is:

```text
linkage/results/local/r3_identifiability_failure_decomposition/20260816_093111
```

The runner records source path, byte count, and modification time before and
after analysis and aborts if any source artifact changes. The matching test
also verifies source immutability. Generated R3A files remain ignored local
evidence under the repository artifact policy.

Earlier development attempts are retained rather than hidden or overwritten:

- `20260816_091505`: table-shape runtime error;
- `20260816_091613`: historical R1 compatibility field absent;
- `20260816_091746`: unsupported tiled-layout legend call;
- `20260816_091923` and `20260816_092419`: complete predecessor outputs;
- `20260816_093111`: final output after figure readability fixes.

The fixes were mechanical compatibility/presentation changes only. No
scientific configuration changed.

## Identifier reconstruction method

For every logged R2B solve attempt, R3A reconstructs the same 100-transition,
0.20 s identifier window and the same normalized finite-difference Jacobian
used by R2B. It records:

- solve time, window start/end, and sample count;
- exact hybrid phase and R1 takeover-mode composition;
- logged and reconstructed rank, seven singular values, and condition number;
- accepted/rejected status and parameter vectors before, raw, and after the
  attempted update;
- normalized parameter error;
- normalized Jacobian-column correlations;
- right singular vectors and phase-aggregated information.

Rank uses the existing R2B numerical rule. The full-rank acceptance gate still
requires rank seven and condition no greater than `1/sqrt(eps) = 6.7108864e7`.
R3A does not reinterpret a tiny singular value as reliable information merely
because stacking crosses the numerical rank tolerance.

## Rank evolution and phase information

Rank evolution across solve attempts is:

| Case | Rank sequence | Accepted / attempts | Interpretation |
|---|---|---:|---|
| nominal | `6, 7` followed by twenty rank-7 windows | 18 / 22 | task motion provides persistent full-rank windows |
| mild | `4,4,4`, seventeen rank-7 windows, then `4,4,4,4,4` | 13 / 25 | tracking/transfer excites all directions; late steady recontact loses them |
| moderate | `4,4,7,7` | 2 / 4 | rank grows during takeover/tracking before the early q2 exit |
| adverse | `5,4,4` | 0 / 3 | failure occurs while attempted windows remain near-static safe-hold data |

The hybrid label alone is not a sufficient excitation descriptor. Moderate
remains in `BED_SUPPORTED_MOTION` for all four attempts, yet its R1
takeover-mode change from `SAFE_HOLD` to `TAKEOVER`/`TRACKING` supplies rank
growth. Adverse terminates at `3.904 s` before a post-tracking solve can occur;
all three attempted windows are `BED_SUPPORTED_MOTION` plus `SAFE_HOLD`.

For mild, stacked phase diagnostics show full numerical rank during tracking,
transfer, suspended motion, and the complete recontact interval. However, the
last five individual steady-recontact windows fall back to rank four. The
full recontact stack therefore describes information accumulated across entry
and settling, not persistent local identifiability at the terminal plateau.

## Adverse identifiable and weak combinations

The final adverse normalized spectrum is:

```text
[1, 0.128543, 2.07071e-4, 9.16552e-5,
 1.39439e-16, 4.98682e-17, 4.88745e-20]
```

The final window has rank four. Stacking all three attempt windows crosses the
numerical rank-seven tolerance, but its condition number is `2.83979088e11`,
more than four thousand times the unchanged R2B limit. Its last three relative
singular values are approximately `6.48e-10`, `2.85e-10`, and `3.52e-12`.
This is numerical accumulation of extremely weak directions, not evidence
that the physical seven-parameter estimate is acceptable.

The strongest final-window column correlations include:

| Pair | Correlation |
|---|---:|
| `lc1_scale`, `qrest1_offset_rad` | -0.9999992 |
| `lc2_scale`, `qrest2_offset_rad` | +0.9998184 |
| `lc2_scale`, `sc_scale` | -0.9997627 |
| `K_scale`, `qrest2_offset_rad` | -0.9996945 |
| `qrest2_offset_rad`, `sc_scale` | -0.9991663 |
| `lc2_scale`, `K_scale` | -0.9990421 |

Consequently, rank four must not be read as four independently identifiable
physical parameters. The informed coordinates are local linear combinations.
In particular, the weakest right-singular direction is dominated by
`K_scale` and `qrest1_offset_rad`, while other weak directions mix link COM,
rest-angle, contact-location, and stiffness coordinates.

The four-dimensional adverse strong subspace also does not transfer cleanly
to the other mismatch cases. Principal-angle cosines against the final strong
four-dimensional subspaces are:

| Comparison | Principal-angle cosines | Angles (deg) |
|---|---|---|
| adverse vs mild | `1.000, 0.928, 0.707, 0.077` | `0, 21.85, 45.05, 85.56` |
| adverse vs moderate | `1.000, 0.9999, 0.547, 0.175` | `0, 0.84, 56.81, 79.93` |

Only one or two directions align well. A fixed global four-parameter physical
subset is therefore not justified. A local/relinearized subspace or grouped
prior is a defensible research candidate, but it requires a separately
approved offline/smoke validation before any closed-loop use.

## Moderate failure decomposition

All times below are aligned to each case's first `TRACKING` sample.

| Source | First outside tube | Terminal | Final progress | Terminal q2 soft clearance |
|---|---:|---:|---:|---:|
| nominal model | +0.656 s | +0.720 s | 0.156077 | -0.00883 deg |
| adaptive | +0.832 s | +0.956 s | 0.170483 | -0.04229 deg |
| oracle model | +3.796 s | +4.070 s | 0.198249 | -0.03520 deg |

Adaptive accepts its first update at `3.000 s`, only `0.072 s` before
tracking entry, with normalized error `0.43589`. Its second accepted update is
only about `0.028 s` before termination. Adaptive therefore gains `0.236 s`
of survival and `0.014405` progress over nominal, but remains far short of the
oracle survival.

R3A also evaluates nominal, current adaptive, and true parameter models at
the exact states and applied inputs recorded on the adaptive trajectory. This
is a same-state model diagnostic, not a counterfactual rollout and not a claim
that another model would have produced the same trajectory.

- At adaptive tracking entry, the reconstructed dynamic margins are
  `-86.37 N` nominal, `-110.84 N` adaptive, and `-122.66 N` true.
- At the terminal recorded state, they are `-402.82 N` nominal,
  `-528.27 N` adaptive, and `-529.19 N` true.
- Across adaptive tracking, adaptive-minus-true margin error averages
  `+15.64 N`, compared with `+53.59 N` for nominal-minus-true.

The accepted model is therefore substantially closer to the oracle model by
the terminal state, yet adaptive and oracle terminate at essentially the same
q2 lower soft boundary (`4.958` and `4.965 deg` absolute clearance before the
violating sample). The moderate outcome is classified as mixed:

- estimator history and update delay limit how soon the controller benefits;
- the terminal mechanism is also present under the oracle model and is a
  remaining q2 constraint/trajectory-feasibility boundary.

It would be incorrect to label the failure purely an estimator failure or
purely an oracle feasibility failure.

## Mild recontact decomposition

The nominal-model mild case never reaches recontact. The adaptive and oracle
recontact intervals are:

| Metric | Adaptive | Oracle |
|---|---:|---:|
| Interval | 17.278--25.280 s | 15.112--15.610 s |
| Logged span / samples | 8.002 s / 4002 | 0.498 s / 250 |
| Active contact fraction | 1.000 | 1.000 |
| Contact active-state transitions | 0 | 0 |
| Initial bed force | 2.0418 N | 2.659 N |
| Final bed force | 1.8343 N | 2.393 N |
| Final minimum gap | -0.6114 mm | -0.7977 mm |
| Time continuously above 2 N | 0.058 s | full 0.498 s |
| Outcome | timeout | complete |

Adaptive enters genuine unilateral contact and never chatters or bounces out
of it. Bed force crosses below the configured 2 N stable-contact threshold
once and never returns. The late plateau is approximately `1.8343 N`, with
gap velocity at numerical zero. The terminal posture is approximately
`q1=20.878 deg`, `q2=41.913 deg`, and the final normalized parameter error is
`0.131815`.

This is a persistent shallow-contact equilibrium below the stability
threshold, not a still-closing transient. Extending the unchanged timeout is
not supported by the observed plateau. The oracle succeeds under the same
policy and threshold, so stable recontact is not intrinsically impossible.
The observed limitation is mixed residual model/posture error plus inadequate
return/contact force margin under the current policy.

## Decision table

The three failures do not support one universal estimator replacement.

| Candidate | Directly supported evidence | What it would address | What it would not address | Decision |
|---|---|---|---|---|
| A. Reduced/local-subspace Windowed NLS | adverse has four strong local combinations, but only one or two transfer consistently across cases | adverse rank/condition gate and parameter grouping | oracle q2 boundary; mild recontact equilibrium | promising offline candidate; validate before closed loop |
| B. Robust loss and smoothing | no solver failure, nonfinite update, or logged outlier mechanism is observed | possible future outliers/noise | lack of excitation or rank; oracle constraint boundary | low priority from current evidence |
| C. EKF/UKF replacement | no evidence that filtering changes the adverse sensitivity rank | state/parameter uncertainty representation | structural excitation deficiency; recontact force margin | not justified as the next step |
| D. Recontact policy/controller improvement | adaptive settles stably at 1.834 N while oracle remains above 2 N and completes | mild return/contact stability margin | moderate/adverse identification and q2 feasibility | highest-priority directly supported implementation candidate |
| E. Constraint-aware safety/reference layer | moderate and adverse oracle cases still hit the same q2 soft boundary | q2 feasibility and pre-boundary reference/safety handling | adverse identifiability; mild shallow contact | high-priority separate candidate after explicit approval |

Candidate D is the first directly supported controller-side experiment for the
mild endpoint. Candidate E is separately supported for moderate/adverse. They
solve different mechanisms and must not be bundled into an unregistered
multi-variable experiment. Candidate A may be studied offline, but the
current evidence does not authorize a fixed four-physical-parameter estimator
or any closed-loop R3 change.

The subsequent isolated Candidate-D experiment is documented in
[R3B_RECONTACT_MARGIN_CONTROLLER.md](R3B_RECONTACT_MARGIN_CONTROLLER.md).
Its fixed 1 N reserve produces a reviewed negative result: mild adaptive
completes, but nominal and mild oracle cannot reach the 3 N target inside the
unchanged local tube and mild adaptive introduces later soft-zone activation.
That result does not revise this R3A diagnosis or support carrying R3B into the
separate constraint-aware experiment.

## Artifacts

The final directory contains nine required figures:

```text
identifier_rank_over_time.png
identifier_singular_values.png
parameter_correlation_matrix.png
identifiable_subspace.png
moderate_nominal_adaptive_oracle.png
moderate_failure_decomposition.png
mild_recontact_diagnostics.png
mild_adaptive_vs_oracle_recontact.png
r3a_failure_taxonomy.png
```

It also contains window, singular-value, correlation, phase-information,
subspace, moderate, mild, and source-manifest CSVs; `summary.txt`;
`console.log`; and `r3a_analysis_workspace.mat`.

## Tests and reproducibility

Ten deterministic R3A tests cover frozen-log loading, exact window dimensions,
adverse rank reconstruction, singular-value validity/order, zero-column-safe
correlation, deterministic phase segmentation, accepted/rejected alignment,
moderate event alignment, mild recontact timing, and source immutability.

The targeted R3A suite completed with `10/10` passing. The complete retained
linkage suite completed with `150/150` passing, zero failed and zero incomplete
tests, in MATLAB R2025b Update 1 (`224.9304 s`).

The executed final offline-analysis command was:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_r3_identifiability_failure_decomposition"
```

The complete regression command was:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_linkage_tests"
```

The warning that `/Users/hankli/Documents/MATLAB` is inaccessible is a local
MATLAB path warning and did not affect either run. A separate MATLAB
license/logger crash occurred during later inspection after the reviewed R2B
formal artifacts had already been fully written; it was not an R2B experiment
failure and the formal experiment was not rerun.

## Scope conclusion

R3A mechanically and analytically decomposes the observed limitations without
changing the experiment. Adverse is dominated by insufficient early natural
excitation and highly correlated parameter combinations. Moderate is mixed
estimator history plus an oracle-level q2 feasibility boundary. Mild reaches a
stable but subthreshold contact equilibrium rather than chatter or a still-
closing transient. These mechanisms require separate future interventions;
R3A itself implements none of them.
