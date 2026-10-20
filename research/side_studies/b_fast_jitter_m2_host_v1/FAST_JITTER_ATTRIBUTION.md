# FAST Jitter Attribution

STATUS: **INCONCLUSIVE_ROOT_CAUSE / CURRENT_TESTED_FAST_PASS**. Historical degradation is real, while this package's lean runs returned close to 047/048 without a B performance repair. This does not retroactively qualify 002–005 or guarantee future scheduling.

| Historical run | FAST p50 / p95 / p99 ms | rolling1s max ms | miss | owner-work p95 ms | native-step p95 us |
|---|---|---|---|---|---|---|
| 047_C13_host_nominal_quiet | 5.004 / 5.399 / 5.931 | 5.391 | 0.46% | 4.176 | 69.63 |
| 048_C13_host_deviation_quiet | 5.005 / 5.427 / 6.228 | 5.352 | 0.85% | 4.331 | 67.58 |
| 002_B_confirm_deviation | 5.184 / 9.584 / 14.241 | 8.520 | 15.03% | 7.571 | 79.62 |
| 003_B_confirm_nominal_harness_retry | 5.071 / 8.182 / 11.960 | 8.216 | 9.03% | 6.771 | 76.45 |
| 004_B_quiet_retest_nominal | 5.111 / 9.481 / 14.110 | 7.300 | 11.86% | 7.515 | 77.62 |
| 005_B_quiet_retest_deviation | 5.050 / 7.868 / 11.008 | 6.887 | 7.75% | 6.599 | 74.63 |

The historical native binaries are hash-identical. All controller, Human, physics, task, FAST adapter and measurement code match after exact package path relocation; only seven added authoring/bootstrap/report harness files differ. Timing start/finish semantics match. Matched nominal003/004 and deviation002/005 configurations preserve the physical/task settings; seed/report labels differ where explicitly recorded in HISTORICAL_JITTER_ATTRIBUTION.json. Per-phase OUTBOUND/HOLD/RETURN, planner-active/idle distributions and every >7.5/10/15ms cycle are retained in *_JITTER_CYCLES.json.

Evidence supports a broad owner-path slowdown: p95 owner work rose from 4.176–4.331ms to 6.599–7.571ms and native-step wall spans also widened. Planner-active tails are worse within runs, but idle p95 also rose from about5.39–5.42ms to7.79–9.54ms. The regression appears in multiple task phases, so rare handoffs cannot explain its frequency. Physics catch-up is separately counted per interval; it was not proved the dominant >50% contributor to these long cycles. Aggregate feedback/observer/receipt spans must not be mistaken for a single function's exclusive compute cost.

Historical per-service thread CPU and exact descheduling were not recorded, so compute-heavy vs descheduling remains unresolved. GC, frequency/power, Windows memory and WSL scheduler causation have not been established. Current native active-session GC deferral and recorded resource values are retained; no CPU-frequency or memory-policy change was made.

Two extra B host controls used thread-CPU/GC probes and remain attribution-only. The capture hook did not replace the compiled commissioning namespace; its initial cumulative owner-span interpretation was invalidated and retained as THREAD_CPU_JITTER_DIAGNOSTICS_v1_INVALID_OWNER_SCOPE.json. Valid adjacent marker differences use the same capture anchor and include scheduled wait plus physics catch-up. They distinguish CPU accumulation from off-CPU time for the observed restored runs, but cannot retrospectively establish why002–005 slowed. Raw diagnostics and limits are explicit. No additional random micro-optimization or controller repair was attempted.

Lean current runs:

| Run | FAST p50 / p95 / p99 ms | rolling1s max ms | miss | backlog max ms | frozen engineering axis |
|---|---|---|---|---|---|
| 001_zero_residual_smoke | 5.006 / 5.411 / 6.121 | 5.658 | 0.65% | 13.016 | PASS |
| 008_nominal_pair1_B | 5.003 / 5.394 / 5.851 | 5.451 | 0.46% | 16.512 | PASS |
| 009_nominal_pair1_M2 | 5.002 / 5.491 / 6.098 | 5.355 | 0.48% | 14.435 | PASS |
| 010_nominal_pair2_M2 | 5.006 / 5.418 / 5.824 | 5.444 | 0.43% | 14.586 | PASS |
| 011_nominal_pair2_B | 5.001 / 5.439 / 6.043 | 5.422 | 0.44% | 14.170 | PASS |
| 012_deviation_pair1_B | 5.003 / 5.411 / 5.968 | 5.393 | 0.41% | 17.544 | PASS |
| 013_deviation_pair1_M2 | 5.005 / 5.448 / 5.858 | 5.389 | 0.41% | 12.836 | PASS |
| 014_deviation_pair2_M2 | 5.005 / 5.418 / 5.870 | 5.393 | 0.38% | 14.549 | PASS |
| 015_deviation_pair2_B | 5.007 / 5.485 / 6.313 | 5.413 | 0.68% | 13.717 | PASS |
| 016_M2_guard_on_final | 5.004 / 5.542 / 7.015 | 5.684 | 1.19% | 13.380 | PASS |
| 017_M2_guard_off_export_retry | 5.006 / 5.421 / 5.996 | 5.415 | 0.51% | 14.172 | PASS |

No local B implementation defect was proved to cause the historical regression. The M2 copied-namespace adapter defect is independently confirmed and repaired; it is not an explanation for B timing002–005.

