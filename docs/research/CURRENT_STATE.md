# Current Research State

## Repository checkpoint

- Observed branch: `agent/midterm-stage11-closeout`
- Scientific-state checkpoint reviewed: `26f735ad514aef14d16f65ca1a7a747bd1ea54c8`

## Current stage

Stage 11D: residual-and-coverage diagnostic.

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

- The residual-and-coverage diagnostic is approved as exploratory work.
- It must use the exact Stage 11C true-state window identities and unchanged
  Stage 11B regression construction.
- Codex may run tests and one local, non-authoritative smoke only.
- The complete Stage 11D diagnostic is not authorized for Codex execution.

## Current freeze

- No new estimator, controller, or safety architecture.
- Allowed work is limited to baseline reconstruction, single-variable ablation, logging, offline replay, and failure-case diagnosis.

## Next authorized action

- Review the Stage 11D implementation and local smoke output.
- Do not run the complete Stage 11D diagnostic yet.
- Do not modify Stage 11C results or assign an automatic scientific outcome.

## Known documentation debt

- The `WindowedLeastSquaresIdentifier` logging-only docstring may not reflect its Stage 9J adaptive use. Record only; do not edit source in this task.
