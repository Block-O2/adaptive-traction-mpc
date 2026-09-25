# Current baseline and audited physical boundary

```mermaid
flowchart TD
    S[Deployable sensor boundary: robot q/dq, cuff pose/twist/wrench, time] --> O[Effective geometry / Human state reconstruction]
    O --> E[Commissioning batch fit; task beta + residual updates]
    E --> M[Accepted model: current baseline applies directly; DEV-C OFF]
    O --> L[Startup / commissioning / ACTIVE_RECOVERY / task state machine]
    M --> P[Fresh-state HWMPC and mechanics screen]
    L --> P
    P --> R[Quintic q/dq reference and cuff mapping]
    M --> U[Human inverse dynamics]
    R --> U
    U --> W[Cuff allocation + executable filter + supervisor]
    W --> T[CR12 torque command]
    T --> PH[MuJoCo CR12 + compliant cuff + Human V2]
    PH --> S
    BED[Fixed hip + proximal capsule + bed contact] --> PH
    PH -. evaluation only .-> D[Per-contact force / gap / impulse / true q]
    BED -. unresolved fixed overlap .-> B[Physical-domain credibility blocker]
```

The diagram describes the explicitly selected local DEV-A baseline, not a new
validated controller. No Human truth, contact force or geometry diagnostic
flows back into O/E/P/U. The fixed hip is attached to world; the bed is an
unchanged infinite plane; the proximal thigh capsule sphere center remains at
the fixed hip under all Human q. Changing hip placement relative to that plane
can therefore change unavoidable overlap before any command is executed.

The timing-aware runner measures planner latency and replays physical wait
intervals under the previous reference. This is controlled synchronous delay
replay, not asynchronous hardware real time. This diagnostic campaign uses
saved wait durations for repeatability and does not requalify runtime.
