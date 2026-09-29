# Zero-value continuous session contract v1

## Scope and frozen inputs

This is one scientific-simulation session of exactly three repetitions of the
registered low-ROM ordinary case `balanced_ordinary_r01.json`. Its case SHA-256
is `ceb33e9eeb243d49ad4bd1ad0a17637243219f3e058f4da0aaf2ed9fbf975b2d`.
The execution options are the existing
`incremental_clearance_terminal_v9.json`; task, controller mathematics, Human
dynamics, planner objective, IK, scheduler, safety limits, and scorer-v2 retain
their frozen meanings. Execution mode is `SCIENTIFIC_SIMULATION`, host delay is
0 ms, and the registered deterministic IK seed is 20260918. No extra case seed
is supplied.

The frozen WSL production source is
`85fb8f10392c20289710c78274d78bb22b01df8c`, with the 618-file
fingerprint
`56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`.
The pre-smoke remote branch HEAD is
`b2a8d3bb8716859bd3cad9f7e834b8f02112658f`. New source files and the
runtime orchestration change have separate SHA-256 values in each
`session_provenance.json`; the frozen fingerprint is a baseline identity, not
a claim that the modified worktree still has the same fingerprint.

## Session and repetition boundary

One Python process owns one session identity. Rep 1 performs the established
physical commissioning and one OUTBOUND → HOLD → RETURN task. Rep 2 and Rep 3
must begin from the previous completed native MuJoCo boundary, with the same
physical plant object, monotonically increasing simulation time, the same
Human belief updater, and the same causal observer. They must not rerun
commissioning, reset the Human belief, or reinitialize the physical plant.
Each repetition gets a distinct episode epoch and output directory.

The explicit carryover allowlist is: physical plant, measurement layer, causal
observer, cuff allocator, last committed command and its actual source/receipt
metadata, startup alignment calibration, and command-response estimator
history. The updater and fit are owned by the outer session context. Their
object identity, version, and content are recorded at the boundary.

Every repetition creates fresh task phase/dwell/arrival state, planner and
schedule, reference history seeded at the registered start target, supervisor,
split monitor, acceleration authority, scientific physics epoch, planning
lifecycle, physical scorer monitor, task decisions, safety counters, terminal
state, trace, and per-repetition metrics. Prior plan requests/results,
activation hooks, return projections, and trajectory history are excluded by
an explicit state allowlist. The previous terminal command is retained only as
the actual held physical input until the next committed command; it is not a
new plan or reference.

## Zero-value policy and data

RL is OFF; no learner is constructed or trained. The existing baseline
waypoint policy makes every decision. For every decision, retain the complete
candidate set, feasibility, existing short-term/model-based cost terms,
baseline selected label, executed label, and selection provenance. The
learned long-term contribution is 0 for evaluated candidates. A candidate
rejected before scoring may have a null `future_value` field; this denotes
*not evaluated*, not a nonzero learned contribution.

## Primary measured interaction cost

`J_F(rep) = Σ[i=0..N-1] ||F_cuff_measured(t_i)||₂ (t_(i+1)-t_i)`.
The source is the saved task-boundary **measured physical cuff force** in
`trace.npz`, the timebase is MuJoCo simulation time, and the integration is
a left Riemann sum over executed control intervals. The terminal boundary
sample has no following interval and contributes no area. The same rule
records cumulative measured moment; peak force/moment include every task
boundary sample. The saved `summary.json` force integral and interval count
must agree with an independent trace calculation.

## Gate and stop rule

Deterministic reset/persistence/no-leakage, synthetic cost, zero-value logging,
and standalone single-repetition checks precede the dynamic session. All three
repetitions must be COMPLETE with OUTBOUND/HOLD/RETURN, physical PASS,
scientific PASS, raw scorer-v2 PASS, finite states, valid safety metrics,
continuous physical boundary, and monotone persisted Human model versions.
Only if the first three-repetition group passes may an identical second
session be used for repeatability. A failed first group is preserved and is
not rerun to seek a pass. No 30-repetition baseline or RL work is authorized
by this contract.

## V2 observed outcome

The fresh `session_smoke_02` group stopped after Rep1 completed. Rep2 failed in reference-history setup because the resumed path passed an extra acceleration vector to `AppliedReferenceMotionHistory`. Neither cross-repetition boundary was validated and repeatability was not run. This is a failed validation, not a revision of the session contract; see `3REP_SMOKE_REPORT_V2.md`.
