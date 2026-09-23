# Architecture Recovery V2.2 Freeze Candidate

Status: **FROZEN FOR FRESH PHASE-2 FORMAL RETRY**

V2.2 preserves V2.1 commissioning, effective geometry, continual 11-beta
adaptation, MPC task/cost/constraints/horizon/solver, mechanics domain, and
truth firewall. It changes only the task residual representation from one
task-wide constant to a bounded linear state map.

The fixed feature vector is
`[1, q1_ROM, q2_ROM, dq1_sat, dq2_sat]`, using estimated state only.
`dq_sat = dq / (1 rad/s + abs(dq))`. A normalized-LMS update with alpha `0.20`
uses the post-beta previous-sample innovation and affects only the next action.
Each coefficient row is projected to L2 norm 12 Nm, and residual output is
clipped to `+/-12 Nm` at observed and every predicted horizon state. Beta and
residual remain separately represented and logged. The residual is
control-effective only; it is not an anatomical estimate.

The sealed development qualification is recorded in
`STATE_RESIDUAL_DEV_RESULT_V1.md`. It passed all 31 frozen gates and independent
audit. Against V2.1, V2.2 improved median/p95 RMSE by 1.86%/1.15%, completed
24/24, and produced zero events or cap hits. The effect is small: 17/24 paired
wins, 7/24 losses, and high-ROM aggregate median was 0.65% worse. No claim of
broad superiority is frozen.

Any behavioral source, feature, alpha, cap, beta cadence, observation,
controller, mechanics, task-domain, or gate change invalidates this freeze.
The next evaluation must use a fresh independently committed seed namespace and
the unchanged Phase-2 formal gates, especially the commissioning-only gate.

After development freeze, the campaign runner gained a non-behavioral
`candidate_arm` selector so the unchanged formal gate function can evaluate
`adaptive_state_residual` while retaining V2.1 as an optional diagnostic arm.
That runner/test revision is not part of the historical development source
seal. The formal retry must create and validate a new formal-execution seal over
the unchanged candidate package plus the revised runner, regression test,
formal preregistration, seed manifest, and config before case generation.
