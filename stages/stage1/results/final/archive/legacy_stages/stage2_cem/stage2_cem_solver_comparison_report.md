# Stage 2 CEM Solver Comparison Report

## Code/files changed
- Added solver abstraction under `src/traction_mpc/mpc/solvers/`.
- Updated `src/traction_mpc/mpc/fixed_mpc.py` to select solver by config.
- Updated adaptive condition loading to accept top-level `mpc_overrides`.
- Added `configs/spring2d_adaptive_mpc_conditions_cem.yaml`.
- Added `scripts/run_spring2d_solver_comparison.py`.

## Scientific setup confirmation
- Cost definition: unchanged; both solvers call the same `stage_cost` and `terminal_cost` callbacks.
- Constraints: unchanged; both solvers call the same constraint callback and penalty.
- Dynamics: unchanged; both solvers call the same Spring2D `step_dynamics` rollout callback.
- Identifier: unchanged; both runs use the existing windowed least-squares identifier config.
- Observation noise/bias settings: unchanged across clean/noise/noise_bias.
- No safe/robust MPC, EKF/UKF, robust identifier, gravity compensation, or post-result tuning was added.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_solver_comparison.py`

## Solver settings
- random_shooting: type=random_shooting, horizon=18, prediction_dt=0.03, num_samples=96, elite_frac=0.15, iterations=2, action_std=[2.5, 0.8], min_std=[0.25, 0.1], seed=23
- cem: type=cem, horizon=18, prediction_dt=0.03, num_samples=128, num_elites=16, iterations=3, cem_alpha=0.7, init_std_F_tan=4.0, init_std_F_rad=0.3, min_std_F_tan=0.2, min_std_F_rad=0.05, seed=23, warm_start=True

## Summary
| solver | condition | target_reached | final theta deg | T_reach | max abs F_rad | max abs delta_r | max abs omega | max abs alpha_step | max abs F_tan | feasible decisions | omega viol | alpha viol | done_reason | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| random_shooting | clean | False | 89.929 | nan | 0.735518 | 0.012071 | 1.89444 | 15.1641 | 9.14496 | 220/267 | 56 | 79 | max_time | 59.622 |
| random_shooting | noise | True | 90.912 | 1.880 | 0.995762 | 0.0119358 | 2.03455 | 50.3062 | 9.20637 | 1/63 | 58 | 91 | target_reached | 14.649 |
| random_shooting | noise_bias | True | 90.052 | 1.830 | 1 | 0.0122448 | 1.78855 | 44.1193 | 9.43977 | 0/61 | 31 | 92 | target_reached | 13.917 |
| cem | clean | True | 90.070 | 2.040 | 0.811119 | 0.0116697 | 1.59652 | 11.0711 | 8.06695 | 0/68 | 16 | 76 | target_reached | 30.218 |
| cem | noise | True | 91.402 | 1.350 | 0.80961 | 0.0105019 | 3.87034 | 61.7359 | 11.2196 | 0/45 | 44 | 73 | target_reached | 19.571 |
| cem | noise_bias | True | 90.122 | 3.220 | 0.70873 | 0.0120018 | 2.6146 | 40.4358 | 11.7072 | 10/108 | 60 | 145 | target_reached | 47.550 |

## Short analysis
Did CEM improve feasible decision ratio?
- clean: decision ratio 0.824 -> 0.000.
- noise: decision ratio 0.016 -> 0.000.
- noise_bias: decision ratio 0.000 -> 0.093.

Did CEM improve final theta or target reaching?
- clean: final theta 89.929 deg -> 90.070 deg; target False -> True.
- noise: final theta 90.912 deg -> 91.402 deg; target True -> True.
- noise_bias: final theta 90.052 deg -> 90.122 deg; target True -> True.

Did CEM reduce omega/alpha violations?
- clean: omega violations 56 -> 16; alpha violations 79 -> 76.
- noise: omega violations 58 -> 44; alpha violations 91 -> 73.
- noise_bias: omega violations 31 -> 60; alpha violations 92 -> 145.

Did noise/noise_bias remain problematic?
- noise: both solvers reached the target=True, but feasibility/violations remained nontrivial random_shooting feasible=1/63, cem feasible=0/45, omega violations 58->44, alpha violations 91->73.
- noise_bias: both solvers reached the target=True, but feasibility/violations remained nontrivial random_shooting feasible=0/61, cem feasible=10/108, omega violations 31->60, alpha violations 92->145.
- clean: non-target termination observed random_shooting=max_time, cem=target_reached.

Bad or unexpected results were recorded as-is. No parameters were tuned after observing these outputs.
