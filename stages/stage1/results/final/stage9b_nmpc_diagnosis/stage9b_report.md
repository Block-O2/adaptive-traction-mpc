# Stage 9B NMPC Diagnosis Report

## Scope
- Clean condition only.
- Diagnosis only: tested solver feasibility, initialization, horizon, alpha slack continuation, and variable scaling.
- No noise/noise_bias runs, no broad controller tuning, and no formal safety claims.
- Dynamics, UKF-bias, filtered Windowed NLS identifier, baseline CEM, Stage 7/8/9A results, and default configs were not intentionally changed.

## Commands Run
- `python scripts/run_spring2d_stage9b_nmpc_diagnosis.py`

## Summary
| variant | success/fail | status examples | N | alpha | scaled | warmstart | rho_L1 | solve mean/max | dyn residual max | constr viol max | slack mean/max/active | first action mean | target | alpha p95/p99/max |
|---|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 0/0 |  | 0 | False | False |  | nan | nan/nan | nan | nan | nan/nan/0 | nan,nan | True | 5.19/6.018/6.438 |
| nmpc_no_alpha_basic | 2/0 | Solve_Succeeded | 18 | False | False | shift | nan | 0.03498/0.04376 | 3.726e-07 | 0 | nan/nan/0 | 35,-0.001177 | False | 180.7/181.1/181.2 |
| nmpc_no_alpha_short_N5 | 2/0 | Solve_Succeeded | 5 | False | False | shift | nan | 0.02049/0.02127 | 2.104e-08 | 0 | nan/nan/0 | 35,-0.001085 | False | 180.7/181.1/181.2 |
| nmpc_no_alpha_short_N8 | 2/0 | Solve_Succeeded | 8 | False | False | shift | nan | 0.02144/0.02222 | 1.343e-08 | 0 | nan/nan/0 | 35,-0.001178 | False | 180.7/181.1/181.2 |
| nmpc_no_alpha_short_N10 | 2/0 | Solve_Succeeded | 10 | False | False | shift | nan | 0.02327/0.02542 | 4.015e-08 | 0 | nan/nan/0 | 35,-0.001177 | False | 180.7/181.1/181.2 |
| nmpc_cem_warmstart | 2/0 | Solve_Succeeded | 18 | False | False | cem | nan | 0.0248/0.02606 | 2.658e-08 | 0 | nan/nan/0 | 35,-0.001177 | False | 180.7/181.1/181.2 |
| nmpc_alpha_slack_rho1 | 13/0 | Solve_Succeeded | 18 | True | False | no_alpha | 1 | 0.04337/0.06184 | 4.449e-08 | 0 | 6.06/98.38/234 | 5.515,2.214e-05 | True | 67.65/69.51/70.1 |
| nmpc_alpha_slack_rho10 | 24/0 | Solve_Succeeded | 18 | True | False | no_alpha | 10 | 0.04699/0.06687 | 5.636e-08 | 0 | 0.3251/71.4/432 | 4.664,2.821e-05 | True | 11.8/47.65/48.51 |
| nmpc_alpha_slack_rho100 | 55/0 | Solve_Succeeded | 18 | True | False | no_alpha | 100 | 0.05476/0.1003 | 3.451e-07 | 0 | 9.543e-08/2.419e-07/990 | 5.315,1.092e-05 | True | 3.051/3.215/3.308 |
| nmpc_alpha_slack_rho1000 | 55/0 | Solve_Succeeded | 18 | True | False | no_alpha | 1000 | 0.05539/0.08601 | 4.498e-07 | 0 | 8.082e-09/9.779e-09/0 | 5.315,1.092e-05 | True | 3.051/3.215/3.308 |
| nmpc_scaled_variables | 55/0 | Solve_Succeeded | 18 | True | True | no_alpha | 100 | 0.0367/0.05676 | 9.783e-05 | 0 | 0.0001061/0.0002408/990 | 5.316,1.108e-05 | True | 3.051/3.215/3.308 |

## Required Answers
1. Can NMPC solve clean without alpha?
- Yes: no-alpha basic failure rate=0, statuses=Solve_Succeeded.

2. Does short horizon solve when full horizon fails?
- Not applicable: full-horizon no-alpha did not fail: full-horizon no-alpha failure rate=0; short-horizon failure rates N5/N8/N10 = 0/0/0.

3. Does CEM warm-start improve solver success?
- No success-rate improvement: CEM warm-start failure rate=0 vs no-alpha basic=0. It did reduce no-alpha mean solve time from 0.03498 s to 0.0248 s.

4. Does variable scaling improve solver success?
- No success-rate improvement: scaled failure rate=0; scales x=3.142,2,1,2, u=35,1, s=3. It did reduce rho100 mean solve time from 0.05476 s to 0.0367 s.

5. At what alpha penalty does slack formulation start failing?
- No alpha-continuation failure observed in tested rho_L1 values. Continuation failure rates rho 1/10/100/1000 = 0/0/0/0.

6. Is failure mainly due to formulation/scaling/initialization or task-alpha conflict?
- Current diagnosis points to Stage 9A formulation details rather than the basic dynamics equality or alpha slack concept: no-alpha, short horizon, CEM warm-start, alpha continuation, and scaled variables all solved on clean.

7. Should next step be proper scaled NMPC refinement, alpha/task redesign, or closing NMPC for now?
- Recommended next step: proper scaled NMPC refinement, specifically reconciling Stage 9A cost/penalty/scaling choices with the Stage 9B solvable formulation.
