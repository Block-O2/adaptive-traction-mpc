# Phase 1B-F Gate Addendum V1

Status: **FROZEN BEFORE V2 QUALIFICATION OUTCOMES**

The first `freeze_qualification_v1` result passed its configured gates. The
first `continual_adaptation_ablation_v1` run was launched without a machine-
evaluated ablation gate and is retained as diagnostic evidence only. Independent
Auditor review identified the omissions before Builder used that run for a
freeze decision.

This addendum freezes the following additional requirements before the V2
qualification and ablation outcomes are generated:

## Combined freeze qualification V2

- Same paired 16-case x 5-arm development matrix and quantitative thresholds as
  V1.
- Adaptive and oracle must each have zero probe settle timeouts.
- Exact post-probe constructed-reference clearance must be present for all 16
  adaptive and all 16 oracle rows, with zero violations.
- Every attempted dynamics update must log phase/time, acceptance/rejection,
  reason, mass-matrix margin, old/raw/trusted residual, frozen parameter names,
  and applied beta.

## Continual-adaptation ablation V2

- Exact paired 8-case x 3-arm matrix.
- Continual adaptive must complete and execute the full horizon in 8/8.
- Every continual row must evaluate actual and exact post-probe reference
  clearance; all post-probe-reference, probe/task-clearance, probe/task-ROM,
  consistency, settle-timeout, solver, and safety counts must be zero.
- Full-episode force/moment must remain at most 200 N/60 Nm.
- Continual adaptation must show benefit over commissioning-only by either:
  at least 20% full-horizon median RMSE improvement when all comparator rows
  have full-horizon metrics, or at least 0.25 completion-rate advantage.
- Continual adaptation must show benefit over no dynamics adaptation by either:
  at least 20% full-horizon median RMSE improvement when all comparator rows
  have full-horizon metrics, or at least 0.50 completion-rate advantage.

The thresholds are development freeze criteria, not fresh held-out claims. No
Phase-2 seed/config/outcome has been generated or viewed.
