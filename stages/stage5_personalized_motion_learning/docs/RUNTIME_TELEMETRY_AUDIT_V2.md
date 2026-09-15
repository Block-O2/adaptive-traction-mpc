# Stage-5 Controlled Runtime Telemetry Audit V2

## Method

Part B was kept independent from Acceleration-Semantics V2. A fresh Python
process constructed one representative loaded `OUTBOUND` snapshot for
`low_low_low=(0.9,0.9,0.8)`, then restored the exact MPC/RNG state and solved it
7000 times. This reproduces the frozen V1 full-20-ms first-action screen and the
production 15-step / 32-candidate / two-iteration workload. It is a fixed-load
runtime diagnostic, not a rehabilitation campaign.

Per solve, the audit recorded wall time, process CPU time, elapsed time, and all
existing MPC section timers. Every 100 solves it also sampled GC counters,
process maximum RSS, and system load. `psutil` was unavailable. macOS exposed
neither usable CPU-frequency data nor usable thermal/performance status;
`pmset` returned error messages despite a zero exit code, the queried `sysctl`
OID was unavailable, and privileged `powermetrics` was not invoked.

## Results

| 200-solve window | Wall mean / p95 / max (ms) | Process mean / p95 / max (ms) |
|---|---:|---:|
| Fresh | 18.489 / 19.129 / 19.727 | 18.437 / 19.060 / 19.638 |
| Middle | 18.870 / 19.598 / 20.829 | 18.805 / 19.473 / 20.579 |
| Post-long | 18.864 / 19.552 / 23.658 | 18.802 / 19.452 / 23.362 |

Fresh-to-post wall time increased 2.03% and process CPU time increased 1.98%.
The historical campaign increase was approximately 16.08% (18.10 to 21.01
ms), so the 133.3 s fixed-snapshot load did not reproduce it: this is comparison
**Case C**.

Major sections moved together by about 1.020x (ratio standard deviation 0.010):
candidate population evaluation 1.021x, Human dynamics 1.025x, interface
propagation 1.020x, allocation 1.023x, loaded transforms 1.022x, screening
1.007x, and other Python/NumPy overhead 1.029x. No component diverged.

GC completed 398 collections during the benchmark. Maximum RSS rose from
approximately 522 MB to 554 MB, yet solve time rose only about 2%; this does not
support memory/GC as the dominant source of the historical 16% effect. Mean
wall-minus-process time remained small (0.053 to 0.061 ms), so this run also
does not support a material wall-only scheduling delay.

## Classification

**B6 — unresolved.** The controlled workload supports Case C: the historical
growth appears campaign/environment/state specific and is not reproduced by
the exact fixed solve. Since usable CPU-frequency, thermal, and detailed
scheduling telemetry were unavailable, B4 cannot be claimed. No controller
mathematics or implementation optimization was performed.

The smallest justified next action is to add the same lightweight per-solve
wall/process and system telemetry to a future *already-authorized* long session,
without changing control behavior, so the slowdown can be observed in the
environment where it actually occurs. A new scientific campaign solely for
runtime diagnosis is not justified.

Raw per-solve and system telemetry are kept under ignored
`results/runtime_telemetry_v2/`; `runtime_audit.json` is the compact summary.
