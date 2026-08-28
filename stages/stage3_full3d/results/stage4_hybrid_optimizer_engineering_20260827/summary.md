# Stage 4 hybrid MPC engineering A/B

One registered engineering A/B. No post-result tuning was performed.

| mode | completion | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS | objective mean | local accept | MPC mean/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| existing_cem | 27.260 s | 0.706/1.683 deg | 132.13/99.38 N | 18.98/13.63 Nm | 124.64/91.09 N | 2.952 | 0/1600 | 176.6/180.5 ms |
| cem_plus_smooth_local_refinement | - | 0.847/2.035 deg | 124.32/103.00 N | 19.14/11.14 Nm | 125.67/76.07 N | 3.445 | 1315/1600 | 263.5/272.3 ms |

Phase-matched descriptive interval: 0-16.000 s.

| mode | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS |
|---|---:|---:|---:|---:|
| existing_cem | 0.716/1.683 deg | 132.13/104.46 N | 18.98/11.15 Nm | 124.64/76.27 N |
| cem_plus_smooth_local_refinement | 0.847/2.035 deg | 124.32/103.00 N | 19.14/11.14 Nm | 125.67/76.07 N |
