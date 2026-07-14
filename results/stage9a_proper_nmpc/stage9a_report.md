# Stage 9A Proper Multiple-Shooting NMPC Report

## Scope
- Diagnosis only: tested CasADi multiple-shooting NMPC with explicit state variables and explicit alpha slack variables.
- Solver availability: CasADi 3.7.2 available; acados_template unavailable in this environment.
- Alpha is a high-priority soft path constraint through nonnegative slack; force bounds are hard optimizer bounds.
- Delta_r and omega are hard-ish through strong path penalties.
- Dynamics, UKF-bias, filtered Windowed NLS identifier, baseline CEM, Stage 7/8 methods, and default configs were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `python scripts/run_spring2d_stage9a_proper_nmpc.py`

## Aggregate Metrics
| method | target | T_reach | fail rate | fallback rate | solve time | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack active | omega p95 | omega max | delta_r count | force count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 1/1 | 2.06 | nan | nan | nan | 5.19 | 6.018 | 6.438 | 0.84 | 2.01 | nan | nan | 0 | 0.2096 | 0.4265 | 0 | 0 |
| alpha200_omega0 | 1/1 | 3.14 | nan | nan | nan | 4.173 | 7.432 | 7.897 | 0.73 | 2.035 | nan | nan | 0 | 0.2022 | 0.4801 | 0 | 0 |
| nmpc_alpha_slack | 1/1 | 2.22 | 1 | 1 | 0.5183 | 104.9 | 136.3 | 151 | 1.19 | 32.53 | 5.482 | 693.6 | 1332 | 2.436 | 3.894 | 0 | 0 |
| nmpc_alpha_slack_with_cem_fallback | 1/1 | 2.06 | 1 | 1 | 0.4668 | 5.19 | 6.018 | 6.438 | 0.84 | 2.01 | 10.24 | 693.6 | 1242 | 0.2096 | 0.4265 | 0 | 0 |

## Stop Condition
- Stress conditions were skipped: clean fallback NMPC solver failure rate was 1

## Required Answers
1. Does proper multiple-shooting NMPC solve reliably on clean?
- No: clean fallback NMPC failure rate=1.

2. Does fallback prevent catastrophic closed-loop failure?
- Yes/mixed: CEM fallback kept the executed trajectory at baseline-like risk when IPOPT failed. Fallback alpha/omega max=6.438/0.4265 vs non-fallback failed-candidate execution=151/3.894. This does not mean NMPC solved successfully.

3. Does NMPC preserve target reaching?
- Yes with fallback, not as a reliable NMPC solve: fallback NMPC target=1/1, but solver success count on clean was 0.

4. Does explicit alpha slack reduce alpha p95/p99/max vs baseline CEM?
- No/mixed: fallback NMPC alpha p95/p99/max=5.19/6.018/6.438; baseline=5.19/6.018/6.438.

5. Does it avoid worsening omega/delta_r/force violations?
- Yes: fallback NMPC omega p95/max=0.2096/0.4265, delta_r count=0, force count=0.

6. How often and how strongly is alpha slack used?
- Slack active total=1242; mean/max slack=10.24/693.6.

7. Is solve time acceptable for this small system?
- No/marginal: mean solve time=0.4668 s, failure rate=1.

8. Is NMPC worth developing further, or should we revise task/alpha definition?
- Recommended next step: revise task/alpha definition or NMPC formulation before linked rods.

## Notes
- Failures and mixed results are retained directly. No post-result tuning was applied.
