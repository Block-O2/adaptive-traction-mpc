# Stage 2 CEM Feasibility-First Solver Comparison Report

## Code/files changed
- Added/updated solver abstraction under `src/traction_mpc/mpc/solvers/`.
- Updated `src/traction_mpc/mpc/solvers/cem.py` to support `selection: feasibility_first`.
- Updated shared solver diagnostics for task cost and violation severity.
- Updated `src/traction_mpc/mpc/fixed_mpc.py` to select solver by config.
- Updated adaptive condition loading to accept top-level `mpc_overrides`.
- Added `configs/spring2d_adaptive_mpc_conditions_cem.yaml`.
- Added `configs/spring2d_adaptive_mpc_conditions_cem_feasfirst.yaml`.
- Added `scripts/run_spring2d_solver_comparison.py`.

## Scientific setup confirmation
- Cost definition: unchanged; all solvers call the same `stage_cost` and `terminal_cost` callbacks.
- Constraints: unchanged; all solvers call the same constraint callback and penalty.
- Dynamics: unchanged; all solvers call the same Spring2D `step_dynamics` rollout callback.
- Identifier: unchanged; all runs use the existing windowed least-squares identifier config.
- Observation noise/bias settings: unchanged across clean/noise/noise_bias.
- Physical parameters, gravity handling, and max_time were unchanged.
- No safe/robust MPC, EKF/UKF, robust identifier, observation filtering, gravity compensation, or post-result tuning was added.

## Selection rule change
- Old CEM ranking: candidates and elites are ordered by penalized cost `J(U) + penalty(U)`.
- Feasibility-first CEM ranking: candidates and elites are ordered lexicographically by `(not feasible(U), violation_score(U), task_cost(U))`.
- This puts every feasible sequence ahead of every infeasible sequence; if none are feasible, the least-violating sequence is selected and task cost is only the tie-breaker.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_solver_comparison.py`
- `python scripts/run_spring2d_solver_comparison.py --random-config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_adaptive_mpc_conditions.yaml --cem-config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_adaptive_mpc_conditions_cem.yaml --cem-feasfirst-config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_adaptive_mpc_conditions_cem_feasfirst.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage2_cem_feasfirst`

## Solver settings
- random_shooting: type=random_shooting, horizon=18, prediction_dt=0.03, num_samples=96, elite_frac=0.15, iterations=2, action_std=[2.5, 0.8], min_std=[0.25, 0.1], seed=23
- cem: type=cem, horizon=18, prediction_dt=0.03, num_samples=128, num_elites=16, iterations=3, cem_alpha=0.7, init_std_F_tan=4.0, init_std_F_rad=0.3, min_std_F_tan=0.2, min_std_F_rad=0.05, seed=23, warm_start=True
- cem_feasibility_first: type=cem, selection=feasibility_first, horizon=18, prediction_dt=0.03, num_samples=128, num_elites=16, iterations=3, cem_alpha=0.7, init_std_F_tan=4.0, init_std_F_rad=0.3, min_std_F_tan=0.2, min_std_F_rad=0.05, seed=23, warm_start=True, violation_weights={'F_tan': 1.0, 'F_rad': 1.0, 'delta_r': 1.0, 'omega': 1.0, 'alpha': 1.0}

## Summary
| solver | condition | target_reached | final theta deg | T_reach | max abs F_rad | max abs delta_r | max abs omega | max abs alpha_step | max abs F_tan | feasible decisions | mean feasible_count | max omega viol severity | max alpha viol severity | max delta_r viol severity | max F_rad viol severity | omega viol | alpha viol | done_reason | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| random_shooting | clean | False | 89.929 | nan | 0.735518 | 0.012071 | 1.89444 | 15.1641 | 9.14496 | 220/267 | 0.824 | 0.694435 | 12.1641 | 0 | 0 | 56 | 79 | max_time | 62.757 |
| random_shooting | noise | True | 90.912 | 1.880 | 0.995762 | 0.0119358 | 2.03455 | 50.3062 | 9.20637 | 1/63 | 0.016 | 0.83455 | 47.3062 | 0 | 0 | 58 | 91 | target_reached | 15.370 |
| random_shooting | noise_bias | True | 90.052 | 1.830 | 1 | 0.0122448 | 1.78855 | 44.1193 | 9.43977 | 0/61 | 0.000 | 0.588548 | 41.1193 | 0 | 0 | 31 | 92 | target_reached | 14.600 |
| cem | clean | True | 90.070 | 2.040 | 0.811119 | 0.0116697 | 1.59652 | 11.0711 | 8.06695 | 0/68 | 0.000 | 0.396525 | 8.07113 | 0 | 0 | 16 | 76 | target_reached | 31.839 |
| cem | noise | True | 91.402 | 1.350 | 0.80961 | 0.0105019 | 3.87034 | 61.7359 | 11.2196 | 0/45 | 0.000 | 2.67034 | 58.7359 | 0 | 0 | 44 | 73 | target_reached | 20.734 |
| cem | noise_bias | True | 90.122 | 3.220 | 0.70873 | 0.0120018 | 2.6146 | 40.4358 | 11.7072 | 10/108 | 0.093 | 1.4146 | 37.4358 | 0 | 0 | 60 | 145 | target_reached | 49.950 |
| cem_feasibility_first | clean | False | 89.580 | nan | 0.780517 | 0.0116782 | 1.62163 | 12.5443 | 8.6395 | 148/267 | 0.554 | 0.421625 | 9.54428 | 0 | 0 | 21 | 100 | max_time | 124.708 |
| cem_feasibility_first | noise | True | 90.196 | 1.370 | 0.872651 | 0.0111121 | 3.39161 | 58.4807 | 11.086 | 0/46 | 0.000 | 2.19161 | 55.4807 | 0 | 0 | 54 | 95 | target_reached | 21.502 |
| cem_feasibility_first | noise_bias | True | 90.365 | 3.460 | 0.715849 | 0.0119185 | 1.83395 | 53.2137 | 8.69602 | 18/116 | 0.155 | 0.633953 | 50.2137 | 0 | 0 | 66 | 110 | target_reached | 54.647 |

## Short analysis
Did feasibility-first CEM improve feasible decision ratio?
- clean: CEM 0.000 -> feasibility_first 0.554.
- noise: CEM 0.000 -> feasibility_first 0.000.
- noise_bias: CEM 0.093 -> feasibility_first 0.155.

Did it reduce violation severity, not only violation count?
- clean: max omega severity 0.396525 -> 0.421625; max alpha severity 8.07113 -> 9.54428; counts omega 16 -> 21, alpha 76 -> 100.
- noise: max omega severity 2.67034 -> 2.19161; max alpha severity 58.7359 -> 55.4807; counts omega 44 -> 54, alpha 73 -> 95.
- noise_bias: max omega severity 1.4146 -> 0.633953; max alpha severity 37.4358 -> 50.2137; counts omega 60 -> 66, alpha 145 -> 110.

Did it hurt target reaching?
- clean: final theta 90.070 deg -> 89.580 deg; target True -> False.
- noise: final theta 91.402 deg -> 90.196 deg; target True -> True.
- noise_bias: final theta 90.122 deg -> 90.365 deg; target True -> True.

Did noise/noise_bias remain problematic?
- clean: non-target termination observed cem=target_reached, feasibility_first=max_time.
- noise: target reached CEM=True, feasibility_first=True; feasible decisions CEM=0/45, feasibility_first=0/46.
- noise_bias: target reached CEM=True, feasibility_first=True; feasible decisions CEM=10/108, feasibility_first=18/116.

Bad or unexpected results were recorded as-is. No parameters were tuned after observing these outputs.
