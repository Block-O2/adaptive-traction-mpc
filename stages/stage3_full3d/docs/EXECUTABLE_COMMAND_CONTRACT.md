# Executable Command Contract

Phase 1 establishes one low-level realization path. It does not change MPC
candidate feasibility, costs, horizons, population, trust, the 200 N gate, or
add a reference manager or safety supervisor.

The pure Stage-3 API is
`traction_mpc_stage3.executable_command.preview_executable_command(...)`. It
receives the measured cuff/robot state, Cartesian target, the existing
allocator's world-frame wrench, the Jacobian at the actual cuff point, bias
torque, and torque limits. It returns `ExecutableCommandPreview`, including:

- realized position, velocity, allocator, and total translational force;
- the raw feedback terms and the unchanged legacy component-clipping result;
- orientation, angular-velocity, allocator, and total moment;
- translational norm, exact margin to the 200 N gate, and gate classification;
- cuff-point Jacobian, unclipped joint torque, clipped command torque, and the
  fixed 5 ms execution period.

`CoupledUR10eHumanV2.preview_executable_command(...)` supplies the live plant
state to that pure API. `apply_nominal_cartesian_control(...)` calls the preview
and applies the returned result; it contains no second realization formula.
The measured Stage-4 path delegates to the same pure function. Its
`preview_stage4_executable_command(...)` adapter invokes the existing Stage-4
allocator exactly once before calling the shared contract.

The default `ATTACHMENT_FROM_CUFF` remains the historical identity transform.
`ENGINEERING_ATTACHMENT_FROM_CUFF` is the opt-in 140 mm side-standoff derived
from committed MuJoCo wrist/cuff/shank geometry. It is a simulation engineering
surrogate, not CR12 hardware truth or calibration. Both the coupled model and
measured-state preview evaluate the Jacobian at the selected cuff point.

## Phase 2: CEM first-action screening

Stage 4 binds the measured robot/cuff state, selected geometry, target, gains,
Jacobian, bias torque, limits, and existing allocator for one 5 ms control
interval. Every CEM candidate's first action is then passed through the shared
Stage-3 `preview_executable_command(...)`. Candidate-invariant realization
terms may be prepared once, but the per-candidate allocator wrench, total force,
200 N norm classification, and corresponding torque are still produced by the
same Stage-3 contract.

Candidates whose first command is not executable-force feasible are excluded
before the existing cheap 15-step Human-space prediction and elite selection.
The horizon, population, elite count, iteration count, objective, trust, and
runtime force gate are unchanged. If no candidate survives, `solve()` returns
`action=None` with `status="NO_SAFE_ACTION"`; it does not substitute a seed,
warm-start, previous, zero, or least-bad action. No HOLD, BRAKE, safety
supervisor, or reference manager is part of this phase.

## Phase 2.5: batched first-action preview

`prepare_executable_command_context(...)` binds all candidate-invariant
low-level terms once. `preview_executable_commands_batch(...)` then consumes
the allocator wrenches for an entire CEM population and returns the same force,
moment, norm, margin, feasibility, and torque fields candidate by candidate.
Stage 4 prepares its unchanged allocator geometry/factors once and passes all
32 first actions through this Stage-3 batch API in their original RNG order.

The scalar API remains as the execution/reference contract and is implemented
through the same prepared-context realization. Tests require identical
feasibility masks, CEM status, selected action, objective, and selected/actual
command identity for nominal, partially infeasible, and zero-safe cases. This
batching changes implementation scheduling only; it adds no controller term,
threshold, approximation, supervisor, or reference behavior.
