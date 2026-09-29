# 3-repetition smoke report

**ZERO_VALUE_3REP_SESSION_SMOKE_FAIL**

## Exact outcome

The preflight standalone low-ROM scientific repetition completed in 38.902 s
host time and passed physical, scientific, and mode-aware evaluation. Five
deterministic session-state tests passed before the attempted continuous
session.

The single requested session attempt started Rep 1 and completed it. Rep 1
was COMPLETE with OUTBOUND → HOLD → RETURN, physical PASS, scientific PASS,
and raw scorer-v2 PASS. The session harness then stopped before Rep 2 because
its zero-value logger incorrectly rejected a candidate that had been
screened out before scoring. At decision index 4, that candidate's
`cost_terms.future_value` and `total_cost` were both null. All evaluated
candidates had `future_value=0`; the decision's numeric value hook was 0
and its value hook was not configured. The parser now distinguishes
unevaluated candidates and its deterministic regression passes. The
original failed attempt and its source hashes remain unchanged.

No Rep 2, Rep 3, or repeatability run occurred. Consequently real
cross-repetition continuity, reset, model persistence, and state-leakage
behavior remain **unverified**, even though the source now has a conditional
carryover path and its pure state-filter test passes. The session is not a
3-repetition PASS.

## Measured Rep 1 results

| Metric | Rep 1 | Rep 2 | Rep 3 |
| --- | ---: | --- | --- |
| Status | COMPLETE; physical/scientific/scorer-v2 PASS | Not run | Not run |
| `J_F` (measured N·s) | 498.2864470707535 | Not available | Not available |
| Measured moment integral (N·m·s) | 55.268007056087825 | Not available | Not available |
| Peak measured force (N) | 108.71942970816471 | Not available | Not available |
| Peak measured moment (N·m) | 14.435377459907963 | Not available | Not available |
| Completion time (sim s) | 5.5249999999871235 | Not available | Not available |
| OUTBOUND/HOLD/RETURN (sim s) | 2.490 / 0.515 / 2.520 | Not available | Not available |
| Human belief sequence, task start → end | 351 → 626 | Not available | Not available |

The trace-derived `J_F` agrees with the runtime's recorded
`498.28644707191495` N·s to numerical summation tolerance. The task had
1105 executed intervals, 13 waypoint decisions, a minimum deployable session
clearance of 0.01787124317737709 m, a minimum true physical clearance of
0.02560490714283214 m (evaluation only), and peak robot torque fraction
0.36764017495640267. The full 13-label waypoint sequence and candidate
records are preserved in `POSTHOC_REP1_DIAGNOSTIC.json` and
`zero_value_waypoint_decisions_POSTHOC.json`. With only one repetition,
waypoint change across repetitions cannot be assessed.

## Provenance and next gate

The WSL checkout began clean on `codex/wsl-learning-scientific-v1` at
`b2a8d3bb8716859bd3cad9f7e834b8f02112658f`. The remote frozen branch
HEAD matched exactly, and all 618 frozen production file hashes matched
`56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`
before modification. Work is on `codex/zero-value-session-v1` with
uncommitted code, tests, and this report. There is no new checkpoint commit
or remote SHA. No files were staged, committed, pushed, reset, stashed,
cleaned, or merged.

Raw trajectories remain ignored under
`results/zero_value_session_v1/session_smoke_01`. The original
`session_result.json` says FAIL, and its original provenance records the
source hashes used during the attempt. `POSTHOC_REP1_DIAGNOSTIC.json`,
`per_repetition_partial.csv`, and `RAW_DATA_MANIFEST_POSTHOC.json` preserve
the subsequent read-only analysis and hashes. The parser fix happened after
the attempted run. No 30-repetition zero-value baseline is authorized; a
new, explicitly versioned 3-repetition attempt would be needed first.
