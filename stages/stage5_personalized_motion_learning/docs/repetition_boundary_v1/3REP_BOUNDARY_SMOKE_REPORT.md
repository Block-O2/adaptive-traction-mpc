# Repetition Boundary v1: three-repetition smoke

Status: **REPETITION_BOUNDARY_V1_VALIDATED**. This is a deterministic Scientific Simulation software smoke, not independent robustness or hardware evidence.

The first fresh attempt, `session_smoke_01`, preserved Rep1 PASS and a Rep2 bootstrap failure (`INCREMENTAL_RESPONSE_REQUIRES_ALIGNED_CAUSAL_ACCELERATION`). One permitted boundary repair added a fresh 5 ms causal monitor reseed before the new TRACK command and assigned a session-global response receipt ID while keeping physics receipts episode-local. No controller mathematics, Human dynamics, planner objective, safety threshold, scorer semantics or Scientific Mode scheduling changed.

| Rep | Task | Physical | Scientific | Scorer-v2 | J_F_task (N s) | J_F_session (N s) | Model sequence after | Settle (s) | Hold (s) |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | COMPLETE | PASS | PASS | True | 498.286447071 | 498.668945080 | 626 | 0.0 | 0.005 |
| 2 | COMPLETE | PASS | PASS | True | 501.521817634 | 502.669307604 | 903 | 0.0 | 0.005 |
| 3 | COMPLETE | PASS | PASS | True | 501.042531417 | 501.807949703 | 1179 | None | None |

Each completed rep has the same 13-waypoint sequence: five `outbound_dq_07`, one `outbound_dq_00`, `hold_dq_00`, five `return_dq_07`, one `return_dq_00`. The sequence and per-rep boundary metrics are in `PER_REP_BOUNDARY_METRICS.json`.

The two outgoing boundaries each settled immediately under the existing task start, force/moment, CR12 velocity and clearance gates, then held for 5 ms. The following epoch spent another 5 ms reseeding the short causal acceleration window under the carried physical command, then applied a fresh TRACK hold and advanced 5 ms. These 10 ms bootstrap intervals are included in `J_F_session` for the incoming rep; the explicit SETTLE/HOLD cost is assigned to the outgoing rep. `J_F_task` excludes all of them.

Native qpos/qvel and plant time match exactly across terminal → boundary → next epoch initial states; no teleport occurred. The Human updater sequence progressed 351→626→903→1179. The previous planner closed, episode objects were newly constructed, all boundary-audit flags passed, and the first request's sensor source was owned by the new epoch TRACK receipt. No cross-rep lifecycle leakage was detected by these checks.

The second complete group, `session_smoke_03_repeat`, used the same registered case, seed 20260918, options and thread settings. Selected numeric metrics, physical q/dq, waypoint sequences and boundary metrics were exactly equal in both groups; see `REPEATABILITY_RESULTS.json`. Raw trajectories remain Git-ignored; hashes for all three attempts are in `RAW_DATA_MANIFEST.json`.
