# Stage-4 statistical L4 diagnosis

This artifact is an offline, non-default replay. It changes no production
estimator, controller, allocator, pacing, plant, trajectory, or safety setting.
Oracle quantities are attached only after each causal online-style decision.

## Pre-registered primary rule

- Validation unit: one clean, non-overlapping 0.5 s integral block.
- Embargo: one complete integral window (0.5 s) after candidate fitting.
- Looks: 8, 12, and 16 clean blocks only.
- Paired losses: candidate minus population prior, and candidate minus the
  last-valid model frozen when the candidate was created.
- Dependence correction: Newey-West/HAC block-mean standard error with lag 2
  and a one-sided Student-t upper confidence bound.
- Multiple testing: rollout-level familywise alpha 0.05, Bonferroni allocated
  across 48 possible candidates, two references, and three looks. Thus each
  upper bound uses alpha 0.000173611 (99.982639% one-sided confidence).
- Promotion: both upper bounds must be strictly below zero and the constrained
  Human model must remain positive definite. Otherwise the candidate remains
  pending until another scheduled look, or is rejected at 16 blocks.
- Evidence and all raw training data are retained after non-promotion. A
  candidate whose frozen last-valid reference is replaced is recorded as
  superseded, not silently deleted or counted as statistical rejection.

## Primary replay

| case | promoted / statistical reject / superseded / pending | first promotion time / phase | longest no-promotion |
|---|---:|---:|---:|
| ideal 200 Hz | 2 / 0 / 26 / 8 | 10.88 s / 0.473 | 10.88 s |
| random noise 200 Hz | 1 / 0 / 25 / 10 | 17.90 s / 0.778 | 17.90 s |
| F/T bias + drift 200 Hz | 1 / 0 / 25 / 10 | 17.90 s / 0.778 | 17.90 s |
| bias + delay 200 Hz | 0 / 0 / 0 / 16 | none | 13.31 s |
| combined delay/ZOH 100 Hz | 0 / 0 / 0 / 18 | none | 12.79 s |

At the first successful look, the paired mean/UCB losses against both frozen
references were -0.604/-0.347 Nms^2 for ideal, -0.676/-0.211 Nms^2 for noise,
and -0.835/-0.193 Nms^2 for bias+drift. The second ideal promotion had UCBs
-0.078 and -0.091 Nms^2 against prior and last-valid respectively.

All 142 L3 candidates were full rank (ordinary and RRQR rank 11) and all had at
least one active physical bound, so their parameter status was consistently
`identified_boundary_pressured`; an active bound reduced parameter confidence
but was not an automatic L4 model veto.

## Sensitivity and oracle diagnosis

The pre-declared lag-3 HAC setting with 12/16/20 blocks delayed first promotion
to 17.40 s (ideal) and 20.88 s (noise and bias+drift), while delay/ZOH cases
still had no promotion. The circular moving-block bootstrap (block length 2,
40,000 replicates) reproduced the primary decision counts and times. The
small number of independent blocks still limits bootstrap tail resolution.

No promoted model worsened post-decision oracle generalized-torque prediction.
Full-trace oracle error changed 4.325->3.641 Nm (ideal), 4.430->4.143 Nm
(noise), and 4.430->4.119 Nm (bias+drift). In bias+drift, beta truth distance
worsened 0.460->0.470 while oracle torque prediction improved by 0.326 Nm:
this is parameter compensation, but not measurement-only improvement at the
audited control output. Delay/ZOH traces made no promotion, so this replay did
not reward timing compensation; it also did not accumulate enough clean future
blocks to statistically assess those candidates.

Selection remains inefficient: across cases, four promoted candidates had
median post-decision oracle improvement 0.311 Nm and median true-beta distance
0.460, while 76 oracle-auditable superseded candidates had 0.412 Nm and 0.417.
Most superseded candidates had fewer than eight clean blocks when the reference
changed, so these are not statistically rejected counterexamples. They show a
chronological candidate-retirement bias: earliest supported evidence wins, not
necessarily the best later control model.

## Recommendation

The paired HAC rule with rollout-level multiplicity control is the recommended
statistical evidence test. It is not yet recommended as production default.
Before final closed-loop revalidation, the candidate lifecycle should be
pre-registered so a last-valid promotion does not turn still-informative
provisional candidates into an order-dependent terminal class (for example, a
single causal provisional queue or a multiplicity-accounted rebase rule).
That lifecycle choice must be made without oracle tuning. Until then, the
subsystem is mechanically testable but not ready for the claimed final
closed-loop trust revalidation.
