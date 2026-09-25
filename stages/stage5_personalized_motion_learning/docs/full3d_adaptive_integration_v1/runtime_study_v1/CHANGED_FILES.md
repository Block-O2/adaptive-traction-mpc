# Exact study file inventory (no staging manifest)

Paths below are relative to `stages/stage5_personalized_motion_learning/`.
All other pre-existing dirty/untracked repository files are outside this study.

Modified existing production file:

- `src/traction_mpc_stage5/human_waypoint_scheduler.py`: nine-line endpoint-floor
  necessary-condition early rejection; original working file saved under
  `results/full3d_adaptive_integration_v1/runtime_study_v1/baseline/source/`.

New study source/config/tests:

- `scripts/study_full3d_planner_runtime_v1.py`
- `scripts/run_full3d_runtime_regression_v1.py`
- `scripts/analyze_full3d_runtime_study_v1.py`
- `configs/full3d_adaptive_integration_v1/runtime_study_v1/contract.json`
- `tests/full3d_adaptive_integration_v1/test_runtime_endpoint_pruning.py`

New documents:

- `docs/full3d_adaptive_integration_v1/runtime_study_v1/STATUS.md`
- `docs/full3d_adaptive_integration_v1/runtime_study_v1/REPORT.md`
- `docs/full3d_adaptive_integration_v1/runtime_study_v1/AUDIT_REPORT.md` (Auditor)
- `docs/full3d_adaptive_integration_v1/runtime_study_v1/COMMANDS.md`
- `docs/full3d_adaptive_integration_v1/runtime_study_v1/CHANGED_FILES.md`

Generated evidence namespace:

- `results/full3d_adaptive_integration_v1/runtime_study_v1/`
  contains `baseline`, `repaired`, `forensics`, `reconstruction_v2`,
  `function_profiles`, `nominal_regression_01..03`, `deadline_fault_01`,
  `analysis`, and final seal. Individual artifact paths/hashes are in the seal.

Start/end full untracked inventories are in provenance JSONs. The first baseline
snapshot was taken after bootstrapping STATUS.md, contract.json and the initial
study harness; those three are study additions, not pre-existing work. The
initial read-only `git status --short` was also recorded in the task tool log.
The starting checkout already contained unrelated Stage4 documents/results/
scripts/tests and extensive Stage5 code/assets; none was staged or cleaned.
