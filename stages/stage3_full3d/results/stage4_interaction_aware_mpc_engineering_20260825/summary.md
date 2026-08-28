# Stage 4 interaction-aware Adaptive MPC engineering comparison

One registered A/B only. No post-result tuning was performed.

`||A_dagger w||` is a minimum-norm equivalent cylindrical surface-load effort proxy, not pressure.

| mode | complete time | tracking RMSE / max | force peak / RMS | moment peak / RMS | surface effort peak / RMS | force-rate peak / RMS |
|---|---:|---:|---:|---:|---:|---:|
| current_adaptive_mpc | 27.250 s | 0.799 / 1.739 deg | 113.14 / 86.98 N | 24.54 / 18.99 Nm | 160.05 / 123.98 N | 67183.9 / 1697.5 N/s |
| interaction_aware_adaptive_mpc | 27.250 s | 0.799 / 1.739 deg | 113.14 / 86.98 N | 24.54 / 18.99 Nm | 160.05 / 123.98 N | 67183.9 / 1697.5 N/s |
