# Stage 5 Architecture Recovery V1 — Immutable System Contract

Status: immutable after initial creation on 2026-09-22.

## Scientific objective

Recover and test the intended Stage 5 chain:

`deployment observations -> session geometry / Human task-state estimation -> effective Human dynamic personalization -> state-feedback Human-waypoint MPC`

This campaign stops at the Phase 3 entry check. It must not implement value
learning, imitation learning, or reinforcement learning.

## Allowed structural prior

- CR12 robot structure/kinematics and legitimate robot-side calibration.
- The Human V2 planar two-link lower-limb structural family, hip/knee topology,
  and joint ordering.
- A cuff attached to the shank inside a predefined physically legal family.
- Registered ROM and engineering motion limits.
- Environment and sensor calibrations that a real deployment can legitimately
  obtain during commissioning.

No additional structural prior may be introduced silently.

## Session-specific unknowns and source rule

At minimum, the deployment source must be audited for Human/mechanical-leg base
placement, joint centers, link geometry used by control, cuff attachment,
initial configuration, Human q/dq, Jacobian geometry, wrench-to-generalized
effect geometry, robot/Human frame relationships, and every state used by Human
dynamics or HWMPC.

Every control-critical session quantity must end as exactly one of:

- `MEASURED`
- `CALIBRATED`
- `ONLINE_ESTIMATED`
- `STRUCTURAL_PRIOR`

`SIMULATION_TRUTH`, `HIDDEN_ORACLE`, and `FIXED_NOMINAL` are forbidden final
sources for a session-specific quantity the original architecture intended to
recover. A historical frozen experiment does not establish a permanent known
quantity.

Effective Human dynamics remain session-specific unknowns. A reduced or
control-effective representation is allowed only when it is identifiable from
deployment observations and supplies all downstream control quantities. Dynamic
parameters must not absorb geometry error and be reported as geometry recovery.

## Deployment observations and truth firewall

Deployable estimation may use only causal robot state, end-effector/cuff
pose/twist, F/T measurements, legitimately calibrated robot/tool/environment
transforms, and causal task history whose real availability is supported by
repository, laboratory, or official documentation.

Simulation truth is permitted only for hidden setup generation, evaluation,
estimation-error scoring, explicitly isolated oracle baselines, and post-run
diagnosis. It is forbidden in deployable estimator inputs, controller state,
deployable Jacobians, generalized-force mappings, candidate generation, HWMPC
prediction, dynamic-ID inputs, model-promotion decisions, and action selection.

## Phase gates

### Phase 0 — assumption and scope recovery

Pass requires an evidence-backed Stage 1-to-5 timeline, a complete current
data-flow trace, a truth/source matrix with no unclassified control-critical
Human quantity, full q/dq/Jacobian/generalized-effect provenance, exact frozen
or bypass points, and independent Auditor approval.

### Phase 1 — geometry/task-state estimator recovery

Identifiability precedes estimator claims. Before held-out evaluation, freeze
outputs, development/held-out families, ranges and rationale, metrics,
thresholds, seeds, failure/exclusion rules, experiment budget, and truth
firewall. Evaluate q, dq, geometry or control-effective equivalent, cuff pose,
Jacobian, generalized effect, convergence/stability, prior sensitivity, setup
variation, and geometry-bias compensation by dynamics. Pass requires all
preregistered held-out gates, no hidden nominal geometry, no truth leak,
downstream sufficiency, and independent Auditor approval.

### Phase 2 — formal unknown-setup validation

Use genuinely hidden bounded setups spanning placement, initial configuration,
segment geometry, cuff attachment, effective dynamics, and other Phase 0
unknowns. Compare: A oracle geometry+oracle dynamics; B estimated geometry+
oracle dynamics; C estimated geometry+estimated dynamics; D wrong fixed nominal
geometry. Separate geometry/state, dynamics, model construction, and execution
errors. Preserve every failure. Once held-out evaluation begins, do not tune on
it, change thresholds/ranges, or add post-hoc exclusions. Pass requires the
deployable stack to meet frozen gates, dynamics not to hide geometry error,
wrong nominal geometry to be distinguishable when material, no truth leak, and
independent Auditor approval.

### Phase 3 entry check

Only the minimum smoke integration is permitted. Existing state-feedback HWMPC
must consume estimated deployable Human state/model without oracle geometry,
without a forced fixed-r path, and without restoring the old detailed 5–20 ms
robot/interface predictor. Candidate construction, version/provenance, and a
non-oracle invalid/uncertain-state failure path must be demonstrated.

## Integrity and workflow

- Builder owns implementation and evidence; an independently contextualized,
  adversarial Auditor reviews each gate and must not edit production source.
- Maximum three Builder-Auditor-repair cycles per phase.
- Formal studies freeze hypotheses, setup/split, allowed inputs, hidden values,
  metrics, gates, seeds/rules, budget, exclusions, and truth firewall before
  held-out results are inspected.
- Failed studies remain evidence. Any revised design returns to development,
  is versioned and preregistered, and uses fresh held-out cases.
- Historical Stage 3/4 artifacts are immutable. Campaign outputs use the
  `architecture_recovery_v1` namespace.
- Physical robot actuation, human experiments, private-data upload, paid compute,
  staging, committing, and pushing are not authorized.

## Terminal states

`PHASE_3_READY` is permitted only when Phases 0–2 and the Phase 3 entry check
all pass their exact gates, all session sources comply, deployable paths contain
no truth, dynamic personalization does not hide geometry error, the Auditor
approves the full chain, limitations are explicit, and no gate was weakened.

Otherwise stop at the first justified state:

- `BLOCKED_IDENTIFIABILITY`
- `BLOCKED_CONTRACT_CHANGE_REQUIRED`
- `BLOCKED_NEW_SENSOR_OR_CALIBRATION_REQUIRED`
- `BLOCKED_REPAIR_LIMIT`
- `BLOCKED_REPOSITORY_RULE`
- `BLOCKED_TOOL_OR_QUOTA`
- `BLOCKED_OTHER_WITH_EVIDENCE`

The complete originating user instruction is preserved outside this repository
at the task attachment path recorded in `RECOVERY_PHASE_STATUS.md`; this file is
the immutable in-repository operational contract.
