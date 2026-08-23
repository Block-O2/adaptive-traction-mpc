# MuJoCo Physical Interface M1.5

## Scope and evidence class

This stage diagnoses the failed MuJoCo V1 load path before any controller or
identification work. It is retained engineering-smoke evidence, not a formal
experiment, hardware validation, or clinical statement.

The 200 N actuator/force-veto bounds, q2 terminal at 2 degrees, q-switch at 30
degrees, Human V2 parameters, normal taught trajectory, initial postures, and
V1 servo gains were not changed. No Windowed NLS, R3C, recovery logic,
q-switch sensitivity, or full protective-mode rerun was executed.

## Repository audit and fact boundary

The repository contains no evidence for the real cuff construction, cuff
preload, attachment orientation, allowed slip, pressure area, robot command
API, inner-loop gains, force-sensor placement, or bed material law. Those
items remain hardware blockers.

The current MuJoCo topology is:

```text
2-DOF Human V2 leg -- distal shank site -- spatial tendon -- robot x/z carriage
        |                                                        |
 unilateral capsule/plane bed contact                  bounded motor servo
```

The V1 tendon has a 15 mm rest length, 1800 N/m stiffness, and 35 Ns/m
damping. It is unilateral and supplies one scalar axial tension. It can go
slack, cannot push, and cannot directly transmit an independent tangential
force. Therefore it is not mechanically equivalent to a fixed cuff.

The temporary comparison model is a MuJoCo `connect` constraint between the
shank cuff site and a robot attachment site 15 mm below the robot origin. It
is a bilateral point constraint, providing effective x/z translation coupling
in this planar model, and uses direct-format nominal solver
parameters `1800 N/m` and `35 Ns/m`, with `solimp = [0.95,0.99,0.001]`.
The robot mass, servo, update rate, and +/-200 N axis bounds are identical to
V1. This point coupling is a simulation hypothesis: it does not model cuff
orientation, contact patch, pressure, wrapping, slip, or a real robot API.

## Diagnostic protocol

### BED_START equilibrium

The unchanged q2=2 degree initial state was simulated for 3 s. The robot
position command was held fixed, and bed support arose only from MuJoCo
contact. Joint state, contact force, penetration, contact-count transitions,
and the complete MuJoCo generalized-force balance were recorded.

### Paired local authority probes

For each interface and each initial q2 in `2 / 10 / 20 / 30 deg`, two
independent probes were run:

- a positive 2 mm flexion-tangent robot command;
- a negative 2 mm extension-tangent robot command.

Each command used a one-second C2 profile with 3.75 mm/s peak commanded speed.
Every probe was paired with an identical no-probe hold rollout from the exact
same initial state. Reported `Delta q2`, robot displacement, and force change
are probe-minus-hold values. This subtraction isolates incremental actuator
influence without adding a hidden joint lock or posture-support force.

The requested postures are not static equilibria in this model. The paired
metrics are therefore short-horizon transient authority evidence, not static
gains or a successful posture-hold test.

## BED_START result

| Metric | Observation |
|---|---:|
| Classification | `SETTLED_OFF_REQUESTED_TERMINAL` |
| Initial q1 / q2 | 0.676 / 2.000 deg |
| Settled q1 / q2 | -0.00471 / 0.71390 deg |
| Final-window peak speed | approximately 0 deg/s |
| Settled bed force | 65.795 N |
| Initial substep bed-force peak | 481.129 N |
| Maximum penetration | 1.7759 mm |
| Net bed-active transitions | 1 |
| Contact-count transitions, first 0.5 s | 132 |
| Contact-count transitions, 0.5--1.0 s | 129 |
| Contact-count transitions, final 0.5 s | 0 |
| Settled contact count | 3 |
| Generalized-force residual norm | 4.34e-15 Nm |

The current initial condition is not a 2-degree contact equilibrium. Gravity,
passive joint torque, compliant joint limits, and initially unloaded bed
contact cause a fast drop, a 481 N load-establishment peak, and switching
between two and three capsule/plane contact points. After approximately one
second, q/dq, net bed support, penetration, and contact count become steady.

Thus the M1 bed model has an initial contact-manifold transient but not
persistent equilibrium chatter. The V1 `BED_START` duration of 0.5 s ends
while individual contact points are still switching. The 49 V1 whole-action
bed-force transitions also include later robot/cuff motion and cannot be
attributed solely to initial settling.

At equilibrium, the human generalized terms are:

```text
bias       = [ 40.6718, -7.6068] Nm
passive    = [  1.8609,  1.1742] Nm
constraint = [ 38.8109, -8.7810] Nm
inertia    = approximately zero
```

The balance closes numerically, but at q2=0.714 degrees rather than the
requested terminal posture.

## Local actuator-authority comparison

Direction-paired values below are `extension / flexion`. A useful locally
consistent mapping would have positive signed `Delta q2 / Delta x_robot` in
both directions. Every observed value is negative.

| Initial q2 | Interface | Hold q2 at 1 s | Actual paired robot dx (mm) | Delta q2/dx (deg/mm) | Interface deformation / dx | Effective force/dx (N/mm) | Peak cuff force (N) | Peak bed force (N) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 2 | tension-only | 0.714 | -1.012 / +1.009 | -0.000606 / -0.000608 | 0.680 / 0.987 | 1.219 / 1.773 | 5.22 | 522 |
| 2 | bilateral point | 0.714 | -0.145 / +0.130 | -0.00786 / -0.00885 | 0.352 / 0.941 | 23.09 / 25.98 | 13.63 | 202 |
| 10 | tension-only | 0.711 | -1.077 / +1.063 | -0.000521 / -0.000529 | 0.867 / 0.887 | 1.547 / 1.592 | 18.53 | 829 |
| 10 | bilateral point | 0.708 | -0.0508 / +0.0421 | -0.0211 / -0.0256 | 0.809 / 0.795 | 69.25 / 83.82 | 36.15 | 725 |
| 20 | tension-only | 0.707 | -1.090 / +1.079 | -0.000421 / -0.000424 | 0.805 / 0.823 | 1.508 / 1.541 | 30.14 | 1082 |
| 20 | bilateral point | -0.045 | -0.0719 / +0.0738 | -0.142 / -0.150 | 0.278 / 0.252 | 48.37 / 47.11 | 53.14 | 882 |
| 30 | tension-only | -0.0318 | -1.073 / +1.065 | -0.00561 / -0.00470 | 0.816 / 0.832 | 1.562 / 1.586 | 40.69 | 1083 |
| 30 | bilateral point | -0.152 | -0.615 / +0.618 | -0.000164 / -0.000162 | 0.012 / 0.012 | 4.060 / 4.032 | 78.26 | 881 |

The corresponding paired peak robot velocities (`extension / flexion`) were
`1.89/1.88`, `6.99/5.55`, `4.93/9.23`, and `8.51/10.64 mm/s` for the
tension-only cases, and `0.278/0.251`, `15.26/22.20`, `9.94/17.30`, and
`13.89/9.96 mm/s` for the bilateral cases. Values exceeding the 3.75 mm/s
command-profile peak arise from the unmatched posture-collapse transient;
they are another reason not to interpret these ratios as steady gains.

Final bed-contact counts at 2/10/20/30 degrees were `2/2/2/1` for the tendon
and `2/2/1/0` for the bilateral hypothesis. At 30 degrees the bilateral
matched rollouts retained bed support for only 3.5--5% of samples before the
posture collapsed, so this case is not a bed-supported local equilibrium.

All actuator-axis forces remained below the unchanged 200 N bound, and no
interaction-force veto was triggered. Full time series retain robot position
and velocity, cuff force vector, q/dq, bed force, penetration, contact count,
commands, and paired hold states.

The tension-only model absorbs 68--99% of paired robot displacement as axial
interface deformation and produces almost no incremental knee response. This
supports the topology diagnosis: it is not a reasonable proxy for a fixed
cuff unless the real hardware is actually a unilateral cable/strap.

The bilateral point hypothesis reduces deformation absorption at 20 and 30
degrees and produces a substantially larger force/displacement response. It
therefore is the better temporary topology for representing a translationally
fixed cuff. However, it does not make the model ready: the initial postures
collapse, the signed knee response is wrong in both directions, and at 30
degrees the incremental motion appears mainly outside q2 rather than as knee
flexion.

## Rerun gate and conclusion

| Required condition | Result |
|---|---|
| BED_START stable at requested 2 degrees | No |
| Probe postures remain representative | No |
| Bilateral interface has correct signed authority both ways | No |
| Interface deformation is not the majority of motion for all probes | No |
| No force veto | Yes |

The full 2-to-30-to-2 protective motion was not rerun, and no q-switch
sensitivity was run. This result does not show that kinematic protective mode
is infeasible. It shows that neither the V1 tendon nor the temporary point
coupling, combined with the current unverified servo and bed assumptions,
provides validated effective knee authority.

Before a hardware-faithful model, the project still needs:

1. cuff attachment points and orientation relative to the shank and robot;
2. whether the connection is rigid, wrapped, strapped, preloaded, or allowed
   to slip, plus directional stiffness/damping and pressure/contact area;
3. real robot position/velocity/force command semantics, inner-loop gains,
   update rate, saturation, gravity compensation, and braking behavior;
4. interaction-force sensor location, axes, bandwidth, filtering, and whether
   it measures cuff load or robot wrist load;
5. bed geometry, compliance, damping, friction, and expected body support;
6. patient/fixture constraints at the hip and out-of-plane motion allowed by
   the real setup.

## Artifacts and reproduction

Retained local output:

```text
linkage/results/local/mujoco_physical_interface_m15/20260823_083928
```

It contains JSON/CSV summaries, complete NPZ time series, equilibrium and
authority plots, and a representative 20-degree authority-probe GIF.

```text
PYTHONPATH=src MPLCONFIGDIR=/tmp/mujoco-m15-mpl \
  conda run -n mpc_learn python scripts/run_mujoco_physical_interface_m15.py
```

## Verification

- repository Python suite: `128 passed` in the `mpc_learn` environment;
- Python bytecode compilation and `git diff --check`: passed;
- no configured `ruff` or `pyflakes` executable is available in the retained
  environment; no dependency was added solely to claim a lint result.
