# DGN V1 decision: one continuous, measured-state startup-to-task session

This is a proposed **DEV** design and test scope, not a production change.
The current formal V1 result remains failed; every original failed case may
be a DEV regression case but is no longer fresh held-out evidence. The DEV
objective is complete CR12+cuff+Human V2+bed OUTBOUND/HOLD/RETURN execution
under the original physical limits, not merely avoiding a handoff exception.

## Primary architectural choice

Replace the *fixed-duration probe → retrospective fit → immediate start check*
transaction with one causally observed, safety-constrained session: physical
support from current measured pose; conservative useful motion; state/event-
driven recovery to the unchanged registered task start; and the existing
fresh-state waypoint task. **Online model updating/promotion is a hypothesis
to earn by matched DEV tests**, not a diagnosis that the current fit was
necessarily wrong. A distinct probe is retained only when task-related safe
motion demonstrably lacks sufficient information. This is one lifecycle
repair, not a stack of after-the-fact tolerances.

### KEEP

- Six-axis CR12 MuJoCo plant, cuff compliance, Human V2 and bed physics;
  deployable sensor boundary and hidden-truth firewall.
- Control-effective geometry `(hip_x, hip_z, L1, knee_to_cuff)`, composite
  beta and state residual as the core adaptive representation; individual
  anatomical parameter identifiability is not a prerequisite.
- Existing 5 ms physical torque execution, 20 ms adaptation concept,
  quintic reference, task phases, hard ROM/velocity/acceleration/wrench limits,
  mechanics screening and 100 ms stale-plan fail-closed rule. Value hook zero.
- Time-aligned N intervals/N+1 boundaries and actual physical wrench
  integration. Do not borrow a reduced Human-only result as CR12 evidence.

### REPAIR / REWIRE (ordered development work, one mechanism tested at a time)

| Current behavior → demonstrated problem | Proposed principle and implementation freedom | Expected mechanism; validation; new risk; simpler alternative |
|---|---|---|
| `initial_support` goes through OUTBOUND progress validation; three varied cases throw before physics despite successful loaded IK. | Give non-task support/maintain-reference a distinct semantic type or entry API, anchored at the measured cuff/robot state, while retaining physical IK, wrench, ROM/contact and actuator screening. Never treat support as task progress. | All three original setups initialize and physically hold without bypassing safety. Check first-command continuity and no hidden geometry. Risk: support action could conceal mechanical incompatibility; simpler alternative of widening the 1° task tolerance is rejected because it changes the task and would not fix the semantic conflation. |
| Fixed nominal geometry/dynamics drive all 7.02 s commissioning motion, though true/reference error usually predates the first **recorded 5 ms** contact flag; 17 handoffs miss true start and some remain nearly stationary while offset over the observed final 0.5 s. Existing `HumanWaypointMPCShadowContractV1.command` already applies measured q/dq PD every 5 ms. | Keep that feedback path; test an **active, measured-state recovery** to registered start under the retained model, terminated by the original q/dq set rather than a single fixed clock. Then test one causally justified model update at a time if retained-model recovery is insufficient. Keep prior support while information is weak. | Preserve complete physical/controller/history state for a matched branch where practical, or label reruns unmatched. Test physical q/qhat/qref, command, cuff force and contact per interval on original failed/nominal DEV cases. Retain bounded timeout/fail-closed outcome. Risk: recovery can add physical exposure; simply waiting an extra fixed duration has no supporting evidence in near-stationary cases but was **not** experimentally ruled out. Arbitrary gain retuning is not evidence-backed. |
| Fit acceptance uses regularized Jacobian and radial residual, then batch-activates geometry/beta/residual with no predictive check or reference recovery. The accepted fit has **not** been shown inaccurate. | First distinguish recovery under retained model from recovery with a single justified update. If updating is needed, separate observation-only geometry information (data Jacobian singular directions/span), contact/motion data eligibility, recent next-interval prediction residual and actual execution margins. Promote a challenger only after an action-relevant check, with timestamped version/provenance. Guard **state estimate and actuator-command continuity**; preserve history. | On matched DEV branches compare next 20 ms measured motion/wrench and command continuity; activate geometry, beta or residual online only if that component improves a demonstrated deficit under unchanged limits. Risk: conservative promotion delays adaptation and data may be insufficient. `fit.accepted` alone is not evidence of action reliability, but its coexistence with a failed handoff does not prove fit error. Do not add a generic scalar confidence as a substitute for these checks. |
| Separate fixed probe, fit, fixed 1 s settle and immediate `start_episode`; no explicit support→recover→task lifecycle. | One reference/phase owner should generate continuous support, exploration/useful task-related motion, recovery to start, task and fallback. If any fit is activated, it cannot create an unapproved reference/command jump. The original task starts only after its original start set is reached. Probe only when an information diagnostic shows task motion is insufficient. | Verify every boundary's q/dq/ddq reference continuity, causal model version and physical execution while planning; no teleport/pause. Test actual OUTBOUND/HOLD/RETURN on DEV cases. Risk: extra state machine complexity; a changed handoff timeout alone has not been shown to repair the observed offsets and cannot handle other lifecycle issues. |
| Planner candidates derive from current state but `_evaluate` constrains progress relative to emitted reference; finite positive Δq lattice and conservative endpoint checks can strand a state. The observed no-feasible case is specifically predicted negative endpoint clearance. | Maintain a safe non-progress/deceleration/realignment option where physically justified, distinguish this from task progress, and make waypoint ranking/action availability sensitive to measured tracking and verified model/clearance support. Do **not** silently remove endpoint screening or change cost/goal. The fixed 0.46 m shank bound must remain until a deployment-valid calibration/uncertainty argument supports an alternative. | Diagnostic test on saved planner states must classify reference-rule rejection separately from endpoint-clearance rejection, then physical CR12 DEV rerun. For the observed knee case, a new action alone cannot certify the goal: generation true static path ≥+26.097 mm vs deployable endpoint −7.746 mm. Risk: additional candidates/runtime; simpler relaxing clearance to hidden true geometry violates firewall. If no deployable bound can certify the goal, fail closed and report a domain/measurement limitation. |
| Commissioning contact is real but not incorporated in data eligibility or full-session safety accounting; a failed case had 56/351 retrospective update intervals overlapping bed contact. | Define a physical-session contact policy before DEV evaluation: distinguish intended supported-bed contact from unplanned collision and specify which *deployable* measurements (not hidden bed normal truth) detect model-invalid intervals. Keep evaluation-only true bed force for audit. Gate or explicitly model contact-affected dynamics updates; preserve geometry data if still valid. | Test baseline-vs-contact-conditioned estimator replay on the same stored data first; physical validation checks contact, cuff force and task metrics across all phases. Risk: if support contact cannot be detected from allowed sensing, the controller must conservatively mark those intervals uncertain; simpler declaring all contact safe/unsafe retroactively is unsupported. |

### REPLACE / ADD ONLY IF NECESSARY

Replace the *fixed commissioning clock and immediate batch-only handoff
interface*; do not replace the adaptive Human model, CR12 torque chain or HWMPC merely
because startup failed. Add a narrowly scoped session/reference owner only
if current `GoalTaskState` plus scheduler cannot express pre-task support,
recovery and bumpless transfer; add explicit fit-information/predictive-error
records rather than a large generic trust subsystem. Stage-4
`UnifiedReferenceManager` suggests a rate-continuous reference clock, but its
historical settings and assumptions must not be copied as calibrated values.

## DEV gates before any new fresh qualification

1. **Mechanically valid entry:** each of the three old pre-step cases obtains
   a physical CR12 support command and steps safely, or fails for a newly
   evidenced mechanical reason. Existing limits and task definition unchanged.
2. **First causal split, then model scope:** compare retained-model active
   recovery against one justified model-update recovery with matched physical,
   controller, reference, history and timing state, or disclose unmatched
   reruns. Only then decide whether online geometry, beta, residual and/or
   predictive promotion are necessary. Prove samples used for any online
   updates were available at that time, identify data-only weak directions,
   record contact eligibility and preserve history. qhat, emitted q/dq/ddq
   reference and executed command must have no unapproved jump at promotion.
   Assess *next-interval* prediction, not only fit residual.
3. **Physical startup recovery:** original stationary-offset and still-moving
   handoff families are tested with actual CR12+cuff+bed execution. A case may
   still fail closed, but cannot be reported as task-capable merely because a
   handoff gate is bypassed. No relaxation of original start, ROM, force,
   clearance, acceleration or timeout contract without separate authorization.
4. **Task planner/execution:** on the old no-feasible case, explicitly resolve
   whether a deployable clearance certificate exists. Demonstrate non-progress
   support/realignment without unbounded wait or stale action; check candidate
   set, deterministic cost and mechanics screen. Track force/deadline cases
   separately; never mask them by widening gates.
5. **Full-session DEV closure:** several representative old failures plus the
   nominal control must complete or be honestly classified across actual
   OUTBOUND/HOLD/RETURN, physical force/clearance/contact/acceleration,
   causal adaptation and timing-aware planning. Keep original failures and
   all DEV reruns. Independent review before a separately preregistered,
   **new-seed** full-3D qualification.

Two decisions remain genuinely external to DGN: whether/how bed support is
intended to be allowed during *all* phases, and whether full shank length (or
a defensible tighter upper bound) can be obtained by a deployment-valid
calibration. Cuff-only effective geometry identifies knee-to-cuff, not full
shank length; the present evidence does not license shrinking the 0.46 m
bound. If the information is unavailable, some true-feasible goals may remain
uncertifiable and must fail closed rather than be declared controller successes.

No DEV implementation, new formal campaign, ROM extension or value learning
was performed in DGN.
