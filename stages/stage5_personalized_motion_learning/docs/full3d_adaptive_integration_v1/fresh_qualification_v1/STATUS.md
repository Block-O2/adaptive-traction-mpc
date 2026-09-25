# Fresh full-3D qualification V1 — restart checkpoint

Date: 2026-09-23. Branch `codex/stage5-architecture-recovery`; starting HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. Existing worktree was
heavily dirty at start; no Git mutation is authorized or performed.

Phase: **TERMINAL — `FULL3D_FRESH_FAILED_WITH_EVIDENCE`**. Independent Auditor gave a
pre-freeze PASS. `FREEZE_MANIFEST.json` sealed 309 source/config/asset paths
on the recorded branch/HEAD; `FREEZE_GIT_STATUS.txt` records the complete
dirty state. Independent Auditor sealed uint64 seed `18386242844751736710`
after hash verification; `SEED_MANIFEST.json` SHA-256 is
`e6352b342f63ac20582b631597ec37fbe5bc0e05ee840f6cd359ba8da44a3b9c`.
The frozen generator accepted 24/34 proposals (10 rejected; 70.59% acceptance)
for the balanced 4×3×2 keys. All 72 paired arm outputs are now preserved and
hashed by `formal_paired_v1/STATUS.json`; the frozen `ANALYSIS.json` reports
0/24 COMPLETE in each arm, 3 case keys with three-arm pre-step runner
exceptions, and gates g2–g7 false. g1 is accounting/provenance-pre-audit only.
No frozen source/config/gate/seed was modified after held-out exposure.
`FINAL_AUDIT.md` gives result-integrity PASS and scientific qualification
FAIL: 63 physical episode artifacts plus nine pre-step exceptions, all retained.
Historical states remain
`FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE` and
`PLANNER_RUNTIME_QUALIFIED`; neither is superseded yet.

Development artifacts retained:

- `development_nominal_01`: ABORTED / SESSION_CLEARANCE_LIMIT after candidate
  injection bypassed the registered loaded-support equilibrium; source corrected.
- `development_nominal_02`: COMPLETE under timing-aware CR12 execution; 976
  task intervals / 977 boundaries; three task phases; no task shank-bed
  contact/ROM/acceleration violation. This predates subsequent initial-support
  fix and is development-only.
- `development_generated_01`: seed 4711001, 24 accepted from 30 proposals,
  subsequently found to double-count the 62 mm hip height in the static
  generator clearance. Retained as invalid development generation, never formal.
- `development_generated_02`: same development-only seed with corrected hip
  convention, 24 accepted from 42 proposals (18 static-clearance rejections).
  This seed is forbidden for held-out.
- `development_varied_ordinary_01` and `_02`: retained initialization-history
  exceptions. First was fixed by using deployable observed initial support;
  second showed the commissioning first waypoint must hold that same observed
  state for the initial history warmup. `_03` then executed physical
  commissioning but aborted at unsettled task handoff; not excluded.
- `development_varied_upper_01`: physically executed upper-current-ROM
  development task, then ABORTED / TASK_VELOCITY_LIMIT at 0.380 s task time.
- `development_nominal_03` and `_04`: COMPLETE after later source changes;
  `_04` independently time-aligned in the analyzer, 13 decisions and no
  deadline miss, with full beta/residual history and explicit actual activation.
- `development_fixed_nominal_02`: COMPLETE; fixed arm skips commissioning fit,
  has 0 task adaptive updates and `FIXED_NOMINAL` clearance/belief provenance.
- `development_commissioning_only_nominal_01`: ABORTED /
  SESSION_CLEARANCE_LIMIT, retained; frozen arm continues no task updates.
- `development_watchdog_stale_01`: injected 110 ms development-only planning
  delay, ABORTED / STALE_PLAN_MAXIMUM_AGE after 20 actual 5 ms intervals
  (400 MuJoCo steps; 21 boundaries); zero plan activations.
- `development_watchdog_infeasible_01`: retained analyzer exception from a
  missing failure-continuity field, corrected without altering controller
  semantics. `_02`: injected no-feasible decision, ABORTED /
  NO_FEASIBLE_WAYPOINT after seven actual 5 ms intervals (140 MuJoCo steps;
  eight boundaries); zero plan activations and no false deadline miss.
- `development_nominal_05`: COMPLETE after watchdog/provenance repair, 974
  task intervals / 975 boundaries, 13/13 actual plan activations, zero
  deadline misses, task minimum true clearance +6.59 mm, no task contact or
  ROM event; q RMSE 0.640 deg, q p95 1.408 deg. Its dq RMSE 7.903 deg/s is
  above preregistered-draft gate 5 (5 deg/s), an explicit adverse development
  prediction. The gate is not raised to accommodate this result.

Last targeted post-watchdog test sweep: 14 passed. Independent Auditor passed
the injected watchdog diagnostics, normal nominal physical run, source
provenance and pre-freeze review. No formal held-out outcome has been viewed.

Frozen V1 implementation: versioned hidden physical Human/hip/
cuff variation, case-specific task and commissioning waypoints, three paired
arms, evaluation-only every-physics-step true shank/bed clearance and contact,
and unchanged 100 ms timing-aware planner contract. Numerical gates are frozen
in `PREREGISTRATION.md`; no formal results exist yet.

Completed: Auditor verified the generated case bundle; Builder executed all
72 paired arms using `run_fresh_full3d_batch_v1.py` with checkpoint/resume.
The sealed bundle is under
`results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1`
and paired outputs under the sibling `formal_paired_v1`. Exact formal command
from repository root (after Auditor case-bundle PASS):

```bash
env MPLCONFIGDIR=/tmp/full3d_fresh_v1_mpl PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_fresh_full3d_batch_v1.py --case-bundle stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1
```

Do not rerun completed paired arms. `STATUS.json` in the paired output records
per-arm SHA-256 and `remaining_case_keys=[]`; `ANALYSIS.json` is the frozen
time-aligned analysis. `FORMAL_RESULT_REPORT.md` gives the current findings.
No action remains in this V1 qualification. Any repair needs separate
development, new version and fresh future held-out seed namespace. Do not
rerun this held-out set or reinterpret its failures as qualification success.
