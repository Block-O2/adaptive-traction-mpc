# Deterministic checks retained for failed implementation attempt

Environment: `/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python`, `PYTHONPYCACHEPREFIX=/private/tmp/codex_scientific_pycache`, `MPLCONFIGDIR=/private/tmp/codex_scientific_mpl`, Stage-5/4/3 source paths on `PYTHONPATH`.

Focused command: `python -m pytest -q -p no:cacheprovider stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_scientific_scheduler.py stages/stage5_personalized_motion_learning/tests/safe_fallback_execution_v1/test_safe_fallback.py stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_integration_contracts.py` from the repository root with the stated source paths. Result: **23 passed**.

Coverage: frozen worker receipt at 0/100/200/500 ms fake delay; mismatch rejection; source/activation version logging; exact physical 100 ms expiry; by-value snapshot mutation test; exact 20 native steps after command; existing realtime >=100 ms lifecycle stale checks; Safe Fallback reachability and RSS C2 geometry. The source of scorer-v2, planner objective, Human model and controller mathematics is unchanged against the documentation checkpoint.

Broader command added `tests/full3d_adaptive_integration_v1/test_runtime_endpoint_pruning.py`. Result: **24 passed, 1 failed**. The failing old test is `test_roundoff_guard_does_not_relax_path_acceptance`: its monkeypatched `counted_path(values,c)` raises `TypeError` when unchanged `human_waypoint_scheduler.py` passes `task_floor_override_m`. Neither file was edited in this attempt; the failure remains recorded without an unrelated repair.

`mpc_learn` `py_compile` on six changed source/script files and the new test, plus `git diff --check`: PASS. The first `python3` test attempt could not collect because Homebrew Python lacked `numpy`; a second environment lacked `matplotlib`; the existing `mpc_learn` environment resolved those dependency errors without installation or code changes.

These focused checks do not establish the complete acceptance plan's atomic write fault, interruption, all-version mutation or full realtime differential gates. The host-delay/scorer gate failed before further dynamic qualification.
