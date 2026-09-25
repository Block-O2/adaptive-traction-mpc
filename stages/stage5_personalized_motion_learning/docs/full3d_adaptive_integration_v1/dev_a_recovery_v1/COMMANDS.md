# DEV-A commands and execution provenance

All commands ran from repository root
`/Users/hankli/Desktop/coding/adaptive-traction-mpc` on branch
`codex/stage5-architecture-recovery`, entry HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. No Git mutation.

Set the environment prefix for every Python command:

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn python ...
```

Exact DEV-A selected commands (append the relevant invocation to the prefix):

```bash
stages/stage5_personalized_motion_learning/scripts/run_dev_a_full3d_case_v1.py \
  --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/balanced_ordinary_r01.json \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/representative_v1/balanced_ordinary_r01

stages/stage5_personalized_motion_learning/scripts/run_dev_a_full3d_case_v1.py \
  --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/balanced_ordinary_r01.json \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/representative_v2/balanced_ordinary_r01

stages/stage5_personalized_motion_learning/scripts/run_dev_a_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/targeted_v1 \
  --case-keys hip_dominant_near_upper_current_rom_r01 hip_dominant_ordinary_r02 balanced_ordinary_r02 hip_dominant_middle_r01

stages/stage5_personalized_motion_learning/scripts/run_dev_a_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/targeted_v2 \
  --case-keys hip_dominant_near_upper_current_rom_r01 hip_dominant_ordinary_r02 balanced_ordinary_r02

stages/stage5_personalized_motion_learning/scripts/run_dev_a_full3d_case_v1.py \
  --case stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/nominal_development_v1

stages/stage5_personalized_motion_learning/scripts/run_dev_a_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v1

stages/stage5_personalized_motion_learning/scripts/run_dev_a_full3d_case_v1.py \
  --case stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/nominal_development_v2

stages/stage5_personalized_motion_learning/scripts/run_dev_a_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2
```

The startup-context-only physical check reused
`scripts/run_fresh_full3d_case_v1.py` on each of the three previously
pre-step cases with unique `dev_a_recovery_v1/startup_context_only/<key>/`
outputs; this intentionally preserved the old commissioning handoff and
therefore did not test active recovery. Each case ran 28,080 physical steps.

Tests used the same environment prefix with `pytest -q` instead of `python`:

```bash
pytest -q \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_a_recovery.py \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_integration_contracts.py \
  stages/stage5_personalized_motion_learning/tests/test_stage5_human_waypoint_shadow.py
```

Result: 15 passed. `py_compile` of edited production modules passed. Broader
regression summary and final `git diff --check` also passed. Summary command:

```bash
stages/stage5_personalized_motion_learning/scripts/summarize_dev_a_regression_v1.py \
  --results stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2/regression_summary.json

stages/stage5_personalized_motion_learning/scripts/summarize_dev_a_regression_v1.py \
  --results stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2/regression_summary_v2.json
```

The latter preserves the original summary and clarifies that an unexecuted
terminal TASK boundary is not a physical TASK force/clearance measurement.
The aggregate counts and timing statistics did not change.

The summary reports 24/24 physical commissioning, 15/24 successful active
recoveries, 2/24 full tasks. After regression V2, the five main source/config
SHA-256 values below were rechecked and unchanged from the start of V2.

SHA-256 at start of final regression V2 (Stage-5 root-relative):

```text
a1e341031bfada0fe24f4a1ce2fada67398ddf8af259ddfd359fb0cf5ec921ed  src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py
c2891d87fd9e6e34b0e8860287e81765784f9766ee95e595ce5338d68e19e40f  src/traction_mpc_stage5/full3d_adaptive_integration_v1/dev_a_recovery.py
d259dc69ee4adcbdd7ecf98efc06258446dce488879f433bf4337965153a8d46  src/traction_mpc_stage5/human_waypoint_shadow.py
18971a51ca6342ceb809efd494aa4b23aa9b5114faa546f37643c7abd9f71d4a  src/traction_mpc_stage5/hold_stabilizer.py
ef79cd9b76b6845a2d791d85667647c55188cf8e7361ab611ffed9dfbea3b9c3  configs/full3d_adaptive_integration_v1/dev_a_recovery_v1.json
```
