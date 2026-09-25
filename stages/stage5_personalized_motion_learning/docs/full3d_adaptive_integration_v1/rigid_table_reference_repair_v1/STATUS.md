# DEV-D restart status

Phase: COMPLETE. Terminal status: `REFERENCE_REPAIR_PARTIAL`. No fresh qualification started.

Branch: `codex/stage5-architecture-recovery`; starting HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. The pre-existing dirty
working tree, previous rigid-table v1/v2 results and older formal failures
must remain untouched. No git staging, commit, push, reset, stash or switch.

Established input: rigid-table assembly v1 broad22 gave 22 commissioning,
22 task entries, 5 complete; geometry-only v2 supplemental1 commissioned,
entered recovery and aborted before task. All 23 physical traces had zero
thigh–table native contact force, but a v2 sleeve sampled-path overlap reached
−3.132480 mm. Eight v1 planning calls exceeded the unchanged 100 ms rule and
failed closed. One old24 case remains initial-assembly-invalid. These are
development outcomes, not fresh qualification.

Completed: evaluation-only aligned reference/physical trajectory diagnosis;
an opt-in deployable hard-table path envelope for commissioning and the
existing recovery/task planner; feedback-driven commissioning targets; focused
unit tests; several versioned, preserved representative CR12–cuff–Human runs.
The old requested shank path goes below the table in two representative cases.
The repaired middle and ordinary cases completed, with planned and physical
shank/sleeve margins positive. A near-upper case with only ~0.1 mm initial
sleeve gap still physically crossed the table at 0.035 s despite an upward
planned segment, and another near-upper case later failed the existing 100 ms
stale-plan rule. The nominal case later aborted on the retained conservative
session shank-clearance monitor during RETURN despite positive true shank gap.
These are distinct remaining mechanisms, not a single reference-path failure.

Latest representative snapshot `representative_final_v1` preserved 5 real
physical results: one measured sleeve penetration at 0.035 s before
commissioning completion; three physically completed commissioning/recovery
but later aborted (stale-plan, task velocity, old session clearance); one
completed full task. The near-upper sleeve event is a measured execution/
initial-support boundary even though its new requested segment raises the
limb; the old requested-path penetration was separately reproduced. Six
focused new geometry tests pass. The source remains opt-in DEV-D, not formal.

`broad_development_v1` finished 23/23 physically executed: 21 commissioned,
21 entered task, 5 complete; 2 measured sleeve penetration aborts, 11 stale
task aborts, 3 no-feasible-waypoint, 1 task velocity, 1 retained session
clearance abort. All thigh/shank native contact peaks were zero. The 21
complete trace artifacts had no sampled requested/actual shank/sleeve negative
geometry; the two sleeve aborts are separately preserved with native interval
traces. This batch uses the pre-audit path checker and must not be conflated
with the later strict-path revision.

Independent Auditor found a real gap: recovery/task scheduler sampling lacked
continuous intersample certification, and its optional endpoint floor could
be negative if a phase goal predicted below table. A strictly opt-in DEV-D
revision now clamps the path floor to zero and requires the combined envelope's
1201-sample derivative-root lower bound in every recovery/task fixed or
duration-searched quintic. Nine focused geometry/scheduler tests pass.
Final strict representative and `broad_strict_v1` physical replay completed.
The strict 23-case batch yielded 21 commissioning/fit/recovery/task entries,
5 full completions and 18 failures (11 stale, 3 waypoint infeasible, 2
velocity, 2 measured sleeve geometric overlaps). All 23 native thigh/shank
contact monitors remained zero, but the sleeve is a separate excluded-contact
analytic geometry and crossed the table in two cases. The strict continuous
reference certificate and nonnegative task floor were independently source-
audited. Final Auditor review supports PARTIAL, not validated. Final report,
plots, V3 corrected aggregate and V2 dependency hash manifest are complete.
35 focused tests pass, JSON and diff/whitespace checks pass. Current branch and
HEAD unchanged; no Git staging/commit/push/reset/stash/switch/deletion.

Do not resume DEV-D as if unfinished. The next authorized task, if requested,
should target the first physical narrow-gap sleeve execution divergence;
the 100 ms task-planner tail remains separately unresolved. Preserve this
versioned package and all unsuccessful development attempts.
