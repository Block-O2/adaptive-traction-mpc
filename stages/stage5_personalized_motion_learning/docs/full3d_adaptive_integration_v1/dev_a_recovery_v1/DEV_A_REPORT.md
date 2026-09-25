# DEV-A — Full-3D startup and active-recovery development report

Status: **DEV_A_PARTIAL_MODEL_OR_EXECUTION_LIMIT_REMAINS**. This is a
versioned development result, not a fresh qualification. The historical
formal result remains `FULL3D_FRESH_FAILED_WITH_EVIDENCE` (zero complete in
72 paired formal-arm runs); it has not been rewritten. The current-domain
full-3D result is not a 120–130° large-ROM validation.

## What changed, and what did not

The old lifecycle physically initialized CR12, commissioned for 7.02 s,
retrospectively fit/replayed the model, switched it at a fixed clock boundary
and immediately asked `start_episode` whether the Human happened to be at
task start. The repaired lifecycle explicitly distinguishes non-task support
from task progress, then uses the *current deployable estimated Human state*
to plan and physically execute recovery before the unchanged task-start
gate. Each 5 ms command still travels through the existing CR12 torque,
compliant cuff, Human V2 and MuJoCo bed/contact plant. No Human q/dq reset or
scripted jump is used. OUTBOUND/HOLD/RETURN task planning remains the existing
fresh-state HWMPC path. The value hook remains exactly zero.

The fit method, effective geometry, 11-D beta, beta limits/smoothing/3%-span
step cap and cadence, residual learner/gain/bounds, task candidate set/cost,
force and moment limits (200 N/60 Nm), ROM, velocity/acceleration limits,
bed mechanics, CR12 plant and 100 ms stale-plan threshold were not tuned or
relaxed. Recovery does not run an additional beta or residual update; task
period updates resume under the existing rule after task entry. Thus the
causal comparison is a **lifecycle repair with the same adaptive model**, not
an adaptation improvement claim.

## Exact production path and startup defect

`runtime.py::_initialize_loaded_runtime` obtains the deployable measured
support state after valid six-axis loaded CR12 IK. Previously it sent
`initial_support` through `HumanWaypointMPCShadowContractV1.prepare`, whose
OUTBOUND progress predicate rejected three varied starts before MuJoCo
stepping. `WaypointExecutionContext` now marks support, commissioning,
recovery and task explicitly. Only `TASK` retains that directional progress
check; all contexts retain registered task q bounds, Human ROM, velocity and
phase-goal consistency. The three formerly pre-step cases each then
completed the original 7.02 s / 28,080 physical commissioning steps under
the startup-only diagnostic. They still failed the old immediate handoff, as
expected. This isolates the initial software-rule failure from the physical
recovery question.

## Active recovery and handoff

After the unchanged fitted model is computed, recovery keeps the prior model
and prior reference physically active during its first planning delay. The
recovery correction target uses the current causal observation:

`q_corr(λ) = q_start + λ(q_start − qhat_now)`, with `λ ∈ {1, .5, .25, .125, 0}`.

The first feasible candidate is selected after the *existing* quintic
scheduler, task/ROM/velocity/causal-acceleration and session-clearance checks,
and adaptive inverse-dynamics mechanics screen. Rejections are logged; no
candidate bypasses a check. The schedule starts from the last *emitted
reference* q/dq/ddq, not lagging true q, to preserve reference continuity.
Its minimum transition duration is the existing 1.5 s commissioning segment;
the overall recovery uses the existing 10 s task-phase timeout. After the
correction segment, it returns smoothly to the registered start if needed,
then requires the unchanged `at_goal` q/dq predicate for 20 ms persistence.
If the emitted reference is already at start, it enters measured settling
directly; it does not insert a second zero-displacement segment. Failure to
settle, no feasible certified segment, deadline miss, session-clearance
violation and physical limit abort remain distinct outputs.

The same task-start q maps to robot desired cuff poses separated by 16.97 mm
under prior versus accepted geometry in `balanced_ordinary_r01`. A C2
quintic SE(3) robot-cuff target bridge spans the first recovery segment;
the nominal model remains in force during the planning wait. The bridge's
reported endpoint position/rotation/twist jumps are numerically zero in the
examined runs; schedule q/dq/ddq boundary jumps are explicitly checked and
zero. This does **not** make model/wrench/torque activation magically
bumpless: in the balanced ordinary development case, the first fitted-model
CR12 torque command changes by 2.208 Nm norm, materially above its ordinary
later 5 ms torque changes (~0.244 Nm p99 in that run). Across the 20 V2
cases that activated the fitted model, the largest first-command step was
**34.780 Nm** (balanced near-upper-current-ROM R01, prior→belief at
t=7.020→7.025 s), with simultaneous allocated robot-site force/moment
changes of **49.582 N / 9.730 Nm**. qref/dqref/ddqref and desired cuff
pose/twist were identical at those two boundaries; the immediately preceding
old-model 5 ms torque change was only 0.058 Nm. This associates the step
with model activation, although no exact same-state no-activation physical
counterfactual was run. A continuous desired cuff pose therefore did **not**
guarantee a continuous generalized action, allocated wrench or CR12 torque.
This is a high-priority unresolved DEV-A execution-continuity issue, not a
claim that the registered absolute force/torque limits were crossed: both
boundary commands were in TRACK, below robot actuator limits, with measured
recovery cuff peak 90.515 N / 7.416 Nm and positive clearance in that case.

Recovery reads measured robot state, cuff pose/twist and cuff wrench via the
existing sensor/observer boundary. The planning origin is qhat/dqhat; true
Human q/dq and contact truth are only logged/scored. A plan older than 100 ms
is never activated. Simulated planning latency is represented by physically
stepping the full plant for the measured compute-delay interval under the
previous reference; this is controlled synchronous delay replay, not a claim
of asynchronous hardware real time.

## Development evidence and causal limit

The same post-commissioning physical/observer state is available to evaluate
the old immediate `start_episode` eligibility: historical failed handoffs
have no intervening physical step after fit, whereas DEV-A proceeds to
recovery. We did **not** clone the complete MuJoCo/controller/RNG/pending-plan
state into two independently continuing physical branches. Therefore the
evidence directly isolates the immediate handoff-gate defect but the later
old/new physical trajectories are paired reruns, not exact state clones.

The first measured-state-as-reference recovery prototype failed on
`balanced_ordinary_r01` because its lagging-state target fell below the
unchanged deployable task endpoint clearance floor; that failure remains in
`representative_v1/`. Symmetric error correction recovered this case in
3.045 s without model-law changes, then its *task* HWMPC correctly rejected
remaining candidates at approximately −4.7 mm predicted endpoint clearance.
The old nominal development case completed the full task before and after
the DEV-A lifecycle change. Its unnecessary 3.035 s V1 recovery became a
1.525 s model-pose bridge and settle in V2; it still completed.

The original DGN finding remains visible: commissioning error developed
before first **recorded 5 ms** contact in 20/21 physically initialized old
cases, and the 17 old handoff failures had median 3.845° true/reference
maximum-joint error, versus 0.399° fitted-state estimate jump. DEV-A traces
retain qref, qhat/dqhat, evaluation-only qtrue/dqtrue, physical cuff
pose/twist/wrench, robot state/torque, contacts, model version and phase on
the same physical timeline. For `balanced_ordinary_r01`, commissioning
time/state/reference/torque/cuff-force arrays are bitwise identical to the
prior DGN exact contact replay. Thus recovery does not erase or relabel the
early physical tracking error.

## Final 24-case consumed-case development regression

The final regression is `results/.../dev_a_recovery_v1/regression_v2/`;
`regression_v1/` is preserved as an earlier lifecycle revision. Each case
uses its original hidden plant/task definition but is **development evidence**
because the failed formal set has already been seen. Only the adaptive
production arm was rerun. All 24 accepted case keys remain in the denominator.
The derived aggregate is `regression_v2/regression_summary_v2.json`; its
predecessor `regression_summary.json` is preserved, and V2 ensures that a
terminal TASK-labelled boundary with zero executed TASK intervals is not
misreported as a task physical force/clearance sample.

| Final V2 development measure | Result |
|---|---:|
| Actual six-axis CR12 initialization and 7.02 s physical commissioning | 24/24 |
| Matched old immediate handoff eligible at the same saved post-commissioning qhat/dqhat | 4/24 |
| Entered ACTIVE_RECOVERY | 24/24 |
| Event-driven recovery settled at unchanged start; task entered | 15/24 |
| Recovery success among the 17 historically failed handoffs | 11/17 |
| Successful recovery from a state where the matched old immediate gate would fail | 12/24 |
| Full OUTBOUND→HOLD→RETURN→COMPLETE | 2/24 |
| Recovery fail-closed: no feasible certified segment / remaining original 10 s budget too short for another 1.5 s segment / session clearance | 3 / 5 / 1 |
| After task entry: no feasible waypoint / stale plan / task velocity / cuff force / session clearance / OUTBOUND timeout | 4 / 4 / 2 / 1 / 1 / 1 |
| Commissioning endpoint true/reference maximum-joint error, median / maximum | 3.332° / 14.154° |
| Successful recovery endpoint estimated/start maximum-joint error, median / maximum | 0.083° / 0.955° |
| Recovery duration across all 24, median / maximum | 3.045 s / 9.075 s |
| Recovery planner time, 61 decisions: median / p95 / max | 2.697 / 8.748 / 11.809 ms; zero recovery stale plans |
| All recovery + task planner calls, 137 decisions: median / p95 / p99 / max | 8.718 / 96.266 / 110.483 / 119.441 ms |

The two completed tasks were `balanced_middle_r01` (time-aligned q RMSE
0.887/0.995°, task physical cuff peak 132.367 N / 19.605 Nm, force integral
638.625 N·s, minimum deployable/true clearance +18.800/+28.942 mm) and
`elevated_start_ordinary_r01` (RMSE 0.545/0.448°, peak 124.629 N /
14.688 Nm, integral 576.574 N·s, clearance +30.122/+40.422 mm).
These are two consumed development cases, not robustness qualification.
Both executed event-driven HOLD and RETURN; no task state was reset at entry.

The four task stale-plan aborts had measured decision times 100.642–119.441
ms, all for task candidate `outbound_dq_07`. No stale result was activated.
The 100 ms contract therefore remains fail-closed but is **not** satisfied
across this varied development set. The V2 recovery planner itself had no
deadline miss. Recovery force peak over all cases had median 85.015 N and
maximum 135.724 N; recovery force integral had median 227.606 N·s and
maximum 687.888 N·s, counting only executed physical intervals. The minimum
recorded recovery deployable clearance was +0.619 mm among executed recovery
intervals. `balanced_ordinary_r02` was refused before any recovery interval
because its fitted session-certification origin was negative (−5.053 mm);
the evaluation-only true physical boundary clearance was approximately
−0.007 mm and a contact was recorded at that boundary.

Observed failure classes must be interpreted separately: a negative
deployable session clearance can fail closed even when evaluation-only true
clearance is positive; a no-feasible *task* waypoint is downstream of a
successful recovery; a 100 ms stale-plan abort is not a model-estimation
failure. A physical cuff-force or velocity abort is not a planning
infeasibility. There was no Human ROM or actual Human acceleration violation
during the final DEV-A recovery physical intervals. The prior V1 development
replay's planner maximum was 127.441 ms; V2's maximum was 119.441 ms, with
four task-stage stale-plan aborts. Runtime study
qualification on a prior development corpus did not prove all varied
full-3D states would stay below 100 ms.

## Contact, force, adaptation, and safety interpretation

Bed support contact is neither universally forbidden nor universally safe.
The evaluation-only `TruePhysicsMonitor` separates commissioning, recovery,
and task physical steps and records true geometric clearance, ROM and contact
steps. A case beginning recovery with an existing contact/negative certified
clearance is kept in the denominator and can fail before executing a recovery
interval. The DGN instrumented `balanced_ordinary_r01` commissioning contact
replay measured 1.085 s loading, 91.384 N normal peak and 73.469 N·s
integral; the nominal development contrast also had contact (1.2495 s,
119.327 N peak, 109.791 N·s integral) and completed. These are not matched
contact interventions. DEV-A's new recovery-stage contact truth is not used
to choose actions. No claim that all contact-affected dynamics samples are
identified correctly is made; that is outside this frozen-model study.

For each episode `summary.json` saves commissioning fit, beta/residual replay,
belief sequence, recovery entry/end beta and residual weights, update counts,
planning model sequence, measured force/moment/integral, certified clearance,
evaluation-only physical clearance/contact and full task adaptation history.
Beta and residual do not move during recovery by design (zero update attempts
there); task-period adaptation is unchanged. Task completion is not evidence
of beta convergence: `balanced_middle_r01` had 15 task-period beta attempts,
12 accepted, four rate-cap hits, and its final accepted beta step was still
0.7001 L2 units only 0.10 s before task end. `elevated_start_ordinary_r01`
had 12/12 accepted, seven rate-cap hits and a final 0.1774 step 0.16 s
before end. Thus even these two successes were **not shown settled**; the
final 5 ms no-update slices only reflect the original beta cadence. DEV-A
did not retune smoothing or the 3%-span cap.

## Decision for DEV-B and remaining first divergence

**Active recovery with the existing model partially repairs the lifecycle,
but does not sufficiently repair the complete varied full-3D task.** The
startup software rule is removed; many displaced physical states now reach
the original task-start predicate and enter task. The earliest remaining
failure varies by case: certified clearance can reject the recovery origin;
larger offsets can leave too little of the original 10 s budget for another
1.5 s minimum-duration recovery segment; after successful recovery,
task-level endpoint clearance, physical
force/velocity and planner deadlines can still abort. A nontrivial
model-activation torque step also remains. None licenses changing beta speed,
the 0.46 m conservative shank bound, safety thresholds or hidden-truth
inputs in DEV-A.

The narrowest next stage is a **single matched DEV-B first-divergence study**:
from one retained post-commissioning state with recovery failure or large
command transient, separate next-interval Human-model prediction error from
qhat error, CR12 low-level execution error and cuff-transmission error under
the same command/physical state. Do not implement model redesign, fresh
qualification, large-ROM extension or learning before that diagnostic.

## Provenance and reproducibility

The independent fresh-context Auditor checked source and all 24 final case
artifacts. Its verdict is **bounded DEV evidence PASS; complete varied-task
repair FAIL**, supporting the partial DEV-A status. It confirmed the narrow
startup-rule fix, real CR12 physical chain, causal recovery inputs, unmodified
model/task/safety limits, four correctly rejected task stale plans and all
retained failures. Its high-priority finding is the fitted-model
action/wrench/torque transient above; it did not find a hard-limit breach in
the cited case. It also required the precise segment-budget timeout wording
used here and a finalized checkpoint.

See `DESIGN_DECISIONS.md`, `COMMANDS.md`, `CHANGED_FILES.md`, versioned
`results/.../dev_a_recovery_v1/` outputs and the independent `AUDIT_REPORT.md`.
The branch remains `codex/stage5-architecture-recovery`; starting published
HEAD was `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. Numerous full-3D
source/assets are untracked and DEV-A results are Git-ignored; clean-clone reproducibility
is **not** claimed. Nothing was staged, committed, pushed, reset, stashed,
deleted or branch-switched. Scientific model/task/plant assumptions and
parameters were not changed; only startup/recovery lifecycle, reference
transition, phase-scoped candidate semantics and diagnostics were edited.
