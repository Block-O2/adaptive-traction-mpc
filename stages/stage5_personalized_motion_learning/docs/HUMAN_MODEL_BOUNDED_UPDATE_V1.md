# Stage-5 bounded Human-model update v1 — offline audit

## Scope

This audit implements only the offline semantics

`validated direction -> bounded provisional successor -> later model evidence`.

No Human model was changed in Goal-MPC, no rehabilitation episode was run, and
the acceleration monitor, pacing/trust thresholds, interface model, task,
Safety Filter and BRAKE remain unchanged.  Current conclusions EXIT C, R-C,
P-B, A-MONITOR-UNRESOLVED and T-A remain frozen.  The recent 77--79 ms mean MPC
runtime observation also remains an open deployment blocker.

## Historical mechanism audit

### Stage 4

The early windowed NLS used three different parameters
`[mass_scale, stiffness_scale, rest_common_offset]`, smoothing `eta=0.25`, a
5% span maximum step, configured parameter bounds, and a `last_valid_theta`
fallback.  It is useful provenance but is not the representation reused here.

The later accumulated/integral base-dynamics identifier—the mechanism carried
into formal Stage 4—starts from a population prior and retains one `last_valid`
model.  Its frozen dynamic update uses:

- parameter bounds derived as 0.5--1.5 times the prior, with the historical
  stiffness/rest-product treatment for the 11-base-parameter representation;
- smoothing `eta = 0.10`;
- componentwise maximum step `0.03 * (upper-lower)`;
- final clipping to parameter bounds;
- rejected/nonfinite/ill-conditioned/non-positive-definite candidates leave
  `last_valid` unchanged.

The later Stage-4 hierarchical/statistical trust path constructs this bounded
proposal first, validates that proposal on embargoed future integral blocks
against the population prior and retained incumbent, and only then replaces the
retained model.  Thus the historical philosophy is already progressive, not an
unbounded nominal-to-personalized replacement.

### Stage 5 reduced Human ID

The reduced vector is
`theta = [alpha_M, alpha_K, alpha_D]`, with engineering bounds `[0.5,1.5]` for
each component, `eta = 0.10`, and the same 3% span maximum component step.  The
implementation already computes:

1. `candidate_scales`: the raw fitted challenger `theta_c`;
2. `proposed_model_scales`: the bounded/smoothed successor;
3. causal future validation of `proposed_model_scales`, not of the raw
   candidate alone;
4. on qualification, publication of that proposed vector as the retained
   **shadow** incumbent.

Therefore no second update rule was added.  The new
`BoundedHumanModelTransition` API calls the existing
`ReducedIntegralScaleIdentifier.bounded_smoothed_step` and makes predecessor,
candidate, provisional successor, displacement, limiting rule and model
versions explicit.  Historical publications remain shadow-only and were never
applied to Goal-MPC.

## Frozen bounded transition

For each component `i`:

```
raw_i       = theta_c,i - theta_k,i
smooth_i    = 0.10 * raw_i
limited_i   = clip(smooth_i, -0.03*span_i, +0.03*span_i)
theta_k+1,i = clip(theta_k,i + limited_i, lower_i, upper_i)
```

Here every `span_i = 1.0`, so the maximum absolute step is 0.03.  These values
are inherited from the existing Stage-4/Stage-5 identifier contract; they were
not selected from downstream task outcomes.

| saved case | theta_k | theta_c | provisional theta_k+1 | truth, evaluation only | active limiter |
|---|---|---|---|---|---|
| nominal | [1, 1, 1] | [1.000885, 0.999630, 1.007894] | [1.000089, 0.999963, 1.000789] | [1, 1, 1] | eta only |
| damping +20% | [1, 1, 1] | [1.000584, 1.010425, 1.193480] | [1.000058, 1.001042, 1.019348] | [1, 1, 1.2] | eta only |
| stiffness +15% | [1, 1, 1] | [1.000758, 1.146591, 1.012167] | [1.000076, 1.014659, 1.001217] | [1, 1.15, 1] | eta only |

For all three, reconstruction matches the historical
`proposed_model_scales` exactly (maximum absolute difference 0).  Neither the
3% maximum step nor parameter bounds activated.  Predecessor, successor and raw
candidate all retained minimum Human mass-matrix eigenvalues above 0.059 and
were finite valid three-scale models.

## Saved-data comparison

The same deployable estimated `q/dq` and reconstructed generalized Human input
were used for all three models.  Each sample unit is a non-overlapping 0.2 s
integral-dynamics block.  Candidate-qualification blocks start after the
historical fit embargo; post-decision blocks start one additional 0.2 s window
after the qualification decision.  No block used to fit the first candidate is
counted as qualification or post-decision evidence.

### Existing candidate-qualification blocks

All eight blocks were OUTBOUND and were the historical future-validation data
that qualified the bounded proposal.

| case | predecessor RMSE | successor RMSE | full candidate RMSE | successor paired improvement |
|---|---:|---:|---:|---:|
| nominal | 0.005606 Nms | 0.005128 Nms | 0.002238 Nms | +16.33% |
| damping +20% | 0.022351 Nms | 0.019920 Nms | 0.004075 Nms | +20.57% |
| stiffness +15% | 0.057945 Nms | 0.052221 Nms | 0.002965 Nms | +18.78% |

This confirms that the actual bounded successor—not merely the candidate
direction—passed the historical transition qualification.

### Genuinely later post-decision blocks

| case | blocks | predecessor RMSE | successor RMSE | full candidate RMSE | successor change | evidence class |
|---|---:|---:|---:|---:|---:|---|
| nominal | 25 | 0.005226 Nms | 0.005531 Nms | 0.009024 Nms | -12.02% | NEUTRAL, paired bounds cross zero |
| damping +20% | 28 | 0.020137 Nms | 0.018906 Nms | 0.011067 Nms | +11.85% | NEUTRAL, paired bounds cross zero |
| stiffness +15% | 4 | 0.071793 Nms | 0.064763 Nms | 0.004234 Nms | +18.62% | NEUTRAL, fewer than 8 blocks |

For damping, the successor improved mean block MSE by 20.00% in OUTBOUND and
10.74% in RETURN; the two very-low-error HOLD blocks favored the predecessor.
The first 8/10/12-block HAC upper bounds remained positive, so this descriptive
mean benefit is not relabeled statistically POSITIVE.  Stiffness had four
later OUTBOUND blocks, all directionally favorable, but cannot reach the
existing first look.  Nominal improved OUTBOUND but degraded RETURN and the
overall later mean, illustrating why publication-time support must not be
treated as permanent proof of every later model comparison.

Some post-decision blocks later contributed to separate subsequent Human-ID
attempts.  They are independent of the first candidate fit and qualification,
but are not claimed as independent evidence for those later research
questions.

## Evidence semantics

No new percentage threshold or weighted trust score is introduced.  The
existing Stage-5 future-validation configuration is reused: HAC lag 2,
non-overlapping blocks, scheduled looks at 8/10/12 blocks, and the existing
anytime family alpha spending.

- **POSITIVE:** at a scheduled look, the one-sided upper bound of
  `loss(theta_k+1)-loss(theta_k)` is below zero.
- **NEGATIVE:** at a scheduled look, the corresponding lower bound is above
  zero.
- **NEUTRAL:** fewer than eight valid later blocks, or every scheduled interval
  crosses zero.

The saved post-decision classifications are therefore all NEUTRAL.  This is an
expected evidence outcome, not a reason to tune the threshold.

## Sensor and circular-validation boundary

There is no dynamic-scale circularity in these saved targets:

- the interface observer reconstructs Human-side cuff state from deployable
  robot/cuff measurements using the fixed nominal Kelvin-Voigt interface;
- `q_hat/dq_hat` then use fixed kinematic geometry;
- generalized Human input uses the same estimated `q` plus measured cuff
  wrench and geometry;
- `alpha_M/K/D` do not enter any of those reconstruction steps.

The scales enter only the compared Human dynamics prediction.  MuJoCo truth is
not used for fit, transition construction, evidence classification or trust;
truth scales are appended only as evaluation labels.

Positive feedback would mean only that the updated control-effective model
explains later deployable-domain measurements better under this fixed
measurement/interface contract.  It would not establish anatomical parameter
truth, Human-state truth, eliminated interface error, acceleration-monitor
correctness, hardware safety, or closed-loop benefit.

## Transition evidence versus post-update feedback

`validated transition evidence` and `post-update positive feedback` remain
separate:

- before a control change, the bounded successor may be authorized
  provisionally because it beat predecessor/prior on embargoed future blocks;
- only after that successor actually controls the plant can new measurements
  provide genuine post-update feedback for that model version;
- positive feedback may support that version, neutral evidence preserves the
  current evidence without increasing authority, and negative evidence should
  stop further correction and preserve rollback to the predecessor.

This audit neither fully resets successor trust nor transfers all predecessor
trust.  The successor is explicitly `PROVISIONAL`, with transition provenance
but without post-update support.

## Decision and next experiment design

**U-A — BOUNDED UPDATE READY FOR ONE-STEP CLOSED-LOOP A/B.**

The rule is historical and already frozen; all reconstructed successors are
valid and exactly match the historically validated proposals; damping and
stiffness preserve the useful candidate direction on later data; validation is
non-circular; and the existing HAC rule supplies non-arbitrary
positive/neutral/negative semantics.  The current later evidence is NEUTRAL,
so U-A does not assert that any successor is already trusted.

The smallest future experiment should use damping +20%:

- Arm A keeps `theta_k = [1,1,1]` for both repetitions;
- Arm B is identical until the same causal validation event, then applies
  exactly one transition to
  `[1.000058, 1.001042, 1.019348]` and disables further updates;
- both arms use fixed gamma 0.5, the same task, nominal interface, acceleration
  monitor, physical limits, seed/CEM settings, Safety Filter and BRAKE;
- post-transition prediction evidence compares successor and retained rollback
  predecessor on identical new blocks;
- closed-loop completion, force and tracking remain a separate control-
  acceptance outcome and cannot retroactively validate the parameter estimate.

This A/B is design-only here and was not run.
