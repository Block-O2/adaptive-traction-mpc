# Round19 development candidate freeze

**Status: DEVELOPMENT_CANDIDATE_FROZEN.** This is an offline development result from the actual simulated CR12 → compliant cuff → Human V2 closed loop. Fresh 48-case qualification was **not** run; `qualification_pass=false` remains correct. This result does not establish continuous-time safety between saved 0.25 ms nodes, hardware realtime, or physical robot readiness.

## Q1–Q4 promotion gate

The separate `ROUND19_PAIRED_QUALITY_EFFECT_AUDIT.md` used four existing Round18/Round19 pairs, no new simulation, and received an independent **Q_PASS** before any full23 rollout. Round18's near-edge estimated-state arrival caused the one false physical arrival. The Round19 causal confirmation removes that false handoff in the targeted case. Some paired RMSEs rise; phase mixture explains the aggregate q increase in two of four pairs, while two have within-phase descriptive increases. Most common-time/same-phase nodes have different references. There is no pre-Round19 frozen per-case pairwise RMSE non-inferiority margin, so none was added post hoc. The unchanged dual absolute quality gates, task/safety limits and full same-source development denominator govern promotion.

Existing telemetry gives complete **discrete native** evidence: N saved integration intervals plus initial boundary give N+1 true state nodes through the final physical boundary; receipt ownership and wall checks agree. The old `native_evidence_complete=false` field expects a 200 Hz sensor record exactly at terminal time, even when completion falls between sensor captures. The independent wall schema and new offline safety recheck preserve that old flag while validating all recorded native nodes. Full 20 ms acceleration is defined only after its first 80 native steps. There is no interstep certificate.

## Frozen candidate and execution

| Item | Frozen value |
|---|---|
| Production source manifest SHA-256 | `2880c67d0844ce551ff068474642a4b6ff9bc1fa2d7c81dfcd6914dd32c1ab99` (652 entries) |
| Controller options SHA-256 | `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb` |
| Case config snapshot SHA-256 | `ece5bae8330d5e8e8734784757aaadd76068c4e0e6f0c3ad0a79e9d2975ae70b` |
| Pre-run freeze | `ROUND19_FULL23_FREEZE.json` |
| Exact five batch commands | `ROUND19_FULL23_BATCH_COMMAND_V1.sh`; batch logs 1–5 |
| Raw simulations | `results/.../round19_full23_confirmation_v1/` |
| Native/wall/receipt scoring | `audits/native_round19_full23_confirmation_v1/` |
| Full machine result | `audits/native_round19_full23_confirmation_v1/ROUND19_FULL23_RAW_AUDIT.json` |

The frozen 23 keys equal the original executable development matrix; historical rejected slot `balanced_ordinary_r02` remains in its registered ledger and was not silently replaced. All 23 new cases were run once under the same Round19 source/options/config. No production or configuration file changed during the matrix. Raw per-case provenance, source map, config snapshot, trace, native intervals, summary, request ledger and failed-attempt records remain in the new result root; scoring was offline and did not add simulations. The source manifest was checked at the pre-run freeze and after each five-case batch; the independent Auditor rehashed all 23 scored products and run inputs and found no mismatch.

## Complete 23-case development result

| Frozen criterion | Result |
|---|---:|
| TASK entered | **23/23** |
| True physical OUTBOUND arrival within original 1° / 2°/s set | **23/23** |
| Continuous valid physical HOLD dwell ≥0.500000 s | **23/23** |
| Actual RETURN completion in original start set | **23/23** |
| True COMPLETE under the original task definition | **23/23** |
| Complete registered discrete native safety and wall evidence | **23/23** |
| Request timing and receipt-reference evidence | **23/23** |
| Same source/options/config | **23/23** |

All registered failure categories have count **0**: plan stale, waypoint infeasible, Human velocity, Human acceleration, measured sleeve clearance, measured shank clearance, force/moment, solver, timeout, transition semantics and other. The repaired `knee_dominant_middle_r01` now reaches physical OUTBOUND arrival at 14.150 s with maximum joint target error 0.740°; its valid continuous dwell is **0.520 s** and its actual RETURN completes. The minimum dwell across the full matrix is 0.520 s, only 20 ms over the frozen requirement.

| Case | Arrival time s | Max absolute arrival error ° | Continuous dwell s | Max absolute RETURN error ° | Original trace q RMSE ° |
|---|---:|---:|---:|---:|---:|
| balanced_near_upper_current_rom_r02 | 15.450 | .271 | .97875 | .606 | .548 |
| elevated_start_ordinary_r01 | 13.330 | .259 | .53000 | .200 | .360 |
| elevated_start_ordinary_r02 | 13.660 | .101 | .54500 | .219 | .357 |
| knee_dominant_middle_r02 | 14.125 | .683 | .54000 | .187 | .770 |
| knee_dominant_middle_r01 | 14.150 | .740 | .52000 | .394 | .752 |
| hip_dominant_ordinary_r01 | 13.415 | .163 | .52500 | .279 | .387 |
| balanced_middle_r01 | 14.305 | .443 | .53000 | .349 | .540 |
| balanced_middle_r02 | 14.290 | .836 | .63900 | .335 | .553 |
| balanced_near_upper_current_rom_r01 | 15.645 | .228 | .99850 | .547 | .537 |
| balanced_ordinary_r01 | 12.880 | .308 | .54000 | .134 | .471 |
| elevated_start_middle_r01 | 14.470 | .828 | .69125 | .427 | .436 |
| elevated_start_middle_r02 | 14.985 | .294 | .90300 | .544 | .392 |
| elevated_start_near_upper_current_rom_r01 | 15.440 | .197 | .54000 | .296 | .487 |
| elevated_start_near_upper_current_rom_r02 | 15.420 | .234 | 1.02375 | .289 | .515 |
| hip_dominant_middle_r01 | 14.975 | .226 | .54500 | .133 | .361 |
| hip_dominant_middle_r02 | 14.975 | .235 | .53000 | .134 | .378 |
| hip_dominant_near_upper_current_rom_r01 | 16.010 | .083 | .53000 | .327 | .384 |
| hip_dominant_near_upper_current_rom_r02 | 16.040 | .116 | .52500 | .056 | .408 |
| hip_dominant_ordinary_r02 | 13.390 | .231 | .53000 | .293 | .374 |
| knee_dominant_near_upper_current_rom_r01 | 15.315 | .103 | .54000 | .246 | .659 |
| knee_dominant_near_upper_current_rom_r02 | 15.230 | .058 | .53000 | .194 | .672 |
| knee_dominant_ordinary_r01 | 13.260 | .767 | .52500 | .107 | .482 |
| knee_dominant_ordinary_r02 | 12.965 | .848 | .53500 | .397 | .512 |

## Physical, quality and timing envelope

| Measure | Round19 full23 | Round18 full23, descriptive |
|---|---:|---:|
| Minimum measured sleeve / shank clearance | **0.035379 / 5.947059 mm** | 0.055001 / 5.965831 mm |
| Maximum human cuff force / moment | 131.113593 N / 18.113815 Nm | 131.059353 N / 18.097396 Nm |
| Maximum Human hip / knee velocity | 24.887227 / 35.736959°/s | 24.993809 / 36.016127°/s |
| Maximum Human hip / knee causal 20 ms acceleration | 241.509387 / 512.243754°/s² | 242.620104 / 512.038583°/s² |
| Planning compute maximum / p95 | 43.051292 / 40.171914 ms | 92.700083 / 40.131624 ms |
| Sample-to-activation maximum / p95 | 67.139333 / 64.280775 ms | 67.063083 / 63.800049 ms |
| Requests / activated / safely dropped | **430 / 430 / 0** | 423 / 422 / 1 |
| Stale / stale activated | **0 / 0** | 1 / 0 |
| Control-cycle misses / maximum backlog | **20,675 / 58.374 ms** | 18,503 / 64.987 ms |

The smallest sleeve gap occurs in `balanced_near_upper_current_rom_r02` during commissioning. It is positive against the unchanged registered boundary, but **0.035379 mm is narrow** and this deterministic development result is no robustness or continuous-time clearance guarantee. Total saved native evidence contains **1,793,990** boundaries and 1,793,967 intervals across 23 cases. There are no recorded ROM, velocity, acceleration, force/moment, geometry, robot torque/velocity or human-bed contact violations at those native nodes. The 20,675 missed control cycles remain recorded; no hardware realtime/WCET claim follows from this offline timing run. Session durations range 16.138–22.608 s; TASK durations 5.941–12.411 s. Maximum absolute terminal arrival error by hip/knee is .767/.848°; maximum absolute RETURN error is .606/.547°.

The frozen **two-stream** completed-cohort gate is median case q RMSE ≤2°, pooled absolute q p95 ≤5°, and median case dq RMSE ≤5°/s in **each** stream. Round19 original trace values are **.481997° / .982062° / 2.875222°/s** over all 23 true completions. Actual-receipt 200 Hz ZOH values are **.370590° / .803038° / 2.371275°/s**. Both pass. Original-trace per-case q RMSE has min/median/p95/max .357/.482/.744/.770°; dq RMSE 1.567/2.875/4.013/4.080°/s. ZOH q RMSE .284/.371/.594/.618°; dq RMSE 1.276/2.371/3.336/3.365°/s. Reference violation checkpoints are zero, and adaptation activity checks pass 23/23.

Round18 completed-cohort quality used **22** true completions: original trace .471833°/.953704°/2.796586°/s and ZOH .384933°/.796225°/2.258884°/s. The changed denominator and phase/reference supports prevent interpreting this aggregate difference as an isolated controller effect. All paired differences, including worsening values, remain documented in the Q1 report. No pairwise margin was added to secure promotion.

## Independent audit, provenance and stop

One independent read-only Auditor reviewed Q1–Q3 and returned **Q_PASS** before the matrix. The same Auditor then verified the frozen full23 matrix, 23 case/source/config/input hashes, true arrival/dwell/RETURN, full saved-native discrete coverage, dual quality, timing and zero stale activation, and accepted **DEVELOPMENT_CANDIDATE_FROZEN**. The only production differences from Round18 are the Round19 causal arrival confirmation and its evidence field; this turn made **no** production/config/model/task/safety edits. Related narrow clock tests had passed 25/25 before this turn; they were not rerun here. This turn ran 23 new development simulations and zero fresh qualification cases. Account weekly usedPercent was 3% at start and **5% at the final check** (added two percentage points). There was one independent Auditor, with two bounded read-only review calls, and zero CLI model workers. No hardware action or Git stage/commit/push/reset/branch change occurred.

The candidate is frozen for development. **Qualification is still required separately** under the existing fresh-case contract, with its own pre-run freeze, complete denominator and independent audit. The current task stops here; it does not start any fresh48 run.
