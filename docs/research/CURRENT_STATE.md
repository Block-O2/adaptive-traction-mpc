# Current Research State

## Repository checkpoint

- Observed branch: `agent/midterm-stage11-closeout`
- Stage 11F implementation checkpoint: `9cd59740865781e0188f596b9e820f1f3591dc81`

## Current stage

Stage 11G: exact-discrete local information audit.

## Authoritative inputs

- Stage 9J replay: `results/stage9j_gap_decomposition/stage9j_replay.csv`
- Stage 11B estimated-state passive subspace audit: `results/stage11b_parameter_subspace_audit/`
- Stage 11C true-state window identities and profile summaries:
  `results/stage11c_state_source_audit/`

## Validated findings

- The fixed-weight online MHE branch was closed after Stage 10F.
- Stage 11A does not support hard or soft information gating.
- Stage 11B did not establish a stable passive parameter subspace.
- The reviewed Stage 11E block-aware calibration result does not explain the
  true-state lambda undercoverage through simple serial-correlation calibration.
- The simple serial-correlation calibration branch is closed; structured
  point-bias H2 remains the active explanation.
- The reviewed Stage 11F replay-closure result supports
  finite-difference/continuous-regression formulation bias: exact discrete
  residual RMS and its affine ratio are zero in all 710 windows.
- Stage 11F does not support discrete simulator/model mismatch, but it does not
  establish that a discrete identifier will work with estimated or noisy states.

## Unresolved question

After removing affine finite-difference formulation bias, does the exact
discrete one-step model retain sufficient passive local information for
`theta = [lambda, kappa, beta]`?

## Stage 11C status

- The full paired matrix is present and mechanically marked `valid_full_run`.
- Stage 11C contains 24 runs and 710 aligned true/estimated windows.
- Its generated report remains neutral and does not assign an automatic scientific
  outcome.

## Stage 11D status

- The user-run full residual-and-coverage matrix is present and mechanically
  marked `valid_full_run`.
- It contains the exact 24 runs and 710 Stage 11C true-state windows.
- Its generated report is neutral; no H1/H2 choice or scientific status has
  been assigned automatically.

## Stage 11E status

- The reviewed full result is mechanically valid: 24 runs and 710 windows.
- Baseline lambda coverage was 0.494; block-calibrated coverage was 0.266,
  for an absolute gain of -0.228.
- Zero of eight conditions gained at least 0.10 coverage.
- Median width inflation was 0.649 and the WLS point-estimate changed fraction
  was zero.
- Under the preregistered block-aware treatment, the user review records H1 as
  insufficient and practical calibration as failed.
- The simple serial-correlation calibration branch is closed. Structured
  point-bias H2 remains active.

## Stage 11F status

- The reviewed full result is mechanically valid: 24 runs and 710 windows.
- Exact discrete weighted residual RMS and the discrete/affine weighted RMS
  ratio are zero in every window and all eight conditions.
- The user review records finite-difference/continuous-regression formulation
  bias as supported and discrete simulator/model mismatch as not supported by
  this audit.
- This is a replay-closure result only. It is not evidence that an exact
  discrete identifier will work with estimated or noisy states.

## Stage 11G status

- The approved increment computes the local Jacobian of the exact discrete
  one-step acceleration-equivalent output with respect to
  `[lambda, kappa, beta]`.
- It uses deterministic central differences at relative step `1e-5`, repeats
  with half-step, and reuses the Stage 11B weighting, physical scaling, SVD,
  rank, weak-direction, and conditional-lambda-information definitions.
- Exact and affine Jacobians use the same Stage 11C/11D/11F 24-run,
  710-window identities.
- No fitting, optimization, estimator, identifier, or controller execution is
  permitted.
- Codex may implement, run tests and compile checks, and run one explicit local
  smoke only.
- The complete Stage 11G diagnostic remains reserved for the user.

## Current freeze

- No new estimator, controller, or safety architecture.
- Allowed work is limited to baseline reconstruction, single-variable ablation, logging, offline replay, and failure-case diagnosis.

## Next authorized action

- Review the Stage 11G implementation, tests, and local smoke artifact.
- Do not run the complete Stage 11G diagnostic yet.
- Do not modify Stage 11C/11D/11F results or assign an automatic Stage 11G
  scientific outcome.

## Known documentation debt

- The `WindowedLeastSquaresIdentifier` logging-only docstring may not reflect its Stage 9J adaptive use. Record only; do not edit source in this task.
