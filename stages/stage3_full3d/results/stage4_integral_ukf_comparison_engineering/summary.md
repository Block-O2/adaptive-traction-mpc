# Stage 4 integral identifier: minimal versus state UKF

Engineering comparison only; no controller, trajectory, plant, gain, or safety setting differs between A and B.

| arch | case | complete | dyn trust (s) | dyn A/R | base L2 (%) | prediction RMSE (N m) | tracking RMSE (deg) | peak F (N) | estimator mean (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | ideal_200hz | True | 4.32 | 4/35 | 9.09 | 2.967 | 0.701 | 117.29 | 1.512 |
| A | noise_200hz | True | 3.80 | 6/33 | 8.60 | 2.525 | 0.671 | 118.91 | 1.490 |
| A | noise_delay_200hz | False | 5.27 | 3/16 | 11.81 | 3.603 | 0.869 | 153.47 | 0.932 |
| B | ideal_200hz | True | 4.02 | 2/36 | 11.63 | 3.606 | 1.661 | 118.15 | 1.974 |
| B | noise_200hz | True | - | 0/38 | 13.73 | 4.340 | 1.543 | 120.32 | 2.002 |
| B | noise_delay_200hz | False | - | 0/22 | 13.73 | 4.392 | 1.510 | 167.72 | 1.514 |
