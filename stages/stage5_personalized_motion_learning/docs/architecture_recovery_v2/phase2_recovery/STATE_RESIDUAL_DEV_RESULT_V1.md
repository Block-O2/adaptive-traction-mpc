# State-Conditioned Residual Development Result V1

Status: **FROZEN DEVELOPMENT GATES PASS; INDEPENDENT FREEZE AUDIT PASS**

The sealed 24-case, four-arm matrix executed and recorded all 96 planned rows.
Candidate, V2.1, and oracle completed 24/24; commissioning-only completed 23/24
and preserved one estimated-ROM supervisor safety abort. The authoritative
development result is
`results/architecture_recovery_v2/phase2_recovery/state_residual_dev_v1/result.json`,
SHA-256 `8888d60fddaf943b2c185025e26989de5de7dacf2d3d6c85c4b967901f5462c4`.
All candidate-specific frozen gates passed. The pre-run eight-file seal SHA-256
was `1a51c2538c453aa197255e686da016454c201e967331f77b3ae056aa8ccd3f39`;
source/config and Git-status drift were both false.

| arm | completion | median RMSE | p95 RMSE | full-episode force/moment |
|---|---:|---:|---:|---:|
| oracle | 24/24 | 0.3926 deg | 0.6588 deg | 144.59 N / 26.91 Nm |
| V2.1 constant residual | 24/24 | 0.4647 deg | 0.7935 deg | 144.59 N / 31.42 Nm |
| state residual candidate | 24/24 | 0.4561 deg | 0.7844 deg | 144.59 N / 33.66 Nm |
| commissioning-only | 23/24 | 0.6850 deg | 2.8616 deg | 144.59 N / 32.08 Nm |

The candidate improved aggregate median by 1.86% and p95 by 1.15% versus
V2.1. It was better in 17 paired cases and worse in 7; the median paired RMSE
difference was -0.0040 deg. This is a small effect, but the frozen development
rule required a strictly lower median and no-worse p95, not a post-hoc minimum
effect size. The result is therefore PASS without enlarging the claim.

Candidate force, moment, ROM, clearance, consistency, settle, solver, and
safety gates all passed with zero events. Every weight/output diagnostic was
finite and bounded. Across candidate rows, the maximum observed residual was
8.9434 Nm, maximum coefficient-row L2 norm was 6.6833 Nm, maximum coefficient
step was 0.9034 Nm, and no coefficient projection, observed-output,
prediction-dynamics, or chosen-rollout cap hit occurred. Continual beta remained
active (569 task attempts, all accepted). The residual is claimed only as a
control-effective correction because its q/dq features overlap physical
stiffness/damping columns.

Independent audit reproduced the artifact hash, all 31/31 frozen gate checks,
all 61 source-snapshot hashes, the pre-run seal, and `30 passed` focused tests.
It classified the exact candidate as freeze-eligible while warning that the
effect is small and not uniform. This development PASS is not held-out or
formal evidence and does not authorize Phase 3. Promotion now requires a fresh,
preregistered Phase-2 formal namespace with unchanged formal gates.
