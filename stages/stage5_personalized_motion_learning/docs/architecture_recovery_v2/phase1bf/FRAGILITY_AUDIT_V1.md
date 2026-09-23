# Phase 1B-F Builder Fragility Audit V1

Status: **BUILDER PASS; INDEPENDENT AUDITOR PASS**

Independent closeout classified the observed active-set transitions as bounded
benign estimator switching, not demonstrated closed-loop chattering, and agreed
that further development tuning now presents greater overfitting risk than
benefit within the declared simulation scope.

Evidence:

- `results/architecture_recovery_v2/phase1bf/freeze_qualification_v2/result.json`
- `results/architecture_recovery_v2/phase1bf/continual_adaptation_ablation_v3/result.json`
- `results/architecture_recovery_v2/phase1bf/freeze_evidence_audit_v1/audit.json`

All evidence is development/freeze-qualification evidence, not fresh held-out or
hardware evidence.

## Freeze-qualification questions

### A. Post-probe mechanical validity

PASS in the current combined family. Adaptive and oracle each evaluated the
exact arm-specific constructed reference in 16/16 cases with zero violations.
Minimum adaptive exact-reference clearance was 50.585 mm; minimum actual task
clearance was 62.493 mm. Probe clearance was narrower at 5.205 mm and remains a
fragility/transfer risk.

### B. Stability after probing/adaptation

PASS. Adaptive completed 16/16 in the combined qualification and 8/8 in the
continual ablation. Combined median/p95 RMSE were 0.9921/2.2927 deg; there were
zero adaptive clearance, ROM, consistency, settle-timeout, solver, or safety
events.

### C. Necessity of continual adaptation

PASS. On the exact paired 8-case matrix, continual adaptive completed 8/8,
commissioning-only 6/8, and no-dynamics 1/8. Continual adaptation met the
predeclared completion-advantage gates against both simpler variants.

### D. Drift, oscillation, and phase-specific failure

No demonstrated instability in the qualified family. Across eight continual
rows, 357 attempted updates were accepted; every applied beta was finite and
inside registered bounds. Accepted minimum mass margin was 0.030384, the 0.03
floor held, maximum applied step was exactly the configured 0.03 span cap, and
trusted residual change was always better than the +0.02 Nm tolerance.

The trace did show 106 mass-margin freezes, 267 conditional freezes, up to 13
frozen-set transitions, nine per-parameter increment sign reversals, and a
maximum normalized path/net ratio of 2.365. These are bounded active-set
switches rather than a demonstrated closed-loop oscillation: every task profile
completed 2/2, all safety gates passed, beta stayed bounded, and residuals
improved. The near-floor margin and switching frequency remain explicit
fragility indicators for future noise/hardware studies.

### E. Combined hidden variation

PASS for the declared conditional simulation family. The 16-case matrix varies
effective dynamics, cuff location, placement, geometry, initial state,
standard/high-ROM stratum, and four task/velocity profiles. Conditional setup
generation accepted 16 cases from 20 proposals. This is not proof outside the
declared domain.

### F. Control sufficiency without oracle geometry

PASS. Adaptive completed 16/16 versus oracle 16/16 while wrong-geometry plus
adaptive dynamics completed 1/16. The representation recovers effective hip,
thigh, and knee-to-cuff geometry without claiming separate full shank length and
cuff-fraction recovery.

### G. Geometry error absorption

No systematic beta absorption was demonstrated. Across 16 development cases,
geometry-error magnitude versus normalized beta error had Pearson correlation
0.0023. Geometry error versus tracking RMSE was 0.629, showing geometry quality
still affects tracking; dynamics adaptation does not erase the need for the
geometry layer. The sample is small, so this is diagnostic rather than proof of
statistical independence.

### H. Probe-induced risk

No registered failure in the validated family: zero contact/clearance, ROM,
consistency, timeout, solver, or downstream corruption event. The probe is the
narrowest-clearance phase (5.205 mm here; 3.955 mm in the retained 96-case
audit), so it remains the dominant mechanics fragility. It also assumes ideal
low-level wrench realization and noiseless cuff twist.

### I. Justification of added layers

Every retained layer maps to preserved evidence: mechanics conditioning fixes
the impossible legacy knee-first family; event settle fixes the 205.3 deg/s
handoff; effective geometry is required by the 1/16 wrong-geometry result;
continual dynamics updates are required by the 8/8 versus 6/8/1/8 ablation; the
mass floor/conditional refit is required by the R3 6/8 to R4 8/8 recovery.

### J. Removability/simplification

Removing continual updates or dynamics adaptation materially degrades
completion. Removing effective geometry fails the combined comparison. The
conditional active set is a bounded repair within the existing identifier, not
a separate learned model. No simpler tested architecture has similar current
capability. Further development tuning now presents more overfitting risk than
demonstrated benefit.

## Layer-by-layer audit

### Mechanics-conditioned generator

- Purpose: exclude analytically impossible contact-free bed tasks.
- Input/output: hidden proposal mechanics and task -> accepted conditional
  development setup plus evaluation record.
- Deployment availability: hidden truth is unavailable; physical deployment
  requires measured/calibrated mechanics-aware planning.
- Failure/observability: distribution shift or incomplete collision model;
  observed by acceptance/rejection, reference certificate, and actual clearance.
- Interaction: upstream of probe/reference; must never enter action selection.
- Simpler replacement: none that preserves explicit impossible-task separation.
- Hardware transfer: necessary concept, but current implementation is not a
  hardware safety layer.

### Bounded knee-led reference

- Purpose: retain knee-leading diversity without the impossible full-knee-first
  shank-down excursion.
- Input/output: start/goal/duration -> smooth outbound/hold/reverse reference.
- Deployment availability: task inputs and certified reference are available.
- Failure/observability: insufficient hip advance or excess speed; observed by
  exact-reference clearance, wrench demand, and execution tracking.
- Interaction: conditions mechanics and excitation seen by adaptation.
- Simpler replacement: coordinated-only motion would shrink task diversity.
- Hardware transfer: requires full collision/reach/comfort certification.

### Event-settled 100 Hz probe

- Purpose: create geometry/dynamics excitation and a safe low-speed handoff.
- Input/output: cuff pose/twist history and applied wrench -> commissioning data
  and settled handoff.
- Deployment availability: assumes measured cuff pose/twist and commanded/applied
  wrench; no hidden truth controls settling.
- Failure/observability: clearance, timeout, poor excitation, inconsistency, or
  high handoff speed; all are logged.
- Interaction: supplies geometry and beta estimators; narrowest mechanics margin.
- Simpler replacement: fixed-time handoff failed at 205.3 deg/s.
- Hardware transfer: ideal wrench/twist assumptions require separate validation.

### Control-effective geometry fit

- Purpose: recover the geometry needed for state inversion and wrench mapping.
- Input/output: cuff pose/orientation history -> hip, thigh length, and
  knee-to-cuff distance.
- Deployment availability: causal cuff observations only.
- Failure/observability: insufficient excitation, residual, condition or bounds;
  explicit acceptance diagnostics.
- Interaction: feeds state estimation, dynamics regressor, model, and MPC.
- Simpler replacement: fixed geometry completed only 1/16 with adaptive dynamics.
- Hardware transfer: calibration/frame errors and cuff compliance remain open.

### Algebraic state estimator

- Purpose: map measured cuff pose/twist through fitted geometry to q/dq.
- Input/output: deployable pose/twist -> estimated joint state.
- Deployment availability: pose channel is plausible; current noiseless twist is
  a frozen simulation assumption.
- Failure/observability: noise/derivative/frame error; partially observable via
  consistency, residual, and state-bound monitors.
- Interaction: drives adaptation, MPC, settle logic, and ROM supervision.
- Simpler replacement: no tested simpler path preserves state-feedback behavior.
- Hardware transfer: filtered/noisy sensing study is mandatory before hardware.

### Continual 11-beta adaptation

- Purpose: maintain control-effective dynamics under hidden setup variation.
- Input/output: estimated q/dq/ddq and applied generalized torque -> bounded beta.
- Deployment availability: uses causal estimated state and applied wrench only.
- Failure/observability: drift, ill-conditioning, mass invalidity or residual
  degradation; per-attempt trace now exposes all.
- Interaction: updates the task-phase prediction model immediately.
- Simpler replacement: commissioning-only lost two of eight cases; nominal lost
  seven of eight.
- Hardware transfer: noise sensitivity and persistent excitation remain open.

### Bound/mass conditional active set

- Purpose: preserve valid inertia while retaining informative non-inertia fits.
- Input/output: joint bounded fit and 0.03 mass audit -> conditionally refit beta.
- Deployment availability: depends only on candidate beta/regressor data.
- Failure/observability: active-set switching, all-frozen fit, residual or mass
  rejection; trace exposes rank, condition, margins, residuals and frozen sets.
- Interaction: limits authority of continual adaptation.
- Simpler replacement: whole-update rejection left two development tails (6/8).
- Hardware transfer: switching under noisy data requires validation.

### Model authority

- Purpose: apply each accepted bounded beta to prediction without a second
  promotion layer.
- Input/output: accepted beta -> current Human prediction model.
- Deployment availability: causal and simple.
- Failure/observability: abrupt updates or model oscillation; controlled by the
  0.03 span step cap and audited trace.
- Interaction: directly changes MPC candidates after accepted updates.
- Simpler replacement: none; adding a promotion layer is unjustified today.
- Hardware transfer: rate/latency and fail-safe fallback remain open.

### Human-space MPC and preview

- Purpose: choose feasible generalized actions for the current estimated model.
- Input/output: estimated state/reference/model -> action and cuff wrench.
- Deployment availability: inputs are causal; execution mapping is abstracted.
- Failure/observability: no feasible action, solver failure, force/moment/ROM
  gate; explicit diagnostics.
- Interaction: consumes every upstream estimate and supplies adaptation wrench.
- Simpler replacement: fixed/nominal baselines fail the declared variation.
- Hardware transfer: does not validate CR12 reach, torque, timing, or interface.

### Mechanics observer and exact-reference audit

- Purpose: independently evaluate reference/probe/task clearance in simulation.
- Input/output: hidden simulated geometry/state -> evaluation-only metrics.
- Deployment availability: unavailable to deployable control; physical system
  needs measured/calibrated collision and safety infrastructure.
- Failure/observability: false confidence from planar shank/flat-bed model;
  limitations are explicit.
- Interaction: terminates evaluation on actual simulated violation but does not
  select adaptive actions. A regression proves positive certificate values
  cannot change adaptive behavior.
- Simpler replacement: removing it would erase mechanics evidence.
- Hardware transfer: current observer is insufficient for physical safety.
