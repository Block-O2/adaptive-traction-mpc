# Stage 7C Alpha-Tail-Aware Gatekeeper Report

## Scope
- Revised gatekeeper-lite scoring only.
- `gatekeeper_mode=candidate_select`, `H=3`, `K=20`; selection remains among top-K CEM candidate sequences.
- No action clipping, scaling, or projection was added.
- Alpha-tail methods used `alpha_max_weight` in `[10, 50, 100]` with fixed alpha/omega/delta_r/force weights.
- Baseline CEM, runtime filter, alpha-soft CEM, progress governor, estimator/identifier flow, and Spring2D dynamics were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `conda run -n mpc_learn python -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7c_alpha_tail_gatekeeper.py`

## Aggregate Metrics
| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | intervention avg | selected rank avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 3/3 | 1.008 | 4.766 | 7.307 | 0.228 | 0.4398 | 0 | 0 |
| alpha100_omega0 | 3/3 | 0.9997 | 5.289 | 8.338 | 0.3284 | 0.4672 | 0 | 0 |
| alpha200_omega0 | 3/3 | 0.9282 | 5.242 | 7.675 | 0.2417 | 0.4667 | 0 | 0 |
| gatekeeper_H3 | 3/3 | 1.223 | 5.132 | 9.427 | 0.009379 | 0.07423 | 0.5687 | 4.878 |
| alpha_tail_gatekeeper_w10 | 3/3 | 1.223 | 5.132 | 9.427 | 0.009379 | 0.07423 | 0.5687 | 4.878 |
| alpha_tail_gatekeeper_w50 | 3/3 | 1.47 | 6.554 | 10.77 | 0.05891 | 0.1248 | 0.5758 | 4.699 |
| alpha_tail_gatekeeper_w100 | 3/3 | 1.652 | 6.543 | 9.938 | 0.09355 | 0.2131 | 0.6504 | 5.649 |

## Required Answers
1. Does alpha-tail-aware scoring reduce alpha p95/max vs old gatekeeper_H3?
- No/mixed: best alpha-tail `alpha_tail_gatekeeper_w10` alpha p95/max avg=5.132/9.427; old H3=5.132/9.427.

2. Does it improve alpha p95/max vs baseline and alpha-soft CEM?
- Vs baseline: No/mixed; baseline alpha p95/max avg=4.766/7.307.
- Vs alpha-soft: No/mixed; best alpha-soft p95/max avg=5.242/7.675.

3. Does it preserve target reaching?
- Yes: alpha-tail methods target success counts are alpha_tail_gatekeeper_w10=3/3, alpha_tail_gatekeeper_w50=3/3, alpha_tail_gatekeeper_w100=3/3.

4. Does it still avoid omega tail risk?
- Yes for best alpha-tail vs baseline using omega p95 and max: best=0.009379/0.07423, baseline=0.228/0.4398.

5. Which alpha_max_weight is best?
- `alpha_tail_gatekeeper_w10` is best by target success first, then alpha p95, alpha max, omega p95, and intervention rate.

6. Should gatekeeper continue to stress validation, or be closed out?
- Close out or revise before stress validation based on this focused revision. Do not infer formal safety guarantees from this result.

## Outputs
- `stage7c_alpha_tail_summary.csv` contains per-method/per-condition metrics.
- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.
- Plots are under `figs/`.
