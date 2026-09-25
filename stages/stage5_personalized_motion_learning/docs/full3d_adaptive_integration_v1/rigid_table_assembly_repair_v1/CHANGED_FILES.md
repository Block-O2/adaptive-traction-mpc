# Added paths and preservation classification

No pre-existing tracked controller, estimator, physics or historical result
file was modified by this stage. No Git staging, commit, push, reset, stash,
branch switch or deletion occurred. The current working tree was already
dirty before this versioned work; see
`assembly_v1/DEPENDENCY_MANIFEST.json::git_status_porcelain_v1_uall_at_prepare`
for the exact initial list. The previous 607 local source/config/model hashes
were checked unchanged after the replication.

This stage added only:

- `src/traction_mpc_stage5/rigid_table_assembly_v1/__init__.py` and
  `assembly.py`: generation/evaluation-side case mapping and screen; never
  imported by deployable controller;
- `scripts/prepare_rigid_table_assembly_v1.py`,
  `run_rigid_table_prefix_v1.py`, `run_rigid_table_development_v1.py`,
  `audit_rigid_table_trajectory_geometry_v1.py`,
  `audit_rigid_table_pose_consistency_v1.py`,
  `prepare_rigid_table_envelope_extension_v2.py`,
  `run_rigid_table_envelope_supplement_v2.py`,
  `audit_rigid_table_supplement_v2.py`,
  `summarize_rigid_table_development_v1.py`,
  `verify_rigid_table_artifacts_v1.py`,
  `finalize_rigid_table_repro_v1.py`: new mechanical, development, audit and
  provenance commands;
- `configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/
  nominal_reference_rigid_table_v1.json`: nominal development reference with
  +0.1 mm positive installation gap;
- `tests/full3d_adaptive_integration_v1/test_rigid_table_assembly_v1.py`:
  negative-gap, counterpart, unchanged-case and tangency tests;
- `docs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/`:
  new contract, design record, status, commands, report, audit and correction;
- `results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/`:
  new case mapping/configs, short mechanics prefixes, representative and
  old24-valid development runs, v2 geometry-only case mapping and one
  supplemental physical failure, aligned physical/contact traces, geometry
  audits, outcome summary and dependency manifest.

The two v1 sleeve-invalid originals remain in its mapping; v2 additionally
admits one at the minimum legal extra elevation and leaves the other invalid.
Both remain in the historical old24 denominator. The old failed formal
qualification and DGN/DEV-A/B/C/integrated
recovery artifacts were neither edited nor deleted. These local added paths
are untracked and the wider full-3D implementation still has prior
uncommitted dependencies; clean-clone reproducibility is not claimed.
