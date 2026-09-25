# Human-waypoint planner runtime study V1

Development runtime engineering; 2026-09-23.
Final status: **PLANNER_RUNTIME_QUALIFIED**, restricted to this development corpus.
Preserved system status: `FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`.

## Scope and frozen contract

This study preserves the existing task, six-axis CR12 MuJoCo plant, cuff model,
effective geometry/beta/residual updates, ROM, speed/acceleration/wrench limits,
clearance policy, event-driven phases, action lattice, costs and exactly-zero
value hook. The 100 ms stale-plan cap is unchanged. No new varied qualification,
large-ROM expansion, RL, hardware actuation or Git publication is performed.
The preregistered engineering contract is `configs/full3d_adaptive_integration_v1/runtime_study_v1/contract.json`.
All results below belong to `results/full3d_adaptive_integration_v1/runtime_study_v1/`.

## Root cause and historical replay

The original attempt13 decision10 records 2093.989667 ms around
`AdaptiveHumanWaypointHWMPCV22.decide`, excluding subsequent `.record()`
serialization. Its full deployable state, emitted reference state, phase times,
belief sequence 521, geometry, beta, residual weights, and previous action are
available. No hidden Human state is needed. Historical input reconstruction is
in `baseline/inputs.json`, with source hashes. Replay three times on the current
environment took 2103.458291, 2107.075875 and 2083.883375 ms. Corresponding CPU
times were 2103.171, 2106.908 and 2083.750 ms. This is demonstrated computation,
not an attribution to OS scheduling noise, cold import, or serialization.

Request: RETURN, elapsed 1.285 s, remaining 8.715 s, ten direct Delta-q
candidates. State is `[0.18303704806415008, 0.35003793707019704,
-0.03478728720678095, -0.013517906976187441]` in rad/rad/s. Reference is
`[0.1860434573160361, 0.3498828364209239, 1.7763568394002505e-15, 0]`.
`return_dq_07` targets `[0.1306771705043202, 0.26277147447048055]` rad.
It passes the early zero-clearance check but violates the later positive
task-endpoint clearance floor. Every interpolating trajectory includes that
endpoint, regardless of duration. Nevertheless, the original scheduler tries
1743 durations (5 ms through 8.715 s), checking increasingly many sampled
points for a candidate which cannot pass. The initial profiled call spends
2077.700334 ms on this candidate of 2110.521459 ms overall. No mechanics
screen is reached for this candidate. Selected feasible action remains
`return_dq_08`, but is rejected as stale by the execution wrapper.
The problematic endpoint clearance is +0.342941 mm; its required floor is
+1.988810 mm. Increasing duration cannot bridge that positional deficit.

For that candidate the nested profile records 1743 extrema evaluations,
1743 causal-acceleration evaluations, 1694 failed path-floor checks, and
3389 clearance evaluations (including floor recomputation). Exclusive
scheduler work is 1683.612253 ms, polynomial extrema 182.404434 ms,
clearance evaluation 96.976569 ms, causal acceleration 70.068169 ms,
coefficient construction 33.222034 ms. Inclusive timings overlap and must
not be added together. Supplemental line profiling separates sampled-position
construction from ROM comparisons within the scheduler's exclusive work.

The complexity is approximately quadratic in the maximum trial count for
this failure: for every eligible duration n, the Python loop constructs n+1
polynomial sample objects. Classification: A (duration search), I (state and
clearance dependent complexity), with bounded candidate multiplication C.
No pathological wrench solve, candidate explosion or exceptional retry loop
caused the historical 2.094 s event. The constant polynomial linear system
does not become state-dependent or singular here. Mechanics-duration retry
exists elsewhere and remains unchanged.

Attempt12's summary records the stale abort but omits the rejected final
decision; its ten recorded planning times are all below 100 ms. Consequently
its missing call time cannot honestly be recovered. The terminal deployable
trace, last next-belief, preceding selected action and RETURN phase counter
can reconstruct its call, compared separately with attempt13. Its terminal
reference was already overwritten with the rejected candidate; the initial
reconstruction mistakenly used it and is preserved as failed forensic evidence
in `forensics/attempt12_reconstruction.json`. Corrected reconstruction in
`reconstruction_v2/reconstruction.json` uses the preceding executed polynomial
endpoint. All input/belief/previous-action values and candidate evaluations
match attempt13 at 1e-10. Replay is 2070.009334 ms before and 30.661708 ms after.
This
is reconstructed evidence, not an invented original log entry. Attempts12/13
also predate the duplicate pending-transition repair and are not training-ready
transition exports. None of their artifacts is modified.

## Minimal source repair and equivalence argument

The sole production change is in
`src/traction_mpc_stage5/human_waypoint_scheduler.py`,
`QuinticHumanWaypointSchedulerV1._plan`. After the separate HOLD path, before
enumerating durations, the scheduler tests whether either boundary is below
the existing path floor. If so, it raises the same infeasibility message as
the exhausted search. The candidate is still generated and receives the same
hard infeasibility classification; no candidate is silently dropped.

For the current smooth SessionClearanceContract and bounded task inputs,
this is a necessary condition: sampled trajectories contain both prescribed
positions. A 1 nm guard is added only to the early rejection test, so inputs
near the threshold still run the original enumeration. Original acceptance
tolerance remains 1e-12 m. This guard does not increase accepted clearance
violation, alter limits or remove an interior-path check. It is not a general
proof for arbitrary discontinuous user-supplied clearance callbacks or
unbounded numerical inputs. HOLD and the disabled-floor legacy path retain
their separate behavior. No duration bisection, assumption of monotone
mechanics feasibility, shortened sample count, or new return trajectory is used.

The 46 deterministic inputs contain every saved decision from attempts12/13/14
(34 calls), plus twelve explicitly synthetic development edge inputs. These
exercise OUTBOUND, near-goal, HOLD, RETURN, the pathological return, near-ROM
bounds, clearance rejection, and initial versus later adaptive beliefs. Existing
near-goal calls exercise the original mechanics-duration retry. Both planners
return normally on 44 inputs; two inputs are identically infeasible. Every
candidate label/action/target, hard classification/rejection, cost, zero value,
selected action, schedule duration/coefficient matrix and mechanics-screen
record matches with absolute and relative tolerance 1e-10; only timing is
excluded. Historical replays also match the saved semantic records. This is
development equivalence evidence, not a proof over arbitrary states.
The two infeasible inputs additionally have all candidate records compared
under `function_profiles/infeasible_candidate_equivalence.json`, with no
differences. These comparisons do not merely compare the final exception text.

## Runtime evidence

The paired 46-call baseline has mean/median/p90/p95/p99/max
197.611/54.788/65.153/1569.428/2662.394/2671.864 ms, with three misses.
The repaired paired calls have 39.040/48.881/64.506/65.036/65.152/65.164 ms,
with no misses. The new low-ROM edge cases expose the same endpoint-floor
failure mechanism as the historical return; these are not additional scientific
episodes.

Twelve repeats of each input in deterministic shuffled order (seed 20260923),
552 calls total, give mean/median/p90/p95/p99/max
39.643/50.513/65.573/66.405/67.010/67.652 ms. Maximum CPU time is 67.640 ms.
The worst call is `attempt_12_decision_02`. Zero calls exceed 100 ms, including
infeasible outcomes; 24 calls are repeated infeasible cases, not usable plans.
No exclusions were applied. Construction/import time is explicitly outside
`decide`, as in the actual initialized runtime; fresh process first-call timings
are retained in baseline and regression artifacts. Profiling overhead is
separated from uninstrumented timing acceptance.

This is a qualified corpus scope only, not a Python/OS worst-case bound or
hardware realtime claim. Remaining potentially long bounded searches for other mechanics-infeasible or
interior-clearance states are not globally removed by this necessary-condition
optimization. Nonzero reference-velocity and retry-exhaustion domains are not
claimed covered by this predominantly settled-segment corpus. Those limitations
must remain visible when interpreting tail statistics.

## Measurement and failure policy

`study_full3d_planner_runtime_v1.py` instruments original calls without changing
inputs or skipping checks. It uses `perf_counter_ns` and `process_time_ns`,
records nested inclusive/exclusive wall times, duration trials, candidate
results, mechanics evaluations and exception paths. Supplemental line regions
measure polynomial sampling, ROM checks, speed/acceleration comparisons, local
cost, zero-value path and ranking. The initial baseline used function wrappers;
line-region instrumentation was added later and its supplemental outputs are
separately versioned. Initial harness itself was not snapshotted; production
baseline was. Later provenance snapshots include the harness and contract.

`decide` measures algorithm wall time. `.record()` is outside that original
timer: measured maximum is 0.076917 ms; paired algorithm plus record maximum
is 67.679542 ms. This is not a total loop WCET claim. Regression03 additionally
measures request capture through the first execution-entry point, including
the runtime's preparation/serialization. Physics continues under the previous
reference via controlled synchronous latency replay rounded upward to 5 ms;
this remains explicitly non-asynchronous simulation. No task-time teleport is
introduced. Rejected stale results retain the existing abort behavior, not an
unvalidated fallback. The old abort path does not simulate the entire rejected
wall wait; that limitation is preserved rather than disguised as asynchronous
safety validation.

Infeasible candidate search is reported as `NO_FEASIBLE_WAYPOINT`; stale
decision age as `STALE_PLAN_MAXIMUM_AGE`; sampled plant safety failures retain
their existing acceleration/clearance/wrench abort reasons. A separate injected
delay diagnostic exercises stale rejection; it is a timing fault test, not an
additional controller or scientific comparison.

## Full-3D regression, independent audit and final disposition

| Existing nominal rerun | COMPLETE duration s | Maximum planner ms | q RMSE deg | Minimum clearance mm |
| --- | ---: | ---: | --- | ---: |
| 01 | 4.880 | 67.488 | 0.4897 / 0.7608 | +0.374537 |
| 02 | 4.865 | 66.439 | 0.4903 / 0.7630 | +0.371151 |
| 03 | 4.860 | 66.258 | 0.4901 / 0.7640 | +0.489326 |

All 39 decisions activate within the unchanged cap (maximum replay age 70 ms).
All three traces retain exact 5 ms boundaries/20 physics substeps, the preceding
reference during delay replay, activation boundaries, continuous q/dq/ddq,
no sampled acceleration flags, nonnegative session clearance, and wrench within
200 N / 60 Nm. Maximum observed force is 125.197919 N and moment 17.713479 Nm.
Adaptation continues with 242/242/241 task attempts and nine accepted beta updates
including commissioning. Causal estimated acceleration peaks stay below 300/600
deg/s2. Bed-thigh support contacts remain (108/104/107 samples); shank-bed contact
count is zero. This is not a no-contact or new target-domain validation claim.
Post-repair wall-time differences alter replay quantization and therefore the
closed-loop trace slightly; no controller weights or scientific configuration
were retuned to match historical metrics.

Regression03's complete request-to-first-execution-entry maximum is 66.400875 ms.
Injected 110 ms planner delay produces a measured 151.920792 ms call and expected
`ABORTED / STALE_PLAN_MAXIMUM_AGE`: zero task execution intervals, zero learning
records, and the rejected decision preserved. There are no natural deadline
misses in the declared repaired timing corpus or the three regressions.

The independent fresh-context Auditor reports PASS in `AUDIT_REPORT.md` and
checks all eight user qualification conditions. One production repair cycle
was needed. Audit prompted a stronger threshold-edge test and corrected the
attempt12 forensic reconstruction; neither changed production semantics.
Nineteen focused tests pass (3.87 s); focused `git diff --check` passes.
No fresh held-out cases were used and no hidden truth entered the controller.
The broader system status remains `FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`.

## Profiling detail, environment, and limitations

Low-overhead function-only supplemental profiles are in `function_profiles/`.
The following are inclusive per-call sums across candidates, milliseconds;
counts differ where a stage is not reached. They include measurement overhead,
are not additive across nested rows, and are separate from the 552-call series.

| Stage | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: |
| candidate generation | 0.222 | 0.283 | 0.296 |
| scheduler search | 32.679 | 55.235 | 70.137 |
| polynomial extrema | 26.851 | 40.016 | 40.743 |
| causal acceleration | 4.483 | 6.719 | 6.814 |
| clearance evaluation | 0.366 | 0.564 | 0.576 |
| fixed-duration scheduler retry | 0.779 | 0.790 | 0.792 |
| adaptive mechanics screen | 9.579 | 14.745 | 14.813 |
| inverse dynamics | 2.370 | 3.633 | 3.775 |
| wrench allocation | 3.363 | 5.159 | 5.198 |
| model construction | 0.030 | 0.045 | 0.047 |

Line-instrumented local-cost/value-default/ranking means are 0.216/0.021/0.017
ms, but with substantial global tracing overhead. Detailed line profiling
inflates the old outlier to 16.724 s and the repaired historical call to 218 ms;
these are intentionally intrusive offline diagnosis, never activated plans or
deadline acceptance samples. `analysis/stage_distributions.json` is explicitly
this line-instrumented series; `function_profiles/stage_distributions.json` is
the lighter function-only series. Per-candidate records include duration,
trial counts, scheduler/mechanics/total time and rejection stage.

The largest supplemental function-profile call is 85.624 ms
(`attempt_14_decision_02`), including a 13.742 ms coefficient-construction
invocation. Its CPU time matches wall time. Its subcause is not established and
is not labeled OS noise; it stays below the unchanged deadline. The actual
uninstrumented qualification maximum remains 67.652 ms. No global claim that
every numerical-library or OS outlier is eliminated is justified.

Existing mechanics retry evidence includes a 439.209 N predicted-force rejection
and eventual 101.704 N acceptance for historical outbound decision05. The
21-sample mechanics screen, force/moment thresholds and duration retry are all
retained. Allocation denominators and exception records are saved; the root
outlier never reaches allocation. NumPy's coefficient system has constant
condition number 524.277, not a RETURN-dependent singularity.

Environment: macOS 26.6.2 ARM64, conda `mpc_learn`, Python 3.10.20,
NumPy 2.2.6, MuJoCo 3.10.0. No JIT is used in this planning path. Initial
Matplotlib font-cache setup occurred during imports, outside measured planner
calls; it cannot explain repeatable same-input 2 s CPU work. Other Python,
library, machine-load or hardware environments require their own timing evidence.

## Files, reproducibility and Git

`COMMANDS.md` records invocations; `CHANGED_FILES.md` lists the study allowlist.
Result directories refuse overwrite. Historical attempts11--14, negative
baseline timings, failed forensic reconstruction and injected deadline failure
remain intact. Baseline and repaired source/config/environment snapshots,
inputs, full profiles, comparisons, timing repetitions, regression traces and
artifact hashes are preserved. The initial missing profiler-source snapshot
is disclosed above; later snapshots include all study harness code.

Starting and ending branch is `codex/stage5-architecture-recovery`, HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. The index remains empty. No staging,
commit, push, reset, stash, branch switch or deletion occurred; unrelated dirty
Stage4/Stage5 assets remain local. The source correction is nine added lines
relative to the campaign-start working file, not the entire pre-existing HEAD
diff. No scientific variable, parameter, model assumption, task or acceptance
threshold changed; only engineering instrumentation/configuration was added.

Exactly one recommended next step: preregister a fresh varied full-3D
qualification study using this audited runtime version. Do not treat this
engineering corpus as that study's held-out evidence.
