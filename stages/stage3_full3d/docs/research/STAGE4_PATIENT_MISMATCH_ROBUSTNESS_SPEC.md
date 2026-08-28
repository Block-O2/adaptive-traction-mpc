# Stage-4 Patient/Model-Mismatch Robustness Experiment Spec

Status: **frozen preregistration text; the user subsequently completed the
formal run**. The reviewed result is in
`results/stage4_patient_mismatch_robustness_formal/research_report.md`. Future
tense below records the preregistration-time contract and is not rewritten from
the outcome. No clinical population range or clinical conclusion is claimed.

Baseline: Git tag `stage4-baseline-v1`, commit
`ef1fe90e61c5981df8e934585780ce188d104ea4`.

## Scientific question and test logic

### Why this test is needed

The frozen formal Stage-4 A/B result used one registered perturbed Human. It
showed smaller tracking and generalized-torque prediction error after trusted
adaptation, while cuff interaction was essentially unchanged. That single case
does not establish robustness across mismatch mechanisms or magnitudes.

The question is therefore: under which mechanically valid Human-V2 mismatches
does the frozen population prior remain adequate, and under which mismatches
does causally trusted patient-specific adaptation improve control-relevant
tracking or torque prediction?

### What is varied

Only the true simulated Human case. The initial suite varies mass-derived
inertia/gravity, passive stiffness, viscous damping, passive equilibrium angle,
and four registered mixed anchors. Geometry changes occur only in three of the
existing anchors.

All new magnitudes are **engineering robustness ranges**, selected before any
closed-loop outcomes and not asserted to be clinical population ranges.

### What stays fixed

Every case has exactly two arms: `prior_only` and `trusted_adaptive`. Their only
scientific difference is whether a statistically qualified dynamics model is
allowed to enter control. Section "Frozen paired A/B contract" is normative.

### What a result would mean

The suite reports continuous paired differences rather than requiring the
adaptive arm to win every case. No promotion, worse adaptive performance,
incomplete tasks, and safety termination are retained as valid outcomes. The
predefined interpretation vocabulary is in section "Interpretation logic";
no threshold may be changed after results are observed.

## Human-V2 physical parameterization

### Raw parameters that are meaningful in the current simulator

The committed Human-V2 plant exposes:

- height `h` and body mass `m`;
- gravity `g` as an environment property, not a patient property;
- two passive stiffnesses `k1,k2`;
- two passive damping coefficients `bv1,bv2`;
- two passive equilibrium angles `qr1,qr2`;
- joint ROM and nonlinear soft-limit parameters;
- derived segment lengths, segment masses, COM positions, inertias, and cuff
  center distance.

`ScaledHumanV2` additionally supports thigh-COM, shank-COM, and sleeve-center
scale factors. The COM scales move the point-mass terms but do not change the
committed segment-inertia formula `I_i = m_i (0.30 L_i)^2`; this is a simulator
parameterization, not an anatomical independence claim.

The nominal raw values are:

| quantity | nominal value |
|---|---:|
| height / body mass | 1.72 m / 75 kg |
| thigh / shank length | `0.254 h` / `0.233 h` |
| thigh / shank mass | `0.099 m` / `0.060 m` |
| thigh / shank COM | `0.433 L1` / `0.430 L2` |
| sleeve center | `0.90 L2` |
| passive stiffness | [10, 10] Nm/rad |
| passive damping | [5, 5] Nms/rad |
| passive equilibrium | [5, 10] deg |

### Exact mapping to the 11-base vector

Let `L1` be thigh length, `c1,c2` the two COM distances, `m1,m2`
the segment masses, and `I1,I2` the committed inertias. Human-V2 maps exactly
to

```text
b  = I2 + m2 c2^2
d  = m2 L1 c2
a  = I1 + m1 c1^2 + b + m2 L1^2
g1 = g (m1 c1 + m2 L1)
g2 = g m2 c2

beta = [a, b, d, g1, g2, k1, k2, k1 qr1, k2 qr2, bv1, bv2]
```

This beta is an exact inverse-dynamics representation while the frozen
nonlinear soft-limit torque is inactive. The integral identifier uses the same
11 columns without instantaneous acceleration.

### Structurally inseparable quantities

- `a` combines both segment inertias, both COM point-mass terms, and the distal
  mass at thigh length. These raw contributors are not individually identified.
- `b` combines distal inertia and distal COM point-mass inertia.
- `d` identifies only the product `m2 L1 c2`.
- `g1` combines proximal and distal gravity contributions; `g2` identifies only
  `g m2 c2`.
- the passive offsets are `rho_i = k_i qr_i`. Beta does not directly identify
  an independent physical equilibrium angle unless `k_i` is interpreted jointly
  with `rho_i`.
- arbitrary changes to these 11 entries need not correspond to any Human-V2
  raw-parameter set. Such changes are excluded from this physical-patient suite.

Beta closeness is therefore a simulator-oracle diagnostic, not evidence that
raw physical parameters were recovered.

### Geometry-coupled and excluded variations

Height changes both dynamics and the MuJoCo geometry: `L1`, `L2`, segment COMs,
inertias, cuff position, and distal contact geometry all change. Sleeve-center
scale changes the cuff location and allocator Jacobian but not beta. The current
separate planar geometry estimator can represent thigh length and knee-to-cuff
vector; distal shank geometry beyond the cuff is not a controller model state.
If changed distal geometry creates bed contact, the resulting interaction is a
plant/contact effect and contaminated estimator windows remain excluded by the
frozen logic.

The following are not introduced in the initial suite:

- independent thigh/shank length, mass, or inertia changes unsupported by the
  current raw Human-V2 class;
- gravity changes, because gravity is shared environment physics rather than a
  patient variable;
- joint-ROM or soft-limit stiffness/damping changes, because the 11-base model
  uses the frozen nominal nonlinear soft-limit law;
- cuff placement changes presented as patient physiology;
- arbitrary 11-base perturbations. These may be added later only as explicitly
  labeled control-model stress tests.

## Exact preregistered case matrix

The canonical declarative source is
`configs/stage4_patient_mismatch_cases.json`. `K scale`, `B scale`, and `COM
scale` are joint-ordered `[hip,knee]`; rest angles below are the resulting
absolute angles. A `geometry=yes` row requires the unchanged geometry estimator.

| case | level | mechanism | h (m) | mass (kg) | COM scale | K scale | B scale | rest (deg) | sleeve scale | geometry |
|---|---|---|---:|---:|---|---|---|---|---:|---|
| `nominal_reference` | near-prior | none | 1.7200 | 75.00 | [1,1] | [1,1] | [1,1] | [5,10] | 1.00 | no |
| `mass_mild_minus_05pct` | mild | inertia/gravity | 1.7200 | 71.25 | [1,1] | [1,1] | [1,1] | [5,10] | 1.00 | no |
| `mass_mild_plus_05pct` | mild | inertia/gravity | 1.7200 | 78.75 | [1,1] | [1,1] | [1,1] | [5,10] | 1.00 | no |
| `stiffness_moderate_minus_20pct` | moderate | stiffness | 1.7200 | 75.00 | [1,1] | [0.8,0.8] | [1,1] | [5,10] | 1.00 | no |
| `stiffness_moderate_plus_20pct` | moderate | stiffness | 1.7200 | 75.00 | [1,1] | [1.2,1.2] | [1,1] | [5,10] | 1.00 | no |
| `damping_moderate_minus_30pct` | moderate | damping | 1.7200 | 75.00 | [1,1] | [1,1] | [0.7,0.7] | [5,10] | 1.00 | no |
| `damping_moderate_plus_30pct` | moderate | damping | 1.7200 | 75.00 | [1,1] | [1,1] | [1.3,1.3] | [5,10] | 1.00 | no |
| `rest_equilibrium_moderate_minus_03deg` | moderate | equilibrium | 1.7200 | 75.00 | [1,1] | [1,1] | [1,1] | [2,7] | 1.00 | no |
| `rest_equilibrium_moderate_plus_03deg` | moderate | equilibrium | 1.7200 | 75.00 | [1,1] | [1,1] | [1,1] | [8,13] | 1.00 | no |
| `registered_stage2_mild_anchor` | mild anchor | mixed | 1.7200 | 78.75 | [1,1] | [1,1] | [1,1] | [3,8] | 1.00 | no |
| `registered_moderate_anchor` | moderate | mixed | 1.7200 | 78.75 | [1.05,0.95] | [1.1,1.1] | [1,1] | [3,8] | 1.02 | yes |
| `registered_formal_perturbed_anchor` | anchor | mixed geometry | 1.8232 | 81.00 | [1.04,0.96] | [1.15,1.15] | [1,1] | [3,13] | 0.94 | yes |
| `registered_stage2_adverse_anchor` | larger anchor | mixed | 1.7200 | 82.50 | [1.10,0.90] | [1.20,1.20] | [1,1] | [3,8] | 1.05 | yes |

The isolated directions are symmetric about the prior where mechanically
meaningful. The mixed cases are intentionally interpretable compositions, not
random samples. Stage-2 mild/moderate/adverse and the frozen formal perturbed
case are copied anchors and are not retuned.

The Stage-2 fixed-prior smoke used a different 15 s reference: mild passed its
completion gate, while moderate/adverse reached 15 s but missed terminal
tracking tolerance; all respected its recorded ROM, force, torque, and solver
checks. Those outcomes motivate the anchors but are not Stage-4 predictions,
formal evidence, or thresholds for this suite.

### Resulting beta and normalized prior distance

Beta column order is `[a,b,d,g1,g2,k1,k2,rho1,rho2,bv1,bv2]`. The normalized
distance is preregistered as

```text
z = (beta_case - beta_prior) / (estimator_upper - estimator_lower)
distance = ||z||_2; maximum component = ||z||_infinity
```

This uses the existing estimator span; it is not a population z-score.

| case | beta (exact construction, rounded for display) | span L2 | span Linf |
|---|---|---:|---:|
| `nominal_reference` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 10, 10, .872664626, 1.74532925, 5, 5] | 0 | 0 |
| `mass_mild_minus_05pct` | [1.37827660, .188746799, .321848216, 31.4117487, 7.22699826, 10, 10, .872664626, 1.74532925, 5, 5] | .111803 | .05 |
| `mass_mild_plus_05pct` | [1.52335835, .208614883, .355726976, 34.7182485, 7.98773492, 10, 10, .872664626, 1.74532925, 5, 5] | .111803 | .05 |
| `stiffness_moderate_minus_20pct` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 8, 8, .698131701, 1.39626340, 5, 5] | .293333 | .20 |
| `stiffness_moderate_plus_20pct` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 12, 12, 1.04719755, 2.09439510, 5, 5] | .293333 | .20 |
| `damping_moderate_minus_30pct` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 10, 10, .872664626, 1.74532925, 3.5, 3.5] | .424264 | .30 |
| `damping_moderate_plus_30pct` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 10, 10, .872664626, 1.74532925, 6.5, 6.5] | .424264 | .30 |
| `rest_equilibrium_moderate_minus_03deg` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 10, 10, .349065850, 1.22173048, 5, 5] | .156205 | .12 |
| `rest_equilibrium_moderate_plus_03deg` | [1.45081748, .198680841, .338787596, 33.0649986, 7.60736659, 10, 10, 1.39626340, 2.26892803, 5, 5] | .156205 | .12 |
| `registered_stage2_mild_anchor` | [1.52335835, .208614883, .355726976, 34.7182485, 7.98773492, 10, 10, .523598776, 1.39626340, 5, 5] | .152789 | .08 |
| `registered_moderate_anchor` | [1.53827383, .194934065, .337940627, 35.4416424, 7.58834817, 11, 11, .575958653, 1.53588974, 5, 5] | .188129 | .10 |
| `registered_formal_perturbed_anchor` | [1.77414605, .228383182, .394670095, 38.4837752, 8.36055674, 11.5, 11.5, .602138592, 2.60926723, 5, 5] | .460384 | .222860 |
| `registered_stage2_adverse_anchor` | [1.62934705, .190619342, .335399720, 37.8871809, 7.53129292, 12, 12, .628318531, 1.67551608, 5, 5] | .348671 | .20 |

The validator records unrounded raw values and beta. All 13 cases pass finite
parameter, positive mass/length, COM-inside-segment, cuff-on-shank,
nonnegative-passive-coefficient, rest-inside-ROM, positive-definite mass-matrix,
and unchanged-soft-limit checks. All beta vectors are inside the existing
identifier bounds.

### Expected dominant effects and model-family status

| mechanism | expected torque-model effect | current representation |
|---|---|---|
| mass pair | common signed change in all five inertia/gravity base terms | exact 11-base; geometry unchanged |
| stiffness pair | slope of `k(q-qr)` changes; `k` and `rho=k qr` move together | exact 11-base |
| damping pair | velocity-proportional torque changes through `bv1,bv2` | exact 11-base |
| equilibrium pair | constant passive offset changes through `rho`; stiffness slope fixed | exact 11-base |
| Stage-2 mild anchor | mass plus passive-equilibrium mismatch | exact 11-base; geometry unchanged |
| registered moderate | mass/COM/passive plus cuff-center mismatch | exact 11-base plus separate geometry estimator |
| formal anchor | frozen mass/height/COM/passive/cuff mismatch | exact 11-base plus separate geometry estimator, subject to contact caveat |
| Stage-2 adverse anchor | larger mass/COM/stiffness/equilibrium plus cuff-center mismatch | exact 11-base plus separate geometry estimator |

No initial case is intentionally outside the current Human-V2/11-base plus
geometry-estimator family. Out-of-family stress tests remain a later, separately
preregistered suite. This is deliberate: the first experiment isolates when
trusted adaptation helps for representable patient mismatch before testing
model inadequacy.

## Frozen paired A/B contract

### Why this control is needed

Patient mismatch must be the only between-case scientific variable, and model
application must be the only within-case A/B variable.

### What is varied

- `prior_only`: trust runs causally, but a qualified beta never enters control.
- `trusted_adaptive`: the same qualified challenger becomes control incumbent at
  the causal promotion time.

### What stays fixed

- continuous high-flexion 23 s reference and 32 s wall-time window;
- `noise_bias_drift_200hz`, measurement seed 44104;
- MPC seed 20260824;
- feasible-first CEM, batched implementation, horizon 15, 32 candidates, two
  iterations, six elites, original tracking/action/action-slew objective;
- zero interaction-aware MPC weights;
- accumulated integral 11-base estimator and existing physical bounds;
- L1/L2/L3 semantics and single-incumbent/at-most-one-challenger L4 rule;
- 0.5 s embargo, clean non-overlap 0.5 s validation blocks, looks at 8/12/16,
  lag-2 HAC, and existing anytime alpha allocation;
- confidence pacing, preprocessing, measurement routing, geometry estimator;
- registered 1:1 cuff-aware allocator and cylindrical proxy definition;
- plant integration, initial state, controller gains, force gate, moment limit,
  ROM, robot torque/velocity constraints, warning handling, and runtime;
- no active excitation, UKF/Kalman, hybrid optimizer, interaction-aware weights,
  tracking tube/corridor, new trust threshold, estimator bound, or retuning.

The machine-readable contract is `FROZEN_SHARED_AB_CONTRACT` in
`patient_mismatch.py`. Tests compare its key MPC/statistical/allocator/pacing
entries with the frozen runtime defaults.

### What a result would mean

Any post-promotion difference is attributable to the trusted control model only
if all isolation assertions below pass. A pair with no promotion is valid and
tests trust protection rather than adaptive control benefit.

## Metrics preregistered before execution

### Primary control metrics

- full-task and post-promotion tracking RMSE;
- maximum absolute tracking error;
- final reference phase and progress fraction, completion, and termination;
- all safety events, including force gate, ROM, unintended contact, torque
  saturation, MPC failure, solver warning, and nonfinite state/wrench.

### Primary adaptation/model metrics

- control-model generalized-torque prediction RMSE, appended by God-view
  evaluation only after rollout;
- first challenger qualification time and first control-promotion time;
- number and timing of promotions;
- reference phase and fraction of trajectory remaining after first promotion;
- candidate state/rejection reason and active-bound pressure;
- whether trusted adaptation ever enters control.

### Logged interaction metrics, not success criteria

- cuff translational force peak/RMS;
- cuff moment peak/RMS;
- cylindrical surface proxy peak/RMS, explicitly not pressure, comfort, or
  tissue loading.

Interaction reduction is not a success criterion because the frozen formal
case supported tracking/prediction benefit, not interaction benefit.

### Simulator-oracle diagnostics

- population-prior-to-true-beta span-normalized distance;
- incumbent/challenger-to-true-beta span-normalized distance;
- exact true beta and raw Human parameters.

These are offline God-view diagnostics only. They may not enter estimation,
trust, pacing, MPC, allocation, termination, or case selection, and beta
closeness is not physical parameter truth.

No new scalar composite score or post-hoc benefit threshold is introduced.
Report `trusted_adaptive - prior_only` and percentage change where the
denominator is well-defined.

## Interpretation logic

The following are descriptive outcome tags. They need not be forced into one
exclusive winner label, and all underlying continuous metrics remain visible.

- **negligible-control-consequence mismatch**: the prior completes safely and
  paired primary differences are practically small when reported continuously.
  No numerical cutoff is invented after viewing the suite.
- **useful adaptation regime**: trusted adaptation enters control and improves
  tracking and/or torque prediction without added safety events or lost
  completion/progress. Conflicting primary metrics are reported as mixed, not
  converted into a win by a composite score.
- **trust-protected regime**: no challenger promotion occurs, or the candidate
  is rejected and prior/last-valid control is retained. This is a valid trust
  outcome, not an experiment failure.
- **model-family limitation**: a case is preregistered as out of family, or an
  offline representability audit shows a nonzero best achievable model residual
  not attributable to noise/contact. No such case is in this initial suite.
- **controller/safety failure**: neither arm safely completes, or both encounter
  the same limiting safety/controller mechanism. The result is retained and no
  tuning follows.
- **mixed or adverse adaptive response**: adaptation promotes but worsens a
  primary metric, adds a safety event, or reduces progress. This is retained as
  evidence against benefit in that case.

The frozen formal anchor is a replication/anchor within this suite. Its prior
result is context, not a criterion that the new run must reproduce exactly.

## Causal and fairness checks

For every pair, mechanically require:

1. identical Human case, initial state, measurement seed and random samples,
   MPC seed and candidate populations, reference, runtime, and shared config;
2. identical statistical trust configuration, qualification time, and
   single-challenger lifecycle up to first adaptive model application;
3. no prior-only control promotion and a constant prior-only control beta;
4. identical pre-promotion time grid, reference phase, God-view Human state,
   desired generalized action, allocated wrench, speed scale, and control beta
   to the existing `atol=1e-10`, `rtol=0` isolation contract;
5. no future-data leakage: candidate training blocks precede embargoed,
   non-overlapping validation blocks; God-view beta/error is appended only
   after rollout;
6. only the trusted patient-specific dynamics model may create post-promotion
   controller differences.

An isolation assertion failure invalidates the pair mechanically; it does not
authorize a rerun with changed scientific settings.

## Implementation and artifact plan

The implementation is declarative rather than copied scripts:

- one JSON case specification;
- one deterministic Human constructor and case-record generator;
- one paired-arm contract generator;
- one reusable paired A/B runner that factors the existing formal runner
  rather than duplicating controller code;
- one JSON summary per case and one aggregate JSON/Markdown summary;
- the existing raw per-arm JSON/NPZ traces retained in a new output directory.

`scripts/run_stage4_patient_mismatch_robustness.py` selects exactly one
preregistered case and invokes the factored existing A/B path. The case changes
only the true Human plant; controller/estimator initialization remains the
population prior. `scripts/validate_stage4_patient_mismatch_cases.py` performs
only construction and structural validation and prints machine-readable
records.

The future per-case result schema version is
`stage4_patient_mismatch_paired_result_v1`, with top-level case record, frozen
contract, A/B isolation, two arms, and comparison. Required arm fields are
frozen in `CASE_RESULT_REQUIRED_FIELDS` and covered by tests.

## Required checks before authorizing the batch

- deterministic config loading and case construction;
- exact raw-parameter-to-11-base inverse-dynamics consistency;
- physical validity and positive-definite mass matrix over the ROM;
- every beta inside the frozen estimator box;
- existing anchors copied exactly;
- prior/adaptive configs differ only by model-application flag;
- frozen scientific contract matches runtime defaults;
- result-schema stability and JSON serializability;
- one dynamics-only and one geometry-changing 0.1-second structural smoke
  proving case injection, paired isolation, and output schema, with no
  scientific interpretation.

## Authorization gate and reserved formal command

This design and implementation are mechanically ready for the user to authorize
formal execution for the **representable Human-V2 mismatch question**. The
case-aware paired runner, end-to-end isolation/schema tests, two structural
smokes, and full Stage-4 regression exist. This statement is not a scientific
result and does not itself authorize Codex to run a formal case or the suite.

After separate user approval, the intended user-only per-case formal command is:

```bash
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_patient_mismatch_robustness.py \
  --case-config configs/stage4_patient_mismatch_cases.json \
  --case-id <preregistered-case-id> \
  --output-dir results/stage4_patient_mismatch_robustness_formal
```

The runner writes to `<output-dir>/<case-id>` and refuses an existing case
directory. Failed, poor, or no-promotion results must be retained without
tuning or rerun.
