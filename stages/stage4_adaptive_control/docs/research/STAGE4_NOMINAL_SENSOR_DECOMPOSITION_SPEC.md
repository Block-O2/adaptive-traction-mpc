# Stage-4 Nominal Sensor-Mechanism Decomposition Specification

Status: **preregistered before execution**. This is a narrow formal engineering
experiment under the frozen Stage-4 controller. It does not modify or reinterpret
the completed 13-case patient-mismatch evidence.

## Scientific question

For the exact nominal Human, whose true dynamics and geometry equal the
population prior, is trusted model promotion driven primarily by ideal sensing,
ordinary zero-mean measurement noise through the existing reconstruction path,
or the added systematic bias and drift?

The estimator beta is evaluated both as a predictor of the measured integral-ID
target and as an offline clean simulator-oracle dynamics model. A promotion is
not automatically favorable or unfavorable.

## Preregistered design

The one true plant is `traction_mpc_stage3.human.HUMAN`. Its true 11-base beta
is exactly `nominal_base_parameters(HUMAN)`, the controller population prior.
The initial state, 23 s continuous high-flexion reference, 32 s wall-time
allowance, plant integration, controller, estimator, bounds, trust lifecycle,
confidence pacing, allocator, MPC, safety rules, and all other settings remain
frozen.

Each sensor regime uses measurement seed `44104`; the MPC seed is `20260824`.
The two paired arms are:

- `prior_only`: the trust lifecycle runs causally, but a qualified beta is not
  applied to control;
- `trusted_adaptive`: the same qualified beta enters control at the causal
  promotion time.

The three existing `sensor_realism_cases()` definitions are used verbatim:

| regime | rate / latency | preprocessing | random noise | systematic force bias / drift | systematic moment bias / drift |
|---|---|---|---|---|---|
| `ideal_200hz` | 200 Hz / 0 s | disabled | all standard deviations zero | zero / zero | zero / zero |
| `noise_200hz` | 200 Hz / 0 s | enabled: 8 Hz causal low-pass and 0.120 s derivative window | robot position 0.02 deg, robot velocity 0.10 deg/s, cuff position 0.30 mm, cuff orientation 0.05 deg, force 0.50 N, moment 0.020 Nm | zero / zero | zero / zero |
| `noise_bias_drift_200hz` | 200 Hz / 0 s | same as `noise_200hz` | same as `noise_200hz` | `[1.5, -1.0, 0.8] N` / `[0.04, -0.03, 0.02] N/s` | `[0.03, -0.02, 0.015] Nm` / `[0.001, -0.0008, 0.0006] Nm/s` |

Because preprocessing is disabled in the existing ideal regime and enabled in
the existing noise regimes, `noise_200hz` tests zero-mean noise **plus the
frozen preprocessing/reconstruction path**. This study will not claim to
separate those two components.

The intended formal matrix is exactly three regimes by two arms, for six
rollouts. No parameter may be tuned after observing a result. Scientific
failures are retained; only an integrity failure stops the suite.

## Frozen shared contract

The following remain exactly as recorded at baseline tag `stage4-baseline-v1`,
commit `ef1fe90e61c5981df8e934585780ce188d104ea4`:

- accumulated integral 11-base estimator and existing physical bounds;
- L1/L2/L3 validity semantics and single-incumbent, at-most-one-challenger L4;
- 0.5 s embargo, non-overlapping 0.5 s validation blocks, looks at 8/12/16,
  lag-2 HAC, and existing anytime alpha spending;
- filtered/hysteretic confidence pacing, including all thresholds and rates;
- feasible-first batched CEM MPC, horizon 15, 32 candidates, two iterations,
  six elites, seed 20260824, and the original objective and constraints;
- registered 1:1 cuff-aware allocator, trajectory, measurement routing, plant,
  safety limits, and 32 s runtime allowance;
- no UKF/Kalman, active excitation, hybrid optimization, interaction-aware
  weights, corridor/tube control, new threshold, or hidden fallback.

Selecting one of the three existing sensor cases is the only allowed
across-regime change. Whether a qualified dynamics model is allowed into
control is the only allowed within-regime A/B change.

## Metrics fixed before execution

For each arm and regime, report:

- whether promotion occurs, first qualification and first promotion time,
  promotion count, rejection count, and challenger status;
- candidate active-bound count and unconstrained bound-pressure diagnostics;
- held-out measured integral-target evidence, including candidate-minus-prior
  and candidate-minus-fixed-incumbent loss differences and registered HAC
  bounds at every evaluated look;
- offline clean simulator-oracle generalized-torque prediction RMSE for the
  applied control model, plus post-decision candidate/incumbent oracle error;
- tracking combined RMSE and maximum absolute error;
- mean/minimum speed scale, time at minimum and nominal speed, final reference
  phase/progress, completion time, and termination reason;
- measurement/reconstruction diagnostics for force, moment, Human state, and
  acceleration where present;
- safety events and the existing descriptive cuff force, cuff moment, and
  cylindrical surface-load proxy metrics.

No new scalar composite score or post-hoc success threshold will be created.
Paired changes use `trusted_adaptive - prior_only` and percentages only where
the denominator is nonzero and scientifically meaningful.

## Preregistered interpretation

- If ideal sensing creates no challenger or promotion and the prior remains at
  zero clean-oracle error, that supports the expectation that an exact nominal
  prior is left essentially untouched. A promotion under ideal sensing must be
  traced to reconstruction, finite-window regression, numerical, contact, or
  closed-loop effects before any conclusion.
- If `noise_200hz` produces held-out measured improvement and promotion while
  clean-oracle prediction worsens, ordinary zero-mean noise plus the frozen
  preprocessing/reconstruction path is sufficient to induce a compensating
  control model. This design cannot attribute that effect to noise alone.
- If adding bias/drift increases promotion strength, bound pressure, or clean-
  oracle degradation relative to `noise_200hz`, systematic sensor nuisance is
  supported as an additional driver.
- Measured-domain predictive improvement and clean physical/oracle improvement
  are distinct. Trust uses only the former; oracle beta distance and oracle
  prediction error remain post-run diagnostics and never enter the decision.
- A promoted model that helps measured prediction or tracking but worsens clean
  oracle prediction is interpreted as a control-effective compensation model,
  not validated physical patient identification.
- A non-promotion, rejection, incomplete reference, poor tracking, bound-
  pressured candidate, or safety event is a valid result and does not authorize
  retuning.

Claims are limited to these engineering sensor definitions, this single seed,
the nominal Human-V2 simulator, and this trajectory. They are not clinical or
population claims.

## Integrity and artifacts

Before formal execution, mechanically verify that the three exact case names
exist, their numerical definitions match the table, the nominal true beta
equals the population prior, the baseline is an ancestor of the checkout, and
the output directory does not exist. Run structural tests/smokes only outside
the formal directory.

For every pair require identical true Human, initial state, sensor seed and
realization before promotion, MPC seed/candidates, reference, runtime, pacing,
trust, estimator, allocator, MPC objective, and safety settings. The prior-only
control beta must stay constant, and pre-promotion paired traces must be equal
under the existing strict isolation contract. God-view values must be offline
only, with no future-data leakage.

Canonical output is new and non-overwriting:
`results/robustness/sensor_robustness/nominal_decomposition/`. It will contain all six
arm JSON/NPZ artifacts, per-regime paired summaries, one aggregate machine-
readable summary, and one compact research report.
