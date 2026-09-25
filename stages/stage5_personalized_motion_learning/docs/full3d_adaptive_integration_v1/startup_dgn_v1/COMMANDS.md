# DGN V1 reproduction commands and environment

Run from repository root `/Users/hankli/Desktop/coding/adaptive-traction-mpc`.
The actual DGN used the existing `mpc_learn` Conda environment (Python 3.10.20,
NumPy 2.2.6, SciPy 1.15.3, MuJoCo 3.10.0, Matplotlib 3.10.9). Source/config/
asset hashes are in `SOURCE_SNAPSHOT.md` and the unchanged 309-path formal
`../fresh_qualification_v1/FREEZE_MANIFEST.json`. All case JSON files below
are the **old, failed formal V1 cases reused as development diagnostics**;
no new hidden seeds were generated. The nominal episode is prior development
evidence. Original results were read, never overwritten.

The diagnostic scripts refuse to reuse an existing output directory. To
repeat a run, change only its `--output` to a **new** versioned path; do not
remove the saved V1/V2 result. Replays instrument evaluation-only channels
and can change planner wall-clock timing; they are not runtime benchmarks.

Common environment prefix used for physical replay:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python
```

Stored-trace 24-case census command:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/aggregate_full3d_startup_dgn_v1.py --formal-root stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/handoff_population_v2.json
```

Aligned-plot command (the five `--episode LABEL PATH` pairs may be supplied
in any order; `_v2` is the corrected authoritative plot set):

```sh
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/analyze_full3d_startup_dgn_v1.py --episode balanced_ordinary_r01 stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/balanced_ordinary_r01/continual_adaptive --episode balanced_ordinary_r02 stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/balanced_ordinary_r02/continual_adaptive --episode hip_ordinary_r01 stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/hip_dominant_ordinary_r01/continual_adaptive --episode knee_middle_r02 stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/knee_dominant_middle_r02/continual_adaptive --episode nominal_development stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_05 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/aligned_existing_traces_v2
```

Pre-step initializer replay:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/diagnose_full3d_initialization_dgn_v1.py --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/hip_dominant_near_upper_current_rom_r01.json --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/elevated_start_ordinary_r02.json --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/elevated_start_middle_r02.json --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/balanced_ordinary_r01.json --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/prestep_initialization_replay_v1.json
```

The failed-case 0.25 ms bed-contact replay:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/replay_full3d_startup_contact_dgn_v1.py --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/balanced_ordinary_r01.json --baseline stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/balanced_ordinary_r01/continual_adaptive --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/contact_replay_balanced_ordinary_r01
```

The separate nominal development comparison replay:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/replay_full3d_startup_contact_dgn_v1.py --case stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json --baseline stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_05 --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/contact_replay_nominal_development
```

Fit-information replay, with exact previously saved 0.25 ms contact times:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/diagnose_full3d_fit_information_dgn_v1.py --case stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases/balanced_ordinary_r01.json --baseline stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_paired_v1/balanced_ordinary_r01/continual_adaptive --contact-replay stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/contact_replay_balanced_ordinary_r01/bed_contact_025ms.npz --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/startup_dgn_v1/fit_information_balanced_ordinary_r01
```

Focused source/diagnostic checks use `python -m py_compile`, JSON parsing,
`git diff --check` and read-only git status. No `git add`, commit, push, reset,
stash, switch, merge or deletion is part of this procedure. For future exact
saved-state *branch* counterfactuals, merely using the same case seed is
insufficient: MuJoCo dynamic state, robot/controller, estimator, reference,
RNG, pending plan and timing state must be restored or the comparison labeled
unmatched. No such branch was claimed in DGN V1.
