# Stage 4 rigid finite-surface cuff load audit

Engineering post-processing only: the validated rigid weld, Architecture A, controller, estimator, continuous 23 s trajectory, and safety settings are unchanged.

Rigid rerun completed: `True`; trace arrays exactly match the registered baseline: `True`; maximum absolute trace difference: `0`.

Common resultant for every length: peak |F| `115.347 N`, peak |My| `24.823 N m`, peak off-axis moment norm `1.808 N m`.

| Lc (mm) | complete | max local (N) | patch peak norms (N) | patch RMS norms (N) | concentration max/mean | axial Mx residual peak (N m) |
|---:|:---:|---:|---|---|---:|---:|
| 60 | True | 515.58 | 515.58/186.10/149.47/479.09 | 389.25/140.95/109.96/358.04 | 1.579 | 1.805 |
| 80 | True | 391.93 | 391.93/144.97/108.87/355.13 | 296.03/110.09/79.30/264.83 | 1.605 | 1.805 |
| 100 | True | 317.81 | 317.81/120.33/84.80/280.81 | 240.13/91.66/61.12/208.96 | 1.632 | 1.805 |
| 120 | True | 268.41 | 268.41/103.91/69.03/231.37 | 202.89/79.43/49.21/171.76 | 1.658 | 1.805 |

The four collinear translational patches span only [Fx,Fy,Fz,My,Mz]. Mx is reported as an unachievable residual; no patch moment is invented.
