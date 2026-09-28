# Simulation research baseline freeze

**Final status: SIMULATION_RESEARCH_BASELINE_NOT_FROZEN.** This is simulation development evidence. It is not runtime, continuous-time safety, hardware, or clinical qualification.

## Candidate and checks

- Workspace: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-learning`; branch `codex/adaptive-traction-learning-baseline`; starting HEAD `5d977ab321af72d4ddb8fef919449c37ad67a4f9`.
- Unique SOURCE_FINGERPRINT: `920b030d191eed8286aad355304c114bfc459a58ae6972dbdd1666f1c935103b`. All 178 frozen source/config/scorer hashes matched before and after runs; production source and scientific parameters were unchanged. The failed split-revalidation module is absent.
- Starting worktree was clean. Scorer-v2 unit tests 4/4 PASS; CR12 XML loaded (nq=nv=6); runtime and High-ROM imports resolved inside this worktree; `git diff --check` PASS.
- The 8-case representative and 23+10+16 development payloads were hash checked before execution. No case was replaced or rerun.

## Results

- Representative: **8/8 PASS** under scorer-v2 task/safety, registered RETURN, frozen smoothness checks, and zero stale activation. Minimum valid dwell 0.590 s; reference near-stop 0.125–0.180 s.
- Development: **35/36 executed PASS**; 13 registered cases remain unrun after the failure. Low ROM 23/23 PASS; fixed-start High-ROM 10/10 PASS; variable-start High-ROM 2/3 PASS.
- Blocking case: `high_rom_function_fresh_03_v1`, start (6°,11°), target (120°,120°). The MuJoCo run reached OUTBOUND→HOLD and HOLD→RETURN, then ABORTED during RETURN at simulation time 24.420000 s with `PASS_THROUGH_PREFETCH_NOT_READY_AT_ENDPOINT`. Request 18 came from the 24.375000 s sample and took 191.428 ms compute. The pass-through segment reached its endpoint before its asynchronous prefetch future was ready; the explicit runtime abort branch fired. Last saved true q was (29.032°, 34.714°), far from the registered RETURN start. This is a real task-completion failure, not a setup-only or scoring artifact.
- Across 43 passing trajectories: minimum valid dwell 0.530 s; maximum reference near-stop 0.300 s; maximum actual near-stop 0.210 s; highest peak force 131.207 N; highest peak moment 18.164 Nm; minimum deployable session clearance 0.000916 m. Saved C2 switch jump and stale activation checks passed.

## Runtime and claim boundary

- The 43 passing runs had zero stale activations. The aborted run's late prefetch was cancelled, not activated. No ≥100 ms stale activation was found. This corpus did not exercise every ≥100 ms rejection branch, so it does not independently prove every fallback.
- Passing-run planning-compute p95 range 19.036–32.457 ms; 9 runs exceeded the historical 30 ms gate. Activation p95 range 36.771–54.967 ms in this corpus; historical 55 ms tail FAIL remains. Maximum observed passing-run control miss ratio 15.745%. These are characterization only, and the 191.428 ms failure shows timing can become a functional blocker.
- `RSS_RUNTIME_QUALIFICATION_NOT_MET` and protocol-v4 failure remain unchanged. No hard-real-time, continuous safety, hardware, or clinical claim follows.
- Raw manifest: 44 retained run directories, 264 files, 7,670,081,586 bytes, SHA256 per file. Large raw trajectories remain git-ignored.

## Commands, provenance, and stop

- Exact run command template: `python stages/stage5_personalized_motion_learning/scripts/high_rom_v1/run_dev_case.py --plant-mode <plant> --case <registered-case> --output <unique-output> --host-monitor-limit-s 300`. Each run was scored with `freeze_tools.py score --stage ... --id ...`. All paths, hashes, and per-case command arguments are recoverable from `PREREGISTRATION.json`, per-case JSON, and `RAW_DATA_MANIFEST.json`.
- No production fix, task/safety threshold change, model/parameter change, rerun, qualification, 30-repeat, value training, or RL. No staging, commit, push, merge, reset, stash, clean, or deletion. A learning execution contract and checkpoint were not created because 8/8 + 49/49 did not pass. The independent Auditor was not invoked under the specified conditional rule.
- Account weekly usage: 23% → 24%, same reset window (Unix 1791047434). +1 percentage point is **ACCOUNT-WIDE DELTA**, not this task's measured consumption.
- Next step: in a separately authorized development revision, diagnose the pass-through prefetch deadline/continuation behavior, then preregister a new validation matrix. Do not resume or relabel this failed matrix.
