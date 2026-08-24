# Stage 11B: Passive Parameter-Subspace Audit

## Dataset coverage

- Mode: `full`; runs=24, windows=710, transitions/window=70.
- Adaptive profiles: initial grid=15 points per dimension, with automatic boundary expansion and local refinement.
- Parameter order: `[lambda, kappa, beta]`.

## Mathematical conventions

- Profile cost is the complete weighted residual sum of squares; nuisance parameters are least-squares profiled at every grid point.
- Numerical rank, practical conditioning, and direction stability are reported separately.
- Normalized and physical-coordinate SVD directions are distinct; physical directions use division by the column norms.

## Full-audit interpretation

Required conclusion: **no stable passive parameter subspace established**.
Numerical rank-3 fraction is 1.000, while practical identifiability is `not established` under the combined physical-scale, profile, absolute-sensitivity, and direction-stability checks.
Across-condition stability: 1D=True (concentration=0.969, angular p95=19.59 deg); 2D=False (concentration=0.947, angular p95=32.34 deg).

## Condition summaries

- `overall`: windows=710, rank3=1.000, physical-scale cond=68.9, sigma_min/residual=24.1, conditional lambda abs/ratio=(3.25, 0.897), practical=not established.
- `clean`: windows=75, rank3=1.000, physical-scale cond=87.7, sigma_min/residual=41.3, conditional lambda abs/ratio=(3.75, 0.964), practical=not established.
- `initial_theta_offset`: windows=87, rank3=1.000, physical-scale cond=80.9, sigma_min/residual=61.7, conditional lambda abs/ratio=(4.07, 0.903), practical=not established.
- `mass_mismatch`: windows=150, rank3=1.000, physical-scale cond=365, sigma_min/residual=38.2, conditional lambda abs/ratio=(0.158, 0.526), practical=not established.
- `noise`: windows=79, rank3=1.000, physical-scale cond=60.7, sigma_min/residual=10.8, conditional lambda abs/ratio=(3.49, 0.919), practical=not established.
- `noise_bias`: windows=73, rank3=1.000, physical-scale cond=58.5, sigma_min/residual=11, conditional lambda abs/ratio=(4.82, 0.901), practical=not established.
- `parameter_mismatch_high_k`: windows=72, rank3=1.000, physical-scale cond=57, sigma_min/residual=125, conditional lambda abs/ratio=(5.07, 0.967), practical=not established.
- `parameter_mismatch_low_k`: windows=84, rank3=1.000, physical-scale cond=105, sigma_min/residual=41.8, conditional lambda abs/ratio=(2.32, 0.941), practical=not established.
- `stronger_noise`: windows=90, rank3=1.000, physical-scale cond=48.3, sigma_min/residual=9.57, conditional lambda abs/ratio=(5.03, 0.724), practical=not established.

## Profile statistics

Profile summaries contain 1420 compact rows. Overall median relative widths: lambda 1D=0.031; lambda in 2D=0.0381; kappa in 2D=0.0122.
Truth inclusion fractions: 1D=0.563, 2D=0.008; resolved-region fraction=1.000; unresolved boundary fraction=0.000.
Each row records the LS optimum, truth cost/inclusion, 95% widths, boundary status, expansion/refinement counts, accepted-point count, and a ridge only when at least three accepted 2D points exist.

## Limitations

- Passive rehabilitation trajectories only; no active excitation.
- Numerical rank does not by itself imply practical or separate parameter identifiability.
- The practical-support decision uses declared conservative diagnostics and the complete 24-run passive replay audit; it is not a proof of global identifiability.
