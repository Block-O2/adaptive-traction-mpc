# Stage 6 Runtime One-Step Safety Filter Report

## Files changed
- Added `src/traction_mpc/mpc/safety_filter.py`.
- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` to log MPC action, safe action, and safety-filter diagnostics.
- Added `configs/spring2d_runtime_safety_filter.yaml`.
- Added `scripts/run_spring2d_safety_filter_comparison.py`.

## Unchanged setup confirmation
- Spring2D dynamics: unchanged.
- MPC cost definition: unchanged.
- Base MPC constraints: unchanged and reused by the runtime filter.
- CEM solver algorithm: unchanged.
- UKF / UKF-bias algorithm: unchanged.
- Windowed NLS identifier algorithm: unchanged.
- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.
- No robust identifier, DREM, EKF, explicit gravity compensation, or post-result tuning was added.

## One-step filter
- The MPC proposes `u_mpc = [F_tan_mpc, F_rad_mpc]`; the environment executes `u_safe` when the filter is enabled.
- The implemented selection approximates `argmin_u ||u - u_mpc||^2` over derivative-free candidates.
- Candidate actions include `u_mpc`, clipped `u_mpc`, configured scaled actions, and a configured local grid around `u_mpc`; all candidates are clipped to input bounds.
- Each candidate is rolled out one step with `x_next = Phi_dt(x_hat_t, u; theta_hat)`, `delta_r_next = r_next - L0`, and `alpha = (omega_next - omega_t) / control_dt`.
- If a feasible candidate exists, the filter selects the feasible candidate with minimum action distance. Otherwise it selects the least-violating candidate by `(violation_score, action distance)` and logs `safety_filter_failed=True`.
- This is an approximate execution-time one-step filter, not a formal invariant-set safety proof.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_safety_filter_comparison.py`

Config used: `configs/spring2d_runtime_safety_filter.yaml`.

## Safety filter config
- `enabled`: compared as `false` and `true`.
- `type`: `one_step_projection`.
- `scales`: `[1.0, 0.8, 0.6, 0.4, 0.2, 0.0]`.
- `F_tan_offsets`: `[-2.0, -1.0, 0.0, 1.0, 2.0]`.
- `F_rad_offsets`: `[-0.2, -0.1, 0.0, 0.1, 0.2]`.
- `violation_weights`: all one.

## Summary table
| estimator | safety | condition | target | final theta deg | T_reach | feasible MPC | omega viol | alpha viol | max omega sev | max alpha sev | filter active | feasible cand | filter failed | mean action delta | max action delta | done | runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| ukf_bias | safety_off | clean | True | 90.146 | 2.060 | 0/69 | 17 | 84 | 0.427 | 6.438 | 0 | 0 | 0 | 0.000 | 0.000 | target_reached | 31.585 |
| ukf_bias | safety_off | noise | True | 90.217 | 1.800 | 0/60 | 16 | 66 | 0.443 | 7.694 | 0 | 0 | 0 | 0.000 | 0.000 | target_reached | 27.673 |
| ukf_bias | safety_off | noise_bias | True | 90.014 | 2.190 | 0/73 | 22 | 90 | 0.450 | 7.790 | 0 | 0 | 0 | 0.000 | 0.000 | target_reached | 33.515 |
| ukf_bias | safety_on | clean | False | 40.833 | nan | 0/267 | 0 | 34 | 0.000 | 6.791 | 801 | 774 | 27 | 1.091 | 3.929 | max_time | 124.641 |
| ukf_bias | safety_on | noise | False | 1.407 | nan | 0/267 | 205 | 163 | 2.098 | 39.963 | 801 | 550 | 251 | 3.006 | 18.026 | max_time | 113.578 |
| ukf_bias | safety_on | noise_bias | False | 46.867 | nan | 0/267 | 0 | 124 | 0.000 | 9.875 | 801 | 683 | 118 | 1.933 | 7.855 | max_time | 129.849 |
| ukf | safety_off | clean | True | 90.070 | 2.040 | 0/68 | 16 | 76 | 0.397 | 8.071 | 0 | 0 | 0 | 0.000 | 0.000 | target_reached | 31.599 |
| ukf | safety_off | noise | True | 90.081 | 4.810 | 76/161 | 19 | 94 | 0.406 | 7.719 | 0 | 0 | 0 | 0.000 | 0.000 | target_reached | 75.599 |
| ukf | safety_off | noise_bias | False | 87.199 | nan | 100/267 | 19 | 96 | 0.390 | 7.481 | 0 | 0 | 0 | 0.000 | 0.000 | max_time | 125.476 |
| ukf | safety_on | clean | False | 43.099 | nan | 0/267 | 0 | 130 | 0.000 | 6.801 | 801 | 681 | 120 | 2.211 | 8.462 | max_time | 117.806 |
| ukf | safety_on | noise | False | 58.425 | nan | 0/267 | 0 | 159 | 0.000 | 7.072 | 801 | 651 | 150 | 2.037 | 7.387 | max_time | 122.441 |
| ukf | safety_on | noise_bias | False | 42.196 | nan | 0/267 | 6 | 136 | 0.044 | 6.566 | 801 | 666 | 135 | 2.271 | 13.735 | max_time | 118.830 |

## Analysis
Did the filter reduce omega/alpha violation count?
- ukf_bias/clean: omega count 17.000 -> 0.000, alpha count 84.000 -> 34.000.
- ukf_bias/noise: omega count 16.000 -> 205.000, alpha count 66.000 -> 163.000.
- ukf_bias/noise_bias: omega count 22.000 -> 0.000, alpha count 90.000 -> 124.000.
- ukf/clean: omega count 16.000 -> 0.000, alpha count 76.000 -> 130.000.
- ukf/noise: omega count 19.000 -> 0.000, alpha count 94.000 -> 159.000.
- ukf/noise_bias: omega count 19.000 -> 6.000, alpha count 96.000 -> 136.000.

Did it reduce max omega/alpha violation severity?
- ukf_bias/clean: omega severity 0.427 -> 0.000, alpha severity 6.438 -> 6.791.
- ukf_bias/noise: omega severity 0.443 -> 2.098, alpha severity 7.694 -> 39.963.
- ukf_bias/noise_bias: omega severity 0.450 -> 0.000, alpha severity 7.790 -> 9.875.
- ukf/clean: omega severity 0.397 -> 0.000, alpha severity 8.071 -> 6.801.
- ukf/noise: omega severity 0.406 -> 0.000, alpha severity 7.719 -> 7.072.
- ukf/noise_bias: omega severity 0.390 -> 0.044, alpha severity 7.481 -> 6.566.

Did it hurt target reaching or increase T_reach?
- ukf_bias/safety_off/clean: target=True, T_reach=2.060, done=target_reached.
- ukf_bias/safety_off/noise: target=True, T_reach=1.800, done=target_reached.
- ukf_bias/safety_off/noise_bias: target=True, T_reach=2.190, done=target_reached.
- ukf_bias/safety_on/clean: target=False, T_reach=nan, done=max_time.
- ukf_bias/safety_on/noise: target=False, T_reach=nan, done=max_time.
- ukf_bias/safety_on/noise_bias: target=False, T_reach=nan, done=max_time.
- ukf/safety_off/clean: target=True, T_reach=2.040, done=target_reached.
- ukf/safety_off/noise: target=True, T_reach=4.810, done=target_reached.
- ukf/safety_off/noise_bias: target=False, T_reach=nan, done=max_time.
- ukf/safety_on/clean: target=False, T_reach=nan, done=max_time.
- ukf/safety_on/noise: target=False, T_reach=nan, done=max_time.
- ukf/safety_on/noise_bias: target=False, T_reach=nan, done=max_time.

How often did it modify the action and how large were the modifications?
- ukf_bias/clean safety_on: active=801, mean_delta=1.091, max_delta=3.929.
- ukf_bias/noise safety_on: active=801, mean_delta=3.006, max_delta=18.026.
- ukf_bias/noise_bias safety_on: active=801, mean_delta=1.933, max_delta=7.855.
- ukf/clean safety_on: active=801, mean_delta=2.211, max_delta=8.462.
- ukf/noise safety_on: active=801, mean_delta=2.037, max_delta=7.387.
- ukf/noise_bias safety_on: active=801, mean_delta=2.271, max_delta=13.735.

How often did it fail to find a one-step feasible candidate?
- ukf_bias/clean safety_on: failed=27, feasible_candidate_found=774.
- ukf_bias/noise safety_on: failed=251, feasible_candidate_found=550.
- ukf_bias/noise_bias safety_on: failed=118, feasible_candidate_found=683.
- ukf/clean safety_on: failed=120, feasible_candidate_found=681.
- ukf/noise safety_on: failed=150, feasible_candidate_found=651.
- ukf/noise_bias safety_on: failed=135, feasible_candidate_found=666.

Was UKF or UKF-bias better with the safety filter enabled?
- clean: UKF-bias target=False, UKF target=False; UKF-bias alpha violations=34, UKF alpha violations=130.
- noise: UKF-bias target=False, UKF target=False; UKF-bias alpha violations=163, UKF alpha violations=159.
- noise_bias: UKF-bias target=False, UKF target=False; UKF-bias alpha violations=124, UKF alpha violations=136.

Bad or mixed results are reported as-is. No parameters were tuned after observing outputs.
