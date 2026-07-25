# Current Research State

## Repository checkpoint

- Observed branch: `agent/midterm-stage11-closeout`
- Stage 11E implementation checkpoint: `17e8915e9c60813bbaf381c02140d441695ff439`

## Current stage

Stage 11F: exact discrete one-step closure audit.

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

## Unresolved question

Is the remaining structured lambda bias introduced mainly by the
continuous-time finite-difference affine regression, or is it already present
in the exact discrete simulator transition?

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

- The approved increment compares the unchanged Stage 11D affine truth
  residual with exact one-step replay closure under the simulator RK4
  transition.
- It uses replay true states, recorded actions, true condition parameters, and
  the exact Stage 11C/11D 24-run, 710-window identities.
- No parameter fitting, optimization, estimator, controller, or identifier
  change is permitted.
- Codex may implement, run tests and compile checks, and run one explicit local
  smoke only.
- The complete Stage 11F diagnostic remains reserved for the user.

## Current freeze

- No new estimator, controller, or safety architecture.
- Allowed work is limited to baseline reconstruction, single-variable ablation, logging, offline replay, and failure-case diagnosis.

## Next authorized action

- Review the Stage 11F implementation, tests, and local smoke artifact.
- Do not run the complete Stage 11F diagnostic yet.
- Do not modify Stage 11C/11D/11E results or assign an automatic Stage 11F
  scientific outcome.

## Known documentation debt

- The `WindowedLeastSquaresIdentifier` logging-only docstring may not reflect its Stage 9J adaptive use. Record only; do not edit source in this task.
