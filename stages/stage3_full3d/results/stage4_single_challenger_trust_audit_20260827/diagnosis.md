# Stage-4 single incumbent--challenger trust diagnosis

This is an offline, non-default replay of saved sensor traces. L1/L2, the
11-base estimator and bounds, L3 reporting, controller, optimizer, allocator,
pacing, plant, trajectory, and safety settings are unchanged. Oracle data are
attached only after a challenger decision.

## Lifecycle

There is exactly one incumbent control model and at most one active challenger.
The challenger freezes the incumbent present at its fit time. While it is
pending, all valid measurements and integral history continue to accumulate,
but no competing estimator candidate is launched for L4 promotion. At a
promotion, the incumbent becomes the challenger; at a rejection, it is
unchanged. Immediately after either decision, the next challenger is fitted
from all valid data accumulated through that decision and starts a fresh 0.5 s
embargo. No challenger has a superseded or reference-race exit.

## Anytime error control

For one-based challenger cycle j, allocate

`alpha_j = 0.05 / [j (j + 1)]`.

Since the sum of `1/[j(j+1)]` over an unbounded stream is one, the total false
promotion budget is 0.05 without a task-duration-dependent challenger ceiling.
Within cycle j, Bonferroni divides alpha_j across the population prior, the
fixed incumbent, and the three registered looks at 8/12/16 clean non-overlap
0.5 s blocks. The first two cycles therefore use per-reference/per-look alpha
0.004166667 and 0.001388889. Each comparison uses the existing lag-2 HAC
one-sided upper bound; promotion requires both upper bounds below zero and a
positive-definite constrained model. At 16 blocks without support, reject.

## Primary replay

| case | challengers P/R/Pending | first promotion / phase | decided validation durations | longest no-promotion |
|---|---:|---:|---:|---:|
| ideal 200 Hz | 3, 2/0/1 | 10.88 s / 0.473 | 5.50, 8.50 s | 10.88 s |
| random noise 200 Hz | 2, 1/0/1 | 17.90 s / 0.778 | 12.52 s | 17.90 s |
| F/T bias + drift 200 Hz | 2, 1/0/1 | 17.90 s / 0.778 | 12.52 s | 17.90 s |
| bias + delay 200 Hz | 1, 0/0/1 | none | none | 13.31 s |
| delay + ZOH 100 Hz | 1, 0/0/1 | none | none | 12.79 s |

All nine challengers are ordinary-rank and RRQR-rank 11, and all nine have
active physical bounds. Their L3 status is therefore uniformly
`identified_boundary_pressured`; active-bound counts range from one to six,
condition numbers from 338 to 11137, and residual RMS from 0.0131 to 0.0540
Nms.

Useful data continue accumulating during validation. The first ideal
challenger adds 275 valid measurements, its second adds 425; noise and
bias+drift each add 626 before first promotion. The delay cases add 398 and 448
valid measurements respectively, but still do not obtain eight clean future
validation blocks before the saved runs terminate at the existing commanded
cuff-force gate. Thus raw-data accumulation is not the bottleneck there; clean
causal validation information and available task duration are.

## Oracle diagnosis

All four promoted challengers improve post-decision oracle generalized-torque
prediction. Full-trace oracle error changes 4.325->3.641 Nm for ideal,
4.430->4.143 Nm for noise, and 4.430->4.119 Nm for bias+drift. There are no
statistically rejected challengers in these saved traces, so the question of a
rejected-but-oracle-better challenger is empirically untested rather than
assumed false.

The former race bias is structurally absent: there is no competing challenger
and no superseded outcome. Parameter compensation remains. Ideal moves toward
true beta (normalized span distance 0.460->0.401), while noise moves
0.460->0.482 and bias+drift 0.460->0.470 despite improving oracle torque
prediction. The promoted models are therefore control-useful on this audit but
not reliable physical-parameter recovery in those realism cases.

## Practical timing and recommendation

The earliest ideal promotion occurs after 47.3% of the 23 s task; the second
leaves only 3.62 s. Under noise and bias+drift, first promotion occurs after
77.8%, leaving about 5.1 s. Delay/ZOH cases never promote before their existing
safety termination. Single-challenger lifecycle correctness therefore removes
selection bias but does not make patient-specific adaptation timely.

The trust subsystem is ready for one final non-default closed-loop
revalidation only as a test of late/no-promotion behavior, not as evidence that
online patient adaptation benefits most of this short task. No rule parameter
should be changed to force earlier promotion. Production default/freeze should
remain pending until that controlled revalidation confirms safe fallback to the
prior/incumbent and quantifies whether the small remaining post-promotion time
has practical value.
