# Stage-5 Acceleration-Semantics V2 Targeted Results

## Disposition

**V2 targeted validation stopped at the first preregistered historical-failure
case. V2 is not ready for a new robustness campaign.** The V1 disposition
remains `EXIT C — STOP THIS IMPLEMENTATION`.

The executed case was `low_low_high`, seed `20260824`, with plant scales
`alpha_t=0.9`, `alpha_r=0.9`, `alpha_d=1.2`. All other plant/task/controller
settings matched the frozen campaign case.

## First-action comparison

| Quantity | V1 historical | V2 attempt 02 |
|---|---:|---:|
| Selected total Human action [q1, q2] (Nm) | [42.2265, -4.9459] | [42.2265, -4.9459] |
| Executable wrench increment [Fx,Fy,Fz,Mx,My,Mz] | — | [-10.5966, 0, 8.7705, 0, 4.8099, 0] |
| First-action feasible / evaluated candidates | — | 64 / 59 |
| Episode result | ABORT at 10 ms | ABORT at 10 ms |
| Abort reason | `TASK_ACCELERATION_LIMIT` | `TASK_ACCELERATION_LIMIT` |

The V2 predictor classified the unchanged historical action as feasible:

| Prefix | Predicted q1/q2 (deg/s²) | Evaluation-truth q1/q2 (deg/s²) |
|---:|---:|---:|
| 5 ms | 139.94 / 363.58 | 185.82 / **633.71** |
| 10 ms | 196.06 / 520.12 | 197.91 / 593.86 |
| 15 ms | 209.35 / 554.46 | 187.18 / 514.28 |
| 20 ms | 208.23 / 546.83 | 180.72 / 466.70 |

The 15/20 ms truth values are read-only results from the already saved
counterfactual continuation of the identical V1/V2 first action; the V2 online
episode itself stopped at 10 ms. No new continuation was run.

The first real violation is q2 at 5 ms: the nominal V2 prediction is low by
270.12 deg/s². The online causal monitor later reported q2 = 610.54 deg/s² at
10 ms and terminated the episode. Thus interval alignment alone does not
remove the mismatch: the remaining blocker is early loaded-execution/interface
transient prediction error, not CEM failure to apply the new prefix predicate.

## Episode/safety/runtime observations

- Peak truth velocity before abort: 1.98 / 5.94 deg/s.
- Peak deployable acceleration: 202.83 / 610.54 deg/s²; peak truth acceleration:
  197.91 / 633.71 deg/s².
- Peak physical force 91.17 N; cumulative force 0.880 N·s; peak moment 14.65 Nm.
- One MPC `SAFE_ACTION`; two Safety Filter `SAFE_UNCHANGED`; no BRAKE, force
  gate, structural event, or MuJoCo warning.
- The single V2 solve took 52.27 ms. The 0.25 ms coupled prefix screen therefore
  introduced a material runtime cost relative to the historical 17.28 ms solve.

The remaining six preregistered cases were intentionally not run after the
stop condition fired. `attempt_01` (5 ms mean-wrench compression) and
`attempt_02` (0.25 ms coupled propagation) are ignored local engineering
artifacts; `attempt_02/targeted_results.json` is the compact result record.
