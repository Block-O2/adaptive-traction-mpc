# Stage 3 Observation Filtering Report

## Files changed
- Added `src/traction_mpc/estimation/filters.py`.
- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` to preprocess observations and log true/raw/filtered states.
- Added `scripts/run_spring2d_filtering_comparison.py`.

## Scientific setup confirmation
- Spring2D dynamics: unchanged.
- MPC cost and base constraints: unchanged.
- Solver algorithms: unchanged except selecting existing CEM or feasibility-first CEM configs.
- Identifier algorithm: unchanged; only its input observation can be raw or filtered by config.
- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.
- No EKF/UKF, DREM, robust identifier, safe MPC, runtime safety filter, or gravity compensation was added.

## Filter equations
- raw: `x_hat_t = y_t`.
- low-pass: `x_hat_t = (1 - lambda) x_hat_{t-1} + lambda y_t`, with `lambda=0.35`.
- alpha-beta theta/omega: predict `theta` with `theta + dt omega`, then correct theta by `alpha e_theta` and omega by `(beta/dt) e_theta`.
- alpha-beta r/r_dot: predict `r` with `r + dt r_dot`, then correct r by `alpha e_r` and r_dot by `(beta/dt) e_r`.
- oracle: `x_hat_t` is the true simulation state. This is a simulation-only upper-bound reference and is not deployable.

## Commands run
- `conda run -n mpc_learn python scripts/run_spring2d_filtering_comparison.py`

Solvers: cem, cem_feasibility_first
Filters: raw, low_pass, alpha_beta, oracle

## Summary
| solver | filter | condition | target_reached | final theta deg | T_reach | feasible decisions | mean feasible_count | max omega severity | max alpha severity | RMS raw omega | RMS filt omega | omega RMS reduction | omega viol | alpha viol | done_reason | runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| cem | raw | clean | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.000 | 0.000 | 0.000 | 16 | 76 | target_reached | 30.831 |
| cem | raw | noise | True | 91.402 | 1.350 | 0/45 | 0.000 | 2.670 | 58.736 | 0.036 | 0.036 | 0.000 | 44 | 73 | target_reached | 20.153 |
| cem | raw | noise_bias | True | 90.122 | 3.220 | 10/108 | 0.093 | 1.415 | 37.436 | 0.036 | 0.036 | 0.000 | 60 | 145 | target_reached | 48.503 |
| cem | low_pass | clean | True | 90.156 | 1.890 | 0/63 | 0.000 | 0.564 | 5.494 | 0.000 | 0.063 | -0.063 | 25 | 96 | target_reached | 28.758 |
| cem | low_pass | noise | True | 90.018 | 2.060 | 0/69 | 0.000 | 0.608 | 9.188 | 0.035 | 0.064 | -0.028 | 21 | 88 | target_reached | 31.653 |
| cem | low_pass | noise_bias | True | 90.152 | 1.290 | 0/43 | 0.000 | 1.044 | 44.288 | 0.036 | 0.156 | -0.119 | 65 | 94 | target_reached | 19.364 |
| cem | alpha_beta | clean | False | 89.973 | nan | 217/267 | 0.813 | 0.972 | 11.402 | 0.000 | 0.107 | -0.107 | 65 | 76 | max_time | 122.167 |
| cem | alpha_beta | noise | True | 90.001 | 2.180 | 10/73 | 0.137 | 0.981 | 11.204 | 0.035 | 0.212 | -0.176 | 65 | 84 | target_reached | 33.748 |
| cem | alpha_beta | noise_bias | True | 90.041 | 5.690 | 74/190 | 0.389 | 0.941 | 40.706 | 0.038 | 0.167 | -0.130 | 67 | 123 | target_reached | 88.515 |
| cem | oracle | clean | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.000 | 0.000 | 0.000 | 16 | 76 | target_reached | 30.872 |
| cem | oracle | noise | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.035 | 0.000 | 0.035 | 16 | 76 | target_reached | 31.041 |
| cem | oracle | noise_bias | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.036 | 0.000 | 0.036 | 16 | 76 | target_reached | 31.018 |
| cem_feasibility_first | raw | clean | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.000 | 0.000 | 0.000 | 21 | 100 | max_time | 120.798 |
| cem_feasibility_first | raw | noise | True | 90.196 | 1.370 | 0/46 | 0.000 | 2.192 | 55.481 | 0.036 | 0.036 | 0.000 | 54 | 95 | target_reached | 20.831 |
| cem_feasibility_first | raw | noise_bias | True | 90.365 | 3.460 | 18/116 | 0.155 | 0.634 | 50.214 | 0.037 | 0.037 | 0.000 | 66 | 110 | target_reached | 53.625 |
| cem_feasibility_first | low_pass | clean | True | 90.293 | 1.800 | 0/60 | 0.000 | 0.641 | 9.447 | 0.000 | 0.064 | -0.064 | 26 | 105 | target_reached | 27.524 |
| cem_feasibility_first | low_pass | noise | True | 90.175 | 2.670 | 30/89 | 0.337 | 0.667 | 48.005 | 0.034 | 0.075 | -0.041 | 38 | 99 | target_reached | 40.821 |
| cem_feasibility_first | low_pass | noise_bias | False | 87.709 | nan | 113/267 | 0.423 | 0.623 | 25.773 | 0.039 | 0.049 | -0.010 | 22 | 141 | max_time | 124.417 |
| cem_feasibility_first | alpha_beta | clean | True | 90.007 | 2.540 | 6/85 | 0.071 | 1.025 | 12.653 | 0.000 | 0.195 | -0.195 | 47 | 90 | target_reached | 39.785 |
| cem_feasibility_first | alpha_beta | noise | True | 90.175 | 2.600 | 18/87 | 0.207 | 0.998 | 14.126 | 0.034 | 0.203 | -0.168 | 45 | 94 | target_reached | 40.839 |
| cem_feasibility_first | alpha_beta | noise_bias | False | 88.874 | nan | 114/267 | 0.431 | 0.736 | 33.050 | 0.039 | 0.138 | -0.099 | 54 | 178 | max_time | 124.800 |
| cem_feasibility_first | oracle | clean | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.000 | 0.000 | 0.000 | 21 | 100 | max_time | 123.703 |
| cem_feasibility_first | oracle | noise | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.035 | 0.000 | 0.035 | 21 | 100 | max_time | 122.455 |
| cem_feasibility_first | oracle | noise_bias | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.039 | 0.000 | 0.039 | 21 | 100 | max_time | 122.780 |

## Short analysis
Did filtering reduce raw observation error?
- raw: mean omega RMS reduction ratio over noisy conditions = 0.000.
- low_pass: mean omega RMS reduction ratio over noisy conditions = -1.388.
- alpha_beta: mean omega RMS reduction ratio over noisy conditions = -3.981.
- oracle: mean omega RMS reduction ratio over noisy conditions = 1.000.

Did filtering reduce omega/alpha violations and improve feasible decision ratio?
- raw: mean max alpha severity over noisy conditions = 50.467; mean feasible decision ratio = 0.062.
- low_pass: mean max alpha severity over noisy conditions = 31.813; mean feasible decision ratio = 0.190.
- alpha_beta: mean max alpha severity over noisy conditions = 24.772; mean feasible decision ratio = 0.290.
- oracle: mean max alpha severity over noisy conditions = 8.808; mean feasible decision ratio = 0.277.

Did filtering hurt target reaching due to lag?
- cem/alpha_beta/clean: done=max_time, target=False.
- cem_feasibility_first/low_pass/noise_bias: done=max_time, target=False.
- cem_feasibility_first/alpha_beta/noise_bias: done=max_time, target=False.

Did noise_bias remain problematic?
- cem/raw: noise_bias feasible=10/108, omega violations=60, alpha violations=145.
- cem/low_pass: noise_bias feasible=0/43, omega violations=65, alpha violations=94.
- cem/alpha_beta: noise_bias feasible=74/190, omega violations=67, alpha violations=123.
- cem/oracle: noise_bias feasible=0/68, omega violations=16, alpha violations=76.
- cem_feasibility_first/raw: noise_bias feasible=18/116, omega violations=66, alpha violations=110.
- cem_feasibility_first/low_pass: noise_bias feasible=113/267, omega violations=22, alpha violations=141.
- cem_feasibility_first/alpha_beta: noise_bias feasible=114/267, omega violations=54, alpha violations=178.
- cem_feasibility_first/oracle: noise_bias feasible=148/267, omega violations=21, alpha violations=100.

Did oracle indicate that better state estimation would help?
- Oracle reached target in 3/6 runs.

Bad or mixed results were recorded as-is. No parameters were tuned after observing outputs.
