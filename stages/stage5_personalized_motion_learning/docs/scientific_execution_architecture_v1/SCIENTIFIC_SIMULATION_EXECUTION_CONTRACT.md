# Scientific simulation execution contract v1 — proposed, unimplemented

Mode is immutable per episode: REALTIME_CHARACTERIZATION or SCIENTIFIC_SIMULATION. Output mode is mandatory. No historical result changes classification. The plant, task/safety limits, model/estimator equations, candidate enumeration/ranking, solver settings and reference polynomial mathematics remain fixed.

ClockProvider exposes distinct sim_time/physics_step and wall_monotonic_ns. Simulation time is origin + integer native step × 0.00025 s, checked against data.time with a roundoff-only assertion. A control interval is exactly 20 native steps (0.005 s). Wall time is profiling only for scientific decisions; resource termination may interrupt a run but marks it INCOMPLETE with retained evidence, never changes a scientific action or credits completion.

Version schema:

| Field | Responsibility |
|---|---|
| episode_epoch | Unique reset/repetition identity; old workers cannot cross resets |
| state_version | Monotone token for each committed control-relevant state mutation, including native step or estimator/measurement update; physics_step is separate |
| phase_version | Increment on task phase transitions, including abort/complete; phase name alone is insufficient |
| human_model_version | Immutable content identity plus existing belief sequence; increment on committed adaptation |
| reference_version | Active schedule/composite and applied progress/receipt identity |
| request_version | Monotone unique request identity within epoch; never reused |
| value_model_version | Separate immutable ranking-model identity, fixed within a repetition |

SimulationSnapshot contains sim_time, physics_step, all versions, permitted Human q/dq ESTIMATES, measured robot/interface state, immutable estimator/filter/monitor state and held-sample identities, belief/model, reference q/dq/ddq and progress, task clocks and command receipt history needed by consumers. It contains no evaluation truth, hidden geometry or live plant pointer. Controller-side physics version is not permission to expose plant qpos/qvel. Evaluation state is stored separately.

PlanningRequest contains original snapshot/version vector, source sim/sample times, target reference boundary, candidate/model identities and host enqueue time (profiling). PlanningResult contains the unchanged source identity, request/result identity, candidate/reference and certificates, status, and real host start/finish/duration. Copy arrays/serialize by value; callbacks may record host events only.

Scientific receipt requires current epoch/state/phase/model/reference tokens equal the source tokens; result not cancelled or previously consumed. No physical, estimator, task, reference, adaptation or learner mutation occurs during critical computation. Snapshot is taken after deterministic acquisition/estimation/adaptation bookkeeping for that boundary. Administrative request records do not mutate scientific state_version. Validation and command construction are also frozen transactions. A successful write/receipt commit is atomic; no physics on failure.

RSS requires two distinct transactions. A planner may compute a suffix from S_k and a known future reference endpoint; receive/stage it while S_k is frozen. The future endpoint is a polynomial prediction, never a future observation. A staged plan is NOT an executable command. At the deterministic splice boundary S_j, build a NEW activation-validation request from S_j; retain the original S_k identity and age. Validate current model, phase, reference C2, geometry and original physical horizon, then issue a certificate bound to S_j. Before write, require that activation certificate's entire version vector still matches. Never relabel old planner source as S_j or apply a result merely because it once passed receipt validation.

Freshness policy returns typed validity with mode and reasons, not fake timestamps. REALTIME preserves host >=100 ms plan protection and every existing check; the known command > boundary requires a separate explicit defect decision. SCIENTIFIC uses version identity for receipt/write, source simulated age and unchanged physical horizons for staged-plan activation. Retain <100 ms simulated source horizon for original/fresh staged sources in v1; no infinite-age permission. Report wall age honestly, even if seconds, as profiling with realtime qualification NOT_APPLICABLE. Keep terminal physical projection horizon and phase/global deadlines. Do not pass sim time in a field named host_ns.

Fault taxonomy: HOST_LATENCY only prolongs frozen wall duration; ALGORITHMIC_FAILURE means infeasible plan, failed validation, deterministic iteration-budget exhaustion, or explicitly preregistered fault at a request/step. Resource watchdog/cancel is INTERRUPTED_HOST_RESOURCE, not algorithmic timeout. No measured host-duration deadline may change scientific candidate selection or fallback decisions.

Commit order: acquire at fixed sensor node -> update observer/monitor -> task transition and due adaptation once in a documented fixed order -> freeze snapshot -> request/receive -> validate -> compute supervised command -> validate token/write/receipt -> advance 20 native steps with unchanged native monitoring -> next sensor boundary. Initialization, commissioning fit/replay, handoff, recovery, TASK and terminal/finalization all obey the freeze. COMPLETE commits at an exact native state and disables further stepping before logging/worker cleanup.

Same seed/initial state/config plus fixed numerical environment must yield identical decisions and native trajectories regardless of host delays. This is a required acceptance property, not an outcome established by this static audit. Cross-host bitwise identity is not assumed.
