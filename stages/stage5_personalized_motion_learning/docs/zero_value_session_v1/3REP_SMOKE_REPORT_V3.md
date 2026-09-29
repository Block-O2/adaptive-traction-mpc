# Zero-value continuous session: V3 smoke report

**Escalation:** `ZERO_VALUE_SESSION_BOUNDARY_AUDIT_REQUIRED`. Raw dynamic status: `ZERO_VALUE_3REP_SESSION_SMOKE_FAIL`. V3 is the third preserved attempt; no fourth dynamic attempt or repeatability group was started.

## Changes and preflight

The immediate V2 TypeError was fixed by passing only q/dq and time to the existing `AppliedReferenceMotionHistory` constructor. The Rep2 skipped-commissioning field read was guarded, and measurement-layer filter/RNG/delivery history was retained across epochs. No underlying reference or control mathematics was changed. The static lifecycle audit is in `REP_BOUNDARY_AUDIT.md`.

Before V3 dynamic execution: zero-value parser 8/8 PASS; direct reference-history and three-epoch lightweight lifecycle 3/3 PASS; scientific scheduler/integration/time contracts 21/21 PASS; standalone scientific case COMPLETE with physical/scientific/scorer-v2 PASS; source compilation PASS.

## Fresh V3 group

| Rep | Execution | Physical | Scientific | Scorer-v2 | Human model version | J_F (N·s) |
|---|---|---|---|---|---|---:|
| 1 | COMPLETE; OUTBOUND→HOLD→RETURN | PASS | PASS | PASS | 351→626 | 498.286447070754 |
| 2 | Exception at first task planning request | — | — | — | no completed task | — |
| 3 | Not started | — | — | — | — | — |

Rep1 used the unchanged baseline waypoint policy; all 13 logged decisions passed zero-value validation with learned contribution 0. Its measured peak force was 108.719429708165 N, moment integral 55.268007056088 N·m·s, peak moment 14.435377459908 N·m, and minimum session clearance 0.017871243177 m. Phase durations were [2.489999999994197, 0.5149999999987998, 2.519999999994127] s. Human and CR12 q/dq boundaries, native state, waypoint sequence, and per-rep metrics are in `session_smoke_03/per_repetition.json` and `.csv`; raw trajectories remain ignored by Git. No three-repetition trend is inferred.

## New boundary failure

Rep2 reached its first task planning request, then `runtime.py:3014` called `receipt_reference_at_sample` in `terminal_reference.py:297`. That API requires the receipt owning the sensor source to have `mode=TRACK`. The fresh epoch's synthetic continuing-support receipt is applied but has no TRACK mode, so it raises `ValueError:tracking error has no TRACK reference at sensor source`. The stack trace is in `session_smoke_03/rep_02/HIGH_ROM_CASE_RESULT.json`. This is a new session receipt/reference lifecycle error. Rep2 did not produce a completed repetition row; neither Rep1→2 nor Rep2→3 dynamic boundary passed the complete gate.

The earlier static audit and mocked lifecycle test did not exercise the first task request against real receipt ownership. Further work requires a separate static/unit audit of cross-epoch command receipt provenance, sensor-source timestamp coverage, TRACK versus support mode, reference-history seeding, planner first-request snapshot, and terminal-command handoff. The user-directed V3 escalation rule prohibits another repair-and-rerun cycle now.

The first group failed, so repeatability was not run. Cross-repetition leakage remains unverified; no leak can be ruled in or out from this incomplete boundary. No ready checkpoint was committed or pushed. Local HEAD and remote source branch are `b2a8d3bb8716859bd3cad9f7e834b8f02112658f`; `origin/codex/zero-value-session-v1` is absent. Frozen production fingerprint: `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. All 14 hashes in `RAW_DATA_MANIFEST_V3.json` were verified.
