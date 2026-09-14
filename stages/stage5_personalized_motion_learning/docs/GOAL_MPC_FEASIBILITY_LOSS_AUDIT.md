# Stage-5 Goal-MPC feasibility-loss audit

Evidence category: engineering diagnostic only. This audit changes no controller
cost, constraint, horizon, candidate count, action space, execution law, plant,
or task logic.

## Reproduction boundary

The final reconstruction is
`results/feasibility_retention_v1/failure_reconstruction_v4/`. Its 90 samples
through 0.445 s are bit-for-bit identical for every common numeric and string
trace field to the saved
`acceleration_semantics_v1/matched_attempt_01` failure. The MPC solve fails at
0.440 s and the supervisor records `ABORTED/NO_SAFE_ACTION` at 0.445 s.

The immediately preceding accepted solve was at 0.420 s. Its first predicted
Human state at 0.440 s differed from the deployable estimate by only
`[+1.03e-5, -4.30e-4, -3.36e-3, -6.63e-2]` in
`[q1 rad, q2 rad, dq1 rad/s, dq2 rad/s]`. In particular, realized `dq2` was
3.80 deg/s lower than predicted, so Human-state execution overshoot did not
cause the loss.

## Exact constraint split at the failed solve

Both production CEM iterations screened all 32 first actions as executable.
All 32 candidates also satisfied Human ROM, task ROM, allocated-force, and
predicted physical-force constraints. No candidate satisfied the horizon
velocity constraint; only 3/32 and 2/32 respectively satisfied acceleration.
The best velocity margins were -0.6158 and -0.4784 rad/s. The first-action
executable/physical force screen was therefore not the rejecting boundary.

The stored previous cost-selected plan and the previous population's
largest-margin feasible plan were shifted and revalidated from the exact
0.440 s measured state. Both became velocity-infeasible at horizon step 2
(40 ms), with minimum margins -1.3414 and -1.5127 rad/s. This is not a
last-step horizon-extension artifact.

| continuation | first violation | velocity margin rad/s | acceleration margin rad/s2 | ROM | force and executable command |
|---|---:|---:|---:|---|---|
| shifted previous selected | velocity step 2 | -1.3414 | +2.4586 | feasible | feasible |
| shifted previous safest | velocity step 2 | -1.5127 | +1.3777 | feasible | feasible |
| support only | velocity step 2 | -1.5018 | +2.9943 | feasible | feasible |
| model-based braking | velocity step 3 | -0.9143 | +0.6854 | feasible | feasible |
| conservative goal progress | acceleration step 1, velocity step 4 | -1.1771 | -1.8696 | feasible | feasible |

A separate diagnostic CEM with 512 candidates, 32 elites, and six iterations
also found zero feasible candidates in 231.2 ms. This search result is not
treated as proof of mathematical infeasibility.

## Evidence-supported root cause

The result supports case B, not case A. The retained sequence does not include
the nominal interface predictor's inferred base-drive/history state. At every
new solve, that state is reconstructed from the latest 5 ms change in observed
interface velocity and then treated as the base drive for the 300 ms horizon.
Consequently, shifting the same action remainder after a measurement update is
not a shift of the same predicted dynamical state.

The previous one-step interface pose prediction was close to the 0.440 s
estimate: translation error was at most 0.033 mm and rotation error at most
0.0060 deg. The velocity/history state was not: translation-velocity error
reached 0.0116 m/s and angular-velocity error 0.0433 rad/s. The newly inferred
base drive changed by `[+2.45, +0.37, -10.80]` N and the angular drive by
`[+0.0315, +0.4712, +0.0667]` Nm. Under the current constant-drive horizon
assumption, that reset makes even the previously feasible remainder violate
velocity within two prediction steps.

This is a deterministic prediction-state completeness/initialization mismatch
inside the nominal interface model. It is not evidence that normal CEM merely
forgot a still-valid plan, and it is not yet evidence that the physical state
is outside the true locally recoverable set.

## Decision

No feasibility-retention control mechanism was enabled and no matched full
episode was rerun. Retaining either the previous objective-best plan or the
previous largest-margin plan would still present an invalid candidate at the
new measured state. Candidate heuristics would mask the earlier model-state
problem.

Before Goal-MPC feasibility retention is reconsidered, the nominal interface
prediction state must make base drive/history explicit and propagate it across
MPC updates, with a causal reconciliation rule for new measurements. The same
state/version must be used by the accepted-horizon prediction and next-solve
revalidation. Only after that correction should shifted-plan validity and a
separately retained feasible continuation be tested again. This would still not
justify the term recursive feasibility without a formal invariant-set or
terminal-condition argument.

Follow-up: `EXPLICIT_INTERFACE_PREDICTION_STATE_V1.md` implements and validates
that state-continuity correction. The historical findings above remain the
before-state evidence.

## Safety/runtime observation

The reproduced prefix has 23 solves, 22 `SAFE_ACTION` and one
`NO_SAFE_ACTION`. MPC runtime was 24.34/26.43/28.07 ms mean/p95/max. Physical
cuff force peaked at 137.23 N, cumulative force was 49.02 Ns, and moment peaked
at 18.69 Nm. There was one BRAKE caused by `NO_SAFE_ACTION`, no 200 N force-gate
event, no Safety Filter intervention, no structural event, and no MuJoCo
warning. Online and evaluation-only velocity/acceleration envelopes remained
satisfied through the abort.
