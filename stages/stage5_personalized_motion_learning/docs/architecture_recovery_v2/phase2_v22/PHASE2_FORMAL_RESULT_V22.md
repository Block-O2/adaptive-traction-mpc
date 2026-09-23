# Architecture Recovery V2.2 Fresh Phase-2 Formal Result

Status: **PHASE_2_PASS**

The formal result is preserved at
`results/architecture_recovery_v2/phase2_v22/formal_unknown_setup_task_v22/result.json`,
SHA-256 `bef5169580a7038d51f5f402096cfe95545cdd8655c9e200b6c627770f446cf2`.
All 168 preregistered rows ran: seven arms by 24 paired fresh cases. All 46
frozen checks passed. The independent Auditor reproduced the row counts,
metrics, gates, seed pairing, source/config manifests, execution seal, and
truth-firewall checks before issuing the authoritative `PHASE_2_PASS` verdict.

## Frozen-gate outcome

| arm | completion | full-horizon median / p95 RMSE | full-episode peak force / moment |
|---|---:|---:|---:|
| oracle | 24/24 | 0.424069 / 0.622307 deg | 172.948 N / 29.919 Nm |
| V2.2 state residual | 24/24 | 0.477010 / 0.701653 deg | 172.948 N / 29.955 Nm |
| V2.1 diagnostic, non-gating | 24/24 | 0.469487 / 0.702720 deg | 172.948 N / 29.954 Nm |
| commissioning-only | 23/24 | 0.606653 / 1.951041 deg | 172.948 N / 29.990 Nm |
| no dynamics adaptation | 6/24 | 3.246108 / 7.931287 deg | 172.948 N / 36.716 Nm |
| wrong geometry + adaptive dynamics | 4/24 | 3.441101 / 6.513867 deg | 172.948 N / 37.142 Nm |
| fixed nominal | 0/24 | 10.124066 / 14.634142 deg | 172.948 N / 35.564 Nm |

V2.2 improved commissioning-only median RMSE by `21.3701%`, clearing the
unchanged `20%` branch. Its completion advantage was only `4.17%`, so the
median branch is the valid and narrow passing branch. Candidate minus oracle
median RMSE was `0.05294 deg`. V2.2 and oracle had zero registered clearance,
ROM, consistency, settle-timeout, solver, supervisor, and safety events.

The V2.1 diagnostic median was about `1.60%` lower than V2.2, while V2.2 p95
was about `0.15%` lower. V2.1 was frozen as non-gating. The Phase-2 result
therefore does not support a broad claim that V2.2 outperforms V2.1; it supports
only the preregistered V2.2 formal gates.

## Adaptation integrity and firewall

- Every V2.2 row reports `deployable_truth_consumed=false`.
- All 569 task beta update attempts were accepted.
- The frozen five-feature state representation, continual beta update, and
  previous-sample/next-action causality were present in every candidate row.
- Peak residual was `3.9535 Nm`; peak coefficient-row L2 norm was `3.1220 Nm`.
- Maximum coefficient step was `0.4580 Nm`, maximum weight total variation was
  `22.3376 Nm`, and maximum residual total variation was `15.9593 Nm`.
- There were zero coefficient projections and zero observed, prediction, or
  selected-rollout output-cap hits.
- Hidden setup was limited to generation, plant, oracle, evaluation, and
  post-run diagnosis.

The ten-file execution seal is
`d87c6c127819c96f794600e48534a00ab30a49cb24a0c06f9697ed091daf9298`.
All 62 source snapshots validated. The exact branch/HEAD and normalized dirty
status remained unchanged during the run; the status hash was
`af092bfd10b0c567eb863b84149d969a1c7eb6343e05b31e7699ad4e36ce48d0`.

## High-ROM boundary

The 12 fresh high-ROM candidates covered goal q1 `66.244--74.175 deg` and q2
`82.234--94.575 deg`; every V2.2 and oracle case completed with zero registered
ROM or analytical shank/flat-bed clearance events. This is formal simulation
evidence only inside the verified Human-V2 `80/100 deg` hard limits. It does
not validate 120--130 deg, physical collision/contact, CR12 reachability, or
clinical/hardware safety.
