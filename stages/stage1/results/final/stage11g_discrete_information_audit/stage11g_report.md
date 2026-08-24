# Stage 11G: Exact-discrete Local Information Audit

## Scope

- Execution mode: `full`.
- Evidence level: `formal`; mechanical status: `valid_full_run`.
- Analyzed runs/windows: 24/710.
- Exact transition: `traction_mpc.models.spring2d_dynamics.step_dynamics`.
- Exact output order: radial `r_dot` increment/dt, then angular `omega` increment/dt.
- Jacobian: deterministic central differences at true `[lambda,kappa,beta]`, with relative step 1e-5 and a half-step repeat.
- Every window stacks 70 transitions into a 140 x 3 Jacobian.
- Stage 11B row weights, physical scaling, SVD, rank, physical weak direction, and conditional lambda information are reused directly.
- Replay x_(t+1) is not consumed by the exact-discrete Jacobian.
- No fit, optimizer, estimator, identifier, or controller is invoked.

This user-run formal artifact awaits human review. The generated report does not assign a scientific conclusion.

## Neutral information summaries

| Condition | Windows | Exact rank-3 | Affine rank-3 | Exact info | Affine info | Exact/affine info | Weak angle | Half-step max p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 75 | 1.000 | 1.000 | 3276.53 | 3.8422 | 724.758 | 0.2584 | 1.41e-07 |
| initial_theta_offset | 87 | 1.000 | 1.000 | 3435.8 | 4.1416 | 713.205 | 0.3808 | 2.57e-07 |
| noise | 79 | 1.000 | 1.000 | 2943.77 | 3.55372 | 694.204 | 0.4263 | 8.44e-08 |
| noise_bias | 73 | 1.000 | 1.000 | 4068.84 | 4.95225 | 693.537 | 0.3901 | 7.39e-08 |
| stronger_noise | 90 | 1.000 | 1.000 | 1596.27 | 5.11831 | 562.321 | 2.653 | 1.02e-08 |
| mass_mismatch | 150 | 1.000 | 1.000 | 122.377 | 0.164049 | 687.403 | 1.753 | 1.62e-05 |
| parameter_mismatch_low_k | 84 | 1.000 | 1.000 | 2053.29 | 2.4252 | 711.962 | 0.3103 | 5.07e-07 |
| parameter_mismatch_high_k | 72 | 1.000 | 1.000 | 4307.44 | 5.08443 | 723.189 | 0.3351 | 1.58e-07 |
| overall | 710 | 1.000 | 1.000 | 2368.58 | 3.37535 | 689.197 | 0.472 | 7.77e-07 |

## Human review criteria (not automatically applied)

- Exact-discrete local information retained: overall median exact/affine conditional-lambda-information ratio at least 0.5, at least 6 of 8 condition medians at least 0.25, and exact rank-3 fraction at least 0.95.
- Exact-discrete information collapse: overall median ratio at most 0.10 or at least 4 of 8 condition medians at most 0.10.
- Otherwise: inconclusive.
- Numerical derivative validity is a separate mechanical requirement.
- These criteria are listed for human review only; this report does not select a category or assign PASS/FAIL/INCONCLUSIVE.

## Limitations

- Local true-state information does not establish estimator performance under state-estimation error or measurement noise.
- Central differences evaluate local sensitivity only at true parameters.
- Smoke metrics, if present, are implementation checks rather than scientific evidence.
