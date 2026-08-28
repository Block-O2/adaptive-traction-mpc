# Stage 4 split-confidence execution comparison

Engineering comparison only; estimator, MPC, plant, sensing, gains, and safety limits are shared.

| mode | termination | reference complete (s) | phase reached (s) | mean/min/max speed | tracking RMSE (deg) | peak force (N) | geom A/R | dyn A/R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| fixed_speed | completed | 23.000 | 23.000 | 1.000/1.000/1.000 | 0.701 | 117.29 | 38/2 | 4/35 |
| adaptive_speed | completed | 26.845 | 28.155 | 0.880/0.500/1.000 | 0.563 | 117.95 | 40/5 | 13/40 |
