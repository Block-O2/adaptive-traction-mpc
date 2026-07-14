# Stage 8A UKF-Bias Covariance Sensitivity Report

## Scope
- Sanity check for UKF-bias covariance sensitivity only.
- Mainline remains CEM + UKF-bias + filtered Windowed NLS identifier.
- Swept one factor at a time: process noise Q, measurement noise R, bias process noise, and initial covariance P0.
- No full Cartesian product was run.
- Dynamics, CEM controller, identifier structure, cost, constraints, Stage 7 methods, and baseline behavior were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `conda run -n mpc_learn python -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage8a_ukf_sensitivity.py`

## Aggregate Metrics
| setting | factor | scale | target successes | RMSE theta | RMSE omega | alpha p95 | alpha max | omega p95 | omega max | T_reach avg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| default | default | 1 | 3/3 | 0.01154 | 0.02209 | 4.766 | 7.307 | 0.228 | 0.4398 | 2.017 |
| Q_0.3 | Q | 0.3 | 3/3 | 0.02502 | 0.03486 | 5.12 | 8.185 | 0.2906 | 0.4351 | 1.89 |
| Q_3 | Q | 3 | 3/3 | 0.004746 | 0.02079 | 8.154 | 37.33 | 0.1707 | 0.6239 | 2.867 |
| R_0.3 | R | 0.3 | 3/3 | 0.01121 | 0.02223 | 5.114 | 10.99 | 0.1942 | 0.4497 | 2.39 |
| R_3 | R | 3 | 3/3 | 0.01088 | 0.02565 | 5.145 | 7.178 | 0.2392 | 0.4474 | 2.09 |
| biasQ_0.1 | bias_process_noise | 0.1 | 3/3 | 0.01085 | 0.02234 | 4.43 | 24.33 | 0.1451 | 0.4412 | 2.537 |
| biasQ_10 | bias_process_noise | 10 | 2/3 | 0.007802 | 0.0199 | 3.684 | 10.54 | 0.08815 | 0.4361 | 2.48 |
| P0_0.3 | P0 | 0.3 | 2/3 | 0.003315 | 0.01901 | 3.83 | 19.1 | 0.08936 | 0.4163 | 2.8 |
| P0_3 | P0 | 3 | 3/3 | 0.02285 | 0.02579 | 5.591 | 7.61 | 0.3023 | 0.5315 | 2.36 |

## Sensitivity Ranges
| factor | alpha p95 range | omega p95 range | omega RMSE range |
|---|---:|---:|---:|
| Q | 3.034 | 0.1199 | 0.01407 |
| R | 0.03076 | 0.04494 | 0.003425 |
| bias_process_noise | 0.746 | 0.05693 | 0.002442 |
| P0 | 1.761 | 0.2129 | 0.00678 |

## Required Answers
1. Are current UKF-bias covariance settings reasonably robust?
- No/mixed based on this one-factor sweep. Default target=3/3, alpha p95 avg=4.766, omega p95 avg=0.228.

2. Which parameter matters most: Q, R, bias noise, or P0?
- `Q` showed the largest combined spread across alpha p95, omega p95, and omega RMSE in this sweep.

3. Does tuning UKF-bias reduce alpha/omega tail risk?
- No/mixed: best setting `biasQ_0.1` alpha p95/max=4.43/24.33, omega p95/max=0.1451/0.4412; default=4.766/7.307, omega=0.228/0.4398.

4. Does any setting hurt target reaching?
- biasQ_10 target=2/3, P0_0.3 target=2/3

5. Should we keep default UKF-bias settings or change them?
- Keep default based on this sanity check; do not treat a small covariance improvement as a controller fix.

6. Is estimator tuning likely the main cause of alpha tail risk?
- Unlikely from this sweep. Alpha tail risk remains primarily a controller/action-generation issue unless a covariance setting consistently reduces alpha p95/max without hurting target reaching or omega risk.

## Outputs
- `stage8a_ukf_sensitivity_summary.csv` contains per-setting/per-condition metrics.
- Per-run timeseries logs are under `logs/{setting}/{condition}/timeseries.csv`.
- Plots are under `figs/`.
