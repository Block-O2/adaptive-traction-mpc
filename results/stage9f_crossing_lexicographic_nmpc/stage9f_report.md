# Stage 9F Crossing-Constrained Lexicographic NMPC Report

## Scope
- Focused target-crossing repair for the Stage 9E near-target underreach failure.
- Terminal crossing constraint: theta_N >= theta_target + 0.1 deg - s_goal.
- Dynamics, estimator, identifier, force bounds, delta_r treatment, omega treatment, alpha definition/limit, and baseline CEM behavior are unchanged.
- rho_alpha_L1 remains 100. Weighted goal slack uses rho_goal_L1=1e6 and rho_goal_L2=1e5. Lexicographic Stage B uses goal_tolerance=1e-5 rad.
- No broad tuning and no formal safety claims.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage9f_crossing_lexicographic_nmpc.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage9f_crossing_lexicographic_nmpc`

## Aggregate Metrics
| method | condition | crossed | target | fail | fallback | solve | A/B solve | final err | max beyond | pred margin | goal slack A/B | alpha p95/max | omega max | delta_r | force |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | clean | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.09021 | 0.09021 | nan | nan/nan | 6.026/11.29 | 1.623 | 0 | 0 |
| baseline_cem | initial_theta_offset | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.1085 | 0.1085 | nan | nan/nan | 4.832/9.142 | 1.715 | 0 | 0 |
| baseline_cem | larger_target_angle | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.09601 | 0.09601 | nan | nan/nan | 5.638/14.45 | 1.603 | 0 | 0 |
| baseline_cem | noise | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.0725 | 0.0725 | nan | nan/nan | 4.993/22.91 | 1.638 | 0 | 0 |
| baseline_cem | noise_bias | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.1392 | 0.1392 | nan | nan/nan | 4.723/8.963 | 1.633 | 0 | 0 |
| baseline_cem | stronger_noise | 3/3 | 3/3 | nan | nan | nan | nan/nan | 0.4174 | 0.4174 | nan | nan/nan | 6.373/28.01 | 1.988 | 0 | 0 |
| nmpc_base | clean | 3/3 | 3/3 | 0 | 0 | 0.07043 | nan/nan | 0.05608 | 0.05608 | nan | nan/nan | 2.9/3.308 | 1.188 | 0 | 0 |
| nmpc_base | initial_theta_offset | 0/3 | 0/3 | 0 | 0 | 0.02907 | nan/nan | -0.05275 | -0.05275 | nan | nan/nan | 0/3.138 | 1.182 | 0 | 0 |
| nmpc_base | larger_target_angle | 3/3 | 3/3 | 0 | 0 | 0.07309 | nan/nan | 0.006675 | 0.006675 | nan | nan/nan | 1.118/3.308 | 1.19 | 0 | 0 |
| nmpc_base | noise | 3/3 | 3/3 | 0 | 0 | 0.07594 | nan/nan | 0.06807 | 0.06807 | nan | nan/nan | 2.827/3.421 | 1.238 | 0 | 0 |
| nmpc_base | noise_bias | 3/3 | 3/3 | 0 | 0 | 0.07635 | nan/nan | 0.08009 | 0.08009 | nan | nan/nan | 2.862/3.776 | 1.245 | 0 | 0 |
| nmpc_base | stronger_noise | 3/3 | 3/3 | 0 | 0 | 0.07893 | nan/nan | 0.1632 | 0.1632 | nan | nan/nan | 2.616/3.536 | 1.254 | 0 | 0 |
| nmpc_crossing_lexicographic | clean | 3/3 | 3/3 | 0 | 0 | 0.05512 | 0.02713/0.05512 | 0.3245 | 0.3245 | 0.1461 | 0.6837/0.3877 | 16.3/58.03 | 2.487 | 0 | 0 |
| nmpc_crossing_lexicographic | initial_theta_offset | 3/3 | 3/3 | 0 | 0 | 0.04856 | 0.02505/0.04856 | 0.2121 | 0.2121 | 0.3147 | 0.5216/0.2387 | 6.741/72.25 | 2.504 | 0 | 0 |
| nmpc_crossing_lexicographic | larger_target_angle | 3/3 | 3/3 | 0 | 0 | 0.05624 | 0.02739/0.05624 | 0.2958 | 0.2958 | 0.4257 | 0.5216/0.2536 | 7.93/76.38 | 2.86 | 0 | 0 |
| nmpc_crossing_lexicographic | noise | 3/3 | 3/3 | 0 | 0 | 0.0587 | 0.02958/0.0587 | 0.07288 | 0.07288 | 0.3418 | 0.5797/0.2901 | 7.983/61.34 | 2.399 | 0 | 0 |
| nmpc_crossing_lexicographic | noise_bias | 3/3 | 3/3 | 0 | 0 | 0.05806 | 0.02964/0.05806 | 0.1335 | 0.1335 | -0.08772 | 2.663/0.7328 | 15.65/60.63 | 2.435 | 0 | 0 |
| nmpc_crossing_lexicographic | stronger_noise | 3/3 | 3/3 | 0 | 0 | 0.05856 | 0.02943/0.05856 | 0.2777 | 0.2777 | 0.4276 | 0.5897/0.3031 | 8.132/61.2 | 2.393 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | clean | 3/3 | 3/3 | 0 | 0 | 0.05462 | 0.02712/0.05462 | 0.3245 | 0.3245 | 0.1461 | 0.6837/0.3877 | 16.3/58.03 | 2.487 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | initial_theta_offset | 3/3 | 3/3 | 0 | 0 | 0.05058 | 0.02701/0.05058 | 0.2121 | 0.2121 | 0.3147 | 0.5216/0.2387 | 6.741/72.25 | 2.504 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | larger_target_angle | 3/3 | 3/3 | 0 | 0 | 0.0561 | 0.02731/0.0561 | 0.2958 | 0.2958 | 0.4257 | 0.5216/0.2536 | 7.93/76.38 | 2.86 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | noise | 3/3 | 3/3 | 0 | 0 | 0.05712 | 0.02827/0.05712 | 0.07288 | 0.07288 | 0.3418 | 0.5797/0.2901 | 7.983/61.34 | 2.399 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | noise_bias | 3/3 | 3/3 | 0 | 0 | 0.05518 | 0.02883/0.05518 | 0.1335 | 0.1335 | -0.08772 | 2.663/0.7328 | 15.65/60.63 | 2.435 | 0 | 0 |
| nmpc_crossing_lexicographic_with_cem_fallback | stronger_noise | 3/3 | 3/3 | 0 | 0 | 0.05556 | 0.0289/0.05556 | 0.2777 | 0.2777 | 0.4276 | 0.5897/0.3031 | 8.132/61.2 | 2.393 | 0 | 0 |
| nmpc_crossing_weighted | clean | 3/3 | 3/3 | 0 | 0 | 0.03584 | nan/0.03584 | 0.1508 | 0.1508 | -13.23 | nan/13.62 | 2.324/22.96 | 1.287 | 0 | 0 |
| nmpc_crossing_weighted | initial_theta_offset | 3/3 | 3/3 | 0 | 0 | 0.03454 | nan/0.03454 | 0.139 | 0.139 | -14.68 | nan/15.06 | 0.7287/27.07 | 1.269 | 0 | 0 |
| nmpc_crossing_weighted | larger_target_angle | 3/3 | 3/3 | 0 | 0 | 0.0366 | nan/0.0366 | 0.2706 | 0.2706 | -19.27 | nan/19.65 | 0.03944/23.06 | 1.289 | 0 | 0 |
| nmpc_crossing_weighted | noise | 3/3 | 3/3 | 0 | 0 | 0.04149 | nan/0.04149 | 0.226 | 0.226 | -13.43 | nan/13.85 | 1.031/23.21 | 1.32 | 0 | 0 |
| nmpc_crossing_weighted | noise_bias | 3/3 | 3/3 | 0 | 0 | 0.04124 | nan/0.04124 | 0.1203 | 0.1203 | -13.35 | nan/13.77 | 1.124/23.37 | 1.334 | 0 | 0 |
| nmpc_crossing_weighted | stronger_noise | 3/3 | 3/3 | 0 | 0 | 0.04641 | nan/0.04641 | 0.1367 | 0.1367 | -13.61 | nan/14.15 | 3.232/23.47 | 1.362 | 0 | 0 |

## Phase 2
- Phase 2 ran for: clean, noise, noise_bias, stronger_noise, larger_target_angle.

## Variant Definitions
- `nmpc_base`: Stage 9D rho100 scaled NMPC.
- `nmpc_crossing_weighted`: adds terminal goal slack with weighted L1/L2 penalty.
- `nmpc_crossing_lexicographic`: Stage A minimizes goal slack; Stage B minimizes original NMPC cost under the Stage A slack bound.
- `nmpc_crossing_lexicographic_with_cem_fallback`: same lexicographic method, with baseline CEM fallback if either solve fails.

## Required Answers
1. Does an explicit crossing constraint restore target success?
- Yes: best crossing method=nmpc_crossing_weighted, initial_theta_offset crossing=3/3, base crossing=0/3.

2. Is lexicographic optimization better than a weighted goal-slack penalty?
- No/mixed: weighted crossed=3/3, lexicographic crossed=3/3; weighted alpha max=27.07, lexicographic alpha max=72.25.

3. Does crossing create a new alpha spike?
- Yes/mixed: winner alpha max=27.07, baseline CEM alpha max=9.142, base NMPC alpha max=3.138.

4. How much goal slack remains before and after Stage B?
- Lexicographic Stage A/B mean goal slack=0.5216/0.2387 deg on initial_theta_offset.

5. Are physical constraints still respected?
- Yes: winner force violations=0, delta_r violations=0.

6. Is the two-stage solve time acceptable?
- Yes for offline/small-system validation: lexicographic Stage A/B mean solve time=0.02505/0.04856 s.

7. Is fallback necessary?
- No material need observed: fallback variant crossed=3/3, fallback rate=0.

8. Is the single-link controller ready for linked-rods preparation?
- No: NMPC refinement; crossing improved target success but introduced regression risk.
- Recommended next step: NMPC refinement; crossing improved target success but introduced regression risk.
