# Phase-3A Robot Control Velocity Path A/B

Exploratory diagnostic evidence only. Formal classifications are preserved.

| case | path | formal | outbound % | return % | tracking RMSE deg | endpoint deg | return deg | velocity F RMS/peak N | command peak N | physical peak N | BRAKE entries | FILTER_INFEASIBLE |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 40/40 | OLD | COMPLETE | 100.00 | 100.00 | 0.157621 | 0.000533 | 0.012788 | 1.668/6.449 | 121.049 | 117.448 | 0 | 0 |
| 40/40 | NEW | COMPLETE | 100.00 | 100.00 | 0.157137 | 0.014173 | 0.022757 | 0.392/1.366 | 119.423 | 117.086 | 0 | 0 |
| 40/80 | OLD | SAFE_INCOMPLETE | 100.00 | 100.00 | 24.661855 | 0.016985 | 64.241169 | 13.433/83.137 | 200.000 | 197.497 | 0 | 1 |
| 40/80 | NEW | COMPLETE | 100.00 | 100.00 | 0.080024 | 0.000636 | 0.009260 | 0.412/1.393 | 123.982 | 121.576 | 0 | 0 |

No controller, model, gain, force threshold, timing, trajectory, or completion tolerance was changed.
