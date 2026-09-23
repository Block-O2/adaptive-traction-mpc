# Phase-Banked Residual Development Preregistration V1

Status: **FROZEN BEFORE CASE GENERATION OR OUTCOMES**

The V2.1 formal failure is preserved and its 24 cases are excluded from this
development comparison. The hypothesis is that a single task-wide constant
residual conflates three known reference regimes. The candidate uses three
zero-initialized banks selected only by the registered deterministic reference
phase: outbound, hold, and return. Only the bank active during the causal prior
interval is updated. There is no learned detector, velocity threshold,
deadband, or hidden-truth input.

Everything else is fixed: residual alpha `0.20`, component cap `+/-12 Nm`,
beta estimator/update path, effective geometry, probe, observations, task
domain, generation, MPC cost/horizon/constraints/solver, and reference phase
boundaries.

## Design and budget

- namespace: `ARV2-P2-RECOVERY3-DEV1`;
- 24 paired cases: four profiles x standard/high ROM x three replicates;
- paired arms: V2.1 single residual (`adaptive`), three phase banks
  (`adaptive_phase_banked_residual`), commissioning-only, and oracle;
- exactly 96 development rollouts;
- same continuous hidden and mechanics-conditioned generation domain as V2.1;
- full denominator, no replacement or outcome-dependent exclusion;
- no alpha, cap, phase-boundary, detector, cost, or gate tuning on this set.

## Preregistered decision

The phase-bank candidate is eligible only if all are true:

1. completion is not below V2.1;
2. aggregate median RMSE is strictly below V2.1;
3. aggregate p95 RMSE is no worse than V2.1;
4. against commissioning-only, it achieves at least 20% median improvement or
   at least 0.25 completion-rate advantage;
5. completion at least 0.90, median/p95 at most 3/5 deg, adaptive-oracle median
   gap at most 2.5 deg, full-episode force/moment at most 200 N/60 Nm, and zero
   clearance, ROM, consistency, settle, solver, and safety events;
6. all residuals are finite and within the frozen bound.

Median RMSE in the first 0.5 s after hold entry and return entry is reported as
a mechanism diagnostic, not an additional promotion gate. If the candidate
fails, it is preserved and rejected without post-hoc thresholds.

