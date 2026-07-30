# Stage 11E: Block-aware Lambda Coverage Calibration Audit

## Scope

- Execution mode: `full`.
- Evidence level: `formal`; mechanical status: `valid_full_run`.
- Analyzed runs/windows: 24/710.
- Baseline: saved Stage 11C true-state one-dimensional lambda profile.
- Treatment: transition-level circular moving-block score bootstrap.
- The two weighted regression channels stay paired by transition.
- Fixed block length/replicates: 10/2000; every replicate contains exactly 70 transitions.
- The original WLS optimum and Stage 11C profile calculation are not changed or refitted.

This user-run formal artifact awaits human review. The generated report does not assign a scientific conclusion.

## Neutral coverage and width summaries

| Condition | Windows | Baseline coverage | Calibrated coverage | Absolute gain | Baseline rel. width | Calibrated rel. width | Median inflation | Point changed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 75 | 0.440 | 0.200 | -0.240 | 0.008519 | 0.004267 | 0.4913 | 0.000 |
| initial_theta_offset | 87 | 0.517 | 0.207 | -0.310 | 0.007233 | 0.004341 | 0.5692 | 0.000 |
| noise | 79 | 0.633 | 0.367 | -0.266 | 0.01169 | 0.00687 | 0.6304 | 0.000 |
| noise_bias | 73 | 0.589 | 0.233 | -0.356 | 0.0117 | 0.007399 | 0.6596 | 0.000 |
| stronger_noise | 90 | 0.633 | 0.511 | -0.122 | 0.01692 | 0.0123 | 0.7694 | 0.000 |
| mass_mismatch | 150 | 0.400 | 0.267 | -0.133 | 0.009467 | 0.005398 | 0.7222 | 0.000 |
| parameter_mismatch_low_k | 84 | 0.393 | 0.143 | -0.250 | 0.005548 | 0.004026 | 0.6299 | 0.000 |
| parameter_mismatch_high_k | 72 | 0.417 | 0.167 | -0.250 | 0.004699 | 0.002891 | 0.5706 | 0.000 |
| overall | 710 | 0.494 | 0.266 | -0.228 | 0.009511 | 0.005582 | 0.6491 | 0.000 |

## Human review criteria (not automatically applied)

- H1 materially supported: overall coverage gain at least 0.20 and at least 6 of 8 conditions gain at least 0.10.
- H1 weakly supported or inconclusive: intermediate results.
- H1 insufficient: overall gain below 0.10 and fewer than 4 of 8 conditions gain at least 0.10.
- Practical calibration is a separate judgment requiring overall coverage at least 0.85 and median width inflation at most 5.
- These criteria are listed for human review only; this report does not select any category or assign PASS/FAIL/INCONCLUSIVE.

## Limitations

- Passive rehabilitation trajectories only; no active excitation.
- True-state regression is an oracle diagnostic, not a deployable estimator.
- The moving-block result evaluates one fixed block length and one fixed bootstrap contract; no data-driven block selection is performed.
- Truth lambda is used only to score coverage after interval construction.
