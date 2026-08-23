# MuJoCo bed-assisted small-angle preparation

## Scope and evidence class

This is an engineering-validation smoke experiment for one question only:
whether the frozen CR12-like 6-DoF robot, bilateral sleeve, Human V2, and
unilateral-bed plant can guide the naturally settled leg to a 5 degree knee
preparation posture while the bed remains available as support. It does not
run the normal controller, a handoff study, Windowed NLS, R3C, or R4.

The observed result is a retained negative result for this simulated plant. It
is neither a hardware claim nor evidence that every bed-assisted preparation
architecture is infeasible.

## Frozen plant and command contract

- Human V2 geometry, mass, inertia, ROM, passive stiffness, and damping are
  unchanged.
- Bed height, compliant-contact parameters, and friction are unchanged.
- The CR12-like robot and bilateral sleeve are unchanged from plant V2.
- The Cartesian position/velocity interface remains a finite-impedance robot
  servo (`Kp=3000 N/m`, `Kd=140 Ns/m`) whose world-frame force components are
  bounded by 200 N. No hardware API is claimed.
- The sleeve equality remains bilateral with the existing `6000 N/m` and
  `120 Ns/m` compliance assumptions.
- No bed force is commanded. All bed load is produced by MuJoCo contact.

## Joint-space preparation path

The initial boundary is the measured state after settle, not a hard-coded
angle. The retained run settled at:

- `q=[-0.00463, 0.71303] deg`;
- `dq` below `1.1e-7 deg/s` in magnitude;
- bed force `62.96 N` and sleeve interaction `4.10 N`.

For `q2_target=5 deg`, the q1 target is constructed from two registered
constraints rather than extrapolating the taught trajectory:

1. Human V2 link geometry gives `q1=2.0498 deg` as the minimum posture that
   leaves the distal shank capsule tangent to the bed.
2. The Human V2 lower soft-zone boundary is 5 degrees. The least q1 satisfying
   both conditions is therefore `q1=5 deg`.

The joint target is `[5, 5] deg`. A four-second quintic boundary trajectory
matches the measured initial `q/dq`, ends with zero reference velocity and
acceleration, and is mapped to the sleeve Cartesian reference using the Human
V2 forward kinematics. Only that EE position/velocity reference is sent to the
robot. The analytic sleeve Jacobian agrees with central finite differences to
`6.96e-10`.

Natural rest begins inside the registered lower soft zone. The gate therefore
does not pretend the initial state is soft-limit-clear: it requires no deeper
soft-zone excursion and exit from that zone at the target, in addition to the
explicit ROM gate.

## Gate and staged rule

The 5 degree case requires stable monotonic q2 progress to within 0.75 degree,
final joint speed no greater than 1 degree/s, no new soft/ROM violation, no
protective stop, interaction below 200 N, sleeve deformation below 1 mm,
continuous Cartesian commands, and no bed-active chatter/loss. The 8 and 10
degree cases are permitted only after a 5 degree PASS.

## Retained result

| target | status | measured final q (deg) | peak interaction | bed force rest -> final | sleeve deformation | direct mechanism |
|---:|:---:|---:|---:|---:|---:|---|
| 5 deg | FAIL | `[-0.00395, -0.05136]` | 34.25 N | 62.96 -> 26.49 N | 0.039 mm | bed-constrained Cartesian load path drove knee extension and reached the lower ROM stop |
| 8 deg | not run | -- | -- | -- | -- | stopped by staged rule |
| 10 deg | not run | -- | -- | -- | -- | stopped by staged rule |

The reference remained smooth: maximum EE-reference step was `0.0946 mm` and
maximum Cartesian force-command step was `4.10 N`. Bed contact stayed active
with zero active-contact transitions during preparation. Peak bed force was
`67.07 N`, and maximum bed penetration was `0.0650 mm`. There was no force
veto; the protective stop was the lower ROM check.

The robot motion did not become knee flexion. q2 decreased by `0.764 deg` while
the requested path advanced. At the stop, the incomplete reference had reached
approximately `[1.74, 2.21] deg`, but measured q was approximately
`[-0.004, -0.051] deg`; EE error was about `10.0 mm` at that instant and
`37.8 mm` relative to the final target.

## Direct mechanical interpretation

The full resting-to-target sleeve displacement is approximately
`[-1.63, 0, +42.63] mm`, almost vertically upward. At the measured resting
configuration, a unit Cartesian force along that path maps through the sleeve
Jacobian to generalized torque `[+0.797, -0.360] Nm/N`: hip-flexion torque but
knee-extension torque under the repository's q2 convention. The bed prevents
the corresponding downward/penetrating link motion and continues to carry
load, so the finite-impedance Cartesian servo unloads the bed while the
available generalized response moves q2 in the wrong direction.

This distinguishes the observed mechanism:

- **Joint path / FK implementation:** numerically consistent; not the direct
  code error.
- **Sleeve geometry/compliance:** deformation is two orders of magnitude below
  the 1 mm gate; not motion-absorbing.
- **Robot force bound:** not reached; increasing it is neither attempted nor
  justified by this run.
- **Bed/load-path constraint:** direct blocker in the simulated topology. A
  single Cartesian sleeve point plus unilateral bed constraint does not realize
  the desired two-joint path near the resting configuration.

Therefore this nominal plant does not currently support the claimed
`bed-assisted small-angle preparation -> normal rehab` architecture. The next
scientific decision should be about the physical constraint/attachment and
command-space design (for example, whether real hardware controls sleeve pose,
provides a second attachment moment, or permits a different supported joint
path), not controller tuning or a higher-angle sweep.

## Reproduction

```bash
conda run -n mpc_learn python scripts/run_mujoco_bed_assisted_preparation.py \
  --output-dir linkage/results/mujoco_bed_assisted_preparation
```

Retained evidence:

- [summary.json](../results/mujoco_bed_assisted_preparation/summary.json)
- [preparation_results.csv](../results/mujoco_bed_assisted_preparation/preparation_results.csv)
- [resting_to_5deg_timeseries.png](../results/mujoco_bed_assisted_preparation/resting_to_5deg_timeseries.png)
- [resting_to_5deg_synchronized.gif](../results/mujoco_bed_assisted_preparation/resting_to_5deg_synchronized.gif)
- [preparation_traces.npz](../results/mujoco_bed_assisted_preparation/preparation_traces.npz)
