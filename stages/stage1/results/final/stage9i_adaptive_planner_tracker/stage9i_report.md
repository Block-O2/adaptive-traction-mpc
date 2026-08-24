# Stage 9I Adaptive Planner/Tracker

Stage 9I separates raw alpha from alpha violation severity and tests UKF-bias plus filtered Windowed NLS integration.

## Aggregate Summary

| method | condition | crossed | raw_alpha_max | alpha_violation_max | crossing_time | planner_fail | tracker_fail | fallback | replan |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive_planner_tracker | clean | 3/3 | 6.363 | 3.363 | 3.1 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | damping_mismatch | 3/3 | 6.423 | 3.423 | 3.16 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | initial_theta_offset | 3/3 | 6.246 | 3.246 | 3.42 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | larger_target_angle | 3/3 | 6.326 | 3.326 | 2.82 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | mass_mismatch | 3/3 | 18.2 | 15.2 | 5.27 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | noise | 3/3 | 6.489 | 3.489 | 3.23 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | noise_bias | 3/3 | 6.856 | 3.856 | 3.073 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | parameter_mismatch_high_k | 3/3 | 6.338 | 3.338 | 3.01 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | parameter_mismatch_low_k | 3/3 | 6.372 | 3.372 | 3.35 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | stronger_bias | 3/3 | 7.198 | 4.198 | 3.003 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker | stronger_noise | 3/3 | 28.8 | 25.8 | 3.107 | 0 | 0 | 0 | 0 |
| adaptive_planner_tracker_replan | clean | 3/3 | 6.363 | 3.363 | 2.48 | 0 | 0 | 0 | 3 |
| adaptive_planner_tracker_replan | damping_mismatch | 3/3 | 6.423 | 3.423 | 2.25 | 0 | 0 | 0 | 2 |
| adaptive_planner_tracker_replan | initial_theta_offset | 3/3 | 6.246 | 3.246 | 2.77 | 5 | 0 | 0 | 2 |
| adaptive_planner_tracker_replan | larger_target_angle | 3/3 | 6.326 | 3.326 | 3.16 | 7 | 0 | 0 | 2 |
| adaptive_planner_tracker_replan | mass_mismatch | 3/3 | 18.2 | 15.2 | 5.04 | 19 | 0 | 0 | 3 |
| adaptive_planner_tracker_replan | noise | 3/3 | 13.87 | 10.87 | 3.073 | 0.6667 | 0 | 0 | 3.667 |
| adaptive_planner_tracker_replan | noise_bias | 3/3 | 6.856 | 3.856 | 2.413 | 0.6667 | 0 | 0 | 2.667 |
| adaptive_planner_tracker_replan | parameter_mismatch_high_k | 3/3 | 6.338 | 3.338 | 2.19 | 0 | 0 | 0 | 2 |
| adaptive_planner_tracker_replan | parameter_mismatch_low_k | 3/3 | 6.372 | 3.372 | 2.68 | 0 | 0 | 0 | 2 |
| adaptive_planner_tracker_replan | stronger_bias | 3/3 | 7.198 | 4.198 | 2.583 | 0.6667 | 0 | 0 | 2.333 |
| adaptive_planner_tracker_replan | stronger_noise | 3/3 | 44.84 | 41.84 | 2.86 | 2.333 | 0 | 0 | 3.667 |
| baseline_cem | clean | 3/3 | 14.29 | 11.29 | 2.03 | 0 | 0 | nan | 0 |
| baseline_cem | damping_mismatch | 3/3 | 11.51 | 8.514 | 2.037 | 0 | 0 | nan | 0 |
| baseline_cem | initial_theta_offset | 3/3 | 12.14 | 9.142 | 2.127 | 0 | 0 | nan | 0 |
| baseline_cem | larger_target_angle | 3/3 | 17.45 | 14.45 | 3.967 | 0 | 0 | nan | 0 |
| baseline_cem | mass_mismatch | 2/3 | 36.74 | 33.74 | 2.35 | 0 | 0 | nan | 0 |
| baseline_cem | noise | 3/3 | 25.91 | 22.91 | 3.143 | 0 | 0 | nan | 0 |
| baseline_cem | noise_bias | 3/3 | 11.96 | 8.963 | 2.25 | 0 | 0 | nan | 0 |
| baseline_cem | parameter_mismatch_high_k | 2/3 | 11.88 | 8.878 | 1.795 | 0 | 0 | nan | 0 |
| baseline_cem | parameter_mismatch_low_k | 3/3 | 11.4 | 8.396 | 2.06 | 0 | 0 | nan | 0 |
| baseline_cem | stronger_bias | 3/3 | 20.64 | 17.64 | 2.687 | 0 | 0 | nan | 0 |
| baseline_cem | stronger_noise | 3/3 | 31.01 | 28.01 | 2.217 | 0 | 0 | nan | 0 |
| fixed_planner_tracker | clean | 0/3 | 6.363 | 3.363 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | damping_mismatch | 0/3 | 6.423 | 3.423 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | initial_theta_offset | 0/3 | 6.246 | 3.246 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | larger_target_angle | 0/3 | 6.326 | 3.326 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | mass_mismatch | 0/3 | 17.49 | 14.49 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | noise | 0/3 | 6.489 | 3.489 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | noise_bias | 0/3 | 6.856 | 3.856 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | parameter_mismatch_high_k | 0/3 | 6.338 | 3.338 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | parameter_mismatch_low_k | 0/3 | 6.372 | 3.372 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | stronger_bias | 0/3 | 7.198 | 4.198 | nan | 0 | 0 | 0 | 0 |
| fixed_planner_tracker | stronger_noise | 0/3 | 6.619 | 3.619 | nan | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | clean | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | damping_mismatch | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | initial_theta_offset | 3/3 | 2.996 | 0 | 1.8 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | larger_target_angle | 3/3 | 3.206 | 0.2063 | 1.85 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | mass_mismatch | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | noise | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | noise_bias | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | parameter_mismatch_high_k | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | parameter_mismatch_low_k | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | stronger_bias | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |
| oracle_planner_tracker | stronger_noise | 3/3 | 3.179 | 0.1789 | 1.72 | 0 | 0 | 0 | 0 |

## Required Answers

1. Stage 9H summary columns named alpha_max were violation severity, not raw alpha. Stage 9I logs raw_alpha_* and alpha_violation_* separately.
2. In Phase 1, oracle executed raw alpha max averaged 2.996 against planned limit 3; violation max averaged 0.
3. Adaptive planner/tracker preserved initial_theta_offset crossing in 3/3 runs.
4. Adaptive vs oracle Phase 1 raw alpha max: adaptive 6.246, oracle 2.996; crossing count adaptive 3, oracle 3.
5. Parameter-mismatch comparison: parameter_mismatch_low_k: fixed 0/3, adaptive 3/3; parameter_mismatch_high_k: fixed 0/3, adaptive 3/3; mass_mismatch: fixed 0/3, adaptive 3/3; damping_mismatch: fixed 0/3, adaptive 3/3. This is a task-success improvement, not a low-alpha success; mass_mismatch still has high adaptive raw alpha.
6. UKF-bias degradation in Phase 1: fixed-model state-estimated crossing 0/3, state RMSE 2.089.
7. One-shot planning Phase 1 adaptive crossing was 3/3; replanning count averaged 2.
8. Event-triggered replanning is not justified by this run: worst replan raw alpha was 44.84 and planner-failure count average is nonzero in several rows. No extra threshold tuning was done.
9. Phase 1 adaptive planner fail avg 0, tracker fail avg 0, fallback avg 0.
10. Single-link is not ready for linked-rods preparation as a low-alpha adaptive controller: Phase 2 adaptive worst raw alpha reached 28.8. Next work should address adaptive planner/tracker robustness before final statistical validation. No formal safety guarantee is claimed.
