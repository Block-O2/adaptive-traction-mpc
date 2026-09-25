# Reproduction commands

Working directory: `/Users/hankli/Desktop/coding/adaptive-traction-mpc`.
Every Python command below was invoked with this environment prefix:

```sh
env MPLCONFIGDIR=/tmp/full3d_adaptive_v1_mpl PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src
```

The initial `--mode baseline` invocation omitted MPLCONFIGDIR and recorded a
Matplotlib temporary-font-cache warning before planning began. The prefix and
each command form one shell invocation; no global environment mutation is needed.

Executed commands in order (read-only inspection omitted):

```sh
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/study_full3d_planner_runtime_v1.py --mode baseline
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/study_full3d_planner_runtime_v1.py --mode repaired
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_full3d_runtime_regression_v1.py --name nominal_regression_01
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_full3d_runtime_regression_v1.py --name nominal_regression_02
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_full3d_runtime_regression_v1.py --name nominal_regression_03
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/study_full3d_planner_runtime_v1.py --mode forensics
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_full3d_runtime_regression_v1.py --name deadline_fault_01 --inject-planner-delay-ms 110
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/study_full3d_planner_runtime_v1.py --mode reconstruction_v2
conda run --no-capture-output -n mpc_learn python -m pytest -q stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1 stages/stage5_personalized_motion_learning/tests/test_stage5_human_waypoint_scheduler.py
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/analyze_full3d_runtime_study_v1.py
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/study_full3d_planner_runtime_v1.py --mode function_profiles
git diff --check -- stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_scheduler.py
conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/analyze_full3d_runtime_study_v1.py --seal
```

All named output directories are retained and scripts refuse to overwrite them.
Do not rerun these names in this workspace. Reproduction in an isolated copy
must preserve the baseline snapshot and select new output paths deliberately.
`baseline/source/` is the original production implementation; current source
is repaired. Later `baseline_scheduler()` explicitly imports the saved original
scheduler. Source snapshots/provenance record which implementation was measured.

The initial wrapper-only baseline profile predates the line profiler; the later
forensics profile explicitly reruns original source with the new instrumentation.
Regression03 adds request-to-execution-entry timing; 01/02 do not contain that
field. Fault injection deliberately adds 110 ms after computation. Neither
diagnostic modifies the underlying control model or the 100 ms rejection rule.

Tests: 19 passed in 3.87 s. `git diff --check`: exit 0.
