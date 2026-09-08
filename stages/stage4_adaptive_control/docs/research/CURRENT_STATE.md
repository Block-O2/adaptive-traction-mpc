# Current Research State: Stage-4 Adaptive MPC Closeout

Status: **simulation-qualified research controller; Stage-4 scientific phase
closed for repository checkpointing**. The latest crossed replication has been
reviewed as authoritative formal evidence at the repository level. Its source
run files retain the historical `formal_user_run_unreviewed` label and are not
rewritten.

Phase-3A High-ROM status: **the corrected robot control-velocity measurement
contract is the current repository interpretation for High-ROM engineering
stress tests**. The source campaign retains its registered
`exploratory_diagnostic_only` category; the user-reviewed interpretation is
authoritative for current repository documentation. Earlier High-ROM BRAKE and
P1 222 N results remain diagnostic history and are not rewritten or deleted.

Baseline ancestry: `stage4-baseline-v1` at
`ef1fe90e61c5981df8e934585780ce188d104ea4`. The final checkpoint extends that
baseline with preregistered patient, sensor, trajectory, and crossed-replication
evidence without changing the frozen controller contract.

## Architecture and mechanics

The simulation plant couples a torque-actuated 3D UR10e surrogate to planar
Human V2. The main Stage-4 evidence uses a six-constraint rigid cuff; Phase 3A
also compares the registered P1 progressive spring-damper interface without
claiming measured tissue fidelity. Robot self-collision remains active;
Human-bed contact retains the Stage-2 definition; robot-Human and robot-bed
collision domains are isolated. The cuff wrench is reconstructed by virtual
work from the constraint or interface generalized force. Raw rotational
equality multipliers are not interpreted directly as physical moment.

The Stage-4 online boundary uses robot state/FK, measured cuff pose/twist, and
reconstructed cuff wrench. MuJoCo Human state and true parameters are available
only for offline evaluation. The controller does not receive God-view truth.

The frozen sagittal allocator preserves requested Human generalized torque and
uses a 1:1 objective balance between resultant force and a minimum-norm
equivalent cylindrical surface-load effort. This surface quantity is a
mathematical proxy, not pressure, comfort, or tissue loading. The formal
controller uses a memoryless allocator; no hidden cuff-force clipping or tissue
model is added.

## Effective dynamics model and trust

The estimator uses a causal accumulated integral regression over 11 Human-V2
base terms: three inertia/coupling combinations, two gravity combinations, two
passive stiffnesses, two stiffness-rest combinations, and two viscous damping
terms. Bounds, regularization, smoothing, and update limits are frozen.

Beta is a **control-effective identifiable base model**. It need not recover
physical patient anatomy. Under systematic sensor bias/drift, a beta that
predicts future measured integral targets better can move away from clean
nominal plant truth while still modestly improving tracking.

Trust is layered and causal:

- L1 checks measurement integrity and timing;
- L2 checks reconstructed state and geometry validity;
- L3 records identification quality and bound pressure;
- L4 validates one challenger at a time against both the population prior and
  the fixed incumbent on future, embargoed, non-overlapping blocks with the
  frozen anytime alpha-spending rule.

There is exactly one retained incumbent and at most one active challenger. A
qualified candidate enters control only in `trusted_adaptive`; `prior_only`
runs the same estimator, trust, and pacing lifecycle but keeps the population
prior in control. Pre-promotion A/B equality is checked from saved traces.
Confidence pacing depends on retained-model validity, not oracle error or
eventual tracking benefit.

## MPC and execution

The formal controller is feasible-first Human-space CEM MPC with horizon 15,
32 candidates, two iterations, six elites, seed 20260824, the original
tracking/action/action-slew cost, and unchanged constraints. The default
batched implementation is regression-equivalent to the retained scalar
reference and falls back to scalar evaluation for unsupported model/allocator
combinations.

Interaction-aware force, cylindrical-surface-effort, and wrench-slew terms are
implemented and have engineering comparisons. They are **not active in the
authoritative formal evidence**: the crossed controller fingerprint keeps all
three interaction weights at zero. No active excitation, hybrid optimizer,
online UKF/Kalman filter, tracking tube, or new safety threshold is active.

Robot translational velocity feedback now has an explicit control-only
measurement path. At the existing 200 Hz control boundary, raw robot joint
position/velocity passes through the registered 140 mm cuff-center WORLD-frame
Jacobian and is held for the existing 5 ms command interval. The frozen
140 Ns/m gain uses this snapshot consistently in first-action screening,
Safety Filter, BRAKE candidate checks, and final execution. Invalid or stale
snapshots fail explicitly; there is no fallback to the old velocity signal.
Rotational velocity feedback is unchanged.

The 8 Hz pose low-pass plus 120 ms causal quadratic derivative remains active
for Human state reconstruction, identification, and the MPC measurement path.
It is no longer reused as the translational robot low-level damping-feedback
velocity. This separates estimation smoothing from control feedback without
changing the Human MPC, estimator, gain, Safety Filter, BRAKE, force target,
models, trajectories, solver, timestep, seed, or geometry.

## Evidence summary

### Original adaptive A/B

The registered perturbed-Human pair completed with exact causal isolation
before the first promotion. Tracking RMSE changed 0.765477° → 0.713056°
(6.85% improvement), and control-model torque-prediction RMSE changed
4.424389 → 3.968691 Nm (10.30%). Cuff force, moment, and surface-proxy changes
were negligible and not consistently favorable. The supported claim is better
tracking and prediction, not reduced cuff interaction.

### Desktop realtime replay

The saved-trace benchmark measured batched MPC mean/p95/max of
9.422/9.583/9.766 ms and full-cycle mean/p95/max of
16.524/17.789/18.641 ms. The mean corresponds to about 60.5 Hz, and all
recorded optimized samples were below 20 ms. This supports >30 Hz desktop
replay, not a hard-realtime hardware deadline.

### Patient/model mismatch

All 13 paired cases promoted. Tracking RMSE improved in 13/13 and torque-
prediction RMSE in 9/13. Both arms completed the reference in 10/13; three
pairs shared incomplete progress because the first challenger was rejected and
qualification occurred late. No recorded safety event occurred. Bound pressure
appeared in every case and reinforces the control-effective, non-anatomical
interpretation of beta.

### Sensor mechanisms and seeds

In the nominal three-regime decomposition, ideal and noise-only sensing did not
promote for seed 44104; noise+bias+drift promoted at 17.74 s, improved the
measured trust target and tracking slightly, but degraded clean-oracle dynamics
prediction.

Across five seeds, promotion frequency was 0/5 for ideal, 2/5 for noise-only,
and 5/5 for noise+bias+drift. All seven promoted nominal cases improved the
measured-domain criterion while degrading clean-oracle prediction. The biased
result is systematic in this fixed seed set, while noise-only promotion remains
seed-variable. Five seeds provide descriptive 20-point frequency resolution,
not a population estimate.

### Trajectory excitation

All six preregistered trajectory regressors were structurally rank 11, but
practical conditioning varied by orders of magnitude. Five trajectories
promoted and improved both tracking and prediction RMSE; maximum error improved
in only two. The knee-dominant case hit the same force gate in both arms before
a challenger formed and remained valid negative evidence. The practically
ill-conditioned two-cycle trajectory promoted latest among the five promoted
cases and left the least remaining reference. Full rank is therefore not
sufficient for timely or useful adaptation, and excitation strength does not
monotonically determine benefit magnitude.

### Authoritative crossed replication

The preregistered balanced-incomplete matrix contains 18 paired cases / 36
arms: 16 new executions and two read-only bridge pairs. Mechanical integrity,
strict JSON, finite NPZ traces, factor/config/runtime provenance, fresh state,
pre-promotion A/B isolation, population-prior retention, embargo/non-overlap,
and single-challenger checks all passed. The crossed matrix SHA-256 is:

`00019282e188a1dca8d182b15ad9dd74d44c33312be5ad88f2f2c73efe1bbc81`.

Observed outcomes:

- 18/18 control promotion;
- 18/18 both arms completed;
- 18/18 tracking-RMSE improvement;
- 18/18 torque-prediction-RMSE improvement;
- no recorded safety events;
- two cases improved RMSE while worsening maximum tracking error;
- first promotion 9.72-15.36 s, mean 11.14 s.

H1 (poorer practical excitation tends to delay promotion), H2 (stronger
mismatch does not necessarily mean larger benefit), and H5 (poor excitation
can reduce remaining adaptation time without preventing promotion) are
supported. H3 (prediction/tracking association) and H4 (seed sensitivity
without demonstrated systematic reversal) are conditionally supported within
the small fractional design. The design does not identify an unrestricted
patient × trajectory × seed interaction.

### Corrected Phase-3A High-ROM baseline

The prior High-ROM command-feasibility boundary was strongly affected by the
history-derived robot velocity-feedback measurement path. In the saved old
40/80 and 120/120 boundary events, that path produced 83.14 N and 135.49 N
velocity-feedback terms before the 200 N executable-force crossing. Those
events remain valid diagnostic evidence for the old measurement contract.

The corrected Rigid NEW versus P1 NEW campaign keeps the Human MPC, 140 Ns/m
gain, Safety Filter, BRAKE, registered 200 N simulation engineering target,
P1 parameters, 0.25 ms timestep, solver, seed, Human/robot models, 140 mm
geometry, and trajectories unchanged. All corrected cases executed 100% of the
reference, recorded no Safety Filter intervention, FILTER_INFEASIBLE, BRAKE,
or NO_SAFE_ACTION event, and passed the retained force contract.

| trajectory | Rigid NEW | P1 NEW | physical outbound/return | physical force peak R/P | principal interpretation |
|---|---|---|---:|---:|---|
| 40/80 | COMPLETE | SAFE_INCOMPLETE | 100.00/100.00% vs 99.72/99.99% | 121.58/122.06 N | P1 adds no feasibility advantage; lower slew with worse tracking/settling |
| 90/120 | SAFE_INCOMPLETE | SAFE_INCOMPLETE | 96.18/100.00% vs 96.49/99.87% | 140.29/128.90 N | P1 lowers force peak and moment and slightly improves tracking |
| 120/120 | SAFE_INCOMPLETE | SAFE_INCOMPLETE | 99.33/99.99% vs 99.30/99.80% | 116.93/117.73 N | both avoid the old boundary; P1 mainly lowers slew with worse tracking/settling |

The retained 0.068969° tolerance still determines formal classification.
Physical outbound/return progress and residual errors are reported separately;
`SAFE_INCOMPLETE` therefore does not automatically mean physical task failure.
The old Rigid 40/80 and 120/120 BRAKE events and old P1 120/120 approximately
222 N physical transient do not persist in the corrected campaign.

P1 compliance is not required for corrected High-ROM feasibility. Its most
consistent independent effect is lower physical-force slew; peak-force,
moment, tracking, deformation, and settling effects remain trajectory- and
history-dependent. The previous strict P1 numerical-qualification FAIL remains
in force and is not relabeled.

The analytic/model-derived High-ROM map uses the registered 1:1 allocator over
q1,q2 = 0–125°. Quasistatic translational force spans 0.06–182.30 N, so the
dense valid domain remains below 200 N. Across the saved decomposition,
static Human mechanics dominate average Human-level demand, nominal reference
dynamics are negligible for these slow trajectories, and the old boundary
excess arises mainly in robot execution velocity feedback. These are auditable
model and saved-evidence statements, not a dynamic capability map or a claim
against learned control.

## Current scientific limits

- Evidence is simulation-only and lies mostly within the representable Human-V2
  family. Out-of-family model inadequacy remains untested.
- Beta is not physical anatomy truth; bound pressure and measured-channel
  compensation are material.
- Interaction values are descriptive. The cuff surface proxy is not pressure,
  comfort, tissue load, or a safety outcome.
- The 200 N force value is a registered simulation engineering stress-test
  target, not a clinical safety threshold or a proven hardware limit. The
  corrected High-ROM cases no longer approach it as the dominant blocker.
- P1 remains an exploratory engineering interface model and has not passed the
  preserved strict numerical-qualification gate.
- The UR10e is a surrogate and does not prove behavior on the CR12.
- Desktop replay is not target-hardware or hard-realtime validation.
- The saved evidence records no safety events, but this is not a clinical
  safety, efficacy, certification, or production claim.
- The crossed sample is deliberately small and fractional; correlations are
  descriptive, and two cases worsened maximum error despite RMSE improvement.

## Canonical entry points and next phase

The complete artifact inventory, experiment-specific conclusions, hashes, and
reproduction commands are in
[`STAGE4_EVIDENCE_MAP.md`](STAGE4_EVIDENCE_MAP.md). Cleanup decisions are in
[`STAGE4_REPOSITORY_MIGRATION.md`](../STAGE4_REPOSITORY_MIGRATION.md).

The corrected High-ROM compact report, comparison JSON, clean-clone/external
archive checksum split, dense force map, compact render sources, pre-correction
diagnostic summaries, and provenance are in
[`phase3a_corrected_high_rom`](../../results/summaries/phase3a_corrected_high_rom/README.md).
The professor-facing corrected comparison is a single offline file:
[`PHASE3A_RIGID_VS_P1_PROFESSOR_REVIEW.html`](../../results/engineering_validation/PHASE3A_RIGID_VS_P1_PROFESSOR_REVIEW.html).
The final HTML and force-landscape builders consume only tracked clean-clone
inputs; historical raw campaigns are not runtime dependencies of either tool.

Stage 4 and its professor-facing report validation are now closed for this
repository checkpoint. The next phase is hardware preparation: validate the
CR12 command/feedback contract, timing, sensor calibration, cuff/contact
mechanics, supervisory safety, and emergency-stop behavior before any
deployment claim. An optional, separately preregistered model-inadequacy study
may vary one unsupported mechanism at a time with this controller frozen.

## Professor-report validation closeout

After `stage4-robustness-final-v1`, a separate professor-facing simulation study
completed the frozen PD/PD+FF/Fixed/Adaptive baseline, three-seed patient
generalization, and descriptive trajectory demonstrations without changing the
Stage-4 controller. Audited evidence and five final media sets are indexed in
[`STAGE4_REPORT_VALIDATION_EVIDENCE_MAP.md`](STAGE4_REPORT_VALIDATION_EVIDENCE_MAP.md).
The next engineering phase is hardware preparation and robot-only commissioning;
model-inadequacy and controller-limit studies remain optional, separately
preregistered scientific extensions.
