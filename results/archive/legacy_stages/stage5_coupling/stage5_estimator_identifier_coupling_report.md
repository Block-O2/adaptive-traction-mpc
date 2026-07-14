# Stage 5 Estimator-Identifier Coupling Report

## Files changed
- Added `configs/spring2d_estimator_identifier_coupling.yaml`.
- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` with backward-compatible coupling-ablation controls.
- Added `scripts/run_spring2d_coupling_ablation.py`.

## Scientific setup confirmation
- Spring2D dynamics: unchanged.
- MPC cost and base constraints: unchanged.
- CEM solver algorithm: unchanged.
- UKF/UKF-bias algorithm: unchanged.
- Windowed NLS identifier algorithm: unchanged; only input source and update application are ablated.
- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.
- No DREM, robust identifier, EKF, safe MPC, runtime safety filter, or explicit gravity compensation was added.

## Coupling cases
- Case A: filtered state to MPC and identifier, adaptive identifier updates MPC, UKF uses adaptive model parameters.
- Case B: filtered state to MPC, raw state to identifier, adaptive identifier updates MPC, UKF uses adaptive model parameters.
- Case C: filtered state to MPC, identifier input none, identifier frozen, UKF and MPC use initial model parameters.
- Case D: filtered state to MPC and identifier, adaptive identifier updates MPC, UKF uses initial model parameters.
- Case E: filtered state to MPC, oracle true state to identifier, adaptive identifier updates MPC. This is simulation-only.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_coupling_ablation.py`

## Summary
| filter | case | condition | target | final theta deg | T_reach | feasible | max omega sev | max alpha sev | RMS filt omega | updates | max param step | final m | final k | final b_r | UKF fail | done | runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| ukf | case_A_current_adaptive | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.898 | 1.200 | 450.069 | 17.298 | 0 | target_reached | 31.765 |
| ukf | case_A_current_adaptive | noise | True | 90.081 | 4.810 | 76/161 | 0.406 | 7.719 | 0.025 | 48 | 42.648 | 1.140 | 413.831 | 43.205 | 0 | target_reached | 76.000 |
| ukf | case_A_current_adaptive | noise_bias | False | 87.199 | nan | 100/267 | 0.390 | 7.481 | 0.029 | 80 | 39.213 | 1.379 | 614.716 | 45.000 | 0 | max_time | 126.506 |
| ukf | case_B_mpc_only_raw_identifier | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.619 |
| ukf | case_B_mpc_only_raw_identifier | noise | True | 90.035 | 1.740 | 0/58 | 0.402 | 7.280 | 0.028 | 17 | 41.028 | 1.207 | 432.586 | 45.000 | 0 | target_reached | 27.242 |
| ukf | case_B_mpc_only_raw_identifier | noise_bias | True | 90.703 | 3.140 | 5/105 | 0.556 | 53.075 | 0.028 | 31 | 154.585 | 1.182 | 513.323 | 45.000 | 0 | target_reached | 48.015 |
| ukf | case_C_frozen_identifier | clean | False | 10.682 | nan | 0/267 | 0.000 | 15.423 | 0.000 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | max_time | 114.824 |
| ukf | case_C_frozen_identifier | noise | False | 10.030 | nan | 0/267 | 0.000 | 14.467 | 0.071 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | max_time | 114.656 |
| ukf | case_C_frozen_identifier | noise_bias | False | 9.248 | nan | 0/267 | 0.000 | 15.116 | 0.055 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | max_time | 114.494 |
| ukf | case_D_frozen_estimator_model | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.876 | 1.200 | 450.082 | 17.293 | 0 | target_reached | 31.618 |
| ukf | case_D_frozen_estimator_model | noise | True | 90.084 | 4.940 | 75/165 | 0.329 | 71.642 | 0.039 | 49 | 42.648 | 1.138 | 440.315 | 41.684 | 0 | target_reached | 77.853 |
| ukf | case_D_frozen_estimator_model | noise_bias | False | 87.132 | nan | 46/267 | 0.334 | 7.481 | 0.032 | 80 | 23.832 | 1.266 | 509.602 | 45.000 | 0 | max_time | 126.633 |
| ukf | case_E_oracle_identifier | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.770 |
| ukf | case_E_oracle_identifier | noise | True | 90.045 | 2.140 | 1/72 | 0.387 | 7.413 | 0.027 | 21 | 43.964 | 1.200 | 450.063 | 17.406 | 0 | target_reached | 33.576 |
| ukf | case_E_oracle_identifier | noise_bias | False | 86.929 | nan | 188/267 | 0.406 | 8.016 | 0.028 | 80 | 40.574 | 1.200 | 449.999 | 17.398 | 0 | max_time | 125.013 |
| ukf_bias | case_A_current_adaptive | clean | True | 90.146 | 2.060 | 0/69 | 0.427 | 6.438 | 0.009 | 20 | 58.776 | 1.173 | 342.004 | 10.272 | 0 | target_reached | 32.374 |
| ukf_bias | case_A_current_adaptive | noise | True | 90.217 | 1.800 | 0/60 | 0.443 | 7.694 | 0.031 | 18 | 79.871 | 1.186 | 280.100 | 24.331 | 0 | target_reached | 28.279 |
| ukf_bias | case_A_current_adaptive | noise_bias | True | 90.014 | 2.190 | 0/73 | 0.450 | 7.790 | 0.026 | 21 | 57.657 | 1.192 | 306.607 | 26.937 | 0 | target_reached | 34.567 |
| ukf_bias | case_B_mpc_only_raw_identifier | clean | True | 90.034 | 1.970 | 0/66 | 0.431 | 7.993 | 0.008 | 19 | 44.734 | 1.200 | 450.080 | 17.369 | 0 | target_reached | 31.095 |
| ukf_bias | case_B_mpc_only_raw_identifier | noise | True | 91.761 | 1.270 | 0/43 | 4.045 | 57.145 | 0.034 | 12 | 41.063 | 1.196 | 415.532 | 45.000 | 0 | target_reached | 19.833 |
| ukf_bias | case_B_mpc_only_raw_identifier | noise_bias | True | 90.069 | 0.970 | 0/33 | 2.203 | 37.149 | 0.029 | 9 | 160.811 | 1.208 | 496.317 | 45.000 | 0 | target_reached | 14.636 |
| ukf_bias | case_C_frozen_identifier | clean | True | 90.360 | 2.190 | 0/73 | 0.954 | 6.382 | 0.068 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | target_reached | 32.723 |
| ukf_bias | case_C_frozen_identifier | noise | True | 90.850 | 2.290 | 0/77 | 0.772 | 6.394 | 0.113 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | target_reached | 34.066 |
| ukf_bias | case_C_frozen_identifier | noise_bias | True | 91.145 | 2.770 | 0/93 | 0.815 | 7.790 | 0.109 | 0 | 0.000 | 0.950 | 360.000 | 12.000 | 0 | target_reached | 40.971 |
| ukf_bias | case_D_frozen_estimator_model | clean | True | 91.164 | 0.900 | 0/30 | 1.757 | 7.452 | 0.035 | 9 | 58.776 | 1.073 | 400.181 | 11.755 | 0 | target_reached | 14.202 |
| ukf_bias | case_D_frozen_estimator_model | noise | True | 90.668 | 0.940 | 0/32 | 1.630 | 8.329 | 0.079 | 9 | 79.871 | 1.078 | 405.799 | 24.143 | 0 | target_reached | 15.002 |
| ukf_bias | case_D_frozen_estimator_model | noise_bias | True | 91.142 | 0.930 | 0/31 | 1.871 | 7.790 | 0.074 | 9 | 57.657 | 1.090 | 412.442 | 25.513 | 0 | target_reached | 14.511 |
| ukf_bias | case_E_oracle_identifier | clean | True | 90.034 | 1.970 | 0/66 | 0.431 | 7.993 | 0.008 | 19 | 44.734 | 1.200 | 450.080 | 17.369 | 0 | target_reached | 31.032 |
| ukf_bias | case_E_oracle_identifier | noise | True | 90.040 | 2.100 | 0/70 | 0.432 | 7.930 | 0.029 | 21 | 44.507 | 1.200 | 450.043 | 17.344 | 0 | target_reached | 32.862 |
| ukf_bias | case_E_oracle_identifier | noise_bias | True | 90.025 | 2.030 | 0/68 | 0.418 | 9.322 | 0.025 | 20 | 41.862 | 1.200 | 450.079 | 17.280 | 0 | target_reached | 31.816 |
| raw | ref_raw_adaptive | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.576 |
| raw | ref_raw_adaptive | noise | True | 91.402 | 1.350 | 0/45 | 2.670 | 58.736 | 0.036 | 13 | 41.030 | 1.207 | 423.196 | 45.000 | 0 | target_reached | 20.667 |
| raw | ref_raw_adaptive | noise_bias | True | 90.122 | 3.220 | 10/108 | 1.415 | 37.436 | 0.036 | 32 | 169.464 | 1.233 | 539.565 | 45.000 | 0 | target_reached | 49.765 |
| oracle | ref_oracle_state | clean | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.679 |
| oracle | ref_oracle_state | noise | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.704 |
| oracle | ref_oracle_state | noise_bias | True | 90.070 | 2.040 | 0/68 | 0.397 | 8.071 | 0.000 | 20 | 43.919 | 1.200 | 450.069 | 17.300 | 0 | target_reached | 31.695 |

## Short analysis
Does giving filtered UKF state to the identifier help or hurt compared with raw identifier input?
- ukf/noise: filtered-vs-raw identifier feasible ratio case_A_current_adaptive=0.472, case_B_mpc_only_raw_identifier=0.000.
- ukf/noise: adaptive-vs-frozen identifier max alpha severity case_A_current_adaptive=7.719, case_C_frozen_identifier=14.467.
- ukf/noise: adaptive-vs-frozen estimator covariance trace case_A_current_adaptive=0.071, case_D_frozen_estimator_model=0.071.
- ukf/noise: filtered-vs-oracle identifier prediction error case_A_current_adaptive=0.023, case_E_oracle_identifier=0.006.
- ukf/noise_bias: filtered-vs-raw identifier feasible ratio case_A_current_adaptive=0.375, case_B_mpc_only_raw_identifier=0.048.
- ukf/noise_bias: adaptive-vs-frozen identifier max alpha severity case_A_current_adaptive=7.481, case_C_frozen_identifier=15.116.
- ukf/noise_bias: adaptive-vs-frozen estimator covariance trace case_A_current_adaptive=0.071, case_D_frozen_estimator_model=0.071.
- ukf/noise_bias: filtered-vs-oracle identifier prediction error case_A_current_adaptive=0.021, case_E_oracle_identifier=0.001.
- ukf_bias/noise: filtered-vs-raw identifier feasible ratio case_A_current_adaptive=0.000, case_B_mpc_only_raw_identifier=0.000.
- ukf_bias/noise: adaptive-vs-frozen identifier max alpha severity case_A_current_adaptive=7.694, case_C_frozen_identifier=6.394.
- ukf_bias/noise: adaptive-vs-frozen estimator covariance trace case_A_current_adaptive=0.073, case_D_frozen_estimator_model=0.073.
- ukf_bias/noise: filtered-vs-oracle identifier prediction error case_A_current_adaptive=0.027, case_E_oracle_identifier=0.006.
- ukf_bias/noise_bias: filtered-vs-raw identifier feasible ratio case_A_current_adaptive=0.000, case_B_mpc_only_raw_identifier=0.000.
- ukf_bias/noise_bias: adaptive-vs-frozen identifier max alpha severity case_A_current_adaptive=7.790, case_C_frozen_identifier=7.790.
- ukf_bias/noise_bias: adaptive-vs-frozen estimator covariance trace case_A_current_adaptive=0.073, case_D_frozen_estimator_model=0.073.
- ukf_bias/noise_bias: filtered-vs-oracle identifier prediction error case_A_current_adaptive=0.024, case_E_oracle_identifier=0.006.

Does freezing the identifier improve stability or hurt adaptation?
- ukf/clean: frozen identifier target=False, feasible=0/267, done=max_time.
- ukf/noise: frozen identifier target=False, feasible=0/267, done=max_time.
- ukf/noise_bias: frozen identifier target=False, feasible=0/267, done=max_time.
- ukf_bias/clean: frozen identifier target=True, feasible=0/73, done=target_reached.
- ukf_bias/noise: frozen identifier target=True, feasible=0/77, done=target_reached.
- ukf_bias/noise_bias: frozen identifier target=True, feasible=0/93, done=target_reached.

Does oracle identifier input improve parameter estimates or closed-loop behavior?
- ukf/clean: oracle-identifier final theta=90.070, final params=(1.200, 450.069, 17.300), target=True.
- ukf/noise: oracle-identifier final theta=90.045, final params=(1.200, 450.063, 17.406), target=True.
- ukf/noise_bias: oracle-identifier final theta=86.929, final params=(1.200, 449.999, 17.398), target=False.
- ukf_bias/clean: oracle-identifier final theta=90.034, final params=(1.200, 450.080, 17.369), target=True.
- ukf_bias/noise: oracle-identifier final theta=90.040, final params=(1.200, 450.043, 17.344), target=True.
- ukf_bias/noise_bias: oracle-identifier final theta=90.025, final params=(1.200, 450.079, 17.280), target=True.

Are UKF-bias target gains coming from better bias estimation or different controller behavior?
- ukf_bias/case_A_current_adaptive/noise_bias: final bias=(0.012, -0.016, 0.006, 0.005), target=True, feasible ratio=0.000.
- ukf_bias/case_B_mpc_only_raw_identifier/noise_bias: final bias=(0.017, -0.015, -0.000, 0.010), target=True, feasible ratio=0.000.
- ukf_bias/case_C_frozen_identifier/noise_bias: final bias=(0.164, -0.086, 0.001, -0.003), target=True, feasible ratio=0.000.
- ukf_bias/case_D_frozen_estimator_model/noise_bias: final bias=(0.159, -0.046, 0.001, -0.011), target=True, feasible ratio=0.000.
- ukf_bias/case_E_oracle_identifier/noise_bias: final bias=(0.010, -0.016, 0.001, 0.002), target=True, feasible ratio=0.000.

Are parameter jumps correlated with innovation spikes, action jumps, or alpha violations?
- ukf/case_B_mpc_only_raw_identifier/noise_bias: max parameter step=154.585, mean innovation=0.036, max alpha severity=53.075.
- ukf_bias/case_A_current_adaptive/clean: max parameter step=58.776, mean innovation=0.007, max alpha severity=6.438.
- ukf_bias/case_A_current_adaptive/noise: max parameter step=79.871, mean innovation=0.043, max alpha severity=7.694.
- ukf_bias/case_A_current_adaptive/noise_bias: max parameter step=57.657, mean innovation=0.038, max alpha severity=7.790.
- ukf_bias/case_B_mpc_only_raw_identifier/noise_bias: max parameter step=160.811, mean innovation=0.042, max alpha severity=37.149.
- ukf_bias/case_D_frozen_estimator_model/clean: max parameter step=58.776, mean innovation=0.077, max alpha severity=7.452.
- ukf_bias/case_D_frozen_estimator_model/noise: max parameter step=79.871, mean innovation=0.126, max alpha severity=8.329.
- ukf_bias/case_D_frozen_estimator_model/noise_bias: max parameter step=57.657, mean innovation=0.131, max alpha severity=7.790.
- raw/ref_raw_adaptive/noise_bias: max parameter step=169.464, mean innovation=nan, max alpha severity=37.436.

Does estimator quality translate into lower alpha/omega violation, or are violations dominated by MPC constraints?
- ukf/case_A_current_adaptive/noise_bias: RMS omega reduction=0.010, omega severity=0.390, alpha severity=7.481.
- ukf/case_B_mpc_only_raw_identifier/noise_bias: RMS omega reduction=0.008, omega severity=0.556, alpha severity=53.075.
- ukf/case_C_frozen_identifier/noise_bias: RMS omega reduction=-0.016, omega severity=0.000, alpha severity=15.116.
- ukf/case_D_frozen_estimator_model/noise_bias: RMS omega reduction=0.007, omega severity=0.334, alpha severity=7.481.
- ukf/case_E_oracle_identifier/noise_bias: RMS omega reduction=0.010, omega severity=0.406, alpha severity=8.016.
- ukf_bias/case_A_current_adaptive/noise_bias: RMS omega reduction=0.011, omega severity=0.450, alpha severity=7.790.
- ukf_bias/case_B_mpc_only_raw_identifier/noise_bias: RMS omega reduction=0.004, omega severity=2.203, alpha severity=37.149.
- ukf_bias/case_C_frozen_identifier/noise_bias: RMS omega reduction=-0.072, omega severity=0.815, alpha severity=7.790.
- ukf_bias/case_D_frozen_estimator_model/noise_bias: RMS omega reduction=-0.041, omega severity=1.871, alpha severity=7.790.
- ukf_bias/case_E_oracle_identifier/noise_bias: RMS omega reduction=0.011, omega severity=0.418, alpha severity=9.322.
- raw/ref_raw_adaptive/noise_bias: RMS omega reduction=0.000, omega severity=1.415, alpha severity=37.436.
- oracle/ref_oracle_state/noise_bias: RMS omega reduction=0.036, omega severity=0.397, alpha severity=8.071.

Bad or mixed results were recorded as-is. No parameters were tuned after observing outputs.
