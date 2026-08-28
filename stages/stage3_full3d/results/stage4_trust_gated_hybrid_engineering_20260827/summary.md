# Stage 4 dynamics-trust-gated hybrid engineering A/B

One registered engineering A/B. The only variable is local-refinement eligibility after the existing dynamics trust event.

| mode | completion | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS | MPC mean/p95 |
|---|---:|---:|---:|---:|---:|---:|
| original_cem | 27.260 s | 0.706/1.683 deg | 132.13/99.38 N | 18.98/13.63 Nm | 124.64/91.09 N | 178.5/180.9 ms |
| dynamics_trust_gated_hybrid | 27.260 s | 0.696/2.017 deg | 133.22/99.49 N | 18.91/13.63 Nm | 124.23/91.10 N | 247.6/267.8 ms |

- pre-trust calls without local refinement: 325
- post-trust eligible/accepted calls: 1275/1127
- mean post-trust objective improvement over all eligible calls: 8.250%
