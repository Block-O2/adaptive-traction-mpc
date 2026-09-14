# Deterministic Stage-5 Baseline Checkpoint

This checkpoint freezes the matched, non-learning deterministic Stage-5
controller immediately before interface-mismatch experiments.

## Controller contract

- Goal-directed, path-free Human-space CEM-MPC. No full q1/q2 time reference,
  coordination ratio, or path corridor is active.
- The single total Human input is parameterized as
  `u_total = u_support + delta_u_motion`; CEM optimizes the motion increment.
- Controller observation uses only the deployable Human/interface estimator.
  MuJoCo Human truth is evaluation-only.
- The nominal interface predictor carries explicit translation, rotation,
  velocity, base-drive, and previous-executable-wrench state across solves.
- Loaded execution has one explicit Human-cuff/robot-cuff pose, twist,
  deformation, and wrench-reference-point authority.
- OUTBOUND and RETURN use Goal-MPC. HOLD uses the validated local loaded-
  equilibrium stabilizer with smooth handoffs.
- Registered task envelopes remain [45, 75] deg/s and [300, 600] deg/s2, with
  acceleration interpreted over the common 20 ms interval.
- Plant-v1, Safety Filter, BRAKE, and the 200 N simulation engineering gate are
  unchanged.
- The fixed Human model is active. Human adaptation, interface learning,
  learned terminal value, and RL/value training are inactive.

## Compact matched evidence

The committed evidence record is
`results/goal_mpc_runtime_v1/optimized_attempt_03_final/summary.json`, SHA-256
`156d5df0c51f94af9442f49b1c1e395117e8e95d54ac3c30fb98bd5ca65d973d`.

Observed engineering-smoke outcome:

- `OUTBOUND -> HOLD -> RETURN -> COMPLETE` in 4.810 s;
- 202/202 MPC solves reported `SAFE_ACTION`;
- 962/962 low-level filter evaluations reported `SAFE_UNCHANGED`;
- zero force-gate, BRAKE, structural, or MuJoCo warning events;
- Goal-MPC runtime 18.180 ms mean, 19.156 ms p95, and 37.426 ms maximum;
- 2/202 solves exceeded the 20 ms period.

This supports the deterministic matched engineering baseline and a p95 runtime
checkpoint. It is not a hard real-time or WCET certification, a hardware safety
claim, an interface-mismatch result, or a learning result.

## Evidence retention policy

Full traces, figures, repeated failed-run outputs, and intermediate profiling
attempts remain local under the ignored `results/` tree. They are not deleted.
Only the reviewed compact final summary is intentionally tracked in this
checkpoint.
