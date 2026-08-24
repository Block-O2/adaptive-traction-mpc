# Current Research State

## Repository checkpoint

- Observed branch: `agent/midterm-stage11-closeout`
- Stage 11G implementation checkpoint: `d96ddb6`
- Research state: **single-link Spring2D phase closed after professor review**

## Final reviewed mechanism chain

1. Fixed/oracle MPC and the long-horizon planner plus short-horizon tracker can
   complete the tested single-link task.
2. Estimated-state errors-in-variables degrade the Windowed NLS identification
   path, but the paired true-state audit shows that EIV is not the complete
   explanation.
3. A fixed block-aware bootstrap did not repair lambda coverage: overall
   coverage changed from 0.494 to 0.266, with zero of eight conditions gaining
   at least 0.10.
4. The affine finite-difference/continuous-regression identifier introduces
   structured point bias on the retained replay.
5. The exact discrete simulator transition closes that replay exactly: the
   weighted residual RMS and exact/affine residual ratio are zero in all 710
   audited windows.
6. Exact-discrete local parameter information is retained at true states and
   true parameters.
7. Exact-discrete parameter recovery itself remains untested.
8. Stage 11H is cancelled because the professor closed the single-link phase.

## Final reviewed Stage 11G result

- Mechanical status: `valid_full_run`.
- Matrix: 24 runs, 710 windows, eight conditions.
- Exact-discrete Jacobian rank-3 fraction: 1.0.
- Overall median exact/affine conditional-lambda-information ratio: 689.197.
- All eight conditions satisfy the retained-information criterion.
- Registered central-difference stability requirement: passed.
- Human-reviewed interpretation: exact-discrete local information is retained;
  exact-discrete information collapse is not supported by this audit.

This is local true-state evidence only. It does not prove parameter recovery
with noisy or estimated states, online estimator performance, closed-loop
adaptive performance, or a safety/stability guarantee. The value 689.197 is an
information ratio, not an estimator-accuracy improvement factor.

## Retained evidence

- Authoritative replay input:
  `results/stage9j_gap_decomposition/stage9j_replay.csv`
- Planner/tracker and gap evidence:
  `results/stage9h_planner_tracker/` and
  `results/stage9j_gap_decomposition/`
- Identification diagnosis:
  `results/stage9k_identifier_ablation/`
- Closed MHE branch:
  `results/stage10f_mhe_divergence_audit/`
- Final paired-state, residual, calibration, closure, and information evidence:
  `results/stage11c_state_source_audit/` through
  `results/stage11g_discrete_information_audit/`
- Scientific closeout:
  `docs/research/SINGLE_LINK_CLOSEOUT.md`

## Closed work

- No Stage 11H implementation or execution.
- No new single-link estimator, controller, or safety architecture is
  authorized under this phase.
- Historical negative-result implementations and curated evidence remain for
  reproducibility; they are not active development branches.

## Explicitly unresolved

- Offline exact-discrete parameter recovery at true states.
- Recovery under estimated-state error and measurement noise.
- Online exact-discrete identification and its closed-loop interaction with the
  planner/tracker.
- Formal safety, stability, robustness, hardware, and multi-link validation.

The next project phase is maintained separately. It will begin with the
professor-supplied MATLAB linkage reference model, which is not present in this
repository.

## Known documentation debt

- The `WindowedLeastSquaresIdentifier` logging-only docstring may not reflect
  its Stage 9J adaptive use. It is retained unchanged as historical code.
