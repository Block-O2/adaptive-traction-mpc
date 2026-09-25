# Independent prefreeze audit addendum — fresh full-3D V1 implementation

Date: 2026-09-23. Scope: read-only review of the development implementation,
draft `PREREGISTRATION.md`, and older development documents. No formal case,
held-out seed, or hidden outcome was generated or inspected. This is a
**freeze-blocking review**, not approval to seal V1.

## Blocking findings

1. **Fixed-population arm depends on a fit it is supposed to discard.**
   `runtime.py` unconditionally calls `_fit_and_replay_commissioning` before
   the `fixed_population` branch replaces the updater (lines 542–548). A
   rejected geometry fit raises at line 360, so this comparator cannot run on
   cases where its predeclared fixed prior should still be runnable. The draft
   contract says it performs the same physical commissioning motion but
   discards its fit. Keep the physical motion and observations identical, then
   construct the fixed prior without requiring fit acceptance. Preserve and
   report the fit result as evaluation/diagnostic data if computed; do not
   silently screen cases on fit success.

2. **A rejected stale plan is incorrectly counted as activated.**
   `analyze_fresh_full3d_v1.py` computes `activated_stale_plan_count` using
   `decision.record()["executed_label"] is not None` (lines 75–78).
   `HumanWaypointFeedbackDecisionV1.record()` populates `executed_label` for
   the selected candidate *before* the runtime's 100 ms activation rejection
   (`human_waypoint_feedback_mpc.py`, lines 124–139;
   `runtime.py`, lines 866–895). Thus a comparator that properly rejects a
   stale plan fails gate 4 as if it had applied it, contrary to the draft
   contract. Record actual activation/first executed interval explicitly and
   test an injected >100 ms deadline in each arm. The guard itself currently
   rejects before `pending` activation; this is an analyzer/trace semantics
   defect, not evidence that the controller applied a stale plan.

3. **Formal case bytes are not bound to the sealed seed or paired arms.**
   `generate_fresh_full3d_cases_v1.py` saves accepted and proposal canonical
   digests, but `run_fresh_full3d_batch_v1.py` checks only the
   `generation_summary.json` *file* hash at restart (lines 48–72). It does not
   compare `generation_summary.seed` with `SEED_MANIFEST.json`, recompute the
   accepted-case digest from `cases/*.json`, or verify the proposal ledger.
   A case file can change between arms while retaining the same key, and the
   resume path overwrites the earlier `case_sha256` in checkpoint entries
   (lines 75–91). Require a pre-run all-case/ledger integrity check and
   reject any case hash mismatch with the first arm and sealed manifest on
   every restart. A development bundle must never be accepted as formal merely
   because it contains 24 distinct keys.

4. **Freeze manifest omits a live compiled execution dependency.**
   `freeze_fresh_full3d_v1.py` includes only `src/**/*.py` from each stage
   (lines 22–35). The worktree contains both
   `src/traction_mpc_stage5/_prefix_native.c` and
   `_prefix_native.cpython-310-darwin.so`. `controller_interface.py` imports
   that extension when available and resolves `prefix_backend="auto"` to
   native (lines 30–34 and 806–809). This can affect candidate-screen
   computation and the 100 ms timing result. Hash and record the source and
   binary actually loaded, its platform/ABI and resolved backend, or force a
   reviewed deterministic backend for all formal arms. A Python-only manifest
   is not a complete source/asset freeze here.

5. **Primary paired RMSE does not compare a common trajectory.**
   The analyzer compares each arm's true q against that arm's own
   planner-selected `q_ref`, then declares a ≥10% adaptive effect on jointly
   complete cases (lines 47–50, 152–166, 202–207). All arms share endpoints
   but choose potentially different waypoint counts, durations and paths.
   Lower own-reference RMSE can result from easier/slower planning without
   improved common-task performance. The draft calls this a meaningful
   adaptive-versus-baseline improvement. Before freeze, either define the
   primary claim narrowly as *own-reference tracking* and add common-task
   completion time/terminal error/effort gates, or preregister a common
   task-progress metric that cannot reward arbitrarily slow trajectories.
   Report own-reference RMSE and physical force for every arm regardless.

6. **Analyzer gate 1 is weaker than the stated provenance/truth firewall.**
   It accepts 72 rows including `RUNNER_EXCEPTION` and trusts
   `summary["truth_firewall"]["human_q_dq_truth_in_controller"]`, which the
   runtime writes as a constant `False` (analyze lines 186–191; runtime lines
   1075–1080). No code/data-flow check, frozen-hash check, seed/case pairing,
   or case-specific source manifest is performed by this gate. Gate 4 later
   rejects runner exceptions, but this does not make gate 1 a provenance
   check. Separate machine-checkable artifact integrity from independent
   source audit; do not promote a self-asserted JSON boolean as firewall proof.

## Additional issues to resolve before seal

- `TruePhysicsMonitor` is called after each 0.25 ms plant step, and source
  inspection supports a physical CR12 torque → compliant interface → Human
  path (`runtime.py`, lines 305–330). It starts TASK monitoring only after
  commissioning (`runtime.py`, lines 600–605), without scoring the exact task
  start boundary. A handoff abort can therefore have no TASK physics samples;
  the analyzer's `minimum_true_clearance_m is not None and <0` treats missing
  physical clearance as no safety violation. Record the stage-transition
  boundary and make missing required monitor data an explicit failed/unknown
  gate, while retaining zero-interval handoff failure in the denominator.
- The true-monitor ROM gate is physics-step-level, but realized cuff peaks and
  actual acceleration gates use 5 ms boundaries. This is allowed if stated
  precisely; do not imply that every hard limit was evaluated at 0.25 ms.
  Add an explicit precision table to the contract and analyzer report.
- The draft promises the “final-ten-update beta-step distribution”; analyzer
  takes the final ten *20 ms adaptation rows*, most of which are non-beta
  updates (`analyze_fresh_full3d_v1.py`, line 129). Select the final ten beta
  attempts or accepted changes as declared, and name which one. Preserve all
  attempts and rate-limit flags including rejects.
- The paired 24-case generator uses static true clearance at 21 straight-line
  interpolation samples and CR12 start/goal IK only (`domain.py`, lines
  95–130). This is a legitimate pre-outcome *conditional* filter, not dynamic
  feasibility, future waypoint reachability, or commissioning safety. The
  draft already makes that limitation mostly clear. Freeze exact tolerances,
  handling of an IK exception, and the complete proposal ledger; never
  replace accepted cases after an arm result.
- `fixed_population` still uses the common nominal `SessionClearanceContract`
  while fitted arms use fitted geometry; this is an intended information
  difference, but the clearance source string currently always says
  `ONLINE_EFFECTIVE_GEOMETRY_CONSERVATIVE_SHANK_SET` (`runtime.py`, lines
  554–562), even for the fixed prior. Correct provenance labels without
  altering the constraint function or safety threshold.
- The result analyzer reports task force/tracking separately from physically
  executed commissioning, as drafted. Preserve commissioning failures and
  physical costs as separate records. Reconfirm that all three arms start the
  task from the same physical state; the fixed arm must not alter commissioning
  control or reset the plant when discarding belief.

## Already supported by source, subject to final regression

- The new `HiddenHumanV2` properties feed segment length, mass, COM, inertia,
  passive stiffness/damping/rest and sleeve lever into MuJoCo XML. The CR12
  sensor-boundary constructor now forwards a case-specific `Stage5Geometry`.
  There are still fixed placement dimensions and a fixed physical interface,
  as declared. No independent full shank versus cuff-fraction identification
  is claimed.
- The online nominal model is constructed before hidden plant use; the hidden
  Human/placement objects are passed to plant initialization, while later
  control uses robot/cuff measurement and fitted or fixed belief. This looks
  directionally consistent with the truth firewall. A final source/data-flow
  guard is still required because the result's firewall flag is declarative.
- The 4×3×2 key design and fixed maximum of 30 proposals per cell implement
  the stated case count and blocking rule. The 0.46 m structural shank bound
  exceeds the generator's maximum physical shank length, but positive
  deployable clearance across the resulting trajectories is a separate
  outcome, not a generation promise.

**Disposition:** Do not freeze or generate formal seeds yet. The Builder can
repair these within development V1, run focused nonformal checks, and request a
second independent review. This addendum changes only a new versioned audit
document; it does not alter controller code, scientific parameters, old
artifacts, Git state, or hidden cases.

## Subsequent source check during development

The Builder changed files while this independent review was in progress. A
targeted re-read confirms findings 1, 2, and 4 have source-level repairs:
`fixed_population` now bypasses fitting and records `NOT_ATTEMPTED`; the
runtime records `plan_activated`/null rejected activation timestamp and the
analyzer uses that field; the freeze walker now includes all files under
`src/`, including the native C source and `.so`. These are **code-inspection
dispositions**, not executed regression or final freeze approval. They should
be checked with focused development tests before sealing.

Finding 3 is only partly repaired at this point. The batch now recomputes the
accepted-case canonical digest, verifies per-case bytes during execution, and
checks earlier arm case hashes. It still does not verify that the bundle's
`generation_summary.seed` equals the sealed `SEED_MANIFEST.root_seed_uint64`,
or bind/check the proposal ledger digest. Consequently a self-consistent
development-seed bundle remains admissible to the formal batch entry point.
This is a remaining freeze blocker.

One further evidence-label problem remains: `run_executed_case` marks any
`qualification_case` result as `fresh_full3d_qualification` regardless of
whether the caller is the development single-case CLI or the frozen formal
batch (`runtime.py`, lines 1100–1125). The single-case CLI has no freeze/seed
validation. Give development and formal outputs distinct machine-readable
evidence categories and ensure the formal label is possible only under the
sealed batch contract. Prior development outcomes remain development evidence.

After that read, the Builder added seed equality, proposal-ledger integrity,
and full deterministic regeneration from the sealed seed to the formal batch.
The batch now passes `formal_qualification=True`, whereas the development
single-case CLI uses the default `False`; the analyzer checks the formal label.
These source changes resolve finding 3 and the evidence-label issue at the
code-inspection level, subject to focused regression. The Builder also revised
gate 7 and the draft preregistration to compare paired **task completion**
rather than each arm's endogenous reference RMSE. This resolves finding 5's
causal metric concern at the contract/source level. Own-reference tracking is
now secondary paired evidence. No formal data were used in these revisions.

As of this addendum's latest read, two smaller but real contract/analysis
mismatches remain: the beta-step “last ten” array still selects the last ten
20 ms adaptation records rather than the declared beta updates, and a task
handoff with no integrated TASK step still yields null true clearance that the
safety check does not classify as missing. The self-asserted truth-firewall
boolean also still requires the separate independent source audit promised by
gate 1; it cannot itself discharge that gate.

There is also a distinction between *accepted for activation* and *actually
activated*: the new `plan_activated` value is assigned immediately from the
measured-delay ≤100 ms predicate, before any interval of that plan executes.
An abort while advancing physics under the preceding reference can leave it
`True` with a predicted `activation_timestamp_s` but no active-plan interval.
The >100 ms rejection is correctly marked `False`; nevertheless the trace
should record the actual first execution boundary separately and the analyzer
should use that record for activation claims.

## Final pre-freeze review: unresolved watchdog-physics boundary

The later development revision now records actual first physical activation,
monitors the TASK handoff boundary, takes final-ten beta steps from actual
attempts/acceptances, separates fixed-arm clearance provenance, verifies the
seed/proposal/case bundle by regeneration, and locks resume to the seed
manifest and Git HEAD. These are source-level repairs of the prior findings;
the targeted development tests and nominal outcomes remain development-only.

One new **freeze blocker** remains. In `runtime.py`, after timing a planner
request, the `simulated_delay_s > 0.100` branch immediately calls
`abort_episode(..., "STALE_PLAN_MAXIMUM_AGE")` and `continue`s, before any
`_execute_interval` advances the old reference under physical MuJoCo time.
Accepted plans do replay physical time under the old reference. As written, a
missed-deadline arm stops at the request boundary, skipping the physical
plant/safety trajectory up to the 100 ms watchdog. This contradicts the
current qualification's no-pause-the-world timing requirement for all paired
arms; gate 4 allows comparator deadline misses, so adaptive zero-miss cannot
make those comparator episodes physically time-aligned. Disclosure of this
historical limitation in the preregistration is necessary but insufficient
for the stated execution contract.

Repair within development V1 before freeze by physically executing the
registered prior/current reference through the unchanged 100 ms watchdog,
then rejecting the stale plan and aborting. Do not activate the stale plan,
extend the threshold, or retrospectively replay the full multi-second solver
wall time. A nonformal injected >100 ms test should verify 20 actual 5 ms
intervals (400 MuJoCo substeps at 0.25 ms), plant/clearance trace coverage,
`plan_activated=False`, null actual activation timestamp, and preserved
deadline failure. Reconcile the preregistration wording with the repaired
watchdog semantics, then request a final Auditor check. No formal seed has
been generated or held-out outcome inspected in this audit.

The same timing omission also appears in the caught `ValueError` from
`adaptive_planner.decide`: the `NO_FEASIBLE_WAYPOINT` branch exits before
measuring/recording planning runtime or replaying any prior reference. This
may be a normal physical-domain failure, not an infrastructure exception, so
it needs the same bounded watchdog-time physics/provenance treatment (or a
source-backed proof that the path cannot occur in this qualification).

## Subsequent watchdog-path repair review

The Builder subsequently added `planning_wait` for both failure paths and
changed the preregistration accordingly. Source now holds the previous
reference through actual `_execute_interval` calls up to the unchanged
100 ms watchdog for a stale result, or through the measured 5 ms-quantized
compute delay for a sub-deadline infeasible result. It logs actual interval
count and leaves rejected `plan_activated=False` with null actual activation
time. A development-only injected stale result produced `ABORTED`/
`STALE_PLAN_MAXIMUM_AGE`, 20 physical 5 ms intervals, 400 MuJoCo substeps,
21 task boundaries and a non-null task true clearance. A development-only
infeasible result produced its distinct `NO_FEASIBLE_WAYPOINT` abort after
7 intervals/140 substeps/8 boundaries for a measured ~30 ms plan. Independent
parsing of both artifacts with the current analyzer returned valid N/N+1
alignment: deadline/infeasible counts were respectively (1, 0) and (0, 1),
with zero stale activations. The new analyzer does not misclassify a fast
infeasible plan as a deadline miss. The two focused V1 test directories yield
14 passing tests.

**Disposition of this blocker:** PASS at source and development-artifact
level. Overall freeze approval remains conditional on the Builder's normal
nominal regression and final dependency/gate seal; this audit has neither
generated a formal seed nor inspected any held-out result. A minor learning-
transition provenance item remains: `selected_plan_activated` in two pending
transition flushes is inferred from `end_time >= start_time`, not from the
actual `decisions[].plan_activated`. Gate 4 correctly uses the latter; align
the ancillary field if later activation claims will cite learning records.

## Final development regression and freeze disposition

The Builder aligned both learning-transition flushes to their recorded
`decision_index` and its actual `plan_activated` field. Independent parsing of
`development_nominal_05` found 13 learning records and 13 decisions, all 13
activated in both records, with zero mismatches. The post-watchdog normal
nominal run is `COMPLETE` with 974 executed 5 ms intervals/975 aligned task
boundaries, 13 actual plan activations, zero deadline misses, 0.640 deg
combined q RMSE, 1.408 deg q absolute p95, +6.59 mm minimum TASK true
clearance, and no TASK shank-bed contact or Human ROM violation. The focused
V1 test directories yielded 14 passes after the timing repair.

Important negative development evidence: the same nominal run's combined
task dq RMSE is **7.903 deg/s**, above the draft formal gate 5 limit of
5 deg/s. Earlier development nominal runs 03/04 are likewise ~7.90 deg/s.
This creates a substantial risk that the fresh qualification will fail gate
5. The numeric gate is deliberately *not* loosened in response to this
development result; a formal failure must be preserved as such.

**Final pre-freeze Auditor disposition: PASS for freezing the present source,
config, domain and preregistered gates.** This means the protocol is ready to
seal, *not* that qualification is likely to pass or that hardware real-time,
large-ROM, clinical or arbitrary 3-D robustness has been shown. The
independent Auditor must inspect the completed freeze manifest before
creating a fresh sealed hidden seed, then later audit every formal result
without changing V1. No formal seed or held-out outcome was generated or
viewed during this pre-freeze review.
