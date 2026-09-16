# Stage-5 reduced Human-ID shadow v1

## Decision

**R-C — HUMAN ID NOT USEFUL ENOUGH.** The frozen three-scale representation is
well conditioned once a complete Stage-5 episode is available, and its raw fit
directions are sensible. However, no challenger in the preregistered five-case
matrix passed embargoed future validation, so no reduced model was published
even to the shadow incumbent. Closed-loop Human adaptation and a fixed-versus-
adaptive A/B are therefore not authorized.

This is a small engineering/shadow diagnostic, not formal or authoritative
evidence. The controller used the nominal Human model in every sample. The
interface remained fixed nominal Plant-v1, and no interface ID, terminal value,
RL, truth-assisted trust decision, or change to motion/safety limits occurred.

## Frozen mapping

The implementation reuses `dynamic_scale_projection()` from Stage 4 exactly:

```text
theta_H = [alpha_M, alpha_K, alpha_D]
beta(theta_H) = P(beta_nominal) theta_H

beta[0:5]  = alpha_M beta_nominal[0:5]
beta[5:9]  = alpha_K beta_nominal[5:9]
beta[9:11] = alpha_D beta_nominal[9:11]
```

The mass block contains the five inertial/gravity combinations. The passive
block couples `k1`, `k2`, `rho1=k1*q_rest1`, and `rho2=k2*q_rest2`; scaling all
four together preserves both nominal rest angles. The last two beta terms are
viscous damping. These are dimensionless control-effective scales, not
anatomical mass, tissue stiffness, or physical damping estimates.

## Preregistered matrix and task outcome

Nominal, mass +8%, and damping +20% reuse the frozen Human-ID v1 traces. Pure
stiffness +15% and the fixed mixed probe are the only new smoke traces.

| Case / truth scale `[M,K,D]` | Trace | Task result | available time | first fit | shadow decisions | retained scale |
|---|---|---|---:|---:|---|---|
| nominal `[1,1,1]` | reused | COMPLETE | 4.935 s | 1.245 s | 1 future reject, 1 pending | `[1,1,1]` |
| mass +8% `[1.08,1,1]` | reused | ABORT, acceleration | 0.270 s | none | no fit | `[1,1,1]` |
| stiffness +15% `[1,1.15,1]` | new | ABORT, acceleration | 1.335 s | 1.245 s | 1 pending | `[1,1,1]` |
| damping +20% `[1,1,1.2]` | reused | COMPLETE | 5.060 s | 1.245 s | 1 future reject, 1 pending | `[1,1,1]` |
| mixed `[1.04,1.10,1.10]` | new | ABORT, acceleration | 0.550 s | none | no fit | `[1,1,1]` |

Every run had zero Safety Filter intervention, BRAKE, 200 N gate event, and
MuJoCo warning. The aborts are preserved consequences of the registered
acceleration envelope; no controller or limit was changed to obtain ID data.

## Data-only identifiability

All values below use the three-scale regression matrix alone. Prior
regularization is excluded from singular values, rank, condition, and
correlation.

| Case | integral blocks | normalized singular values | rank | condition | max correlation |
|---|---:|---|---:|---:|---:|
| nominal | 95 | `[1.1292,0.9999,0.8515]` | 3 | 1.326 | 0.275 |
| mass +8%, pre-abort | 2 | `[1.4191,0.9890,0.0901]` | 3 | 15.746 | 0.992 |
| stiffness +15%, pre-abort | 23 | `[1.4159,0.9232,0.3779]` | 3 | 3.746 | 0.845 |
| damping +20% | 98 | `[1.1360,1.0000,0.8424]` | 3 | 1.349 | 0.290 |
| mixed, pre-abort | 8 | `[1.4059,0.9689,0.2911]` | 3 | 4.829 | 0.913 |

For the two complete episodes, phase-only matrices also remained rank 3. The
nominal OUTBOUND/HOLD/RETURN condition numbers were `1.958/2.386/3.364`; the
damping case values were `2.113/3.680/3.696`. Corresponding maximum
correlations were `0.511/0.574/0.810` and `0.561/0.807/0.835`. Thus no reduced
direction numerically disappears over a complete task, although HOLD and
RETURN alone are less separated than the whole episode.

History length, not the 0.10/0.20/0.40 s integration-window choice, dominates
conditioning. At 1.25 s, nominal/damping condition numbers were `4.212/4.475`
with correlations `0.878/0.889`; whole-episode values improved to about `1.3`
and `0.3`. Across the three tested window lengths the complete-case condition
numbers changed only from `1.324--1.335` nominal and `1.346--1.357` damping.
The early mass trace is numerically rank 3 but practically almost collinear;
full numerical rank is not treated as usable identification.

Regularization sensitivity confirms this distinction. The complete damping
fit stayed near `[0.9999,1.0005,1.2233]` from zero through `1e-2` prior weight.
The two-block mass fit changed from `[1.0798,1.4313,0.9304]` without a prior to
`[1.0798,1.0038,1.0006]` at the declared `1e-3` weight. Regularization therefore
stabilizes weak early directions but is not evidence that those directions are
identified. The fit is bounded convex linear least squares, so numerical
multi-start is inapplicable; incumbent initialization affects only the bounded
smoothed publication step. The integral regression has no fitted latent state.

## Causal prediction and trust outcome

| Case | first raw candidate | training RMSE, nominal→candidate | future result | retained future improvement |
|---|---|---|---|---|
| nominal | `[1.0021,0.9982,1.0102]` | `0.01324→0.00382 Nms` | rejected at 12 blocks; mean loss difference `+1.11e-5 Nms²` | 0% |
| mass +8% | none | unavailable | abort before a fit | 0% |
| stiffness +15% | `[1.0017,1.1532,1.0045]` | `0.05494→0.00194 Nms` | pending when episode aborted | 0% |
| damping +20% | `[1.0015,1.0051,1.2011]` | `0.05105→0.00343 Nms` | rejected: 12-block mean improved, but upper confidence bound remained `+5.98e-5 Nms²` | 0% |
| mixed | none | unavailable | abort before a fit | 0% |

The stiffness and damping raw candidates point in the correct evaluation-only
direction, and the complete-case candidates are insensitive to the tested
regularization range. That is not enough for publication: stiffness never
reached its first future look, while damping's future block improvements were
variable and did not establish the preregistered confidence requirement. The
second nominal and damping challengers remained pending at episode end.

Because every retained model remained nominal, retained-versus-nominal
integrated-torque and Human-state prediction improvements are exactly zero.
For reference, nominal-model one-step/20 ms deployable-state errors were
`0.308/0.380 deg/s` dq RMSE in nominal and `0.725/1.635 deg/s` in damping; their
maximum dq errors were `3.93/3.94` and `3.88/5.71 deg/s`. These use recorded
future deployable generalized inputs for offline evaluation, never truth for
online fitting or trust.

## Adaptation latency and endpoint

The first possible fit is about 1.245 s and a first eight-block decision needs
another 1.8 s including the embargo. Mass +8% supplies only 0.270 s and two
overlapping integral blocks; mixed supplies 0.550 s and eight blocks. Pure
stiffness reaches one fit at 1.245 s but aborts 0.090 s later, before any future
qualification. An identifier cannot correct these mismatches before enough
safe data exist.

The reduced model fixes beta11's pathological whole-episode correlation, but
it does not establish stable causal publication benefit under the current
single-episode task and unchanged safety envelope. Per the frozen decision
rule, the endpoint is **R-C**, not R-A or R-B. No closed-loop A/B is
preregistered. Further estimator invention is not recommended from this
evidence; any future Human-adaptation work would require a separately approved
research question addressing safe pre-task information or repeated-session
evidence without weakening the task constraints.

The previous interface-model limitation remains unresolved for hardware. This
fixed-interface study makes no simultaneous Human/interface uncertainty,
hardware-readiness, anatomical-recovery, or 3--5 repetition personalization
claim.
