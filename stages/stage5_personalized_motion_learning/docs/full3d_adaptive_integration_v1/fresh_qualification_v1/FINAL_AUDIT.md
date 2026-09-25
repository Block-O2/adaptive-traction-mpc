# Independent post-outcome audit — fresh varied full-3D V1

Date: 2026-09-23. Auditor scope: frozen source, sealed case bundle,
`formal_paired_v1/STATUS.json`, all 72 arm records, raw summaries/traces,
and `ANALYSIS.json`. No case was rerun, excluded, replaced, or tuned; no
frozen source, config, gate, seed, or historical result was edited.

## Decision

**Result-integrity audit: PASS with material limitations below. Scientific
qualification: FAIL. Terminal classification: `FULL3D_FRESH_FAILED_WITH_EVIDENCE`.**

This is not a tool/quota block or an inconclusive empty run: 21 case keys
completed real physical commissioning in all three arms, yet no arm completed
the registered task. Nine additional runner exceptions (three case keys ×
three arms) arose deterministically from the frozen V1 initial-support
candidate validation before any physical time step. The preregistration
explicitly keeps preserved runner exceptions in the 24-key denominator.
Those exceptions are an executable-domain defect of this version, not a
license to omit or regenerate the three cases. They limit the claim to
21 physically commissioned case keys plus nine preserved pre-step failures;
they do not prevent a decisive FAIL, because even the 21 physically run
adaptive cases produced 0 completions. A repaired controller/generator would
be a new version and require fresh held-out cases.

## Provenance and physical execution

- Freeze manifest SHA-256:
  `8545edac3f6d2febbac1c129fc86021a3547b96c5d62dbeae41d23d84044fa9c`;
  independent seed manifest SHA-256:
  `e6352b342f63ac20582b631597ec37fbe5bc0e05ee840f6cd359ba8da44a3b9c`.
  All 309 frozen source/config/asset hashes still match, including the
  native backend. Recorded branch/HEAD match the freeze. The exact sealed
  24-case bundle and 34-proposal ledger were independently regenerated
  before execution and remain case-hash bound to every arm.
- `STATUS.json` (SHA-256
  `dab8cd53b6bc45b23505108d50efba9a0200dcc55daf0c7a9e5d61060b6c6f6d`)
  is `FORMAL_ALL_ARMS_COMPLETED`: 72/72 records, 63 complete episode
  artifacts and nine preserved `runner_exception.json` artifacts. Every
  recorded artifact SHA-256 and paired case SHA-256 matches disk. No formal
  case/arm is missing or replaced.
- Source call path is `run_executed_case` →
  `Stage5CR12SensorBoundaryPlant` → the CR12 six-actuator MuJoCo model with
  Human V2, physical compliant cuff and bed →
  `plant.apply_executable_command` → twenty `plant.step()`/`mujoco.mj_step`
  calls per 5 ms control interval. The evaluation-only monitor runs after
  every 0.25 ms step and once at TASK handoff. All 63 episode traces have
  nonzero physical CR12 torque during commissioning; ten have nonzero task
  torque. Physical TASK intervals total 5,646. All 63 record actuation
  enabled, controlled planner-delay replay, the same config snapshot, 0.25 ms
  physics, 5 ms control, 20 ms adaptation cadence, and no MuJoCo warning.
  This is synchronous timing replay, not operating-system or hardware
  real-time certification.
- For each of the 21 case keys with all episode artifacts, the three arms'
  commissioning arrays for Human truth, CR12 q and applied CR12 torque are
  bitwise identical. The arms share the physical commissioning, task, plant,
  low-level execution, constraints and timing rule. The fixed arm discards
  commissioning fit; commissioning-only retains its fitted handoff but
  freezes task beta/residual; only continual adaptive updates them. Task-only
  analyzer totals are 15 attempted/15 accepted beta updates and 352 nonzero
  residual steps in adaptive, versus zero task updates in both baselines.
  The 24-key arm order was rotated by case index. These checks support
  structural comparison fairness; machine-load variation in measured
  planning times remains a simulation limitation.

## Truth boundary and metric checks

The hidden Human/geometry objects are constructed from the case to build and
initialize the physical plant. Initial CR12 q is solved from that physical
pose, which is an initial-condition operation, not an online controller
oracle. The deployable model starts from the same fixed nominal prior for
every case. `CausalMeasurementLayer` extracts robot q/dq, cuff pose/twist and
physical cuff wrench/timestamps; the observer, estimator, force map, planner
and action path receive measurements/online belief plus the registered task,
not hidden Human q/dq or true clearance. Source searches and the runtime
data flow put `truth_state` and the true-physics monitor in trace/evaluation
output only. The summary's self-declared `truth_firewall` boolean is not
itself proof; this independent source/data-flow review found no deployable
hidden-truth path. It does not prove independent identification of physical
shank length versus cuff attachment fraction or hardware sensing realism.

For all 63 episode artifacts, TASK trace has exactly N+1 observations for N
5 ms executed intervals, with uniform 5 ms boundary differences and 20
monitored physics steps per interval. The independent left-boundary
world-frame force and moment integrals agree with saved values to at most
`1.14e-9 N·s` and `1.8e-14 Nm·s`, respectively. The frozen analyzer compares
physical q/dq and reference at the same boundary, and its source uses actual
`plan_activated`/activation timestamps, not proposed activation, for stale
application. Across 63 episodes, all activated plans were at or below
100 ms age; zero stale plans were applied. On
`hip_dominant_middle_r01`, all three arms had a measured >100 ms plan,
executed the prior reference for twenty physical 5 ms intervals to the
watchdog, then rejected that plan with `plan_activated=false` and null actual
activation time. Adaptive gate 4 still fails because its own arm missed the
deadline. No claim about a real concurrent scheduler follows.

True shank/bed clearance is the physical capsule-bottom-to-bed-plane signed
distance evaluated at every integrated physics step and the task handoff
boundary; deployable session clearance is a different conservative
estimated-geometry quantity. `balanced_ordinary_r02` adaptive had a
`-0.0000074327 m` TASK-handoff true clearance and one shank-bed contact
observation despite zero TASK intervals. This is a near-zero-depth contact,
not evidence of a large collision, but the frozen zero-contact/no-negative-
clearance gate has no post hoc tolerance. The generation-side static screen
had accepted this case at `+0.00243185 m`; it did not guarantee the dynamic
commissioning handoff. `knee_dominant_near_upper_current_rom_r02` adaptive
had a measured 5 ms-boundary cuff force peak `200.0173 N`, exceeding the
unchanged 200 N gate by `0.0173 N`. Wrench peaks are only certified at the
registered 5 ms boundaries, not at every 0.25 ms physics substep.

## Frozen gates and interpretation

| Gate | Auditor interpretation |
|---|---|
| 1 provenance/firewall | PASS for record completeness and inspected source firewall, **not** 24 successful physical rollouts. The analyzer's `g1_provenance_and_count_pre_audit=true` tolerates nine explicit runner exceptions by design and must not be described as execution success. |
| 2 task completion | FAIL: adaptive 0/24; commissioning-only 0/24; fixed 0/24. Adaptive 17/24 fail at unsettled handoff, three case keys raise the shared pre-step exception, and four remaining adaptive cases fail by session clearance, no feasible waypoint, realized force, or stale deadline. |
| 3 task physical safety | FAIL: one adaptive true negative clearance/contact at TASK handoff; one adaptive force peak above 200 N; plus three adaptive runner exceptions with no task-safety trace. No adaptive task ROM or sampled acceleration violation was recorded in the runnable cases. |
| 4 timing | FAIL: one adaptive >100 ms planning deadline; stale result correctly rejected, not applied. The same case has a deadline miss in each comparator. |
| 5 completed-task tracking | FAIL by frozen rule because no adaptive completion exists. Completed-case RMSE/p95 is undefined, **not** a measured tracking-threshold exceedance. The unfavorable 7.903 deg/s nominal development dq result had been disclosed before freeze and did not change this gate. |
| 6 task adaptation exercised | FAIL: only three adaptive cases reached task updates with beta proposals, accepted beta updates and nonzero residual steps, versus the required 18/24. |
| 7 paired meaningful improvement | FAIL: 0 versus 0 completions against each comparator; no adaptive-only recovery. Jointly completed-case tracking comparisons are undefined. This does not establish method equivalence. |

There is additional safety scope to report prominently: **all 21/21
physically commissioned adaptive cases recorded shank-bed contact during
commissioning** (1,966–10,173 monitor observations). The frozen contract
explicitly logs rather than gates commissioning shank contact and applies
its no-contact criterion only to TASK, so the Auditor does not invent a
retroactive gate. Nevertheless no total-session contact-free safety claim is
supported. Of 21 runnable adaptive cases, 18 execute zero task intervals;
only three proceed into task adaptation. At the fitted handoff, the 17
adaptive `COMMISSIONING_HANDOFF_NOT_SETTLED` cases have physical Human angle
error above the registered 1 deg start tolerance (median maximum-joint
error about 3.84 deg); the estimator error is similar. The failure is thus
not merely a false post-fit state label.

The three shared runner-exception case keys are
`hip_dominant_near_upper_current_rom_r01`,
`elevated_start_ordinary_r02`, and `elevated_start_middle_r02`. Their
`ValueError: waypoint moves away from the registered phase goal` traceback
comes from `_initialize_loaded_runtime` initial-support candidate validation
before `plant.apply_executable_command` or any `mj_step`. The generation
screen checked static true clearance, initial contact and start/goal CR12
IK, not this controller candidate predicate. These are genuine V1
case-executability failures and must remain visible, but cannot be cited as
measured dynamic safety events.

Two reporting cautions: `summary.task.accepted_beta_update_count` and
`summary.task.residual_update_count` are cumulative updater counters that
include commissioning; use `ANALYSIS.json`'s `adaptation_trace`-derived
task-only counts for gate 6. Likewise a zero-interval handoff still has one
TASK boundary, so a boundary force/contact/clearance peak can be non-null
while task force integral is zero. The 21/21 commissioning contact and the
nine pre-step exceptions rule out any statement that every accepted case
completed a contact-free physical TASK trial.

`ANALYSIS.json` SHA-256:
`173c8694d0ca2859d56e10054d373d3ca37a7c01b4c499c1c78e0149a5da9f11`.
The exact recommended next step is to preserve V1 as failed formal evidence
and return to separate development; any proposed repair needs a new
versioned contract and fresh held-out seed namespace, not a V1 rerun.
