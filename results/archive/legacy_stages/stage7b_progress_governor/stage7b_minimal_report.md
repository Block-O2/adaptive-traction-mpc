# Stage 7B-minimal Fixed-Rate Progress Governor Report

## Scope
- Added optional `progress_governor_mode`: `off` and `fixed_rate`.
- Fixed-rate governor updates `theta_cmd` toward the final target and MPC tracks `theta_cmd` when enabled.
- Tested fixed rates 15, 30, and 45 deg/s only. No extra tuning was performed.
- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier flow, baseline CEM with governor off, old runtime filter, and Stage 7A alpha-soft implementation were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `conda run -n mpc_learn python -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7b_progress_governor.py`

## Aggregate Metrics
| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | T_reach avg | action smooth avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 3/3 | 1.008 | 4.766 | 7.307 | 0.228 | 0.4398 | 2.017 | 0.2057 |
| alpha100_omega0 | 3/3 | 0.9997 | 5.289 | 8.338 | 0.3284 | 0.4672 | 1.933 | 0.2088 |
| alpha200_omega0 | 3/3 | 0.9282 | 5.242 | 7.675 | 0.2417 | 0.4667 | 2.333 | 0.1787 |
| fixed_rate_15 | 2/3 | 1.32 | 5.764 | 26.46 | 0.3113 | 1.291 | 6.61 | 0.2111 |
| fixed_rate_30 | 2/3 | 1.17 | 5.167 | 28.47 | 0.2337 | 1.012 | 6.31 | 0.1595 |
| fixed_rate_45 | 2/3 | 1.291 | 6.092 | 33.93 | 0.2952 | 1.068 | 4.57 | 0.1503 |

## Required Answers
1. Does fixed-rate progress governor preserve target reaching?
- No/mixed: fixed-rate target successes are fixed_rate_15=2/3, fixed_rate_30=2/3, fixed_rate_45=2/3.

2. Does it reduce alpha p95/max compared with baseline and alpha-soft CEM?
- Best fixed-rate method is `fixed_rate_30` with alpha p95 avg=5.167 and alpha max avg=28.47.
- Compared with baseline: did not improve both p95 and max.
- Compared with alpha-soft candidates: did not improve both p95 and max.

3. Does it avoid worsening omega tail risk?
- No/mixed for the best fixed-rate method using omega p95 avg vs baseline: best=0.2337, baseline=0.228.

4. Which rate is best?
- `fixed_rate_30` by target success first, then alpha p95, alpha max, omega p95, and T_reach.

5. Should we continue to safety-aware governor next?
- Not yet / only with caution: the minimal fixed-rate governor evidence should be judged before adding safety-aware gating. If target reaching is preserved and alpha improves without omega degradation, continue to a safety-aware governor or PSF/gatekeeper-lite; otherwise report the mixed result without tuning more rates.

## Outputs
- `stage7b_minimal_summary.csv` contains per-method/per-condition metrics.
- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.
- Plots are under `figs/`.
