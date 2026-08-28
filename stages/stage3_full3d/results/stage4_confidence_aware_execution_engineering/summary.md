# Stage 4 confidence-aware execution comparison

Engineering comparison only. Estimator, MPC, plant, sensing, gains, and safety limits are shared.

| mode | termination | reference complete (s) | mean/min/max speed | tracking RMSE (deg) | peak force (N) | peak sagittal moment (N m) | geom/dyn updates |
|---|---|---:|---:|---:|---:|---:|---:|
| fixed_speed | completed | 23.000 | 1.000/1.000/1.000 | 0.701 | 117.29 | 27.10 | 38/4 |
| confidence_aware_speed | completed | - | 0.564/0.500/1.000 | 0.541 | 113.69 | 26.14 | 53/16 |
