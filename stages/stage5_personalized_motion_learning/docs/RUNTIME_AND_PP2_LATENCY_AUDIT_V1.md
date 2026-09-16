# Stage-5 Goal-MPC Runtime Regression and PP2-A Latency Audit v1

## Scope and frozen boundaries

This audit starts from the PP2-A checkpoint `fe04bf06dfe5c22505e5d489b8026a5e11969007`.
It does not run a rehabilitation episode, refit Human-ID, alter the registered
motion/safety contracts, or reinterpret PP2-A. Large fixed-snapshot timing files
remain ignored under `results/pp2_runtime_latency_audit_v1/`.

## Runtime measurement contract

All Stage-5 episode summaries place `perf_counter()` immediately around
`GoalDirectedHumanSpaceMPC.solve_goal()`. The measurement includes support-action
construction, CEM sampling/update, full-horizon Human/interface propagation,
cost/constraint evaluation, loaded executable-command preview, first-action
physical-interface screening, and the preview-side Safety Filter calculation.
It excludes Human-ID fitting, future validation, progressive authority, gamma
logic, task-state updates, MuJoCo stepping, trace/JSON collection, plotting, and
report generation. Human-ID and progressive callbacks run before the timed
solve. The separately executed low-level command and its final Safety Filter
call occur after it.

The historical deterministic controller and current controller therefore time
the same outer function, but not the same control fingerprint. Commit
`4697b764e6a99441171e8d1cc6a10a141cf9cbf5` activated the V2 cumulative
5/10/15/20 ms first-action acceleration predicate. Each population screen now
couples Human and Kelvin-Voigt interface dynamics through 80 physical 0.25 ms
substeps and refreshes the loaded command every 5 ms. Human-ID itself did not
enter the CEM candidate loop.

## Matched fixed-snapshot timings

The current benchmark restores the exact MPC/RNG state before every solve,
warms up 20 solves, then measures 300 solves. Horizon/population/iterations are
unchanged at 15/32/2. The historical commit cannot accept the later session
snapshot injection API, so it was not modified to force a direct run. The
current `legacy_full20` isolation reproduces the pre-V2 semantics on the same
snapshot and agrees with both historical records.

| Path | Mean / median [ms] | p95 / p99 / max [ms] | Interpretation |
|---|---:|---:|---|
| Authoritative deterministic episode (`e6ea54b`) | 18.180 / not recorded | 19.156 / not recorded / 37.426 | State-varying 202-solve episode |
| Historical V1 fixed telemetry, fresh window | 18.489 / not recorded | 19.129 / not recorded / 19.727 | Earlier 200-solve fixed window |
| Current code, V2 omitted for isolation | 18.491 / 18.465 | 19.038 / 19.626 / 20.425 | Same current snapshot/environment |
| Current V2 before cache fix | 92.062 / 91.873 | 92.932 / 94.243 / 127.685 | Exact fixed snapshot; duplicate prefix work present |
| Current V2 after cache fix | 53.448 / 53.389 | 54.157 / 56.387 / 61.141 | Exact fixed snapshot; current semantics retained |

PP2-A's state-varying episodes reported 74.43--80.54 ms mean and
90.70--93.16 ms p95. Different feasible-subset sizes explain why those means
need not equal the deliberately fixed all-candidate snapshot; the code-region
and dominant mechanism are the same.

## Runtime root-cause components

| Component/change | Historical/current-legacy behavior | Current V2 behavior | Necessity | Mean timing evidence | Optimize? |
|---|---|---|---|---:|---|
| Full-horizon coupled Human/interface rollout | Active | Active | Required current Goal-MPC model | dynamics 15.089 ms legacy; 13.450 ms after fix | No semantic removal |
| Base executable/interface first-action screen | One 20 ms hold | Still active | Required | 1.638 ms legacy | No |
| V2 prefix acceleration screen | Absent | 5/10/15/20 ms, 80 coupled substeps per population | Required by current frozen acceleration semantics | optimized first-action screen 38.095 ms | No in this task |
| Duplicate prefix propagation for the feasible subset | Absent/cheap | Same screened rows recomputed inside horizon setup | Not required | horizon setup 38.389 -> 0.119 ms | **Yes; fixed** |
| Allocation, geometry and loaded transforms | Batched, candidate-specific | Same, plus work inside prefix propagation | Required/candidate-specific | post-fix 1.256 / 1.210 / 2.238 ms | No invariant-cache claim |
| CEM sampling, elite update and cost arithmetic | Active | Unchanged | Required | 0.044 / 0.063 / 0.299 ms | No material issue |
| Human-ID/future validation/progressive authority | Outside timed solve | Outside timed solve | N/A | 0 ms inside solve | No |
| Logging/plotting/JSON | Outside timed solve | Outside timed solve | N/A | 0 ms inside solve | No |

The fix reuses a cached first-action population for an exact subset/reordering.
It also reuses the already computed initial support value rather than obtaining
the mathematically identical value through a vectorized path that differed by
`7.1e-15` Nm and defeated exact cache matching. No candidate, prefix, force,
motion, Safety Filter, or CEM predicate is removed.

The fixed-snapshot equivalence gate found identical selected first action and
selected horizon, exact candidate feasibility masks for both CEM populations,
zero prefix-state/margin/executable-force differences, and all selected
command/safety diagnostics equal within the existing numerical convention
(`atol=1e-11`; comparison with the original support recomputation differed in
objective by only `2.27e-12`). Mean runtime fell 41.94% and p95 fell 41.72%.
It remains 2.89x the legacy isolation and above the 20 ms
period.

Wall and process CPU moved together: before the fix 92.062 vs 91.764 ms mean;
after it 53.448 vs 53.285 ms. Mean wall-minus-process time was 0.298 and 0.163
ms respectively. Python 3.10.20, NumPy 2.2.6, SciPy 1.15.3, no explicit BLAS
thread environment variables, modest RSS changes, and no wall-only delay do not
support R3 as the main explanation. macOS thermal/frequency telemetry was not
available, so no thermal claim is made.

Classification: **R1 — ALGORITHMIC / CONTROL-PATH COMPUTATION REGRESSION**.
The redundant duplicate was an implementation inefficiency; the remaining
dominant cost is the semantically active V2 coupled prefix predicate, not
diagnostic instrumentation. Runtime decision: **RT-C — PARTIAL IMPROVEMENT /
MULTIPLE CAUSES**. Reaching 20 ms now requires a separately authorized design
decision (for example different acceleration-screen formulation, fidelity,
budget, or period), not more unstructured micro-optimization.

## PP2-A adaptation latency

Times are session seconds. `theta_1` entered with inherited RPL-A POSITIVE
support. For later rows, support is new post-activation evidence for the active
predecessor. Queue time is the later of qualification and required predecessor
support.

| Transition | Rep start | First fit / candidate | Qualified | Post-support POSITIVE | Neutral block | Queued | Next activation | Active duration | `||delta theta||` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| theta_1 -> theta_2 | 0.000 | 0.995 | 2.795 | inherited | 0.000 | 2.795 | 9.300 | 9.300 | 0.017991 |
| theta_2 -> theta_3 | 9.300 | 9.300 | 11.100 | 11.105 | 0.005 | 11.105 | 18.740 | 9.440 | 0.018783 |
| theta_3 -> theta_4 | 18.740 | 18.740 | 20.540 | 20.345 | 0.000 | 20.540 | 27.615 | 8.875 | 0.016784 |
| theta_4 -> theta_5 | 27.615 | 27.615 | 29.415 | 29.420 | 0.005 | 29.420 | 36.675 | 9.060 | 0.015104 |
| theta_5 -> theta_6 | 36.675 | 36.675 | 38.475 | 38.280 | 0.000 | 38.475 | budget ended | 8.535 to session end | 0.013655 |

For the four activated transitions, the 36.675 s to theta_5 activation
decomposes into 0.995 s initial data acquisition (2.71%), 7.200 s registered
future validation (19.63%), 0.010 s extra NEUTRAL-gate waiting (0.03%), and
28.470 s repetition-boundary waiting (77.63%). Post-update support took
1.805/1.605/1.805/1.605 s in Reps 2--5, but almost entirely overlapped the
1.8 s challenger validation; it delayed queue release by only 10 ms total.
After Rep 1, accumulated session data allowed the next valid fit at each new
repetition boundary, so data acquisition was not the continuing bottleneck.

## Saved-trace alpha=0.25 counterfactual

Every comparison reconstructs the exact saved deployable block windows and
uses only estimated Human state plus deployable measured generalized input.
MuJoCo truth is not an input. The source result and traces are hash-checked
before/after. Loss units are Nms^2. The counterfactual cannot establish the
trajectory that a different controlling model would have produced.

| Transition | Qualification predecessor / alpha=.10 / alpha=.25 | alpha=.25 relative loss change | Same-rule qualification | Post-update-like predecessor / .10 / .25 | alpha=.25 post classification | D cap at .25 |
|---|---:|---:|---|---:|---|---|
| theta_1 -> theta_2 | .00049306 / .00039504 / .00032153 | -18.61% | supported | .00046956 / .00037533 / .00030746 | POSITIVE | yes |
| theta_2 -> theta_3 | .00037820 / .00030547 / .00026743 | -12.45% | supported | .00040722 / .00033147 / .00029212 | POSITIVE | yes |
| theta_3 -> theta_4 | .00032991 / .00027020 / .00022907 | -15.22% | supported | .00034672 / .00028600 / .00024442 | POSITIVE | yes |
| theta_4 -> theta_5 | .00029558 / .00024459 / .00020050 | -18.03% | supported | .00029244 / .00024334 / .00020099 | POSITIVE | yes |
| theta_5 -> theta_6 | .00025163 / .00021015 / .00016670 | -20.67% | supported | unavailable before activation | unavailable | yes |

Alpha_D of the first raw candidate was 1.19911, already 99.5% along the
evaluation-only theta_1-to-1.2 direction; later raw candidates were about
1.224--1.225. The online 0.10 rule moved alpha_D from 1.01935 to active theta_5
at 1.08799, closing 38.0% of that descriptive gap and leaving 0.11201. An
arithmetic-only alpha=0.25 chain using the same candidates would have reached
1.13799 after the same four activation opportunities (65.7% closed; 0.06201
remaining); its fifth queued successor would be 1.15963. The +/-0.03 cap binds
for alpha_D in all five per-transition alpha=0.25 calculations. No saved future
block shows prediction degradation or statistical rejection, but closed-loop
acceptability remains unknown.

Update-speed decision: **U5 — MULTIPLE FACTORS**. Repetition-boundary scheduling
dominates elapsed activation latency, while the 0.10 bounded step dominates how
far each supported activation moves. The 1.8 s future-validation rule is a
smaller fixed contribution; continuing information acquisition and the
post-update gate were not the main limit in this PP2-A session.

## Next experiment design only

Do not run until the runtime design blocker is separately accepted. Then use a
small matched A/B under damping +20%: Arm A alpha=0.10, Arm B alpha=0.25;
retain max step 0.03, all validation/post-update rules, gamma=0.5, task,
interface, acceleration monitor, limits, CEM settings and matched seed schedule.
Primary question: whether the larger evidence-validated bounded step reaches a
useful deployable prediction model in fewer repetitions without reducing
future-prediction reliability or closed-loop acceptability. Do not combine it
with trust-to-gamma pacing.

This audit does not establish real-time readiness, hardware safety, convergence,
or an online alpha=0.25 result. A-MONITOR-UNRESOLVED remains frozen.
