# Independent fresh-context audit — Full-3D startup DGN V1

Date: 2026-09-23. Initial decision: **FINDINGS** (four bounded evidence/decision
wording issues below). This is a diagnostic-report audit, not controller
qualification. The historical formal result remains
`FULL3D_FRESH_FAILED_WITH_EVIDENCE`.

The Auditor independently read repository `AGENTS.md`, the original attached
user task, the Builder documents, diagnostic scripts, original formal
preregistration/report/audit, actual local source and saved numerical traces.
No Builder reasoning was supplied as evidence. The Auditor changed only this
report; no production source, configuration, historical result, Git index or
branch was changed. No physical replay or new formal experiment was run by
the Auditor.

## Verified findings

All paths below are relative to
`stages/stage5_personalized_motion_learning/` unless stated otherwise.

1. **Actual source and formal result are intact.** Independent SHA-256
   recomputation matches all **309/309** entries of
   `docs/full3d_adaptive_integration_v1/fresh_qualification_v1/FREEZE_MANIFEST.json`.
   Branch is `codex/stage5-architecture-recovery`, HEAD
   `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. The local source is newer than
   published HEAD and must continue to be identified by the manifest.
   Independent enumeration of `results/full3d_adaptive_integration_v1/
   fresh_qualification_v1/formal_paired_v1/*/*` finds 21 ABORTED physical
   episodes and three preserved pre-step exceptions in each arm: 72 records,
   zero completed formal tasks. The nominal COMPLETE comparison is a separate
   development result, not a 25th formal case.

2. **The three initialization failures are software/lifecycle rejections.**
   The preserved `runner_exception.json` files identify
   `runtime.py:236 -> human_waypoint_shadow.py:332 -> :327`:
   `ValueError: waypoint moves away from the registered phase goal`.
   `_initialize_loaded_runtime` solves the loaded CR12 IK before this call.
   `prestep_initialization_replay_v1.json` and
   `scripts/diagnose_full3d_initialization_dgn_v1.py` wrap and delegate to the
   original IK and prepare methods, confirming finite IK return followed by
   the same progress predicate. The three exceptions are not evidence of
   robot mechanical impossibility. Successful stepping after a repair remains
   untested and is properly a DEV gate.

3. **The 17 handoff misses involve real physical displacement.** Independent
   reads of the raw `trace.npz` files reproduce median maximum-joint
   true/reference error **3.84486825 deg**, pre-fit estimate/true error
   **0.39799977 deg**, and fitted-minus-pre-fit estimate jump
   **0.39932520 deg**. The final commissioning and first TASK boundaries occur
   without an intervening physical step. The source fits only after the
   physical program, immediately switches model and observer mapping, and
   applies `start_episode`; there is no active post-fit recovery interval.
   Thus geometry activation alone cannot explain the pre-existing physical
   start error. This proves the abort trigger/lifecycle mismatch; it does not
   isolate the physical cause of the preceding tracking offset.

4. **Contact load and replay consistency check out.** The two
   `contact_replay_*/diagnostic_summary.json` records agree with independent
   integration of `bed_contact_025ms.npz`. Failed balanced case: duration
   **1.085 s**, normal-force peak **91.38350656 N**, integral
   **73.46949925 N s**; nominal development comparison: **1.2495 s**,
   **119.32720291 N**, **109.79066075 N s**. Every commissioning array named
   by the replay comparison is bitwise equal to its respective baseline.
   The two different cases are not a matched intervention on contact; their
   comparison refutes contact occurrence as a sufficient failure classifier,
   not contact's possible contribution to either dynamics or identification.
   The instrumented `TruePhysicsMonitor.observe` only records hidden contact
   information. It does not return it into the controller.

5. **Fit-information interpretation is appropriately narrow.**
   `architecture_recovery_v2/effective_model.py:128-166` explicitly appends
   prior residuals and computes condition from `solved.jac`. The analytic
   data-only derivative in `diagnose_full3d_fit_information_dgn_v1.py` matches
   the fitted radial equation; the regularization scaling matches source.
   The saved result reports data-only condition **1393.0351**, augmented
   **1337.4186**, and actual fitted **1337.4188**, with nonzero data singular
   minimum **0.02278247**. It does not support a claim that regularization
   fabricated rank in this case. The 56/351 contact-overlap count concerns
   retrospective intervals; those updates occur too late to cause earlier
   commissioning motion. Contact contamination of estimates is an exposure
   mechanism, not a measured estimate-bias effect or an isolated failure cause.

6. **No-feasible is not established physical infeasibility.** The original
   `knee_dominant_middle_r02/continual_adaptive/summary.json` preserves
   `NO_FEASIBLE_WAYPOINT: ... target waypoint enters existing shank-table
   geometry (-7.746332 mm)`. `human_waypoint_scheduler.py:536-543` rejects
   negative endpoint clearance before duration search. `SessionClearanceContract`
   uses estimated hip/thigh plus fixed 0.46 m shank upper bound and 1 mm margin.
   The emitted-reference monotonic rule remains in
   `human_waypoint_feedback_mpc.py:224-242`, but this specific exception does
   not report it as the cause. The failed call records no per-candidate
   evaluations after the exception; therefore no new detailed candidate census
   should be implied. True static path clearance and executed partial-path
   clearance do not demonstrate future goal execution. The Builder correctly
   refuses to remove the bound using hidden truth.

7. **Truth firewall and inference scope are preserved in inspected paths.**
   Hidden geometry is used by `scenario.py` and runtime initialization to
   construct the physical case; nominal model and causal interface observations
   enter the observer, fit, force map and action path. Hidden Human q/dq and bed
   contact/clearance remain in trace/evaluation output in the inspected runtime
   and diagnostic scripts. This is source/data-flow review, not proof of sensor
   transfer to hardware. No fresh final seed set was generated by these DGN
   scripts. The plan keeps OUTBOUND/HOLD/RETURN completion and original limits,
   distinguishes evidence categories, and does not claim qualification PASS.

## Corrections required before audit closure

### F1 — Keep the 20/21 ordering claim at its measured sampling resolution

`aggregate_full3d_startup_dgn_v1.py` obtains contact onset from 5 ms trace
boundaries, whereas the original `TruePhysicsMonitor` saves only aggregate
substep contact counts, not first-contact timestamps. Independent recomputation
confirms **20 before / one after** at those boundaries; the smallest observed
event separation is 40 ms. However, this does not itself exclude a transient
contact between earlier boundaries in every case. Only the two replayed cases
have complete 0.25 ms contact telemetry.

Required correction: qualify the short evidence ledger and causal summary as
“first recorded 5 ms shank/bed contact” for 20/21, reserving substep first-contact
claims for the exact replayed cases. Do not silently generalize the balanced
replay's 2.48075 s onset to all 21. No additional replay is needed merely to
correct this wording; the existing evidence already supports the proposed
diagnostic distinction.

### F2 — An apparent stationary offset does not falsify every longer hold

The last 0.5 s shows very little error change in ten handoff cases, and makes
“just wait longer” an unsupported remedy. It does not mathematically establish
an asymptotic wrong equilibrium or constitute a counterfactual longer-hold
experiment. `DGN_REPORT.md` currently places an extra fixed wait in RULED_OUT;
`DEV_DECISION_PLAN.md` calls it “falsified”. Those categorical formulations are
stronger than the available finite trace.

Required correction: state “near-stationary offset over the observed final
0.5 s; no evidence that extending a fixed wait would repair it”. Keep the
bounded, state-based recovery proposal and do not run a new wait experiment
solely to defend stronger language.

### F3 — Distinguish the proposed online repair from a demonstrated necessity

The existing controller already uses measured q/dq PD feedback every 5 ms:
`human_waypoint_shadow.py::command` computes position/velocity feedback and
`runtime.py::_execute_interval` executes it through the loaded CR12 chain.
The demonstrated defect is therefore not absence of feedback. Early physical
tracking error, unmodeled contact exposure and immediate batch handoff justify
testing a continuous recovery/adaptation lifecycle. They do not yet establish
that moving **all** geometry, beta and residual updates online, plus predictive
challenger promotion, is the minimum necessary repair. Accepted geometry fit
plus failed handoff also does not prove that the geometry fit was inaccurate;
the measured fit correction is often small.

Required correction: explicitly identify the current measured-feedback path,
mark online promotion as a DEV hypothesis, and make the first DEV comparison
separate active recovery under the retained model from recovery with one
causally justified model update. Preserve physical/controller/reference/history
state for a matched comparison, or disclose unmatched reruns. Use the next
interval's measured motion/wrench and command continuity to decide which update
capability is necessary before activating the full proposed combination. This
is a sequencing/complexity gate within the one proposed DEV plan, not a demand
to implement DEV during DGN or add a general trust framework.

### F4 — Name the historical sensing/initialization assumptions explicitly

`stage4_adaptive_control/src/traction_mpc_stage4/cold_start.py:100-104`
(relative to `stages/`) initializes `OneShotHumanEstimatorV2` with measured cuff
pose and `initial_reference.q_rad`; its lines 153-164 pass
`current.bed_force_n > BED_CONTACT_CONTAMINATION_FORCE_N` as `bed_contaminated`.
The current full-3D deployment boundary has no bed-normal-force observation.
The historical comparison's general “assumptions differ” statement is correct
but insufficiently explicit for deciding which contact-eligibility mechanism
can be reused.

Required correction: disclose the known registered initial-angle anchor and
bed-force contamination input when citing that historical online-identification
mechanism. These source facts do not themselves classify the entire Stage-4
system as oracle; they do mean that its exact contact-eligibility and
initialization interfaces are not justified for the current observation set.
Keep the present prohibition on copying hidden contact truth into deployment.

## Remaining uncertainty and completion boundary

The exact split among preload/nominal inverse-dynamics error, cuff compliance,
CR12 servo behavior and later bed support is still OPEN. The two contact
replays isolate instrumentation effects, not those competing physical causes.
Live post-promotion command continuity is untested in the failed handoffs
because no post-switch physical command executes there. Contact policy and
a deployment-valid full-shank length bound require an explicit future contract;
they cannot be inferred from the hidden setup. Ideal twist and zero sensor
noise/latency remain assumptions.

These uncertainties do not require solving the controller to complete DGN.
After F1–F4 are corrected, the evidence supports a bounded DEV decision with
its first causal comparison explicit. The current STATUS text should then be
updated to name the final diagnostic status and actual audit disposition,
rather than leaving “write reports / audit pending” as the next action.

## Checks performed and scope of changes

Read-only commands included `git status --short`, `git branch --show-current`,
`git rev-parse HEAD`, targeted `rg`/`sed`/`cat` source/artifact reads, and
Python/NumPy numerical recomputation with
`/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python`. Recomputed:
309 dependency hashes, 72 outcome records, 21 adaptive contact/event-order
traces, 17 handoff median errors/jumps, both contact-force integrals and exact
commissioning array matches. Initial system Python lacked NumPy; the recorded
`mpc_learn` interpreter resolved that read-only analysis dependency.
The representative `aligned_existing_traces_v2/balanced_ordinary_r01.png`
was visually inspected; its contact band and late offset agree with the trace,
and the unexecuted terminal zero torque is absent. `git diff --check` passed
(this command checks tracked diffs; the new report was separately reviewed).

No scientific variables, assumptions, physical parameters, controller gains,
configs or acceptance thresholds were changed. No hardware, paid compute,
formal experiment, staging, commit, push, reset, stash, merge, deletion or
branch switch occurred. Auditor-created file: this `AUDIT_REPORT.md` only.

## Closure addendum — independent re-review, 2026-09-23

**Final diagnostic evidence/decision audit: PASS with the explicitly retained
limitations above.** Initial FINDINGS and their reasoning remain recorded;
this addendum closes them after checking the revised documents on disk.

- **F1 closed:** DGN population analysis, OBSERVED ledger, causal ledger and
  DEV table now explicitly identify first recorded 5 ms contact flags. The
  report reserves exact substep onset for the two instrumented replays.
- **F2 closed:** the report calls the offset near-stationary only within the
  observed window and states that extra waiting was not tested. DEV no longer
  calls a longer hold falsified or promises recovery from additional wait.
- **F3 closed:** the plan explicitly retains existing measured q/dq PD and
  labels online promotion a DEV hypothesis. Its first causal split compares
  retained-model active recovery with one justified update; complete matched
  state/history is required or unmatched reruns must be disclosed. It does
  not infer fit inaccuracy from handoff failure or demand the full online
  geometry/beta/residual/promotion combination before that test.
- **F4 closed:** the historical comparison explicitly names the known initial
  reference-q anchor and `bed_force_n` contamination input, and disallows
  treating those interfaces as validated cuff-only startup capabilities.

No new numerical contradiction or hidden-truth path was found during the
closure review. This PASS supports `DGN_COMPLETE` as a diagnosis/DEV-decision
status after the Builder completes the stated documentation/provenance checks;
it is not a qualification PASS, proof of hardware readiness, or evidence that
the proposed DEV repair already works. The next scientific step is the one
versioned DEV lifecycle plan, beginning with its minimal causal recovery
comparison. DGN must stop before implementing it.
