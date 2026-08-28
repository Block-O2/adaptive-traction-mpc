# Stage-4 hierarchical trust diagnosis

## Evidence boundary

This is an offline prototype replay of the five registered sensor-realism
traces. It does not alter the production estimator, controller, parameter
bounds, confidence pacing, allocator, plant, trajectory, or safety settings.
Oracle state and registered beta are evaluated only after each causal
promotion decision. No new closed-loop rollout was run.

The bias/drift and 100 Hz traces were produced by the earlier closed-loop
estimator architecture. Current geometry and 11-base integral estimators are
replayed offline on their saved measurement trajectories.

## Exact four-layer semantics

### L1 measurement validity

Hard rejection is limited to measurement-integrity evidence:

- non-finite data or timestamps;
- non-monotonic/future timestamps;
- sample age beyond the registered latency plus one registered sample period;
- duplicate or stale ZOH samples;
- explicit dropout or sensor-reported saturation;
- the registered 0.12 s preprocessing warm-up.

The saved frontend has no saturation flag or registered hardware F/T range.
Therefore finite wrench magnitude is not used as a rejection test and
saturation availability is reported as false.

### L2 state and geometry validity

Hard rejection is limited to non-finite reconstruction, invalid SO(3)/geometry
bases at a 1e-6 numerical tolerance, or a rank-deficient two-column state
reconstruction Jacobian. Pose/twist closure errors are recorded but are not
hard gates, because poor fit is an estimator outcome rather than proof of bad
measurement integrity.

### L3 identification quality

Every finite constrained candidate is retained with SVD rank, RRQR rank,
condition number, integral residual, active bounds, unconstrained normalized
bound pressure, residual-scaled parameter covariance indicators, and maximum
correlation. Status is one of `identified_interior`,
`identified_boundary_pressured`, or `weakly_identified`. L3 does not promote or
reject a control model.

All 142 candidates are full SVD/RRQR rank and below the unchanged 1e5 condition
gate, but every candidate is boundary-pressured. Median condition numbers range
from 425 (ideal) to 3497 (100 Hz); median maximum unconstrained violations range
from 0.565 to 2.419 parameter spans. Thus parameter-identification confidence
is low even where control prediction is useful.

### L4 control-model validity

A candidate does not alter the retained model while validation is pending. The
candidate is first passed through the unchanged estimator application rule
(alpha 0.10 smoothing and 3% span step cap). The resulting proposed control
model is promoted only if it remains physically positive definite and has
strictly lower summed held-out integral MSE than both the population prior and
the current last-valid model. Parameter distance to either reference is never
used. Failed candidates and their data remain recorded; the controller-facing
fallback remains prior or last-valid.

## Causal held-out design

- Fit end: the time of the cumulative integral candidate.
- Embargo: one complete 0.5 s integral window.
- Validation: the first two subsequent clean 0.5 s grid windows.
- Minimum decision delay: 1.5 s; contaminated windows are skipped, extending
  the delay rather than causing a model rejection.
- Training and validation share no raw time sample; adjacent validation windows
  may share their zero-measure boundary endpoint.
- Oracle information does not participate in window selection, loss, or
  promotion.

The current prototype uses strict point improvement without a statistical
margin. This is suitable for diagnosing the architecture, not for production
promotion.

## Offline results

| case | L1 valid/invalid | candidates | promoted/unpromoted/pending | first promotion s | full-trace oracle prior to final Nm | beta truth distance prior to final |
|---|---:|---:|---:|---:|---:|---:|
| ideal 200 Hz | 1149/1 | 36 | 29/0/7 | 6.88 | 4.325 to 0.301 | 0.460 to 0.439 |
| noise 200 Hz | 1144/6 | 36 | 16/14/6 | 6.88 | 4.430 to 1.006 | 0.460 to 0.437 |
| bias and drift 200 Hz | 1144/6 | 36 | 22/8/6 | 6.88 | 4.430 to 0.968 | 0.460 to 0.693 |
| bias and delay 200 Hz | 660/7 | 16 | 5/0/11 | 6.85 | 5.408 to 3.720 | 0.460 to 0.504 |
| combined 100 Hz | 634/7 | 18 | 12/0/6 | 7.33 | 5.145 to 2.667 | 0.460 to 0.466 |

L2 rejects zero samples in all cases. Its largest pose/velocity closure errors
increase from 0.94 mm/0.0011 m/s in ideal sensing to 8.56 mm/0.0208 m/s in the
100 Hz combined case, but remain diagnostic rather than outcome-based gates.

## Selection-bias audit

Across all cases, 106 candidates have complete validation: 84 are promoted and
22 are valid but unpromoted. The promoted group has median phase-matched oracle
improvement of 0.221 Nm relative to its own last-valid reference; the
unpromoted group has 0.0107 Nm. The cross-pair probability that an unpromoted
candidate has greater phase-matched oracle improvement is 0.0628.

Only noise and bias/drift contain both decision groups. Their corresponding
probabilities are 0.0446 and 0.227. Active-bound frequency is 100% in both
promoted and unpromoted groups, so numerical bound proximity does not drive
the L4 split.

Absolute oracle errors are lower in the unpromoted group because those
candidates occur predominantly in easier late phases. The phase-matched
comparison removes that trajectory-difficulty confound. On the available
control-prediction evidence, the rule does not preferentially reject candidates
with larger local oracle improvement.

Parameter truth tells a more nuanced story. Across all cross pairs, the
probability that an unpromoted candidate is closer to true beta is 0.460, so
there is no aggregate systematic advantage. In the noise case alone it is
0.915, whereas in bias/drift it is 0.267. This disagreement is expected under
control-equivalent parameter compensation and supports keeping parameter-ID
status separate from control-model validity.

The bias/drift final beta moves away from truth (0.460 to 0.693 span-normalized
L2) while retrospective full-trace oracle control prediction improves (4.430
to 0.968 Nm). This is a compensated control model, not an accurate physical
parameter estimate.

## Starvation and conservatism

- No failed promotion discards its training measurements or candidate record.
- Valid raw data continue accumulating to 1149/1144 samples in completed 200 Hz
  traces and 660/634 in early-terminated delay traces.
- First promotion occurs at 6.85 to 7.33 s.
- Thirty-six late candidates remain pending because the saved trace ends before
  two future clean validation windows are available; delay cases contribute 17
  of them and both saved delay rollouts terminate early.
- Of the 106 candidates with complete validation, 79.2% are promoted. All
  evaluable ideal, delayed-200-Hz, and combined-100-Hz candidates promote.

The prototype is therefore not data-starved or excessively conservative. Its
point-improvement rule is instead too permissive for production use.

## Recommended production rule

Keep the hard L1/L2 semantics and the separate L3 parameter status. Replace the
prototype L4 point comparison with a pre-registered paired predictive-evidence
rule over clean, embargoed integral blocks: require a one-sided uncertainty
bound on candidate-minus-reference loss to favor the candidate against both
population prior and current last-valid. Set its confidence level and required
block count from statistical design and registered sensor specifications, not
oracle outcomes. Do not use parameter distance to prior, bound proximity, or
oracle data in promotion.

Retain every failed candidate as negative evidence, continue accumulating its
underlying data, and apply the unchanged smoothing/step limit only after model
promotion. Report parameter-identification status and control-model status as
independent outputs.

The 11-base estimator formulation can remain unchanged, but the trust layer is
not ready to become production-default or for final closed-loop revalidation.
The next justified step is to pre-register and mechanically test the paired
L4 uncertainty rule on these saved traces without oracle-based threshold
tuning; only then should a final closed-loop revalidation be authorized.
