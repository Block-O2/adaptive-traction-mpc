# Stage-5 frozen Human-model successor replication v1

## Frozen question and independence audit

This study asks whether the already-qualified bounded successor explains new
post-transition deployable Human dynamics more accurately than its predecessor
without degrading closed-loop behavior.  The pair was frozen before execution:

- `theta_0=[1,1,1]`;
- `theta_1=[1.0000584390985465,1.0010424686528112,1.0193479803467633]`;
- evaluation-only Human truth was `[1,1,1.2]`.

There was no Human-ID fit, refit, second update or truth access online.  Gamma
was exactly 0.5.  Interface, task, Goal-MPC, HOLD, acceleration monitor,
registered limits and safety chain were unchanged.

The original seed `20260824` is deterministic: its matched arms were
bit-for-bit identical through the causal transition (610 samples, zero maximum
difference in time, estimated state, truth q/dq, executed action and physical
wrench).  An exact same-seed rerun therefore was not counted as independent
evidence.  Before inspecting new outcomes, the next three controller-search
seeds were fixed as `20260825`, `20260826`, and `20260827`; 25/26 continue the
existing Stage-5 seed convention and 27 is its consecutive extension.  Each
seeded matched A/B rollout is one top-level replication unit.  Blocks within a
rollout remain correlated and were never pooled as independent replications.

Arm A used `theta_0` throughout.  Arm B used `theta_0` until the first
deployable OUTBOUND sample at or after 3.045 s, then switched once to the
already frozen `theta_1`.  The actual transition was 3.045 s in every Arm B.
The first eligible prediction block began strictly after a 0.2 s embargo.
Within each pair, all audited quantities were exactly equal through transition.

## Prediction evidence

Loss is the existing integral-dynamics deployable-domain loss.  A negative
paired difference means `theta_1` was better.  The unchanged correlated-data
HAC classification is shown honestly; all three are NEUTRAL.

| CEM seed | valid blocks | theta1-favorable | mean loss theta0 | mean loss theta1 | paired mean [Nms2] | descriptive reduction | HAC |
|---:|---:|---:|---:|---:|---:|---:|---|
| 20260825 | 30 | 27 | 3.410866e-4 | 2.965232e-4 | -4.456340e-5 | 13.07% | NEUTRAL |
| 20260826 | 28 | 26 | 3.628657e-4 | 3.181034e-4 | -4.476225e-5 | 12.34% | NEUTRAL |
| 20260827 | 26 | 24 | 4.087232e-4 | 3.578166e-4 | -5.090655e-5 | 12.46% | NEUTRAL |

The top-level sample size is three rollout units, with three favorable and zero
unfavorable rollout means.  This is replication of direction, not a claim that
the block count is an independent sample size or that the HAC test became
positive.

## Phase-wise result

Values are `theta_1 - theta_0` mean loss; negative favors the successor.

| seed | OUTBOUND (fav/total) | HOLD (fav/total) | MIXED (fav/total) | RETURN (fav/total) |
|---:|---:|---:|---:|---:|
| 20260825 | -6.678671e-5 (5/5) | +8.835669e-7 (0/2) | -1.109373e-6 (1/2) | -4.773889e-5 (21/21) |
| 20260826 | -5.854978e-5 (4/4) | +4.846808e-7 (1/2) | -2.927922e-6 (1/2) | -5.071287e-5 (20/20) |
| 20260827 | -9.809567e-5 (2/2) | -5.875607e-7 (1/2) | -1.295265e-5 (1/2) | -5.501493e-5 (20/20) |

OUTBOUND and RETURN repeat the favorable direction in all three rollout units.
HOLD is weak and inconsistent, as expected for damping discrimination near a
static state, but it was retained rather than removed post hoc.

## Matched closed-loop consequence

| seed | arm | status | complete [s] | HOLD enter / RETURN enter [s] | peak F [N] | integral F [Ns] | peak M [Nm] | MPC mean / p95 / max [ms] |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 20260825 | theta0 | COMPLETE | 9.150 | 4.310 / 4.965 | 109.846 | 859.479 | 14.410 | 78.46 / 93.70 / 101.68 |
| 20260825 | theta1 | COMPLETE | 9.435 | 4.295 / 4.910 | 112.989 | 884.793 | 14.410 | 77.45 / 93.59 / 124.66 |
| 20260826 | theta0 | COMPLETE | 8.850 | 4.070 / 4.765 | 110.350 | 834.273 | 14.625 | 79.29 / 93.66 / 117.82 |
| 20260826 | theta1 | COMPLETE | 8.940 | 4.090 / 4.780 | 111.342 | 842.949 | 14.625 | 79.30 / 93.91 / 104.14 |
| 20260827 | theta0 | COMPLETE | 8.915 | 3.805 / 4.530 | 110.216 | 833.953 | 14.657 | 79.13 / 93.84 / 126.47 |
| 20260827 | theta1 | COMPLETE | 8.715 | 3.670 / 4.410 | 110.665 | 813.418 | 14.657 | 79.61 / 93.88 / 121.63 |

| seed | arm | terminal q error [deg] | terminal dq [deg/s] | longest HOLD [s] | peak estimated/truth dq [deg/s] | peak deployable/truth 20 ms qdd [deg/s2] |
|---:|---|---:|---:|---:|---:|---:|
| 20260825 | theta0 | [0.102,-0.171] | [-1.036,0.491] | 0.660 | [5.712,10.954] / [5.733,10.973] | [135.21,329.78] / [130.08,280.87] |
| 20260825 | theta1 | [-0.017,-0.020] | [-0.096,0.500] | 0.620 | [5.522,10.393] / [5.513,10.360] | [134.77,337.64] / [114.10,268.73] |
| 20260826 | theta0 | [0.172,-0.294] | [-1.113,0.490] | 0.700 | [5.819,10.819] / [5.868,10.772] | [158.65,382.09] / [150.85,353.75] |
| 20260826 | theta1 | [0.070,-0.348] | [-1.248,0.441] | 0.695 | [5.894,11.096] / [5.894,10.980] | [136.70,357.20] / [115.10,251.68] |
| 20260827 | theta0 | [0.020,-0.090] | [-0.525,0.498] | 0.590 | [6.008,13.585] / [5.926,13.694] | [165.64,428.69] / [138.61,334.95] |
| 20260827 | theta1 | [-0.024,-0.006] | [-0.021,0.497] | 0.530 | [5.730,10.729] / [5.731,10.694] | [144.09,356.99] / [134.07,353.08] |

All six runs satisfied online and evaluation-only velocity/20 ms acceleration
envelopes.  Every MPC solve returned SAFE_ACTION; counts were 422/438,
405/409, and 407/396 for Arm A/B by seed.  Every run had zero NO_SAFE_ACTION,
force-gate, BRAKE, Safety Filter intervention, structural event and MuJoCo
warning.  Path freedom remained: there is no prescribed q trajectory,
coordination ratio or corridor.  Arm-B completion time changed by +0.285,
+0.090 and -0.200 s; peak force by +3.143, +0.993 and +0.448 N.  These small,
mixed closed-loop differences are descriptive, not a performance benefit.

The measured Goal-MPC runtime was 77.45--79.61 ms mean and 93.59--93.91 ms
p95 for Arm B; every solve missed the 20 ms period.  Runtime remains a separate
deployment blocker and was not optimized.

## Decision

**RPL-A — FROZEN SUCCESSOR REPLICATED.**

All three preregistered rollout means favor the same frozen successor, both
moving phases repeat that direction, and no matched registered violation or
categorical closed-loop degradation appeared.  This between-run evidence is
stronger than the original single rollout even though each unchanged within-run
formal test remains NEUTRAL.  The conclusion is limited to the fixed damping
+20% simulated Human, fixed nominal interface, fixed gamma and current task.
It does not establish anatomical recovery, hardware safety, acceleration-
monitor correctness or a general personalization guarantee.

## Progressive-personalization experiment design (not run)

The smallest next study keeps the same condition, authorities, fixed gamma and
three preregistered seeded replication units.  In each unit it would:

1. collect predeclared causal evidence under the active `theta_k`;
2. qualify exactly one new challenger with the existing fit, embargo and
   future-validation rules, then apply the existing bounded update once;
3. freeze `theta_k+1` and collect a separate, genuinely later embargoed block
   set to test the consequence of that correction;
4. record active-model trust separately from challenger evidence; and
5. keep pacing authority disabled so trust cannot change gamma.

A `theta_1 -> theta_2` transition would be permitted only after predeclared
support for a newly generated bounded candidate; prior RPL-A evidence cannot be
reused as evidence for `theta_2`.  Post-update evidence cannot justify the same
transition retroactively, and blocks/rollouts remain separate analysis levels.
The study is design-only here; no progressive run or second update occurred.

Raw traces remain local/ignored under
`results/human_model_frozen_successor_replication_v1_attempt_01/`.  The compact
tracked result is `HUMAN_MODEL_FROZEN_SUCCESSOR_REPLICATION_V1_SUMMARY.json`.
