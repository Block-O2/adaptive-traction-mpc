# Stage-5 Model-Update Max-Step Comparison v1

Status: **formal comparison complete**.

Supported conclusion: **0.04 gives the best speed/stability tradeoff**.

This comparison fixed `model_update_alpha=0.25` and changed only the absolute
per-scale bounded-update cap: 0.03, 0.04, or 0.05.  The formal alpha-comparison
step=0.03 arm passed all reuse checks and was not rerun.  Step=0.04 and 0.05
were each executed fresh for five matched repetitions.

Formal result:
`results/model_update_max_step_comparison_v1_formal_attempt_01/model_update_max_step_comparison_results.json`
(SHA-256 `be8cd160e0ca5b63d560c6f56888202fc20c3ba78f5d9aec0b30680f5e803fbb`).

## Frozen contract

- Only variable: `maximum_per_scale_step = 0.03 / 0.04 / 0.05`.
- Fixed `model_update_alpha=0.25`.
- Damping +20% Human; evaluation-only truth `[1.0,1.0,1.2]`.
- Same supported `theta_1`, seeds `20260828..20260832`, gamma 0.5,
  Human-ID, 8-block future validation, post-update evidence authority,
  repetition-boundary activation, native prefix backend, task, interface,
  monitor, limits, Safety Filter, and BRAKE.
- Frozen endpoint: `0.00021518124214580563 Nms^2`.
- Predeclared materiality: fewer repetitions to the endpoint, or at the same
  endpoint repetition at least 10% lower loss than the smaller acceptable cap.
- `effectively uncapped` means no parameter hits the step cap in any qualified
  transition.

Contract SHA-256:
`7591595d2709520c60b754b3dccba9983429162821fe14d2fe9c4e649f212b33`.

## Step=0.03 reuse audit

All 13 checks passed: formal execution provenance, alpha=0.25, five matched
repetitions, seeds, theta_1, step=0.03, truth isolation, gamma, native backend,
unchanged acceleration monitor/controller contract, COMPLETE status, and no
registered safety event.  Arm A was therefore reused exactly and not rerun.

## Theta and prediction-loss evolution

| Rep | Step 0.03 active `[M,K,D]` | Loss | Step 0.04 active `[M,K,D]` | Loss | Step 0.05 active `[M,K,D]` | Loss |
|---:|---|---:|---|---:|---|---:|
| 1 | `[1.000058,1.001042,1.019348]` | 0.0003829484 | same | 0.0003829484 | same | 0.0003829484 |
| 2 | `[1.000213,1.002859,1.049348]` | 0.0002921061 | `[1.000213,1.002859,1.059348]` | 0.0002546447 | `[1.000213,1.002859,1.064290]` | 0.0002622025 |
| 3 | `[1.000174,1.002155,1.079348]` | 0.0002233074 | `[1.000174,1.002155,1.099348]` | **0.0001753156** | `[1.000174,1.002155,1.104504]` | **0.0001652826** |
| 4 | `[1.000140,1.001612,1.109348]` | 0.0001466860 | `[1.000132,1.001618,1.130609]` | 0.0001181152 | `[1.000141,1.001625,1.134431]` | 0.0001178808 |
| 5 | `[1.000111,1.001220,1.138267]` | 0.0001009195 | `[1.000099,1.001213,1.153942]` | 0.0000781305 | `[1.000113,1.001235,1.156829]` | 0.0000769230 |

All three arms improved monotonically.  Step=0.04 and 0.05 both reached the
endpoint in repetition 3; step=0.03 required repetition 4.

| Cap | Repetition reached | Simulated task time | Loss at reach |
|---:|---:|---:|---:|
| 0.03 | 4 | 35.130 s | 0.0001466860 |
| 0.04 | 3 | 26.735 s | 0.0001753156 |
| 0.05 | 3 | 25.975 s | 0.0001652826 |

At the shared repetition-3 endpoint, 0.05 was 5.72% lower than 0.04.  This did
not meet the frozen 10% additional-benefit criterion.  The 0.760 s secondary
time difference likewise did not change the repetition count.

## Requested versus actual alpha_D steps

No alpha_M or alpha_K transition hit any cap.

| Rep | 0.03 requested / actual | 0.04 requested / actual | 0.05 requested / actual |
|---:|---|---|---|
| 1 | 0.04494 / **0.03000 capped** | 0.04494 / **0.04000 capped** | 0.04494 / 0.04494 |
| 2 | 0.04395 / **0.03000 capped** | 0.04145 / **0.04000 capped** | 0.04021 / 0.04021 |
| 3 | 0.03659 / **0.03000 capped** | 0.03126 / 0.03126 | 0.02993 / 0.02993 |
| 4 | 0.02892 / 0.02892 | 0.02333 / 0.02333 | 0.02240 / 0.02240 |
| 5 | 0.02161 / 0.02161 | 0.01754 / 0.01754 | 0.01685 / 0.01685 |

Cap binding counts `[M,K,D]` were `[0,0,3]`, `[0,0,2]`, and `[0,0,0]`.
Therefore 0.05 was effectively uncapped for all observed qualified updates.

## Evidence and stability

- Every arm produced five qualified successors at the frozen first 8-block
  causal look; every qualification upper bound was below zero.
- Repetitions 2–5 in every arm produced post-update POSITIVE evidence at the
  first 8-block look.
- No NEUTRAL or NEGATIVE evidence occurred.
- Rep-5 `theta_6` was qualified/queued but not activated in this five-repeat
  study, so it has no post-activation evidence.
- alpha_D remained monotone positive in every arm.
- alpha_M and alpha_K each had one small direction reversal in every arm, with
  no repeated oscillation.
- No arm showed parameter oscillation or loss reversal.

## Closed-loop comparison

| Metric | Step 0.03 | Step 0.04 | Step 0.05 |
|---|---:|---:|---:|
| COMPLETE | 5/5 | 5/5 | 5/5 |
| Total task time | 43.535 s | 42.960 s | 42.210 s |
| Peak physical force | 113.045 N | 114.704 N | 113.810 N |
| Sum force integrals | 4089.414 N s | 4039.927 N s | 3967.958 N s |
| Peak moment | 15.265 Nm | 15.296 Nm | 15.302 Nm |
| Peak estimated velocity q1/q2 | 6.374 / 11.881 | 6.324 / 12.282 | 6.432 / 12.491 deg/s |
| Peak truth velocity q1/q2 | 6.418 / 11.775 | 6.326 / 12.253 | 6.426 / 12.485 deg/s |
| Peak deployable acceleration q1/q2 | 173.472 / 472.880 | 180.368 / 481.708 | 173.592 / 473.270 deg/s^2 |
| Peak truth acceleration q1/q2 | 160.025 / 473.129 | 160.049 / 473.220 | 160.061 / 473.265 deg/s^2 |
| NO_SAFE_ACTION / gate / BRAKE | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Safety Filter intervention / warnings | 0 / 0 | 0 / 0 | 0 / 0 |

All arms remained inside the registered motion, force, and moment envelopes.
Matched regression-reason lists were empty for every 0.04/0.05 repetition.

## Runtime

| Metric | Step 0.03 | Step 0.04 | Step 0.05 |
|---|---:|---:|---:|
| MPC solves | 1992 | 1972 | 1927 |
| Weighted mean | 18.888 ms | 18.739 ms | 18.776 ms |
| Worst repetition p95 | 19.461 ms | 19.210 ms | 19.348 ms |
| Maximum | 47.002 ms | 50.010 ms | 48.227 ms |
| >20 ms | 17 | 7 | 19 |

Representative p95 remained below 20 ms, but deadline misses remain and this
does not establish WCET or hard-real-time execution.

## Conclusion

**0.04 gives the best speed/stability tradeoff.**

- Both 0.04 and 0.05 materially improved over 0.03 by reaching the frozen
  endpoint one repetition earlier.
- 0.05 was fully uncapped and remained acceptable, but it did not reduce the
  repetition count relative to 0.04.
- Its 5.72% lower repetition-3 loss did not meet the frozen 10% criterion for
  additional justified benefit.
- Both larger caps had stable parameters, POSITIVE evidence, and acceptable
  closed-loop behavior; parsimony therefore selects 0.04.

This conclusion is limited to the simulated damping +20%, fixed nominal
interface, fixed gamma condition.  Acceleration semantics remain unresolved;
there is no hardware-safety, WCET, simultaneous-interface-adaptation, or
value/RL claim.
