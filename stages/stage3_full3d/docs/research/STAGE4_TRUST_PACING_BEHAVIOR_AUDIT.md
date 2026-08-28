# Stage-4 Trust and Pacing Behavior Audit

Status: **read-only scientific audit of `formal_user_run_unreviewed` evidence**.
No formal rollout was rerun. No controller, estimator, trust, pacing, sensor,
trajectory, safety, bound, or MPC setting was changed. The canonical result
files under `results/stage4_patient_mismatch_robustness_formal/` were not
modified.

## Audit scope and evidence

This audit reads the preregistration, aggregate summary, per-arm JSON files,
and all paired NPZ traces. It also checks the current implementations of the
measurement boundary, accumulated integral identifier, online single-
challenger trust lifecycle, statistical L4 decision, and confidence-aware
reference clock.

The causal implementation relevant to this audit is:

1. The confidence-aware reference starts at speed scale `0.5`.
2. Pacing uses validity of the **retained** geometry and dynamics models. It
   does not use candidate acceptance, information confidence, oracle beta
   distance, or oracle prediction error.
3. The dynamics model is not marked trustworthy until a challenger qualifies.
   This occurs in both arms. In `prior_only`, qualification retains the
   population prior; in `trusted_adaptive`, it also applies the proposed model.
4. Once both retained models are valid, raw model confidence becomes one. A
   0.75 s low-pass filter must cross the `0.75` enter threshold; the observed
   delay from first qualification to high confidence is about 1.021 s.
5. Speed then ramps from `0.5` to `1.0` at `0.25/s`, taking 2.0 s. Rejected
   later candidates do not invalidate the retained model or slow the reference.

This separation is important: statistical trust decides whether a proposed
control-effective model predicts future **measured integral targets** better;
pacing asks only whether a retained model has passed the frozen validity
lifecycle.

## 1. Nominal promotion

### Observed causal chain

The nominal Human beta exactly equals the population-prior beta. The prior-only
God-view control-model prediction RMSE is therefore exactly `0.0 Nm` in this
simulation. Nevertheless, the estimator does not observe clean Human state or
clean generalized torque. It receives the registered
`noise_bias_drift_200hz` measurement stream:

- force noise `0.5 N`, fixed bias `[1.5, -1.0, 0.8] N`, and drift
  `[0.04, -0.03, 0.02] N/s`;
- moment noise `0.02 Nm`, fixed bias `[0.03, -0.02, 0.015] Nm`, and drift
  `[0.001, -0.0008, 0.0006] Nm/s`;
- pose/orientation noise, causal 8 Hz low-pass preprocessing, and a 0.12 s
  causal derivative window.

In the nominal saved run, the measured-vs-clean diagnostics were:

| diagnostic | observed value |
|---|---:|
| force-vector measurement error RMS | 1.9833 N |
| moment-vector measurement error RMS | 0.1977 Nm |
| hip/knee state-estimation RMSE | 0.2443 / 0.5360 deg |
| hip/knee acceleration-estimation RMSE | 1.0177 / 1.6390 rad/s² |

The measured wrench is mapped through the estimated geometry/state into the
generalized-input target used by the integral regression. Consequently, even
with an exact true prior, the regression target contains systematic sensor,
preprocessing, and reconstruction effects that the 11-base beta can absorb.

The adaptive-arm nominal challenger sequence was:

| challenger | fit / decision (s) | training RMS old→candidate (Nms) | active bounds | statistical result | post-decision God-view prediction |
|---:|---:|---:|---:|---|---|
| 0 | 4.72 / 13.24 | 0.0929→0.0321 | 6 | rejected at 16 blocks | prior 0.0000, challenger 0.1469 Nm |
| 1 | 13.24 / 17.74 | 0.3853→0.0621 | 4 | qualified at first 8-block look | prior 0.0000, challenger 0.1098 Nm |
| 2 | 17.74 / 28.24 | 0.3606→0.0737 | 3 | rejected at 16 blocks | incumbent 0.1104, challenger 0.1842 Nm |
| 3 | 28.24 / trace end | 0.3475→0.1273 | 2 | pending | unavailable |

For challenger 1, the eight clean, embargoed future blocks gave paired
candidate-minus-prior MSE mean `-0.01910 Nms²` with registered HAC bounds
`[-0.02677, -0.01142]`. Both upper bounds against the population prior and
fixed incumbent were below zero, so L4 promoted it exactly according to the
preregistered rule. Oracle beta distance and clean prediction error were
appended only after this decision and did not enter it.

The promoted proposal was a smoothed, bounded step rather than the raw least-
squares candidate. The underlying fit was strongly boundary pressured: four
parameters were at a bound, and the unconstrained `rho1` violation alone was
10.50 estimator spans. The bounds therefore materially shaped and limited the
compensating proposal, but they did not manufacture the held-out improvement:
the bounded proposal itself produced the negative future-block loss difference
used for promotion.

After application, nominal full-task control-model God-view prediction RMSE
changed from `0.0000` to `0.0710 Nm`. Tracking RMSE changed from `0.4331` to
`0.4249 deg`. Thus the promoted model was better for the registered measured
integral-prediction criterion and slightly better for closed-loop tracking, but
worse as a clean true-dynamics predictor.

### Best explanation

The best-supported explanation is **control-effective compensation for the
noisy, biased, drifting measurement/reconstruction channel**, with estimator
bound effects shaping the compensation. It is not evidence of true nominal
Human parameter mismatch. A finite-sample false promotion cannot be ruled out
from one seed, and the registered familywise error is nonzero, but this was not
a marginal decision: the first-look HAC upper bound was clearly below zero and
the same model reduced training residual substantially. The known deterministic
bias/drift and the clean-oracle degradation make pure sampling fluctuation a
less complete explanation.

This is scientifically acceptable if beta is interpreted as a
**control-effective measured-domain model**. It would be a problem only if the
promotion were claimed to identify physical patient parameters or to improve
clean plant-model truth.

## 2. Why exactly three references are incomplete

The three incomplete cases share one event sequence:

1. The first challenger is rejected only after the maximum 16 validation
   blocks, at about 13.2 s.
2. A second challenger is then fit immediately, but must still wait through the
   frozen 0.5 s embargo and eight 0.5 s validation blocks.
3. The second challenger qualifies at about 17.7 s.
4. Filter/hysteresis keeps the speed at `0.5` until about 18.7–18.8 s.
5. The 2 s recovery ramp reaches nominal speed at about 20.7–20.8 s.

The resulting pacing is compared with three completed controls below. Durations
are integrated from the 1 kHz saved speed traces.

| case | first-challenger outcome | first qualification (s) | high confidence (s) | nominal speed (s) | time at 0.5 / 1.0 (s) | mean speed | final phase / progress |
|---|---|---:|---:|---:|---:|---:|---:|
| nominal_reference | reject at 16 | 17.74 | 18.761 | 20.760 | 18.761 / 11.240 | 0.6913 | 22.12 / 0.9617 |
| stiffness_moderate_plus_20pct | reject at 16 | 17.70 | 18.721 | 20.720 | 18.721 / 11.280 | 0.6919 | 22.14 / 0.9626 |
| damping_moderate_plus_30pct | reject at 16 | 17.76 | 18.781 | 20.780 | 18.781 / 11.220 | 0.6909 | 22.11 / 0.9613 |
| rest_equilibrium_moderate_minus_03deg | qualify at 16 | 13.74 | 14.761 | 16.760 | 14.761 / 15.240 | 0.7538 | 24.12 / 1.0000 |
| mass_mild_plus_05pct | qualify at 8 | 9.66 | 10.681 | 12.680 | 10.681 / 19.320 | 0.8175 | 26.16 / 1.0000 |
| registered_formal_perturbed_anchor | qualify at 8 | 9.72 | 10.741 | 12.740 | 10.741 / 19.260 | 0.8166 | 26.13 / 1.0000 |

The two-second transition duration is effectively constant in every case. Under
this frozen clock, the phase deficit is the time integral of `1-speed_scale`.
For nominal it is `9.88 s`, so a 32 s wall-time window accumulates only
`32 - 9.88 = 22.12 s` of reference phase. The same arithmetic explains the
other two incomplete cases. The completed `rest_equilibrium_minus` control is
important: even a first qualification as late as 13.74 s leaves enough phase
to pass 23 s, whereas the approximately 17.7 s qualifications do not.

For every one of the 13 cases, the following full-trace prior/adaptive maximum
absolute differences are exactly zero:

- combined retained-model confidence;
- filtered model confidence;
- hysteretic execution-confidence state;
- reference speed scale;
- accumulated reference phase.

Therefore incompletion is definitively a shared trust/pacing outcome, not an
effect of applying the adaptive model. Later rejection counts also cannot be
the cause: after the first qualification, the retained model remains valid and
rejected candidates do not reduce speed. Active-bound pressure is ubiquitous
and has no direct pacing input. It can affect whether a challenger predicts
well enough to qualify, but it is neither necessary nor sufficient for
incompletion.

The direct cause is **late first qualification after initial-candidate
rejection**, followed by the intentionally conservative confidence filter,
hysteresis, and recovery ramp.

## 3. Cross-case trust and pacing behavior

The table uses the trusted-adaptive arm for qualification/promotion counts.
In that arm every qualification is applied, so qualification count equals
promotion count. `Bounds` is the maximum active-bound count over a case's
challengers; `violation` is the largest unconstrained violation as a fraction
of estimator span. Minimum speed was `0.5` in every case.

| case | first Q/P (s) | promotions | rejections | max bounds / violation | mean speed | time min / nominal (s) | final progress |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal_reference | 17.74 / 17.74 | 1 | 2 | 6 / 10.50 | 0.6913 | 18.761 / 11.240 | 0.9617 |
| mass_mild_minus_05pct | 8.60 / 8.60 | 2 | 1 | 2 / 3.28 | 0.8341 | 9.621 / 20.380 | 1.0000 |
| mass_mild_plus_05pct | 9.66 / 9.66 | 3 | 1 | 3 / 3.08 | 0.8175 | 10.681 / 19.320 | 1.0000 |
| stiffness_moderate_minus_20pct | 9.28 / 9.28 | 3 | 1 | 4 / 3.41 | 0.8234 | 10.301 / 19.700 | 1.0000 |
| stiffness_moderate_plus_20pct | 17.70 / 17.70 | 2 | 2 | 5 / 13.62 | 0.6919 | 18.721 / 11.280 | 0.9626 |
| damping_moderate_minus_30pct | 9.20 / 9.20 | 1 | 1 | 3 / 2.46 | 0.8247 | 10.221 / 19.780 | 1.0000 |
| damping_moderate_plus_30pct | 17.76 / 17.76 | 1 | 2 | 5 / 4.40 | 0.6909 | 18.781 / 11.220 | 0.9613 |
| rest_equilibrium_moderate_minus_03deg | 13.74 / 13.74 | 2 | 1 | 4 / 13.78 | 0.7538 | 14.761 / 15.240 | 1.0000 |
| rest_equilibrium_moderate_plus_03deg | 8.60 / 8.60 | 2 | 1 | 5 / 1.67 | 0.8341 | 9.621 / 20.380 | 1.0000 |
| registered_stage2_mild_anchor | 9.82 / 9.82 | 3 | 1 | 4 / 3.44 | 0.8150 | 10.841 / 19.160 | 1.0000 |
| registered_moderate_anchor | 10.02 / 10.02 | 4 | 0 | 4 / 2.50 | 0.8119 | 11.041 / 18.960 | 1.0000 |
| registered_formal_perturbed_anchor | 9.72 / 9.72 | 4 | 0 | 4 / 3.13 | 0.8166 | 10.741 / 19.260 | 1.0000 |
| registered_stage2_adverse_anchor | 10.28 / 10.28 | 4 | 0 | 3 / 3.45 | 0.8078 | 11.301 / 18.700 | 1.0000 |

Observed relationships:

- First qualification almost completely determines mean speed, accumulated
  phase, and completion because the post-qualification filter and ramp are
  fixed. The three incomplete cases are exactly the three first-challenger
  rejections in the suite.
- Total rejection count is a misleading pacing predictor. Several completed
  cases have a later rejection; such a rejection does not invalidate the
  current model. Only rejection before the first qualification delays the
  initial speed unlock.
- Mismatch magnitude or geometry does not explain completion. For example, the
  larger formal geometry anchor qualifies at 9.72 s and completes, while the
  nominal case qualifies at 17.74 s and does not.
- Prediction benefit does not drive trust confidence. The +20% stiffness case
  improves prediction by 15.46% yet unlocks late; both damping directions have
  similar small tracking changes, but only +30% damping rejects the first
  challenger and becomes incomplete.
- Tracking benefit also does not drive pacing. Trust evaluates future measured
  integral prediction, not closed-loop tracking or God-view metrics.
- All cases have boundary-pressured candidates. High pressure occurs in both
  completed and incomplete cases, so it is a model/identification limitation,
  not a standalone completion explanation.
- Once first qualification occurs, raw retained-model confidence stays high;
  neither information-confidence fluctuations nor later candidate rejections
  create repeated slowdown episodes in these traces.

## 4. Scientific interpretation

### Is nominal promotion a scientific problem?

Not as a control-effective adaptation under the registered measurement model.
The trust rule did what it claims: it selected a bounded model that predicted
future measured integral targets better. The promotion is a warning against a
stronger claim. It demonstrates that the 11-base estimate absorbs sensor bias,
drift, preprocessing, and state/wrench reconstruction error; it is not physical
patient-parameter truth, and it can worsen clean oracle prediction even while
slightly improving tracking.

### Is three-case incompletion a pacing weakness or expected conservatism?

It is expected under the frozen semantics, but it exposes a specific
over-conservative cold-start design limitation: even a physically valid and,
in the nominal case, exactly correct population prior remains at minimum speed
until some replacement challenger qualifies. The implementation therefore
couples “no statistically qualified challenger yet” to “retained dynamics not
trusted for nominal pacing.” This is not an A/B fairness error, and no safety
event occurred, but it matters for short-task completion and future operational
claims.

### Is the trust lifecycle logically incorrect?

No evidence indicates a lifecycle error. The saved evidence shows one active
challenger, a fixed incumbent reference, causal training/embargo/validation,
registered 8/12/16 looks, anytime alpha spending, no oracle use, no race or
supersession, and preservation of the retained model after rejection. The
nominal promotion is a criterion/scope issue, not a causal-logic violation.

### Is redesign required before further robustness work?

No redesign is required to continue scientific robustness work under this
frozen contract. Trust and pacing should remain frozen so new evidence remains
comparable. The current results do not justify a parameter or threshold change.

Before making task-completion, physical-identification, or deployment claims,
the measurement-compensation and cold-start pacing semantics should be tested
in a separate preregistered study. Any later change to incumbent-confidence
semantics would define a new controller/execution version and must not be folded
back into these results.

## Recommended next scientific step

Preregister a **nominal sensor-mechanism decomposition** using the existing
sensor ladder and otherwise frozen controller/trust/pacing implementation:
ideal measurements, noise-only measurements, and the current
noise+bias+drift measurements. The question should be whether promotion,
boundary pressure, clean-oracle degradation, first-qualification timing, and
reference completion appear only after bias/drift is introduced. This directly
tests the leading causal explanation without retuning thresholds or rerunning
the 13-case robustness suite.
