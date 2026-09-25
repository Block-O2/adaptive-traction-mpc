# Qualification Attempt 2 final report

**Status: QUALIFICATION_ATTEMPT2_PASS.** The frozen scorer reports `qualification_pass=true`, and the independent read-only final audit confirms the gate and evidence. This is offline simulation evidence, not hardware readiness.

## Candidate and preregistration

- Frozen Round19 production source manifest SHA-256: `2880c67d0844ce551ff068474642a4b6ff9bc1fa2d7c81dfcd6914dd32c1ab99` (652 files, unchanged before and after 48 runs). Frozen controller config SHA-256: `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb`. No production controller, planner, estimator, model, plant, task, safety, scoring or parameter change was made in Attempt 2.
- The versioned `QUALIFICATION_ATTEMPT2_STREAM_AMENDMENT_V2.md` froze separate setup/task PCG64 streams before Attempt 2 cases were exposed. Original domain ranges, mechanical screen, 48 slots, task/safety limits and qualification gate remained fixed. The existing lifecycle code retains its historical v1 internal identifier; the scientific generation protocol is Attempt2 v2.
- Batch 2 was presealed at root `7433081872978425150`; 48 unique slot seeds and 48 substantive `physical`+`task` payloads have zero overlap with Attempt 1 and the exposed original/generated/formal development bundles. Four slots belong to each of 12 family/range cells. Attempt 1 remains a failed, exposed 48-slot campaign.
- Generation was interrupted after 45 logged proposal/screen pairs and 25 finalized cases, before any rollout. Its exact prefix and hashes were preserved. The same consumed attempt was resumed by deterministic replay; the already accepted sixth proposal for slot 26 was materialized without redraw. Final ledger has 84 proposal/screen pairs, 48 sealed cases, unchanged root/seal, one attempt charge and no case replacement. Independent Auditor released F1 only after full payload freshness and bundle audit. The preexecution case manifest's `development_case_hash_count=24` covers original assembly cases; the separate freshness audit covers all exposed pools.

## Fixed 48-case outcome

| Measure | Result |
|---|---:|
| TASK entered | 48/48 |
| Valid physical arrival | 47/48 |
| Continuous true dwell ≥0.500000 s | 47/48 |
| Actual RETURN complete | 47/48 |
| True COMPLETE | 47/48 |
| Saved-native discrete safety pass | 48/48 |
| Source/config match | True |

One case, `b02_elevated_start_near_upper_current_rom_r02`, failed TASK and remains in the denominator. Three TASK requests took 4143.554/1794.255/1027.111 ms of planner compute, expired past 100 ms and were safely dropped without activation. The frozen three-expiry retry rule aborted TASK after 7.0015 s. Physical goal arrival, HOLD/dwell and RETURN never occurred. This is `plan_stale`, not true completion, stale activation or a safety pass converted into task success. The other three cases in its cell completed; all other cells completed 4/4. The cause of this planner compute tail remains unresolved.

| Failure category | Cases |
|---|---:|
| plan_stale | 1 |
| waypoint_infeasible | 0 |
| velocity | 0 |
| acceleration | 0 |
| measured_sleeve_clearance | 0 |
| measured_shank_or_table_clearance | 0 |
| force_or_moment | 0 |
| solver | 0 |
| timeout | 0 |
| transition_semantics | 0 |
| nonfinite_or_numerical | 0 |
| other | 0 |

## Safety, quality and timing

- The saved 0.25 ms native-node audit passed all 48/48 cases across 3,721,767 boundaries and 3,721,719 intervals, with no registered ROM, velocity, acceleration, force/moment, geometry or human-bed contact boundary violation. This checks sampled boundaries, not mathematical continuous-time safety between them.
- Minimum measured sleeve clearance: **0.100000 mm**; minimum measured shank/table clearance: **5.446839 mm**. Maximum interface force on either side: **133.631 N**; maximum moment: **18.494 Nm**. The narrow sleeve clearance is retained, not treated as a robustness margin.
- Human velocity peaks (hip/knee): [25.292785873672475, 36.564465933145605] °/s; 20 ms acceleration peaks: [217.46427753167328, 488.7017697626751] °/s². Robot joint velocity peaks: [19.864434577684545, 26.84758946188913, 7.508422889432355, 22.274836616940966, 27.905032936489228, 18.318095375640368] °/s; torque peaks: [77.39203151391536, 161.07111896357972, 52.57431288194961, 20.716522700587205, 13.527642670869499, 32.18710448881786] Nm.
- Frozen dual completed-cohort quality: original trace median q RMSE **0.487461°**, pooled q p95 **0.982259°**, median dq RMSE **2.872263°/s**; actual-receipt ZOH respectively **0.384422°**, **0.812546°**, **2.433717°/s**. Both meet ≤2° / ≤5° / ≤5°/s. Failed case is excluded only from the frozen completed-cohort quality statistic, not the 48-case denominator.
- Planning compute mean/p95/max: **28.740/40.173/4143.554 ms**. Sample-to-activation age mean/p95/max: **36.319/63.776/77.342 ms**. Requests **897**, activated **893**, safely dropped **4**, stale **4**, stale activated **0**. Safe drop did not hide the failed task.
- Control-cycle deadline misses: **40,509**; maximum backlog **89.828 ms**. These offline timings do not establish hardware real-time performance.

## Frozen qualification gate

Completion **47/48** exceeds the preregistered ≥46/48 threshold. Adaptation-active cases **48/48** exceed ≥36/48. Each of 12 cells has ≥1 true completion. The independent failure review found one isolated, mechanism-classified task failure and no unexplained concentrated cell failure; it did not establish the underlying compute-tail root cause.

| Frozen check | Scorer result |
|---|---|
| exact_denominator | PASS |
| all_registered_outcomes_terminal | PASS |
| all_executed_evidence_and_safety | PASS |
| completion_threshold | PASS |
| cell_coverage | PASS |
| adaptation_activity | PASS |
| dual_quality | PASS |
| source_audit | PASS |
| relevant_tests | PASS |
| no_unexplained_concentrated_failure | PASS |

Frozen scorer output: `gate_passed=true`, `qualification_pass=true`. The independent final Auditor reproduced the 48-case denominator, source/config and case provenance, freshness, true task semantics, saved native-node safety, timing/stale accounting, dual quality, and all ten frozen gate checks. All 47 completed cases have uninterrupted true goal dwell of at least 0.525 s. The failed case remains in the denominator. The separate saved N+1 wall/native coverage supports full sampled-node evidence for the aborted case even though its older per-case `legacy_native_complete=false` field reflects terminal trace lag. Auditor verdict: `FINAL_AUDIT_PASS`.

## Provenance and task boundary

- Case manifest: `QUALIFICATION_ATTEMPT2_CASE_MANIFEST.json` SHA-256 `9b0a30e95d5f12b96bca6c5c2d7ebb60cc52e59819b9a5937d978d73e4071f24`; bundle manifest SHA-256 `e426e2397e7a9e4cd44c164173997cef266a59882d7e227f3e80806ef99cb9cf`.
- Full metrics: `QUALIFICATION_ATTEMPT2_RAW_RESULT.json` SHA-256 `806c30ccbc4b8b5332567ff6d943124c8de9f0764e24f7b24a27c00b5579ade3`; fresh gate: `audits/qualification_attempt2_v1/FRESH_COHORT_GATE.json` SHA-256 `6568f3e2929c7b2f88c09a0314a00e71b11990ed6b8bccec765f93876a5f6ea7`; native coverage and all per-case artifacts are retained.
- Attempt 2 ran **48 qualification simulations** and no case rerun. No Attempt 3, repair cycle, hardware actuation, Git staging, commit, push, reset or branch change occurred. The earlier STOP marker was copied into the audit directory before the user-authorized bounded continuation.
- Weekly account usedPercent start: **5%**; end: **8%** (3 percentage points added). One independent read-only Auditor, **8 review turns**; no other model/CLI worker calls outside the frozen controller's own planner.

**Recommended next step:** Stop after final audit and ask the user to decide whether to use this qualified simulation candidate for any subsequent, separately authorized work.
