# Stage 4 sensor-realism engineering summary

These deterministic perturbations are engineering assumptions, not measured CR12 specifications.
All non-ideal cases use the same 8 Hz causal low-pass and 120 ms local-quadratic derivative window.
No F/T bias is estimated or subtracted, and MuJoCo bed/contact truth is not fed to the estimator.

| case | complete | geom trust (s) | dyn trust (s) | dyn L2 err (%) | track RMSE (deg) | peak F (N) | torque frac |
|---|---:|---:|---:|---:|---:|---:|---:|
| ideal_200hz | True | 2.82 | 8.32 | 9.94 | 0.719 | 117.66 | 0.457 |
| noise_200hz | True | 2.30 | - | 13.73 | 0.840 | 119.03 | 0.481 |
| noise_bias_drift_200hz | True | 2.30 | - | 13.73 | 0.840 | 119.03 | 0.481 |
| noise_bias_delay_200hz | False | 2.27 | - | 13.73 | 0.926 | 168.13 | 0.668 |
| noise_bias_delay_100hz | False | 2.25 | - | 13.73 | 0.873 | 156.67 | 0.633 |
