# Stage 9C Scaled Alpha-Slack NMPC Validation Report

## Scope
- Formal closed-loop validation of the Stage 9B solvable scaled multiple-shooting NMPC formulation.
- Meaningful slack activity threshold: s_alpha > 1e-05.
- Clean multi-seed phase runs first; noise/noise_bias only run if clean is reasonable.
- No broad tuning and no formal safety claims.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage9c_scaled_nmpc_validation.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage9c_scaled_nmpc_validation`

## Aggregate Metrics
| method | condition | target | fail rate | fallback | solve | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack active | omega p95 | omega max | delta_r | force |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alpha200_omega0 | clean | 5/5 | nan | nan | nan | 4.922 | 8.726 | 9.494 | 0.866 | 2.132 | nan | nan | 0 | 0.3635 | 0.4838 | 0 | 0 |
| alpha200_omega0 | noise | 5/5 | nan | nan | nan | 5.03 | 8.663 | 9.233 | 0.932 | 2.132 | nan | nan | 0 | 0.3887 | 0.5173 | 0 | 0 |
| alpha200_omega0 | noise_bias | 4/5 | nan | nan | nan | 4.793 | 9.078 | 22.62 | 1.024 | 3.194 | nan | nan | 0 | 0.3279 | 0.6089 | 0 | 0 |
| baseline_cem | clean | 5/5 | nan | nan | nan | 5.436 | 9.408 | 10.22 | 0.81 | 2.159 | nan | nan | 0 | 0.32 | 0.4532 | 0 | 0 |
| baseline_cem | noise | 5/5 | nan | nan | nan | 4.954 | 9.946 | 17.2 | 0.97 | 2.747 | nan | nan | 0 | 0.3086 | 0.4971 | 0 | 0 |
| baseline_cem | noise_bias | 5/5 | nan | nan | nan | 4.857 | 7.859 | 9.045 | 0.816 | 2.04 | nan | nan | 0 | 0.3205 | 0.4934 | 0 | 0 |
| nmpc_rho1000_scaled | clean | 5/5 | 0 | 0 | 0.06454 | 2.905 | 3.202 | 3.308 | 0.29 | 0.3942 | 1.601e-05 | 8.762e-05 | 1080 | 0 | 0 | 0 | 0 |
| nmpc_rho1000_scaled | noise | 5/5 | 0 | 0 | 0.06324 | 2.826 | 3.212 | 3.4 | 0.424 | 0.4161 | 1.675e-05 | 9.226e-05 | 1188 | 0.00662 | 0.0384 | 0 | 0 |
| nmpc_rho1000_scaled | noise_bias | 5/5 | 0 | 0 | 0.06369 | 2.864 | 3.527 | 3.756 | 0.452 | 0.4397 | 1.589e-05 | 8.829e-05 | 1080 | 0.01427 | 0.04571 | 0 | 0 |
| nmpc_rho100_scaled | clean | 5/5 | 0 | 0 | 0.07476 | 2.9 | 3.201 | 3.308 | 0.29 | 0.3937 | 0.0001618 | 0.0008189 | 6300 | 0 | 0 | 0 | 0 |
| nmpc_rho100_scaled | noise | 5/5 | 0 | 0 | 0.07592 | 2.827 | 3.212 | 3.399 | 0.42 | 0.4158 | 0.0001725 | 0.0009411 | 6317 | 0.006693 | 0.03842 | 0 | 0 |
| nmpc_rho100_scaled | noise_bias | 5/5 | 0 | 0 | 0.07568 | 2.87 | 3.53 | 3.755 | 0.452 | 0.4383 | 0.0001667 | 0.0008861 | 6300 | 0.01433 | 0.04574 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | clean | 5/5 | 0 | 0 | 0.07661 | 2.9 | 3.201 | 3.308 | 0.29 | 0.3937 | 0.0001618 | 0.0008189 | 6300 | 0 | 0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | noise | 5/5 | 0 | 0 | 0.07595 | 2.827 | 3.212 | 3.399 | 0.42 | 0.4158 | 0.0001725 | 0.0009411 | 6317 | 0.006693 | 0.03842 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | noise_bias | 5/5 | 0 | 0 | 0.075 | 2.87 | 3.53 | 3.755 | 0.452 | 0.4383 | 0.0001667 | 0.0008861 | 6300 | 0.01433 | 0.04574 | 0 | 0 |

## Required Answers
1. Does scaled NMPC solve reliably on clean multi-seed?
- Yes: clean rho100 solver failure rate=0.

2. Does it preserve target reaching vs baseline CEM?
- Yes: clean rho100 target=5/5, baseline=5/5.

3. Does it reduce alpha p95/p99/max/duration/integral?
- Yes: clean rho100 alpha p95/p99/max/duration/integral=2.9/3.201/3.308/0.29/0.3937, baseline=5.436/9.408/10.22/0.81/2.159.

4. Does it avoid worsening omega/delta_r/force violations?
- Yes: clean rho100 omega p95/max=0/0, delta_r=0, force=0.

5. How often is alpha slack meaningfully active?
- Clean rho100 thresholded active count=6300 with threshold 1e-05; mean/max slack=0.0001618/0.0008189.

6. Is rho100 enough, or does rho1000 help?
- rho1000 does not materially help clean aggregate alpha max/target: rho1000 alpha max=3.308, rho100 alpha max=3.308.

7. Is solve time acceptable for this small system?
- Yes for offline/small-system validation: clean rho100 mean solve time=0.07476 s.

8. Does fallback materially improve robustness?
- No material effect observed: fallback clean target=5, fallback rate=0.

9. Should next step be stress validation, NMPC refinement, alpha/task redesign, or linked rods preparation?
- Recommended next step: stress validation.
