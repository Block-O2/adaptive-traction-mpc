# Minimal implementation map — no production edits in this audit

Paths below are under stages/stage5_personalized_motion_learning unless stated otherwise.

| Existing file | Proposed bounded change | Reason |
|---|---|---|
| src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py | Replace legacy DEV-A/DEV-D timing-replay entry guards with explicit mode contract checks; extract request/receipt/activation and step/terminal orchestration; mode factory; remove scientific dependence on future readiness and perf_counter replay; freeze fit and low-level compute | Largest integration surface; preserve planner inputs and mathematical branches |
| same directory / online_planning.py | Add versioned envelopes and injected executor/validity; separate profiling from expiry; staged result vs applied command | Reuse worker serialization; no live runtime exposure |
| same directory / wall_physics.py | Only adapter/interface wiring needed for unchanged realtime executor; preferably leave internals intact | Keep old-control catch-up, captures, receipts, watchdog and metrics |
| same directory / activation_validation.py | Extract age-policy inputs and terminal-age decision; retain mechanics/geometry/C2/task-clock mathematics | Avoid faking host_ns in scientific path |
| same directory / safe_fallback.py | Inject typed admission validity into latch choose/resume; keep prepare_decision and certified stop math | Separate host latency from algorithm failure |
| same directory / terminal_commit.py | Policy-specific transaction orchestration, preserve realtime implementation | Scientific exact-node atomic commit without wall tail |
| scripts/high_rom_v1/run_dev_case.py | Explicit execution_mode, metadata/host interruption, composition | Default remains realtime; no legacy boolean shortcut |

New modules in full3d_adaptive_integration_v1: execution_policy.py (ClockProvider + policies), simulation_snapshot.py (version envelopes and immutable boundary), scientific_scheduler.py (frozen barrier, fixed-step owner, receipts and terminal commit). Shared event extraction may be a fourth small module only if it reduces duplicate orchestration.

Expected scope: about 6–7 existing production files plus 3–4 new modules, roughly 700–1400 added/changed production lines, 400–800 focused test lines. These are planning estimates, not measured patch size or a delivery guarantee. Moderate migration risk, concentrated in RSS staged activation and COMPLETE transactions. No new scientific configuration values; execution mode belongs to harness metadata, not physics tuning.

Must remain mathematically and preferably byte-for-byte unchanged: human_waypoint_feedback_mpc.py; human_waypoint_scheduler.py; architecture_recovery_v2/{phase3_human_waypoint.py,functional_benchmark.py,effective_model.py}; controller_interface.py; loaded_execution.py; loaded_supervisor.py; human.py; cr12_plant.py; fast_plant.py; task.py; rigid_table_reference.py; terminal_reference.py; rolling_suffix_splice.py; receipt_reference_governor.py; applied_reference_history.py; measurement/observer/filter math, MuJoCo XML, existing configs and scorer-v1/v2. Runtime inline controller mathematics and safe_fallback.prepare_decision are protected blocks even if their files are touched.

Migration order: freeze baseline hashes + fake-clock realtime golden traces -> add policies/snapshots -> scientific exact-step session and commissioning -> same worker path + deterministic RSS staging -> terminal/scorer metadata -> bounded acceptance tests. No 30-repeat or value learning before all gates pass. If integration requires changing controller equations, safety thresholds, bridge geometry or task success definitions, stop and revise design rather than expanding this implementation silently.

Realtime command exact-100-ms discrepancy: first characterize current behavior. A deliberate > to >= bug fix is separate, explicit and tested; never bundle it as an unnoticed execution-mode change or claim the current code already meets that boundary. Preserve historical FAIL either way.
