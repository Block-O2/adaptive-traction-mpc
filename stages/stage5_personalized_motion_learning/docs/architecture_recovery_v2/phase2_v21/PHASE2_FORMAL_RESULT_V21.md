# Architecture Recovery V2.1 Fresh Phase-2 Formal Result

Status: **PHASE_2_FAIL**

The formal result is preserved at
`results/architecture_recovery_v2/phase2_v21/formal_unknown_setup_task_v21/result.json`,
SHA-256 `fa27334b9876db38a8bb556026932b23811926b53181d92b721fea6710100275`.
All 144 preregistered rows ran. Source/config drift and Git-status drift were
both false; the stripped status hash remained `af092bfd...`.

## Frozen-gate outcome

Exactly one gate failed: `adaptive_beats_commissioning_only`.

| arm | completion | median RMSE | p95 RMSE | task peak force/moment |
|---|---:|---:|---:|---:|
| oracle | 24/24 | 0.3987 deg | 0.6048 deg | 116.07 N / 24.68 Nm |
| adaptive V2.1 | 24/24 | 0.4597 deg | 0.6923 deg | 116.18 N / 24.75 Nm |
| commissioning-only | 24/24 | 0.5480 deg | 1.0470 deg | 132.99 N / 25.94 Nm |
| fixed nominal | 0/24 | 11.2859 deg | 14.6386 deg | 162.20 N / 34.35 Nm |
| wrong geometry + adaptive dynamics | 7/24 | 4.3643 deg | 6.9732 deg | 140.68 N / 30.01 Nm |
| no dynamics adaptation | 3/24 | 3.8911 deg | 8.7690 deg | 151.13 N / 29.87 Nm |

Adaptive improved commissioning-only median by 16.12%, below the frozen 20%
threshold, while completion advantage was zero. The p95 improvement was 33.88%
but was descriptive and cannot substitute for the frozen median/completion
gate. The result is therefore FAIL despite excellent absolute tracking and
large advantages over fixed, wrong-geometry, and no-adaptation controls.

Adaptive full-episode peak, including commissioning, was 133.57 N / 24.75 Nm.
It had zero clearance, ROM, solver, consistency, settle, or safety events.
Oracle also passed all gates. The residual remained finite and bounded in all
adaptive rows: peak 5.282 Nm, zero cap hits, maximum update 0.445 Nm, and
maximum per-case L1 variation 25.650 Nm.

All 24 cases generated; 31 setup proposals were needed, for conditional
acceptance 0.774. Seven rejected proposals violated the preregistered analytic
clearance screen. No failed case was removed or replaced after generation.

Formal high-ROM goals reached 73.45 deg hip and 94.28 deg knee, within the
previously characterized reduced-plant envelope. The plant remains registered
only to 80/100 deg; requested 120--130 deg joint angles are outside the current
verified plant/ROM contract and were not misrepresented as validated.

## Consequence

This result does not authorize Phase 3. The original V2 formal failure and this
V2.1 failure both remain authoritative negative evidence. The root cause is a
remaining median-benefit shortfall against an already strong commissioning
model, while the task-local constant residual primarily improves tails. Any
repair must return to new development cases and a later fresh held-out
namespace; these 24 cases may not be used for parameter selection or rerun as
formal evidence.

