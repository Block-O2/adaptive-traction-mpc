# Zero-value continuous session: V2 smoke report

**Result:** `ZERO_VALUE_3REP_SESSION_SMOKE_FAIL`. This fresh group stopped after Rep1 completed and Rep2 failed during runtime setup. The preserved previous attempt is `session_smoke_01`; the fresh attempt is `session_smoke_02`. No repeatability run was started.

## Preflight

- Eight focused deterministic tests: PASS. Scored `future_value=0` and explicitly unscored `future_value=null` are accepted; scored nonzero value, missing status, and inconsistent unscored status fail.
- Offline parse of the preserved first attempt's Rep1: 13 decisions, including an unscored candidate, PASS.
- Standalone `balanced_ordinary_r01` scientific simulation: COMPLETE; physical, scientific, and raw scorer-v2 PASS (40.45867936 s host time).
- Same registered case, case SHA `ceb33e9eeb243d49ad4bd1ad0a17637243219f3e058f4da0aaf2ed9fbf975b2d`, options SHA `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb`, seed 20260918, and single-thread WSL scientific environment. Frozen production fingerprint: `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`.

## Fresh continuous group

| Rep | Execution | Physical | Scientific | Scorer-v2 | Human model version | J_F (N·s) |
|---|---|---|---|---|---|---:|
| 1 | COMPLETE; OUTBOUND→HOLD→RETURN | PASS | PASS | PASS | 351→626 | 498.286447070754 |
| 2 | EXCEPTION during reference-history setup; no task execution | — | — | — | unmeasured | — |
| 3 | Not started | — | — | — | unmeasured | — |

Rep1 selected waypoint labels: `outbound_dq_07, outbound_dq_07, outbound_dq_07, outbound_dq_07, outbound_dq_07, outbound_dq_00, hold_dq_00, return_dq_07, return_dq_07, return_dq_07, return_dq_07, return_dq_07, return_dq_00`. Its 13 logged decisions passed zero-value validation; evaluated candidates had zero learned value contribution and baseline selection remained in force. No progression or force trend can be inferred from one completed repetition.

Rep1 measured peak cuff force: 108.719429708165 N; cumulative/peak moment: 55.268007056088 N·m·s / 14.435377459908 N·m. Minimum session clearance: 0.017871243177 m. Phase durations: [2.489999999994197, 0.5149999999987998, 2.519999999994127] s. Initial/final Human and CR12 q/dq, native qpos/qvel, raw trajectory, and all per-repetition metrics are in `session_smoke_02/per_repetition.json` and `rep_01/trace.npz`; the per-repetition CSV is alongside them.

## Failure boundary

`AppliedReferenceMotionHistory.__init__` accepts `(clock, initial_q, initial_dq, initial_time_s)`. The resumed Rep2 path at `runtime.py:1796` passes `*initial_reference` where `initial_reference=(start_q, zeros_dq, zeros_ddq)`, then passes time. This supplies one extra positional argument, causing `TypeError:AppliedReferenceMotionHistory.__init__() takes 5 positional arguments but 6 were given`. The Rep2 exception is recorded in `rep_02/HIGH_ROM_CASE_RESULT.json`.

Rep1 carried model version 626 at completion, but Rep2 could not finish initialization. Rep1→2 physical state continuity, transient reset, stale planner isolation, and leakage cannot be fully evaluated. Rep2→3 was not reached. The harness's design carries the physical plant, Human updater and belief, causal observer, command-response history, and committed command metadata; it recreates task phase, arrival/dwell, reference/planner lifecycle, supervisor, monitors, scorer, trace, and per-repetition metrics. This run validates only the Rep1 initial boundary, not either cross-repetition boundary.

The first fresh dynamic group failed, so the repeatability session and 30-repetition baseline were not run. No ready checkpoint was committed or pushed. Local HEAD is `b2a8d3bb8716859bd3cad9f7e834b8f02112658f`; remote `codex/wsl-learning-scientific-v1` is the same SHA, and `origin/codex/zero-value-session-v1` does not exist. Raw artifact hashes are in `RAW_DATA_MANIFEST_V2.json` and all listed hashes were verified.
