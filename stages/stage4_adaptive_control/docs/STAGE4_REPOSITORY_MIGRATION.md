# Stage-4 repository migration

This record documents the storage-only reorganization performed on
`codex/final-repo-cleanup`. Scientific settings, controller definitions,
physical parameters, accepted result values, and Git history were not changed.
The exact pre-cleanup layouts remain available at
`stage4-robustness-final-v1` and `stage4-report-validation-final-v1`.

## New boundary

- `stages/stage3_full3d/` now contains the coupled 3D simulation foundation.
- `stages/stage4_adaptive_control/` contains estimation, trust, adaptive MPC,
  report validation, tests, documentation, and curated evidence.
- Stage 4 imports Stage 3 APIs; no Stage-3 implementation was duplicated.

The complete machine-readable old-to-new path table and metadata-only hash
changes are in [`STAGE4_REPOSITORY_MIGRATION.json`](STAGE4_REPOSITORY_MIGRATION.json).
Frozen preregistration configs retain their original bytes and SHA-256 values.
`traction_mpc_stage4.artifact_paths` resolves their historical result paths to
the current semantic hierarchy and is protected by regression tests.

## Evidence retention

Kept in the active tree:

- all canonical JSON/Markdown summaries, tables, manifests, and configs;
- the complete 36-arm patient-generalization raw study used by the current
  metric/provenance audit;
- all six trajectory-demo traces and every trace referenced by the current
  visualization manifest;
- the original adaptive A/B pair used as the external reference clock;
- the knee-dominant shared force-gate traces as unique negative evidence;
- the full failed preregistered PD-v1 gain-selection evidence;
- the real MuJoCo renderer/tests, external-delivery provenance manifest, and
  compact README GIF/PNGs derived from the accepted MP4s.

Removed from the active tree:

- superseded engineering, audit, smoke, one-shot, and schematic-renderer
  result directories;
- implementation modules/scripts/tests/docs tied only to those removed paths;
- 125 large NPZ files whose results remain represented by canonical summaries
  and whose frozen runners/configs can regenerate them.
- repository copies of the three full professor-delivery MP4s, which are
  intentionally stored externally with the professor report;
- the superseded Stage-3 `stage4_one_shot` presentation media and redundant
  Fixed-versus-Adaptive PNG already represented by the README hero GIF.

Four trajectory traces used as read-only bridges by the crossed-replication
contract remain present so its registered SHA checks and analysis-matrix
reconstruction continue to work without rerunning science.

## Cleanup inventory

- 606 retained tracked files were moved or renamed into the Stage-4 boundary.
- 31 superseded engineering/smoke/result directories were removed.
- 11 dead audit/alternative source modules, 32 one-off scripts, 8 tests tied
  only to removed implementations, and 10 superseded documents were removed.
- 125 regenerable NPZ traces were removed while 59 scientifically required
  traces remain.
- 413 material files were removed in total; generated caches and `.DS_Store`
  files were also cleared.
- No item remained in an uncertain-only category.

## Storage

Sizes below are exact file-byte totals and exclude every `.git` directory.

| scope | before | after |
|---|---:|---:|
| working tree | 2,025,481,533 B / 1,671 files | 610,608,403 B / 1,128 files |
| Stage 3 | 1,915,942,541 B / 1,212 files | 40,110,307 B / 57 files |
| independent Stage-4 root | not present | 461,058,873 B / 620 files |
| all stage results | 1,952,572,293 B | 539,891,054 B / 774 files |
| all stage tests | 895,472 B / 116 files | 320,112 B / 51 files |
| all stage docs | 335,520 B | 277,636 B / 31 files |
| tracked README media | not present | 1,485,269 B / 3 files |

The net working-tree reduction is 1,414,873,130 bytes (about 1.32 GiB). Git
history was not rewritten, so repository-object storage is intentionally
unchanged.

The cleanup used a recoverable operating-system temporary quarantine during
review. That location is not part of repository provenance and may be cleared
automatically. The historical Git tags are the durable recovery mechanism.

## Metadata-only rewrites

Public visualization/video manifests and current phase manifests previously
contained username-specific absolute paths or obsolete result names. Only
those path strings were normalized. The migration JSON records each old and
new SHA-256. Numerical arrays, metrics, controller fingerprints, trace hashes,
and accepted external MP4 hashes were unchanged. The video provenance manifest
now lives under `results/summaries/`; the full delivery MP4s are not tracked.

## Scientific boundary

No formal experiment, benchmark, controller rollout, parameter tuning, or new
simulation result was produced by this migration. The README GIF and PNGs are
media conversions from the accepted real MuJoCo MP4s.
