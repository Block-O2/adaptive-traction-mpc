# Stage 4 10 ms latency localization

Architecture A, realistic noise, frozen 23 s trajectory, and nominal cuff placement; only routed timestamp delay differs.

| case | complete | duration (s) | termination | RMSE (deg) | peak F (N) | off-axis M (N m) | peak robot speed (deg/s) |
|---|---:|---:|---|---:|---:|---:|---:|
| no_delay | True | 23.000 | completed | 0.785 | 118.91 | 1.81 | 16.42 |
| estimator_delay_only | True | 23.000 | completed | 0.813 | 119.02 | 1.93 | 16.26 |
| mpc_state_delay_only | True | 23.000 | completed | 0.960 | 120.02 | 1.85 | 20.13 |
| low_level_delay_only | False | 14.900 | total_commanded_cuff_force_gate | 0.789 | 165.30 | 9.64 | 56.14 |
| all_delay | False | 14.195 | total_commanded_cuff_force_gate | 0.897 | 161.96 | 9.55 | 54.06 |
| all_delay_low_level_extrapolated | False | 12.200 | total_commanded_cuff_force_gate | 0.967 | 166.58 | 9.08 | 48.23 |
