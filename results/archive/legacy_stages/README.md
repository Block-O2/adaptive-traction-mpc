# Legacy Stage 1–8 Results

These directories contain the curated historical evidence retained by Stage 10-0. Raw trajectories, repeated videos, caches, and redundant plots were removed because the scripts and configs remain available. Conclusions below are copied or condensed from the retained reports; archiving does not change them.

| Stage | Purpose | Final conclusion | Retained artifacts | Why archived |
|---|---|---|---|---|
| `stage1_spring2d` | Establish Spring2D and initial fixed/adaptive comparisons | Adaptive control improved progress over the mismatched fixed baseline, but strict crossing and noise/bias robustness were unresolved | README, two summary CSVs, one figure | Superseded baseline |
| `stage2_cem` | Compare CEM with random shooting | CEM improved target reaching but did not solve feasibility | Report, summary, one figure | Solver-selection evidence is complete |
| `stage2_cem_feasfirst` | Test feasibility-first CEM ranking | Feasibility improved in some cases but target reaching and violations remained mixed | Report, summary, one figure | Diagnostic branch closed |
| `stage3_filtering` | Compare raw, low-pass, alpha-beta, and oracle observations | Simple smoothing introduced lag and was not a reliable main estimator | Report, summary, one figure | Estimator comparison superseded by UKF |
| `stage4_ukf` | Compare UKF and UKF-bias | UKF-bias became the later target-reaching mainline under biased observations; feasibility remained unresolved | Report, summary, one figure | Mainline decision carried into later stages |
| `stage5_coupling` | Ablate estimator/identifier coupling | Filtered state into MPC and Windowed NLS with adaptation enabled was the preferred data flow | Report, summary, one figure | Coupling decision carried into later stages |
| `stage6_safety_filter` | Test one-step runtime action filtering | Negative baseline: the filter often destroyed target reaching | Report and summary | Method closed |
| `stage6b` | Diagnose sign convention and force reversal | Sign convention and `F_tan` reversal were ruled out as the main failure cause | Report, probe, two diagnostic figures | Diagnostic complete |
| `stage7a_alpha_soft` | Test alpha-soft CEM | Better than runtime filtering but insufficiently robust | Report, summary/manifest, representative figures | Method closed |
| `stage7b_progress_governor` | Test fixed-rate progress governance | Target reaching and safety were unreliable | Report, summary, three figures | Method closed |
| `stage7c_gatekeeper_lite` | Test lightweight gatekeeping | Preserved reaching and reduced omega risk but did not fix alpha tails | Report, summary, three figures | Method closed |
| `stage7c_gatekeeper_alpha_tail` | Revise gatekeeper for alpha tails | Revised scoring did not fix alpha p95/max severity | Report, summary, three figures | Method closed |
| `stage7d_safety_aware_governor` | Test safety-aware command governor | Failed target reaching and worsened safety tails | Report, summary, three figures | Method closed |
| `stage8a_ukf_sensitivity` | One-factor UKF-bias covariance sensitivity | Keep default covariance; tuning did not reliably resolve alpha tails | Report, summary, three figures | Sensitivity study complete |
| `stage8b_oracle_diagnosis` | Diagnose oracle/budget/action-smoothness effects | No tested method jointly preserved full reaching and reduced alpha p95/max | Report, summary, three figures | Diagnostic complete |
| `stage8c_constraint_revision` | Audit alpha metric and task/constraint conflict | Report raw max together with p95/p99/duration/integral; simple time/urgency changes did not resolve the conflict | Report, summary, three figures | Diagnostic complete |
| `stage8d_low_freq_cem` | Test low-frequency action parameterizations | No low-frequency mode improved all alpha metrics while preserving 3/3 reaching | Report, summary, three figures | Method closed |
| `stage8e_explicit_nmpc` | Test minimal explicit direct-shooting NMPC | The minimal formulation failed crossing and had a 100% solver failure rate | Report, summary, three figures | Superseded by scaled multiple shooting |

Historical scripts remain under `scripts/`. Rerunning them may recreate their original active `results/stage*` output directories; those regenerated outputs are local artifacts until curated.
