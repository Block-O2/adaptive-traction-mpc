# Stage-4 patient/model-mismatch robustness formal report

Evidence category: `formal_user_run_unreviewed`.

This is a paired engineering-robustness experiment within the current representable Human-V2 model family. It is not a clinical population claim. No post-hoc threshold or composite success score is used.

## Completion and integrity

All 13 preregistered cases and 26 arms are present. Provenance, frozen fingerprints, A/B isolation, causal embargo/non-overlap, and finite trace checks passed mechanically.

Both arms completed the reference in 10/13 cases. Both arms had the same incomplete-reference outcome in 3/13 cases. No recorded safety event occurred in any case.

## Per-case paired results

Positive benefit columns mean lower error under trusted adaptation.

| case | geom | progress P/A | tracking RMSE P/A (deg) | tracking benefit % | prediction RMSE P/A (Nm) | prediction benefit % | promotions | first promotion (s) | tags |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---|
| `nominal_reference` | no | 0.9617/0.9617 | 0.4331/0.4249 | 1.88 | 0.0000/0.0710 | n/a | 1 | 17.74 | controller_safety_failure_shared_incomplete_trajectory, mixed_primary_metrics_after_promotion, zero_mismatch_sanity_reference |
| `mass_mild_minus_05pct` | no | 1.0000/1.0000 | 0.8140/0.8028 | 1.37 | 1.2984/1.1561 | 10.96 | 2 | 8.60 | useful_adaptation_regime |
| `mass_mild_plus_05pct` | no | 1.0000/1.0000 | 0.2994/0.2566 | 14.29 | 1.2489/1.0743 | 13.98 | 3 | 9.66 | useful_adaptation_regime |
| `stiffness_moderate_minus_20pct` | no | 1.0000/1.0000 | 0.6128/0.6121 | 0.11 | 1.1210/1.0010 | 10.70 | 3 | 9.28 | useful_adaptation_regime |
| `stiffness_moderate_plus_20pct` | no | 0.9626/0.9626 | 0.6445/0.5990 | 7.06 | 1.2438/1.0514 | 15.46 | 2 | 17.70 | controller_safety_failure_shared_incomplete_trajectory, useful_adaptation_regime |
| `damping_moderate_minus_30pct` | no | 1.0000/1.0000 | 0.4530/0.4513 | 0.37 | 0.2346/0.2488 | -6.02 | 1 | 9.20 | mixed_primary_metrics_after_promotion |
| `damping_moderate_plus_30pct` | no | 0.9613/0.9613 | 0.3581/0.3555 | 0.74 | 0.2063/0.2145 | -3.95 | 1 | 17.76 | controller_safety_failure_shared_incomplete_trajectory, mixed_primary_metrics_after_promotion |
| `rest_equilibrium_moderate_minus_03deg` | no | 1.0000/1.0000 | 0.4262/0.4132 | 3.05 | 0.5236/0.5500 | -5.04 | 2 | 13.74 | mixed_primary_metrics_after_promotion |
| `rest_equilibrium_moderate_plus_03deg` | no | 1.0000/1.0000 | 0.8190/0.8141 | 0.60 | 0.5236/0.5018 | 4.16 | 2 | 8.60 | useful_adaptation_regime |
| `registered_stage2_mild_anchor` | no | 1.0000/1.0000 | 0.5612/0.4962 | 11.58 | 1.4592/1.2350 | 15.36 | 3 | 9.82 | useful_adaptation_regime |
| `registered_moderate_anchor` | yes | 1.0000/1.0000 | 1.0272/0.9561 | 6.92 | 2.0560/1.8174 | 11.61 | 4 | 10.02 | useful_adaptation_regime |
| `registered_formal_perturbed_anchor` | yes | 1.0000/1.0000 | 0.7655/0.7131 | 6.85 | 4.4244/3.9687 | 10.30 | 4 | 9.72 | useful_adaptation_regime |
| `registered_stage2_adverse_anchor` | yes | 1.0000/1.0000 | 1.9229/1.7761 | 7.63 | 3.8261/3.2669 | 14.62 | 4 | 10.28 | useful_adaptation_regime |

## Promotion and estimator behavior

Trusted adaptation entered control in 13/13 cases, with 32 promotions total. First promotion ranged from 8.60 to 17.76 s (median 9.82 s), leaving 14.12 to 18.70 s of reference.

The adaptive arms recorded 13 challenger rejections. Every case showed active-bound pressure in at least one challenger; the per-case counts and unconstrained violation magnitudes are retained in the aggregate JSON. This limits interpreting the fitted 11-base vectors as physical patient parameters.

## Mismatch type, geometry, and relationships

Tracking RMSE decreased in 13/13 cases; torque-prediction RMSE decreased in 9/13. Cases with prediction worsening are reported as mixed primary-metric outcomes even when tracking improved.

The three geometry-changing anchors had mean tracking improvement 7.13% and mean prediction improvement 12.17%. The ten dynamics-only cases (including the nominal reference) had mean tracking improvement 4.10% and mean defined prediction improvement 6.18%.

Across cases, prediction-error benefit and tracking-error benefit had Pearson r=0.870 and Spearman rho=0.791. These descriptive associations do not establish a threshold or causal dose-response. Mismatch-distance correlations are retained in the aggregate JSON and do not make the 11-base distance a population score.

Force, moment, and cylindrical surface-proxy values are logged descriptively per case in the aggregate JSON. They are not success criteria, and the cylindrical quantity is not pressure, comfort, or tissue loading.

## Next scientific question

Preregister a separate out-of-family model-inadequacy experiment that varies one unsupported mechanism at a time, while retaining this frozen controller and trust contract. The first target should distinguish estimator bound pressure from irreducible model residual; it should not retune bounds or add new control logic within the present evidence set.
