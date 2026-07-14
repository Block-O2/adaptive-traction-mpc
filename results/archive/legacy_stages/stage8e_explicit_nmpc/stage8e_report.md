# Stage 8E Explicit Constrained NMPC Report

## Scope
- Diagnosis only: tested a minimal explicit direct-shooting NMPC baseline with alpha slack.
- Baseline CEM and alpha200 reference use existing CEM code.
- NMPC freezes current estimated [m, k, b_r] over each horizon and updates between MPC solves via the existing filtered Windowed NLS flow.
- Force bounds are hard via optimizer bounds; delta_r and omega are hard-ish quadratic penalties; alpha uses implicit L1+L2 slack penalty.
- Dynamics, estimator/identifier implementations, baseline CEM, Stage 7/8 methods, and default configs were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `python scripts/run_spring2d_stage8e_explicit_nmpc.py`

## Aggregate Metrics
| method | target | T_reach | fail rate | solve time | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack active | omega p95 | omega max | delta_r count | force count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 3/3 | 2.017 | nan | nan | 4.766 | 6.798 | 7.307 | 0.8 | 2.044 | nan | nan | 0 | 0.228 | 0.4398 | 0 | 0 |
| alpha200_omega0 | 3/3 | 2.333 | nan | nan | 5.242 | 7.305 | 7.675 | 0.7133 | 2.059 | nan | nan | 0 | 0.2417 | 0.4667 | 0 | 0 |
| nmpc_alpha_slack | 0/3 | nan | 1 | 0.2328 | 0.05969 | 7.843 | 31.31 | 0.41 | 2.39 | 1.14 | 28.98 | 6796 | 0.5716 | 1.026 | 0 | 0 |

## Required Answers
1. Does explicit NMPC preserve target reaching?
- No: NMPC target=0/3.

2. Does alpha slack NMPC reduce alpha p95/p99/max vs baseline CEM?
- No/mixed: NMPC alpha p95/p99/max=0.05969/7.843/31.31; baseline=4.766/6.798/7.307; alpha200=5.242/7.305/7.675.

3. Does it avoid worsening omega/delta_r/force violations?
- No/mixed: NMPC omega p95/max=0.5716/1.026, delta_r count=0, force count=0.

4. How often is alpha slack active?
- Active slack count across NMPC decision horizons: 6796; mean/max slack=1.14/28.98.

5. Is solve time acceptable for this small system?
- No/marginal: mean NMPC solve time=0.2328 s, failure rate=1.

6. Is NMPC worth developing further, or does this indicate task/constraint conflict?
- This still indicates task/constraint conflict or insufficient minimal NMPC formulation.

7. Should next step be NMPC refinement, task/constraint revision, or linked rods?
- Recommended next step: task/constraint revision before linked rods; NMPC alone did not resolve the conflict.

## Notes
- Failures and mixed results are retained directly. No post-result tuning was applied.
