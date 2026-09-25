# DEV-D broad consumed-development regression

The authoritative final physical batch is `results/full3d_adaptive_integration_v1/
rigid_table_reference_repair_v1/broad_strict_v1/`. Its
`DEVELOPMENT_SUMMARY_V3.json` includes every selected case and all exact
per-case outcomes. This is **not fresh qualification**. The earlier
`broad_development_v1` (before the Auditor-driven strict recovery/task
continuous-path check) and all representative iterations remain separately
preserved. They must not be pooled as one configuration.

| Development cohort | Initial valid and physically executed | Commissioning and geometry fit | Recovery success / task entry | Full OUTBOUND–HOLD–RETURN |
|---|---:|---:|---:|---:|
| Immediately preceding rigid-table assembly v1 + v2 supplement | 23 | 23 | 22 | 5 |
| Final strict DEV-D reference version | 23 | 21 | 21 | 5 |
| Still-invalid `balanced_ordinary_r02` | 0 of 1 old key | — | — | — |

The first row is a 22-case v1 batch plus a separate one-case v2 supplement,
not a homogeneous controlled 23-case paired campaign. DEV-D held the adaptive
fitter/update laws, task MPC objective/candidates, CR12/cuff/Human physics,
table and contact settings, task/motion/force limits, DEV-C-off state and
100 ms stale-plan rule fixed. It changed commissioning reference selection and
added a strictly opt-in hard-table path screen. Physical planning delay is
replayed as continued MuJoCo motion under the old reference, not by pausing
simulation. Output differences are therefore development evidence about
reference and runtime interactions, not a clean isolated statistical effect.

Final strict DEV-D failure accounting: 5 COMPLETE, 11
`STALE_PLAN_MAXIMUM_AGE`, 3 `NO_FEASIBLE_WAYPOINT`, 2
`TASK_VELOCITY_LIMIT`, and 2
`COMMISSIONING_MEASURED_SLEEVE_PENETRATION`. All 23 remain in the selected
development denominator. The 2 early aborts have `runner_exception.json`,
`dev_d_reference_abort.json` and full native 0.25 ms contact-interval traces;
they do **not** have fabricated complete `summary.json`/5 ms trace files.
One sleeve abort occurs at 0.035 s (−0.017875 mm measured gap), the other at
5.955 s (−0.032834 mm). Sleeve collision remains disabled in MuJoCo, so the
negative signed gaps are geometric overlaps rather than sleeve contact-force
measurements.

For all 21 runs with complete 5 ms traces, the evaluation-only physical-
geometry audit found zero sampled negative requested or actual shank/sleeve
gaps. Minimum requested shank/sleeve were +14.603/+8.177 mm and minimum
actual shank/sleeve +7.418/+2.277 mm, respectively, across those 21 traces.
These minima **exclude** the 2 aborted runs, whose measured sleeve gaps are
negative. All 23 native contact monitors recorded 0 N thigh-table and
shank-table peak force and zero detected contact intervals. This removes the
old shank-reference penetration/contact pattern in the completed traces; it
does not prove continuous physical collision freedom or protection for
MuJoCo-excluded sleeve/cuff-bar pairs and articulated robot links.

All 21 completed commissioning records accepted a control-effective geometry
fit from at least 353 samples. Observed fitted angular spans were
0.195979–0.340879 rad; worst reported fit condition number 1955.253. There
were 84 commission segment planning calls, median 0.407 ms, p95 4.714 ms,
maximum 5.238 ms, with no commissioning planning deadline miss in these 21
summaries. Twenty selected segments used the logged monotone upward escape
from a pessimistically negative structural upper-shank prior; that exception
is never used in recovery/task. Task-period adaptation remains active: the
21 summaries record 324 accepted beta updates and 9453 residual updates in
aggregate. Counts show activity, not convergence or model correctness.

On 109 task planning calls, measured compute time was mean 62.708 ms, median
73.510 ms, p90 100.116 ms, p95 106.218 ms, p99 123.888 ms, maximum
124.615 ms (`hip_dominant_near_upper_current_rom_r01`). Eleven task decisions
missed the existing age deadline and were rejected; 11 cases aborted stale.
Three additional decisions returned a timely `NO_FEASIBLE_WAYPOINT` and are
**not** deadline misses. An earlier derived `DEVELOPMENT_SUMMARY_V2.json`
mistakenly counted every `activation_accepted_by_deadline=False`, including
those 3 infeasible calls, as 14 “deadline misses.” The source-level per-
decision `activation_rejected_reason` resolves the distinction; corrected
`DEVELOPMENT_SUMMARY_V3.json` reports 11. Neither artifact was erased.

For 21 complete traces, maximum recorded full-session physical cuff-force
and moment norms were 159.430 N and 22.846 Nm; full-session force integral
range was 244.167–870.909 N·s, using recorded executed-interval costs.
The 5 COMPLETE cases' time-aligned task q RMSE (degrees) were:

| Case | q1 RMSE | q2 RMSE |
|---|---:|---:|
| `balanced_ordinary_r01` | 0.418 | 0.905 |
| `elevated_start_ordinary_r01` | 0.581 | 0.456 |
| `elevated_start_ordinary_r02` | 0.641 | 0.470 |
| `hip_dominant_ordinary_r01` | 0.730 | 0.344 |
| `hip_dominant_ordinary_r02` | 0.686 | 0.354 |

Across those 21 traces there were zero recorded actual Human acceleration-
violation flags and zero evaluation-only Human ROM violation steps. The
maximum reported task CR12 actuator-torque fraction was 0.576. The 2 early
abort records lack complete full-session force/acceleration summaries, so
these aggregate limits must not be silently extended to them. The original
force, motion, ROM and robot constraints remain in code; no physical limit
was relaxed to obtain the 5 completions.

The most important interpretation is mixed: the requested hard-table path
defect is repaired in the 21 complete traces, and commissioning remains
informative, but whole-session reliability did **not** improve (5/23 complete
in both development cohorts). The new explicit sleeve monitor correctly
exposes two physical overlap failures, and the 100 ms high-level planner tail
remains a major independent failure mode. One originally COMPLETE nominal
representative also aborted on the retained conservative clearance monitor
under the changed commissioning trajectory. DEV-D is therefore partial,
not a qualified full-3D controller.
