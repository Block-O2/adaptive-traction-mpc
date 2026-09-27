# Scorer-v2 RETURN endpoint semantics

**Status: `SCORER_V2_VALIDATED` for offline development scoring.** This is a versioned independent evaluation change. Production control, RSS, planner, task state machine, estimator, physical model, safety limits, 2.000°/s threshold and runtime gate are unchanged. No new simulation was run.

## Frozen definition

- Keep the COMPLETE proposal/source time and state. For RETURN endpoint only, score the exact native physics state whose timestamp equals the accepted physical COMPLETE commit and the RETURN→COMPLETE transition. Require the last native node and the saved final native boundary to agree exactly. Missing or ambiguous mapping raises `EndpointMappingError`; there is no nearest-node tolerance.
- Do not interpolate, delay a fixed number of milliseconds, or search for the first favorable sub-threshold node. The native truth enters only the post-run evaluator. Save scorer-v1 source timestamp/state, proposal estimated state, commit timestamp/state, scorer-v2 timestamp/state, and version metadata.
- All other scorer-v1 conditions, including task quality, safety, clearance, force/moment, stale plan age, and thresholds, are reused without alteration. The original `summarize_phase_b.py` remains unchanged and reproduces its historical FAILs.

## Existing-trace comparison

| Case | v1 sample (s) | v1 knee (°/s) | v1 | physical commit / v2 sample (s) | v2 knee (°/s) | v2 | Other task/safety |
|---|---:|---:|---|---:|---:|---|---|
| `p03_rss` | 23.740000 | 2.007421042 | FAIL | 23.742250 | 1.997947357 | PASS | identical |
| `p04_rss` | 23.760000 | 2.000546705 | FAIL | 23.762000 | 1.987412362 | PASS | identical |
| `p01_rss` | 23.705000 | 1.854932032 | PASS | 23.707000 | 1.848840326 | PASS | identical |
| `p03_c08` | 27.500000 | 0.963982884 | PASS | 27.502000 | 0.981384939 | PASS | identical |
| `p04_c08` | 27.480000 | 0.982847320 | PASS | 27.482500 | 1.001036810 | PASS | identical |

`p03_rss` and `p04_rss` are explicitly labeled `RESCORED_UNDER_SCORER_V2`; their old scorer-v1 FAIL evidence is preserved. The five retained runs score 3/5 under v1 and 5/5 under v2. The only existing fields changed are `conditions.true_return`, `true_return`, final true q/dq, and the derived overall `pass`; for the three already-passing runs, only endpoint q/dq descriptive values changed. Full original and v2 score objects are in `SCORER_V1_V2_EXISTING_COMPARISON.json`. Repeated v2 scoring was exactly deterministic.

## Historical impact

The bounded audit scanned **253 canonical scorer-v1 development traces**: 244 `CLEAR_MARGIN`, 2 `NEAR_BOUNDARY`, 0 `NO_RAW_TRACE`, and 7 non-COMPLETE. The two near-boundary cases are the retained `p03_rss` and `p04_rss`; both change FAIL→PASS when scored at the exact commit. No other development RETURN endpoint result changed. The near classification is derived from each run’s observed source-to-commit velocity change versus its original threshold margin, not a post hoc fixed band. The full inventory and run paths are in `HISTORICAL_IMPACT_AUDIT.json`. For the 244 clear-margin inventory rows, the bounded scan used the saved final-native-boundary snapshot and matching COMPLETE timestamp; full last-node mapping was run on the two near-boundary cases and the other three five-case controls.

Round19 formal Qualification Attempt 2 has its own earlier frozen scoring contract and 47/48 result. The High-ROM `summarize_phase_b.py` scorer-v1 was not its scorer. This change does not alter that historical qualification claim; an analogous audit of its separate scorer is outside this request. No qualification-level blocker was found within the scorer-v1 impact scope.

## Verification and limitations

- Four focused mapping tests passed, including exact timestamp failure and boundary-state mismatch rejection. Five existing traces passed v1 reproducibility, v2 deterministic repetition, and unchanged non-RETURN task/safety conditions. The scorer-v2 CLI result on retained `p03_rss` matched the offline v2 endpoint and all conditions. `py_compile` and `git diff --check` passed. The initial `unittest -m` invocation used an invalid absolute module name, and the first `py_compile` attempt was blocked from writing a bytecode cache outside the sandbox; corrected commands passed without source edits.
- Commands: `PYTHONPATH=.../scripts/high_rom_v1 .../mpc_learn/bin/python tests/high_rom_v1/test_score_return_endpoint_v2.py -v`; versioned CLI on retained `p03_rss`; `docs/scorer_v2_endpoint_v1/compare_existing.py`; `docs/scorer_v2_endpoint_v1/audit_history.py`; `PYTHONPYCACHEPREFIX=/private/tmp/scorer_v2_pycache .../mpc_learn/bin/python -m py_compile ...`; `git diff --check`. Analysis scripts use fixed local paths to this worktree and write temporary aggregates before copying them into this document directory.
- No new development simulation was run. Thus a newly generated run artifact has not been compared against its later offline rescore; the retained-trace CLI and function outputs agree.
- Weekly bucket `codex.primary`: 6% used at start, 7% at last valid read, same 10080-minute window ending Unix 1791047434. At +1 percentage point, the historical audit scope was closed and no optional new simulation was started.
- Branch `codex/full3d-cr12-waypoint-smoothness-v1`, HEAD `1901d4f6806cf08016495cabace58626ce994181`. Previously dirty production files match the prior audit fingerprints byte-for-byte; scorer-v1 is unchanged. This turn adds only scorer-v2, tests and docs. Nothing was staged, committed, pushed, merged, reset, stashed, cleaned or deleted.

## Next step

If needed, run one separately scoped development case that emits scorer-v2 as a post-run artifact, then compare that artifact to an independent offline invocation. Do not revise scorer-v1 results or formal qualification.
