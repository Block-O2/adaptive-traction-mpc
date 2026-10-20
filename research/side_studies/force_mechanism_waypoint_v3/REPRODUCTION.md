# Reproduction and artifact locations

Canonical package is in WSL at `/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3`. This Windows directory is the review mirror. The canonical package preserves the new copied source/dependency/weight closure and every new full raw trace, compressed native-state log and command receipt stream. Historical B/18D raw files remain in their original packages and are SHA-bound in `audit/ARCHIVE_INPUTS.json`; they have not been replaced by resampled curves.

Runtime: `/home/hank/envs/adaptive-online-rl-v1/bin/python -B`; existing NumPy/SciPy/Matplotlib/MuJoCo, single-thread numerical settings. No installation or external data fetch is required.

Do not rerun the stopped campaign in place. Its unique attempt IDs, original failures and budgets are part of the evidence. To deliberately reproduce the fixed physical study, first prepare a new sibling output directory:

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3/control/prepare_reproduction.py --destination /home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3_reproduction_001
```

Preparation alone performs zero physics. It copies the final closure and exact registered candidate constants, relocates paths, keeps the shared historical fixture read-only, creates empty result/attempt directories and freezes a new manifest. It resets only the new reproduction's wall-clock budget. It does not reset or alter this study. The fresh study has at most 12 STARTs: one legal cold parent, seven registered baseline/zero/smooth/opposite arms, and conditional half/repeat for each direction. No new optimizer or force search is run. If a fresh reproduction is intentionally requested, run the exact command printed by preparation. Each candidate inherits the entire legal live parent by `os.fork`; saved q/dq never reconstruct a physical branch.

The completed study used 14 STARTs because a missing output directory caused the first parent to stop after a completed B fork. Both STARTs remain in the accounting. The saved B was evaluated without new physics; a fresh parent/B pair was then used before any nonzero intervention. This engineering repair did not expand the scientific candidate set.

Analysis sources are in `control/`. `analyze_mechanism.py` is the original fresh-output bootstrap and refuses an existing destination. `allocator_counterfactual.py` and `demand_decomposition.py` are algebraic model analyses. `wrench_component_reconstruction.py` uses disposable model kinematics only, forbids all MuJoCo stepping functions and checks total-wrench reconstruction. `postprocess_targeted.py`, `targeted_demand_terms.py`, and `compact_figures.py` process completed raw runs and do not step physics. Make a separately named analysis copy before regenerating finalized figures or derived evidence.

`EXECUTION_CODE_MANIFEST.json` identifies the immutable physical execution closure; its first-start predecessor is retained under `audit/startup_EXECUTION_CODE_MANIFEST.json`. Additional postprocessing scripts are separately covered by `ANALYSIS_CODE_MANIFEST.json`. `RUN_PLAN.json`, `RUN_PLAN_REPAIR1.json`, the original plan copy, `CANDIDATE_PLAN.json`, and `EXECUTABLE_PLAN.json` retain the original design and prephysical control-certificate amendment.

The exact evidence gates are in `MOTION_ACCEPTANCE_PROTOCOL.json`, `TARGETED_MATH_TESTS.json`, the per-run measured/receipt audits, the zero/repeat gates, and `PARENT_FORK_GATE.json`. Scientific-mode causality is not host-clock qualification. The prior 18D prefix motion 0/4 and host/strict failures remain unchanged.
