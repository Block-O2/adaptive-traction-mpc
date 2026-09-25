# Independent runtime study audit V1

Auditor: fresh-context agent, independent of Builder reasoning. Date: 2026-09-23.
Scope: development runtime engineering only; no new scientific experiments or
production edits by Auditor. Starting branch `codex/stage5-architecture-recovery`,
HEAD `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. Existing dirty state preserved.

Audit status: PASS for the declared development runtime study scope.
Recommended terminal classification: `PLANNER_RUNTIME_QUALIFIED`.
Preserved integration status:
`FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`.

## Independently checked evidence

- Read `AGENTS.md`, frozen runtime contract, harness, scheduler, planner, adaptive
  wrapper, session clearance evaluator, production timing boundary, regression
  capture wrapper, and existing integration/time-contract tests.
- Verified SHA-256 digests of all five saved baseline/repaired production files.
  Repaired snapshots match live files. The only difference between snapshots is
  the nine-line necessary-condition rejection in scheduler `_plan`; all other
  four production files are byte-identical.
- Compared all common semantic fields of the 34 stored historical decisions
  against baseline replay, excluding runtime, with absolute/relative tolerance
  1e-10: no mismatches. This independently validates history reconstruction for
  recorded decisions rather than only trusting the paired comparison summary.
- Checked 46 paired cases: zero semantic/error mismatches, including candidate
  lists, rejection reasons, mechanics records, rankings, selected action,
  schedules, costs, and polynomial coefficient matrices. Forty-four cases return
  a decision; two retain their original no-feasible-candidate rejection. These
  rejected calls are valid runtime/equivalence samples, not successful motions.
- Verified each of the 46 cases appears exactly 12 times in the timing corpus:
  552 calls, zero >100 ms, maximum 67.652042 ms, p99 67.00969092 ms. Paired baseline
  maximum is 2671.86425 ms, with three >100 ms cases. These are measured development
  samples, not an exhaustive worst-case execution time bound.

## Root cause and profiling

Attempt 13's historical final request took 2093.989667 ms. Its saved-input
baseline repetitions took 2103.458291, 2107.075875, and 2083.883375 ms. CPU times
closely match wall time, supporting actual computation rather than incidental
process suspension as the dominant cause.

The original profile attributes 2103.235959 ms to scheduler search. Candidate
`return_dq_07` performs 1743 coefficient constructions/duration trials although
its endpoint already violates the existing task endpoint clearance floor. The
search samples both endpoints at every duration, so duration cannot repair that
particular infeasibility. Repaired code rejects it before this loop.

The wrapper calls each original function once and propagates exceptions. Nested
wrapper wall times are inclusive; self times subtract direct instrumented child
times. Line-region events, when present, are inclusive and must not be added to
wrapper totals as an independent partition. Profiling changes runtime and is
separate from all 552 unprofiled qualification calls.

The two original baseline profile files do not contain line-region events even
though the current harness contains line tracing. They support duration counts
and aggregate attribution but cannot be cited for the later line breakdown.
Builder preserved them, disclosed the initial missing harness snapshot in
`REPORT.md`, and saved separate detailed profiles and expanded provenance under
`forensics/`. The detailed baseline is 16723.5085 ms with 11727.258428 ms of
instrumented sampled-position construction; repaired detailed profiling is
218.172 ms. These much slower traced calls are diagnostic probes, not timing
qualification measurements. This distinction resolves the profiling concern.

## Repair correctness and boundaries

The new condition uses the same endpoint clearance evaluator and the same
`_path_clearance_is_valid` predicate as the original path check. It only rejects
when endpoint clearance plus 1e-9 m still fails the original floor minus 1e-12 m.
The 1 nm term is an early-rejection guard; it does not relax the eventual path
acceptance check. Inputs in that guard band still undergo the original search.
HOLD exits before the new check and retains its original behavior. Disabled
endpoint-floor mode is unchanged.

For this study's finite, bounded joint states/velocities, 10 s maximum phase,
float64 quintic construction, and smooth `SessionClearanceContract`, the guard
comfortably exceeds ordinary endpoint cancellation error. This is a local
engineering equivalence argument backed by paired outputs; it is not a formal
numerical proof for arbitrary caller-provided clearance callbacks, unbounded
custom tasks, or callbacks with side effects.
Across 288 saved baseline schedules, an independent sum of coefficient rows
differs from prescribed target positions by at most 2.220446049250313e-16 rad.
This supports the guard margin on the observed corpus only.

Auditor challenged the first roundoff test because its displacement/time budget
could fail acceleration before checking path clearance. Builder corrected the
test to use a smaller displacement at the same 0.5 nm clearance deficit and
assert that the original path predicate receives more than two samples. The
four added tests cover impossible-endpoint pruning, unchanged guard-band
acceptance, HOLD, and disabled-floor legacy behavior. Builder reports the full
targeted suite: 19 passed in 3.87 s. Auditor inspected the corrected test source
and did not duplicate that run.

No candidate truncation, duration cap, lattice change, cost change, constraint
weakening, dynamics/model change, altered optimizer, value hook, or truth input
is introduced. The selected action and mechanics checks remain identical on
the paired corpus. Session geometry comes from the saved online belief; simulator
truth is not imported into candidate generation or the added endpoint check.

The repaired profile covers 12 fixed-duration mechanics retry calls across
historical decision 05 of attempts 12, 13, and 14. It does not establish bounds
for arbitrarily long mechanics rejection searches, all interior-only clearance
failures, all nonzero-reference-velocity states, or all hidden conditions. Those
remain limitations of the qualification domain and are not silently removed.

## Timing boundary

The production stale-plan timing starts immediately before adaptive `decide` and
ends after it returns. `decision.record`, reference-boundary metadata, pending
learning-record construction, low-level execution, and final JSON/NPZ file output
are outside that interval. The regression wrapper's small request capture is
inside the production outer timer, while its inner timing measures the planner.
No regression file writes occur inside `decide`.

In the 552-call harness, maximum record serialization is 0.076917 ms and maximum
decide-plus-record is 67.679542 ms. This does not measure all application/OS
overhead. Qualification must explicitly mean planner computation under the
existing simulated planning-delay boundary. It does not certify total-loop
real-time operation, asynchronous scheduling, or physical CR12 readiness.

Regression 03 additionally captures request entry through the next first
execution-function entry, including request capture, serialization, metadata,
and pending-record preparation. Its maximum is 66.400875 ms. The capture wrapper
does not change production timing or policy. This addresses the immediate
preparation-overhead concern without claiming a bound for all application work.

## Full-3D regression and deadline fault evidence

Independently read all three nominal `run/summary.json` outputs and regression
capture code. Runs 01/02/03 are `COMPLETE`, with no stale-plan rejection. Their
maximum production planner timings are 67.487833, 66.439125, and 66.258500 ms.
Each remains a nominal development rerun, not a new held-out robustness case.
Runs 01/02 preserve 242 continual adaptation updates and nine accepted beta
updates, continuous reference boundaries, no shank-bed contact samples, and
TRACK-only execution. Bed-thigh support contacts remain present (108/104 samples
in 01/02); they must not be summarized as no contact of any kind.

The separate injected-delay diagnostic retains its failed episode:
151.920792 ms, `ABORTED`, `STALE_PLAN_MAXIMUM_AGE`, and the rejected decision
record. Thus the 100 ms stale-result guard remains active. This is an expected
fault-injection outcome, not a failed uninstrumented qualification call.

## Checks and change accounting

Auditor commands were read-only `git branch/rev-parse/status`, `cat`, `sed`, `rg`,
`diff`, and Python standard-library JSON/hash comparisons. No additional
simulation campaign was launched by Auditor. This report is the Auditor's only
file change. No parameters/configs/assumptions/scientific variables changed by
Auditor; no files staged, committed, pushed, reset, stashed, or deleted.

## Missing attempt 12 request and reconstruction correction

Attempt 12's saved terminal estimated state, timestamp, next belief sequence
521, previous executed action, and prior selected schedule independently match
attempt 13's final request context. However, the terminal trace reference was
already overwritten by the rejected plan. The first reconstruction used that
contaminated reference and produced different feasibility/schedule outcomes.
That failed reconstruction remains in `forensics/attempt12_reconstruction.json`;
it is not accepted as the historical request replay.

In `reconstruction_v2/reconstruction.json`, the request reference instead comes
from the preceding executed polynomial endpoint, and elapsed phase time comes
from repeated 5 ms addition over the saved RETURN nodes. Auditor inspected this
code and artifact: inputs, previous action, and belief agree with attempt 13;
old/new records and historical candidate evaluations have no differences at the
frozen tolerance. Baseline replay is 2070.009334 ms; repaired replay is
30.661708 ms. Thus attempt 12's computation is convincingly explained without
claiming to recover its missing original wall time. The incorrect first
reconstruction was corrected by versioned forensic work, not a production or
scientific-contract change.

## Final qualification decision

| Frozen qualification condition | Independent disposition |
| --- | --- |
| Historical/pathological outlier reproduced or explained | PASS: attempt 13 reproduced; attempt 12 corrected reconstruction documented |
| Root cause demonstrated | PASS: endpoint-infeasible candidate exhausts 1743 duration trials |
| Source repair audited | PASS: one nine-line production change, same floor predicate |
| Semantics preserved or revision validated | PASS within corpus: 46 paired cases and historical replay agree |
| Development corpus has no >100 ms calls | PASS: 552/552 within cap, including declared infeasible calls |
| Timing-aware full-3D regression completes without stale failure | PASS: three nominal runs, 13 decisions each |
| Safety, clearance, acceleration, adaptation, execution not weakened | PASS: source unchanged outside necessary-condition check; trace checks pass |
| Independent audit passes | PASS with the explicit scope limitations in this report |

Auditor also inspected the analysis code and `analysis/regression_checks.json`:
all three runs retain 5 ms task intervals/20 physics substeps, previous reference
during planning wait, activation boundaries, q/dq/ddq continuity, wrench limits,
nonnegative measured-model clearance, and active adaptation. Minimum session
clearances are 0.374537, 0.371151, and 0.489326 mm. The trace's truth-input flag
alone is not a firewall proof; this assessment additionally relies on the
reviewed source/input data flow and unchanged production-file hashes.

No unresolved blocking audit finding remains for `PLANNER_RUNTIME_QUALIFIED`
as a development planner qualification. It does not promote the broader system
status, certify varied-domain robustness, provide a global WCET bound, or prove
hardware readiness. Production timing excludes post-planner serialization;
regression 03 measures its immediate overhead separately. Simulation uses
synchronous controlled-delay replay, and the stale-abort path does not replay
the entire rejected wall wait. Those limitations remain explicit.

Recommended next step: retain this version as the qualified development planner
baseline under its declared input corpus and timing boundary.

## Supplemental function-profile and final-report review

Auditor inspected `function_profiles/profiles.json`,
`function_profiles/stage_distributions.json`,
`function_profiles/infeasible_candidate_equivalence.json`, the corresponding
archived harness, and final `REPORT.md`. No additional experiment was run.

- The function-only mode disables this harness's `sys.settrace` installation.
  All 46 input IDs are unique and present; their saved events contain zero
  line-region entries. All 46 calls remain below 100 ms. The profile still adds
  wrappers, timers, candidate-record serialization, and allocation diagnostics,
  so it remains separate from the 552 uninstrumented timing samples.
- Maximum function-profile runtime is 85.624 ms for
  `attempt_14_decision_02`, with process CPU time also 85.624 ms. One coefficient
  construction for `outbound_dq_06`, duration 0.035 s, took 13.742458 ms wall and
  13.743 ms CPU. Its subcause is unresolved; neither Auditor nor final report
  attributes it to OS noise or claims that all numerical-library outliers are
  eliminated. The larger observed instrumented maximum is explicitly retained.
- Independently recomputed counts, means, and maxima of every stage's inclusive
  per-call sums: all agree with `stage_distributions.json`. These nested sums
  overlap and are not an additive partition of planner runtime.
- Independently compared all ten old/new candidate records for each of
  `development_edge_05` and `development_edge_09`, using 1e-10 absolute/relative
  tolerance: no differences. This closes the earlier limitation that a thrown
  planner exception prevented the main paired harness from saving the complete
  candidate set for those two cases.
- Verified all hashes listed in the supplemental provenance against its archived
  files. Final `REPORT.md` distinguishes 67.652 ms uninstrumented qualification,
  85.624 ms function-only profiling, and the intrusive 16.724 s / 218 ms line
  probes. It preserves the unknown subcause, synchronous replay, excluded
  serialization, stale-abort wait limitation, and incomplete broader domain.

No new blocking finding or production repair is required. The scoped PASS and
`PLANNER_RUNTIME_QUALIFIED` recommendation are unchanged. This appendix is the
only follow-up edit by Auditor; no tests, scientific runs, or Git mutations were
repeated.
