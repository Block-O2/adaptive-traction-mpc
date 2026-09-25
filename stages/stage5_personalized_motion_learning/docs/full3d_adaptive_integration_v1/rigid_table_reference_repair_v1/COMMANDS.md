# DEV-D exact local commands and evidence versions

All commands were run from the repository root on the existing
`codex/stage5-architecture-recovery` working tree. No Git staging, commit,
push, branch switch, reset or stash was performed. The reusable local Python
prefix was:

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn python
```

Append the following script and arguments to that prefix:

```bash
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_reference_development_v1.py \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/representative_strict_v1 \
  --case-keys balanced_near_upper_current_rom_r02 balanced_middle_r01 balanced_ordinary_r01 balanced_near_upper_current_rom_r01 nominal_reference_rigid_table_v1
```

The final strict old-23 development replay used:

```bash
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_reference_development_v1.py \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_reference_repair_v1/broad_strict_v1 \
  --case-keys balanced_middle_r01 balanced_middle_r02 balanced_near_upper_current_rom_r01 balanced_near_upper_current_rom_r02 balanced_ordinary_r01 elevated_start_middle_r01 elevated_start_middle_r02 elevated_start_near_upper_current_rom_r01 elevated_start_near_upper_current_rom_r02 elevated_start_ordinary_r01 elevated_start_ordinary_r02 hip_dominant_middle_r01 hip_dominant_middle_r02 hip_dominant_near_upper_current_rom_r01 hip_dominant_near_upper_current_rom_r02 hip_dominant_ordinary_r01 hip_dominant_ordinary_r02 knee_dominant_middle_r01 knee_dominant_middle_r02 knee_dominant_near_upper_current_rom_r01 knee_dominant_near_upper_current_rom_r02 knee_dominant_ordinary_r01 knee_dominant_ordinary_r02
```

`broad_development_v1` is a separate earlier pre-Auditor strict-path version.
`representative_v1` through `representative_current_v2`,
`representative_final_v1` and `representative_optimized_v1` are preserved
development iterations. Every physical result directory has its own
`dev_d_run_manifest.json` with the exact `sys.argv`, case SHA-256 and flags;
the batch-level `batch_status.json` provides restart order and all outcomes.
Do not merge these configuration versions or call any of them held-out.

The repeatable tests, isolated timing check, aggregation and figure generation
are respectively:

```bash
-m pytest -q stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_d_rigid_table_reference.py
stages/stage5_personalized_motion_learning/scripts/profile_dev_d_geometry_v1.py --output NEW_PROFILE_PATH.json --repeats 1000
stages/stage5_personalized_motion_learning/scripts/summarize_rigid_table_reference_development_v1.py --batch BATCH_DIRECTORY --output NEW_SUMMARY_PATH.json
stages/stage5_personalized_motion_learning/scripts/plot_rigid_table_reference_development_v1.py --case V2_CASE_JSON --old OLD_RUN_DIR --new NEW_RUN_DIR --near-upper-case NEAR_UPPER_V2_CASE_JSON --near-upper-run NEAR_UPPER_NEW_RUN_DIR --output-dir FIGURE_DIRECTORY
```

`NEW_PROFILE_PATH`, `NEW_SUMMARY_PATH`, and the other capitalized paths must
be replaced with distinct versioned destinations. The concrete paths used
for each artifact are recorded in the result directory and final report.
The source/profile versions `geometry_profile_before_v1.json` and
`geometry_profile_after_v1.json` isolate a vertical-only algebraic
optimization; they are not hardware deadline qualification.
