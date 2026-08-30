# Stage-4 Single-Challenger Closed-Loop A/B

Evidence: `formal_user_run_unreviewed`.

The cylindrical quantity is a minimum-norm equivalent surface-load proxy, not pressure or comfort.

| arm | termination | completion s | progress | first promotion s |
|---|---:|---:|---:|---:|
| prior_only | completed | 28.8700000000123 | 1.000000 | none |
| trusted_adaptive | completed | 28.8700000000123 | 1.000000 | 9.720000000000052 |

## full_task

| arm | tracking RMSE deg | max deg | F peak/RMS N | M peak/RMS Nm | surface proxy peak/RMS N |
|---|---:|---:|---:|---:|---:|
| prior_only | 0.765477 | 1.81988 | 143.896 / 103.442 | 20.4372 / 12.8794 | 133.918 / 86.7215 |
| trusted_adaptive | 0.713056 | 1.56114 | 144.637 / 103.533 | 20.4372 / 12.874 | 133.918 / 86.6946 |

## pre_first_trusted_adaptive_promotion

| arm | tracking RMSE deg | max deg | F peak/RMS N | M peak/RMS Nm | surface proxy peak/RMS N |
|---|---:|---:|---:|---:|---:|
| prior_only | 0.536527 | 1.47469 | 117.871 / 99.4781 | 20.4372 / 17.7373 | 133.918 / 116.689 |
| trusted_adaptive | 0.536527 | 1.47469 | 117.871 / 99.4781 | 20.4372 / 17.7373 | 133.918 / 116.689 |

## post_first_trusted_adaptive_promotion

| arm | tracking RMSE deg | max deg | F peak/RMS N | M peak/RMS Nm | surface proxy peak/RMS N |
|---|---:|---:|---:|---:|---:|
| prior_only | 0.858633 | 1.81988 | 143.896 / 105.397 | 18.1639 / 9.50741 | 118.896 / 66.534 |
| trusted_adaptive | 0.787659 | 1.56114 | 144.637 / 105.532 | 18.1393 / 9.49628 | 118.794 / 66.4811 |
