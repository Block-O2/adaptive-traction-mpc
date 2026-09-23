# Architecture Recovery V2 Phase-2 Formal Result V2

Status: **PHASE_2_FAIL**

This result is immutable formal held-out evidence. It must not be rerun, tuned
against, relabeled as PASS, or replaced.

## Provenance

- result: `results/architecture_recovery_v2/phase2/formal_unknown_setup_task_v2/result.json`
- result SHA-256: `21f32c73b44ee7143b702214b69959fc3014cb7bc54bc700555da497903182c5`
- config SHA-256: `50343db39266aeb4bdd6511ea2798a65a440a57f3ad7f71d883304eda4b1341a`
- branch / HEAD: `codex/stage5-architecture-recovery` / `4caea258ec1450f082bb7cb8097cc1441bdf589f`
- matrix: 24 hidden cases x 6 paired arms = 144 rows
- source/config drift during run: none
- formal cases generated: 24/24 from 27 proposals; three rejected proposals
  failed the preregistered clearance screen; no formal case was excluded or
  replaced.

The independent Auditor recomputed all HMAC seeds, matched all 59 sealed
source/config hashes, verified the complete paired matrix, and found no
deployable simulation-truth consumption.

The execution seal's pre-recorded Git-status hash did not match the live status
hash at launch. The difference was limited to the pre-existing `AGENTS.md`
staged/unstaged state; every behavior-relevant source/config hash matched and
the live status was unchanged during the run. This does not explain the
scientific result, but a future formal runner must fail closed on this mismatch.

## Frozen-gate outcome

Exactly one gate failed: `adaptive_beats_commissioning_only`.

| Arm | Completion | Median RMSE | p95 RMSE |
|---|---:|---:|---:|
| oracle | 24/24 | 0.4441 deg | 0.5714 deg |
| adaptive | 23/24 | 0.5566 deg | 1.8781 deg |
| commissioning-only | 23/24 | 0.6153 deg | 3.4666 deg |
| fixed nominal | 0/24 | 8.7928 deg | 15.2559 deg |
| wrong geometry + adaptive dynamics | 3/24 | 8.3314 deg | 18.9661 deg |
| no dynamics adaptation | 6/24 | 2.5702 deg | 8.3730 deg |

Adaptive passed completion, median/p95, oracle-gap, force/moment, mechanics,
ROM, clearance, solver, and safety gates. Its full-episode peaks were 156.07 N
and 31.72 Nm. It materially beat fixed, wrong-geometry, and no-dynamics arms.

The commissioning-only gate nevertheless failed because:

- completion margin was `0.0`, below `0.25`;
- commissioning-only had 23 rather than 24 full-horizon metrics, making the
  preregistered median branch ineligible;
- diagnostically, the available median reduction was only 9.55%, below 20%.

Continual adaptation improved 16 of 24 paired cases and reduced p95 by 45.8%,
but did not demonstrate broad median dominance. The shared failed high-ROM
coordinated case had insufficient commissioning excitation and remained a
tracking failure after task updates. This is a scientific FAIL, not a mechanics
or software-runtime failure.

## Required consequence

Phase 3 is not authorized from this result. The failed artifact is preserved.
The campaign returned to new development cases, retained the same observations,
unknown set, hidden domain, baselines, and formal gates, and required a fresh
future held-out namespace after any independently frozen repair.
