# Implementation timebase and ownership map

| Boundary | Realtime characterization | Attempted scientific simulation |
| --- | --- | --- |
| Physical clock | `WallPhysicsSession` maps monotonic host time to catch-up native steps | `ScientificPhysicsSession` advances only when `next_control_tick` explicitly performs 20 native steps |
| Planner worker | `PlanLifecycle.submit` returns a future; physics may advance while pending | `ScientificPlanLifecycle.submit` waits for the same worker future at the source epoch; host-only delay is injected after worker completion |
| Snapshot | `snapshot_task_call` serializes planner and inputs by value | Same serialized boundary; no plant/runtime pointer in payload |
| Result validity | Host capture age and existing wall guards | Source/receipt simulation version equality at frozen worker receipt; physical source age at activation; separate host profiles |
| RSS | Original C2/geometric bridge, activation validation and fallback | Same bridge and geometric screens; staged activation age uses physical source/revalidation times |
| Command | Wall prepare/apply may integrate prior torque to host readiness and checks wall age | Command construction/write at a fixed native state, then exactly 20 native steps |
| Terminal | Wall-causal return commit and host tail | Physical-age exact-node commit, with host duration logged separately |
| Scorer | Unchanged scorer-v2 tests host `activation_age_ms` | Unchanged scorer-v2 still tests host `activation_age_ms`; this prevents delay-gate PASS |

`SimulationVersion` currently records episode path, native/sample count, physical step/time, phase count, Human-model sequence and applied receipt count. It is a first implementation of the contract, not a complete proof that every staged reference or control-relevant in-boundary mutation increments a token. The 100 ms realtime plan guard remains in `PlanLifecycle`; the exact-100-ms command-write `>` defect was not changed.
