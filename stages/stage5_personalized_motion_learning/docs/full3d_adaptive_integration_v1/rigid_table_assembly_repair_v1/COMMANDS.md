# Exact commands and artifact namespace

Repository cwd:
`/Users/hankli/Desktop/coding/adaptive-traction-mpc`.

All Python/pytest commands below use this prefix before their script/test
arguments:

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
 conda run --no-capture-output -n mpc_learn python
```

Executed development and audit commands (script paths follow the common
Python prefix above):

```bash
stages/stage5_personalized_motion_learning/scripts/prepare_rigid_table_assembly_v1.py
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_prefix_v1.py
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_development_v1.py \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/representative_v1 \
 --case-keys balanced_near_upper_current_rom_r01 balanced_ordinary_r01 balanced_middle_r01 nominal_reference_rigid_table_v1 --include-nominal
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_development_v1.py \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/broad_old24_valid_v1
stages/stage5_personalized_motion_learning/scripts/summarize_rigid_table_development_v1.py \
 --runs stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/broad_old24_valid_v1 \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/review_v1
stages/stage5_personalized_motion_learning/scripts/audit_rigid_table_trajectory_geometry_v1.py \
 --runs stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/representative_v1 \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/trajectory_geometry_representative_v1
stages/stage5_personalized_motion_learning/scripts/audit_rigid_table_trajectory_geometry_v1.py \
 --runs stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/broad_old24_valid_v1 \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/trajectory_geometry_broad_v1
stages/stage5_personalized_motion_learning/scripts/verify_rigid_table_artifacts_v1.py
stages/stage5_personalized_motion_learning/scripts/audit_rigid_table_pose_consistency_v1.py \
 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/pose_consistency_v1/POSE_AUDIT.json
stages/stage5_personalized_motion_learning/scripts/prepare_rigid_table_envelope_extension_v2.py
stages/stage5_personalized_motion_learning/scripts/run_rigid_table_envelope_supplement_v2.py
stages/stage5_personalized_motion_learning/scripts/audit_rigid_table_supplement_v2.py
```

Versioned outputs live under:
`stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/`.
`assembly_v1/OLD_TO_NEW_CASE_MAPPING.json` contains all 24 original/revised
case hashes, exact geometry changes and v1 validity; `assembly_v2/` separately
records the geometry-only sleeve-clearance extension and its 23/24
initial/task-endpoint validity. `STATIC_CONTACT_SWEEP.json`
and `prefix_v1/PREFIX_CONTACT_RESULTS.json` contain pre-outcome mechanics
evidence. Full-run folders contain unchanged runtime `summary.json`, aligned
`trace.npz`, individual interval contact-force arrays, contact summary,
assembly/command manifest and any runner exception. `batch_status.json` is
updated after every completed case and supports restart without overwriting.
The v2 physical supplement is under `supplemental_v2/`; it aborted in active
recovery and is not folded into the v1 22-case batch metrics.

Original historical formal/dev evidence is never edited. No git stage, commit,
push, reset, stash, branch switch or deletion is part of these commands.

Focused tests (same environment variables and PYTHONPATH as above, replacing
`python` with `pytest`):

```bash
pytest -q \
 stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_rigid_table_assembly_v1.py \
 stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_a_recovery.py \
 stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_integration_contracts.py \
 stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_runtime_endpoint_pruning.py
```

Result: 14 passed. A prior four-test run of the new rigid-table unit test file
also passed. The `verify_rigid_table_artifacts_v1.py` read-only check recomputed
all 22 physical contact integrals and hashes and matched 125 planner calls,
eight deadline misses and five completions.

Additional final checks:

```bash
# With the common Python prefix, parse/compile all new Python files via
# ast.parse and load all new JSON files (including the nominal config).
# With the common Python prefix, inspect all new source/doc text for trailing
# whitespace; zero findings.
git diff --check
# With the common Python prefix, after documentation/audit is settled:
stages/stage5_personalized_motion_learning/scripts/finalize_rigid_table_repro_v1.py
```

`git diff --check` alone does not cover the newly added untracked files, so
additional text/AST/JSON checks were run explicitly. Final dependency-hash manifest is under
`results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/repro_v1/`.
