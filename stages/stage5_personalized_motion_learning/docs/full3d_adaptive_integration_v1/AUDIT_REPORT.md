# Independent Audit Report: FULL-3D Adaptive Integration V1

Date: 2026-09-23  
Auditor role: independent source/artifact review, separate from Builder  
Audited status proposal: `FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`

## Scope

The Auditor checked the claimed physical chain, simulation-truth boundary,
timing contract, transition records, constraint descriptions, collision masks,
dependency provenance, nominal trace, no-actuation trace, and corrected-time
Phase-2 evaluator against source and saved artifacts. The audit did not treat
completion, a solver return, or a rendered video as sufficient evidence.

## Findings and Builder dispositions

| Severity | Finding | Disposition |
|---|---|---|
| P1 reporting | The draft claimed the Human-waypoint planner screened future CR12 reach. Source screens Human ROM/motion/clearance and inverse-dynamics wrench only; CR12 feasibility is checked at the current state during low-level execution. | Corrected the report and diagram. The separate large-ROM study may use CR12 IK, but this is not part of deployed candidate screening. |
| P2 provenance | Terminal learning rows lacked `next_adaptive_state`. | Repaired logging only; no control law or parameter changed. The final nominal and no-actuation artifacts are rerun after this repair. |
| P2 semantics | Transition `observation` and `adaptive_state` are planner-request-time values, while `start_time_s` is activation time. | Documented explicitly. No activation-time state is invented; execution beliefs, cost window, next state, and completion remain separately recorded. |
| P2 timing | The global-timeout path could take an extra 5 ms interval and could omit final pending-transition flush. | Repaired exact timeout-boundary termination and terminal flush; task timeout must be a positive integer multiple of 5 ms. |
| P2 trace integrity | A low-level exception could leave a proposed, unexecuted interval and force cost in the trace. | Repaired by removing the proposed row before recording the terminal boundary. |
| P2 provenance | Dependency hashes were stale after repairs, mesh paths omitted `vendor/`, and the corrected evaluator manifest omitted its imported timing helper. | Regenerated after the final source/artifact freeze; all 42 declared paths resolve and match SHA-256. The V1.2 evaluator manifest includes the timing helper. |
| P2 reporting | The draft called world axes/origin fitted. | Corrected: WORLD X/Z and zero origin are structural conventions; fitted geometry is hip x/z, thigh length, and knee-to-cuff distance. |
| P3 terminology | The large-ROM report called nominal-geometry clearance conservative. | Corrected to nominal-geometry clearance. The runtime uses a different conservative upper-bound shank set. |
| P1 constraint | Task-complete `attempt_11` crossed the deployable conservative session-clearance set for 61 samples, minimum `-3.303649 mm`, although hidden true contact stayed zero. | Preserved as failed acceptance evidence. The versioned repair adds a task-endpoint reference floor and a sampled fail-closed realized monitor. `attempt_14` remained positive, minimum `+0.278774 mm`. |
| P1 timing | Clearance-repaired attempts 12/13 aborted on the unchanged 100 ms stale-plan cap; attempt 13's rejected solve took `2093.990 ms`. | Preserved prominently. No deadline relaxation or search heuristic was added. Attempt 14 completed with 43.023/67.042/67.614 ms mean/p95/max, but this is conditional nominal evidence, not repeatable timing qualification. |
| P2 transition integrity | A stale-plan abort duplicated the last pending transition, and interval count was inferred from row count. | Pending state is cleared immediately after flush; final attempt has 13 unique windows. A separate executed-interval counter verifies 981 boundaries for 980 integrations. |

## Independently verified claims

- The task path is physically connected: six CR12 actuator torques are applied
  to MuJoCo, the robot moves the cuff, and an explicit compliant site
  interface loads Human V2. There is no task-time Human state assignment or
  direct Human actuation.
- Deployable-path estimation consumes robot/tool measurements and reconstructed
  interface wrench, not hidden Human q/dq or hidden Human geometry/dynamics.
  True Human state and contacts are written only to evaluation channels.
- Collision masks are: robot/adapter `1/1`, Human `2/4`, bed `4/2`, visual cuff
  bar `0/0`. Human-bed and permitted CR12 self-contact are active; direct
  robot-Human and robot-bed geom contact are filtered.
- High-level planning is event-driven. Fifty hertz is the continual adaptation
  cadence, not the waypoint-planning cadence.
- Planning-delay handling is controlled synchronous replay: the physics plant
  is advanced under the prior reference for an upward-quantized measured delay.
  This is not an asynchronous or hard-real-time claim.
- The historical Phase-2 evaluator paired a post-step true state with a
  pre-step estimate/reference and integrated an extra endpoint interval. The
  opt-in aligned evaluator corrects both without changing the historical
  default or rewriting old results.
- The value hook is exactly zero. No RL/value/imitation training was performed,
  and learning cannot bypass deterministic feasibility or execution guards.
- Final `attempt_14` is `COMPLETE` with 981 task boundaries, 980 independently
  counted integrations, exact 5 ms/20-physics-step progression, zero sampled
  acceleration or clearance violations, and `+0.278774 mm` minimum deployable
  session clearance.
- Its independently recomputed force exposure is `463.612746 N s`; the 13
  unique learning records partition this into `407.200587 N s` after activation
  and `56.412158 N s` of planning-wait exposure, with terminal next-belief
  fields present.
- `no_task_actuation_diagnostic_06` has zero task torque and aborts after 20 ms
  on actual-motion acceleration. The corrected Phase-2 V1.2 replication has
  168 aligned rows and all 46 frozen checks true, with unchanged manifests.

## Scope limits retained after audit

The evidence supports only a nominal low/moderate-ROM development
qualification. It does not support varied-session target-domain validation,
120--130 degree dynamic validation, real HEX sensing, hardware timing,
collision protection for filtered pairs, or clean-clone reproducibility while
the required implementation/assets remain uncommitted.

The appropriate terminal status is therefore
**`FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`** as a successful audited
nominal-development execution. Attempts 11--13 remain mandatory negative
evidence: the status does not mean repeatable timing qualification, robust
clearance invariance, or varied-domain validation. A broader status would
exceed the evidence.
