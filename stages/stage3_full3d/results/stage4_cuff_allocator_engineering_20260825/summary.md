# Stage 4 cuff allocator engineering comparison

The allocator preserves the requested Human generalized torque. `A_dagger w` is not pressure.

| allocator | complete | equality peak | tracking RMSE / max | force peak / RMS | moment peak / RMS | surface effort peak / RMS | local patch proxy peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_force_minimizing_allocator | 27.250 s | 3.575e-14 Nm | 0.799 / 1.739 deg | 113.14 / 86.98 N | 24.54 / 18.99 Nm | 160.05 / 123.98 N | 61.55 N |
| cuff_aware_allocator | 27.260 s | 1.856e-13 Nm | 0.706 / 1.683 deg | 132.13 / 99.38 N | 18.98 / 13.63 Nm | 124.64 / 91.09 N | 48.62 N |
