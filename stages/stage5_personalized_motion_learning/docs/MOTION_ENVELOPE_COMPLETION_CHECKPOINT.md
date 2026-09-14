# Stage-5 motion-envelope and completion-margin checkpoint

> Historical introduction of the provisional envelope. The online
> acceleration measurement semantics are superseded by
> `ACCELERATION_SEMANTICS_V1.md`; the numerical `[300,600] deg/s2` limits are
> unchanged.

Evidence category: engineering smoke/diagnostic only. This checkpoint adds no
RL, value learning, interface mismatch, time-indexed joint reference,
coordination ratio, or path corridor. Plant v1, the 200 N engineering gate,
Safety Filter/BRAKE, CEM horizon/candidates/iterations, Human model, objective
weights, and loaded-HOLD stabilizer gains are unchanged.

## Frozen provisional envelope basis

The independent joint limits are:

| quantity | q1 | q2 |
|---|---:|---:|
| velocity limit | 45 deg/s | 75 deg/s |
| acceleration limit | 300 deg/s2 | 600 deg/s2 |

These values were selected before the new matched replay. The Stage-4
registered moderate trusted-adaptive trace had evaluation-only peak velocity
`[13.18, 17.89] deg/s` and estimator peak velocity `[14.48, 19.73] deg/s`.
Its estimator acceleration p99 was `[141.89, 265.55] deg/s2`. The Stage-5
legacy low/moderate replay had velocity p99 near `[9.76, 17.24] deg/s` and
estimator acceleration p99 `[149.94, 297.56] deg/s2`. The selected envelope
therefore leaves substantial joint-specific engineering headroom around
successful low/moderate motion while rejecting the prior unconstrained
complete episode's `[68.47, 170.66] deg/s` evaluation-only peaks. It is a
provisional simulation envelope, not a clinical or hardware-qualified limit.
The unequal joint limits do not couple q1 and q2.

Single-sample 5 ms acceleration peaks in the historical traces are much
larger than their p99 values because interface loading and estimator
differentiation contribute short transients. Those peaks were retained as
evidence; they were not used to inflate a rehabilitation-motion limit until
the episode passed.

## Controller-only completion margin

The actual `GoalTaskSpec` completion tolerances remain `[1, 1] deg` and
`[2, 2] deg/s`. Online phase decisions use only the deployable interface-aware
estimate and the conservative subset:

| quantity | margin q1/q2 | effective online tolerance q1/q2 |
|---|---:|---:|
| angle | `[0.05, 0.10] deg` | `[0.95, 0.90] deg` |
| velocity | `[0.75, 1.50] deg/s` | `[1.25, 0.50] deg/s` |

The margin comes from the saved matched trace
`results/goal_mpc_complete_v1/attempt_05_final/trace.npz`. Exact
estimator-minus-evaluation-truth discrepancies at the old transitions were:

| transition time | transition | abs q error [deg] | abs dq error [deg/s] |
|---:|---|---:|---:|
| 2.080 s | OUTBOUND to HOLD | `[0.00168, 0.00079]` | `[0.17981, 0.10759]` |
| 2.865 s | HOLD to RETURN | `[0.000001, 0.000002]` | `[0.00003, 0.00007]` |
| 4.615 s | RETURN to COMPLETE | `[0.01569, 0.03477]` | `[0.63699, 1.25132]` |

The chosen margins exceed all exact-transition discrepancies with a small
deterministic guard. At the old estimated COMPLETE decision, evaluation truth
had position error `[0.99641, 0.39908] deg` and speed
`[2.01331, 2.35578] deg/s`; the velocity state was outside the original task
set. The tightened online predicate would reject that old decision. MuJoCo
truth is used only in this offline audit and is absent from the online
predicate.

## Runtime profile and changes

A 0.1 s cProfile diagnostic identified the full-horizon interface rollout and
the repeated selected first-action screen as the remaining avoidable costs.
The Stage-5-only implementation now:

- reuses geometry/Jacobian results between adjacent horizon steps and cuff
  allocation;
- precomputes the constant Kelvin-Voigt analytic transition coefficients and
  vectorizes the three peak samples;
- reuses the selected first-action result already screened in a CEM
  population;
- records per-solve timing sections without adding diagnostics inside the
  per-candidate scalar path.

With the old unconstrained task used only as an apples-to-apples 0.1 s runtime
diagnostic, post-change mean/p95/max Goal-MPC time is
`15.925/16.165/16.202 ms`; horizon, 32 candidates, and two CEM iterations are
unchanged. Under cProfile instrumentation it is `20.031/20.489/20.548 ms`,
compared with `27.191/27.713/27.844 ms` before the change. The post-change
unprofiled breakdown is approximately `10.055 ms` horizon dynamics,
`4.342 ms` first-action screening, and `1.116 ms` remaining overhead.

## Matched checkpoint attempt

Primary output:
`results/motion_envelope_checkpoint_v1/matched_attempt_01`.

The requested full matched episode did not complete. It ended at `0.005 s`
in OUTBOUND with `NO_SAFE_ACTION`; the supervisor entered BRAKE once. All
64 first-action candidates passed executable/force screening, but zero
candidates satisfied the new acceleration constraint. The best candidate's
minimum acceleration margin was still `-13.474 rad/s2`; velocity, ROM,
allocated force, and predicted physical force each had feasible candidates.
This is an initial-condition feasibility problem: the episode starts with an
unloaded/zero-strain interface while the leg immediately needs a loaded
supporting equilibrium. The full-horizon predictor correctly exposes the
resulting load-build transient instead of hiding it.

Observed before termination:

- estimated peak velocity `[3.038, 1.185] deg/s`; evaluation-only peak
  velocity `[5.247, 4.899] deg/s`;
- estimated 5 ms peak acceleration `[607.55, 237.07] deg/s2`;
  evaluation-only peak acceleration `[1049.47, 979.76] deg/s2`;
- peak/cumulative physical cuff force `55.481 N / 0.1387 N s`;
- peak physical cuff moment `5.990 Nm`;
- peak interface translation/rotation `0.423 mm / 0.101 deg`;
- Goal-MPC runtime `15.865 ms` for the one failed solve;
- no 200 N force-gate, structural, nonfinite, or MuJoCo warning; no Safety
  Filter decision was executed before the `NO_SAFE_ACTION` BRAKE.

No HOLD runtime or meaningful phase/path timing exists because the controller
did not leave OUTBOUND. The formulation remains path-free by construction and
the unit tests continue to accept distinct q1-first and q2-first intermediate
paths, but this failed replay cannot provide new empirical path-shape evidence.

## Checkpoint conclusion

This checkpoint does not pass, so the deterministic Stage-5 controller is not
ready to freeze and interface-mismatch testing remains blocked. The minimal
next design decision is how to establish a constraint-consistent loaded start
(or an explicit pre-episode load-establishment phase) while keeping the motion
envelope hard. Raising the acceleration limits to admit the current transient,
silently exempting startup, or retuning CEM weights was not performed.

## Reproduction records

- Primary matched command:
  `PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src conda run --no-capture-output -n mpc_learn python stages/stage5_personalized_motion_learning/scripts/run_stage5_complete_goal_episode.py --output-dir stages/stage5_personalized_motion_learning/results/motion_envelope_checkpoint_v1/matched_attempt_01`
- Regression command:
  `PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src conda run --no-capture-output -n mpc_learn pytest -q stages/stage5_personalized_motion_learning/tests`
- Result: 48 tests passed. The primary matched command completed mechanically
  and preserved its output, but the task outcome was the blocked
  `NO_SAFE_ACTION`/BRAKE result above.
