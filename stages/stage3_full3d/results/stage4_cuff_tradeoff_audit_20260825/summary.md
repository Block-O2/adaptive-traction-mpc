# Stage 4 exact 1D cuff allocation trade-off

Structural audit with tau_h fixed sample-by-sample. No controller rerun or weight change.

`A_dagger w` is a minimum-norm equivalent cylindrical surface-load proxy, not pressure.

| strategy | force peak/RMS | moment peak/RMS | surface peak/RMS | local patch peak | force-gate samples | equality peak |
|---|---:|---:|---:|---:|---:|---:|
| minimum_force | 95.99/80.11 N | 23.27/17.77 Nm | 151.18/115.96 N | 57.36 N | 0 | 1.59e-14 Nm |
| minimum_surface_proxy | 237.89/173.72 N | 6.16/3.53 Nm | 71.46/48.99 N | 28.02 N | 569 | 3.10e-14 Nm |
| current_one_to_one | 114.91/91.98 N | 16.94/11.77 Nm | 111.11/79.07 N | 43.15 N | 0 | 1.64e-14 Nm |
| minimum_moment | 345.29/223.60 N | 0.00/0.00 Nm | 86.32/55.90 N | 21.58 N | 610 | 3.07e-14 Nm |

Knee weight ratio (surface/force): 1.99526
1:1 / knee ratio: 0.501187
