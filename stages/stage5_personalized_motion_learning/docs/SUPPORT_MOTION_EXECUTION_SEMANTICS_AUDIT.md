# Stage-5 support/motion execution-semantics audit

> Historical pre-fix audit. The loaded/unloaded reference-authority conflict
> identified here is removed by `LOADED_EXECUTION_AUTHORITY_V1.md`. This file
> and its original evidence remain retained rather than rewritten.

## Scope and evidence

This is a targeted engineering structural audit, not a controller change or a
scientific experiment.  It uses the frozen Plant-v1 matched model, the fixed
Human model, the provisional 5 deg/10 deg start state, and one 50 ms paired
diagnostic.  The five branches were restored from the same plant/controller
snapshot (`a72878787ca0b3e1a58fd7937009af305295796ac9041ed9c06c66ecd1ae6151`).
The only perturbations were `delta_tau = [0,0], [+/-0.5,0], [0,+/-0.5] Nm`.
No Stage-3/4 source, controller, cost, constraint, Plant-v1 parameter, or
registered motion-envelope value was changed.

Machine-readable evidence is in
`results/support_motion_semantics_audit_v1/audit_summary.json`; the complete
paired table is in `paired_response.csv`.

## Structural conclusion

At the Human-input boundary there is one control input:

```text
tau_total(q,dq) = inverse_dynamics(q,dq,0) + delta_tau_motion.
```

`tau_support + delta_tau_motion` is only a mathematical/CEM
parameterization.  It is not a second task, state, or physical input.  At the
same estimated `q,dq`, a direct `tau_total=[41.0175946,-7.3284183] Nm` and the
decomposed form with `tau_support=[40.5175946,-7.5784183] Nm` and
`delta_tau=[0.5,0.25] Nm` produced exactly the same total input, allocated
wrench, executable wrench, and 20 ms predicted endpoint wrench (maximum
absolute difference `0.0` for all four checks).

The complete Stage-5 execution law is nevertheless not currently coherent.
The Goal-MPC path constructs a loaded `CuffPoseReference`, but the inherited
Stage-4 adapter discards `reference.world_from_cuff` and regenerates an
unloaded Human cuff pose and twist from `reference.q_rad/dq_rad_s`.  HOLD and
the handoff path use the explicit loaded robot-side pose.  These authorities
are not active in the same cycle, but the authority changes between Goal-MPC,
handoff, and HOLD.  The full-horizon predictor also uses a future command
resolver rather than the same low-level pose/velocity-feedback law executed at
the next control instant.  Thus first-action screening is execution-equivalent,
while later predicted command semantics are not.

## Representative command chain

The representative branch is `delta_tau_motion=[+0.5,0] Nm` at
`q=[5,10] deg`, `dq=[0,0] deg/s`.

| Stage | Quantity at the representative instant | Frame/sign and authority | Candidate dependence | Prediction/execution agreement |
|---|---|---|---|---|
| Human observation | `q_hat,dq_hat=[0.0872665,0.174533,0,0]` | Human generalized coordinates; deployable interface-aware observer | invariant for the instant | same observation/version |
| Support | `[40.5176,-7.57842] Nm` | Human generalized input; `inverse_dynamics(q_hat,dq_hat,0)` | invariant for the instant | same algebra in CEM and execution |
| Motion decision | `[0.5,0] Nm` | Human generalized-input increment; CEM decision | dependent | optimized variable |
| Total Human request | `[41.0176,-7.57842] Nm` | Human generalized input; support plus increment | dependent | allocator receives this total |
| Cuff allocation | `[-31.7349,0,74.0568, 0,12.9111,0]` | world wrench about the Human cuff site; physical `+My` maps to generalized `[-My,+My]`; legacy scalar `my_nm` has the opposite sign | dependent | same allocator/version |
| Pose target passed | position `[0.721424,0,0.0778467] m`; loaded orientation | world robot-side loaded equilibrium from nominal interface model | invariant for the instant | **not consumed by Goal adapter** |
| Pose/twist actually used | position `[0.722667,0,0.0749281] m`; unloaded Human cuff orientation; zero twist | regenerated from Human geometry and `reference.q/dq` by Stage-4 adapter | invariant for the instant | shared by first-action candidates and final Goal execution |
| Low-level feedback | force `[3.72720,0,-8.75604] N`; moment `[0,-4.73054,0] Nm` | world; target minus measured robot cuff pose/twist | invariant for the instant | same at first-action preview/execution |
| Executable wrench | `[-28.0077,0,65.3008, 0,8.18052,0]` | world, applied at robot attachment site; feedback plus allocator wrench | dependent through allocation | same first-action value; later horizon law differs |
| Robot command | `[17.3648,86.2768,49.3174,7.81993,-2.80077,13.2253] Nm` | robot joint coordinates; robot bias plus nullspace posture plus `J_R^T W_total`, then torque limits | dependent | same first-action command/version |
| Interface | Plant-v1 spring-damper wrench | Human/robot site wrenches in world; equal/opposite force with reference-point-consistent moments | dependent and dynamic | nominal predictor approximates it; plant is evaluation truth |
| Actual Human input at 5 ms | `[39.0176,-8.13783] Nm` | Human generalized coordinates; `J_H^T W_H` from physical interface | dependent and dynamic | evaluation-only measurement |

The loaded and actually used Goal targets differ by `3.1721 mm` and
`2.25867 deg`.  Consequently even support-only receives unloading feedback:
`[3.727,0,-8.756] N` and `My=-4.731 Nm`.  This is a confirmed reference
authority bug, not evidence that support and motion should be separate tasks.

## Paired response

Every value below is a paired difference relative to support-only.  Wrench
triples are `[Fx,Fz,My]`; Human vectors are `[joint1,joint2]`.  The CSV retains
all six world-wrench components.

| Branch | delta allocated/first executable `[Fx,Fz,My]` | delta physical wrench `[Fx,Fz,My]` at 5 / 20 / 50 ms | delta actual Human input at 5 / 20 / 50 ms | delta `dq` deg/s at 5 / 20 / 50 ms | delta `ddq` deg/s2 at 5 / 20 / 50 ms |
|---|---|---|---|---|---|
| `+delta_tau1` | `[-0.675,+1.090,+0.296]` | `[-0.849,+0.409,+0.121] / [-1.040,+0.646,+0.150] / [-1.312,+0.691,+0.223]` | `[+0.185,+0.025] / [+0.330,-0.010] / [+0.293,+0.058]` | `[+0.047,+0.145] / [+0.260,+0.572] / [+0.778,+1.525]` | `[+9.46,+28.94] / [+14.08,+24.98] / [+24.16,+54.80]` |
| `-delta_tau1` | `[+0.675,-1.090,-0.296]` | `[+0.841,-0.411,-0.115] / [+1.068,-0.650,-0.160] / [+1.081,-0.708,-0.223]` | `[-0.193,-0.018] / [-0.324,+0.000] / [-0.302,-0.047]` | `[-0.073,-0.210] / [-0.238,-0.517] / [-0.519,-0.927]` | `[-14.54,-41.95] / [-6.07,-5.84] / [-12.69,-22.11]` |
| `+delta_tau2` | `[-1.559,+1.012,+0.752]` | `[-1.988,+0.710,+0.285] / [-2.602,+1.211,+0.372] / [-3.135,+1.334,+0.560]` | `[+0.254,+0.131] / [+0.536,+0.090] / [+0.442,+0.258]` | `[+0.104,+0.388] / [+0.537,+1.490] / [+1.279,+3.108]` | `[+20.83,+77.67] / [+21.86,+46.55] / [+21.29,+48.37]` |
| `-delta_tau2` | `[+1.559,-1.012,-0.752]` | `[+1.978,-0.710,-0.276] / [+2.632,-1.189,-0.361] / [+3.184,-1.332,-0.569]` | `[-0.263,-0.121] / [-0.531,-0.086] / [-0.432,-0.267]` | `[-0.145,-0.489] / [-0.635,-1.718] / [-1.325,-3.201]` | `[-28.90,-97.82] / [-35.78,-79.27] / [-20.16,-45.53]` |

At the first instant the paired feedback-force and feedback-moment differences
are exactly zero for every branch, so the allocated-wrench increment passes
unchanged into the executable-wrench increment.  The later response is delayed
and mildly asymmetric because the finite interface, Human/robot dynamics, and
feedback context evolve after each 5 ms update.  More importantly, the
support-only absolute response is not an equilibrium: by 50 ms it has
`dq=[-7.77,-17.52] deg/s`.  The paired diagnostic therefore demonstrates a
valid incremental control direction around an invalid execution reference.

## Reference and cost/constraint semantics

- No prescribed full `q1(t),q2(t)` reference, fixed coordination ratio, or
  path corridor is present in Goal-MPC.  The phase goal is constant and task
  completion remains owned by `GoalTaskSpec`.
- Sharing the current observation, support, and loaded reference among the
  first-action CEM candidates is correct for a torque-increment action space;
  it is not itself a bug.  The bug is that the shared loaded pose is discarded.
  Across future horizon steps, reference/feedback quantities must become
  consistent with each candidate's predicted state if that execution law is
  to be modeled.
- Goal action effort is applied only to `delta_tau_motion`.  This is coherent
  only if the term is explicitly defined as motion-increment effort; it is not
  total Human/cuff effort.
- Goal slew is also applied only to `delta_tau_motion`.  Because
  `tau_support(q,dq)` varies, it is not the slew of the total executed Human
  request or robot/cuff command.  This is a confirmed semantic mismatch if the
  objective is intended to penalize physical command smoothness.
- Human q, q-velocity, and q-acceleration constraints apply to predicted Human
  total motion.  The force checks use predicted transmitted total force,
  allocated total force, and the exact first-action total executable force.
  They are not applied to the increment alone.
- No numeric cuff-moment hard gate is currently registered in Goal-MPC.  Moment
  is predicted/logged and robot torque feasibility limits it indirectly, but
  it must not be described as an explicit moment constraint until a threshold
  is specified.

## Sign, frame, and compensation checks

- Allocator moment signs are internally consistent: physical world `+My` in
  `wrench_world` maps through `[-1,+1]` into Human generalized input.  Only the
  legacy scalar key `my_nm` intentionally stores the opposite sign.
- Human gravity, Coriolis, and passive mechanics enter `tau_support` through
  Human inverse dynamics.  Robot `qfrc_bias` is added only in robot joint
  coordinates.  No Human/robot gravity double compensation was found.
- A frame/reference-point hazard remains: the allocator wrench is defined
  about the Human cuff site but is inserted into a command applied at the robot
  attachment site.  The loaded-pose feedback/future support correction is
  supposed to close that distinction.  Because the Goal adapter discards the
  loaded pose and the future predictor uses a different correction law, the
  current closure is not consistent even though the allocator sign itself is.

## Minimal recommended fix before another episode

Do not change action space, CEM weights, task states, or constraints.  Use one
Stage-5 execution-context builder for Goal first-action batch screening,
supervisor execution, HOLD, and both handoffs.  That builder must consume the
explicit nominal-interface loaded robot pose/twist and must not regenerate it
from `reference.q/dq`.  The full-horizon command resolver should implement the
same pose/velocity feedback and Human-site-to-robot-site wrench convention for
each candidate-predicted state.  Then define whether effort/slew means the
motion increment or the total executed quantity; if it means command
smoothness, compute slew on the total request/command without changing its
weight.  A cuff-moment limit requires a separate approved numeric contract.
