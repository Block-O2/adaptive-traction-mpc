# Safe fallback execution result

Final status: **PAUSED_QUOTA_OR_TIME**.

Targeted: 7/7 executed PASS; fixed targeted denominator 8. Optional original eight-case representative freeze NOT run because account-wide usage reached 29%. This is not FALLBACK_EXECUTION_REPRESENTATIVE_READY and does not authorize a 49-case freeze.

| Run | Task | Gate | Fallbacks | Ref near-stop s | Stale activations | Force N | Moment Nm |
|---|---|---|---:|---:|---:|---:|---:|
| original_natural | COMPLETE | True | 1 | 0.15000000000071623 | 0 | 115.64525046479585 | 15.50598479644723 |
| delay_0 | COMPLETE | True | 1 | 0.15000000000071623 | 0 | 115.60327440776982 | 15.502986758066886 |
| delay_100 | COMPLETE | True | 1 | 0.20000000000095497 | 0 | 115.60166780916343 | 15.503446832763682 |
| delay_200 | COMPLETE | True | 1 | 0.21000000000100272 | 0 | 115.7896574032156 | 15.504103854919778 |
| targeted_low_ordinary | COMPLETE | True | 0 | 0.13499999999968537 | 0 | 109.1426639283282 | 14.491102521494161 |
| targeted_high_120_sync | COMPLETE | True | 0 | 0.1550000000007401 | 0 | 115.6118265496893 | 15.743962562872019 |
| targeted_high_120_hip | COMPLETE | True | 1 | 0.1750000000008356 | 0 | 115.51635278706935 | 15.735564426335648 |

## Required answers

1. The historical 191.428 ms compute failure occurred because a 40 ms bridge ended at nonzero dq while the future was unfinished. It aborted at source age 47.488 ms, before expiry. Historical failure and matrix are unchanged; see READ_ONLY_RECONSTRUCTION.md and the provenance checkpoint.
2. The selected primary carries a prevalidated original bridge and stop before activation. Fork = latest certified 5 ms bridge grid node strictly before endpoint (0.035 s in tested cases). Receipt reference progress is capped at the fork; primary not activated/validated before reaching it commits braking irrevocably. This is a reference-progress deadline, not a wall-clock/WCET guarantee.
3. Constructing/validating the stop occurs in the isolated worker before primary admission. Commit and stop sampling do not call or await the future planner. The existing per-command safety supervisor still runs. Delayed/cancelled producer output cannot preempt braking. The scope is current deployable model and tested simulation, not universal physical invariance.
4. Original-case 200 ms availability delay passed stop→hold→fresh replan→resume→COMPLETE. Result became visible at source age 239.214 ms and was dropped; fresh resume age was 62.397 ms. Natural run independently reproduced a 191.053 ms compute tail and recovered.
5. Natural and 0 ms runs each included a natural fallback; do NOT claim zero-fallback normal execution for them. Both retained whole-trace near-stop=0.150 s, below the frozen original-case cap .350 s. Separate no-fallback representative evidence is in the table. All original primary q/dq/ddq polynomials are unchanged by the preparation adapter. Intentional fallback occurrences are explicitly reported.
6. All executed-run stale activations are in the table. Deterministic tests reject exactly 100 and 200 ms. The previous >100 comparison was tightened to >=100; timestamp origins were not renewed. Scorer-v2 source and thresholds are unchanged.
7. Optional original eight-case representative freeze was NOT run. The targeted denominator is a different eight-run development protocol and must not be conflated with representative readiness.

8. Production source/config/scorer fingerprint (179 files including the new module): `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`. Freeze v1 matched after execution.

9. Provenance-only checkpoint: `8a995494b4afa9615c7aacaeec66a99596e576eb`. Final candidate checkpoint is recorded separately in CHECKPOINT_SHA.txt after commit; no promotion implied.

10. ACCOUNT-WIDE usage: original task start24%, authorized resume26%, last29%, reset window1791047434. Shared-account delta, not measured task-only consumption. No quota reset.

11. Do not start49-case. The one next step, only with renewed quota authorization, is the unrun targeted variable-start case on the unchanged candidate. Optional eight-case and49 remain blocked until this gate passes.

## Validation and integrity

15 deterministic/scorer tests passed. 69/69 retained moving endpoints passed the pre-implementation model feasibility check, not a new dynamic campaign. AST and git diff --check passed. Tests initially failed collection due to missing scorer PYTHONPATH; the failing invocation remains. One evidence-wrapper Boolean bookkeeping correction is charged conservatively as the single repair. Old false summaries and separately recomputed corrected reviews remain; no natural/0ms rerun and no production repair occurred. See SCORING_BOOKKEEPING_CORRECTION.md. No acceptance threshold or scorer-v2 semantics changed.

Files: three existing production modules changed (runtime.py, online_planning.py, activation_validation.py); safe_fallback.py added; one test module added; new docs/protocol/results/manifests under docs/safe_fallback_execution_v1. No scientific cost/search/task/force/moment/clearance/ROM/noise/plant/solver/rollout-duration changes. New execution assumption is explicit admission of a certified escape; no new sensor or hidden truth. Source of escape inputs is deployable belief/reference/registered limits. No hardware actuation. No subagent or independent Auditor was dispatched.

Commands and environment: COMMANDS.json. Raw traces remain ignored; RAW_DATA_MANIFEST.json gives hashes. All attempted dynamic runs retained and none retried for a random PASS. No49-case/30-repeat/value/RL/fresh qualification. Local individual staging/commits only; no push/merge/reset/stash/clean/delete/worktree creation. Canonical checkout source was not edited.

## Future async value contract

The architecture supports a droppable producer: execution owns the selected primary plus escape independently. A future value interface must fix value/model/trajectory versions, enforce its ranking deadline, drop late outputs, and use baseline ranking when missing. It must not delay execution or bypass activation validation. No value/RL implementation or training was performed.

Hard stop: ACCOUNT-WIDE29%. The final variable-start targeted case remains unrun; no additional worker or run will be dispatched. All seven completed targeted runs, including hip-leading delay, remain preserved.
