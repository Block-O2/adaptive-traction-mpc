# DEV-A file ownership and reproducibility boundary

No file was staged, committed, pushed, reset, stashed or deleted. Branch
`codex/stage5-architecture-recovery`; entry HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`.

Production changes specifically made for DEV-A:

| Path below Stage-5 root | DEV-A action | Git state at entry |
|---|---|---|
| `src/traction_mpc_stage5/human_waypoint_shadow.py` | Explicit task vs startup/commissioning/recovery candidate context; recovery robot target twist | tracked, pre-existing modified |
| `src/traction_mpc_stage5/hold_stabilizer.py` | Optional explicit robot target twist for recovery; default unchanged | tracked, pre-existing modified |
| `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py` | Startup context, ACTIVE_RECOVERY state machine, timing-aware CR12 physical execution, monitoring, trace/provenance | pre-existing untracked full-3D subtree |
| `src/traction_mpc_stage5/full3d_adaptive_integration_v1/dev_a_recovery.py` | New C2 robot-cuff pose bridge | new |
| `src/traction_mpc_stage5/fresh_qualification_v1/physics_monitor.py` | Evaluation-only ACTIVE_RECOVERY stage counters | pre-existing untracked full-3D subtree |

New DEV-A-only implementation/test artifacts under Stage-5 root:

- `configs/full3d_adaptive_integration_v1/dev_a_recovery_v1.json`
- `scripts/run_dev_a_full3d_case_v1.py`
- `scripts/run_dev_a_development_batch_v1.py`
- `scripts/summarize_dev_a_regression_v1.py`
- `tests/full3d_adaptive_integration_v1/test_dev_a_recovery.py`
- `docs/full3d_adaptive_integration_v1/dev_a_recovery_v1/{STATUS,DESIGN_DECISIONS,COMMANDS,CHANGED_FILES,DEV_A_REPORT,AUDIT_REPORT}.md`
- `results/full3d_adaptive_integration_v1/dev_a_recovery_v1/` (versioned
  startup-only, targeted, nominal, regression V1/V2 development artifacts;
  local but Git-ignored by Stage-5 `.gitignore:10`)

The production full-3D runner, model/assets, case generator, and many of its
dependencies were already untracked or dirty at entry; DEV-A results are
Git-ignored. DEV-A does not claim
clean-clone reproducibility. Historical Stage-4 work, prior full-3D attempts,
formal qualification artifacts and the other pre-existing unrelated dirty
paths remain untouched. There were 578 dirty/untracked paths at entry, not
578 DEV-A changes.
