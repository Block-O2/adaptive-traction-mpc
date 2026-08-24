# Stage 11D: Residual and Coverage Diagnostic

## Scope

- Execution mode: `full`.
- Evidence level: `formal`; mechanical status: `valid_full_run`.
- Analyzed runs/windows: 24/710.
- State source: replay true states only.
- Window identities, actions, 70-transition rule, row weights, affine parameterization, LS construction, and Stage 11C profile values are unchanged.

This is a user-run formal artifact awaiting review. It is not automatically authoritative and does not contain a scientific judgment.

## Metric definitions

- Regression channels are evaluated separately as radial and angular; autocorrelation never uses the interleaved residual sequence.
- Heteroscedasticity proxies use correlations between weighted squared residuals and raw destination-state/action magnitudes.
- The normalized truth score is the cosine-normalized projection `(H_w[:,j]^T e_w)/(||H_w[:,j]|| ||e_w||)`.
- State magnitude uses `[theta, r]`; state-rate magnitude uses `[omega, r_dot]`. These raw-unit norms are descriptive proxies only.

## Neutral summaries

| Condition | Windows | Lambda coverage | Lambda error (median) | Lambda rel. width (median) | Truth RMS radial/angular | Abs. lambda score (median) |
|---|---:|---:|---:|---:|---:|---:|
| clean | 75 | 0.440 | 0.007967 | 0.008519 | 0.003246/0.0007817 | 0.195 |
| initial_theta_offset | 87 | 0.517 | 0.005057 | 0.007233 | 0.007047/0.000609 | 0.1419 |
| noise | 79 | 0.633 | 0.004654 | 0.01169 | 0.006094/0.0007153 | 0.1111 |
| noise_bias | 73 | 0.589 | 0.006109 | 0.0117 | 0.007444/0.0008829 | 0.1356 |
| stronger_noise | 90 | 0.633 | 0.006887 | 0.01692 | 0.01393/0.001062 | 0.1642 |
| mass_mismatch | 150 | 0.400 | 0.006529 | 0.009467 | 0.0007507/0.00053 | 0.2068 |
| parameter_mismatch_low_k | 84 | 0.393 | 0.01116 | 0.005548 | 0.0024/0.0006473 | 0.4784 |
| parameter_mismatch_high_k | 72 | 0.417 | 0.007345 | 0.004699 | 0.002998/0.0008701 | 0.3283 |
| overall | 710 | 0.494 | 0.006483 | 0.009511 | 0.005237/0.0007138 | 0.1815 |

## Residual dependence and score summaries

| Condition | LS RMS radial/angular | Truth ACF lag 1 radial/angular | Truth ACF lag 5 radial/angular | Truth ACF lag 10 radial/angular | Squared-residual corr. state/rate/action (radial) | Abs. normalized truth score lambda/kappa/beta |
|---|---:|---:|---:|---:|---:|---:|
| clean | 0.003198/0.0007551 | 0.5703/0.9483 | -0.2136/0.7548 | 0.04362/0.5384 | -0.3302/0.1874/0.2758 | 0.195/0.08077/0.1411 |
| initial_theta_offset | 0.006854/0.0004926 | 0.6454/0.9448 | -0.003249/0.7495 | -0.1656/0.5327 | -0.3706/0.3403/0.2828 | 0.1419/0.0906/0.1592 |
| noise | 0.005815/0.0007536 | 0.6172/0.9254 | -0.1696/0.7059 | -0.09216/0.4712 | -0.271/0.2279/0.2236 | 0.1111/0.08392/0.1617 |
| noise_bias | 0.007187/0.0008907 | 0.5469/0.9241 | -0.08728/0.7015 | -0.01824/0.4948 | -0.2756/0.2288/0.2152 | 0.1356/0.08243/0.144 |
| stronger_noise | 0.0124/0.001464 | 0.6568/0.9079 | -0.08049/0.6592 | -0.03742/0.4533 | -0.1293/0.117/0.1559 | 0.1642/0.1274/0.1873 |
| mass_mismatch | 0.000772/0.0001184 | 0.5952/0.941 | -0.0131/0.7611 | -0.03491/0.5527 | -0.3595/0.3142/0.2739 | 0.2068/0.1228/0.1556 |
| parameter_mismatch_low_k | 0.002107/0.000493 | 0.5412/0.9473 | -0.1496/0.7562 | 0.03153/0.5171 | -0.4509/0.3636/0.4408 | 0.4784/0.0734/0.0842 |
| parameter_mismatch_high_k | 0.002918/0.0004786 | 0.5017/0.9498 | -0.1034/0.7552 | -0.01826/0.5263 | -0.2981/0.2336/0.249 | 0.3283/0.1155/0.09882 |
| overall | 0.005162/0.0007484 | 0.5999/0.9407 | -0.09446/0.7443 | -0.04022/0.5298 | -0.2976/0.2421/0.2607 | 0.1815/0.09959/0.1506 |

## Competing explanations

- H1 concerns residual dependence or non-constant residual scale.
- H2 concerns structured truth residual projected onto the lambda column.
- This generated report presents the requested diagnostics without automatically selecting H1 or H2 and without assigning a scientific outcome.

## Limitations

- Passive rehabilitation trajectories only; no active excitation.
- True-state regression is an oracle diagnostic, not a deployable estimator.
- Magnitude proxies combine variables with different physical units; no new normalization or threshold was introduced.
