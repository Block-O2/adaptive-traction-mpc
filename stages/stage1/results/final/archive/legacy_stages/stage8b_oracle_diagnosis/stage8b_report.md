# Stage 8B Single-Link Oracle Diagnosis Report

## Scope
- Diagnosis only: checked whether low-alpha target-reaching trajectories exist in the current Spring2D single-link task.
- Compared baseline mainline, oracle CEM, high-budget CEM, and a single smooth-action CEM diagnostic.
- Conditions: clean, noise, noise_bias. Optional model_mismatch_light was not run to keep this diagnostic minimal.
- Dynamics, estimator implementation, identifier implementation, existing baseline behavior, and Stage 7 methods were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage8b_oracle_diagnosis.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage8b_oracle_diagnosis`

## Diagnostic Overrides
- `oracle_cem`: true state for MPC state input; true physical parameters used as MPC prediction parameters; identifier frozen; default CEM budget.
- `high_budget_cem`: samples=256, elites=32, iterations=5, horizon=24.
- `smooth_action_cem_diagnostic`: default budget with action-rate cost weights `w_F_tan_rate=0.05`, `w_F_rad_rate=1.0`; all default/off methods keep action-rate weights at 0.

## Aggregate Metrics
| method | target successes | alpha mean | alpha p95 | alpha p99 | alpha max | omega p95 | omega max | action smoothness | T_reach avg | runtime avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_mainline | 3/3 | 1.008 | 4.766 | 6.798 | 7.307 | 0.228 | 0.4398 | 0.2057 | 2.017 | 34.36 |
| oracle_cem | 0/3 | 0.2891 | 2.16 | 6.32 | 8.382 | 0 | 0.4044 | 0.05817 | nan | 133.5 |
| high_budget_cem | 1/3 | 0.8404 | 4.244 | 7.978 | 11.32 | 0.03341 | 0.3257 | 0.1999 | 7.46 | 538.7 |
| smooth_action_cem_diagnostic | 3/3 | 1.008 | 4.766 | 6.798 | 7.307 | 0.228 | 0.4398 | 0.2057 | 2.017 | 34.59 |

## Delta vs Baseline
| method | delta alpha p95 | delta alpha max | delta omega p95 | delta action smoothness |
|---|---:|---:|---:|---:|
| baseline_mainline | 0 | 0 | 0 | 0 |
| oracle_cem | -2.606 | 1.074 | -0.228 | -0.1475 |
| high_budget_cem | -0.5222 | 4.017 | -0.1946 | -0.005858 |
| smooth_action_cem_diagnostic | 0 | 0 | 0 | 0 |

## Required Answers
1. Does oracle CEM reduce alpha tail vs mainline baseline?
- No/mixed: oracle delta alpha p95/max = -2.606/1.074.

2. Does high-budget CEM reduce alpha tail?
- No/mixed: high-budget delta alpha p95/max = -0.5222/4.017.

3. Does smooth-action CEM reduce alpha tail?
- No/mixed: smooth-action delta alpha p95/max = 0/0.

4. Does any diagnostic method preserve target reaching while reducing alpha p95/max?
- No method satisfied both full target reaching and lower alpha p95/max than baseline across the three conditions.

5. Is alpha tail mainly due to estimator/identifier error, CEM search budget, action-sequence roughness, or task/constraint conflict?
- the evidence points more toward task/constraint conflict or the current action-generation formulation than estimator error alone.

6. Should next step be smooth/acceleration-aware CEM, robust identifier, or task/constraint revision?
- Recommended next step from this diagnostic: task/constraint revision or a different action-generation formulation.

7. Is it safe to move to linked rods now?
- Not yet with confidence; this diagnosis is simulation evidence, not a formal safety guarantee. Best aggregate method was `baseline_mainline`.

## Notes
- Bad or mixed results are retained in the summary CSV and are not manually tuned after the run.
