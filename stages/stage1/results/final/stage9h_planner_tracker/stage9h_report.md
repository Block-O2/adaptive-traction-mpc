# Stage 9H Planner + Tracker

This stage tests a hierarchical long-horizon crossing planner plus short-horizon NMPC tracker. It does not change Spring2D dynamics, baseline CEM, Stage 9D/9F results, or the target crossing success definition.

## Part A Boundary

| mode | N | time_s | success | alpha_peak | warm_start | status |
|---|---:|---:|---:|---:|---|---|
| fixed_alpha_3 | 42 | 1.26 | False | 3 | heuristic | Infeasible_Problem_Detected |
| fixed_alpha_4 | 42 | 1.26 | False | 4 | heuristic | Infeasible_Problem_Detected |
| min_alpha | 42 | 1.26 | False | nan | heuristic | Infeasible_Problem_Detected |
| fixed_alpha_3 | 45 | 1.35 | False | 3 | heuristic | Infeasible_Problem_Detected |
| fixed_alpha_4 | 45 | 1.35 | False | 4 | heuristic | Infeasible_Problem_Detected |
| min_alpha | 45 | 1.35 | True | 14.36 | interpolated_nearest_successful_longer_horizon | Solve_Succeeded |
| fixed_alpha_3 | 48 | 1.44 | False | 3 | heuristic | Infeasible_Problem_Detected |
| fixed_alpha_4 | 48 | 1.44 | False | 4 | heuristic | Infeasible_Problem_Detected |
| min_alpha | 48 | 1.44 | True | 5.31 | interpolated_nearest_successful_longer_horizon | Solve_Succeeded |
| fixed_alpha_3 | 50 | 1.5 | False | 3 | heuristic | Infeasible_Problem_Detected |
| fixed_alpha_4 | 50 | 1.5 | True | 4 | minimum_alpha_solution | Solve_Succeeded |
| min_alpha | 50 | 1.5 | True | 3.733 | interpolated_nearest_successful_longer_horizon | Solve_Succeeded |
| fixed_alpha_3 | 54 | 1.62 | True | 3 | minimum_alpha_solution | Solve_Succeeded |
| fixed_alpha_4 | 54 | 1.62 | True | 4 | minimum_alpha_solution | Solve_Succeeded |
| min_alpha | 54 | 1.62 | True | 2.348 | interpolated_nearest_successful_longer_horizon | Solve_Succeeded |
| fixed_alpha_3 | 57 | 1.71 | True | 3 | minimum_alpha_solution | Solve_Succeeded |
| fixed_alpha_4 | 57 | 1.71 | True | 4 | minimum_alpha_solution | Solve_Succeeded |
| min_alpha | 57 | 1.71 | True | 1.837 | interpolated_nearest_successful_longer_horizon | Solve_Succeeded |
| fixed_alpha_3 | 60 | 1.8 | True | 3 | minimum_alpha_solution | Solve_Succeeded |
| fixed_alpha_4 | 60 | 1.8 | True | 4 | minimum_alpha_solution | Solve_Succeeded |
| min_alpha | 60 | 1.8 | True | 1.508 | smooth_reference | Solve_Succeeded |

Multiple warm starts were attempted; a single IPOPT failure was not treated as physical infeasibility.

## Phase 1 Aggregate

| method | condition | crossed | alpha_p95 | alpha_max | tracker_fail | fallback | tracking_error |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline_cem | initial_theta_offset | 3/3 | 4.832 | 9.142 | nan | nan | nan |
| nmpc_base | initial_theta_offset | 0/3 | 0 | 3.138 | 0 | 0 | nan |
| nmpc_crossing_weighted | initial_theta_offset | 3/3 | 0.7287 | 27.07 | 0 | 0 | nan |
| oracle_planner_nmpc_tracker | initial_theta_offset | 3/3 | 0 | 0 | 0 | 0 | 0.03757 |
| oracle_planner_nmpc_tracker_with_cem_fallback | initial_theta_offset | 3/3 | 0 | 0 | 0 | 0 | 0.03757 |

## Phase 2 Aggregate

| method | condition | crossed | alpha_p95 | alpha_max | tracker_fail | fallback | tracking_error |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline_cem | clean | 3/3 | 6.026 | 11.29 | nan | nan | nan |
| baseline_cem | larger_target_angle | 3/3 | 5.638 | 14.45 | nan | nan | nan |
| baseline_cem | noise | 3/3 | 4.993 | 22.91 | nan | nan | nan |
| baseline_cem | noise_bias | 3/3 | 4.723 | 8.963 | nan | nan | nan |
| baseline_cem | parameter_mismatch_high_k | 2/3 | 4.315 | 8.878 | nan | nan | nan |
| baseline_cem | parameter_mismatch_low_k | 3/3 | 5.424 | 8.396 | nan | nan | nan |
| baseline_cem | stronger_noise | 3/3 | 6.373 | 28.01 | nan | nan | nan |
| nmpc_base | clean | 3/3 | 2.9 | 3.308 | 0 | 0 | nan |
| nmpc_base | larger_target_angle | 3/3 | 1.118 | 3.308 | 0 | 0 | nan |
| nmpc_base | noise | 3/3 | 2.827 | 3.421 | 0 | 0 | nan |
| nmpc_base | noise_bias | 3/3 | 2.862 | 3.776 | 0 | 0 | nan |
| nmpc_base | parameter_mismatch_high_k | 3/3 | 2.832 | 3.277 | 0 | 0 | nan |
| nmpc_base | parameter_mismatch_low_k | 3/3 | 2.805 | 3.32 | 0 | 0 | nan |
| nmpc_base | stronger_noise | 3/3 | 2.616 | 3.536 | 0 | 0 | nan |
| nmpc_crossing_weighted | clean | 3/3 | 2.324 | 22.96 | 0 | 0 | nan |
| nmpc_crossing_weighted | larger_target_angle | 3/3 | 0.03944 | 23.06 | 0 | 0 | nan |
| nmpc_crossing_weighted | noise | 3/3 | 1.031 | 23.21 | 0 | 0 | nan |
| nmpc_crossing_weighted | noise_bias | 3/3 | 1.124 | 23.37 | 0 | 0 | nan |
| nmpc_crossing_weighted | parameter_mismatch_high_k | 3/3 | 0.1115 | 23.04 | 0 | 0 | nan |
| nmpc_crossing_weighted | parameter_mismatch_low_k | 3/3 | 0.01979 | 22.92 | 0 | 0 | nan |
| nmpc_crossing_weighted | stronger_noise | 3/3 | 3.232 | 23.47 | 0 | 0 | nan |
| oracle_planner_nmpc_tracker | clean | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker | larger_target_angle | 3/3 | 0.006692 | 0.2063 | 0 | 0 | 0.04084 |
| oracle_planner_nmpc_tracker | noise | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker | noise_bias | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker | parameter_mismatch_high_k | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker | parameter_mismatch_low_k | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker | stronger_noise | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | clean | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | larger_target_angle | 3/3 | 0.006692 | 0.2063 | 0 | 0 | 0.04084 |
| oracle_planner_nmpc_tracker_with_cem_fallback | noise | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | noise_bias | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | parameter_mismatch_high_k | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | parameter_mismatch_low_k | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |
| oracle_planner_nmpc_tracker_with_cem_fallback | stronger_noise | 3/3 | 0 | 0.1789 | 0 | 0 | 0.03322 |

Note: oracle planner/tracker rows use true state and true physical parameters for architecture validation. The parameter_mismatch rows mainly stress the reference adaptive methods; adaptive planner/tracker integration is not included here.

## Required Answers

1. The shortest practically feasible alpha<=3 crossing horizon found in Part A is N=54 (1.62 s). The refined alpha<=3 boundary is below N=60, but it still requires a long crossing horizon relative to the short N=18 tracker.
2. The oracle planner + tracker crossed under initial_theta_offset in 3/3 runs.
3. Actual alpha relative to the plan: phase-1 oracle alpha max severity average was 0; planned hard alpha limit was 3 rad/s^2.
4. It avoided Stage 9F-like alpha spikes in the aggregate metric used here.
5. Tracker failure average for oracle planner + tracker was 0; fallback average was 0.
6. One-shot planning is plausible only if tracking error stays bounded; this run logs tracking error but does not prove replanning is unnecessary.
7. Adaptive state/parameter integration was not mixed into the oracle architecture in this script; it remains a gated Part C follow-up after oracle evidence is accepted.
8. The single-link architecture is a candidate for final adaptive ablation before linked-rods preparation, but not a formal safety result.

No formal safety guarantee is claimed.
