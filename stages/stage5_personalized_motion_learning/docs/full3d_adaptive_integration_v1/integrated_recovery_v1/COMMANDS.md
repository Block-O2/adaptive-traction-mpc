# Executed commands and local reproduction

Repository cwd: `/Users/hankli/Desktop/coding/adaptive-traction-mpc`.
Environment is the existing `mpc_learn` Conda environment; exact Python,
MuJoCo, NumPy, SciPy and platform versions are in BASELINE_MANIFEST.json.
No hardware or external compute is used.

Common prefix (replace the final `python` with `pytest` only for tests):

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn python
```

The following command suffixes were executed with that prefix, sequentially:

```bash
stages/stage5_personalized_motion_learning/scripts/prepare_integrated_recovery_v1.py

stages/stage5_personalized_motion_learning/scripts/diagnose_integrated_contact_v1.py \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/contact_v1/assembly_and_checkpoint.json

stages/stage5_personalized_motion_learning/scripts/replay_integrated_contact_v1.py \
  --case-key balanced_near_upper_current_rom_r01 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/contact_replay_v1/balanced_near_upper_current_rom_r01

stages/stage5_personalized_motion_learning/scripts/replay_integrated_contact_v1.py \
  --case-key balanced_ordinary_r01 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/contact_replay_v1/balanced_ordinary_r01

stages/stage5_personalized_motion_learning/scripts/replay_integrated_contact_v1.py \
  --case-key development_nominal \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/contact_replay_v1/development_nominal

stages/stage5_personalized_motion_learning/scripts/summarize_integrated_contact_v1.py \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/review_v2
```

The summarize script was first run without `--output` to produce review_v1;
v2 changes only plot scaling, retaining v1. Diagnostic first attempt failed on
the native `mj_fullM` signature; the corrected invocation above completed.
Scripts refuse to overwrite existing output directories/files. To reproduce,
select a new output path; do not erase any prior evidence. Heavy original
DEV-B checkpoints and historical case/summary/trace paths must remain locally
available; replay manifests record them and fixed planning delays.

Final focused checks used:

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn pytest -q \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_c_bumpless_transfer.py \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_a_recovery.py \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_integration_contracts.py \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_runtime_endpoint_pruning.py
git diff --check
```

Read-only Git branch/HEAD/status, SHA256 verification, JSON parsing and independent
interval-array recomputation are also recorded in manifests/audits. No Git
stage/commit/push/reset/stash/switch operation occurred.

Compact local review packaging (read-only archive of existing files):

```bash
tar -czf stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/integrated_recovery_v1/compact_review_v1.tar.gz \
  -T stages/stage5_personalized_motion_learning/docs/full3d_adaptive_integration_v1/integrated_recovery_v1/REVIEW_PACKAGE_FILES.txt
```

The list includes historical aligned reference/estimate/physical traces solely
as provenance, not as new campaign outcomes. Large checkpoint pickles remain
local; the archive is a review package, not a self-contained clean clone.
