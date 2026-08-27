# Stage-4 Reproducible Baseline Checkpoint

Status: baseline checkpoint frozen by Git tag `stage4-baseline-v1` after the
2026-08-28 audit. The closed-loop evidence retains its recorded category
`formal_user_run_unreviewed`. This document does not relabel a scientific run
as authoritative.

## Baseline architecture and frozen contract

- Plant: 3D torque-actuated UR10e surrogate, Human V2, and explicit rigid cuff.
- Allocation: frozen 1:1 cuff-aware sagittal allocator. Its cylindrical
  minimum-norm surface-load quantity is a mathematical proxy, not pressure,
  comfort, or tissue loading.
- Estimation: accumulated integral 11-base Human dynamics identifier with the
  existing physical box constraints. The resulting beta is a control-effective
  representation; it is not validated physical parameter truth.
- Trust: unchanged L1 measurement validity, L2 state/geometry validity, L3
  identification-quality reporting, and causal statistical L4 with one fixed
  incumbent and at most one challenger.
- Execution: existing confidence pacing with low-pass filtering and hysteresis.
- MPC scientific definition: feasible-first CEM, 32 candidates, 2 iterations,
  horizon 15, 6 elites, seed 20260824, original tracking/action/action-slew
  objective, and unchanged constraints. The interaction weights remain zero.
- Engineering implementation: `HumanSpaceMPC()` defaults to the behaviorally
  equivalent batched implementation. `HumanSpaceMPC(implementation="scalar")`
  remains the regression and fallback reference. Unsupported model/allocator
  combinations fall back to scalar population evaluation.
- Explicitly absent: online UKF/Kalman estimation, hybrid optimizer, tracking
  corridor/tube, and active excitation. Some optional historical modules remain
  import dependencies but are not enabled in this baseline.

No scientific parameter, bound, weight, safety limit, trajectory, sensor
assumption, or RNG semantic is changed by this checkpoint.

## Formal closed-loop A/B headline

Registered case: perturbed Human, continuous 23 s reference, 32 s wall-time
observation window, `noise_bias_drift_200hz`, measurement seed 44104, and the
shared frozen controller above. The first trusted-adaptive promotion occurred
at wall time 9.72 s / reference phase 4.86 s, leaving 18.14 s of reference.
Both arms completed at wall time 28.87 s. The causal isolation checks were
exact before promotion and no solver, force-gate, ROM, unintended-contact, or
MuJoCo warning event was recorded.

| full-task metric | prior-only | trusted adaptive |
|---|---:|---:|
| tracking RMSE (deg) | 0.765477 | 0.713056 |
| maximum tracking error (deg) | 1.819879 | 1.561138 |
| control-model torque prediction RMSE (Nm) | 4.424389 | 3.968691 |
| cuff force peak / RMS (N) | 143.896 / 103.442 | 144.637 / 103.533 |
| cuff moment peak / RMS (Nm) | 20.437 / 12.879 | 20.437 / 12.874 |
| cylindrical surface proxy peak / RMS (N) | 133.918 / 86.721 | 133.918 / 86.695 |

Observed tracking RMSE decreased by 6.85% and control-model torque prediction
RMSE decreased by 10.30%. Force, moment, and surface-proxy changes were
negligible and not consistently favorable. Therefore the supported conclusion
is: **adaptation improves tracking and prediction, not cuff interaction**.

## Realtime implementation headline

The engineering replay uses the saved trusted-adaptive trace as fixed input,
seed 20260824, 10 warm-up calls, and 30 measured calls repeated three times.

| implementation | MPC mean / p95 / max (ms) | full-cycle mean / p95 / max (ms) |
|---|---:|---:|
| scalar | 175.212 / 176.634 / 199.668 | 185.220 / 187.293 / 207.753 |
| batched | 9.422 / 9.583 / 9.766 | 16.524 / 17.789 / 18.641 |

The batched MPC speedup is 18.60x and the full replay cycle speedup is 11.21x.
The measured full-cycle mean corresponds to 60.5 Hz. **At least 30 Hz is
supported by desktop replay timing, not hard-realtime hardware proof.** The
same caveat applies to the observed 50 Hz replay result: OS scheduling, real
drivers, I/O blocking, and target-hardware worst-case jitter have not been
validated.

## What is and is not established

Established for this registered simulation/replay configuration:

- causal single-incumbent/challenger lifecycle without race or superseded state;
- measurable tracking and generalized-torque prediction benefit from trusted
  adaptation;
- scalar/batched agreement for candidate populations, elite updates, selected
  action, objective, Human generalized torque, cuff allocation, short rollout,
  and safety events to tight floating-point tolerances;
- desktop replay feasibility above 30 Hz, with all measured optimized samples
  below 20 ms in the recorded timing audit.

Not established:

- robustness across patient/model mismatch, sensor regimes, or hardware;
- physical truth of the identified 11-base beta;
- reduced cuff interaction due to adaptation;
- hard-realtime deadline guarantees;
- clinical efficacy, comfort, tissue safety, certification, or production
  readiness. **No clinical or production claim is made.**

Known limitations include one registered perturbed Human and trajectory, late
causal validation relative to a short task, sensor-bias/parameter-compensation
risk, simulation-only plant/contact assumptions, and unpinned package versions
in `requirements.txt`. The audited environment was Python 3.10.20, NumPy 2.2.6,
SciPy 1.15.3, MuJoCo 3.10.0, and pytest 9.1.1.

The next planned scientific question is **patient/model mismatch robustness**.

## Minimum reproducible checkpoint manifest

Runtime/environment and plant assets:

- `pyproject.toml`, `requirements.txt`
- `models/ur10e_torque.xml`
- `vendor/mujoco_menagerie/universal_robots_ur10e/ur10e.xml`
- `vendor/mujoco_menagerie/universal_robots_ur10e/assets/`
- `src/traction_mpc_stage3/{__init__,coupled,frames,human,ik,reference,robot,robot_backends,robot_interface}.py`

Stage-4 control and trust implementation:

- `src/traction_mpc_stage4/{__init__,adaptive_estimators,cold_start,confidence_execution,cuff_allocator,dynamics_failure_audit,estimator_v2,evaluation,hierarchical_trust,human_model,identifiability,identifier,integral_identifier,measurement,minimal_adaptation,mpc,online_trust,reference,sensor_realism,state_ukf,statistical_trust,surface_loads}.py`
- `scripts/run_stage4_single_challenger_closed_loop_ab.py`
- `scripts/profile_stage4_realtime.py`

Direct checkpoint tests:

- `tests/test_stage3c_human_rigid_cuff.py`
- `tests/test_ur10e_robot_core.py`
- every `tests/test_stage4_*.py` file, including the scalar/batched equivalence
  and default/fallback assertions in `tests/test_stage4_mpc.py`

To keep the full Stage-4 regression suite and the historical negative-audit
implementations reproducible, the checkpoint also retains the remaining
current `src/traction_mpc_stage4/*.py`, Stage-4 scripts, Stage-4 tests, and
Stage-4 documentation. These are code/protocol evidence; their experimental
branches are not enabled in the frozen controller. In particular this includes
the cuff trade-off, distributed-cuff, trust-rule, oracle-chain, reduced-model,
action-Pareto, local-resolution, and hybrid-optimizer audit implementations.

Protocol and summary:

- `docs/research/STAGE4_SINGLE_CHALLENGER_CLOSED_LOOP_AB_SPEC.md`
- `docs/research/CURRENT_STATE.md`

Canonical formal evidence, all six files retained:

- `results/stage4_single_challenger_closed_loop_ab_formal/{prior_only,trusted_adaptive}.json`
- `results/stage4_single_challenger_closed_loop_ab_formal/{prior_only,trusted_adaptive}_trace.npz`
- `results/stage4_single_challenger_closed_loop_ab_formal/comparison_summary.{json,md}`

Canonical realtime evidence:

- `results/stage4_realtime_implementation_sprint_20260828/baseline_sections_v2/{timing.json,cprofile.txt}`
- `results/stage4_realtime_implementation_sprint_20260828/optimized_final_v3/{timing.json,cprofile.txt}`

The trusted-adaptive trace is also the fixed replay input for the realtime
benchmark, so no duplicate trace is required.

Canonical evidence SHA-256:

```text
870d546aa608193bbd63664604880b94b557d0e3b370745ab561f0e67445a6b3  comparison_summary.json
fda74e3ac9178091c1d8acdd02cb697223af2aebaab59a12d5608d8a5eef2c7b  comparison_summary.md
b5e3b697f95af715061702e660a370c6f461ab9bda376a05f8dce8aed6528cff  prior_only.json
2ef8e9b9b34b20bebed9c02f562e39240cb912424c4ebc24edaa48b81ee981b2  prior_only_trace.npz
5defec210f0dec8368b410f50c9443761402a95befbf67ca8cc380851a8ef2ce  trusted_adaptive.json
7dd4da7fba462912835b5c10fce878b272ac34d0945e5488e3f732932ae55c70  trusted_adaptive_trace.npz
0d4e2e29554a810678d505325875bb9a98f925bacb3f4d309a24e09964de9fb7  scalar timing.json
c7b81095423f353748cbad25d6dce9fa08b6e01b0c07f499470e117808d887ff  scalar cprofile.txt
3ed2fc4411c9440349e4bcece53795978b815f38be795a1f15370032e082da97  batched timing.json
3b2df53db6033e95a6a54539dc275a78d1b2da32b4ce5f3ea9d584622d87a040  batched cprofile.txt
```

## Reproduction commands

Formal A/B is a user-run experiment. Do not overwrite the frozen output and do
not rerun it merely to validate this checkpoint. If an independent reproduction
is later authorized, run from `stages/stage3_full3d` into a new directory:

```bash
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_single_challenger_closed_loop_ab.py \
  --output-dir results/stage4_single_challenger_closed_loop_ab_reproduction
```

Realtime scalar replay:

```bash
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/profile_stage4_realtime.py \
  --trace results/stage4_single_challenger_closed_loop_ab_formal/trusted_adaptive_trace.npz \
  --output-dir results/stage4_realtime_reproduction_scalar \
  --implementation scalar --warmup-calls 10 --measured-calls 30 \
  --repeats 3 --profile-calls 10
```

Realtime batched replay uses the same command with a distinct output directory
and `--implementation batched`.

## Retention and later cleanup candidates

All historical negative evidence and formal outputs remain preserved. The
following realtime-only directories are superseded intermediate runs and are
not part of the minimum checkpoint: `baseline`, `baseline_detail`,
`baseline_full_cycle`, `baseline_v2`, `optimized_smoke`, `optimized_smoke_v2`,
`optimized_final`, and `optimized_final_v2`. They may be removed or archived in
a separately authorized cleanup after the checkpoint is committed. Python
`__pycache__` and `.pytest_cache` directories are also regenerable. Nothing is
deleted by this audit.
