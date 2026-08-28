# Stage 4 reduced-estimator predictive audit

Offline engineering evidence only. The validated geometry + 11-base integral estimator remains unchanged.

| case | full rank/cond | reduced rank/cond | full torque RMSE | reduced torque RMSE | reduced normalized RMSE |
|---|---:|---:|---:|---:|---:|
| nominal_sanity | 11/349.0 | 3/1.3 | 0.000069 Nm | 0.000049 Nm | 0.000% |
| registered_moderate | 11/349.0 | 3/1.3 | 0.000071 Nm | 0.489762 Nm | 1.683% |
| registered_cold_start_perturbed | 11/349.0 | 3/1.3 | 0.000077 Nm | 0.063522 Nm | 0.201% |
