# Stage 4 UKF Estimator Report

## Files changed
- Added `src/traction_mpc/estimation/ukf.py`.
- Updated `src/traction_mpc/estimation/filters.py` for the common estimator interface and UKF factory support.
- Updated `src/traction_mpc/estimation/__init__.py` exports.
- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` to call estimator predict/update and log estimator diagnostics.
- Added `scripts/run_spring2d_estimator_comparison.py`.

## Scientific setup confirmation
- Spring2D dynamics: unchanged.
- MPC cost and base constraints: unchanged.
- Solver algorithms: unchanged; CEM and feasibility-first CEM are selected from existing configs.
- Identifier algorithm: unchanged; only input observation source is configurable as raw or filtered.
- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.
- No DREM, robust identifier, safe MPC, runtime safety filter, or explicit gravity compensation was added.
- UKF prediction uses the current MPC/adaptive model parameters, not true physical parameters. Oracle remains the only clean-state simulation reference.

## Estimator models
- UKF: state `x = [theta, omega, r, r_dot]`, prediction `x_next = Phi_dt(x, u; theta_p) + w`, measurement `y = x + v`.
- Bias-aware UKF: augmented state `z = [x, b]`, random-walk bias `b_next = b + w_b`, measurement `y = x + b + v`.
- Bias-aware UKF estimates effective observation bias; it is not physical parameter identification.
- Oracle uses the simulator true state and is simulation-only, included only as an upper-bound reference.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_estimator_comparison.py`

Primary comparison: solver `cem`, filters raw, alpha_beta, ukf, ukf_bias, oracle.
Secondary comparison: run, filters raw, ukf, ukf_bias, oracle.

## Summary
| solver | filter | condition | target_reached | final theta deg | T_reach | feasible decisions | mean feasible_count | max omega sev | max alpha sev | RMS raw omega | RMS filt omega | omega RMS reduction | mean innovation | max cov trace | UKF failures | omega viol | alpha viol | done_reason | runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| cem | raw | clean | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.000 | 0.000 | 0.000 | nan | nan | 0 | 16 | 76 | target_reached | 31.381 |
| cem | raw | noise | True | 91.402 | 1.350 | 0/45 | 0.000 | 2.670 | 58.736 | 0.036 | 0.036 | 0.000 | nan | nan | 0 | 44 | 73 | target_reached | 20.668 |
| cem | raw | noise_bias | True | 90.122 | 3.220 | 10/108 | 0.093 | 1.415 | 37.436 | 0.036 | 0.036 | 0.000 | nan | nan | 0 | 60 | 145 | target_reached | 49.649 |
| cem | alpha_beta | clean | False | 89.973 | nan | 217/267 | 0.813 | 0.972 | 11.402 | 0.000 | 0.107 | -0.107 | nan | nan | 0 | 65 | 76 | max_time | 125.619 |
| cem | alpha_beta | noise | True | 90.001 | 2.180 | 10/73 | 0.137 | 0.981 | 11.204 | 0.035 | 0.212 | -0.176 | nan | nan | 0 | 65 | 84 | target_reached | 34.573 |
| cem | alpha_beta | noise_bias | True | 90.041 | 5.690 | 74/190 | 0.389 | 0.941 | 40.706 | 0.038 | 0.167 | -0.130 | nan | nan | 0 | 67 | 123 | target_reached | 90.892 |
| cem | ukf | clean | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.000 | 0.000 | -0.000 | 0.006 | 0.071 | 0 | 16 | 76 | target_reached | 31.903 |
| cem | ukf | noise | True | 90.081 | 4.810 | 76/161 | 0.472 | 0.406 | 7.719 | 0.035 | 0.025 | 0.010 | 0.037 | 0.071 | 0 | 19 | 94 | target_reached | 77.096 |
| cem | ukf | noise_bias | False | 87.199 | nan | 100/267 | 0.375 | 0.390 | 7.481 | 0.039 | 0.029 | 0.010 | 0.035 | 0.071 | 0 | 19 | 96 | max_time | 127.955 |
| cem | ukf_bias | clean | True | 90.146 | 2.060 | 0/69 | 0.000 | 0.427 | 6.438 | 0.000 | 0.009 | -0.009 | 0.007 | 0.073 | 0 | 17 | 84 | target_reached | 32.766 |
| cem | ukf_bias | noise | True | 90.217 | 1.800 | 0/60 | 0.000 | 0.443 | 7.694 | 0.035 | 0.031 | 0.004 | 0.043 | 0.073 | 0 | 16 | 66 | target_reached | 28.481 |
| cem | ukf_bias | noise_bias | True | 90.014 | 2.190 | 0/73 | 0.000 | 0.450 | 7.790 | 0.037 | 0.026 | 0.011 | 0.038 | 0.073 | 0 | 22 | 90 | target_reached | 34.953 |
| cem | oracle | clean | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.000 | 0.000 | 0.000 | nan | nan | 0 | 16 | 76 | target_reached | 32.071 |
| cem | oracle | noise | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.035 | 0.000 | 0.035 | nan | nan | 0 | 16 | 76 | target_reached | 31.986 |
| cem | oracle | noise_bias | True | 90.070 | 2.040 | 0/68 | 0.000 | 0.397 | 8.071 | 0.036 | 0.000 | 0.036 | nan | nan | 0 | 16 | 76 | target_reached | 32.068 |
| cem_feasibility_first | raw | clean | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.000 | 0.000 | 0.000 | nan | nan | 0 | 21 | 100 | max_time | 125.775 |
| cem_feasibility_first | raw | noise | True | 90.196 | 1.370 | 0/46 | 0.000 | 2.192 | 55.481 | 0.036 | 0.036 | 0.000 | nan | nan | 0 | 54 | 95 | target_reached | 21.716 |
| cem_feasibility_first | raw | noise_bias | True | 90.365 | 3.460 | 18/116 | 0.155 | 0.634 | 50.214 | 0.037 | 0.037 | 0.000 | nan | nan | 0 | 66 | 110 | target_reached | 54.976 |
| cem_feasibility_first | ukf | clean | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.000 | 0.000 | -0.000 | 0.002 | 0.071 | 0 | 21 | 100 | max_time | 126.844 |
| cem_feasibility_first | ukf | noise | True | 90.489 | 4.380 | 65/146 | 0.445 | 0.568 | 44.069 | 0.035 | 0.025 | 0.009 | 0.038 | 0.071 | 0 | 29 | 106 | target_reached | 69.831 |
| cem_feasibility_first | ukf | noise_bias | False | 87.382 | nan | 79/267 | 0.296 | 0.376 | 8.394 | 0.039 | 0.029 | 0.009 | 0.035 | 0.071 | 0 | 25 | 119 | max_time | 128.516 |
| cem_feasibility_first | ukf_bias | clean | True | 90.013 | 2.040 | 1/68 | 0.015 | 0.460 | 8.879 | 0.000 | 0.010 | -0.010 | 0.009 | 0.073 | 0 | 29 | 94 | target_reached | 32.347 |
| cem_feasibility_first | ukf_bias | noise | True | 90.268 | 4.510 | 60/151 | 0.397 | 0.538 | 19.024 | 0.035 | 0.027 | 0.007 | 0.038 | 0.073 | 0 | 28 | 111 | target_reached | 72.347 |
| cem_feasibility_first | ukf_bias | noise_bias | True | 90.121 | 4.120 | 56/138 | 0.406 | 0.398 | 42.136 | 0.037 | 0.027 | 0.010 | 0.038 | 0.073 | 0 | 39 | 117 | target_reached | 65.902 |
| cem_feasibility_first | oracle | clean | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.000 | 0.000 | 0.000 | nan | nan | 0 | 21 | 100 | max_time | 125.612 |
| cem_feasibility_first | oracle | noise | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.035 | 0.000 | 0.035 | nan | nan | 0 | 21 | 100 | max_time | 125.272 |
| cem_feasibility_first | oracle | noise_bias | False | 89.580 | nan | 148/267 | 0.554 | 0.422 | 9.544 | 0.039 | 0.000 | 0.039 | nan | nan | 0 | 21 | 100 | max_time | 125.388 |

## Short analysis
Did UKF reduce filtered state RMS error compared with raw and alpha-beta?
- cem/noise: lowest omega filtered RMS among comparable filters was ukf (0.025).
- cem/noise_bias: lowest omega filtered RMS among comparable filters was ukf_bias (0.026).
- cem_feasibility_first/noise: lowest omega filtered RMS among comparable filters was ukf (0.025).
- cem_feasibility_first/noise_bias: lowest omega filtered RMS among comparable filters was ukf_bias (0.027).
- cem/ukf/noise_bias: target=False, feasible=100/267, max alpha severity=7.481.
- cem/ukf_bias/noise_bias: target=True, feasible=0/73, max alpha severity=7.790.
- cem_feasibility_first/ukf/noise_bias: target=False, feasible=79/267, max alpha severity=8.394.
- cem_feasibility_first/ukf_bias/noise_bias: target=True, feasible=56/138, max alpha severity=42.136.

Did bias-aware UKF improve noise_bias?
- cem/ukf/noise_bias: omega RMS reduction=0.010, theta RMS reduction=0.001, done=max_time.
- cem/ukf_bias/noise_bias: omega RMS reduction=0.011, theta RMS reduction=0.003, done=target_reached.
- cem_feasibility_first/ukf/noise_bias: omega RMS reduction=0.009, theta RMS reduction=0.001, done=max_time.
- cem_feasibility_first/ukf_bias/noise_bias: omega RMS reduction=0.010, theta RMS reduction=0.002, done=target_reached.

Did UKF reduce omega/alpha violation severity or improve feasible decision ratio?
- cem/ukf/noise: feasible ratio=0.472, max omega severity=0.406, max alpha severity=7.719.
- cem/ukf/noise_bias: feasible ratio=0.375, max omega severity=0.390, max alpha severity=7.481.
- cem/ukf_bias/noise: feasible ratio=0.000, max omega severity=0.443, max alpha severity=7.694.
- cem/ukf_bias/noise_bias: feasible ratio=0.000, max omega severity=0.450, max alpha severity=7.790.
- cem_feasibility_first/ukf/noise: feasible ratio=0.445, max omega severity=0.568, max alpha severity=44.069.
- cem_feasibility_first/ukf/noise_bias: feasible ratio=0.296, max omega severity=0.376, max alpha severity=8.394.
- cem_feasibility_first/ukf_bias/noise: feasible ratio=0.397, max omega severity=0.538, max alpha severity=19.024.
- cem_feasibility_first/ukf_bias/noise_bias: feasible ratio=0.406, max omega severity=0.398, max alpha severity=42.136.

Did UKF hurt target reaching due to model bias or lag?
- cem/ukf/noise_bias: target=False, done=max_time.
- cem_feasibility_first/ukf/clean: target=False, done=max_time.
- cem_feasibility_first/ukf/noise_bias: target=False, done=max_time.

Did any UKF failure occur?
- cem/ukf/clean: failures=0.
- cem/ukf/noise: failures=0.
- cem/ukf/noise_bias: failures=0.
- cem/ukf_bias/clean: failures=0.
- cem/ukf_bias/noise: failures=0.
- cem/ukf_bias/noise_bias: failures=0.
- cem_feasibility_first/ukf/clean: failures=0.
- cem_feasibility_first/ukf/noise: failures=0.
- cem_feasibility_first/ukf/noise_bias: failures=0.
- cem_feasibility_first/ukf_bias/clean: failures=0.
- cem_feasibility_first/ukf_bias/noise: failures=0.
- cem_feasibility_first/ukf_bias/noise_bias: failures=0.

Bad or mixed results were recorded as-is. No parameters were tuned after observing outputs.
