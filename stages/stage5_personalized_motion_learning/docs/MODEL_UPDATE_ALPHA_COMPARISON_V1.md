# Stage-5 Model-Update-Alpha Comparison v1

Status: **formal matched longitudinal execution complete**.

Decision: **AS-A — ALPHA 0.25 IMPROVES PERSONALIZATION SPEED**.

This controlled comparison changed only `model_update_alpha`: Arm A used 0.10
and Arm B used 0.25.  Both arms were run fresh for five matched repetitions
from the same supported `theta_1`, with damping +20%, fixed gamma 0.5, the
same seeds, the same 0.03 per-scale cap, and all other registered control,
evidence, task, interface, motion, and safety semantics frozen.

Formal result artifact:
`results/model_update_alpha_comparison_v1_formal_attempt_01/model_update_alpha_comparison_results.json`
(SHA-256 `43abe83c0b4509e38f542b4a83fcc14e78798971d646cd4759d8c088c09c0899`).

## Frozen contract and provenance

- NAT-A checkpoint: `a0a69595a66672971a6f8f2e17572f33df328bd2`.
- Contract SHA-256:
  `60e0ce49048dc98e33c2efb6b44475d6fb530bde3f5fff0ffe881c87c26468b3`.
- Human evaluation-only truth: `[1.0, 1.0, 1.2]`; unavailable to fitting,
  candidate generation, validation, authority, or control.
- Initial active model:
  `[1.0000584390985465, 1.0010424686528112, 1.0193479803467633]`.
- Seeds: `20260828, 20260829, 20260830, 20260831, 20260832`.
- `maximum_per_scale_step=0.03`, bounds `[0.5,1.5]`, regularization `1e-3`.
- One active model per repetition; at most one queued successor; activation
  only at the next repetition boundary; another update requires post-update
  POSITIVE evidence.
- Explicit native prefix backend with unchanged 5/10/15/20 ms screens and
  0.25 ms physical recurrence.
- Acceleration monitor remains A-MONITOR-UNRESOLVED and unchanged.

The previously saved PP2-A baseline passed the reuse audit, but the user
explicitly authorized and requested both arms fresh.  The fresh alpha=0.10
numeric traces reproduced PP2-A within `5.87e-14`; the only unequal trace
field was the intentionally new model-version string.

## Model evolution and prediction loss

| Rep | Arm A active theta `[M,K,D]` | Arm A loss | Arm B active theta `[M,K,D]` | Arm B loss |
|---:|---|---:|---|---:|
| 1 | `[1.00005844, 1.00104247, 1.01934798]` | 0.0003829484345 | `[1.00005844, 1.00104247, 1.01934798]` | 0.0003829484345 |
| 2 | `[1.00012036, 1.00176913, 1.03732463]` | 0.0003033732258 | `[1.00021325, 1.00285913, 1.04934798]` | 0.0002921060870 |
| 3 | `[1.00011407, 1.00159658, 1.05610706]` | 0.0002771243922 | `[1.00017428, 1.00215524, 1.07934798]` | 0.0002233074201 |
| 4 | `[1.00010450, 1.00144239, 1.07289074]` | 0.0002324261683 | `[1.00013984, 1.00161178, 1.10934798]` | **0.0001466860337** |
| 5 | `[1.00009456, 1.00130241, 1.08799431]` | **0.0002151812421** | `[1.00011135, 1.00122031, 1.13826658]` | **0.0001009195192** |

At equal applied-transition count, Arm B had lower deployable prediction loss
after every nontrivial transition: 3.71%, 19.42%, 36.89%, and 53.10% lower at
repetitions 2 through 5 respectively.  Both arms' losses improved monotonically.

The frozen endpoint was `0.00021518124214580563 Nms^2`:

| Arm | Repetition reached | Cumulative simulated task time |
|---|---:|---:|
| alpha=0.10 | 5 | 44.210 s |
| alpha=0.25 | 4 | 35.130 s |

Arm B reached it one repetition and 9.080 simulated task seconds earlier
(20.54% less accumulated task time).

## Bounded transitions and cap binding

Each row is the successor queued at the end of that repetition.  The Rep-5
successor is `theta_6` and was qualified but not activated within this study.

| Arm/Rep | Actual delta `[M,K,D]` | Cap `[M,K,D]` |
|---|---|---|
| A/1 | `[+0.00006192,+0.00072667,+0.01797665]` | `[N,N,N]` |
| A/2 | `[-0.00000630,-0.00017256,+0.01878243]` | `[N,N,N]` |
| A/3 | `[-0.00000957,-0.00015418,+0.01678368]` | `[N,N,N]` |
| A/4 | `[-0.00000994,-0.00013999,+0.01510356]` | `[N,N,N]` |
| A/5 | `[-0.00000926,-0.00012647,+0.01365410]` | `[N,N,N]` |
| B/1 | `[+0.00015481,+0.00181666,+0.03000000]` | `[N,N,Y]` |
| B/2 | `[-0.00003897,-0.00070389,+0.03000000]` | `[N,N,Y]` |
| B/3 | `[-0.00003444,-0.00054346,+0.03000000]` | `[N,N,Y]` |
| B/4 | `[-0.00002849,-0.00039147,+0.02891860]` | `[N,N,N]` |
| B/5 | `[-0.00002634,-0.00029776,+0.02161231]` | `[N,N,N]` |

Arm B's requested alpha_D displacements were 0.04494, 0.04395, 0.03659,
0.02892, and 0.02161.  The cap therefore bound alpha_D in three of five
qualified transitions, including three of the four transitions activated in
the study.  No alpha_M or alpha_K step hit the cap.  For those first three
alpha_D transitions, a still larger `model_update_alpha` would have produced
the same bounded alpha_D successor.

## Evidence authority

- Every arm/repetition produced one challenger and one successor qualified for
  the next repetition using the frozen 8-block causal future-validation look.
  Every qualification upper bound was below zero.
- `theta_1` began with its previously frozen POSITIVE support.
- Repetitions 2–5 in both arms provided post-update POSITIVE evidence for the
  active successor, each at the first registered 8-block look.
- There were no NEUTRAL or NEGATIVE outcomes.
- The Rep-5 queued `theta_6` in each arm has qualification evidence but, by
  design, no post-activation evidence inside a five-repetition study.

## Stability

- alpha_D moved in one consistent positive direction in both arms.
- Neither arm showed oscillation in alpha_M, alpha_K, or alpha_D.
- alpha_M and alpha_K each had one small direction reversal in both arms; this
  was not repeated oscillation.  Arm B's largest deviations remained small
  (alpha_M 1.000213, alpha_K 1.002859).
- Every active Arm-B transition improved the deployable prediction loss.

## Matched closed-loop results

| Metric | alpha=0.10 | alpha=0.25 |
|---|---:|---:|
| COMPLETE | 5/5 | 5/5 |
| Total task time | 44.210 s | 43.535 s |
| Peak physical force | 113.922 N | 113.045 N |
| Sum of per-episode force integrals | 4151.715 N s | 4089.414 N s |
| Peak cuff moment | 14.875 Nm | 15.265 Nm |
| Peak estimated velocity q1/q2 | 6.473 / 11.915 deg/s | 6.374 / 11.881 deg/s |
| Peak truth velocity q1/q2 | 6.417 / 11.838 deg/s | 6.418 / 11.775 deg/s |
| Peak deployable acceleration q1/q2 | 154.984 / 436.987 deg/s^2 | 173.472 / 472.880 deg/s^2 |
| Peak truth acceleration q1/q2 | 155.655 / 462.542 deg/s^2 | 160.025 / 473.129 deg/s^2 |
| SAFE_ACTION | 2037/2037 | 1992/1992 |
| NO_SAFE_ACTION / gate / BRAKE | 0 / 0 / 0 | 0 / 0 / 0 |
| Safety Filter intervention norm | 0 | 0 |
| MuJoCo warnings | 0 | 0 |

Both arms stayed below the registered 300/600 deg/s^2 acceleration limits and
the registered velocity/force/moment envelopes.  Every repetition completed
OUTBOUND, a continuous HOLD, RETURN, and COMPLETE.  No closed-loop regression
criterion was triggered for Arm B.

## Runtime

| Metric | alpha=0.10 | alpha=0.25 |
|---|---:|---:|
| MPC solve count | 2037 | 1992 |
| Weighted mean | 18.817 ms | 18.888 ms |
| Worst per-repetition p95 | 19.273 ms | 19.461 ms |
| Maximum | 57.316 ms | 47.002 ms |
| Solves >20 ms | 15 | 17 |

Both representative p95 values remained below 20 ms, with occasional deadline
misses.  This does not establish WCET or hard real-time execution.

## Decision and next study design

**AS-A — ALPHA 0.25 IMPROVES PERSONALIZATION SPEED.**

The larger alpha reached the fixed deployable-quality endpoint earlier under
identical evidence rules, remained non-oscillatory, improved loss after every
active transition, and introduced no registered closed-loop or safety
regression.

The preregistered frequent-binding rule was met: alpha_D hit the 0.03 cap in
3/5 qualified transitions.  Thus the cap, rather than alpha itself, became the
dominant early alpha_D update-size bottleneck.

Next experiment design only — **not executed**:

- keep `model_update_alpha=0.25` in both arms;
- Arm A keeps max step 0.03;
- Arm B uses one preregistered moderate max step 0.04;
- retain the same Human condition, `theta_1`, seeds, evidence authority,
  repetition-boundary activation, gamma, controller, monitor, and safety
  semantics;
- primary question: whether 0.04 reduces repetitions/time to the same fixed
  deployable-quality endpoint without negative evidence, instability, or
  closed-loop regression.

The proposed 0.04 value is justified by the observed requested alpha_D steps:
it fully admits the third 0.03659 step and partially relaxes the first two
0.04494/0.04395 steps, while remaining a single moderate increment over 0.03.
No step-cap experiment was run in this task.

Follow-up status: the later explicitly authorized `0.03 / 0.04 / 0.05` formal
comparison is documented in `MODEL_UPDATE_MAX_STEP_COMPARISON_V1.md`; it
supports 0.04 as the best speed/stability tradeoff for this condition.

## Scope

This result supports only the simulated damping +20%, fixed-nominal-interface,
fixed-gamma condition.  It does not demonstrate hardware safety, a resolved
acceleration contract, WCET, simultaneous Human/interface adaptation, or
value/RL learning.
