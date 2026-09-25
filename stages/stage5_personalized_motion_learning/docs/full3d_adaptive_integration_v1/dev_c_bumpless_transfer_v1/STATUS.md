# DEV-C restart status

Status: **DEV_C_SCOPE_CHANGE_REQUIRED**. DEV-C is development evidence, not
fresh qualification. Do not run another DEV-C batch under the current design.

The original direct-switch dynamics jump was repaired at four matched
checkpoints, but the finite Human-action bridge did not meet the frozen
Human/cuff/CR12 output-continuity contract across the consumed 24-case
development regression. The later deployable output-envelope revision failed
closed at a recovery-start handoff: with its frozen zero-slope first step
(`alpha=0`) the Human-action step was zero, yet desired cuff force changed
5.059 N against the predeclared 2.69 N development gate. The accepted model
was not fully realized in that case. The source does not enable DEV-C by
default, and formal qualification explicitly rejects DEV-C opt-in.

Final evidence paths:

- `matched_v1/` through `matched_v4/`: versioned local direct/transfer traces;
  `matched_v3/` and `matched_v4/` each pass the four selected checkpoints.
- `regression_v1/`: completed consumed 24-case v2 development replay;
  authoritative `regression_summary_dev_c_v3.json` excludes non-executed
  terminal zero commands. 24 commissioned, 15 task entries, 2 complete;
  5 planner deadline misses correctly fail closed.
- `sessions_problem_v4_diag2/elevated_start_middle_r01/`: preserved v3
  output-envelope failure and exact endpoint-step event.
- `DEV_C_REPORT.md`: final interpretation and open causal decomposition.

No estimator, physical plant, task cost, scientific threshold, or historical
formal result was changed. No Git stage/commit/push/reset/stash/switch/delete.
