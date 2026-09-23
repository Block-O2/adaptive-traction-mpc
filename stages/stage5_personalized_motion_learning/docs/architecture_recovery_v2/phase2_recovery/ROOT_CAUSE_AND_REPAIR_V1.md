# Phase-2 Recovery Root Cause and Repair V1

Status: **DEVELOPMENT REPAIR QUALIFIED; INDEPENDENT FREEZE AUDIT PENDING**

## Root cause

The formal V2 failure showed that accumulated continual beta refits improve
difficult tails but often have little authority after an informative eight-second
commissioning probe. The batch fit weights the entire probe/task history, so a
new task operating region may be diluted by older probe rows. Because the
11-dimensional beta is also a control-effective representation under small
geometry mismatch, the remaining task-local generalized-torque error is not
guaranteed to vanish merely by accumulating more global rows.

## Approach 1: bounded recency window

A causal bounded history window was added as an optional, versioned task-phase
identifier mode. Windows of 200, 300, and 400 samples and task smoothing values
0.10, 0.20, and 0.30 were screened on eight new balanced development cases.

All variants completed 8/8, but the best median improvement over
commissioning-only was only 8.77%. Several cases improved while others
regressed. This is mixed/negative evidence: recency alone did not resolve the
formal root cause and is not enabled in the candidate architecture.

## Approach 2: task-local residual adaptation

The selected repair estimates the remaining causal generalized-torque residual
from the same deployable pose/twist history and previously applied wrench. It:

1. performs the existing bounded beta update;
2. computes `tau_applied - Y(q,dq,ddq) beta` after that update;
3. applies an EWMA with alpha `0.20`;
4. caps each generalized residual at `+/-12 Nm`;
5. presents the residual to MPC as an additive control-effective torque term;
6. leaves the physical beta estimate, plant truth, geometry fit, force
   allocation, task, cost, constraints, horizon, and optimizer unchanged.

The implementation uses the two constant `-rho` regressor columns only as an
exact numerical embedding into the existing batched model. The residual remains
separately logged and is not claimed to be an anatomical rest-angle estimate.
Hidden setup truth is not an input.

Alpha values 0.05, 0.10, 0.20, 0.30, and 0.50 were screened on the same eight
development cases. Improvement saturated as alpha increased; alpha 0.20 was
selected as the least aggressive value near the plateau before the independent
confirmation set was run.

## Independent development confirmation

Sixteen new balanced cases used seeds `312001..312016` and task seeds
`322001..322016`, disjoint from the failed formal cases and the screening set.

- adaptive: 16/16, median 0.4651 deg, p95 1.0377 deg;
- commissioning-only: 13/16, median 0.8010 deg, p95 4.3463 deg;
- median improvement: 41.94%;
- adaptive peaks: 137.77 N / 33.33 Nm;
- adaptive ROM, clearance, solver, and safety events: zero.

The exact-current six-arm freeze qualification passed every unchanged
formal-style gate:

- oracle 16/16, median 0.4089 deg;
- adaptive 16/16;
- fixed nominal 0/16;
- wrong geometry + adaptive dynamics 4/16;
- no dynamics adaptation 5/16;
- commissioning-only 13/16.

Result:
`results/architecture_recovery_v2/phase2_recovery/residual_bias_freeze_qualification_v3/result.json`,
SHA-256 `1c7ac1e69f4842567605568fd934afbbaa6f483211bf10cce672195140274d45`.
The exact stripped Git-status hash was
`af092bfd10b0c567eb863b84149d969a1c7eb6343e05b31e7699ad4e36ce48d0`
before and after the run. The runner reported no source/config drift.

No adaptive residual reached its cap. Maximum observed absolute residual was
8.4842 Nm and total cap-hit count was zero. Across adaptive rows, the maximum
single update was 1.6836 Nm, the maximum per-case accumulated L1 variation was
32.9459 Nm, and all final residuals were finite and inside the 12 Nm component
bound. The 16 adaptive cases contained 8,770 updates and 121 component sign
reversals. These are audit diagnostics only and do not enter action selection.

## Same-case layer-necessity ablation

The exact same 16 confirmation cases were rerun with recency, task smoothing,
and residual adaptation all explicitly disabled. The legacy continual-beta path
completed 15/16 with median 0.5668 deg and p95 3.5659 deg. The selected residual
path completed 16/16 with median 0.4651 deg and p95 1.0377 deg. Its force and
moment maxima also decreased from 143.03 N / 35.20 Nm to
123.42 N / 33.33 Nm. This isolates a material tail and completion benefit from
the residual layer on the frozen development cases; it is not held-out formal
evidence.

The focused architecture-recovery suite passed 27 tests. Added checks cover the
bounded non-mutating causal update, physical-beta separation, arm isolation,
evaluation-only truth perturbation invariance with the residual both enabled
and disabled, and fail-closed Git-status sealing.

## Failed/interrupted development attempts

Two initial residual-bias screening jobs used a wrapper that forced the scalar
MPC path. They were manually interrupted after several minutes before producing
result files. Their empty versioned output directories are retained; no formal
evidence was affected. The mathematically equivalent residual was then embedded
in the existing base-parameter batch representation and regression tested.

## Freeze condition

The candidate may be frozen as V2.1 only after independent Auditor confirmation
that the residual is causal, truth-firewalled, comparison-fair, mechanically
valid, and not an invalid reinterpretation of beta. A fresh formal retry must
use a new preregistration, namespace, salt, seeds, exact live Git-status seal,
and the unchanged V2 gates.
