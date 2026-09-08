# Phase-3A corrected baseline: Rigid NEW vs P1 NEW

Exploratory evidence only. Formal classifications and the prior strict P1 numerical-qualification FAIL are preserved.

| case | arm | evidence | formal | physical outbound/return % | tracking RMSE deg | endpoint/return deg | Human demand RMS/peak N | position F RMS/peak N | velocity F RMS/peak N | nominal executable RMS/peak N | command RMS/peak N | physical RMS/peak N | force slew RMS/peak N/s | moment peak Nm | SF/FI/BRAKE/NSA | P1 deformation mm/deg |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 40/80 | rigid | REUSED_HASH_LOCKED_RIGID_NEW_BASELINE | COMPLETE | 100.00/100.00 | 0.080024 | 0.000636/0.009260 | 101.408/122.845 | 1.208/2.893 | 0.412/1.393 | 101.504/123.982 | 101.508/123.982 | 101.424/121.576 | 768.007/252000.697 | 17.355 | 0/0/0/0 | 0.095/0.068 |
| 40/80 | P1 | NEW_REGISTERED_RUN | SAFE_INCOMPLETE | 99.72/99.99 | 0.447750 | 0.133323/0.816850 | 101.404/122.877 | 1.316/2.976 | 0.437/3.749 | 101.629/124.742 | 101.633/124.742 | 101.566/122.058 | 225.676/8733.299 | 19.062 | 0/0/0/0 | 1.055/0.509 |
| 90/120 | rigid | NEW_REGISTERED_RUN | SAFE_INCOMPLETE | 96.18/100.00 | 1.925403 | 4.200879/0.044553 | 88.488/121.514 | 60.951/118.804 | 1.120/6.139 | 112.582/151.088 | 112.586/151.088 | 109.455/140.293 | 917.355/252000.697 | 65.102 | 0/0/0/0 | 0.093/0.148 |
| 90/120 | P1 | NEW_REGISTERED_RUN | SAFE_INCOMPLETE | 96.49/99.87 | 1.740756 | 3.858937/0.857479 | 88.744/121.659 | 51.207/101.909 | 0.969/4.696 | 107.358/137.497 | 107.361/137.497 | 104.957/128.898 | 232.109/8733.299 | 57.430 | 0/0/0/0 | 1.084/1.048 |
| 120/120 | rigid | NEW_REGISTERED_RUN | SAFE_INCOMPLETE | 99.33/99.99 | 0.262704 | 0.774398/0.027297 | 81.972/118.378 | 5.971/16.870 | 0.519/2.038 | 83.696/119.316 | 83.695/119.316 | 81.750/116.934 | 629.106/252000.697 | 17.219 | 0/0/0/0 | 0.076/0.068 |
| 120/120 | P1 | NEW_REGISTERED_RUN | SAFE_INCOMPLETE | 99.30/99.80 | 0.488700 | 0.809383/0.834416 | 81.953/118.514 | 5.813/16.356 | 0.531/3.749 | 83.720/119.963 | 83.720/119.963 | 81.863/117.734 | 182.448/8733.299 | 19.062 | 0/0/0/0 | 1.035/0.509 |

## Matched differences (P1 NEW minus Rigid NEW)

| case | tracking RMSE delta deg | command peak delta N | physical peak delta N | physical slew RMS delta N/s | BRAKE transition delta | FILTER_INFEASIBLE sample delta |
|---|---:|---:|---:|---:|---:|---:|
| 40/80 | 0.367726 | 0.759 | 0.482 | -542.331 | +0 | +0 |
| 90/120 | -0.184648 | -13.590 | -11.395 | -685.246 | +0 | +0 |
| 120/120 | 0.225997 | 0.647 | 0.800 | -446.659 | +0 | +0 |

Force-norm differences are comparisons, not additive component decompositions.

## P1 deformation and exploratory energy diagnostics

| case | translation peak mm | rotation peak deg | stored energy peak J | damping loss J | max absolute residual J | max positive residual J | max absolute residual ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| 40/80 | 1.054999 | 0.508738 | 0.116350225 | 0.119145663 | 0.00210281292 | 0.000117117589 | 0.00972214489 |
| 90/120 | 1.083744 | 1.048087 | 0.464555354 | 0.140137067 | 0.00220880733 | 0.000117117589 | 0.00384302215 |
| 120/120 | 1.035306 | 0.508738 | 0.116350225 | 0.164928191 | 0.00210281292 | 0.000117117589 | 0.00804545105 |

Reference completion and physical geometric progress are reported separately. No new practical completion threshold is introduced.

No controller, estimator, gain, force threshold, timing, solver, seed, trajectory, Human/robot model, geometry, Safety Filter, BRAKE, or P1 parameter was changed.
