# Current realtime causality

Code evidence: TIMEBASE_AUDIT.md. “Realtime” here describes the current host-causal harness, not hardware realtime assurance.

```mermaid
sequenceDiagram
 participant M as Main/runtime
 participant P as WallPhysicsSession/MuJoCo
 participant W as Isolated planner worker
 participant L as Lifecycle/validity
 M->>P: boundary / catch_up under last applied torque
 P-->>M: grid measurement and causal estimator state
 M->>L: capture + request(source sample, capture ns)
 M->>W: serialized snapshot
 loop While result pending
 M->>M: existing reference / RSS bridge / safety supervisor
 M->>P: prepare/apply receipt, next_control_tick
 P->>P: native steps under receipt-owned torque, sensor captures
 M->>M: sensor-supported task clock, adaptation, limits
 end
 W-->>L: worker finish timestamp
 M->>L: collect, expiry check, validation start
 M->>M: current model / phase / C2 / geometry validation
 M->>P: prepare_apply integrates old torque to ready grid
 M->>L: actual activation freshness
 M->>P: write torque and commit receipt/reference
 P->>P: next native interval; repeated acquisition
 M->>M: RETURN terminal transaction with catch-up and tail checks
 M->>M: persist exact COMPLETE native node; post-run scorer-v2
```

Physics advances during TASK worker computation through main-thread stepping/catch-up. There is no separate MuJoCo physics thread: synchronous command construction temporarily stops actual integration, then catch-up integrates elapsed wall intervals under OLD torque. This is still a wall-causal physical result.

Reference desired phase advances with data.time; emitted progress is capped by receipt governor and fallback fork, so it is not simply equal to wall time. The applied torque remains active until a successful write. Command/source age uses monotonic host capture mapped from the original physical sensor grid; worker completion cannot refresh it.

Stale checks occur in PlanLifecycle.expired/activate (>=100 ms), future handoff and RSS splice original/fresh ages (<100 ms), FallbackLatch choose/resume (<100 ms), and WallPhysicsSession.apply (>100 ms before and after write). This last exact-boundary discrepancy remains unresolved; the historical intended >= rule and actual implementation must not be conflated.

Safe Fallback commits at a capped physical reference fork, without computing a new stop then. Host readiness/expiration determines whether a valid primary can supersede that path. Certified braking is nonpreemptible; fallback HOLD is distinct from task dwell. Coverage is High-ROM TASK pass-through, not arbitrary commissioning movement.

Task phase/dwell primarily use physical and sensor time. RETURN additionally uses host-age projection/finalization checks, so a physical scorer can still receive host-dependent trajectories/endpoints. Scorer-v2 is a post-run evaluator with separately confirmed offline agreement, not the task-state update loop.

Moving COMMISSIONING computes TRACK torque every nominal 5 ms using an observation and quintic reference. Slow compute delays command write while old torque is integrated; the command can expire even with no planner future. The retained failed sample 4.095 s was command-ready at 41.125 ms but rejected later than 100 ms. Do not infer an exact OS cause from that trace.

Simple pause is insufficient: lifecycle expiry, command write age, splice age, fallback admission, terminal 10 ms horizon, legacy measured-latency replay, and cleanup catch-up survive a pause. Turning off online_timing also disables safe_fallback_enabled and selects different planning behavior.
