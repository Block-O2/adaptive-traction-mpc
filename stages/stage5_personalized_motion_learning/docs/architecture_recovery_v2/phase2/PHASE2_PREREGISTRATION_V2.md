# Architecture Recovery V2 Phase-2 Preregistration V2

Status: **DOMAIN/GATES/BUDGET FROZEN — HIDDEN SEEDS NOT YET GENERATED**

Recorded: 2026-09-22, Asia/Shanghai.

## Frozen architecture

Phase 1B-F passed Builder and independent Auditor review. The architecture is
sealed by `phase1bf/FREEZE_MANIFEST_V1.json`, SHA-256
`81fe92d47c18bdc003c1b17aca266192ed562f64cf73e9991c93fff0df565e44`.
No controller, estimator, probe, reference, mechanics-domain, task-domain, or
gate tuning is permitted after hidden seed generation.

Phase-2-only force/moment exposure and runtime logging was added after the
freeze qualification. A deterministic frozen-case replay matched every
behavior field, including tracking, wrench peaks, dynamics path, and accepted
update times. The logging does not change action selection.

## Scientific question

Does the frozen control-effective adaptive MPC remain functionally effective
across fresh hidden continuous patient/setup/task variation, and materially
outperform fixed/wrong/no-adaptation controls where adaptation matters, without
deployable access to hidden simulation truth?

This study does not require recovery of individual physical parameters and
does not establish hardware readiness.

## Formal budget and balanced design

- Evidence category: `formal_held_out`.
- Case count: exactly 24.
- Cells: four task profiles x standard/high-ROM x three replicates.
- Arms per case: six.
- Total formal rollouts: 144.
- No pilot, tuning, case replacement, or threshold revision after outcomes.

Task profiles:

1. `coordinated`;
2. `hip_lead`;
3. `knee_led_clearance_constrained_v1`;
4. `two_rate`.

Arms:

1. oracle;
2. frozen adaptive;
3. fixed nominal;
4. wrong/fixed geometry with adaptive dynamics;
5. no dynamics adaptation;
6. commissioning-only dynamics.

## Explicit continuous hidden domain

- patient height scale: `[0.88, 1.12]`;
- patient mass scale: `[0.78, 1.28]`;
- passive stiffness scale: `[0.65, 1.45]`;
- passive damping scale: `[0.70, 1.35]`;
- rest offsets q1/q2: lower `[-4,-5] deg`, upper `[5,6] deg`;
- thigh COM scale: `[0.88, 1.12]`;
- shank COM scale: `[0.86, 1.14]`;
- hip X placement: `[-0.12, 0.12] m`;
- hip Z placement: `[0.045, 0.16] m`;
- cuff fraction of full shank: `[0.52, 0.88]`;
- initial q1/q2: lower `[6,10] deg`, upper `[18,28] deg`;
- standard goal q1/q2: lower `[35,48] deg`, upper `[62,78] deg`;
- high-ROM goal q1/q2: lower `[66,82] deg`, upper `[75,95] deg`;
- standard duration: `[9,12] s`;
- high-ROM duration: `[12,15] s`;
- position noise standard deviation: `0.00015 m`;
- angle noise standard deviation: `0.03 deg`;
- cuff twist: frozen ideal noiseless simulated derivative assumption;
- bed height: `0.012 m`;
- shank capsule radius: `0.045 m`.

Mechanics-conditioned generation uses:

- pre-probe reference clearance reserve at least `0.025 m`;
- static generation screen at most `150 N / 45 Nm`;
- generation attempt budget 5000 per fixed task draw;
- actual hidden clearance evaluated every at most `0.005 s`;
- exact arm-specific post-probe constructed-reference clearance logged for
  every arm.

Generation remains a conditional hidden population. Acceptance, attempts, and
rejection causes are reported overall and per profile/ROM cell.

## Seed ownership and commitment

Only after this document and the freeze manifest exist, the independent Auditor
will:

1. create a fresh 256-bit random salt;
2. publish `SHA256(salt)` as commitment;
3. derive setup and task seeds independently with HMAC-SHA256 namespace
   `ARV2-P2-V2` and message fields profile, ROM stratum, replicate, role, retry;
4. map the first eight digest bytes into `[1, 2^31-1]`;
5. rederive only exact collisions or seeds appearing in development configs,
   without generating or inspecting setup/task values or outcomes;
6. seal the salt and explicit 24 pairs in the formal seed manifest.

The Builder must not inspect formal outputs until source/config/preregistration
hashes and the formal command are sealed.

## Exclusions and denominator

- No post-generation exclusion.
- No replacement case after generation exhaustion or any observed result.
- Generation exhaustion, exception, missing metric, timeout, abort, contact,
  clearance, ROM, solver, or safety event remains in the configured denominator
  as a failed row for the affected arm.
- Only pre-generation exact seed collision/development-seed collision may be
  deterministically rederived under the committed seed rule.
- All six arms face the exact same accepted setup/task realization per case.

## Frozen quantitative gates

Adaptive:

- completion rate at least `0.90`;
- full-horizon median RMSE at most `3 deg`;
- full-horizon p95 RMSE at most `5 deg`;
- full-episode peak force at most `200 N`;
- full-episode peak moment at most `60 Nm`;
- zero reference/probe/task clearance violations;
- zero probe/task ROM violations;
- zero consistency aborts and settle timeouts;
- zero solver failures and safety aborts.

Oracle:

- completion exactly `1.0`;
- the same zero-event and 200 N/60 Nm gates;
- adaptive minus oracle median RMSE at most `2.5 deg`.

Adaptive comparison gates use either branch:

- versus fixed nominal, wrong geometry, and no dynamics: at least `0.50`
  completion-rate advantage or at least `20%` full-horizon median improvement;
- versus commissioning-only: at least `0.25` completion-rate advantage or at
  least `20%` full-horizon median improvement.

All expected arms must contain exactly 24 unique paired case keys and every
adaptive/oracle row must contain full tracking and exact-reference metrics.

## Required reporting without post-hoc gates

Report completion, q/dq tracking, p95/tails, peak and cumulative force/moment,
clearance/contact, ROM, solver/safety events, runtime, adaptation convergence,
mass-margin proximity, active-set switching, conditional-generation behavior,
profile/ROM failure modes, and maximum validated high-ROM envelope.

Cumulative exposure, runtime, switching frequency, and hardware-transfer risks
are descriptive in this formal study; no comfort/hardware threshold will be
invented after outcomes.

## Truth firewall

Hidden truth is restricted to generation, plant, explicit oracle arm,
evaluation, and post-run diagnosis. It may not enter deployable state/model,
Jacobian/wrench mapping, candidate generation, prediction, update acceptance,
action selection, or model promotion. The exact-reference clearance audit is
evaluation-only and has a regression proving that changing a positive audit
value cannot change adaptive behavior.

## Phase outcome

The study is PASS only if every frozen gate passes. A FAIL is preserved and
diagnosed; it does not authorize tuning on these 24 cases or rerunning them.
Any legitimate repair returns to development and requires a newly preregistered
future held-out set under a fresh namespace/salt.
