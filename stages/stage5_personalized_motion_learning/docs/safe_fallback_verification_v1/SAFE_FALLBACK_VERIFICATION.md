# Safe Fallback verification v1 — final

**SIMULATION_RESEARCH_BASELINE_NOT_FROZEN.** This is simulation research evidence only. The first case in the fresh 49-case matrix had a functional task failure, so the matrix stopped with 48 cases unrun. No 30-repeat, value learning, RL, fresh qualification, or hardware actuation was performed.

## Frozen source and gates

- Workspace branch: `codex/learning-safe-fallback-v1`; Safe Fallback source checkpoint `0cb898b61497b51b5d2a645b3941d03dd3f3f74b`; representative checkpoint `37c7ed9c3396e290f0534b8a9ff8566d68f52b39`.
- Identical 179-file production/config/scorer fingerprint before and after all runs: `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`. No production, plant, task, cost, solver, safety threshold, noise, duration, assumption, or scoring change.
- Prechecks: 15/15 deterministic/scorer-v2 tests, case/harness hashes, XML nq=nv=6, import, `git diff --check`. One initial import check lacked project PYTHONPATH; corrected check passed without source edits.
- Original eight-case representative set and new 23+10+16 development set retained in their frozen order. `DEVELOPMENT49_PREREGISTRATION.json` records checkpoint HEAD, fingerprint, case hashes, criteria and run order before the first 49 run. No case was substituted or rerun.

## Observed results

- **Targeted 8/8 PASS.** The final variable-start case ran once: COMPLETE, scorer-v2/safety/C2 PASS, reference near-stop 0.150 s, stale activation 0. Two older natural targeted runs use preserved corrected evidence reviews for a Boolean bookkeeping error; their raw runs were not repeated.
- **Representative 8/8 PASS.** All eight reran once under the current fingerprint. Fallback commits 0; stale activations 0; all scorer-v2, force, moment, clearance, q/dq, dwell, RETURN, RSS smoothness and C2 checks passed. Minimum valid dwell 0.580 s; peak force 117.000 N; peak moment 15.966 Nm; minimum session clearance 0.004022 m.
- **Fresh 49-case: 0/1 PASS; 48 unrun.** First case `low_balanced_near_upper_current_rom_r02` raised `STALE_COMMAND_SOURCE_MAXIMUM_AGE` during active COMMISSIONING, at physics time 4.2885 s. The command from sample 4.095 s was ready 41.125 ms after source capture; at the write guard its age exceeded 100 ms and it was cancelled before plant write. MuJoCo and 804 prior command receipts had applied, so this is **TASK_FAILURE**, not a setup-only nonstart. The exact host scheduling cause of the tail is unconfirmed. The three activated planner requests were <100 ms; no stale primary activation or fallback commitment was observed in this failed case. Source fingerprint and raw 29 MB runtime trace are preserved. No setup repair or rerun.

## Fallback and runtime boundary

Across targeted runs, 5 committed fallback events occurred in 5 cases; all those cases recovered to COMPLETE. The original natural run again showed a 191.053 ms planner tail and recovered. The 200 ms controlled delay stopped, held, dropped a late old plan, requested a fresh plan, resumed and completed. The representative runs had no fallback; this incomplete 49 case failed before the Safe Fallback branch was active.

All observed plan activations met the >=100 ms stale rule; deterministic tests include exactly 100 and 200 ms rejection. The failed command was rejected by a separate pre-write source-age guard. Normal-path reference near-stop and C2 continuity passed in all representative runs. Runtime characterization is in `RUNTIME_CHARACTERIZATION.json`; historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` and the 55 ms activation-tail failure remain FAIL. Simulation-host timing does not establish realtime or hardware safety. Earlier 49-case functional failure, scorer-v1 FAIL, and Safe Fallback development negatives remain intact.

No independent Auditor was dispatched: the task authorizes it only after 49/49 PASS. There is no final freeze checkpoint or `LEARNING_EXECUTION_CONTRACT.md`. The representative checkpoint is local only. ACCOUNT-WIDE quota: 29% start, 29% end; the unchanged value is not task-specific usage. Formal 30-repeat zero-value baseline is **not authorized**.

Raw runs are Git-ignored and linked by hashes in `RAW_DATA_MANIFEST.json`. `FAILURE_EVENT_TIMELINE.json` records the failed receipt and 48 unrun cases. No push, merge, reset, stash, clean, deletion, or worktree creation.
