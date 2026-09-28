# Scientific simulation mode feasibility gate

Decision: `SCIENTIFIC_SIMULATION_MODE_NOT_JUSTIFIED` under this task's implementation scope. This is an architecture/scope decision from source inspection, not a claim that offline deterministic execution is impossible. No scientific-simulation mode was implemented or validated; no representative or continuous-session experiment was run.

## Required mode boundary

`REALTIME_CHARACTERIZATION` retains the existing host-wall-clock execution semantics: native physics catches up under the last applied command, the 55 ms historical activation target is reported, >=100 ms source age is rejected, and Safe Fallback remains available. The commissioning moving-torque tail and `RSS_RUNTIME_QUALIFICATION_NOT_MET` remain unresolved.

A valid `SCIENTIFIC_SIMULATION` mode would hold the exact current MuJoCo state fixed while planner/command work completes, validate the result against that same state, then advance the next physical interval. It would preserve the same controller, estimator, planner, safety screens, reference mathematics, plant, task and thresholds. Host compute time and physics pause duration would remain separate `HOST_RUNTIME_CHARACTERIZATION` provenance. Each result would explicitly carry `execution_mode`. Passing offline results would not establish hardware timing capability.

## Source findings

| Path | Coupling that prevents a runner-only switch |
|---|---|
| `full3d_adaptive_integration_v1/wall_physics.py` | `catch_up`, `prepare_apply`, and `next_control_tick` advance native physics according to host monotonic time, including while a planner works. `apply` checks 100 ms against wall-clock source capture. |
| `full3d_adaptive_integration_v1/online_planning.py` | `PlanLifecycle.expired` and `activate` use the same host-clock 100 ms rule; worker completion timestamps also use host time. Merely pausing MuJoCo would still expire plans after a 100/200 ms injected delay. |
| `full3d_adaptive_integration_v1/runtime.py` | The online path submits an async plan, then executes existing reference or an RSS bridge while the future is pending. Plan collection, pass-through prefetch, Safe Fallback, phase transitions, actual activation revalidation and command receipts are intertwined with that progression. Several direct `monotonic_ns()` calls participate in guards and provenance. |
| `scripts/high_rom_v1/run_dev_case.py` | The runner supplies the frozen options and calls `run_executed_case`; it has no execution-clock or planner-ready/physics-pause boundary. Turning off `monotonic_async_planning` selects a different synchronous planning path and disables the same Safe Fallback behavior. |

A harness-only stale bypass would allow an old plan to execute after the simulation state changed, violating the user's explicit safety condition. Pausing physics alone leaves wall-clock expiry and command-write checks active. Disabling the async path changes reference/fallback behavior. A correct design therefore needs coordinated production execution, lifecycle, scheduling, receipt and provenance changes, plus equivalence tests. That exceeds the authorized one main harness implementation plus at most one local harness repair; it cannot be asserted equivalent from source inspection alone.

The required seven equivalence gates, representative 4–8 runs, 0/100/200 ms delay invariance, three-repeat smoke, 3 × 30 continuous zero-value sessions and value dataset are all **NOT RUN** because the mode gate failed. No value/RL training occurred. No historical runtime FAIL was promoted to PASS.

## Hardware boundary

Runtime assurance is `REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`. Before CR12 actuation, the project still needs a phase-independent native executor, watchdog/heartbeat, trajectory buffering, bounded stale-command behavior, controlled stop/hold, independent force/velocity/joint protection, high-level failure fallback, timing fault injection, latency/WCET characterization, and E-stop integration. The present offline feasibility assessment does not satisfy those requirements.
