# Interface Mismatch v1 engineering report

Mismatch v1 is now reclassified and closed for decision purposes by
`INTERFACE_UNCERTAINTY_V1.md`. Its endpoint is B: a conservative finite-model
range catches the known false negative but makes nominal execution unusable,
so low-dimensional online interface identification is required before Human
identification. The original results below are unchanged.

## Scope and frozen contract

This is a small one-factor-at-a-time engineering probe from deterministic
checkpoint `e6ea54b701e2a825cc8558c3e0cae214a1fac777`. It is not a formal
scientific experiment, a hardware-calibrated uncertainty set, or a clinical
safety validation. The controller, Human model, CEM horizon/population/
iterations, action space, costs, motion envelope, HOLD controller, Safety
Filter/BRAKE, and 200 N simulation engineering gate were not changed. Human
adaptation, interface learning, terminal value learning, and RL remain off.
The shared CEM settings are seed `20260824`, 20 ms prediction/replanning step,
15 horizon steps, 32 candidates, 6 elites, and 2 CEM iterations.

The controller nominal Kelvin--Voigt record stayed fixed at:

- `Kt = [25000, 25000, 25000] N/m`;
- `Dt = [346.19104557, 377.33911767, 343.90028453] Ns/m`;
- `Kr = 320 Nm/rad`;
- `Dr = 10.02820618 Nms/rad`.

Only the `Stage5SensorBoundaryPlant` receives the cell-specific truth record.
The online observer, Goal-MPC rollout, first-action screening, loaded execution,
and HOLD controller continue to receive the independent controller nominal
record. Every result cell records both records and their explicit difference.

The shared initial condition fixes Human `q/dq` and the required static support
wrench to the checkpoint values. Because a fixed robot-side deformation is not
a static equilibrium for a different stiffness, the evaluation fixture alone
uses plant truth to set the corresponding robot-side equilibrium pose. This
truth record is not passed to online control. An earlier fixture attempt that
reused the nominal robot deformation produced a t=0 acceleration violation and
was retained locally as invalid preflight evidence, not counted as a sweep
cell.

## Experiment matrix

The three nominal ×1.0 matrix cells share one deterministic replay, so the
nine reported OFAT cells require seven unique plant runs.

| Factor | ×0.7 plant truth | ×1.0 plant truth | ×1.3 plant truth |
|---|---:|---:|---:|
| translational stiffness `Kt` | `[17500,17500,17500] N/m` | `[25000,25000,25000] N/m` | `[32500,32500,32500] N/m` |
| rotational stiffness `Kr` | `224 Nm/rad` | `320 Nm/rad` | `416 Nm/rad` |
| translational damping `Dt` | `[242.334,264.137,240.730] Ns/m` | `[346.191,377.339,343.900] Ns/m` | `[450.048,490.541,447.070] Ns/m` |
| rotational damping `Dr` | `7.01974 Nms/rad` | `10.02821 Nms/rad` | `13.03667 Nms/rad` |

All non-selected truth parameters stay nominal in each row. The 0.7/1.3
factors are engineering probes only.

## Observed task and motion results

Entries under H/R/C are absolute phase-entry times in seconds. Joint vectors
are `[q1,q2]`. Acceleration is the common causal/evaluation 20 ms quantity.

| unique cell | result | H/R/C (s) | HOLD (s) | peak velocity estimate / truth (deg/s) | peak acceleration deployable / truth (deg/s2) |
|---|---|---:|---:|---:|---:|
| `Kt×0.7` | COMPLETE | 1.705 / 2.425 / 4.250 | 0.720 | `[28.50,65.56]` / `[28.37,65.44]` | `[216.35,490.33]` / `[265.39,656.34]` |
| nominal | COMPLETE | 2.150 / 2.875 / 4.810 | 0.725 | `[25.70,59.98]` / `[25.77,60.08]` | `[189.07,458.69]` / `[193.49,481.89]` |
| `Kt×1.3` | ABORT `TASK_ACCELERATION_LIMIT` at 0.385 s | -- | -- | `[28.38,64.58]` / `[28.49,64.84]` | `[228.60,734.07]` / `[223.27,504.37]` |
| `Kr×0.7` | ABORT `INITIAL_CONDITION_OUTSIDE_SETTLED_START_SET` at 0 s | -- | -- | `[0,0]` / `[0,0]` | `[34.15,121.76]` / approximately `[0,0]` |
| `Kr×1.3` | COMPLETE | 1.940 / 2.695 / 4.665 | 0.755 | `[29.19,67.26]` / `[29.39,67.81]` | `[226.69,579.01]` / `[198.46,459.46]` |
| `D×0.7` | COMPLETE | 2.165 / 2.820 / 4.745 | 0.655 | `[26.85,61.16]` / `[26.82,60.85]` | `[178.15,365.80]` / `[189.92,482.75]` |
| `D×1.3` | COMPLETE | 2.105 / 2.605 / 4.595 | 0.500 | `[27.28,59.39]` / `[27.07,58.90]` | `[229.58,597.63]` / `[198.80,487.73]` |

The frozen velocity limits are `[45,75] deg/s`; every started cell stayed
within them in both estimated and truth traces. The frozen acceleration limits
are `[300,600] deg/s2`. `Kt×0.7` completed according to deployable control but
truth q2 reached `656.34 deg/s2`, 56.34 above the evaluation envelope.
`Kt×1.3` shows the opposite discrepancy: deployable q2 reached `734.07 deg/s2`
and caused the abort while truth peaked at `504.37 deg/s2`. `D×1.3` retained
only `2.37 deg/s2` deployable q2 margin.

## Mechanical, estimation, and prediction results

Force prediction is norm-error RMSE/p95/max. Interface-prediction columns are
20 ms prediction versus plant truth RMSE. State errors are estimate-minus-
evaluation-truth RMSE. A dash means no MPC prediction existed before the t=0
start-set rejection.

| cell | force peak / cumulative (N / Ns) | moment peak (Nm) | interface max translation / rotation | q RMSE (deg) | dq RMSE (deg/s) | interface prediction translation / rotation RMSE | force prediction RMSE/p95/max (N) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Kt×0.7` | 127.62 / 394.41 | 19.97 | 6.922 mm / 3.370 deg | `[0.186,0.187]` | `[0.172,0.262]` | 1.571 mm / 0.046 deg | 1.597 / 3.021 / 5.165 |
| nominal | 130.43 / 452.76 | 19.57 | 5.107 mm / 3.422 deg | `[0.002,0.004]` | `[0.084,0.158]` | 0.086 mm / 0.041 deg | 1.362 / 2.617 / 5.329 |
| `Kt×1.3` | 135.98 / 41.40 | 18.86 | 4.119 mm / 3.313 deg | `[0.109,0.108]` | `[0.181,0.292]` | 0.987 mm / 0.083 deg | 1.374 / 2.305 / 9.399 |
| `Kr×0.7` | 79.30 / 0.00 | 12.61 | 3.172 mm / 3.227 deg | `[0.627,1.595]` | `[0,0]` | -- | -- |
| `Kr×1.3` | 121.28 / 430.67 | 18.65 | 4.795 mm / 2.530 deg | `[0.283,0.746]` | `[0.334,0.835]` | 0.146 mm / 0.495 deg | 2.606 / 4.597 / 5.834 |
| `D×0.7` | 129.76 / 446.53 | 19.53 | 5.117 mm / 3.454 deg | `[0.013,0.033]` | `[0.523,1.109]` | 0.090 mm / 0.039 deg | 1.388 / 3.006 / 4.818 |
| `D×1.3` | 128.20 / 430.32 | 19.09 | 5.065 mm / 3.327 deg | `[0.011,0.028]` | `[0.205,0.470]` | 0.086 mm / 0.051 deg | 1.391 / 2.664 / 5.310 |

The largest force observed was 135.98 N, below the unchanged 200 N engineering
gate. Cumulative force is duration-dependent and therefore is not a normalized
force comparison; in particular the `Kt×1.3` value ends at the 0.385 s abort.

## MPC, runtime, safety, and path freedom

| cell | SAFE_ACTION / NO_SAFE_ACTION | Safety Filter | BRAKE / gate / warning | runtime mean/p95/max (ms) | >20 ms | path-freedom diagnostic |
|---|---:|---:|---:|---:|---:|---:|
| `Kt×0.7` | 174 / 0 | 850 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.186 / 19.177 / 20.112 | 1 | 0.271 |
| nominal | 202 / 0 | 962 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.320 / 19.154 / 19.499 | 0 | 0.258 |
| `Kt×1.3` | 20 / 0 | 77 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.389 / 19.753 / 20.193 | 1 | 0.157 |
| `Kr×0.7` | 0 / 0 | no execution | 0 / 0 / 0 | -- | 0 | -- |
| `Kr×1.3` | 193 / 0 | 933 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.173 / 19.131 / 20.161 | 1 | 0.276 |
| `D×0.7` | 202 / 0 | 949 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.251 / 19.115 / 19.377 | 0 | 0.255 |
| `D×1.3` | 202 / 0 | 919 `SAFE_UNCHANGED`, 0 intervention | 0 / 0 / 0 | 18.375 / 19.341 / 41.858 | 3 | 0.269 |

Every started solve returned `SAFE_ACTION`; no failure was caused by CEM
feasibility loss. All running cells retained a nonzero normalized q1/q2
progress difference, and the logs confirm no full time reference, coordination
ratio, or path corridor. Runtime mean remained 18.17--18.39 ms and every p95
remained below 20 ms. The six isolated misses, including the 41.86 ms wall-
clock maximum, preclude a WCET claim but do not change simulated action-hold
timing.

The fresh nominal run reproduces all checkpoint task, phase, solver, safety,
mechanical, motion, state, and path metrics exactly. Runtime is profiled but is
not expected to be bitwise deterministic; this fresh run had zero deadline
misses versus 2/202 in the checkpoint.

## Robustness interpretation

The first degradation is not force-gate or CEM feasibility. It is the fixed-
parameter interface inversion/prediction that supplies the Human state:

1. Translational stiffness mismatch increases 20 ms translation prediction
   RMSE from 0.086 mm nominal to 0.987--1.571 mm, then changes q/acceleration
   estimates. This produces both a missed truth acceleration violation at
   `Kt×0.7` and a conservative false online violation at `Kt×1.3`.
2. Rotational stiffness is the most start/completion-sensitive factor. At
   `Kr×0.7`, the t=0 nominal observer q error is `[0.627,1.595] deg`; q2 already
   lies outside the immutable 1 deg start tolerance. At `Kr×1.3`, the episode
   completes, but rotation prediction RMSE rises to 0.495 deg, q2 estimation
   RMSE to 0.746 deg, and force prediction RMSE to 2.606 N.
3. Damping mismatch leaves static initialization intact and all damping cells
   complete. Its earliest effect is transient dq estimation: q2 dq RMSE is
   1.109 deg/s at `D×0.7`. At `D×1.3`, the deployable acceleration monitor is
   nearly saturated despite comfortable truth margin.
4. Force peaks, explicit execution screening, Safety Filter/BRAKE, numerical
   warnings, and runtime did not degrade first. No running cell reached the
   200 N gate or produced `NO_SAFE_ACTION`.

Thus the nominal Kelvin--Voigt structure remains mechanically usable for the
completed damping probes and the positive stiffness probes that pass online
task monitoring, but one fixed nominal parameter record is not sufficient for
the whole ±30% stiffness probe: two cells abort and one additional completed
cell violates the evaluation-only acceleration envelope. This is evidence for
eventual interface-parameter uncertainty handling or estimation, not evidence
that a residual learner is currently required.

The next structural-mismatch experiment should remain one-factor and small:
use one mild progressive translational stiffness plant with the same nominal
small-deformation tangent K/D, selecting its nonlinear coefficient a priori so
the tangent changes by about 10% at the nominal observed peak deformation.
Compare it only with the frozen nominal cell, keep the controller linear and
non-learning, and report the same observer/prediction/motion chain. This should
be deferred until the parameter-mismatch start/acceleration semantics above
are explicitly accepted; otherwise structural and parameter effects would be
confounded.

## Reproduction and retained evidence

The successful aggregate is
`results/interface_mismatch_v1_attempt03/sweep_summary.json`; per-cell full
traces and plots remain local in the ignored results tree and are not intended
for commit. Two preflight attempts are also retained locally:

- `interface_mismatch_v1`: no valid episode; nominal robot-side deformation
  was incorrectly reused for the mismatched physical equilibrium;
- `interface_mismatch_v1_attempt02`: three cell summaries were completed, then
  the runner stopped at the legitimate `Kr×0.7` t=0 rejection before that
  rejection had structured aggregation support.

Successful command:

```bash
MPLCONFIGDIR=/tmp/stage5_interface_mismatch_mpl \
XDG_CACHE_HOME=/tmp/stage5_interface_mismatch_cache \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_interface_mismatch_v1.py \
  --output-dir stages/stage5_personalized_motion_learning/results/interface_mismatch_v1_attempt03
```
