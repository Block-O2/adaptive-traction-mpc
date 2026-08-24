# Stage 11F: Exact Discrete One-step Closure Audit

## Scope

- Execution mode: `full`.
- Evidence level: `formal`; mechanical status: `valid_full_run`.
- Analyzed runs/windows: 24/710.
- Reused transition: `traction_mpc.models.spring2d_dynamics.step_dynamics` through `Spring2DEnv.step -> step_dynamics`.
- Alignment: replay `action[step]` maps replay true `state[step-1]` to true `state[step]`.
- Parameters: exact Stage 9J condition true parameters and dt.
- No parameter fit, optimizer, estimator, identifier, or controller is invoked.

This user-run formal artifact awaits human review. The generated report does not assign a scientific conclusion.

## Neutral closure summaries

| Condition | Windows | Discrete weighted RMS | Affine weighted RMS | Median ratio | Ratio p95 | Actions in limits |
|---|---:|---:|---:|---:|---:|---:|
| clean | 75 | 0 | 0.00268877 | 0 | 0 | True |
| initial_theta_offset | 87 | 0 | 0.0051644 | 0 | 0 | True |
| noise | 79 | 0 | 0.00454266 | 0 | 0 | True |
| noise_bias | 73 | 0 | 0.00545265 | 0 | 0 | True |
| stronger_noise | 90 | 0 | 0.00991067 | 0 | 0 | True |
| mass_mismatch | 150 | 0 | 0.000722315 | 0 | 0 | True |
| parameter_mismatch_low_k | 84 | 0 | 0.00214994 | 0 | 0 | True |
| parameter_mismatch_high_k | 72 | 0 | 0.00241819 | 0 | 0 | True |
| overall | 710 | 0 | 0.0039289 | 0 | 0 | True |

## Residual construction

- Raw residual is exact predicted next state minus replay true next state in `[theta, omega, r, r_dot]` order.
- Radial acceleration-equivalent residual is the `r_dot` one-step residual divided by dt.
- Angular acceleration-equivalent residual is the `omega` one-step residual divided by dt.
- Channels retain Stage 11D order `[radial, angular]` and square-root weights `[0.6, 0.25]`.
- The primary ratio divides the combined discrete weighted RMS by the unchanged combined Stage 11D affine truth weighted RMS.

## Human review criteria (not automatically applied)

- Finite-difference/continuous-regression bias supported: overall median ratio at most 0.01 and at least 7 of 8 conditions have median ratio at most 0.05.
- Discrete/model mismatch retained: overall median ratio at least 0.25 or at least 4 of 8 conditions have median ratio at least 0.25.
- Otherwise: inconclusive.
- These criteria are listed for human review only; this report does not select a category or assign PASS/FAIL/INCONCLUSIVE.

## Limitations

- This is a replay-closure diagnostic, not a closed-loop experiment.
- Saved replay actions are used directly after mechanically confirming that they lie within the environment action limits.
- The discrete acceleration-equivalent residual and affine residual retain the same channel weights but arise from different residual constructions.
