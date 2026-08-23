# Near-Extension Protective Mode

## Scope

This is a MATLAB command-interface sanity version for a dedicated
near-extension patch. It does not extend R3B/R3C/R4 recovery theory and does
not claim physical contact safety, clinical validity, or hardware readiness.
Human Model V2, the bed model, Windowed NLS, the normal taught trajectory, the
normal force-aware controller, and the existing componentwise force bounds are
unchanged.

The normal region delegates directly to
`bed_supported_v1_robot_controller`. The patch does not invert the force map
or use force to generate motion. It emits a low-speed position/velocity/
acceleration command. Measured force remains an independent hard veto that
latches `PROTECTIVE_STOP`.

## Engineering switch selection

The recommendation is `q_switch = 30 deg`. This is an engineering selection,
not a clinical threshold.

The frozen strict-taught-path, registered-robust 200 N diagnostic gives:

| Registered reserve | q2 entry | cond(A) | sigma_min(A) | observed margin |
|---:|---:|---:|---:|---:|
| 0 N | 27.020 deg | 10.124 | 0.08409 | 0.449 N |
| 5 N | 28.204 deg | 9.683 | 0.08770 | 5.364 N |
| 10 N | 29.536 deg | 9.228 | 0.09175 | 10.411 N |
| 20 N | 32.496 deg | 8.348 | 0.10070 | 20.111 N |

Thus `30 deg` sits just beyond the observed zero/5 N edge and approximately at
the 10 N engineering-reserve boundary. Nearby sensitivity is explicit: moving
the switch down toward `28.2 deg` leaves only about 5 N registered reserve;
moving it up toward `32.5 deg` corresponds to about 20 N. This is also
consistent with the force atlas: the current coordination line becomes more
poorly conditioned and force-amplifying as q2 decreases, with `cond(A)` about
13.79 at 20 degrees, 27.79 at 10 degrees, and unbounded at zero.

The snapshot is extracted from the retained local
`robust_suspended_feasibility_envelope/boundary_details.csv` with SHA-256
`3d85ccf8138f23c5bd019620178f02c3ae2d0dd71f06717dbd73f327708b119c`.
The four source rows are tracked beside the implementation so a fresh checkout
does not depend on ignored local result directories.

## Inputs and outputs

Each state-machine step receives:

- current time, measured joint position and velocity;
- measured two-component contact force for veto monitoring only;
- landing/takeoff request;
- unchanged normal reference and the unchanged normal-controller context.

It returns:

- the active state and actuation-mode label;
- in kinematic states: `q_cmd`, `dq_cmd`, and `ddq_cmd`, with force command
  absent (`NaN`);
- in `NORMAL_REHAB`: the unchanged controller's force command and details;
- veto and controller-call telemetry.

## State machine and continuity

Landing:

```text
NORMAL_REHAB -> BLEND_TO_LANDING -> KINEMATIC_LANDING -> TERMINAL
```

Takeoff:

```text
BED_START -> KINEMATIC_TAKEOFF -> BLEND_TO_NORMAL -> NORMAL_REHAB
```

At patch entry, the polynomial captures the current measured `q` and `dq`.
It does not teleport to the taught reference. A C2 quintic boundary polynomial
then follows the taught q1/q2 coordination line between 30 and 2 degrees over
4 s. Landing ends at q2 = 2 degrees with zero commanded velocity and
acceleration. Takeoff ends at the 30-degree taught-path state and matches the
normal reference velocity and acceleration before delegating back to the
existing controller. The 0.75 s beginning/end portions carry the explicit
blend state labels; they are parts of one continuous polynomial, not separate
spliced references.

If measured force is nonfinite or exceeds the unchanged 200 N component bound,
the supervisor latches `PROTECTIVE_STOP`, freezes the kinematic command at the
measured position, and issues no force command. This verifies veto routing
only. A zero-velocity command is not evidence of a physically safe hold.

## MATLAB sanity experiment

The authorized runner is:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch \
  "addpath(genpath('linkage/matlab')); run_near_extension_protective_mode_sanity"
```

The experiment uses ideal measured-state following of the emitted kinematic
command. It checks state ordering, boundary capture, takeoff handoff,
q2-terminal accuracy, force-inversion bypass, hard-veto latching, and exact
normal-controller delegation. It writes a synchronized GIF with mechanism,
joint commands, command velocity, state, force monitor, and inversion-call
status. This is smoke/sanity evidence, not a formal scientific experiment.

## What MATLAB does not validate

The present model does not contain the real robot's position/velocity command
interface, inner servo bandwidth, command latency, rate/acceleration limits,
or mode-switch semantics. More importantly, it cannot establish how a
position/velocity-controlled arm interacts with the patient's cuff, soft
tissue, mattress, friction, unilateral contact, load transfer, or unexpected
patient motion. The ideal-following sanity run therefore cannot validate
contact force transients, impact at takeoff/landing, a physically safe stop,
or whether q2 = 2 degrees is reachable under real support and comfort limits.

## MuJoCo entry requirements

Before the next main stage, specify and validate:

- the robot-side position/velocity interface, update rate, limits, latency,
  tracking error, and controller-mode transition behavior;
- cuff/contact geometry, compliance, damping, friction, unilateral separation,
  and force-sensor location/noise/latency;
- bed/support contact and the initial load-bearing state at q2 = 2 degrees;
- force-veto response semantics, including braking behavior and what external
  support makes a stopped state physically admissible;
- MuJoCo acceptance checks for command continuity, contact impulse/peak force,
  tracking error, terminal error, no penetration/contact loss, and repeatable
  takeoff/landing under the approved uncertainty cases.

No q-switch, force, or terminal-angle value in this sanity version is a
clinical safety threshold.
