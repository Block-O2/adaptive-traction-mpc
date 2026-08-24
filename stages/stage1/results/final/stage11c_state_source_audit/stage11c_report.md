# Stage 11C: Estimated-State vs True-State Paired Subspace Audit

## Dataset coverage

- Mode: `full`; state source: `paired`; runs=24; windows=710; transitions/window=70.
- Mechanical status: `valid_full_run`.
- Both sources use identical actions, window ends, weights, parameterization, adaptive profiles, and SVD/subspace diagnostics.

## Scientific interpretation

Scientific interpretation is pending review against the approved Experiment Spec.
This report presents observed metrics only and does not assign scientific PASS, FAIL, or INCONCLUSIVE.

## State-source metrics

- `estimated`: practical identifiability=not established; 1D/2D truth inclusion=(0.563, 0.008); 1D/2D stable=(True, False).
- `true`: practical identifiability=not established; 1D/2D truth inclusion=(0.494, 0.375); 1D/2D stable=(True, True).
## Paired differences

- True minus estimated truth inclusion: 1D=-0.069; 2D=0.366.
- Median true-minus-estimated residual RMS=-0.00568; physical-scale condition=-2.4; conditional lambda information ratio change=0.00162.
- Median estimated-vs-true direction angle: 1D=2.95 deg; 2D principal angle=8.35 deg.
- Direction concentration change: v1=-0.0396; v12=0.0769.

## Limitations

- Passive rehabilitation trajectories only; no active excitation.
- True-state regression is an oracle diagnostic, not an implementable online estimator.
