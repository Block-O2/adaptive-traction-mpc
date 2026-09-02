# Stage 4 High-ROM Time-Scale Continuation Audit

## Scope and frozen contract

This is an engineering feasibility audit, not formal or authoritative
scientific evidence and not a controller design. The accepted A.1/B.0 work was
checkpointed at `bb012f0ac9afabd90b037eb38edbc3edf6e1fcd5`, and this audit was
run from branch `codex/high-rom-time-scale-audit`.

The only changed variable was the opt-in external constant path time scale
`alpha_scan`. Fixed MPC used the population prior. The estimator/trust lifecycle
ran in shadow mode but had no model or clock authority. MPC/CEM, estimator,
Safety Filter, BRAKE, allocator, gains, independent 200 N command and physical
gates, nominal High-ROM Human V2, 140 mm adapter, suspended scenario, seed
44104, path geometry, and Reference Manager mathematics were unchanged.

The preregistered machine-readable spec is
`configs/high_rom_time_scale_scan_v1.json`, SHA-256:

`0075d137feab5787ac949f01901bd0bee9f72915900ba197af1bb51374f41ee3`

The simulation horizon was `ceil((23/alpha_scan)/0.005)*0.005`; the old 32 s
timeout was not used. Endpoint completion used the existing exact reference
phase/termination contract rather than introducing a new tracking tolerance.

## Registered scan results

Because every trajectory failed at alpha 0.25, the frozen rule required alpha
0.125 next. Every alpha 0.125 run also failed, so no 0.50/0.75/1.00 run or
bisection was permitted.

| Path | alpha | Ideal duration | Observed duration | Result / termination | Physical force RMS / P95 / peak | Command force RMS / P95 / peak | Tracking RMSE | Acceleration / jerk RMS |
|---|---:|---:|---:|---|---|---|---:|---|
| 90/120 | 0.25 | 92.000 s | 29.766 s | FAIL, physical force gate | 100.073 / 117.386 / 200.352 N | 101.119 / 118.933 / 200.000 N | 0.509 deg | 108.886 deg/s2 / 4242.616 deg/s3 |
| 90/120 | 0.125 | 184.000 s | 184.000 s | FAIL, permanent BRAKE at endpoint | 97.327 / 109.787 / 172.622 N | 97.513 / 110.185 / 200.000 N | 31.611 deg | 43.924 deg/s2 / 1734.120 deg/s3 |
| 100/60 | 0.25 | 92.000 s | 92.000 s | FAIL, permanent BRAKE at endpoint | 94.375 / 107.524 / 167.221 N | 94.772 / 108.828 / 200.000 N | 24.763 deg | 98.937 deg/s2 / 3677.345 deg/s3 |
| 100/60 | 0.125 | 184.000 s | 184.000 s | FAIL, permanent BRAKE at endpoint | 95.161 / 105.742 / 180.230 N | 95.425 / 106.211 / 199.299 N | 25.076 deg | 85.224 deg/s2 / 3177.165 deg/s3 |
| 120/120 | 0.25 | 92.000 s | 92.000 s | FAIL, permanent BRAKE at endpoint | 94.157 / 109.392 / 167.573 N | 94.466 / 110.196 / 193.294 N | 38.100 deg | 62.762 deg/s2 / 2420.232 deg/s3 |
| 120/120 | 0.125 | 184.000 s | 52.725 s | FAIL, BRAKE_INFEASIBLE | 97.236 / 110.535 / 171.947 N | 97.694 / 111.594 / 197.987 N | 0.068 deg | 66.417 deg/s2 / 2732.912 deg/s3 |

The 120/120 alpha-0.125 tracking metric is censored at reference phase 6.591 s
by the early `BRAKE_INFEASIBLE` termination. Its small RMSE is not evidence of
full-path tracking.

## Per-path decisions

| Path | Low-speed PASS exists | Maximum safe alpha | Minimum safe completion time | PASS/FAIL monotone | Classification |
|---|---|---|---|---|---|
| 90/120 | no at 0.125 | undefined | undefined | yes, both tested speeds fail | C: NOT SPEED-RESOLVABLE |
| 100/60 | no at 0.125 | undefined | undefined | yes, both tested speeds fail | C: NOT SPEED-RESOLVABLE |
| 120/120 | no at 0.125 | undefined | undefined | yes, both tested speeds fail | C: NOT SPEED-RESOLVABLE |

Binary PASS/FAIL is monotone only in the trivial sense that every registered
speed failed. Interaction metrics are not monotone with speed. For 100/60,
slowing from 0.25 to 0.125 increased physical-force peak from 167.221 N to
180.230 N. The double-120 slower run also had a higher force peak and terminated
earlier in path phase.

## Safety Filter, BRAKE, and failure boundaries

- 90/120 alpha 0.25: three filtered cycles, peak absolute lambda 40.289, then
  the physical gate crossed for 1 ms. At alpha 0.125, one filtered cycle and
  one infeasible cycle started a BRAKE lasting 126.190 s through endpoint.
- 100/60 alpha 0.25: one filtered and one infeasible cycle, peak absolute
  lambda 20.034, BRAKE 63.570 s. At alpha 0.125 the first filter decision was
  infeasible with lambda zero, and BRAKE persisted 127.905 s.
- 120/120 alpha 0.25: the first infeasible filter transition produced a BRAKE
  lasting 65.095 s through endpoint. At alpha 0.125, BRAKE became terminal
  infeasible after 0.015 s.

For each alpha-0.125 classification boundary, exact `mjSTATE_INTEGRATION`
snapshots were retained at the last safe state and the first
`FILTER_INFEASIBLE` state that began the permanent BRAKE. Deterministic prefix
replays matched the original compact traces exactly at 52.715 s (120/120),
56.095 s (100/60), and 57.810 s (90/120). The registered run metrics hashes
were unchanged by snapshot recapture.

## Trend and engineering implication

Slowing reduced acceleration and jerk for 90/120 and 100/60, but did not
restore task completion. For 90/120 it converted a physical gate crossing into
a long permanent BRAKE. For 100/60 the force peak increased at the slower
speed. For 120/120 the slower run reached a terminal BRAKE failure before one
third of the reference phase.

Therefore none of the three paths has demonstrated a sufficiently slow,
nonzero constant time scale that lets the current controller complete safely.
The tested limitation persists at alpha 0.125 and is not resolvable as a simple
dynamic speed boundary. The evidence points to the existing Safety
Filter/BRAKE/allocator feasibility and switching behavior as an architectural
limit of constant time scaling. It does not authorize a controller patch.

In particular, double-120 is **not genuinely speed-feasible** under the current
controller based on this scan.

No measured-force controller, task relaxation, BRAKE recovery, new margin,
Reference Manager modification, impedance/admittance change, allocator change,
MPC cost, Adaptive MPC, trajectory-specific tuning, or additional seed was
implemented or tested.
