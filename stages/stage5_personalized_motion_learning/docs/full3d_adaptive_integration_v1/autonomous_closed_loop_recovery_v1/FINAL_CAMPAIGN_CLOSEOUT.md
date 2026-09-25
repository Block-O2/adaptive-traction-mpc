# Full-3D CR12 simulation campaign closeout

**Status: SIMULATION_QUALIFIED under the frozen Attempt 2 gate.** Round19 development is 23/23 true COMPLETE; fresh Qualification Attempt 2 is 47/48 true COMPLETE against the preregistered minimum of 46/48. This closeout does not revise the controller, task, safety limits, scorer, or prior results.

## System and recovery

The tested offline loop is CR12 → compliant cuff → Human V2, with deployable causal observation and state estimation, the frozen Round19 reference/controller/planner, physical simulation feedback, and an execution gate that discards plans older than 100 ms. Simulation truth is reserved for generation and offline scoring. TASK requires physical arrival, at least 0.500000 s of continuous valid dwell, and actual RETURN completion.

The recovery started from 5/23 completed executable development cases in the reference-repair baseline. It retained the original 23-case matrix, task, plant, and safety definitions while addressing clearance, request timing, reference delivery, HOLD/RETURN transitions, and evidence accounting. Round18's full matrix reached 22/23 true completion; the remaining case had an estimated-versus-physical arrival boundary mismatch. Round19 added causal arrival confirmation and passed the unchanged full 23-case development gate. Qualification Attempt 1 remains **FAIL**: 48 registered, 10 started, 9 runner COMPLETE, one measured sleeve failure, and 38 unexecuted. Its exposed cases were not reused as fresh qualification evidence. Attempt 2 used 48 preregistered fresh cases and passed the frozen gate without a repair or rerun after outcomes were seen.

## Frozen candidate and outcomes

| Measure | Round19 development | Qualification Attempt 2 |
|---|---:|---:|
| Registered/executable cases | 23 | 48 |
| True physical arrival | 23 | 47 |
| Continuous valid dwell ≥0.500000 s | 23 | 47 |
| Actual RETURN and true COMPLETE | 23 | 47 |
| Saved 0.25 ms native-node safety audit | 23/23 | 48/48 |
| Stale-plan activations | 0 | 0 |

Frozen production source-manifest SHA-256 (652 entries): `2880c67d0844ce551ff068474642a4b6ff9bc1fa2d7c81dfcd6914dd32c1ab99`. Frozen controller config SHA-256: `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb`. The development and Attempt 2 reports, run provenance, and independent audits bind these same hashes. The original Attempt 2 48-case denominator was retained: the sole failure, `b02_elevated_start_near_upper_current_rom_r02`, is `plan_stale` after three requests expired without activation. All other registered failure categories have count zero. The cause of its long planning-compute tail remains unknown.

Development minimum measured sleeve/shank clearance was 0.035379/5.947059 mm; maximum force/moment was 131.114 N/18.114 Nm. Attempt 2 minima were 0.100000/5.446839 mm; maxima were 133.631 N/18.494 Nm. Attempt 2 had 897 requests, 893 activations, four safely dropped stale requests, and zero stale activations. Its planning-compute p95/max was 40.173/4143.554 ms; sample-to-activation p95/max was 63.776/77.342 ms. Control-cycle deadline misses were 20,675 in development and 40,509 in Attempt 2. The frozen dual quality and ten qualification gate checks passed, and the final independent Auditor accepted the Attempt 2 evidence.

## Claim boundary and remaining issues

This evidence supports **qualification of the frozen candidate in the specified offline MuJoCo simulation domain**. It does not support physical CR12 actuation, hard real-time operation, continuous-time safety between saved 0.25 ms nodes, clinical safety, or patient suitability. The measured development sleeve clearance is narrow. The unexplained Attempt 2 `plan_stale` failure, 4143.554 ms compute maximum, and many control-cycle deadline misses remain open engineering issues. No planning-latency study or new rollout is part of this closeout.

## Evidence and reproducibility

- [Frozen development report](DEVELOPMENT_CANDIDATE_FREEZE_REPORT.md), [Round19 freeze/source manifest](ROUND19_FULL23_FREEZE.json), [development promotion record](ROUND19_DEVELOPMENT_PROMOTION.json), and [independent full-matrix audit](audits/native_round19_full23_confirmation_v1/ROUND19_FULL23_RAW_AUDIT.json).
- [Attempt 1 failed disposition](FRESH_BATCH01_DISPOSITION_V1.json) and [frozen qualification contract](FRESH_QUALIFICATION_V1.md) (the ≥46/48 gate predates Attempt 2 execution).
- [Attempt 2 preregistration](QUALIFICATION_ATTEMPT2_PREREGISTRATION.md), [case manifest](QUALIFICATION_ATTEMPT2_CASE_MANIFEST.json), [versioned random-stream amendment](QUALIFICATION_ATTEMPT2_STREAM_AMENDMENT_V2.md), [freshness audit](audits/qualification_attempt2_v1/ATTEMPT2_FRESHNESS_AUDIT.json), [raw aggregate](QUALIFICATION_ATTEMPT2_RAW_RESULT.json), [frozen gate](audits/qualification_attempt2_v1/FRESH_COHORT_GATE.json), [full report](QUALIFICATION_ATTEMPT2_FINAL_REPORT.md), and [final independent audit](audits/qualification_attempt2_v1/INDEPENDENT_FINAL_AUDIT.json).
- Per-case provenance, request ledgers, native traces, and config snapshots remain in `results/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/round19_full23_confirmation_v1/` and `.../fresh_qualification_attempt2_round19_v1/`. Those local raw result trees are large; a Git checkpoint must state explicitly whether it contains them. A source-manifest match against the current workspace alone does not establish that a clean clone contains every source byte or raw trace.

## Repository checkpoint disposition

The requested closeout branch exists and the current workspace still matches the frozen source/config hashes. The [worktree classification](CLOSEOUT_WORKTREE_AUDIT.json) found pre-existing tracked Stage-5 source modifications inside the 652-entry manifest, many untracked files outside this campaign, and ignored raw trace trees. Their provenance cannot be safely reduced to a campaign-only staging list that would reproduce the complete frozen candidate in a clean clone. **CLOSEOUT_READY_COMMIT_BLOCKED_BY_WORKTREE**: no local commit or clean-clone reproduction is claimed. The [independent closeout audit](FINAL_CAMPAIGN_CLOSEOUT_AUDIT.json) returned `AUDITOR_PASS` for the scientific summary and claim boundaries; it did not rehash every source file or raw trace. The existing worktree and all earlier evidence are preserved.
