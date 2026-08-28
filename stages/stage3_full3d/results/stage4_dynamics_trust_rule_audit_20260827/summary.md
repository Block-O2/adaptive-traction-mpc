# Stage-4 dynamics trust-rule numerical audit

Saved traces were replayed offline. Production estimator logic, bounds, and tolerance were not modified.

## Bound-detection tolerance sweep

| atol | mode | accepted | trust wall/phase (s) | accepted attempts |
|---:|---|---:|---:|---|
| 0e+00 | existing_cem | 16 | 6.500/3.250 | [0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17] |
| 0e+00 | cem_plus_smooth_local_refinement | 21 | 6.480/3.240 | [0, 1, 2, 3, 4, 10, 11, 12, 15, 16, 18, 19, 20, 21, 22, 29, 40, 41, 42, 48, 50] |
| 1e-12 | existing_cem | 8 | 6.500/3.250 | [0, 1, 2, 6, 10, 12, 13, 14] |
| 1e-12 | cem_plus_smooth_local_refinement | 3 | 6.480/3.240 | [0, 1, 3] |
| 1e-10 | existing_cem | 7 | 6.500/3.250 | [0, 1, 2, 10, 12, 13, 14] |
| 1e-10 | cem_plus_smooth_local_refinement | 1 | 6.480/3.240 | [0] |
| 1e-09 | existing_cem | 5 | 6.500/3.250 | [0, 1, 2, 10, 13] |
| 1e-09 | cem_plus_smooth_local_refinement | 1 | 6.480/3.240 | [0] |
| 1e-08 | existing_cem | 3 | 6.500/3.250 | [0, 2, 10] |
| 1e-08 | cem_plus_smooth_local_refinement | 1 | 6.480/3.240 | [0] |
| 1e-07 | existing_cem | 3 | 6.500/3.250 | [0, 2, 10] |
| 1e-07 | cem_plus_smooth_local_refinement | 0 | - | [] |
| 1e-06 | existing_cem | 1 | 11.500/7.240 | [10] |
| 1e-06 | cem_plus_smooth_local_refinement | 0 | - | [] |
| 1e-05 | existing_cem | 1 | 11.500/7.240 | [10] |
| 1e-05 | cem_plus_smooth_local_refinement | 0 | - | [] |

## Interpretation

The tolerance sweep reproduces the current raw-unit distance test only. It is a sensitivity diagnosis, not a proposed scientific acceptance rule.
