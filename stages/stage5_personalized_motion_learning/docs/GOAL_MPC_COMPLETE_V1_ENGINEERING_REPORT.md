# Stage-5 first complete non-learning Goal-MPC episode

Evidence category: matched-model engineering smoke only. No Stage-3/4 source,
Plant-v1 parameter, MPC cost/constraint, horizon/candidate setting, task
tolerance, Safety Filter/BRAKE rule, force gate, Human model, or learning/value
behavior changed.

Superseded readiness note: the later motion-envelope checkpoint exposes an
initial acceleration infeasibility and therefore blocks interface mismatch.
See `MOTION_ENVELOPE_COMPLETION_CHECKPOINT.md`; the complete episode below is
retained historical evidence under the previously disabled motion envelope.

## Controller chain

The completed chain is:

`OUTBOUND Goal-MPC -> bumpless loaded local HOLD -> continuous 0.5 s HOLD ->`
`bumpless executable-reference transfer -> RETURN Goal-MPC -> COMPLETE`.

RETURN uses the existing phase target from `GoalTaskSpec`, terminal value zero,
and the existing path-free Goal-MPC objective. No prescribed q1/q2 time
reference, coordination ratio, or path corridor is present. The existing
RETURN controller settled without a terminal local stabilizer.

At RETURN entry, Goal-MPC's causal last action is synchronized to the action
actually executed by HOLD. A generic 0.10 s Stage-5 executable-reference
handoff makes the first RETURN physical wrench equal to the last HOLD wrench.
The first RETURN target wrench is frozen during this transfer and CEM is held;
otherwise repeatedly optimizing under a raw-command prediction while executing
only a partial blend creates a deterministic prediction/execution mismatch.
After the transfer, unchanged RETURN Goal-MPC resumes.

## Primary matched episode

The retained primary output is
`results/goal_mpc_complete_v1/attempt_05_final`.

- OUTBOUND: 0.000 to 2.080 s;
- HOLD: 2.080 to 2.865 s, including a true continuous 0.500 s interval;
- RETURN: 2.865 to 4.615 s;
- COMPLETE: 4.615 s.

The estimated terminal return error is `[0.98072, 0.36431] deg`, with estimated
velocity `[-1.37633, -1.10446] deg/s`, satisfying the configured 1 deg and
2 deg/s GoalTaskSpec conditions. Evaluation-only truth at the same instant is
`[0.99641, 0.39908] deg` and `[-2.01331, -2.35578] deg/s`; the phase transition
correctly uses only the deployable estimate, but this thin truth-side velocity
margin must be watched in the mismatch checkpoint.

The actual path is stored sample-by-sample in `trace.npz`. Its observed q range
was `[4.872,9.843] -> [20.488,37.491] deg` outbound and
`[20.000,35.000] -> min [3.500,5.288] -> [5.981,10.364] deg` on return. The
maximum normalized q1/q2 progress difference was 0.356, confirming that the
real path was not constrained to a fixed coordination ratio.

Full-episode peak physical cuff force was `173.252 N`, cumulative force was
`443.642 N s`, peak moment was `24.967 Nm`, peak translational interface
deformation was `6.406 mm`, and peak rotational deformation was `3.925 deg`.
RETURN alone had `121.477 N` peak force, `133.723 N s` cumulative force, and
`20.694 Nm` peak moment.

Human-state estimation RMSE was q `[0.0120,0.0260] deg` and dq
`[0.540,0.986] deg/s`; peak absolute errors were q `[0.102,0.209] deg` and dq
`[4.980,8.649] deg/s`. Goal-MPC runtime was `21.911/23.670/25.376 ms`
mean/p95/max. Loaded local HOLD runtime was `0.522/0.629/1.790 ms`; the RETURN
handoff adapter was `0.683/0.901/0.959 ms`.

The OUTBOUND-to-HOLD first executable discontinuity was `1.42e-13 N`,
`8.88e-16 Nm`, and `0.00880 Nm` robot joint-torque-vector norm. The
HOLD-to-RETURN first discontinuity was `1.62e-13 N`, `1.78e-15 Nm`, and
`3.56e-5 Nm` robot joint-torque-vector norm. During the 0.10 s RETURN transfer,
the largest 5 ms force/moment command steps were `5.790 N` and `0.989 Nm`.

All 923 Safety Filter decisions were `SAFE_UNCHANGED`; no force-gate, BRAKE,
structural, nonfinite, or MuJoCo warning occurred.

## Retained diagnostic attempts

- `attempt_01_existing_return` completed but exposed the avoidable direct
  HOLD-to-RETURN wrench jump of `62.17 N / 10.62 Nm`.
- `attempt_02_bumpless_return` removed the first jump but re-optimized CEM while
  executing only a partial blend; this deterministic mismatch became
  self-exciting and ended with `NO_SAFE_ACTION`.
- `attempt_03_frozen_return_transfer` completed after freezing the first target
  through the transfer; `attempt_04_final` adds complete command/path metrics.
  `attempt_05_final` changes only the saved controller label so the retained
  primary artifact identifies the complete execution chain unambiguously.

This historical matched episode motivated the small interface-mismatch
checkpoint, but it no longer authorizes that run: the subsequent explicit
motion-envelope checkpoint must pass first. Truth-side completion error remains
an evaluation-only diagnostic and all current gates/abort behavior remain in
force.
