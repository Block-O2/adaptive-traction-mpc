# DEV-C executed commands and environment

All commands below were executed from
`/Users/hankli/Desktop/coding/adaptive-traction-mpc` on the existing
`codex/stage5-architecture-recovery` branch. `mpc_learn` was the existing
Conda environment; the full session code uses real MuJoCo CR12–cuff–Human
stepping. The four matched calls for each output arm were dispatched as
independent commands (some concurrently), not combined into a new plant.

Common prefix:

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn python
```

Strongest matched local branch (the same script/input structure was run for
`balanced_middle_r01`, `balanced_ordinary_r01`, and `development_nominal`):

```bash
python stages/stage5_personalized_motion_learning/scripts/run_dev_c_matched_v1.py \
  --checkpoint-dir stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3/balanced_near_upper_current_rom_r01 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/matched_v3/balanced_near_upper_current_rom_r01/bumpless \
  --arm bumpless \
  --transfer-config stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v2.json
```

The command above used the common environment prefix, with `python` replacing
the prefix's final `python`; direct-switch comparisons used `--arm direct`
and `matched_v1/<case>/direct` output. `matched_v1/` and `matched_v2/` were
run before duration revision, against the v1 fixed-duration config.

Analysis/plots:

```bash
python stages/stage5_personalized_motion_learning/scripts/analyze_dev_c_matched_v1.py \
  --results stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1 \
  --repaired-set matched_v3
```

Representative version-2 sessions:

```bash
python stages/stage5_personalized_motion_learning/scripts/run_dev_c_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/sessions_v2 \
  --case-keys balanced_near_upper_current_rom_r01 balanced_ordinary_r01 balanced_middle_r01

python stages/stage5_personalized_motion_learning/scripts/run_dev_c_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/sessions_nominal_v2
```

The initial fixed-duration runs are retained as `sessions_v1/` and
`sessions_nominal_v1/`. The same-code nominal DEV-C-off replay used
`scripts/run_dev_a_full3d_case_v1.py` with the development nominal case JSON
and output `sessions_nominal_direct_v1/`.

Consumed 24-case adaptive DEVELOPMENT regression (restart-safe; completed
case artifacts are read, not overwritten):

```bash
python stages/stage5_personalized_motion_learning/scripts/run_dev_c_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/regression_v1
```

Focused transfer unit tests were run with the same Conda/PYTHONPATH prefix,
replacing `python` with `pytest -q`:

```bash
pytest -q stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_c_bumpless_transfer.py
```

The completed regression is interpreted by the retained
`regression_v1/regression_summary_dev_c_v3.json`; earlier drafts are not
authoritative because they included terminal non-executed zero commands.
Output-envelope v3 matched replays used the same four checkpoint arguments
above with `--transfer-config
stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v3.json`
and separate `matched_v4/<case>/bumpless` outputs. The same analysis script
used `--repaired-set matched_v4`. Representative failed sessions used:

```bash
python stages/stage5_personalized_motion_learning/scripts/run_dev_c_development_batch_v1.py \
  --cases stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases \
  --case-keys elevated_start_middle_r01 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/sessions_problem_v4_diag2
```

The `diag2` output repeats an earlier separately retained
`sessions_problem_v4/` failure with more endpoint-event logging. The final
focused test command additionally included `test_dev_a_recovery.py`,
`test_integration_contracts.py`, and `test_runtime_endpoint_pruning.py`:
**20 passed**. JSON parsing and `git diff --check` were run separately.

No fresh held-out qualification or real-hardware actuation was run. No
repository data was uploaded. No Git staging, commit, or push was performed.
