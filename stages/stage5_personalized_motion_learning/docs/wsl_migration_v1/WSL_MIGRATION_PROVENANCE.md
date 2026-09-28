# WSL migration provenance

Migration branch: `codex/learning-wsl-migration-v1`. Pre-migration HEAD: `3aceaa8d178559bfe910b9aab6ead0f895935e6b`. Safe Fallback production implementation checkpoint: `0cb898b61497b51b5d2a645b3941d03dd3f3f74b`. The final migration HEAD is the immutable Git object reported by `git rev-parse HEAD` after the closeout commit and must equal `git ls-remote origin refs/heads/codex/learning-wsl-migration-v1`. It cannot be embedded in its own committed contents.

Production source fingerprint: `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7` over 179 frozen source/config/scorer files; map SHA256 `5043119ad85feac3ce97dce482a792d6137ec1da30df7f49c6a0fd41f7c704ba`. This closeout does not change those files, scientific parameters, task/safety thresholds, controller, plant, scorer, Safe Fallback or commissioning semantics. New files are migration orchestration and documentation; the old evidence runner receives path-only portability fixes.

## Commit graph from production checkpoint

| Commit | Purpose | Production change | Evidence only | Scientific status |
|---|---|---|---|---|
| `0cb898b` | Safe Fallback implementation and seven targeted passes | Yes | No | Development checkpoint, not baseline freeze |
| `37c7ed9` | Eighth targeted and 8/8 representative verification | No | Yes | Development representative PASS |
| `3303004` | First fresh49 failure | No | Yes | 0/1 PASS; 48 unrun; TASK_FAILURE |
| `a310112` | Account quota observation | No | Yes | No new scientific result |
| `3aceaa8` | Moving commissioning stale recovery audit | No | Yes | Architecture recovery unjustified; unresolved |

Known PASS: targeted 8/8 and representative 8/8 under scorer-v2 and frozen source fingerprint. Known FAIL: prior 49-case baseline failed on ~191 ms planner tail; controlled 200 ms delay exercised certified fallback; Safe Fallback fresh49 first case failed during moving commissioning and stopped at 0/1. RSS runtime qualification remains `RSS_RUNTIME_QUALIFICATION_NOT_MET`; activation has observed >55 ms tail (representative maximum 61.909 ms). The 100 ms source age expiration rule rejects stale commands; no stale activation is an observed property of these runs, not a universal guarantee. Safe Fallback uses prevalidated committed stop, hold, fresh replan and resume; this does not repair the moving commissioning stale-command failure.

Historical evidence: `docs/simulation_research_baseline_v1`, `docs/safe_fallback_execution_v1`, `docs/safe_fallback_verification_v1`, `docs/commissioning_stale_recovery_v1`, and `docs/scorer_v2_endpoint_v1` under Stage 5. Raw traces remain local and ignored; tracked result summaries and SHA manifests preserve provenance. The untracked `CHECKPOINT_SHA.txt` was inspected and included as an exact implementation SHA pointer. No old FAIL was removed. No real robot was actuated. Status is a migration checkpoint, **not** `SIMULATION_RESEARCH_BASELINE_FROZEN`, hard-real-time, hardware or clinical qualification.
