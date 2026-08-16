# Dynamic Robust Load Transfer V1 — R2B Adaptive Tracking

## Purpose and boundary

R2B asks whether a bounded online Windowed Nonlinear Least Squares identifier,
using only naturally occurring task transitions, can recover a meaningful part
of the nominal-to-oracle tracking gap. It does not add deliberate excitation,
change the reference or controller gains, relax constraints, replace R1 Safe
Takeover, or add a safety filter. R3 is not implemented.

Every adaptive case starts with `theta_model = theta_nominal`. True simulation
parameters enter only the physical plant and post-hoc result reporting. A
failed, nonfinite, ill-conditioned, poor-fit, or invalid update retains the
last accepted controller model.

## Identified and fixed parameters

The seven estimated components are exactly the registered mismatch variables:

```text
[mass_scale, lc1_scale, lc2_scale, K_scale,
 qrest1_offset_rad, qrest2_offset_rad, sc_scale]
```

| Case | mass | lc1 | lc2 | K | qrest1 / qrest2 (deg) | sc |
|---|---:|---:|---:|---:|---:|---:|
| nominal | 1.00 | 1.00 | 1.00 | 1.00 | 0 / 0 | 1.00 |
| mild | 1.05 | 1.00 | 1.00 | 1.00 | -2 / -2 | 1.00 |
| moderate | 1.05 | 1.05 | 0.95 | 1.10 | -2 / -2 | 1.02 |
| adverse | 1.10 | 1.10 | 0.90 | 1.20 | -2 / -2 | 1.05 |

The fixed, case-independent bounds are the registered sensitivity envelope:
mass/lc1/lc2 `[0.90,1.10]`, K `[0.80,1.20]`, each rest offset `[-2,2] deg`,
and sc `[0.95,1.05]`. Link lengths, damping, gravity, ROM, soft-limit
constants, bed/contact constants, controller gains, and all task parameters
remain known and fixed.

## Measurement and residual contract

Each transition is appended only after the next state is measured. The runtime
identifier receives:

- current measured `q,dq`;
- current applied two-component robot force;
- subsequently measured next `q,dq`;
- known `dt`, hip calibration, bed/contact model, and fixed configuration.

It receives no true parameter object, case label, oracle state, or future state
beyond the completed one-step transition. The current simulation already uses
exact state feedback; R2B adds no separate perfect-acceleration signal or
finite-difference derivative.

For each window transition, candidate parameters are applied to the actual
linkage model and the existing RK4 step. The residual is:

```text
r_i(theta) = [(q_pred_next-q_measured_next)/dt;
              dq_pred_next-dq_measured_next]
```

This preserves the exact discrete simulator structure and gives both blocks
velocity units. The Spring2D implementation contributed only the generic
window/bounds/one-step-prediction pattern; none of its dynamics or parameters
were copied.

## Window, solver, and validation gate

- control period: `0.002 s`;
- window: 100 transitions = `0.20 s`;
- final NLS cadence: every 500 transitions = `1.0 s` simulated time;
- solver: bounded normalized-coordinate projected Gauss-Newton / LM;
- finite-difference step: `1e-4` of normalized coordinate;
- maximum iterations: 6;
- fixed line search: `[1, 0.5, 0.25, 0.125]`;
- numerical rank: all seven components required;
- maximum Jacobian condition: `1/sqrt(eps)`;
- fit gate: candidate residual must be finite and not exceed current-model
  residual beyond numerical tolerance;
- update bound: at most 20% of each registered range per accepted 1 Hz update.

The initial provisional replay measured the exact-RK4 solve at roughly
`1.16 s` mean for nominal under a 10 Hz proposed cadence. Before closed-loop
connection, cadence was therefore fixed once at 1 Hz. The per-simulated-second
maximum update rate remained 20% of a registered range. This is not a case
sweep or performance retuning.

Mismatch solves in the final replay still take approximately `1.75--4.01 s`
on the current machine. Consequently R2B is a simulated-time adaptive-control
experiment, not evidence of real-time deployability. No cheaper estimator was
substituted after observing that limitation.

## Offline replay gate

The reviewed implementation gate is
`linkage/results/local/dynamic_robust_load_transfer_v1_adaptive_tracking_r2b_offline_replay/20260815_182639`.
It reuses the R1 formal trajectories from `20260815_171801`; it is not a new
closed-loop scientific experiment.

Normalized error uses each registered parameter range as its scale.

| Case | Initial error | Final accepted error | Accepted / rejected / failures | First accepted | Final rank | Gate interpretation |
|---|---:|---:|---:|---:|---:|---|
| nominal | 0 | 0 | 18 / 4 / 0 | 2.0 s | 7 | zero drift |
| mild | 0.750 | 0.435 | 1 / 3 / 0 | 4.0 s | 7 | correct direction |
| moderate | 0.889 | 0.436 | 1 / 2 / 0 | 3.0 s | 7 | correct direction; raw estimate nearly true |
| adverse | 1.323 | 1.323 | 0 / 3 / 0 | none | 4 | naturally collected pre-failure data insufficient for seven-parameter acceptance |

All estimates remained finite and physical. Nominal did not drift, mild and
moderate improved, adverse safely retained the nominal model, and no solver
failed. The fixed offline gate therefore authorized closed-loop connection.
It does not establish closed-loop performance.

## Non-formal startup smoke

The retained six-second smoke directory is
`linkage/results/local/dynamic_robust_load_transfer_v1_adaptive_tracking_r2b_startup_smoke/20260815_183824`.

| Case | Status at cap/exit | Progress | Takeover | Accepted / rejected / failures | Parameter error | Soft / ROM samples |
|---|---|---:|---:|---:|---:|---:|
| nominal | cap during transfer | 0.275157 | 0.020 s | 5 / 1 / 0 | 0 -> 0 | 0 / 0 |
| mild | cap in tracking | 0.184989 | 3.876 s | 3 / 3 / 0 | 0.750 -> 0.294 | 0 / 0 |
| moderate | q2 soft-limit at 4.028 s | 0.170483 | 3.074 s | 2 / 2 / 0 | 0.889 -> 0.245 | 1 / 0 |
| adverse | q2 soft-limit at 3.904 s | 0.163303 | 3.358 s | 0 / 3 / 0 | 1.323 -> 1.323 | 1 / 0 |

All cases preserved R1 entry, finite estimates, the component-force bound, and
existing safety termination. This smoke is mechanical evidence only. Mild's
six-second survival and moderate's later exit are not promoted as formal
scientific results.

## Tests

Ten R2B tests cover window ordering/no-future leakage, parameter-bound
rejection, failed-solver fallback, residual rejection, bounded update rate,
nominal replay, mismatch direction, source-level no-oracle dependency, R1
traversal, force/soft/ROM regression, and unchanged task/safety configuration.
The final Dynamic Robust V1 group completed with `42/42` passing, and the full
retained linkage suite completed with `140/140` passing in MATLAB R2025b
Update 1 (`170.3571 s`, zero failures and zero incomplete tests).

## Formal adaptive evaluation

The reviewed user-run formal directory is:

```text
linkage/results/local/dynamic_robust_load_transfer_v1_adaptive_tracking_r2b/20260816_083505
```

The saved base configuration, nominal parameters, and calibration are exactly
equal to the reviewed R1 and R2A artifacts; the saved plan is exactly equal to
R2A. All four initial controller models equal nominal, and all four
plant-consistent initial-admissibility reports pass.

| Case | Final status / phase | Time (s) | Tracking survival (s) | Final s | Transfer | Takeover (s) |
|---|---|---:|---:|---:|---:|---:|
| nominal | `TASK_COMPLETE` / `NONE` | 22.512 | 22.492 | 1.000000 | yes | 0.020 |
| mild | `RECONTACT_FAILED` / `RETURN` | 25.280 | 21.404 | 0.754685 | yes | 3.876 |
| moderate | `SOFT_LIMIT_VIOLATION` / `TRACKING` | 4.028 | 0.954 | 0.170483 | no | 3.074 |
| adverse | `SOFT_LIMIT_VIOLATION` / `TRACKING` | 3.904 | 0.546 | 0.163303 | no | 3.358 |

Nominal exactly retains the R1 completion. Mild reaches transfer at `6.688 s`,
liftoff at `10.190 s`, and the `RECONTACT` mode at `17.278 s`, but does not
maintain the configured stable-contact condition before the unchanged `8 s`
recontact timeout. It therefore terminates as `RECONTACT_FAILED`; this is a
later return/contact limitation, not the original early tracking soft-limit
failure. Moderate and adverse retain one q2-lower soft-limit sample and zero
ROM-violation samples.

| Case | Peak component / norm (N) | Saturation fraction | Min force margin (N) | Min / peak bed (N) | Min soft / ROM margin (deg) |
|---|---:|---:|---:|---:|---:|
| nominal | 185.950 / 186.375 | 0 | 14.050 | 0 / 152.540 | 0 / 5.000 |
| mild | 200.000 / 200.690 | 0.005854 | 0 | 0 / 174.177 | 0 / 5.000 |
| moderate | 200.000 / 202.473 | 0.091315 | 0 | 93.391 / 182.871 | -0.042294 / 4.957706 |
| adverse | 166.990 / 168.115 | 0 | 33.010 | 106.633 / 179.820 | -0.036344 / 4.963656 |

The force constraint remains a component box; vector norms above `200 N` are
not component violations. No case exceeds the component bound.

## Formal identifier result

Theta order is `[mass, lc1, lc2, K, qrest1, qrest2, sc]`, with angular offsets
in radians. Normalized error scales each component by its registered range.

| Case | Error initial -> final | Accepted / rejected / failures | First accepted (s) | Final fit RMS |
|---|---:|---:|---:|---:|
| nominal | 0 -> 0 | 18 / 4 / 0 | 2.0 | 0 |
| mild | 0.750 -> 0.131815 | 13 / 12 / 0 | 4.0 | `2.18e-11` |
| moderate | 0.888819 -> 0.244966 | 2 / 2 / 0 | 3.0 | `4.05e-7` |
| adverse | 1.322876 -> 1.322876 | 0 / 3 / 0 | none | `0.016511` |

```text
nominal true/model:
[1, 1, 1, 1, 0, 0, 1]

mild true:
[1.05, 1, 1, 1, -0.0349066, -0.0349066, 1]
mild final raw:
[1.050362, 1.005080, 1.000389, 1.001185, -0.0258967, -0.0348691, 0.999238]
mild final accepted:
[1.050351, 1.005078, 1.000383, 1.001197, -0.0258964, -0.0348698, 0.999238]

moderate true:
[1.05, 1.05, 0.95, 1.10, -0.0349066, -0.0349066, 1.02]
moderate final raw:
[1.056916, 1.046782, 0.941470, 1.098564, -0.0198201, -0.0335188, 1.019516]
moderate final accepted:
[1.056916, 1.046782, 0.941470, 1.098564, -0.0198201, -0.0279253, 1.019516]

adverse true:
[1.10, 1.10, 0.90, 1.20, -0.0349066, -0.0349066, 1.05]
adverse final raw, rejected at rank 4:
[1.10, 0.908693, 0.90, 1.008030, -0.0349066, -0.0349066, 1.006043]
adverse final accepted:
[1, 1, 1, 1, 0, 0, 1]
```

All cases start collecting transitions before tracking. Moderate accepts its
first update during takeover, mild accepts its first update just after tracking
entry, and adverse never passes the full-rank gate. There are no solver
failures, nonfinite accepted estimates, or unsafe model corruption. Formal
mean solve times are `3.31`, `10.27`, `12.86`, and `5.80 s` from nominal to
adverse, further confirming that this exact-RK4 implementation is simulated-
time evidence only and not a real-time deployment claim.

## Nominal / adaptive / oracle comparison

| Case | Nominal-model | Adaptive | Oracle-model | Descriptive gap closure |
|---|---|---|---|---:|
| mild | soft limit; survival 0.524 s; s=0.109981 | recontact timeout; survival 21.404 s; s=0.754685 | complete; survival 22.490 s; s=1 | progress 72.44%; survival 95.06% |
| moderate | soft limit; survival 0.718 s; s=0.156077 | soft limit; survival 0.954 s; s=0.170483 | soft limit; survival 4.068 s; s=0.198249 | progress 34.16%; survival 7.04% |
| adverse | soft limit; survival 0.546 s; s=0.163303 | identical soft-limit endpoint; survival 0.546 s; s=0.163303 | soft limit; survival 3.490 s; s=0.162124 | progress denominator not meaningful; survival approximately 0% |

The observed mild result materially approaches the oracle and moves the
terminal limitation from early tracking to stable recontact. Moderate
identification moves toward truth and gives a small control improvement, but
the accepted model is still delayed/inexact at termination and the oracle also
fails at the same q2 boundary; both identification time and remaining
constraint/feasibility limitations matter. Adverse natural data are not
full-rank for the seven-parameter update, so the validation gate correctly
retains nominal behavior; R2B provides no adverse control improvement.

This one fixed formal matrix completes the approved R2B evaluation scope. The
evidence answers the Windowed-NLS question positively for mild, weakly for
moderate, and negatively for adverse under the available natural excitation.
It supports carrying the documented return/contact, moderate constraint, and
adverse identifiability limitations into a separately approved R3 decision;
R3 is not implemented here.

The executed reproducibility command was:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_dynamic_robust_load_transfer_v1_adaptive_tracking"
```

R2B stops after one fixed four-case formal evaluation. It does not start R3,
add uncertainty tightening, change the reference, add a safety filter, or
replace Windowed NLS.
