# Full-3D adaptive startup DGN V1 — causal diagnosis

Date 2026-09-23. Status: diagnostic evidence, **not** a repaired controller or
new qualification. Chinese is used for the analysis; source identifiers retain
their exact spelling. The failed `fresh_qualification_v1` remains formal
`FULL3D_FRESH_FAILED_WITH_EVIDENCE` (24 paired cases × three arms, zero complete
in every arm). All original cases reused here are *development diagnostics*.
The local uncommitted implementation that produced the result, not Git HEAD
alone, is the subject. See `SOURCE_SNAPSHOT.md`, `DIAGNOSTIC_PROTOCOL.md` and
`COMMANDS.md` for the frozen local dependency basis and replay procedure.

## 1. Actual source-grounded session, not the intended abstraction

1. `fresh_qualification_v1/domain.py::generate_cases/mechanical_screen` makes
   hidden varied plant/task cases, checks **true static** shank clearance along
   a straight start–goal interpolation, initial shank/bed noncontact and goal/
   start CR12 endpoint IK. It does not test the deployable initial-support
   waypoint predicate or later dynamics. Hidden parameters belong to plant and
   evaluation, not controller.
2. `full3d_adaptive_integration_v1/runtime.py::_initialize_loaded_runtime`
   constructs `nominal_control_model()` with fixed nominal effective world
   geometry and population dynamic beta. It resets the varied coupled MuJoCo
   CR12+cuff+Human V2+bed plant at hidden physical start (generation-only
   truth), computes a *nominal* loaded-support preload, applies its cuff-relative
   offset at the physical cuff pose and solves physical CR12 IK. It then measures
   robot/cuff pose, ideal twist and interface wrench (200 Hz, zero noise/bias/
   latency in this formal setup) and reconstructs `q_hat,dq_hat` from that
   measurement using **nominal**, not varied true, controller geometry. Thus
   physical initialization is anchored to the physical cuff, while the
   deployable state/cuff mapping is still fixed to nominal placement.
3. Before the first MuJoCo integration step, the measured `q_hat` is passed as
   an OUTBOUND `initial_support` candidate through
   `human_waypoint_shadow.py::HumanWaypointMPCShadowContractV1.prepare`.
   `_validate_candidate` applies task-progress geometry to this support hold;
   an estimate >1° behind the registered start and pointing away from the goal
   throws. If it passes, `command`/safety filter provides the first physical
   CR12 torque command. The support is **not** an ideal Human torque.
4. `runtime.py::run_executed_case` then emits a fixed 7.02 s commissioning
   program: 20 ms warmup, four 1.5 s quintic segments, then 1 s return hold.
   Every 5 ms it observes real MuJoCo physics (0.25 ms substeps), reconstructs
   state under `population_prior_v1`, applies **existing measured q/dq PD**
   inside `HumanWaypointMPCShadowContractV1.command`, solves loaded waypoint inverse dynamics,
   screens wrench/execution and commands the actual CR12. The commissioning
   reference starts from measured initial support and returns to the registered
   **physical task start**. Its fixed time does not wait on a physical settling
   event. 20 ms cuff pose/twist/wrench samples accumulate; **geometry, beta and
   residual are not updated online during the physical commissioning motion**.
5. At 7.02 s, `_fit_and_replay_commissioning` fits effective geometry on all
   stored cuff position/shank-angle samples and retrospectively replays 351
   dynamics/residual updates. These estimates/history and `belief.sequence`
   persist into the task. The runner atomically replaces the controller model,
   observer geometry and session-clearance geometry at handoff. No post-fit
   physical recovery interval is executed. `task.py::start_episode` then
   requires the newly estimated `q_hat,dq_hat` to be inside the unchanged
   registered start set (1° per joint and 2°/s in this domain), or aborts.
6. Only after this gate does `AdaptiveHumanWaypointHWMPCV22.decide` score
   fresh-state Human Δq candidates, schedule quintic reference, screen model
   inverse-dynamics/wrench and pass reference to CR12 torque control.
   Continual task beta/residual updates occur at 20 ms; commissioning-only
   freezes both and fixed-population omits the fit. During a pending decision,
   the previous/current reference remains active and the plant advances. A
   plan older than 100 ms is rejected; timeout/force/clearance/acceleration
   paths fail closed. This is genuine coupled physical task execution, but only
   three adaptive cases ever reached nonzero task motion in the failed study.

The source makes the current registered-start requirement *essential to this
runner's task-entry contract* (`start_episode`), not evidence that a robot
cannot safely support or recover from another valid physical state. One cannot
simply ignore the requirement while still claiming completion of the same
start/goal task. Model confidence does **not** pace commissioning or change
candidate selection; accepted point estimates and source strings enter the
planner. Measurement age, reference and belief version are logged at task
decisions; the commissioning fit is a batch activation, not a gradual online
promotion. The old nominal reference remains active during planning latency.

## 2. Failure-family classification

| Original adaptive outcomes | Observed mechanism and evidential limit |
|---|---|
| Three shared pre-step exceptions | `initial_support` OUTBOUND progress validation throws **after successful loaded CR12 IK**, before physics. Software/lifecycle mismatch, not demonstrated robot reach infeasibility. |
| 17 commissioning handoff failures | Real q missed return/start before fit, often while qhat closely tracked real q. The fixed program ended without a state-dependent recovery. This is physical reference-tracking plus procedural handoff failure; exact torque/interface contribution to the tracking error remains open. |
| One handoff clearance abort | Fitted session-conservative deployable clearance became negative; true clearance is distinct. A fail-closed contract event, not proof of true collision. |
| One task no-feasible waypoint | At a near-goal task state, session-conservative target endpoint clearance rejected remaining candidates. This demonstrates mismatch between generation-side true static feasibility and deployable conservative feasibility; it does not prove the true goal is dynamically executable. |
| One task force abort | Measured cuff force 200.017 N exceeded the frozen 200 N limit by 0.017 N. Correctly fail-closed; no post-hoc threshold relaxation. |
| One task deadline abort | A measured 108.069 ms decision exceeded 100 ms and was not silently activated. Separate runtime-study qualification did not guarantee all varied full-3D states. |

Fixed-population differences are retained in the original report (15 handoff,
three clearance, one no-feasible, one timeout, one stale, three pre-step).
Zero completion across arms cannot isolate task-period adaptation value:
continual and commissioning-only encountered the same dominant startup gate.

### Pre-step exceptions: exact discriminating replay

`prestep_initialization_replay_v1.json` invokes the unchanged initializer for
the three failed cases plus one valid contrast. All three loaded-preload IK
calls returned finite six-axis configurations. Their nominal-geometry measured
initial estimates fell behind physical registered start by respectively
−1.022°, −1.116° and −1.386° in **each** joint. The task progress dot products
were respectively −0.03942, −0.01459, −0.03661 rad², with the candidates
outside the 1° origin tolerance; `HumanWaypointMPCShadowContractV1._validate_candidate`
reproduced `ValueError: waypoint moves away from the registered phase goal`.
The matched contrast `balanced_ordinary_r01` differed by only +0.025° and
initialized. This demonstrates an inappropriate task-waypoint predicate for a
pre-task physical support state. It does **not** establish that every varied
setup will satisfy all CR12 reach, cuff and bed mechanics after the software
predicate is repaired.

### Commissioning first divergence and handoff

`handoff_population_v2.json` aligns the 24 original adaptive records on
physical time: 3 pre-step, 21 physically commissioned, 17 handoff failures.
There was no shank/bed contact at the initial boundary in any of the 21.
Against the **existing** 1° task angular tolerance (used descriptively, not
as a new controller trigger), true q/reference error exceeded tolerance
*before* the first **5 ms-sampled** bed-contact flag in 20/21; that flag
preceded it in only one. Sub-5 ms contact onset has been independently
resolved only for the two focused physical replays, so this population-level
ordering is limited by the stored monitor resolution.
All 21 later contacted the bed. Among the 17 handoff failures, the median
maximum-joint physical true/reference error at handoff was 3.845°, whereas
the median pre-fit qhat/true discrepancy was 0.398°; zero of 17 physically
landed inside the 1° angular start set and zero of 17 newly estimated states
landed inside it. Thus the abort is not merely an estimator relabeling at
fit activation. The median max-joint qhat jump upon geometry activation was
0.399° with **no corresponding physical motion**. Such a jump is real and
matters for continuity, but cannot explain the already present physical offset.

Representative `balanced_ordinary_r01`: start true (5.883°, 9.485°), nominal
qhat (5.908°, 9.511°), no bed contact; true dq/reference exceeded the existing
2°/s tolerance by 0.005 s and q/reference exceeded 1° by 0.080 s. First
5 ms bed contact was 2.485 s; an exact matched 0.25 ms replay located it at
2.48075 s. At 7.02 s true q was (6.849°, 12.093°), +0.966°/+2.608° from
start, while pre-fit qhat differed from true by just −0.0235° in each joint.
The post-fit qhat changed +0.0141°, with no physical q change, and task entry
aborted. The last 0.5 s error changed only −0.00494° and speed was at most
0.0125°/s: this case was nearly stationary **over the observed window** while
offset from the reference. The trace gives no positive evidence that merely
waiting a fixed extra duration would recover it, but does not prove an
asymptotic equilibrium. In the full 17, ten had
similarly very low terminal speeds (~0.006–0.016°/s and ≤~0.007° error change
over 0.5 s), whereas seven were still moving ~1.3–3.2°/s with improving
error. These are descriptive clusters, not new pass/fail criteria.

The aligned nominal development comparison also made shank/bed contact yet
returned near the registered start and completed its task. Its first >1°
true/reference divergence was later (~2.06 s) and did not persist. Therefore
contact occurrence by itself is not a sufficient cause of handoff failure.
The failure plot and working contrast are
`results/.../startup_dgn_v1/aligned_existing_traces_v2/{balanced_ordinary_r01,nominal_development}.png`.
The `_v1` plot output had an unexecuted terminal-boundary zero torque display
artifact; `_v2` excludes it and is authoritative. Original trace data did not
change.

### What the contact replay adds and does not add

Two **unchanged coupled-plant** diagnostic replays instrumented only the
evaluation-only `TruePhysicsMonitor.observe` callback. For both cases the
commissioning time, qref, qhat, qtrue, six-axis robot q/command, cuff force
and 5 ms contact arrays matched saved baseline **exactly (maximum difference
0)**. In the failed `balanced_ordinary_r01`, bed normal force peaked 91.384 N,
force integral 73.470 N·s, 1.085 s integrated contact duration, minimum
contact distance −1.106 mm. The successful nominal contrast had peak 119.327 N,
109.791 N·s and 1.2495 s duration, minimum −1.144 mm. This is material
temporary bed loading, not just binary boundary chatter. It arrived well
after first divergence in the failed case; it could compound motion/model
error but its independent causal contribution is not isolated. The formal
task-period safety gate did not count commissioning contact; DGN neither
retroactively forbids nor declares all such support acceptable. The controller
has no deployable bed-normal-force signal. Contact load is offline truth only.

`_fit_and_replay_commissioning` feeds every 20 ms sample to the free-motion
inverse-dynamics beta/residual updater without a contact-eligibility flag.
The exact `balanced_ordinary_r01` replay found 56 of 351 retrospective update
intervals overlapping 0.25 ms physical bed contact (the coarser 5 ms census
finds 55). This proves exposure to unmodeled support load, **not** that those
particular updates caused this episode's earlier tracking deviation; they
were applied only after commissioning ended.

### Prior/fit/reliability and task planning

`architecture_recovery_v2/effective_model.py::fit_effective_geometry` fits
`(hip_x, hip_z, L1, knee_to_cuff)` from cuff pose and measured shank angle.
It requires ≥30 samples, ≥4° angular span, ≤3 mm RMS radial residual,
reported condition ≤2e5, no bound hit. The reported condition uses the
**regularized** least-squares Jacobian, not observation-only information.
`balanced_ordinary_r01` had 352 samples, 0.2076 rad shank span and accepted
fit (reported condition 1337.42, RMS ~µm). The unchanged replay's analytic
data-only Jacobian condition was 1393.04, augmented regularized 1337.42; the
weak direction jointly trades hip position and thigh length. In this case
regularization improves conditioning only modestly; it did **not** fabricate
full rank from rank-deficient data. Nevertheless the current acceptance metric
cannot certify data-only information, out-of-sample model prediction or
full-session action reliability. `AdaptiveHumanBeliefV22` holds geometry, beta,
residual weights and provenance/counts, but no covariance/support/margin that
changes action selection. A low radial fit residual does not test CR12/cuff/
bed predictive error. We do not label the prior intrinsically unsuitable:
nominal works, and the observed issue is fixed-prior motion plus unverified
batch promotion and unconditional procedural handoff.

The local planner **retains** the emitted-reference monotonic rule in
`human_waypoint_feedback_mpc.py::_evaluate`; candidates are derived from fresh
state, but schedules are anchored at the emitted reference, so a physical
state ahead/behind that reference can make an otherwise useful action fail the
progress test. This is a demonstrated source constraint, **not** demonstrated
as the cause of the observed `knee_dominant_middle_r02` exception. There the
last successful decision had five feasible candidates, then the next task
decision raised `NO_FEASIBLE_WAYPOINT` because the conservative session model
predicted a target endpoint at −7.746 mm. Generation-side true *static* path
clearance for this accepted case was at least +26.097 mm; actual executed
partial-task physical minimum was +26.166 mm. The unexecuted goal has no
actual physical execution proof. The scheduler hard-rejects a negative
endpoint before its polynomial-duration search; the 0.46 m structural shank
upper bound plus 1 mm margin can disagree strongly with the hidden true
geometry. It would be scientifically wrong simply to drop that safeguard or
replace it with hidden truth. The runtime also lacks an explicit support,
deceleration, or measured-state re-anchor action in this exhausted candidate
set. The deadline case and 100 ms stale-plan handling are separate failures.

## 3. Focused historical Stage 4 comparison

`stage4_adaptive_control/cold_start.py::run_cold_start_adaptive_case` already
demonstrated a population-prior controller that updates an estimator and solves
MPC while following teaching motion; it initialized its estimator from the
**known registered initial reference q** and could pass a `bed_force_n`
contamination flag into identification. Neither is a deployable replacement
for unknown-start, cuff-only sensing in the present setup. That study did
**not** prove arbitrary unknown-start/setup generalization, and its plant/
execution assumptions differ from this six-axis CR12 physical chain.
`confidence_execution.py` has
`ExistingEstimatorConfidenceMonitor` and `UnifiedReferenceManager`: it
separates model/information validity, retains valid models and paces one
reference clock using trust and force. Current full-3D integration reuses
population effective dynamics and low-level measured execution, but bypasses
that online-identification/reference-pacing lifecycle: physical commissioning
holds nominal model then batch-activates it and uses a fixed reference clock.
The old trust stack is therefore a *mechanism to study*, not a proven module
to transplant wholesale. In particular, numerical conditioning of a
regularized fit should not be used as its information-confidence input.

## 4. Evidence-strength ledger and open limitations

- **OBSERVED:** three exact pre-step progress-predicate exceptions; 20/21
  threshold-level physical angular divergences before the first **recorded
  5 ms** bed-contact flag; all 21 later have recorded contact;
  17 handoff failures with real physical start error; qhat model-switch jump;
  accepted regularized fit; retrospective dynamics updates overlapping contact;
  conservative deployable clearance no-feasible event; fail-closed force and
  stale-plan events. Source paths and result JSON above support these.
- **CAUSALLY SUPPORTED:** the three pre-step exceptions are caused by reusing
  task-progress validation for initial physical support, not CR12 IK failure;
  the dominant handoff abort arises because fixed-duration commissioning ends
  with real q outside the registered start and no active recovery, not because
  fit alone moves the patient; in 20/21, the recorded 5 ms contact flag follows
  the first threshold-level angular divergence (with exact 0.25 ms ordering
  additionally confirmed for one failed replay), and contact occurrence alone
  cannot discriminate failure.
- **RULED OUT at this evidence scope:** “all 24 physical rollouts ran”; “the
  17 handoff misses are merely geometry-estimate jumps”; “the observed
  contact is sufficient by itself to explain all failures”; “accepted fit or many
  samples certify next-action reliability”; “no feasible candidate proves the
  hidden physical goal is impossible.” An extra fixed wait was not tested as a
  counterfactual; the near-stationary wrong-offset cases provide no positive
  evidence that waiting alone would repair them.
- **OPEN:** the exact share of preload mismatch, population inverse dynamics,
  CR12 servo/actuator, cuff compliance and later bed support in the earliest
  tracking error; whether support contact is intended/allowed in a future
  session; uncertainty calibration of the effective geometry/clearance; true
  goal dynamic executability in the no-feasible case; command continuity when
  a fit actually promotes into a live task (failed handoffs do not execute a
  post-switch command). The current controller **already** has measured q/dq
  feedback; whether online geometry, beta, residual or predictive model
  promotion is necessary beyond active recovery under the retained model
  remains a DEV hypothesis. These require DEV tests, not hidden-truth insertion.

No source/control parameters were changed, no new held-out outcomes generated,
no production runtime claim is made from instrumented replays, and no physical
hardware was actuated.
