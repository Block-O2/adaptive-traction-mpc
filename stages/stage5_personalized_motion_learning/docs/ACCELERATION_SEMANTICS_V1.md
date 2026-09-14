# Stage-5 acceleration-semantics checkpoint

Evidence category: targeted engineering audit and one matched engineering
smoke. No controller architecture, cost, action space, Plant-v1 parameter,
motion-envelope value, HOLD gain, Safety Filter/BRAKE rule, or force gate was
changed.

## Registered meaning

The registered `[300,600] deg/s2` envelope was derived from sampled Human
motion data, while Goal-MPC constrains the change in predicted Human velocity
over each 20 ms prediction step. It is therefore now explicitly interpreted
as a 20 ms interval-acceleration limit, not an instantaneous MuJoCo `qacc`
limit.

The three quantities are separate:

- MPC predicted acceleration: predicted `dq` change over the future 20 ms MPC
  interval; this remains the candidate hard-constraint quantity.
- deployable realized acceleration: causal time mean, over the trailing 20 ms,
  of fixed-Human-model `qdd(q_hat,dq_hat,tau_measured)`, where `tau_measured`
  comes from the same-timestamp measured physical wrench about the Human cuff;
  this is the online monitoring authority.
- evaluation-only truth acceleration: Human truth `dq` change over the same
  interval; it is never passed to control.

Before 20 ms of history exists, the monitor uses every causal sample since
episode start. No sample or startup period is exempt. Instantaneous model
acceleration and MuJoCo `qacc` remain logged diagnostics but are not compared
against this interval-defined task envelope.

## Saved-trace audit

The diagnostic replay exactly reproduced the prior 45 ms failure trace; the
maximum finite numeric difference was `0.0`. The old 5 ms endpoint interval
showed:

| quantity | q1 | q2 |
|---|---:|---:|
| deployable dq-difference | 247.12 | 665.71 |
| causal model mean over the same 5 ms | 133.75 | 372.15 |
| evaluation truth over the same 5 ms | 166.98 | 511.41 |

Thus the old q2 abort was a false interval-limit violation caused by
differentiating the interface-aware velocity estimate over one 5 ms sample.
On the unified trailing 20 ms semantics, saved-trace peak model/truth values
were `[67.01,155.78]` and `[74.39,189.00] deg/s2`; neither violated the
unchanged limits. Exact synchronized evidence is in
`results/acceleration_semantics_v1/saved_trace_audit_v2/`.

An intentionally retained intermediate instantaneous-monitor diagnostic
showed why instantaneous `qdd` was not adopted: at 45 ms the model estimate
and evaluation-only MuJoCo `qacc` reached q2 values of `670.70` and
`735.09 deg/s2`, although their interval accelerations remained within the
registered data-derived envelope. That diagnostic is not promoted.

## Matched episode

The only full matched episode is retained at
`results/acceleration_semantics_v1/matched_attempt_01/`. It did not complete:

```text
OUTBOUND 0.000 s -> ABORTED 0.445 s (NO_SAFE_ACTION)
```

Acceleration semantics passed throughout:

| 20 ms acceleration peak | q1 | q2 | limit satisfied |
|---|---:|---:|---:|
| MPC predicted | 221.79 | 482.86 | yes |
| deployable realized | 205.30 | 464.35 | yes |
| evaluation-only truth | 206.62 | 540.77 | yes |

The active blocker is not acceleration monitoring. At the final solve, all 64
first actions passed executable/force screening, but both 32-candidate horizon
populations had zero task-velocity-feasible candidates. Their best velocity
margins were `-0.6158` and `-0.4784 rad/s`; only 3/32 and 2/32 candidates were
independently acceleration-feasible. The measured terminal speed was
`[27.50,55.53] deg/s`, inside `[45,75]`, but the current prediction/sampling
set could not find a trajectory that remained inside the future velocity
envelope. This evidence identifies the current algorithmic blocker but does
not prove that the physical task is infeasible under a different controller.

Other observed metrics:

- peak/cumulative cuff force: `137.23 N / 49.0169 N s`;
- peak cuff moment: `18.693 Nm`;
- interface translation/rotation: `5.442 mm / 3.286 deg`;
- q peak estimation error: `[0.00984,0.02060] deg`;
- dq peak estimation error: `[0.4749,0.8107] deg/s`;
- Goal-MPC mean/p95/max: `24.927/27.532/27.680 ms`;
- 88 Safety Filter results were `SAFE_UNCHANGED`; the supervisor entered BRAKE
  once because of `NO_SAFE_ACTION`;
- zero physical-force-gate, Safety Filter intervention, structural event, or
  MuJoCo warning.

HOLD and completion-margin behavior were not exercised. The formulation still
contains no full prescribed q trajectory, coordination ratio, or path
corridor; the observed early-path normalized q1/q2 progress difference reached
`0.1818`. The deterministic controller is not ready to freeze or proceed to
interface mismatch.

## Reproduction

- exact prefix replay:
  `run_goal_mpc_smoke(... maximum_duration_s=0.05, record_selected_horizon_diagnostics=True ...)`;
- audit:
  `python scripts/audit_stage5_acceleration_semantics.py`;
- full matched smoke:
  `run_goal_mpc_smoke(... record_selected_horizon_diagnostics=True, use_loaded_local_hold=True, use_bumpless_return_handoff=True ...)`;
- Stage-5 tests: `59 passed`;
- inherited Stage-4 allocator/Safety Filter/BRAKE regressions: `17 passed`.
