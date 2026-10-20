# Native-Scheduler Coordination Residual Realization v2

Terminal status: **READY_NATIVE_COORDINATION_INTERFACE_V2**. E **READY**, V **READY**.

This is interface development and physical evaluation on the previously exposed nominal Human. It proves no held-out generalization, real-time host deadline qualification, hardware readiness or optimal value function. No training or large value dataset was started.

## Root fix and exact source chain

v1 failed because ten recorded native intervals in each phase held q while retaining nonzero dq intent, reflecting wait/ownership semantics. Treating those tuples as physical phase-clock Hermite derivatives created huge accelerations and jerk. The original B was not thereby shown physically unsafe. v2 never uses a logged B tape to execute a trajectory.

Repository root: `/home/hank/coding/adaptive-traction-mpc-learning`; stage: `stages/stage5_personalized_motion_learning`.

1. `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py:3194` requests the native task waypoint; `:3252` serializes only the causal planner/request graph with `online_planning.snapshot_task_call`. The additive v2 runtime selects the research subclass and keeps the original request path.

2. `terminal_reference.py:368` selects the original terminal reference and calls the original `HumanWaypointFeedbackMPCV1.decide`. `coordination_residual_v2.py:8` first obtains that complete original nominal decision. Zero/HOLD returns it directly.

3. At the original selected target, normalize by the registered start/goal task spans. Apply `p_h=p_h_B+delta`, `p_k=p_k_B-delta`. Both target common progress and all original endpoint choices are preserved. The generic action is a PWL graph in native nominal progress, with zero endpoints and independent phase graphs. It is not a reference spline. Bounds violations explicitly reject and retain nominal B; every rejection is recorded.

4. The unchanged `human_waypoint_feedback_mpc.py:240` `_evaluate` calls `scheduler.plan_reference_contract` (`:286`; scheduler definition `human_waypoint_scheduler.py:441`). Original velocity/acceleration, duration-window, continuous geometric clearance, frozen Human mechanics and causal tracking-offset certificates all remain active. No threshold is weakened.

5. Original `online_planning.execute_task_snapshot` applies the unchanged safe-fallback preparation. Native runtime `:2979` selects the suffix, `:3005` checks q/dq/ddq boundary continuity, `:3045` commits planner memory, and `:3424` uses the native receipt governor (when enabled). `:3517` samples the native owned schedule. Original `_execute_interval`, CR12 mapping, safety, phase completion and R2 transition guard execute it. Planning waits retain their original q/dq/ddq ownership semantics.

The v2 runtime is a separate source file. Exact paths and verified final line numbers are in `EXACT_SOURCE_CHAIN.json`; final hashes and executed revisions are in `SOURCE_MANIFEST.json` and `source_history`. Native C2 means scheduler polynomial and activation-boundary continuity; no claim is made that wait-time dq intent is the derivative of a continuously interpolated q tape.

## Frozen contract and repairs

`CONTRACT.json` froze zero tolerance (arrays 1e-10, force integral 1e-6), unchanged native safety, R2 9/1/9 phase clocks and existing +20ms quantization allowance, five minimal patterns, amplitudes [0.01,0.005,0.0025,0.001], at most 20 minimal physical attempts, four structural repairs, 12 branch continuations and one advancing physics owner. All candidates use native nominal target, causal state/reference/belief and registered task endpoints. Hidden state is forked only for restoration and evaluator use.

The model/plant/options and initializer are inherited verbatim from B; no new stochastic setup is introduced. Repeated zero runs are deterministic. CPython and NumPy RNG states are explicitly restored after fork; observer-local RNGs and all hidden model/native state are process-copied.

Repair 1 added selected residual metadata to the decision evaluations. The first hip result is retained and not relabeled as having a complete metadata audit. Zero logging regression and all five patterns followed.

Repair 2 corrected the historical mapping: a frozen B differential is not the current conditional native nominal differential. The failed initial fixed/CEM traces remain read-only. The corrected mapping computes `delta=d_hist(m)-d_B_nominal` at each native decision, then runs the same scheduler. The initial JSON loop ran CEM first; those two runs are development diagnostics. Repaired historical gates explicitly run fixed then CEM. Zero and all five minimal regressions preceded the repaired history gates.

## Zero residual hard gate

Final zero pass: True; reference maximum error 0.0; all trace maximum error 0.0; J_F difference 0.0. Ownership/wait and safety decisions exact: True. Three zero runs independently reproduced the same B. See `ZERO_OWNERSHIP_GATE.json` for the compared fields.

## Physical runs, including failures

| Run | Physical VALID/MATCHED | Activated nonzero | J_F N s | Force peak/mean/RMS N | Moment integral/peak | Clearance m | OUT/HOLD/RETURN s |
|---|---|---:|---:|---|---|---:|---|
| branch_parent_v2 | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| catchup_0.01_history | True/True | 6 | 1442.928763 | 114.346/75.825/77.823 | 99.383416/15.571 | 0.010050 | 9.005/1.020/9.005 |
| catchup_0.01_logged | True/True | 6 | 1442.928763 | 114.346/75.825/77.823 | 99.383416/15.571 | 0.010050 | 9.005/1.020/9.005 |
| early_OUTBOUND_baseline | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| early_OUTBOUND_hip | True/True | 1 | 1434.131179 | 114.836/75.363/77.390 | 101.885512/15.558 | 0.006455 | 9.005/1.020/9.005 |
| early_OUTBOUND_knee | True/True | 1 | 1443.413374 | 116.056/75.850/77.994 | 98.963609/15.884 | 0.006455 | 9.005/1.020/9.005 |
| hip_0.01 | True/True | — | 1442.009751 | 114.342/75.776/77.798 | 99.052681/15.558 | 0.008797 | 9.005/1.020/9.005 |
| hip_0.01_history | True/True | 9 | 1442.009751 | 114.342/75.776/77.798 | 99.052681/15.558 | 0.008797 | 9.005/1.020/9.005 |
| hip_0.01_logged | True/True | 9 | 1442.009751 | 114.342/75.776/77.798 | 99.052681/15.558 | 0.008797 | 9.005/1.020/9.005 |
| independent_0.01_history | True/True | 8 | 1412.840329 | 114.342/74.244/76.227 | 107.189199/15.558 | 0.006859 | 9.005/1.020/9.005 |
| independent_0.01_logged | True/True | 8 | 1412.840329 | 114.342/74.244/76.227 | 107.189199/15.558 | 0.006859 | 9.005/1.020/9.005 |
| knee_0.01_history | True/True | 8 | 1433.934649 | 116.599/75.352/77.546 | 101.958785/15.884 | 0.006859 | 9.005/1.020/9.005 |
| knee_0.01_logged | True/True | 8 | 1433.934649 | 116.599/75.352/77.546 | 101.958785/15.884 | 0.006859 | 9.005/1.020/9.005 |
| late_OUTBOUND_baseline | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| late_OUTBOUND_hip | True/True | 1 | 1436.978601 | 115.479/75.512/77.604 | 100.649465/15.711 | 0.006455 | 9.005/1.020/9.005 |
| late_OUTBOUND_knee | True/True | 1 | 1440.689042 | 115.479/75.707/77.787 | 100.180968/15.711 | 0.006455 | 9.005/1.020/9.005 |
| mid_OUTBOUND_baseline | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| mid_OUTBOUND_hip | True/True | 1 | 1436.272185 | 115.479/75.475/77.556 | 100.817719/15.711 | 0.006455 | 9.005/1.020/9.005 |
| mid_OUTBOUND_knee | True/True | 1 | 1441.403854 | 115.479/75.745/77.836 | 100.011804/15.711 | 0.006455 | 9.005/1.020/9.005 |
| mid_RETURN_baseline | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| mid_RETURN_hip | True/True | 1 | 1442.817834 | 115.479/75.819/77.920 | 99.272419/15.711 | 0.007978 | 9.005/1.020/9.005 |
| mid_RETURN_knee | True/True | 1 | 1439.638431 | 115.479/75.652/77.730 | 100.897642/15.711 | 0.012585 | 9.005/1.020/9.005 |
| native_CEM_segment_MATCHED | False/False | 8 | 1385.118767 | 109.960/72.237/74.059 | 116.873697/15.192 | 0.009911 | 9.150/1.020/9.005 |
| native_fixed_hip_segment_MATCHED | True/True | 9 | 1390.988960 | 110.880/73.058/74.939 | 112.626646/15.232 | 0.006308 | 9.015/1.020/9.005 |
| native_graph_CEM_segment_MATCHED | True/True | 10 | 1410.338051 | 110.648/74.113/75.811 | 109.736753/15.192 | 0.006357 | 9.005/1.020/9.005 |
| native_graph_fixed_hip_segment_MATCHED | True/True | 10 | 1419.327080 | 111.754/74.585/76.377 | 106.999706/15.232 | 0.006435 | 9.005/1.020/9.005 |
| reversal_0.01_history | True/True | 10 | 1438.444871 | 114.346/75.589/77.556 | 100.704119/15.571 | 0.006602 | 9.005/1.020/9.005 |
| reversal_0.01_logged | True/True | 10 | 1438.444871 | 114.346/75.589/77.556 | 100.704119/15.571 | 0.006602 | 9.005/1.020/9.005 |
| zero_history_v2 | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| zero_logging_v2 | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |
| zero_v2 | True/True | — | 1438.613498 | 115.479/75.598/77.685 | 100.417251/15.711 | 0.006455 | 9.005/1.020/9.005 |

## Minimal and historical expressivity

Five final minimal patterns passed: True. Accepted deltas, HOLD disablement and terminal zero are in `RESIDUAL_SEMANTICS_AUDIT.json`. Per-decision common target errors are recorded in all `*_AUDIT.json`. Every rejected proposal remains visible.

Historical q references are converted to spatial `d_hist(m)` graphs only. Duplicate progress selects the first recorded q; any progress backtracking and endpoint-zero projection are disclosed in `HISTORICAL_SPATIAL_GRAPH.json`. No historical timestamp, dq derivative or old 1.3x segment pacing enters execution. Force costs are compared descriptively within current R2, not claimed to reproduce historical 1.3x-segment costs.

- fixed_hip_segment_MATCHED: pass True; normalized spatial path errors `{"OUTBOUND": {"executed_backtrack": -0.0, "normalized_path_peak": 0.013148411472620261, "normalized_path_rms": 0.0037738279183838087}, "RETURN": {"executed_backtrack": -0.0, "normalized_path_peak": 0.004365841733221654, "normalized_path_rms": 0.0019407615098656831}}`.

- CEM_segment_MATCHED: pass True; normalized spatial path errors `{"OUTBOUND": {"executed_backtrack": -0.0, "normalized_path_peak": 0.008781091019595358, "normalized_path_rms": 0.0026834982529443264}, "RETURN": {"executed_backtrack": -0.0, "normalized_path_peak": 0.004343897826918665, "normalized_path_rms": 0.0019378741083294472}}`.


## Full-state same-state branching

The reused v1 API is a Linux process-scoped address-space fork, not a portable disk restart. Computational workers are quiesced without changing native pending ownership. Full MuJoCo integration state, mutable model, Python graph, scheduler/governor/task/planner/request/lifecycle, reference, observer/RNG, prefix trace/cost and caches are cloned. The verification manifest adds lifecycle, arguments and request to the v1 fields. Opaque native objects/locks remain fork-preserved and explicitly listed. Parent waits synchronously for each child; only one child advances physics. Start hashes are checked before candidate/output mutation; parent hashes are checked after every child.

Four points are frozen in `BRANCH_CONTRACT.json`. They are native opportunities: early OUT at native target m≈0.20, mid OUT≈0.59, late OUT≈0.79, mid RETURN≈0.59. Late is the last native target strictly interior for both lead signs (phase elapsed about 4.26s), not the settled 7.5s endpoint wait. This is a limitation of native decision availability, explicitly selected before the branch experiment.

Each candidate acts over one declared ±0.04 progress chunk at amplitude ±0.01, then zero residual under B. Labels contain full Human geometry/dynamics/residual model hash, snapshot hash, action, continuation policy, complete task validity, remaining J_F and moment integral, force/moment metrics, timing and execution audit. Costs are realized continuation costs under the declared B policy, not V*/Q*.

Branch gate: `{"complete_valid": true, "cost_differences": true, "distinct_execution": true, "pass_": true}`.

| Snapshot | Candidate | Accepted/activated | Different ref | Δ remaining J_F | Δ remaining M | VALID/MATCHED |
|---|---|---:|---|---:|---:|---|
| early_OUTBOUND | hip | 1 | True | -4.482319315 | 1.468261088 | True/True |
| early_OUTBOUND | knee | 1 | True | 4.799875179 | -1.453641769 | True/True |
| mid_OUTBOUND | hip | 1 | True | -2.341312968 | 0.400468037 | True/True |
| mid_OUTBOUND | knee | 1 | True | 2.790355456 | -0.405446840 | True/True |
| late_OUTBOUND | hip | 1 | True | -1.634896975 | 0.232214315 | True/True |
| late_OUTBOUND | knee | 1 | True | 2.075543672 | -0.236283312 | True/True |
| mid_RETURN | hip | 1 | True | 4.204335940 | -1.144832247 | True/True |
| mid_RETURN | knee | 1 | True | 1.024932450 | 0.480390869 | True/True |

## Integrity, provenance and readiness

Starting branch `codex/coordination-research-interface-v1`, HEAD `41cdddef117caa4b191a52129c4ff83e481fd5a8`; final branch `codex/coordination-residual-realization-v2`. Protected files 676, changed count 0, HEAD unchanged True, staged diff unchanged True. Pre-existing dirty/untracked state was preserved. No staging, committing, pushing, merging, reset, training, hardware or multi-Human work occurred.

Executed command family: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/hank/envs/adaptive-online-rl-v1/bin/python -u <Windows-mounted-v2-script>`. Raw logs `zero.log`, `zero_logging.log`, `minimal.log`, `history.log`, `zero_history.log`, `continuation.log` record stage progression and failures. Raw native `summary.json`, `trace.npz`, `native_reference.npz`, native evaluator records and losslessly verified compressed runtime artifacts are in the corresponding WSL result folders. The exact option/case config is saved per run.

E readiness **READY**; V readiness **READY**. Promotion requires all physical/history/branch gates plus integrity, not API unit tests. The readiness scope is this unified simulation interface on one exposed Human. No training evidence is claimed.

Exactly one next recommendation: freeze a separate bounded E/V training contract.

