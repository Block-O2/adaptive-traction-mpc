# DEV-C file ownership and reproducibility

Paths below are under `stages/stage5_personalized_motion_learning/`.
This task began on `codex/stage5-architecture-recovery` at
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`; the exact 609-path
pre-existing dirty/untracked inventory is in `GIT_ENTRY.json`. It is not
DEV-C-owned. No prior DEV-A, DEV-B, formal qualification, or Stage-4 result
artifact was deleted or rewritten.

## DEV-C production/control application

- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/bumpless_transfer.py`:
  new finite action-level transfer manager.
- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py`:
  integration at initial accepted-model activation and task-period promotions,
  explicit opt-in default False, transfer tracing; this full-3D runtime was an
  untracked local dependency at DEV-C entry, so Git HEAD alone cannot show a
  line diff of its DEV-C portions.
- `src/traction_mpc_stage5/human_waypoint_shadow.py`:
  optional post-inverse-dynamics/pre-allocation action transform, default None.
- `configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1.json`:
  original fixed-duration development config, preserved after adverse result.
- `configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v2.json`:
  action-gap-scaled duration development config used for the 24-case replay;
  frozen output gates remain identical to v1.
- `configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v3.json`:
  development-only output-envelope revision; preserved failed representative
  session, not promoted. `run_executed_case` defaults DEV-C to False and
  rejects it for formal qualification.

## DEV-C diagnostics/tests

- `scripts/run_dev_c_matched_v1.py`
- `scripts/analyze_dev_c_matched_v1.py`
- `scripts/run_dev_c_development_batch_v1.py`
- `scripts/summarize_dev_c_regression_v1.py`
- `tests/full3d_adaptive_integration_v1/test_dev_c_bumpless_transfer.py`

## DEV-C documentation

- `docs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/`
  contains `GIT_ENTRY.json`, `CONTINUITY_FREEZE.md`, `DESIGN_REVISIONS.md`,
  `TRANSFER_DESIGN.md`, `MATCHED_STATE_RESULTS.md`, `DEV_C_REPORT.md`,
  `STATUS.md`, `COMMANDS.md`, `AUDIT_REPORT.md`, `CHANGED_FILES.md`, and
  `GIT_EXIT.json` as they are completed.

## Local ignored result evidence

- `results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/`
  contains all direct/bumpless matched traces, adverse v1/v2/v3 iterations,
  v3 fail-closed session, plot PNGs, and the consumed 24-case development regression.
  This namespace is Git-ignored by Stage-5 `.gitignore` and is **not**
  available in a clean clone by default.

No files were staged, committed, pushed, reset, stashed, or deleted. The
current full-3D stack still has many uncommitted/untracked dependencies beyond
DEV-C; no clean-clone reproducibility claim is made.
