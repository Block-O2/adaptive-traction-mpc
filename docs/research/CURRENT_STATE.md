# Current Research State

## Repository checkpoint

- Observed branch: `agent/midterm-stage11-closeout`
- Stage 11D formal-input checkpoint: `44ad70466523ce30a6e897261acac90b1fc3ffbf`

## Current stage

Stage 11E: block-aware lambda coverage calibration audit.

## Authoritative inputs

- Stage 9J replay: `results/stage9j_gap_decomposition/stage9j_replay.csv`
- Stage 11B estimated-state passive subspace audit: `results/stage11b_parameter_subspace_audit/`
- Stage 11C true-state window identities and profile summaries:
  `results/stage11c_state_source_audit/`

## Validated findings

- The fixed-weight online MHE branch was closed after Stage 10F.
- Stage 11A does not support hard or soft information gating.
- Stage 11B did not establish a stable passive parameter subspace.

## Unresolved question

Why does true-state regression greatly improve the `[lambda, kappa]` geometry
while the one-dimensional lambda profile still under-covers lambda?

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

- The approved increment calibrates only the Stage 11C true-state lambda
  interval width with a transition-level circular moving-block score bootstrap.
- The two weighted regression channels remain paired by transition.
- Block length 10, 2000 replicates per window, deterministic window seeds,
  70-transition windows, WLS point estimates, and Stage 11C profile results are
  fixed by the experiment contract.
- Codex is authorized to implement, run tests and compile checks, and run one
  explicit local smoke only.
- The complete Stage 11E diagnostic remains reserved for the user.

## Current freeze

- No new estimator, controller, or safety architecture.
- Allowed work is limited to baseline reconstruction, single-variable ablation, logging, offline replay, and failure-case diagnosis.

## Next authorized action

- Review the Stage 11E implementation, tests, and local smoke artifact.
- Do not run the complete Stage 11E diagnostic yet.
- Do not modify Stage 11C/11D results or assign an automatic scientific
  outcome.

## Known documentation debt

- The `WindowedLeastSquaresIdentifier` logging-only docstring may not reflect its Stage 9J adaptive use. Record only; do not edit source in this task.
