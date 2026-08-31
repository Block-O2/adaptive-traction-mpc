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
