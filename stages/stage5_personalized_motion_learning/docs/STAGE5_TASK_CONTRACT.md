# Stage-5 Task Contract

## Purpose and non-goals

This document defines the future goal-directed task presented to CEM-MPC. It
does not implement the controller, select scientific weights/limits, authorize
an experiment, or prescribe a full `q1/q2` time trajectory. All quantities use
SI units internally; angles shown in degrees are reporting conveniences.

## Episode and phase semantics

One episode is exactly one ordered cycle:

`OUTBOUND -> HOLD -> RETURN -> COMPLETE`

Safety termination may occur from any active phase:

`active phase -> ABORTED`

`COMPLETE` and `ABORTED` are distinct terminal statuses. Detailed timeout,
BRAKE, constraint, measurement, and numerical causes are retained as the abort
reason. An aborted episode is not completed and must not be encoded as a
zero-cost success.

The task input is a `GoalTaskSpec`, not a reference trajectory. At minimum it
contains:

- registered start region `Q_start`;
- registered goal region `Q_goal`;
- allowed Human ROM/path region `Q_allowed`;
- outbound and return progress definitions;
- outbound hold and return-target completion predicates;
- maximum episode/phase durations and hard kinematic/dynamic limits;
- collision/contact policy and termination policy;
- objective definitions, normalization, and weights;
- version/fingerprint of this entire contract.

## Start/goal ROM contract

The frozen Human V2 simulation ROM remains the outer model domain:

- `q1 in [0 deg, 80 deg]`;
- `q2 in [0 deg, 100 deg]`.

These outer bounds are not automatically the allowed task region. Every future
Experiment Spec must define `Q_allowed`, `Q_start`, and `Q_goal` as subsets of
the geometry-validated, constraint-feasible region. A goal outside that region
is an invalid task, not an MPC failure.

The current baseline start `(5 deg, 10 deg)` and previously exercised goals
such as `(20 deg, 35 deg)`, `(38 deg, 80 deg)`, and `(45 deg, 84 deg)` are
registered simulation fixtures only. This contract does not silently choose
one as the universal rehabilitation goal. The exact start/goal regions and
tolerances remain Experiment-Spec fields.

## True start and completion conditions

An episode may begin only when all of the following are true for a specified
settling interval:

- estimated/measured Human state is inside `Q_start`;
- joint speed is inside the registered start-settled bound;
- cuff pose/interface deformation and measured wrench are finite;
- required measurements and model versions are valid;
- no Safety Filter/BRAKE/structural fault is active.

Outbound completion requires the state to remain in `Q_goal` for the complete
registered goal-hold duration while satisfying all hard constraints. Merely
crossing a goal coordinate once is insufficient.

True episode completion requires all of the following:

1. valid outbound completion;
2. valid goal hold;
3. valid return to `Q_start` with joint speed inside its settled bound;
5. no unresolved BRAKE, abort, hard-constraint violation, collision, invalid
   measurement, nonfinite state, or numerical warning;
6. an explicit `COMPLETE` terminal record.

Timeout, partial geometric progress, zero velocity outside the completion
regions, or simply stopping simulation time is not true completion. HOLD must
remain dynamically/safely feasible; stopping motion alone does not prove a
safe hold.

The Stage-5 task module supplies explicitly provisional configurable defaults
for software validation. They are not formal or hardware limits; an approved
Experiment Spec must review or replace them before scientific execution.

## No prescribed full time trajectory

The controller receives the current estimated state, active phase, phase goal,
allowed region, and remaining time budget. It does not receive a complete
time-indexed sequence of `q1_ref(t), q2_ref(t)` or their derivatives.

CEM-MPC may internally predict state/action sequences over its finite horizon.
The executed low-level command may also include a one-step local pose/twist
target derived from the selected first predicted transition. Neither is a
predefined episode-long `q1/q2` trajectory.

## Motion and progress contract

Progress is phase-relative and state-based:

- outbound progress increases from `Q_start` toward `Q_goal`;
- return progress increases from `Q_goal` toward `Q_start`;
- hold progress is accumulated valid dwell time inside the applicable region.

The exact scalar progress coordinate must be versioned. It may be based on
normalized distance or a registered path coordinate, but must not use
God-view simulator-only state online. Small reversals may be allowed when
needed for feasible, smooth, or safer motion; any monotonicity/corridor rule is
an explicit constraint, not an undocumented preference.

The current minimal implementation reports only clipped, ROM-normalized
distance reduction to the active phase target. This scalar is diagnostic: it
does not trigger transitions, impose monotonicity, select a `q1/q2`
coordination ratio, or define a path corridor.

The allowed-motion contract must reject predicted states outside `Q_allowed`
and must define behavior near singular/poor-transmission regions. A goal or
path is invalid if no feasible outbound, hold, and return contract exists.

## Duration and speed treatment

Time is handled in two separate ways:

- **hard:** maximum episode/phase duration, joint speed, acceleration, action,
  action-rate, and any required deceleration/stopping constraints;
- **objective:** elapsed-time or lack-of-progress cost encouraging efficient
  completion without prescribing when each joint must reach an intermediate
  angle.

A faster episode is not preferable if it violates force, kinematic, collision,
execution, or safety constraints. The exact time cost, budgets, speed limits,
and acceleration limits remain Experiment-Spec parameters for formal work.
The current software checkpoint uses explicitly provisional independent-joint
engineering limits of `[45, 75] deg/s` and `[300, 600] deg/s2`; they neither
specify a time trajectory nor constrain the q1/q2 coordination ratio.

## Cuff-force decomposition

Let `R_WC` be the measured/registered cuff rotation, `F_W` the physical cuff
force in world coordinates, and `M_W` the physical cuff moment about the
registered cuff reference point. Define

- `F_C = R_WC^T F_W = [F_axial, F_tangential, F_radial]`;
- total force: `F_total = ||F_W|| = ||F_C||`;
- signed shank-axis force: `F_axial = e_x^T F_C`;
- transverse vector: `F_transverse_C = [0, F_tangential, F_radial]`;
- transverse magnitude: `F_transverse = sqrt(F_tangential^2 + F_radial^2)`;
- signed principal radial force: `F_radial = e_z^T F_C`;
- cuff moment in cuff coordinates: `M_C = R_WC^T M_W` and
  `M_total = ||M_W||`.

The reference point, sign, and frame must accompany every logged wrench.
Interface spring force, reconstructed physical cuff force, low-level commanded
force, allocator-predicted force, and MuJoCo contact/equality diagnostics are
different signals and must not be interchanged.

## Hard constraints

The future MPC/safety contract must explicitly represent, validate, and log:

- allowed Human joint region and any phase/path corridor;
- Human joint velocity and acceleration bounds;
- generalized action and action-rate bounds;
- total cuff-force and component-specific force bounds;
- cuff-moment/component bounds;
- robot joint position, velocity, torque, and command feasibility;
- cuff translation/rotation deformation where required by Plant v1 validity;
- robot self-collision and any registered Human/bed/environment collision or
  contact policy;
- finite state/model/wrench and numerical-health requirements;
- first-action executable screening and Safety Filter/BRAKE feasibility.

Not every item above is currently predicted by Stage-4 MPC; the interface
audit in `STAGE5_LEARNING_CONTROL_CONTRACT.md` records those gaps. Hard
constraints cannot be traded against objective improvement.

The existing `200 N` value remains only the Stage-4 simulation engineering
force gate. It is not a clinical threshold, hardware-certified limit, measured
tissue limit, comfort limit, or automatically appropriate component-wise
bound. This task defines no replacement threshold.

## Performance objectives

Subject to every hard constraint, candidate objectives may include:

- outbound/return goal-distance and hold-error cost;
- elapsed-time or lack-of-progress cost;
- cumulative total force, for example `integral ||F|| dt` and/or a registered
  squared-force cost;
- cumulative axial, transverse, and radial force terms, preserving sign when
  physically meaningful;
- cumulative cuff-moment cost;
- generalized action effort;
- action, wrench, acceleration, and velocity smoothness/slew;
- terminal remaining-cost estimate from the published value model.

Reporting metrics and optimization penalties are not necessarily identical.
Every term must define units, normalization, aggregation, and weight before a
formal experiment. No weight is frozen by this contract.

## Objective versus constraint rule

| Quantity | Objective role | Hard-constraint role |
|---|---|---|
| goal/progress error | encourage completion and useful progress | goal/return regions define true completion; allowed path may be hard |
| elapsed time | encourage efficient completion | phase/episode timeout terminates non-success |
| force components and moment | reduce cumulative interaction | registered maxima/rates remain non-negotiable |
| velocity/acceleration | smooth motion | registered limits remain non-negotiable |
| action/action slew | reduce effort and abrupt commands | actuator/execution feasibility remains non-negotiable |
| collision/contact | no reward tradeoff | permitted/forbidden contact policy is hard |
| learned value | rank feasible long-term outcomes | cannot relax or replace any constraint |

## Episode outcome record

The terminal record must distinguish at least:

- `COMPLETE`;
- `TIMEOUT_OUTBOUND`, `TIMEOUT_HOLD`, or `TIMEOUT_RETURN`;
- `BRAKE_TERMINATED` or `ABORTED`;
- `HARD_CONSTRAINT_VIOLATION`;
- `COLLISION_OR_CONTACT_VIOLATION`;
- `INVALID_MEASUREMENT_OR_MODEL`;
- `NONFINITE_OR_NUMERICAL_FAILURE`.

The first terminal cause, active phase, progress, final state, final wrench,
constraint margins, and recovery/hold status must be retained.

## Current minimal software representation

`configs/stage5_goal_task_v1.json` loads into immutable `GoalTaskSpec`; the
immutable `GoalTaskState` advances through `OUTBOUND`, `HOLD`, `RETURN`, and
one of the terminal phases `COMPLETE` or `ABORTED`. The transition is pure and
uses only controller-available estimated/measured `q`, `dq`, optional `ddq`,
sample duration, and an optional external abort reason. A separate immutable
`ControllerCompletionMargin` can only tighten phase decisions; it cannot alter
or relax the actual `GoalTaskSpec` completion set. MuJoCo truth is excluded
from this online path.

The provisional low/moderate software-validation fixture is:

| Field | Provisional value |
|---|---:|
| start/return target | `(5 deg, 10 deg)` |
| outbound goal | `(20 deg, 35 deg)` |
| q bounds | `q1: 0--80 deg`, `q2: 0--100 deg` |
| angle completion tolerance | `(1 deg, 1 deg)` |
| velocity completion tolerance | `(2 deg/s, 2 deg/s)` |
| outbound hold | `0.5 s` uninterrupted valid dwell |
| common active-phase timeout | `10.0 s` |
| provisional task velocity limits | `(45 deg/s, 75 deg/s)` |
| provisional task acceleration limits | `(300 deg/s2, 600 deg/s2)` |
| controller-only completion margin | angle `(0.05, 0.10) deg`; velocity `(0.75, 1.50) deg/s` |

These values are interface-test defaults, not a formal Experiment Spec,
clinical thresholds, or hardware-qualified limits. The actual completion
tolerances remain `(1, 1) deg` and `(2, 2) deg/s`; the margin only delays an
online transition until the estimate lies inside their conservative subset.
