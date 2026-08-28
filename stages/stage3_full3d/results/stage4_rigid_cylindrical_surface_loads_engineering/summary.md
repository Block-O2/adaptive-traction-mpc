# Stage 4 rigid cylindrical-surface cuff load audit

Engineering post-processing only. The validated rigid weld, Architecture A, controller, estimator, continuous 23 s trajectory, and safety settings are unchanged.

Rigid rerun completed: `True`; all trace arrays bitwise equal to baseline: `True`; maximum absolute difference: `0`.

Wrench map rank/nullity: `6/42`. All six resultant components are reproduced by 16 translational-force patches; no direct patch moment is used.

Common resultant: peak/RMS |F| `115.347/88.960 N`; peak/RMS |M| `24.825/18.673 N m`; peak |My| `24.823 N m`.

| Lc (mm) | max local (N) | patch peak range (N) | patch RMS range (N) | prox/dist row sum peak (N) | circumferential sector sum peaks (N) | concentration at max load | reduction vs 60 mm |
|---:|---:|---:|---:|---:|---|---:|---:|
| 60 | 67.12 | 8.43-67.12 | 4.91-49.74 | 189.70/163.38 | 77.45/221.10/76.82/251.18 | 1.750 | 0.0% |
| 80 | 62.38 | 8.99-62.38 | 5.53-46.32 | 188.67/160.19 | 86.71/197.36/86.18/225.99 | 1.709 | 7.1% |
| 100 | 57.59 | 9.35-57.59 | 5.84-42.86 | 183.28/153.17 | 90.80/174.78/90.30/201.93 | 1.688 | 14.2% |
| 120 | 53.08 | 9.38-53.08 | 5.88-39.58 | 175.52/144.19 | 91.32/154.68/90.82/180.41 | 1.679 | 20.9% |

Patch peak/RMS 4x4 matrices and full axial/circumferential distributions are in `comparison_summary.json`. These are equivalent surface forces, not pressure or clinical metrics.
