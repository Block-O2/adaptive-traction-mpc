# Stage-5 Goal-MPC Runtime Optimization v1

Evidence category: engineering smoke and implementation profiling only.

## Frozen control contract

This checkpoint does not change the controller architecture, action space,
CEM horizon (15), production population (32), CEM iterations (2), objective
weights, motion envelope, Plant-v1, loaded execution semantics, explicit
interface prediction state, HOLD controller, Safety Filter/BRAKE, or the 200 N
engineering gate. No learning or interface mismatch is active.

## Repeated-work audit

| Class | Quantities | Treatment |
|---|---|---|
| solve-invariant | fixed Human coefficients; nominal interface K/D/mass/inertia; 0.25 ms screening substep and 20 ms hold; allocator surface metric/Hessian diagonal; fixed world sagittal basis | precompute the semi-implicit interface transition powers and retain existing immutable constants |
| horizon-step invariant | integration step; cost/constraint scales; fixed parameter arrays | reuse without rebuilding scientific objects |
| candidate-invariant | solve-initial deployable Human/interface observation; initial base drive; previous executable wrench; current loaded execution context | broadcast into the population; never infer separately per candidate |
| candidate-specific | motion increment and total support-centered action; q/dq-dependent support; Human-cuff Jacobian/frame; loaded target and interface state; requested/support/executable/transmitted wrench; predicted q/dq, force, moment, cost and every constraint margin | remain batched but candidate-specific; never cached as population-invariant |

The confirmed duplication was candidate-specific rather than invariant: each
horizon step computed support, geometry, and the action-to-wrench map, then the
loaded-command resolver recomputed the same three quantities for the same
candidate states. The optimized path computes the candidate-specific map once,
applies it separately to total and support action, and passes the resulting
support wrench to the loaded execution transform.

## Semantic-preserving changes

1. First-action interface screening still evaluates all 80 registered 0.25 ms
   semi-implicit spring-damper substeps. The temporal Python loop is replaced by
   precomputed powers of that exact discrete linear recurrence; every substep is
   still present for peak-force and peak-moment evaluation.
2. A candidate-step action-to-world-wrench allocation map is built once and
   applied to both total action and support action.
3. The already computed support wrench is passed into future loaded execution,
   removing duplicate support dynamics, geometry, and allocation.
4. Full-horizon instrumentation now separates setup, support dynamics,
   geometry, cuff allocation, loaded execution/wrench transforms, interface
   propagation, Human propagation, and bookkeeping. Episode summaries also
   record per-section maximum and 20 ms deadline misses.

No constraint is approximated or weakened. Candidate-dependent loaded/interface
states remain candidate-dependent.

## Runtime profile

Full matched episodes used the same deterministic production configuration and
completed at 4.810 s. Values are milliseconds per MPC solve.

| Section | Baseline mean | Baseline p95 | Optimized mean | Optimized p95 | Optimized max |
|---|---:|---:|---:|---:|---:|
| candidate generation | 0.041 | 0.047 | 0.041 | 0.049 | 0.077 |
| candidate population evaluation | 19.396 | 21.332 | 15.056 | 15.818 | 32.061 |
| Human dynamics propagation | 4.960 | 5.066 | 4.995 | 5.190 | 8.834 |
| interface-state propagation | 2.377 | 2.450 | 2.387 | 2.540 | 5.046 |
| cuff allocation | 1.204 | 1.235 | 1.272 | 1.354 | 2.775 |
| loaded execution / wrench transforms | 5.070 | 5.175 | 2.276 | 2.439 | 4.620 |
| first-action executable screening | 4.337 | 4.514 | 1.661 | 1.839 | 3.795 |
| force/motion constraint and cost evaluation | 0.280 | 0.299 | 0.284 | 0.309 | 0.508 |
| elite selection/update | 0.068 | 0.079 | 0.067 | 0.078 | 0.095 |
| other Python/NumPy overhead | 1.289 | 1.348 | 1.291 | 1.469 | 1.711 |
| solve total | 25.131 | 27.149 | 18.118 | 19.092 | 37.352 |
| externally measured solve | 25.195 | 27.216 | 18.180 | 19.156 | 37.426 |

The baseline run predates serialization of per-section maxima, so only its
whole-solve max is available: 28.199 ms. The final optimized artifact records
mean/p95/max for every section. The dominant remaining deterministic section is
the unchanged batched RK4 Human dynamics propagation (4.995 ms mean), followed
by interface propagation (2.387 ms) and loaded transforms (2.276 ms).

The final run has 2/202 externally measured solves above 20 ms (0.9901%); p95 is
19.156 ms. One broad wall-clock outlier raises several independent vectorized
sections together and produces the 37.426 ms maximum, consistent with process
scheduling/system jitter rather than one newly dominant mathematical kernel.
The simulated action hold remains a fixed number of physics steps, so this
wall-clock overrun does not alter simulated time or the executed action-hold
duration. This satisfies the requested p95 engineering target, but it is not a
hard worst-case real-time guarantee.

## Equivalence evidence

Baseline and optimized full traces have identical task phase labels, executed
generalized actions, Human q/dq estimates and evaluation truth, executable
wrenches, physical cuff wrench, and interface states. The only nonzero numeric
trace differences are prediction-only force values: at most
5.684e-14 N for the predicted next wrench and 4.263e-14 N for predicted peak
force. All 202 solves remain `SAFE_ACTION`; phase transitions remain 0.000,
2.150, 2.875, and 4.810 s.

The baseline artifact did not persist the full selected horizon sequence, so an
array-level pre/post sequence comparison is unavailable. Deterministic selected
first actions are nevertheless identical at every executed solve, and focused
tests compare the optimized recurrence against the former substep recurrence
and the shared allocation map against separate total/support allocations at
tight tolerances. Predicted physical-force errors, phase completion margins,
and all safety outcomes are unchanged to reported precision.

## Final matched episode

- Status: `OUTBOUND -> HOLD -> RETURN -> COMPLETE`; duration 4.810 s.
- Estimated peak joint velocity: [25.701, 59.984] deg/s; evaluation-only truth:
  [25.766, 60.076] deg/s, below [45, 75] deg/s.
- Deployable realized peak acceleration: [189.065, 458.692] deg/s2;
  evaluation-only truth: [193.487, 481.891] deg/s2, below [300, 600] deg/s2.
- Peak/cumulative physical force: 130.431 N / 452.762 N s; peak moment:
  19.575 Nm.
- Peak interface translation/rotation: 5.107 mm / 3.422 deg.
- Human-state estimation RMSE: q [0.001925, 0.004233] deg; dq
  [0.08435, 0.15799] deg/s.
- Physical force-norm prediction error RMSE/p95/max:
  1.362/2.617/5.329 N.
- Local HOLD plus safety runtime mean/p95/max: 0.661/0.795/0.964 ms.
- Safety: 962 `SAFE_UNCHANGED`, zero force-gate, BRAKE, structural, or MuJoCo
  warning events.
- Path freedom remains structural: no full time reference, coordination ratio,
  or path corridor is present.

Artifacts:

- `results/goal_mpc_runtime_v1/baseline_profile/`
- `results/goal_mpc_runtime_v1/optimized_attempt_03_final/`

Conclusion: the deterministic Stage-5 implementation meets the p95 runtime
checkpoint and preserves the matched complete episode. It is ready for a clean
checkpoint before the separately authorized small interface-mismatch test. The
two isolated deadline misses should remain visible; hard real-time/WCET claims
would require a separate timing qualification.
