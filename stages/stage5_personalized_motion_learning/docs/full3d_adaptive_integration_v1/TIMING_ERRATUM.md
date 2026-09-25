# Timing Erratum: Architecture-Recovery V2 Evaluator

Date: 2026-09-23

## Scope and preservation rule

This erratum does not alter or relabel the historical V2/V2.1/V2.2 artifacts.
Those results remain the output of their snapshotted evaluator. It documents a
source-level defect, introduces an opt-in corrected contract, and classifies
the reused-seed V2.2 run as a corrected replication rather than fresh held-out
evidence.

## Confirmed historical defect

The historical default in
`architecture_recovery_v2.functional_benchmark.run_closed_loop_case` uses

```text
task_steps = round(T / dt) + 1
for k in range(task_steps):
    t = k dt
    reference = r(t)
    estimate = x_hat(t)
    x_true = integrate(x_true, u, dt)
    append(x_true, estimate, reference)
```

Thus a stored row pairs `x_true(t+dt)` with `x_hat(t)` and `r(t)`. It also
executes `round(T/dt)+1` intervals, so its plant may advance beyond `T` by
10--30 ms for the frozen random V2.2 task durations. A constant-speed
diagnostic at `0.5 rad/s`, `dt=0.02 s` produces a false `0.01 rad` RMSE under
the historical pairing and exactly zero under aligned pairing.

The defect affects tracking, state-estimation, terminal, and force-exposure
interpretation. It does not show that the adaptive architecture is invalid;
it shows that the published numeric comparison must be read under the old
indexing convention until corrected replication is inspected.

## Corrected opt-in contract

The default remains `historical_post_state_pre_reference_v1` so old behavior
cannot change silently. The opt-in `boundary_aligned_v2` path uses:

- `N = ceil(T/dt)` half-open integration intervals;
- `N+1` state/reference boundary samples at equal timestamps;
- a final interval of `T-(N-1)dt` when `T/dt` is non-integer;
- no endpoint-only extra integration step;
- inverse-dynamics acceleration divided by the actual preceding sample time;
- force and moment exposure `sum(value_k * actual_dt_k)`;
- final completion tests at the exact `T` boundary.

The reusable implementation is
`full3d_adaptive_integration_v1.time_contract`; the V2 evaluator exposes the
opt-in argument without changing its historical default. Six focused tests
cover the known-motion offset, non-integer duration, interval cost, historical
default, aligned branch, and session-clearance contract.

## Corrected V2.2 replication classification

Configuration:
`configs/full3d_adaptive_integration_v1/phase2_v22_corrected_time_replication_v1_2.json`.
It inherits the same 24 cases, seven arms, controller settings, and frozen
thresholds. It changes only the time contract. Because those seeds and their
outcomes were already viewed, the result is explicitly
`corrected_replication_of_previously_viewed_held_out_cases_not_fresh_generalization`.

The original `21.3701%` comparison and preregistered `20%` gate are not assumed
to survive correction and were not used as tuning targets. Corrected metrics
are reported in `ACCEPTANCE_REPORT.md` and the replication result artifact.

## Observed corrected replication

All 168 rows (24 cases x seven arms) executed with unchanged seeds,
controller settings, and gates. Every corrected row that reached the horizon
records exactly `N+1` boundary samples, `N` intervals, and the requested task
duration. The candidate `adaptive_state_residual` arm completed 24/24 cases;
median/p95 tracking RMSE changed from historical `0.477010/0.701653 deg` to
aligned `0.253711/0.396179 deg`. Commissioning-only remained 23/24 complete
and its median changed from `0.606653 deg` to `0.464897 deg`.

Therefore the same formula,

```text
(commissioning_only_median - continual_candidate_median)
/ commissioning_only_median
```

changes from `21.3700986%` to `45.4263835%`. The frozen 20% check still passes,
as do all 46 recorded gate checks, but the new percentage is a corrected
same-seed replication result, **not** a new preregistered generalization claim.
The candidate's corrected full-episode peak wrench is `172.947717 N` and
`29.954792 Nm`; mean force exposure is `1744.447128 N s`. No source/config
changed during the run according to its source manifest.
The final V1.2 manifest explicitly includes the imported
`full3d_adaptive_integration_v1/time_contract.py` helper. Earlier V1 and V1.1
replications are preserved: V1 omitted final boundaries for some aborted
comparator rows, while V1.1 corrected those rows but did not enumerate the
imported helper in its source manifest.
