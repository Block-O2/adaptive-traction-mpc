# MuJoCo Protective Mode V1

## Scope and evidence class

This stage is a minimal MuJoCo engineering smoke for the MATLAB
near-extension protective-mode command interface. It asks whether the
kinematic patch remains mechanically plausible after adding actuator, cuff,
gravity, and unilateral bed-contact dynamics.

The result is a retained negative engineering smoke, not a formal or
authoritative scientific result, clinical threshold, hardware validation, or
robot API integration. It does not include Windowed NLS, R3B, R3C, R4, an
uncertainty matrix, or a large parameter sweep. Human V2, the MATLAB taught
trajectory, q2 terminal at 2 degrees, q-switch baseline at 30 degrees, and the
200 N veto threshold were not changed after observing the result.

## M1 model assumptions

### Human leg

- two sagittal MuJoCo hinge joints with the retained coordinates
  `q1 = thigh absolute angle` and `q2 = positive knee flexion`;
- nominal Human V2 height/mass `1.72 m / 75 kg`;
- exact retained thigh/shank lengths `0.436880 / 0.400760 m`, masses
  `7.425 / 4.500 kg`, COM locations, planar y-axis inertias, distal cuff
  location `sc = 0.360684 m`, passive `K = diag(10,10)`, passive
  `B = diag(5,5)`, and ROM `[0,80] / [0,100] deg`;
- MuJoCo requires a three-dimensional inertia tensor. The dynamically active
  planar `Iyy` is unchanged; unused `Ixx=Izz=0.51 Iyy` is an explicit M1
  completion assumption.

### Bed and contact

- horizontal plane at `z = 0.012 m`;
- unilateral MuJoCo compliant contact only; bed support force is read from the
  contact solver and is never assigned by the script;
- friction `0.70`, contact `solref = [0.020 s, 1.0]`, `solimp` width
  `0.003 m`, and thigh/shank capsule radii `0.050 / 0.045 m`;
- hip height `0.062 m`, selected geometrically so the terminal thigh is
  tangent to the bed at reset rather than initialized with hidden penetration.

### Robot and cuff

- a `0.5 kg` planar x/z carriage with two MuJoCo motor actuators;
- the abstract actuator adapter accepts Cartesian position and velocity
  commands, applies `Kp = 1800 N/m`, `Kd = 90 Ns/m`, gravity compensation for
  the carriage only, and clips each motor at `+/-200 N`;
- this is an explicit M1 interface assumption, not a claim about a real robot,
  controller, SDK, update rate, or manufacturer limit;
- the cuff is a tension-only compliant MuJoCo spatial tendon with `15 mm`
  slack length, `10 mm` commanded working extension, `1800 N/m` stiffness,
  and `35 Ns/m` damping. It can go slack and extend, but it is not an
  anatomically resolved bilateral cuff;
- interaction force sensing is reconstructed from the MuJoCo tendon
  length/velocity and this frozen constitutive law. It is simulation state,
  not a modeled hardware F/T transducer.

The simulation step is `1 ms`; the command/sensor period is `5 ms`. The
kinematic modes command the MuJoCo robot servo. No actuator applies ideal
joint torque or endpoint force directly to the human joints.

## Controller and switching

The commanded sequence is:

```text
BED_START
-> KINEMATIC_TAKEOFF
-> NORMAL_REHAB
-> KINEMATIC_LANDING
-> TERMINAL
```

Takeoff and landing retain the four-second MATLAB C2 boundary trajectory.
They capture measured q/dq. A second C2 Cartesian correction makes the actual
robot position/velocity/acceleration command continuous even if the measured
human state differs from the previous normal reference. At the two mode
boundaries, the recorded one-sample position steps are `0.203 mm` and
`0.0375 mm`; these are finite `5 ms` trajectory increments, not mathematical
command discontinuities. Interaction-force steps are `0.156 N` and `0.149 N`.

`NORMAL_REHAB` uses the unchanged Human V2 taught reference from the 30-degree
outbound crossing, through peak flexion/hold, to the 30-degree return crossing.
The fixed M1 controller maps the nominal q/dq reference to a Cartesian cuff
target and executes it through the same bounded x/z servo. It does not use
Windowed NLS or force inversion.

The automatic hard veto latches when reconstructed cuff force is nonfinite or
exceeds 200 N. It executes a 0.25 s C2 Cartesian braking command and then
holds the end-effector target. The baseline never reached 200 N, so a separate
manual-veto probe was run at `t = 2.5 s` to exercise the identical braking
path. That probe is not represented as a measured-force exceedance.

## Registered engineering-smoke result

Retained local output:

```text
linkage/results/local/mujoco_protective_mode_v1/20260823_080555
```

### Concise result

| Question/metric | Observed result |
|---|---:|
| Requested state sequence | complete at command/state-machine level |
| Physical takeoff endpoint | q2 = -0.0734 deg versus 30 deg command |
| Physical landing endpoint | q2 = 0.7139 deg versus 2 deg command |
| Stable terminal mean | q2 = 0.7139 deg; bed force = 65.80 N |
| Observed q2 range | -0.159 to 2.000 deg |
| Peak interaction force | 176.15 N; no automatic 200 N veto |
| Peak bed force | 481.13 N substep peak during initial settling |
| Maximum bed penetration | 1.776 mm |
| Maximum cuff extension | 97.86 mm |
| Inactive-cuff samples during motion modes | 283 |
| Bed-contact transitions | 49; chatter observed |
| Takeoff->normal force near switch | 46.37 N peak; 0.156 N sample step |
| Normal->landing force near switch | 44.08 N peak; 0.149 N sample step |
| Baseline classification | `TERMINAL_UNSTABLE_OR_INCOMPLETE` |

The physical takeoff did not occur. During BED_START, the passive/gravity/bed
system settled from commanded q2 = 2 degrees to approximately 0.71 degrees.
During takeoff and normal reference motion, q2 stayed near extension while the
robot target moved away. The tension-only cuff therefore accumulated almost
98 mm extension and force rose gradually to 176 N. This is a load-path and
contact-authority failure, not a numerical crash or a switch impulse.

The bed/robot transfer was not smooth. Bed force initially peaked at 481 N,
then the baseline recorded 49 bed-contact transitions. The interaction-force
trace itself did not show a sharp normal/kinematic switch spike; its dominant
feature was the slow force build-up caused by the stalled human state and
growing cuff extension.

The requested 2-degree terminal was not a stable physical equilibrium under
the current M1 support/cuff assumptions. The final settled value was about
0.714 degrees, and the knee briefly crossed the nominal lower ROM by
0.159 degrees despite the MuJoCo joint limit compliance. Thus the MATLAB
terminal command result does not carry over as a physical-contact result.

### Veto braking probe

The manual probe was injected halfway through the failed takeoff, when the
human knee was already essentially stalled. It produced:

| Metric | Observed value |
|---|---:|
| Human q2 braking distance | 0.000488 deg |
| Robot end-effector braking distance | 0.669 mm |
| Post-veto peak interaction force | 11.44 N |
| Reported q2 settling time | 0 s because q2 was already below 1 deg/s |

This verifies the actuator-side veto/braking route but is not evidence for
braking a successfully moving limb. A meaningful moving-state force-veto test
must wait until the baseline can physically take off.

## q-switch sensitivity gate

The requested `20 / 25 / 30 / 32.5 deg` sensitivity was not run. The runner
contains the registered four-value gate, but executes it only if the 30-degree
baseline is mechanically complete. Because baseline takeoff failed, changing
q-switch would answer a different question and could hide the more basic cuff
authority/contact failure.

The MATLAB 30-degree value remains an engineering baseline derived from the
quasistatic force atlas. This MuJoCo result neither validates nor compares it.

## MATLAB to MuJoCo change in conclusion

- Preserved: the supervisor sequence and the actual robot actuator command can
  be made C2/continuous; the near-extension path does not call force inversion.
- Rejected for this M1 model: a continuous kinematic command is not sufficient
  to make the human leg follow the patch.
- Rejected for this M1 model: commanding terminal q2 = 2 degrees does not make
  2 degrees a stable physical terminal under gravity, cuff, and bed contact.
- Newly exposed: a tension-only compliant cuff can accumulate large extension
  and force while providing insufficient generalized knee authority.
- Newly exposed: natural bed contact introduces an initial load transient and
  substantial contact chatter that MATLAB ideal following could not show.
- Still unresolved: whether a real bilateral cuff and real robot
  position/velocity controller can supply the required two-dimensional load
  path without unacceptable pressure, transient force, or loss of contact.

## Decision before fixed control or Windowed NLS

This result is not ready for Windowed NLS. Identification would be observing a
failed and structurally inadequate M1 load path, not a valid normal-rehab
plant/controller interaction.

It is also premature to reconnect the existing normal force-aware controller
as the next fix. Before controller work, the project needs:

1. the real robot command/feedback/force contract;
2. a justified bilateral cuff/contact geometry with pressure/compliance and
   force-sensor placement;
3. a mechanically admissible BED_START equilibrium and a non-chattering bed
   contact representation;
4. a demonstrated fixed-model takeoff to q-switch and stable return to 2
   degrees under the unchanged force bound;
5. only then, a moving-state automatic-force-veto braking validation.

No controller, contact, stiffness, force limit, initial posture, trajectory,
q-switch, or terminal value was tuned after the negative baseline.

## Reproduction

The local environment used MuJoCo `3.10.0` in conda environment `mpc_learn`.

```text
PYTHONPATH=src MPLCONFIGDIR=/tmp/mujoco-protective-mpl \
  conda run -n mpc_learn python scripts/run_mujoco_protective_mode_v1.py
```

The runner writes a model snapshot, JSON summary, concise CSV, full baseline
and veto time series, synchronized PNGs, and one complete-action GIF. Local
outputs remain ignored and are not promoted as authoritative evidence.

## Verification

- repository Python suite: `108 passed` in the `mpc_learn` environment;
- inherited MATLAB protective-mode contract suite: `9 passed` in MATLAB
  R2025b Update 1;
- Python bytecode compilation and `git diff --check`: passed;
- `pyflakes`/`ruff`: not available in the retained environment, so no lint
  result is claimed and no dependency was added solely for this task.
