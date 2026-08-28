# Stage-4 Closeout Validation Record

Date: 2026-08-28
Branch: `codex/stage4-patient-mismatch-robustness`
Baseline: `stage4-baseline-v1` / `ef1fe90e61c5981df8e934585780ce188d104ea4`

No formal scientific experiment was rerun. Validation was limited to tests,
compilation, strict parsing, path checks, and read-only evidence integrity.

## Test results

| scope | command | result |
|---|---|---|
| Stage 1 | `conda run -n mpc_learn pytest -q` from `stages/stage1` | 99 passed |
| Stage 2 | `conda run -n mpc_learn pytest -q` from `stages/stage2_linkage` | 19 passed |
| Stage 3 core | `PYTHONPATH=src conda run -n mpc_learn pytest -q tests/test_real_robot_interface_contract.py tests/test_stage3c_human_rigid_cuff.py tests/test_ur10e_robot_core.py` | 26 passed |
| Stage 4 full | `PYTHONPATH=src:. conda run -n mpc_learn pytest -q tests/test_stage4_*.py` | 158 passed |

The first Stage-3 attempt omitted `PYTHONPATH` and failed during collection
with `ModuleNotFoundError: traction_mpc_stage3`. The first Stage-4 attempt used
only `PYTHONPATH=src` and failed during collection with
`ModuleNotFoundError: scripts`. Both were invocation/environment errors, not
test failures. The corrected commands above passed without source or config
changes.

## Static and repository checks

- Every Python file under `stages/` passed `python -m py_compile` in the
  `mpc_learn` environment.
- All 285 repository JSON files passed strict `jq` parsing.
- README, Stage-3 README, and `CURRENT_STATE.md` contained 16 checked local
  Markdown links with zero broken targets.
- `git diff --check` passed.
- The three canonical config files are distinct and their SHA-256 values match
  the evidence map.
- No structural-smoke marker exists under a formal result directory.
- No formal scientific output was overwritten or regenerated.

## Evidence integrity

The artifact maps embedded in the patient, nominal sensor decomposition,
nominal sensor multiseed, trajectory, and crossed aggregate summaries were
recomputed with SHA-256. Every listed file matched. The crossed check followed
the 16 new cases in the crossed directory and the two preregistered read-only
bridges in their original trajectory-evidence directories.

All 108 NPZ files under canonical `stage4_*formal` evidence were opened with
`allow_pickle=False`. Their 4,968 arrays (319,680,372 values) were finite; zero
files or arrays failed.

## Scientific-change declaration

Scientific variables changed: **none**.

Explicitly unchanged: plant and rigid-cuff mechanics, Human parameters,
11-base estimator definition and bounds, trust rule, pacing, allocator, MPC
horizon/candidate/iteration/elite counts, costs, interaction weights,
constraints, seeds, sensor regimes, trajectories, runtime limits, safety
gates, and formal artifacts.

Formal commands remain reserved for the user and must target new result
directories. The next formal baseline/visualization study requires a new
approved Experiment Spec.
