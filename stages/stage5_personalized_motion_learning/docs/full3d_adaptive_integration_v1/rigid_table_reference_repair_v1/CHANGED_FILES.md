# DEV-D change ownership and reproducibility

This task started on `codex/stage5-architecture-recovery` at
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce` with extensive unrelated
pre-existing dirty/untracked files. No stage, commit, push, reset, stash,
branch switch or deletion was performed. Stage-4 modifications, historical
Stage-5 packages, failed qualification, old rigid-table results and unrelated
archives were deliberately left local and untouched.

## DEV-D production-source changes

- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/rigid_table_reference.py`
  — new prior/accepted-geometry hard-table envelope, informative feedback
  commissioning waypoint projection, conservative continuous quintic
  certificate and combined retained-shank clearance. The 3D-to-z-only margin
  optimization is numerically cross-tested, not a scientific simplification.
- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py`
  — pre-existing locally untracked full-3D implementation, augmented with
  default-off DEV-D mode, timing-aware commissioning replanning, causal
  measured sleeve guard, combined recovery/task envelope, failure logging and
  aligned traces. Baseline hash recorded before this stage:
  `a4d0785107cdb4003dc6957943a86cf9cd721fe99aedc6a491f44ce4c47210bb`.
- `src/traction_mpc_stage5/human_waypoint_scheduler.py`
  — already dirty before DEV-D; this stage only added the optional strict
  nonnegative/continuous path certification hooks. The default-off scheduler
  behavior was preserved. The rest of its pre-existing local diff is not
  claimed as DEV-D work.

Final source SHA-256 values in
`results/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/
DEV_D_DEPENDENCY_MANIFEST_V2.json`: runtime
`1a4f48746c0a7dab5b9b4618c54bb8f55eb535c72ea3ff2b01c11cf32f57d3de`,
envelope
`dfe02689c279185fba8a9148ba773d21a4d50a07673049455ea57083cc16bfe5`,
scheduler
`dfcb882cc32eaec45e45730ee0c44c9d3b5265cf67d5ff5d9735bc11f61ff5f2`.

## New DEV-D scripts, tests, config and reports

- `scripts/diagnose_rigid_table_reference_v1.py` — evaluation-only aligned
  requested/estimated/actual gap diagnosis.
- `scripts/run_rigid_table_reference_development_v1.py` — restart-safe coupled
  physical development runner and native contact monitor.
- `scripts/summarize_rigid_table_reference_development_v1.py` — no-exclusion
  aggregate and later explicit V3 deadline-count correction.
- `scripts/plot_rigid_table_reference_development_v1.py` — static, explicitly
  evaluation-only old/new trajectory figures.
- `scripts/profile_dev_d_geometry_v1.py` — isolated geometry microbenchmark.
- `scripts/snapshot_dev_d_dependencies_v1.py` — local source/model/config hashes.
- `tests/full3d_adaptive_integration_v1/test_dev_d_rigid_table_reference.py`
  — geometry, feedback projection, truth-independent cuff pose, optimization
  equivalence, monotone lift and strict scheduler tests.
- `configs/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/
  DEVELOPMENT_CONFIG.json` — declarative final development-mode provenance;
  inherited registered scientific configuration is not overwritten.
- `docs/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/`
  — contract, design, case map, representative/regression/audit reports,
  status, commands, changed-file record, final report and two figures.
- `results/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/`
  — versioned old-path diagnosis, every failed/successful representative
  iteration, the pre-strict and final strict 23-case batches, timing profiles,
  no-exclusion summaries and two local dependency manifests.

The final dependency snapshot hashes 164 broad relevant source/model/config
files; 62 are untracked at this published HEAD. It covers local code/assets,
not a clean clone of the current tree. Per-run manifests record exact case
hash, flags and command but lack a cryptographic source hash captured inside
the execution process; the final snapshot documents final dirty source after
the strict batch. That provenance limitation is explicit, and no clean-clone
reproducibility claim is made.
