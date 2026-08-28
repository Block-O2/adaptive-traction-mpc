# Stage-4 Repository Cleanup Audit

Audit date: 2026-08-28
Baseline: `stage4-baseline-v1` / `ef1fe90e61c5981df8e934585780ce188d104ea4`
Working branch: `codex/stage4-patient-mismatch-robustness`

This classification was completed before deleting Stage-4 artifacts. The
cleanup policy is conservative: scientific auditability takes precedence over
minimum file count. Stage 1-3 curated content is outside the cleanup scope
except for clearly generated operating-system or Python cache files.

## Classification

### A. Canonical implementation

- Active Stage-4 controller, model, estimator, trust, pacing, allocator,
  measurement, evaluation, and trajectory code under
  `src/traction_mpc_stage4/`.
- The paired A/B runner and the patient, sensor, trajectory, crossed-matrix,
  realtime, and evidence-summary scripts under `scripts/`.
- Stage-3 plant, robot, Human-V2, rigid-cuff, reference, frame, model, and
  interface dependencies used by those Stage-4 paths.

Disposition: preserve.

### B. Canonical scientific configs

- `configs/stage4_patient_mismatch_cases.json`
- `configs/stage4_trajectory_excitation_suite.json`
- `configs/stage4_crossed_excitation_replication.json`
- The corresponding approved Experiment Specs under `docs/research/`.

Disposition: preserve byte-for-byte. In particular, the crossed matrix hash is
`00019282e188a1dca8d182b15ad9dd74d44c33312be5ad88f2f2c73efe1bbc81`.

### C. Essential regression and tests

- All `tests/test_stage4_*.py` tests, including the new patient, sensor,
  trajectory, crossed-runner, summary, config/provenance, causal-isolation,
  and trust-lifecycle tests.
- Stage-3 rigid-cuff and UR10e core tests exercised by the Stage-4 stack.

Disposition: preserve. No test is removed merely because coverage overlaps.

### D. Authoritative evidence

- Frozen A/B evidence:
  `results/stage4_single_challenger_closed_loop_ab_formal/`.
- Realtime replay evidence:
  `results/stage4_realtime_implementation_sprint_20260828/`.
- Reviewed formal evidence and canonical summaries:
  `stage4_patient_mismatch_robustness_formal/`,
  `stage4_nominal_sensor_decomposition_formal/`,
  `stage4_nominal_sensor_multiseed_formal/`,
  `stage4_trajectory_excitation_generalization_formal/`,
  `stage4_trajectory_excitation_generalization_summary/`,
  `stage4_crossed_excitation_replication_formal/`, and
  `stage4_crossed_excitation_replication_summary_final/`.

Disposition: preserve all per-arm JSON, Markdown, and NPZ traces. These are the
canonical recorded artifacts and are not regenerated during cleanup.

### E. Concise research documentation

- `docs/research/CURRENT_STATE.md` and the Stage-4 evidence map.
- Approved Stage-4 specs, final reports, trust/pacing behavior audit, root
  `README.md`, stage README, and hardware-boundary documentation.

Disposition: preserve and update only for closeout accuracy and path hygiene.

### F. Reproducible or generated intermediate outputs

- Retained Stage-4 engineering comparisons and concise audit outputs that
  establish architecture choices or negative/mixed findings, including cuff
  allocation/surface proxy, sensor realism, integral-estimator selection,
  trust-rule diagnosis, single-challenger lifecycle, optimizer rejection,
  measurement/oracle-chain diagnosis, and trajectory design audit.
- Final corrected iterations are retained where a diagnostic was rerun to fix
  an analysis defect: hierarchical trust `v5`, oracle chain `v4`, hybrid
  estimator failure `v2`, and the former multi-candidate statistical-lifecycle
  audit `v3`.

Disposition: preserve. Their status remains exploratory or engineering, never
formal or authoritative.

### G. Superseded smoke, debug, and temporary artifacts

The following are safe to remove because a corrected/final artifact exists and
no canonical document or formal result depends on the obsolete copy:

- `results/stage4_hierarchical_trust_audit_20260827/` through `_v4/`;
- `results/stage4_oracle_chain_audit_20260827/` through `_v3/`;
- `results/stage4_statistical_trust_audit_20260827/` and `_v2/`;
- `results/stage4_hybrid_estimator_failure_audit_20260827/` (superseded by
  `_v2` with the retained candidate table);
- `results/stage4_trajectory_excitation_structural_smoke_20260828/`;
- `results/stage4_crossed_excitation_replication_structural_smoke_20260828/`
  and `_v2/`;
- ignored `__pycache__`, `.pytest_cache`, and `.DS_Store` files.

The smoke outputs carry explicit smoke markers and are superseded by complete
formal evidence. Early diagnostic iterations either identify their own error
in `SUPERSEDED.md` or omit data retained by the corrected final iteration.

Disposition: remove from the repository after this audit is recorded. The
directories were quarantined, rather than permanently deleted, at
`/private/tmp/adaptive-stage4-cleanup.l44pLn`. They can be restored from that
temporary path until the operating system clears it; they are not recoverable
from Git because they were untracked.

### H. Uncertain or out-of-scope material

- All curated Stage 1-3 code, tests, reports, formal results, and vendor assets.
- Stage-4 engineering or negative-result directories not explicitly listed in
  category G, even when they are not part of the minimum active controller.
- Historical presentation media and earlier frozen Stage-4 checkpoints.

Disposition: preserve. No aggressive historical cleanup is authorized.

## Deletion guard

Before and after removal, the cleanup must verify that all category-D
directories still exist, that the crossed matrix and aggregate hashes are
unchanged, and that no formal directory contains a structural-smoke marker.
Formal experiments must not be rerun or overwritten as part of validation.
