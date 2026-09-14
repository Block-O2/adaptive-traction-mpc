# Stage-5 support-centered Goal-MPC checkpoint

Evidence category: engineering smoke/diagnostic only. No RL, value learning,
interface mismatch, full joint trajectory, coordination ratio, path corridor,
or new task phase was added. Plant v1, Human model, HOLD stabilizer, 200 N
engineering gate, Safety Filter/BRAKE, motion envelope, objective weights,
horizon, candidate count, and CEM iterations are unchanged.

## Inherited support audit

- Stage 1 `FixedModelMPC` sampled absolute `[F_tan, F_rad]` actions. Gravity
  was inside the Spring2D prediction model, but the normal controller had no
  explicit inverse-dynamics or equilibrium-support command.
- Stage 2 introduced the explicit computed-acceleration command
  `tau_required = M qdd_command + C + G + tau_passive`, then allocated that
  Human generalized input into cuff force and sagittal moment. At a stationary
  target, this becomes the nonzero loaded support command.
- Stage 3 states that it ports the frozen Stage-2 law and retains the same
  inverse-dynamics cuff feedforward.
- Stage 4 retained the same total inverse-dynamics action in its CEM seed, but
  CEM still sampled and penalized absolute generalized action. It did not
  expose support and motion as separate optimization coordinates.

The Stage-5 decomposition therefore reuses the Stage-2/3/4 inverse-dynamics
meaning rather than inventing a new gravity compensation law:

`u_support(q_hat,dq_hat) = inverse_dynamics(q_hat,dq_hat,0)`

`u_total = u_support + delta_u_motion`.

Only `delta_u_motion` is sampled, effort-penalized, and slew-penalized. At each
horizon step the support term is recomputed from the predicted deployable
Human state and fixed Human model. Allocation, full-horizon nominal interface
propagation, first-action execution screening, Safety Filter, and the physical
plant receive the total action. No MuJoCo Human truth enters online control.

The provisional motion exploration standard deviation is `[1.50, 1.00] Nm`
with floor `[0.30, 0.20] Nm`, substantially below the inherited absolute-action
scale `[10, 5] Nm`. The initial population explicitly contains an independently
paced motion seed, the exact support-only sequence, and a shifted continuation
of the currently executed motion increment. These are sampling coordinates,
not changes to the registered motion envelope.

## Loaded start and execution consistency

The matched smoke starts at the same controller-nominal loaded equilibrium
used by the support model; this is a time-zero engineering initial condition,
not a PRELOAD/READY phase. At `[5, 10] deg`, the support input is
`[40.518, -7.578] Nm`, physical Human-site wrench is
`[-31.060, 0, 72.967, 0, 12.615, 0]`, and nominal interface strain is
`[-1.492, 0, 2.799] mm` and `[0, 2.259, 0] deg`. The initial physical
generalized input and model support input agree to numerical precision.

Future interface prediction now also distinguishes Human-site allocated
moment from the robot-site pure support couple. The exact screened first
command remains authoritative; later horizon commands preserve the loaded
support couple and add only the allocated motion-wrench increment.

## Matched complete-episode attempt

Primary retained output:
`results/support_centered_goal_mpc_v1/matched_attempt_01`.

The attempt did not complete. It remained in OUTBOUND and aborted at
`0.685 s` with `NO_SAFE_ACTION`; the supervisor then registered one BRAKE.
There were 34 accepted MPC solves before the failed solve. At the failure all
64 first actions passed executable/force screening, while no full sequence
satisfied the velocity/acceleration/ROM combination.

The first 0.1 s remained loaded and inside the motion envelope:

- estimated peak velocity `[3.062, 6.975] deg/s` and acceleration
  `[148.56, 425.41] deg/s2`;
- evaluation-only peak velocity `[3.050, 6.950] deg/s` and acceleration
  `[115.89, 328.22] deg/s2`;
- peak force/moment `82.839 N / 12.615 Nm`.

Across the retained attempt:

- estimated q range `[2.183, 5.032]` to `[5.006, 10.013] deg`;
- evaluation-only q range `[2.184, 5.032]` to `[5.000, 10.000] deg`;
- estimated peak velocity `[8.668, 16.671] deg/s` and acceleration
  `[180.30, 598.72] deg/s2`;
- evaluation-only peak velocity `[8.713, 16.734] deg/s` and acceleration
  `[152.41, 415.03] deg/s2`;
- peak/cumulative cuff force `85.333 N / 48.537 N s`;
- peak cuff moment `12.842 Nm`;
- peak interface translation/rotation `3.349 mm / 2.259 deg`;
- MPC runtime mean/p95/max `19.244/21.578/21.786 ms`;
- Safety Filter `SAFE_UNCHANGED` 136 times, no 200 N force-gate event, no
  structural/nonfinite event, and no MuJoCo warning.

The registered 45/75 deg/s and 300/600 deg/s2 motion envelope was satisfied
by both the controller estimate and evaluation-only truth. There was no HOLD
or RETURN timing because OUTBOUND did not finish. The measured path has no
time reference or imposed ratio/corridor; its maximum normalized q1/q2
progress difference was `0.0320`, but it moved in the wrong direction and is
not evidence of successful path selection.

## Failure diagnosis

The initial loaded equilibrium is consistent, and the motion envelope is not
intrinsically infeasible: the first 34 MPC solves found constraint-feasible
sequences. Sampling omission is also not the primary cause because the exact
support-only and continuation anchors were present.

The blocker is the support/motion command interface. A positive first selected
motion increment `[1.279, 0.583] Nm` changed the robot command from the loaded
support wrench to a cuff allocation with about 5.3 N less vertical force and
3.4 Nm less commanded moment. After 5 ms, the transmitted physical Human input
was approximately `[-0.961, -0.240] Nm` below support, so q moved away from the
outbound target even though the requested generalized increment was positive.
The same deterministic allocation/interface transient recurred while the CEM
continued to value the unexecuted later part of each short-horizon plan. By
`0.68 s`, the state was close enough to the lower ROM/velocity boundary that
the next population had no fully feasible sequence.

This is not evidence for an interface residual learner. It is a deterministic
motion-increment execution semantic that must be made locally monotone or
otherwise completion-consistent around loaded support before mismatch or
learning work. The result was retained; weights, horizon, candidates, motion
limits, and physical parameters were not changed to make it pass.

## Reproduction

Primary command:

`MPLCONFIGDIR=/tmp/stage5_mpl PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_stage5_complete_goal_episode.py --output-dir stages/stage5_personalized_motion_learning/results/support_centered_goal_mpc_v1/matched_attempt_01`

Regression checks: all 51 Stage-5 tests and the 23 focused unchanged Stage-4
Human-model/MPC tests passed.
