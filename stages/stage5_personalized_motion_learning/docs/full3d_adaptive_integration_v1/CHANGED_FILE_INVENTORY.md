# FULL-3D Adaptive Integration V1 Changed-File Inventory

Date: 2026-09-23  
Recorded branch: `codex/stage5-architecture-recovery`  
Recorded starting HEAD: `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`

No file was staged, committed, pushed, reset, stashed, or deleted in this
campaign. The repository already had a large dirty/untracked research working
tree. This inventory identifies the focused campaign delta; it is not a claim
that every other dirty Stage-5 file was created here.

## New campaign implementation and tests

- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/__init__.py`
- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/time_contract.py`
- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py`
- `scripts/run_full3d_adaptive_integration_v1.py`
- `scripts/render_full3d_evidence_v1.py`
- `scripts/study_full3d_large_rom_v1.py`
- `tests/full3d_adaptive_integration_v1/test_time_contract.py`
- `tests/full3d_adaptive_integration_v1/test_integration_contracts.py`

## Focused existing-source modifications

- `src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py`
  adds the opt-in boundary-aligned evaluator while preserving the historical
  default.
- `scripts/architecture_recovery_v2/run_functional_campaign.py` accepts a
  wrapper/base config, records the effective config, and seals the imported
  timing helper in the final source manifest.
- `src/traction_mpc_stage5/human_waypoint_feedback_mpc.py` adds the bounded
  mechanics-feasible duration search used by this integration.
- `src/traction_mpc_stage5/human_waypoint_scheduler.py` exposes the schedule
  boundary quantities needed to verify q/dq/ddq continuity.

## New configs and documentation

- all files under `configs/full3d_adaptive_integration_v1/`
- all files under `docs/full3d_adaptive_integration_v1/`

## New result namespace

- all files under `results/full3d_adaptive_integration_v1/`

This includes preserved failed/superseded development runs, the baseline,
corrected-time replication versions, final nominal and no-actuation traces,
large-ROM study, and evaluation-only media. Generated `__pycache__` entries are
not scientific deliverables.

## Reused pre-existing local dependencies

The campaign reused, but did not claim to create, the CR12 XML, robot/plant
modules, vendor URDF/SRDF/mesh assets, Stage-3 Human/cuff interface, Stage-4
measurement layer, recovered V2.2 effective model/updater, and existing loaded
TRACK/BRAKE execution stack. Exact final hashes appear in
`DEPENDENCY_MANIFEST.md`.

Because several reused dependencies and all new campaign files are outside the
recorded commit, a clean checkout at the recorded HEAD does not reproduce the
run. Publication remains a separate authorized repository task.

## Final Git state

Final inspection remained on
`codex/stage5-architecture-recovery...origin/codex/stage5-architecture-recovery`
at `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. `git status --short`
contained 201 top-level status entries because the repository already included
substantial unrelated Stage-4 and Stage-5 dirty/untracked work. The focused
campaign status comprises four modified tracked files
(`run_functional_campaign.py`, `functional_benchmark.py`,
`human_waypoint_feedback_mpc.py`, `human_waypoint_scheduler.py`) plus the seven
untracked campaign paths/directories enumerated above. Result files are ignored
by Git but remain present and hashed in the dependency manifest. No index,
commit, remote, branch, stash, or reset operation was performed.
