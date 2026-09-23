# Architecture Recovery V2.1 Freeze Candidate

Status: **PHASE 1B-F PASS — BUILDER AND INDEPENDENT AUDITOR FREEZE**

Recorded: 2026-09-22, Asia/Shanghai.

## Frozen change from V2

V2.1 retains the accepted effective-geometry fit, bounded dynamic
base-parameter identifier, commissioning probe, mechanics-conditioned task
domain, reference generator, MPC cost, constraints, horizon, and solver. It
adds one task-local two-dimensional generalized-torque residual:

- sample: previous applied generalized torque minus the current causal
  regressor prediction;
- inputs: estimated pose/twist history, finite-difference acceleration, and the
  previously commanded cuff wrench;
- update: EWMA alpha `0.20`;
- bound: componentwise `+/-12 Nm`;
- use: control-effective MPC prediction only;
- physical beta: unchanged and separately logged;
- enabled arms: adaptive and wrong-geometry adaptive-dynamics only.

Task recency windows and alternate task smoothing are explicitly disabled.
The residual is not an anatomical stiffness/rest-angle estimate.

## Evidence

Exact-current qualification completed 16/16 adaptive and 16/16 oracle cases.
Adaptive median/p95 tracking was `0.4651/1.0377 deg`. Task peak interaction was
`123.42 N / 33.33 Nm`; full-episode peak including commissioning was
`137.77 N / 33.33 Nm`. There were zero adaptive clearance, ROM, solver, or
safety events. All unchanged frozen-style gates passed.

On the same 16 development cases, disabling the residual reduced the legacy
continual-beta path to 15/16 and increased p95 from `1.0377` to `3.5659 deg`.
Median improvement was 17.9%. The new layer is retained primarily for the
demonstrated tail/completion benefit, not because of an inflated median claim.

All adaptive residuals were finite and within bounds. Maximum magnitude was
`8.4842 Nm`, maximum update was `1.6836 Nm`, and cap hits were zero. The
focused suite passed 27/27 tests. The qualification's 58-entry live source
manifest, HEAD, and exact stripped Git-status hash were independently checked.

## Freeze decision

Builder and independent Auditor agree that further tuning before fresh formal
evaluation would create more overfitting risk than benefit. V2.1 is frozen for
the next Phase-2 held-out campaign. No architecture, estimator, task domain,
mechanics domain, quantitative gate, or formal budget may change after the
fresh seed manifest is sealed.

## Explicit scope and risk

This is a conditional planar reduced-Human-V2 simulation architecture, not a
hardware-ready controller. Its deployable observation assumption currently
includes ideal noiseless simulated cuff twist and finite-difference
acceleration. Sensor noise, latency, robot/interface dynamics, real OnRobot HEX
frame loads, and physical CR12 execution remain outside this freeze claim.

