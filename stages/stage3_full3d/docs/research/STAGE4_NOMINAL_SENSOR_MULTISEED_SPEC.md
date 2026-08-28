# Stage-4 Nominal Sensor-Decomposition Multi-Seed Specification

Status: **preregistered before execution**. This experiment repeats the existing
nominal-only sensor decomposition across a small fixed seed set. It does not
modify or overwrite the single-seed decomposition or the 13-case patient-
mismatch evidence.

## Scientific question

Is the trusted nominal compensating promotion observed under
`noise_bias_drift_200hz` a repeatable sensor-regime effect, or mainly variability
from one measurement seed and the finite-sample trust decision?

The hypothesis is not assumed true. The experiment reports distributions and
per-seed outcomes, including unfavorable or null results.

## Fixed seed set and scale

The preregistered measurement seeds are:

```text
44104, 54113, 64122, 74131, 84140
```

The first value preserves the original formal decomposition as an internal
replication anchor. The other four are fixed deterministically before any new
rollout by `44104 + 10009*k`, for `k = 1, 2, 3, 4`. Five seeds give descriptive
promotion frequencies in 20-percentage-point increments: enough to distinguish
an isolated observation from repeated occurrence without presenting this as a
large Monte Carlo study or a precise population-probability estimate.

The MPC seed remains `20260824` in every rollout. Each measurement-seed/sensor
pair starts the frozen MPC random stream identically in `prior_only` and
`trusted_adaptive`. Thus the only within-pair scientific variable is whether a
statistically qualified model may enter control. Across measurement seeds, only
the existing sensor RNG seed changes; MPC stochastic semantics do not.

## Fixed experiment matrix

The true patient is always the exact nominal
`traction_mpc_stage3.human.HUMAN`, whose true 11-base beta equals the population
prior. Each seed uses exactly the three existing sensor cases:

- `ideal_200hz`;
- `noise_200hz`;
- `noise_bias_drift_200hz`.

No bias-only, drift-only, preprocessing-only, new magnitude, or new sensor case
is introduced. The existing ideal case has zero stochastic perturbation, so its
five seed repeats are expected to be numerically identical; they remain in the
matrix to preserve the complete preregistered design and detect any unexpected
seed leakage.

For every one of the 5 seeds by 3 regimes, run:

- `prior_only`: trust runs causally, but qualification cannot change control
  beta;
- `trusted_adaptive`: the same qualified challenger enters control at its
  causal promotion time.

The formal matrix is therefore 15 paired comparisons and 30 rollouts.

## Frozen settings

Except for the preregistered measurement seed, retain the previous nominal
sensor-decomposition contract exactly:

- continuous high-flexion 23 s reference and 32 s wall-time allowance;
- accumulated integral 11-base estimator and existing physical bounds;
- L1/L2/L3 validity and the fixed single-incumbent/at-most-one-challenger L4;
- 0.5 s embargo, clean 0.5 s blocks, looks at 8/12/16, lag-2 HAC, and existing
  anytime alpha spending;
- existing filtered/hysteretic confidence pacing and all thresholds/rates;
- feasible-first batched CEM MPC, horizon 15, 32 candidates, two iterations,
  six elites, seed `20260824`, original objective and constraints;
- registered 1:1 cuff-aware allocator, measurement routing, plant integration,
  initial condition, preprocessing belonging to each existing sensor case,
  safety limits, and warning/termination handling;
- zero interaction-aware weights and no UKF/Kalman, active excitation, hybrid
  optimizer, corridor/tube control, new threshold, or retuning.

Baseline provenance remains tag `stage4-baseline-v1`, commit
`ef1fe90e61c5981df8e934585780ce188d104ea4`. Runtime fingerprints and exact
source hashes are recorded before execution.

## Metrics and distributions

For each seed/regime/arm, retain the existing per-run metrics:

- first qualification and promotion time; qualification, promotion, rejection,
  and pending counts;
- active-bound count, pressured parameters, and unconstrained violation;
- all held-out measured candidate-minus-prior and candidate-minus-fixed-
  incumbent loss differences and registered HAC bounds;
- clean simulator-oracle control-model prediction RMSE and post-decision
  candidate/incumbent oracle errors;
- tracking RMSE and maximum error;
- mean/min/max speed, time at minimum/nominal speed, final phase/progress, and
  reference completion;
- force/moment/state/acceleration measurement-reconstruction diagnostics;
- safety, solver, robot-limit, force, moment, and cylindrical surface-proxy
  metrics.

For each sensor regime, report the complete per-seed values plus count/frequency
and the median, minimum, maximum, and quartiles where meaningful. In particular
report promotion timing, clean-oracle prediction change, tracking RMSE/max-error
change, pacing/progress, and maximum bound pressure. No post-hoc threshold or
composite score is introduced.

## Preregistered outcome categories

Each trusted-adaptive seed/regime result receives one descriptive category:

- **A — no trusted promotion**: no challenger enters control;
- **B — trusted measured-domain compensation with oracle degradation**: a
  challenger is promoted under the registered held-out measured-loss rule and
  the applied arm has strictly higher clean-oracle control-model RMSE than its
  paired prior-only arm;
- **C — trusted measured-domain and oracle improvement**: a challenger is
  promoted and the applied arm has strictly lower clean-oracle control-model
  RMSE than its paired prior-only arm.

Exact oracle equality after promotion, if observed, is reported separately and
not forced into B or C. Because the exact nominal prior has zero clean-oracle
model error, category C is structurally unlikely and any occurrence requires an
integrity/numerical audit rather than favorable reinterpretation.

Promotion itself establishes measured-domain improvement only under the frozen
trust rule: both preregistered upper bounds must be below zero. Clean-oracle beta
distance and prediction error are offline simulator evidence and never enter
trust, pacing, control, termination, or seed selection.

## Interpretation fixed before execution

- `ideal_200hz` supports “prior usually protected” only if most or all seeds are
  category A and the seed-irrelevant repeats agree exactly. Any ideal promotion
  must be investigated as reconstruction, finite-window, numerical, contact, or
  RNG leakage behavior.
- `noise_200hz` supports “stronger candidates but limited promotion” only if its
  bound pressure exceeds ideal descriptively while promotion remains less
  frequent than under bias+drift. Otherwise report the contrary result.
- `noise_bias_drift_200hz` supports systematic nuisance compensation only if
  promotion recurs across multiple seeds and is appreciably more frequent than
  noise-only in this five-seed set. A single recurrence or similar regime
  frequencies is treated as seed-specific or unresolved.
- Category B supports a control-effective compensation interpretation, not
  physical patient identification. Category C would still not establish
  physical parameter truth.
- Tracking, pacing, and safety consequences are reported separately from the
  trust decision. Conflicting metrics remain mixed results.
- No observed result authorizes changing thresholds, bounds, pacing, MPC, or
  sensor parameters.

Further bias/noise/drift/preprocessing decomposition is scientifically justified
only if this repeat shows a stable difference between the cumulative existing
regimes that cannot be explained as one-seed variability. Any such split would
require a new preregistration and new sensor configurations; it is not part of
this experiment.

## Integrity and artifacts

Before execution verify the five exact seeds, three exact existing sensor
definitions and magnitudes, exact nominal Human/prior equality, baseline
ancestry, frozen non-seed fingerprints, structural A/B isolation, and absence
of the output directory. Within every pair require identical seed realization,
initial states, MPC stream, trust lifecycle, pacing, reference, runtime, and
configuration until causal model application. Prior-only beta must remain the
population prior, God-view data must stay offline, and traces must be finite.

Integrity failures stop the suite; scientific rejection, non-promotion,
incompletion, poor tracking, bound pressure, or safety events are retained and
do not stop it.

Canonical output is new and non-overwriting:
`results/stage4_nominal_sensor_multiseed_formal/`. It will contain all 30 arm
JSON/NPZ artifacts, 15 per-pair summaries, one execution manifest, one aggregate
machine-readable summary, one promotion-frequency table, and one concise
research report.
