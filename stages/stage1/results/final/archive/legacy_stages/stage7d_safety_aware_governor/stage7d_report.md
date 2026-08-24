# Stage 7D Safety-Aware Command Governor Report

## Scope
- Added `progress_governor_mode=safety_aware`.
- The governor maintains `theta_cmd` and chooses among command rates `[0, 10, 20, 30, 45]` deg/s.
- Safety-aware scoring uses a 3-step surrogate rollout and a fixed threshold; no retreat/backtracking, action projection, or extra rate tuning was added.
- MPC tracks `theta_cmd` when the governor is enabled.
- Dynamics, estimator/identifier flow, baseline CEM, runtime filter, alpha-soft CEM, and gatekeeper code were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `conda run -n mpc_learn python -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7d_safety_aware_governor.py`

## Aggregate Metrics
| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | hold rate avg | T_reach avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 3/3 | 1.008 | 4.766 | 7.307 | 0.228 | 0.4398 | 0 | 2.017 |
| alpha100_omega0 | 3/3 | 0.9997 | 5.289 | 8.338 | 0.3284 | 0.4672 | 0 | 1.933 |
| alpha200_omega0 | 3/3 | 0.9282 | 5.242 | 7.675 | 0.2417 | 0.4667 | 0 | 2.333 |
| fixed_rate_30 | 2/3 | 1.17 | 5.167 | 28.47 | 0.2337 | 1.012 | 0 | 6.31 |
| gatekeeper_H3 | 3/3 | 1.223 | 5.132 | 9.427 | 0.009379 | 0.07423 | 0 | 2.983 |
| safety_aware_governor | 0/3 | 1.668 | 8.584 | 31.43 | 0.4045 | 1.588 | 0.8477 | nan |

## Required Answers
1. Does safety-aware governor preserve target reaching?
- No/mixed: safety-aware governor target=0/3.

2. Does it reduce alpha p95/max vs baseline, alpha-soft, fixed-rate, and gatekeeper?
- No/mixed: safety-aware alpha p95/max avg=8.584/31.43; baseline=4.766/7.307; alpha-soft best=5.242/7.675; fixed_rate_30=5.167/28.47; gatekeeper_H3=5.132/9.427.

3. Does it avoid worsening omega tail risk?
- No/mixed: safety-aware omega p95/max avg=0.4045/1.588; baseline=0.228/0.4398.

4. How often does it hold progress?
- Average hold rate=0.8477.

5. Is it better than fixed-rate governor?
- No/mixed by target success plus alpha p95/max vs `fixed_rate_30`.

6. Should this continue to stress validation or be closed out?
- Close out or revise before stress validation based on this minimal Stage 7D evidence.

## Outputs
- `stage7d_summary.csv` contains per-method/per-condition metrics.
- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.
- Plots are under `figs/`.
