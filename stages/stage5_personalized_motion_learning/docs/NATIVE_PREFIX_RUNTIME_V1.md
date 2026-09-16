# Stage-5 exact native prefix runtime feasibility

## Plain-language result

The exact current 5/10/15/20 ms prefix screen can run within the 20 ms
replanning budget on the measured development host without changing its
control or physical semantics.  A narrow optional C backend reduced the prefix
screen from about 27.5 ms to 3.3 ms and the full fixed-snapshot Goal-MPC solve
from about 43.2 ms to 19.0 ms.  Nominal and progressive-theta5 p95 values were
19.29 and 19.34 ms.  The paired complete-episode replay also stayed below 20 ms
at p95 (19.57 ms), although 3 of 219 solves exceeded 20 ms and the observed max
was 28.88 ms.  This is an engineering timing result, not a WCET or hard
real-time certification.

Decision: **NAT-A — SAME SEMANTICS REAL-TIME BUDGET MET** under the registered
representative p95 criterion.

## Checkpoint and frozen contract

The predecessor IMP-B work was frozen in commit `038aef4` with:

- 5/10/15/20 ms cumulative prefix acceleration checks;
- 0.25 ms physical substeps, 20 substeps per prefix and 80 total;
- 32 candidates, two CEM iterations and the unchanged horizon;
- float64 equations, RK4 Human integration, semi-implicit interface update,
  loaded execution semantics and feasibility predicates;
- no change to acceleration limits, Human-ID, trust/gamma, task, Safety
  Filter, BRAKE, force gate or personalization.

## Native boundary and data flow

The smallest useful native boundary is one 5 ms physical segment for a whole
candidate batch.  Segment-boundary support, allocation and loaded-command
refresh stay in their existing Python implementations because they are
candidate-dependent authority logic and accounted for less than 1 ms in the
prior profile.  Porting them would enlarge the native semantic surface without
being needed to meet budget.

```text
Python, once per CEM population
  initial state/interface/frame + first executable command
  controller constants packed once per preview
                 |
                 v
  repeat four prefixes (5/10/15/20 ms)
    update explicit base drive from command increment        [Python]
    propagate 32 candidates x 20 dependent 0.25 ms steps     [one C call]
      frame transform of base drive
      semi-implicit translation/rotation interface step
      physical spring-damper force and moment
      Human generalized input at the cuff
      float64 RK4 Human step
      geometry/Jacobian/frame update
    store prefix state/interface/command                     [Python]
    support + cuff allocation + loaded command refresh       [Python]
                 |
                 v
  cumulative prefix acceleration + feasibility              [Python]
  unchanged CEM cost/elites/selection/Safety Filter          [Python]
```

There are four native calls per population and eight per normal two-iteration
solve, never one call per candidate or substep.  The sequential temporal
recurrence remains sequential inside C.  Candidate independence is expressed
by the inner candidate batch loop.  C does not receive CEM costs, task phase,
Safety Filter state, MuJoCo truth, plant parameters, or logging objects.

### Boundary inputs and outputs

Inputs are contiguous float64 arrays for Human state, interface translation /
velocity / rotation / angular velocity, Human-frame rotation, Jacobian, base
drive and angular drive, plus a 49-value immutable controller-constant vector.
The constant vector contains the fixed Human beta/ROM soft-limit values,
controller nominal interface K/D/effective mass/inertia, geometry bases and
lengths, rest interface state and configured timestep.

State arrays are updated in place.  Production returns only the final segment
state needed for the next segment boundary.  Audit mode additionally records
every substep's q/dq, four interface-state vectors and physical force/moment;
prefix diagnostics are reconstructed by the unchanged Python code.

## Toolchain decision

The repository had no C/C++ extension, Cython, Numba, JAX or pybind11 path.
CFFI happened to be installed but was not declared and was therefore not used
as a permanent dependency.  Apple clang was available and Stage 5 already
used setuptools.  The retained backend is a small CPython C extension built by
setuptools using only the Python buffer protocol; it adds no runtime package
dependency and does not require NumPy headers.

The build disables floating-point contraction (`-ffp-contract=off`; strict FP
flags are selected on Windows), does not enable fast-math and builds through
both `setup.py build_ext --inplace` and a PEP-517 wheel.  The readable NumPy
backend remains the default/reference path.  `prefix_backend="native"` is an
explicit selection; `prefix_backend="auto"` has a tested NumPy fallback when
the extension is unavailable, while an explicit unavailable native request
fails loudly.

## Numerical and control equivalence

Absolute regression tolerance remained `1e-11`; it was not loosened.

| Snapshot | Maximum numeric difference | Feasibility masks | Elite indices | Selected sequence/action | Safety diagnostics |
|---|---:|---|---|---|---|
| Nominal / near-limit fixed solve | 5.60e-14 | exact | exact | exact | exact |
| Progressive theta5 fixed solve | 6.13e-14 | exact | exact | exact | exact |
| Saved conservative false-positive event | 4.26e-14 | n/a segment audit | n/a | n/a | no truth used |
| Saved retained real short-transient event | 4.26e-14 | n/a segment audit | n/a | n/a | no truth used |

The full-solve comparison covered every CEM population's prefix states,
interface state, executable wrench, cumulative acceleration, margins,
feasibility masks, candidate costs, elite indices and selected action.  The
saved-event checks compared every 0.25 ms substep, including physical
force/moment.  Repeated native calls were deterministic and had no stale
workspace state.

The paired existing episode completed in both arms with identical phase
transitions, q/dq, executed actions, physical wrench, acceleration monitor,
model version, Safety Filter, BRAKE, force-gate and warning results.  The
largest selected-prefix difference was `8.88e-14`; all physical plant traces
were exact.

## Paired fixed-snapshot runtime

The benchmark used 20 warmups and 300 timed solves per backend and snapshot in
one process, with alternating backend order.  Values are milliseconds.

| Snapshot/backend | Prefix mean / median / p95 / p99 / max | Total mean / median / p95 / p99 / max | Process mean |
|---|---:|---:|---:|
| Nominal NumPy | 27.539 / 27.503 / 27.983 / 28.616 / 30.710 | 43.219 / 43.168 / 43.867 / 44.734 / 47.009 | 43.099 |
| Nominal native | 3.370 / 3.283 / 3.596 / 3.682 / 15.813 | 19.023 / 18.871 / 19.285 / 19.841 / 56.618 | 18.915 |
| Theta5 NumPy | 27.502 / 27.489 / 27.925 / 28.076 / 28.848 | 43.152 / 43.140 / 43.722 / 43.940 / 44.916 | 43.042 |
| Theta5 native | 3.317 / 3.279 / 3.533 / 3.633 / 3.717 | 18.930 / 18.899 / 19.340 / 19.575 / 19.641 | 18.881 |

The nominal native run contained one isolated scheduling/outlier event; p99
remained 19.84 ms but the observed max was 56.62 ms.  The result therefore
does not support a strict deadline or WCET claim.  Prefix mean speedup was
8.17x nominal and 8.29x theta5; total mean speedup was 2.27x and 2.28x.

## Break-even and remaining hotspot

Measured native non-prefix work was 15.65 ms mean / 15.93 ms p95 nominal and
15.61 ms mean / 16.02 ms p95 theta5.  A simple component budget therefore
leaves about 4.35/4.07 ms nominal and 4.39/3.98 ms theta5 for prefix mean/p95.
The native prefix used 3.37/3.60 ms and 3.32/3.53 ms, leaving about 0.48 ms of
p95 component margin in the tighter theta5 case.  The measured total p95—not a
sum of separate quantiles—was 19.29/19.34 ms.

The ordinary full-horizon candidate dynamics now dominates at about 13.5 ms
mean.  No second native optimization pass was started because the registered
p95 target was already met and this task was limited to the prefix recurrence.

## Production integration and limitations

The native backend is retained because it provides a material speedup,
preserves decisions, is deterministic in repeated fixed-snapshot tests, builds
with the existing setuptools toolchain and leaves the NumPy reference intact.
It is not silently selected: current call sites default to `numpy`, and a
runtime must request `native` or deliberately request `auto`.

This result is host/compiler specific.  New architectures, compilers, Python
versions or numerical libraries require rebuilding and rerunning the same
native/reference gate.  The episode's three deadline misses and the fixed-run
max outlier remain deployment evidence against any hard real-time claim.

## Next controlled study (design only)

Because NAT-A is reached, the next study may return to the previously deferred
personalization-speed comparison, but it was not run here:

- Arm A: bounded update smoothing alpha = 0.10.
- Arm B: bounded update smoothing alpha = 0.25.
- Keep max step 0.03, evidence/validation rules, gamma 0.5, damping +20%,
  matched seeds, acceleration monitor, interface, task and limits unchanged.
- Run as a controlled closed-loop comparison; do not treat the prior saved-data
  alpha=0.25 counterfactual as closed-loop evidence.
