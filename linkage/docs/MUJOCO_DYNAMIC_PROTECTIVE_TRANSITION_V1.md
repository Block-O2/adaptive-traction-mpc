# MuJoCo Dynamic Protective Transition V1

## Scope

This diagnostic tests whether one pre-specified smooth protective primitive can
move the frozen CR12-like 6-DoF, bilateral point-sleeve, Human V2 plant from an
engineering initialization at `q2=3 deg` to a larger-angle candidate without
exceeding the existing 200 N interaction gate or safety constraints.

It does not solve the natural-rest-to-3-degree initialization problem, run the
normal controller, implement a hybrid controller, use MPC/learning, optimize a
trajectory, or tune a failed experiment. Bed contact remains the unchanged
unilateral MuJoCo environment and is never commanded as a support force.

Angles in this report are simulation engineering values, not clinical
thresholds.

## Analytical facts

- The bilateral point-sleeve robot map loses rank at `q2=0`; full rank away
  from zero does not itself establish force-bounded dynamic feasibility.
- The retained MATLAB Human V2 definition includes linear passive torque and a
  smooth cubic soft-limit RHS torque inside the 5-degree boundary.
- PR #22's MJCF joints reproduce gravity and linear spring/damping but omit the
  retained cubic soft-limit term.

## Explicit model consistency choice

This experiment uses option 1 from the experiment contract: it applies the
retained Human V2 soft-limit term through MuJoCo `qfrc_applied` at every 1 ms
simulation substep. Registered values are unchanged:

- margin `5 deg`;
- boundary torque `25 Nm`;
- damping `2 Nms/rad`;
- the same lower/upper activation equations and velocity-dependent inward
  damping as the retained MATLAB source.

This is a source-model consistency correction relative to PR #22's MJCF, not
parameter tuning. Geometry, masses, inertias, ROM, linear passive dynamics,
bed, sleeve, Cartesian servo, robot torque limits, and the 200 N bounds are
unchanged. The default V2 environment remains backward compatible; the term is
enabled explicitly for this diagnostic.

## Simulation engineering assumptions

### Initialization

Each candidate starts independently at

`q=[1.435304, 3.000000] deg`, `dq=[0,0]`.

`q1` is obtained from the previously audited nonpenetrating ankle-level path

\[
q_1(q_2)=\operatorname{atan2}(L_2\sin q_2,
L_1+L_2\cos q_2).
\]

The human posture, sleeve point, robot IK, equality connection, and velocities
are consistent to numerical precision; initial EE error is below `2e-10 mm`
and bed penetration is zero. Static equilibrium is deliberately not claimed:
the previous audit found it outside the 200 N quasistatic gate. This experiment
tests whether motion can depart dynamically.

With the retained soft term active, the initialized constraint state has
sleeve interaction `21.96 N`, soft-limit RHS torque `[9.06,1.60] Nm`, and
initial free dynamic acceleration approximately
`[-342.42,+1318.56] deg/s^2` in `[q1,q2]`.

### Fixed primitive

- Candidate targets: `q2=[10,15,20,25,30] deg`.
- The same ankle-level q1(q2) path is used for every target.
- Progress is a quintic minimum-jerk curve with zero endpoint velocity and
  acceleration.
- Duration is fixed analytically so peak reference q2 speed is `5 deg/s`:
  `T=1.875*abs(delta_q2)/5`.
- Human sleeve forward kinematics and its analytic Jacobian produce EE
  position and velocity references.
- The unchanged finite-impedance Cartesian EE servo executes those references.
- A completed target must remain within `0.75 deg` and `2 deg/s` for at least
  `0.20 s`, then complete a `0.50 s` fixed-target hold.
- The 3-degree engineering floor uses the existing 0.05-degree numerical ROM
  tolerance. The reference never commands below 3 degrees. Crossing the floor,
  ROM, or 200 N interaction gate latches a protective stop.

No primitive, duration, controller, force limit, or gate is changed after the
first matrix result.

## Simulation evidence

| forward candidate | duration | result | stop time | final q `[q1,q2]` | final dq `[dq1,dq2]` | peak sleeve force | peak bed force | direct reason |
|---:|---:|:---:|---:|---:|---:|---:|---:|---|
| 3 -> 10 deg | 2.625 s | FAIL | 0.030 s | `[1.239,2.921] deg` | `[-11.48,-7.78] deg/s` | 28.53 N | 122.06 N | engineering-floor violation |
| 3 -> 15 deg | 4.500 s | FAIL | 0.025 s | `[1.291,2.950] deg` | `[-10.37,-6.41] deg/s` | 27.01 N | 0 N | engineering-floor violation |
| 3 -> 20 deg | 6.375 s | FAIL | 0.025 s | `[1.291,2.950] deg` | `[-10.37,-6.41] deg/s` | 27.01 N | 0 N | engineering-floor violation |
| 3 -> 25 deg | 8.250 s | FAIL | 0.030 s | `[1.239,2.922] deg` | `[-11.41,-7.63] deg/s` | 28.50 N | 147.43 N | engineering-floor violation |
| 3 -> 30 deg | 10.125 s | FAIL | 0.025 s | `[1.291,2.950] deg` | `[-10.37,-6.41] deg/s` | 27.01 N | 0 N | engineering-floor violation |

No forward target reaches its region or completes its planned horizon, so no
reverse run is admitted by the registered rule.

The representative 3-to-10-degree trace shows the common mechanism. q2 first
rises only `0.0048 deg`, while q1 immediately accelerates toward extension.
By 10--15 ms, coupled dynamics reverse q2 velocity. At 30 ms the reference has
advanced only to `3.00010 deg`, but actual q2 is `2.92087 deg` and moving at
`-7.78 deg/s`. The EE error grows to `2.08 mm`; the servo produces primarily
upward force, but interaction stays far below 200 N.

The bed does not create a recovery channel. It is initially unloaded. In the
representative run, falling q1 causes one brief `122 N` environmental impact,
then contact unloads again. Other target runs either have no force-bearing bed
contact or a similarly isolated impact. No bed force is prescribed.

## Interpretation

There is no continuous safe dynamic bridge under this fixed primitive and
frozen plant. Failure is not caused by the 200 N sleeve-force gate, actuator
component saturation, command discontinuity, or target hold. It occurs before
the target-dependent portions of the references differ materially.

The direct simulated mechanism is an initialization/startup authority failure:
the 3-degree zero-speed state is not a bounded-force equilibrium, the unchanged
Cartesian position servo begins with essentially zero tracking error rather
than the large generalized preload required by the plant, q1 collapses toward
the bed, and coupled human/sleeve dynamics drive q2 back through the engineering
floor. The retained inward soft-limit torque is active but does not prevent
that coupled reversal.

This negative result does not prove that every dynamically assisted protective
motion is impossible. It shows that the present bilateral point sleeve plus
zero-error Cartesian position primitive cannot safely launch from the stated
3-degree floor. A later experiment would require separately authorized
mechanical moment/second-channel evidence or a clearly specified bounded
preload/velocity-capable robot contract; changing the registered primitive now
would be tuning after failure.

## Reproduction and retained artifacts

```bash
conda run -n mpc_learn python \
  scripts/run_mujoco_dynamic_protective_transition.py \
  --output-dir linkage/results/mujoco_dynamic_protective_transition_v1
```

- [summary.json](../results/mujoco_dynamic_protective_transition_v1/summary.json)
- [transition_results.csv](../results/mujoco_dynamic_protective_transition_v1/transition_results.csv)
- [transition_traces.npz](../results/mujoco_dynamic_protective_transition_v1/transition_traces.npz)
- [candidate comparison](../results/mujoco_dynamic_protective_transition_v1/candidate_comparison.png)
- [representative synchronized GIF](../results/mujoco_dynamic_protective_transition_v1/representative_forward.gif)
- [representative time series](../results/mujoco_dynamic_protective_transition_v1/representative_forward_timeseries.png)
