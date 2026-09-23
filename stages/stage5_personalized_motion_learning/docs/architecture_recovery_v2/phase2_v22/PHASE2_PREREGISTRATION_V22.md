# Architecture Recovery V2.2 Fresh Phase-2 Preregistration

Status: **DOMAIN, ARCHITECTURE, GATES, BUDGET, AND EXCLUSIONS FROZEN BEFORE OUTCOMES**

Recorded: 2026-09-22, Asia/Shanghai.

## Preserved prior evidence

Both `ARV2-P2-V2` and `ARV2-P2-V21` remain authoritative `PHASE_2_FAIL`
results. Neither is reclassified, rerun, or used as fresh evidence. The V2.2
state-conditioned residual is frozen by
`phase2_recovery/FREEZE_MANIFEST_V2_2.json`, SHA-256
`dd92a4b7601f01866e3e48591228904457a827b1ebc62481435bf50ee2e12b81`.

## Frozen V2.2 architecture and question

Does frozen V2.2 adaptive MPC remain functionally effective across fresh
hidden continuous patient/setup/task variation and materially outperform fixed,
wrong-geometry, no-adaptation, and commissioning-only controls without
deployable hidden truth?

V2.2 preserves V2.1 and replaces only its constant task residual with the
independently qualified state map `[1,q1_ROM,q2_ROM,dq1_sat,dq2_sat]`.
Velocity scale is `1 rad/s`, normalized-LMS alpha is `0.20`, coefficient-row L2
limit is `12 Nm`, and observed/predicted output limit is `+/-12 Nm`. Continual
beta remains active and the residual update uses post-beta previous-sample
innovation with next-action causality. No architecture, estimator, probe,
reference, domain, formal gate, budget, or exclusion change is permitted after
this preregistration and seed seal.

- evidence: formal held-out;
- exactly 24 paired cases;
- four profiles x standard/high ROM x three replicates;
- seven arms per case, 168 rollouts total;
- gating arms: oracle, V2.2 state residual, fixed nominal, wrong-geometry
  adaptive dynamics, no dynamics adaptation, commissioning-only dynamics;
- V2.1 constant residual is an extra diagnostic arm and cannot affect PASS;
- no pilot, tuning, replacement, threshold revision, or case exclusion.

## Frozen domain and mechanics

The continuous hidden domain, task profiles, noise, timing, mechanics, and
generation policy are byte-for-byte the same values as V2.1: height
`[0.88,1.12]`, mass `[0.78,1.28]`, passive stiffness `[0.65,1.45]`, damping
`[0.70,1.35]`, recorded rest/COM/hip/cuff/initial/goal/duration ranges, pose
noise `0.00015 m / 0.03 deg`, ideal simulated twist derivative, bed height
`0.012 m`, shank radius `0.045 m`, minimum analytic reference clearance
`0.025 m`, static generation screen `150 N / 45 Nm`, and at most 5,000 setup
draws for each fixed task draw. Hidden clearance is evaluated at no more than
0.005 s intervals. Conditional attempts and rejection causes are reported.

## Unchanged formal gates

V2.2 candidate: completion at least 0.90; full-horizon median/p95 RMSE at most
`3/5 deg`; full-episode force/moment at most `200 N / 60 Nm`; zero reference,
probe, or task clearance/ROM violations; zero consistency aborts, settle
timeouts, solver failures, and safety aborts.

Oracle: completion exactly 1.0; the same zero-event and wrench gates; candidate
minus oracle median RMSE at most 2.5 deg.

Candidate comparison passes against fixed nominal, wrong geometry, and no
dynamics if completion advantage is at least 0.50 or median improvement is at
least 20%. It passes against commissioning-only if completion advantage is at
least 0.25 or median improvement is at least 20%. Every configured arm must
contain all 24 unique paired keys and every candidate/oracle row must have
complete full-horizon metrics. V2.1 diagnostic outcomes have no pass/fail role.

Every V2.2 residual and weight must be finite and bounded. Feature contract,
continual-beta enablement, coefficient projection, observed-output clipping,
prediction-dynamics clipping, chosen-rollout clipping, norm/max-step/variation,
and residual variation/sign reversals are mandatory integrity diagnostics.

## Exclusions, truth firewall, and terminal rule

There are no post-generation exclusions or replacements. Generation failure,
missing metrics, abort, contact, ROM, solver, safety, or timeout remains in the
denominator. Hidden truth may enter only generation, plant, oracle, evaluation,
and post-run diagnosis; it may not enter deployable state, geometry/Jacobian,
beta/residual update, prediction, candidate generation, action selection, or
promotion.

The study is `PHASE_2_PASS` only if every unchanged formal gate and V2.2
integrity check passes. Any failure is preserved as `PHASE_2_FAIL`; no tuning
may use these formal cases.
