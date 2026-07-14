# Stage 7C Gatekeeper-Lite Report

## Scope
- Added `gatekeeper_mode`: `off` and `candidate_select`.
- Gatekeeper-lite runs after CEM planning and before executing the first action.
- It selects among top-K CEM candidate action sequences; it does not clip, scale, or project the final action.
- Tested `gatekeeper_horizon` values `[3, 5]` with `K=20` only.
- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, baseline CEM with gatekeeper off, old runtime filter, Stage 7A alpha-soft, and Stage 7B governor code were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `conda run -n mpc_learn python -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7c_gatekeeper_lite.py`

## Aggregate Metrics
| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | intervention avg | T_reach avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 3/3 | 1.008 | 4.766 | 7.307 | 0.228 | 0.4398 | 0 | 2.017 |
| runtime_filter_old | 0/3 | 0.5659 | 3.259 | 18.88 | 0.5961 | 0.6993 | 0 | nan |
| alpha100_omega0 | 3/3 | 0.9997 | 5.289 | 8.338 | 0.3284 | 0.4672 | 0 | 1.933 |
| alpha200_omega0 | 3/3 | 0.9282 | 5.242 | 7.675 | 0.2417 | 0.4667 | 0 | 2.333 |
| gatekeeper_H3 | 3/3 | 1.223 | 5.132 | 9.427 | 0.009379 | 0.07423 | 0.5687 | 2.983 |
| gatekeeper_H5 | 3/3 | 1.31 | 5.513 | 11.74 | 0 | 0 | 0.1717 | 4.367 |

## Required Answers
1. Does gatekeeper-lite preserve target reaching?
- Yes: H3 target=3/3, H5 target=3/3.

2. Does it reduce alpha p95/max compared with baseline and alpha-soft CEM?
- Best gatekeeper is `gatekeeper_H3` with alpha p95 avg=5.132, alpha max avg=9.427.
- Compared with baseline: did not improve both p95 and max.
- Compared with alpha-soft candidates: did not improve both p95 and max.

3. Does it avoid worsening omega tail risk?
- Yes for best gatekeeper using omega p95 avg vs baseline: best=0.009379, baseline=0.228.

4. How often does it intervene?
- H3 average intervention rate=0.5687; H5 average intervention rate=0.1717.

5. Is H=3 or H=5 better?
- `gatekeeper_H3` is better by target success first, then alpha p95, alpha max, omega p95, and intervention rate.

6. Is it better than old one-step runtime filter?
- Yes: runtime filter target=0/3, alpha p95 avg=3.259; best gatekeeper target=3/3, alpha p95 avg=5.132.

7. Should this continue to stress validation, or be closed out?
- Close out or revise before stress validation based on this minimal evidence. Continue only if target reaching is preserved and alpha tail improves without omega tail degradation.

## Outputs
- `stage7c_summary.csv` contains per-method/per-condition metrics.
- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.
- Plots are under `figs/`.
