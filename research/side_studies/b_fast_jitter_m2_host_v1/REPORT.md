# B FAST Jitter Attribution & Frozen M2 Host-Clock Execution v1

**STATUS**: Track A historical root cause remains unconfirmed; current tested FAST service recovered without B repair. Track B proves **M2_HOST_RESEARCH_FEASIBLE**. No **REALTIME_DEPLOYMENT_QUALIFIED** claim. Both tracks completed independently and no heavy physical runs overlapped.

**Track A — FAST**: historical047/048 p95 about5.4ms vs002–005 7.87–9.58ms was reconstructed read-only. Mathematical/source/native-binary/timing-boundary equality is confirmed; broad owner/physics wall slowdown and idle-phase regression are supported, a CPU-frequency/Windows-memory/descheduling root cause is not. Two low-cost B controls and their measurement limits are retained. No controller performance repair. Full tail events and p50/p95/p99, rolling1s, miss/backlog are in FAST_JITTER_ATTRIBUTION.md and per-run axes.

**Track B — M2**: offline120D/K3/issued slots/mask/Q identity PASS; guard-on19ms is separated from retained40ms bridge/100ms native lifecycle. Guard-on016=0 nonzero executions, guard-off017=5. Fully exported M2 valid=6, nonzero native plan executions=25, associated native steps=143,645; new selection/carry separate. No Q training or online adaptation. Detailed lineage: EXECUTED_RESIDUAL_RECEIPTS.json. Compute and lateness: M2_COMPUTE_AND_LATENESS.json.

**Paired B vs M2**:

| Pair | raw B J_F N·s | raw M2 J_F N·s | B−M2 N·s | moment integral change | nonzero M2 plans | result |
|---|---|---|---|---|---|---|
| nominal_pair1 | 1453.310 | 1376.657 | 76.653 | +18.92% | 5 | VALID_PAIR |
| nominal_pair2 | 1452.946 | 1357.712 | 95.234 | +24.20% | 6 | VALID_PAIR |
| deviation_pair1 | 1452.299 | 1334.509 | 117.789 | +6.75% | 4 | VALID_PAIR |
| deviation_pair2 | 1429.088 | 1340.849 | 88.238 | +22.85% | 5 | VALID_PAIR |

All four exposed-condition gains are positive, but moment integrals increase6.75–24.20%. Deviation pair1 force peak increases107.18→112.30N. True/estimated tracking and clearances are fully reported; M2 does not dominate every metric. The legal-deviation tests repeat one registered two-action prefix at two seeds; different independent prefixes were NOT_RUN, so no claim across arbitrary legal deviations is supported.

| Pair / phase | J_F B / M2 N·s | clock duration B / M2 s | mean force B / M2 N | duration contribution M2−B N·s | mean-force contribution M2−B N·s |
|---|---|---|---|---|---|
| nominal_pair1 / OUTBOUND | 741.349 / 735.112 | 9.01000 / 9.07500 | 82.281 / 81.004 | +5.307 | -11.544 |
| nominal_pair1 / HOLD | 54.918 / 54.939 | 1.03000 / 1.03000 | 53.318 / 53.339 | +0.000 | +0.021 |
| nominal_pair1 / RETURN | 657.043 / 586.605 | 9.01150 / 9.01150 | 72.924 / 65.106 | +0.000 | -70.438 |
| nominal_pair2 / OUTBOUND | 748.752 / 740.854 | 9.01000 / 9.01000 | 83.102 / 82.226 | +0.000 | -7.898 |
| nominal_pair2 / HOLD | 54.916 / 54.651 | 1.03000 / 1.02500 | 53.317 / 53.318 | -0.267 | +0.002 |
| nominal_pair2 / RETURN | 649.278 / 562.207 | 9.01275 / 9.01150 | 72.062 / 62.398 | +0.000 | -87.072 |
| deviation_pair1 / OUTBOUND | 739.906 / 724.835 | 9.01000 / 9.01000 | 82.121 / 80.448 | -0.000 | -15.071 |
| deviation_pair1 / HOLD | 54.647 / 54.912 | 1.02500 / 1.03000 | 53.314 / 53.312 | +0.267 | -0.002 |
| deviation_pair1 / RETURN | 657.745 / 554.763 | 9.01125 / 9.01150 | 73.002 / 61.572 | +0.000 | -102.982 |
| deviation_pair2 / OUTBOUND | 718.367 / 724.779 | 9.01000 / 9.00500 | 79.730 / 80.486 | -0.401 | +6.813 |
| deviation_pair2 / HOLD | 55.183 / 54.909 | 1.03500 / 1.03000 | 53.317 / 53.310 | -0.267 | -0.007 |
| deviation_pair2 / RETURN | 655.538 / 561.161 | 9.00925 / 9.01150 | 72.797 / 62.282 | +0.338 | -94.715 |

| Pair / method | force peak N | moment integral Nm·s / peak Nm | true shank / measured sleeve minimum mm | true-reference TASK RMS tracking joint1 / joint2 deg |
|---|---|---|---|---|
| nominal_pair1 / B | 115.563 | 96.061 / 15.744 | 17.273 / 9.375 | 0.466 / 0.452 |
| nominal_pair1 / M2 | 114.116 | 114.234 / 15.743 | 11.639 / 3.975 | 0.433 / 0.796 |
| nominal_pair2 / B | 115.558 | 96.436 / 15.742 | 17.250 / 9.354 | 0.466 / 0.454 |
| nominal_pair2 / M2 | 110.277 | 119.769 / 15.742 | 15.238 / 7.224 | 0.424 / 0.894 |
| deviation_pair1 / B | 107.177 | 108.620 / 15.302 | 11.731 / 4.285 | 0.461 / 0.509 |
| deviation_pair1 / M2 | 112.299 | 115.957 / 15.306 | 13.487 / 5.542 | 0.429 / 0.874 |
| deviation_pair2 / B | 112.247 | 98.520 / 15.299 | 16.776 / 8.859 | 0.453 / 0.509 |
| deviation_pair2 / M2 | 107.222 | 121.032 / 15.298 | 14.891 / 6.881 | 0.424 / 0.920 |

Phase-duration attribution uses the exact symmetric product decomposition per OUT/HOLD/RETURN: ΔJ=Δduration×average(mean force)+Δmean force×average(duration). Both physical phase-clock and integrated trace durations are retained, and phase sums close the original full-task integral. No HOLD clipping, shortening or fabricated time; mean-force contribution is evidence compatible with coordination, not a pure causal identification. Same physical setup/seed/waypoints/instrumentation is frozen within each pair; real-time measured commissioning fits may differ. Moment integrals/peaks, raw force/force peak, complete native physical safety/clearance/tracking, proposal age, all rejects/fallback and runtime axes remain in PAIRED_RESULTS.json. No old1335N·s subtraction.

**Qualification** (independent axes; diagnostics do not establish engineering qualification):

| Attempt | physical | causal host | FAST engineering | legacy R2 | legacy strict55 |
|---|---|---|---|---|---|
| 001_zero_residual_smoke | PASS | PASS | PASS | FAIL | PASS |
| 002_M2_guard_on_smoke | FAIL | PASS | PASS | FAIL | FAIL |
| 003_M2_guard_off_smoke | FAIL | PASS | PASS | FAIL | FAIL |
| 004_M2_guard_on_retry | FAIL | NOT_EVALUABLE_FULL_EXPORT | NOT_EVALUABLE | NOT_EVALUABLE | NOT_EVALUABLE |
| 005_M2_guard_off_retry | FAIL | NOT_EVALUABLE_FULL_EXPORT | NOT_EVALUABLE | NOT_EVALUABLE | NOT_EVALUABLE |
| 006_B_threadCPU_nominal | PASS | PASS | PASS | FAIL | PASS |
| 007_B_threadCPU_deviation | PASS | PASS | PASS | FAIL | FAIL |
| 008_nominal_pair1_B | PASS | PASS | PASS | FAIL | FAIL |
| 009_nominal_pair1_M2 | PASS | PASS | PASS | FAIL | FAIL |
| 010_nominal_pair2_M2 | PASS | PASS | PASS | FAIL | FAIL |
| 011_nominal_pair2_B | PASS | PASS | PASS | FAIL | PASS |
| 012_deviation_pair1_B | PASS | PASS | PASS | FAIL | FAIL |
| 013_deviation_pair1_M2 | PASS | PASS | PASS | FAIL | FAIL |
| 014_deviation_pair2_M2 | PASS | PASS | PASS | FAIL | FAIL |
| 015_deviation_pair2_B | PASS | PASS | PASS | FAIL | FAIL |
| 016_M2_guard_on_final | PASS | PASS | PASS | FAIL | FAIL |
| 017_M2_guard_off_export_retry | PASS | PASS | PASS | FAIL | FAIL |

All conclusions are finite actual host-clock development simulation results. Passing FAST numeric criteria on observed lean runs does not promote B/M2 to formal runtime or hardware qualification. Legacy R2 and strict55 are reported independently and historical results unchanged.

**Negative evidence**:002/003 failed envelope routing;004 retained a partial repair's unconsumed hint;005 failed artifact export and remains partial evidence only. One integration repair cycle has two source-binding/route patch revisions, followed by one evidence-only dataclass serialization correction. The diagnostic capture-hook scope was invalidated; adjacent marker differences are retained with scheduled-wait limits. Historical slowdown cause remains unknown. Late/cancelled Q proposals and consumed issued slots remain visible. No persistent Human session or personalization claim.

**Budget**: t0=2026-10-08 12:56:02+08; hard cap15:56:02; dispatch cutoff15:36:02. At report generation wall=49.05min, physical attempts=17/20, native steps=1,769,713, physical simulation=442.42825s. START=END=17. Added bytes/CRC/final close time are in FULL_PACKAGE_VERIFICATION.json and PACKAGE_CLOSED.json. All original TASK workers JOIN exitcode0; no task-owned process remains. WSL available minimum=5.389GiB; Windows available minimum=0.367GiB; commit headroom minimum=3.962GiB; swap in/out deltas=19/0, OOM delta=0. Main Git branch/HEAD/status/index/staged diff, historical source/data and frozen Q remain unchanged. No WSL restart or power/RAM/swap/scheduler change; no unrelated process killed.

**NEXT**: On a new separately authorized bounded package, capture matched service-start/end thread CPU and scheduler wait on the actual compiled loop during a recurrence of the002–005 slowdown; preserve the frozen B/Q/40ms bridge and all safety contracts.

**REPORT PATH**: /home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1/REPORT.md; Windows review copy C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1/REPORT.md.

STOP. No automatic follow-on work.

