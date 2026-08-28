# Stage-4 hierarchical trust offline audit

The prototype is not production-default. Oracle data was appended only after each causal promotion decision.

| case | L1 valid/invalid | L2 valid/invalid | candidates | promoted | valid unpromoted | pending | first promotion s | max no-promotion s | promoted/nonpromoted oracle median Nm | rejected-better pair probability | full-trace oracle prior->final Nm | final/prior truth distance |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal_200hz | 1149/1 | 1149/0 | 36 | 29 | 0 | 7 | 6.880 | 6.880 | 0.810/nan | nan | 4.325->0.301 | 0.439/0.460 |
| noise_200hz | 1144/6 | 1144/0 | 36 | 16 | 14 | 6 | 6.880 | 7.000 | 1.887/0.902 | 0.045 | 4.430->1.006 | 0.437/0.460 |
| noise_bias_drift_200hz | 1144/6 | 1144/0 | 36 | 22 | 8 | 6 | 6.880 | 7.000 | 1.186/0.748 | 0.227 | 4.430->0.968 | 0.693/0.460 |
| noise_bias_delay_200hz | 660/7 | 660/0 | 16 | 5 | 0 | 11 | 6.850 | 6.850 | 3.382/nan | nan | 5.408->3.720 | 0.504/0.460 |
| noise_bias_delay_100hz | 634/7 | 634/0 | 18 | 12 | 0 | 6 | 7.330 | 7.330 | 2.406/nan | nan | 5.145->2.667 | 0.466/0.460 |
