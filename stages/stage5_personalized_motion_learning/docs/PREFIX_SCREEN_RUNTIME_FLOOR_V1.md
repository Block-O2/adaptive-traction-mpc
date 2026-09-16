# Stage-5 same-semantics prefix-screen runtime floor v1

## Plain-language result

Checkpoint `765dddb` preserves the preceding runtime/latency audit.  The current
5/10/15/20 ms screen can be implemented materially faster without changing a
controller decision: the matched fixed-snapshot solve fell from 53.43 ms mean /
54.20 ms p95 to 42.90 ms mean / 43.43 ms p95.  Prefix screening itself fell
from 38.19 to 27.50 ms mean.  A paired complete episode produced identical
actions, plant traces, phases and safety results; only prefix-prediction
roundoff at about `1.1e-14` remained.

The result is **IMP-B — MAJOR IMPROVEMENT, STILL ABOVE 20 MS**.  Every one of
the 219 episode MPC solves still exceeded 20 ms.  The remaining solve is
dominated by the required two population screens, each propagating 32
candidates through 80 sequential physical substeps, plus about 13.5 ms of
ordinary horizon dynamics.  No hard real-time or WCET claim is made.

## Frozen computation and data flow

```text
estimated Human/interface state + fixed active Human model
                         |
               support(q,dq) + CEM delta-u
                         |
          32 candidate first total Human inputs
                         |
     loaded robot target + cuff allocation + low-level feedback
                         |
        executable-command/Safety-Filter preview (batched)
                         |
      nominal 20 ms force/moment hold preview (batched)
                         |
     V2 cumulative prefix screen, repeated for 2 CEM iterations
       +--------------------------------------------------+
       | broadcast one causal state to 32 candidates      |
       | 4 x 5 ms segments                                |
       |   20 x 0.25 ms sequential physical substeps      |
       |     world/Human frame transforms                 |
       |     Kelvin-Voigt translation/rotation update     |
       |     transmitted physical wrench -> Human input   |
       |     four-stage RK4 Human dynamics                |
       |     candidate geometry/frame update              |
       |   record q,dq/interface state at 5/10/15/20 ms   |
       |   refresh support/allocation/loaded command      |
       +--------------------------------------------------+
                         |
 cumulative acceleration margins + force/command feasibility mask
                         |
 feasible full-horizon rollout -> cost -> elites -> selected action
```

The 32 candidates are independent and already share one NumPy batch.  The two
Human joints, three-axis interface coordinates and executable-wrench
calculations are also batched.  The 80 time steps cannot be evaluated in
parallel without changing the recurrence: every Human/interface/frame state is
the initial condition for the next 0.25 ms step.

| Classification | Quantities |
|---|---|
| Solve-invariant | Human/interface parameters, registered limits, 0.25 ms step, prefix times, geometry basis/lengths, allocation metric |
| Candidate-invariant at initialization | measured Human/interface state, explicit base drive/history, prior executable command |
| Candidate-specific after command application | executable wrench, base drive, interface states, Human q/dq, Jacobian/frame, support, allocation, transmitted wrench, margins |
| Constant over all 80 substeps | numerical step and physical/model parameters only |
| Sequential Python loop | four segments times 20 dependent substeps |
| Batched NumPy | all 32 candidates inside every substep; no candidate-by-candidate Python loop |

## Profile evidence

The fixed benchmark restores the same MPC and RNG snapshot for every solve,
warms 20 solves and measures 300.  Region instrumentation is diagnostic and
therefore reported separately from uninstrumented production timing.  The
profile observed exactly two prefix calls per solve, 32 candidates per call,
80 substeps per call, 1600 RK4 steps and 6400 prefix continuous-dynamics
evaluations per solve.

| Prefix region, both CEM iterations | Checkpoint mean [ms] | Optimized mean [ms] | Optimized p95 [ms] |
|---|---:|---:|---:|
| Human forward dynamics | 23.556 | 13.981 | 14.240 |
| Geometry and frame update | 5.969 | 5.336 | 5.495 |
| Interface state and transmitted wrench | 4.941 | 4.679 | 4.866 |
| Drive frame transforms | 0.412 | 0.406 | 0.434 |
| Loaded command refresh | 0.462 | 0.451 | 0.487 |
| Support and allocation refresh | 0.439 | 0.464 | 0.497 |
| State copy/setup | 0.121 | 0.112 | 0.123 |
| Acceleration/feasibility comparison | 0.082 | 0.072 | 0.082 |
| Candidate command column construction | 0.004 | 0.004 | 0.005 |
| Instrumented region sum | 35.986 | 25.504 | not additive by quantile |

The post-optimization function profile still assigns 14.3 ms/solve under
profiler overhead to 6400 calls of the Stage-5 prefix continuous dynamics,
about 3.9 ms to 1620 cached-geometry calls, and substantial remaining time to
small-array `cross`/`einsum` operations.  Python-visible peak allocation was
about 0.76 MB for one traced solve (about 82 kB net retained); allocation was
not large enough to justify a persistent shared workspace and its state-leak
and thread-safety burden.

## Retained implementation-only changes

- Cache immutable Human beta, ROM soft-limit boundaries, geometry bases and
  geometry lengths once per preview.
- Use a Stage-5-only batched continuous-dynamics kernel with the same equations
  and float64 precision.
- Use the closed-form inverse of the same symmetric 2x2 Human mass matrix.  The
  largest observed prefix difference from `np.linalg.solve` was about
  `1.1e-14` in acceleration and did not change any predicate.
- Skip construction of the full cubic soft-limit law only when every candidate
  is provably inside its zero-torque region; use the inherited exact law when
  any candidate is outside.
- Cache geometry invariants while retaining candidate-specific trigonometry,
  Jacobians and frames.
- Expose evaluation-only prefix interface state and executable-wrench arrays so
  the equivalence gate can compare them.  They do not enter control decisions.

Candidate batching was already present.  Experiments that stacked more small
arrays or manually expanded cross products were not retained because they were
neutral or slower.  A reusable workspace was not retained.  Numba, JAX,
Cython, line-profiler and Scalene are absent; CFFI happens to be importable but
is not a declared Stage-5 dependency or repository build convention.  No new
compiler/JIT dependency was added silently.

## Runtime benchmark

| Frozen snapshot/path | Prefix mean / median / p95 / p99 / max [ms] | Total mean / median / p95 / p99 / max [ms] | Process mean [ms] |
|---|---:|---:|---:|
| Nominal reference | 38.193 / 38.111 / 38.767 / 39.439 / 64.244 | 53.429 / 53.297 / 54.195 / 54.584 / 92.969 | 53.249 |
| Nominal optimized | 27.495 / 27.420 / 27.883 / 28.349 / 36.690 | 42.902 / 42.768 / 43.428 / 44.739 / 61.403 | 42.764 |
| Progressive theta_5 reference | 38.371 / 38.344 / 38.870 / 39.330 / 39.893 | 53.770 / 53.748 / 54.442 / 54.915 / 55.549 | 53.618 |
| Progressive theta_5 optimized | 27.856 / 27.853 / 28.232 / 28.409 / 28.480 | 43.405 / 43.402 / 43.902 / 44.123 / 44.688 | 43.279 |

For the paired nominal snapshot, prefix mean decreased 28.01% (1.389x), and
total mean decreased 19.70% (1.245x).  The optimized total is 53.40% below the
old 92.06 ms pre-cache path and 19.73% below the checkpoint's 53.45 ms record.
The second active-model snapshot confirms that the gain is not confined to one
nominal beta vector.  The nominal 300-solve run contained one isolated tail
outlier in each arm; the p99 values remained 54.58 and 44.74 ms, so the report
retains both the p99 and the observed max rather than quoting a best run.

## Strict equivalence

Reference and optimized solves used identical restored snapshots and RNG.
Across nominal/near-limit and progressive-theta_5 full solves:

- candidate feasibility and prefix-feasibility masks were exact;
- candidate costs, full-horizon predicted states and constraint margins were
  exact;
- elite indices, selected sequence and selected first action were exact;
- executable force/moment, Safety Filter and gate diagnostics were exact;
- prefix interface states and commands differed by at most `1.42e-14`;
- prefix Human state differed by at most `8.33e-17` and acceleration/margin by
  at most `1.11e-14`.

Saved controller-side states from the known mass +8% conservative false-positive
event and retained low/low/high real short-transient event produced continuous-
dynamics differences of `2.13e-14` and `3.55e-15`, respectively.  Evaluation
truth was not used by either implementation.

The paired regression episode completed in both arms at 4.935 s with identical
phase transitions (HOLD 2.110 s, RETURN 2.610 s), all 219 actions, q/dq,
physical force/moment, deployable acceleration and model-version traces exact.
Both had 219 SAFE_ACTION, 987 SAFE_UNCHANGED, zero gate/BRAKE/warnings, peak
force 120.545 N, cumulative force 459.488 Ns, peak moment 16.499 Nm, peak
estimated velocity `[13.546, 25.551] deg/s` and acceleration
`[173.145, 395.376] deg/s^2`.  Episode runtime changed from 53.844 ms mean /
54.746 ms p95 to 44.006 ms mean / 45.501 ms p95; all 219 solves still missed
20 ms.

## Same-semantics floor and next study

The fastest measured same-semantics prefix result is 27.495 ms mean / 27.883
ms p95 on the nominal snapshot; the fastest total is 42.902 ms mean /
43.428 ms p95.  The progressive values are essentially the same.  Prefix physical
propagation remains dominant, followed by about 13.5 ms ordinary horizon
dynamics.  A total below 20 ms would leave roughly 4--5 ms for the entire
prefix screen, requiring a large further reduction.  No obvious remaining
candidate-loop duplication or invariant reconstruction was found.  Native
compilation of the exact recurrence could be investigated only after choosing
and supporting a repository build mechanism; its benefit has not been proven.

Decision: **IMP-B — MAJOR IMPROVEMENT, STILL ABOVE 20 MS**.

The smallest follow-up is design-only until separately approved:

1. Freeze whether the engineering acceleration contract is a 5 ms transient,
   a 20 ms realized-motion interval, both, or two distinct contracts.
2. Compare the current exact high-level screen against an architecture where a
   fast execution-level command/wrench/slew guard owns short transients while
   Goal-MPC owns the slower Human-motion envelope; do not loosen limits.
3. Evaluate a multi-rate high-level Goal-MPC and faster low-level safety loop,
   including full latency, phase, force and acceleration revalidation.
4. Consider screening fewer candidates only if an evidence-backed mechanism
   preserves the feasible-first guarantee; do not assume a subset is safe.

Acceleration monitoring remains **A-MONITOR-UNRESOLVED** and the offline
alpha=0.25 personalization result remains unimplemented.
