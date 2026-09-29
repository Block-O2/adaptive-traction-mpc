# Scientific Simulation Mode implementation attempt

## Terminal status

**SCIENTIFIC_SIMULATION_VALIDATION_FAIL.** The 0/100/200/500 ms host-delay runs produced exactly equal scientific trajectories, but the unchanged scorer-v2 failed its `plan_age` condition at 100/200/500 ms. The frozen acceptance contract required scorer-v2 PASS in all four runs. No source or threshold was changed after observing that result; no qualifying checkpoint or push was made.

This is a versioned failed implementation attempt. It must not be represented as a validated scientific mode. The prior `RSS_RUNTIME_QUALIFICATION_NOT_MET` remains FAIL.

## Source and scope

- Source branch/HEAD before work: `codex/learning-wsl-migration-v1` / `1298733a1993449a7bdefe6ee1c068cae71c3056`.
- The only startup dirty state was the 13 untracked Astra audit documents. They were explicitly staged and committed as documentation checkpoint `1bfbc6d9ba451202b4e91d3354800716e7990b39`.
- Implementation branch: `codex/scientific-simulation-v1`, created from that checkpoint. Production implementation and test edits remain uncommitted. No implementation commit or remote push was made.
- Production fingerprint: `193c374b379ab8568b113672220e9e8c03a47c7455c97ac0a4a63e56567c7ffa` over 617 Stage-3/4/5 production source/script/config/asset files, including both new modules. Individual SHA256 values are in `PRODUCTION_FINGERPRINT.json`.
- The frozen ten-file integration hash at the delay-test preregistration was `70a9ea090053dde80a0411d7b27be90bed87871c72c32011648388c37bb12d34`.

## Implementation attempted

- New `execution_policy.py`: explicit mode enum and versioned scientific lifecycle. A submitted async worker is joined at the source epoch; its by-value result is rejected if the recorded simulation version changed. Realtime `PlanLifecycle` remains the default.
- New `scientific_scheduler.py`: exact native-step physical session. Host computation does not call catch-up; a committed 5 ms command is followed by 20 native 0.25 ms steps. A failed write is rolled back before physics advances.
- `runtime.py`: mode selection, scientific session/lifecycle composition, mode-tagged artifacts, simulation-age RSS/fallback checks, and scientific RETURN commit routing. Shared controller torque mathematics, planner objective, Human model, task limits, safety thresholds and scorer-v2 source were untouched.
- `activation_validation.py`: rolling-handoff age policy takes simulation age in scientific mode while recording real host age separately; original geometry, C2 and mechanics checks remain.
- `terminal_commit.py`: scientific exact-node RETURN commit uses physical source age and original physical deadlines; realtime commit remains in place.
- `run_dev_case.py`: mode and host-only delay CLI flags. Default remains `REALTIME_CHARACTERIZATION`.
- New deterministic test file covers frozen worker delay, epoch mutation rejection, exact 20-step actuation, snapshot by-value behavior, activation version records and the exact 100 ms simulated-age boundary.

The proposed full version-vector contract is **not fully proven** by this attempt. The current `state_version` combines native step and sample counts, and `reference_version` uses receipt count; a separate proof of every control-relevant mutation and staged-reference version is still required. No future leakage was observed in the by-value test, but a whole-program firewall audit was not completed.

## Tests and runs

- `py_compile` with the `mpc_learn` Python environment and `git diff --check`: PASS.
- Focused scientific, Safe Fallback and integration tests: **23 passed**. This includes the unchanged realtime lifecycle exact-100-ms tests and RSS C2/fallback tests.
- A broader old endpoint-pruning test produced **1 failure** in unchanged `human_waypoint_scheduler.py`/test code: its monkeypatched `counted_path(values,c)` does not accept the existing `task_floor_override_m` keyword. The failed test and traceback were retained; it was not repaired as part of this mode task.
- One exploratory smoke (`smoke_nominal_sync_0ms`) was COMPLETE and scorer-v2 PASS. It was excluded from the preregistered four-way comparison.
- Formal development delay runs: 0, 100, 200, 500 ms all COMPLETE. Source, case, options, numerical thread settings, comparison rule and exclusions were frozen in `HOST_DELAY_TEST_CONTRACT.json` before these four runs.
- The exploratory 0 ms smoke and formal 0 ms baseline were exactly equal in all 48 `trace.npz` arrays and all 104,180 native physics states. This is one same-host repeatability comparison, not an independent robustness result.
- Across all four formal runs, all 48 trace arrays were exactly equal, including Human true/estimated q/dq, CR12 q/dq, reference, wrench, clearance, phase and selected-waypoint labels. Native time, qpos, qvel, command torque and contact pairs were also exactly equal at all 104,180 nodes. All 20 request source/activation version and outcome sequences matched after excluding the path-valued episode identity. Physics ended at 26.045 s; OUTBOUND→HOLD, HOLD→RETURN and RETURN→COMPLETE were at 17.575, 18.595 and 26.045 s. The command receipt histogram was 5,209 receipts with 20 native steps and one terminal receipt with zero steps.
- Peak cuff force 115.4824 N, peak moment 15.7091 Nm and minimum session clearance 0.00633489 m were equal across delay runs. There were 10 `ESCAPE_ADMITTED` events and no latency-triggered fallback commit in each run.

| Injected host delay | Wall elapsed (s) | Max scorer plan age (ms) | Scorer-v2 |
| ---: | ---: | ---: | --- |
| 0 ms | 49.173 | 49.364 | PASS |
| 100 ms | 51.112 | 166.377 | FAIL: `plan_age` |
| 200 ms | 52.814 | 281.322 | FAIL: `plan_age` |
| 500 ms | 56.734 | 582.730 | FAIL: `plan_age` |

The unchanged scorer reads `summary.timing.requests[*].activation_age_ms`, which is a real host capture-to-activation interval, and requires it below 100 ms. The scientific controller path correctly records these actual host timings, so host delay alone makes scorer-v2 FAIL even with identical physical outcomes. Altering that field or scorer interpretation after seeing these results would change the frozen acceptance semantics. This is the observed acceptance conflict; it is not a controller or physics trajectory failure.

## Gates not reached

Because the delay/scorer gate failed, no additional 4–8 representative set, realtime dynamic differential case, full interruption/atomicity suite, WSL equivalence, 30-repeat, value learning or RL was run. Realtime preservation evidence is limited to focused deterministic tests and source-path inspection; it is **not** dynamic non-regression qualification. The independent whole-program truth/version audit remains open. `SCIENTIFIC_SIMULATION_MODE_VALIDATED` was not attained.

The original realtime path still uses wall-causal catch-up, >=100 ms plan lifecycle stale checks, Safe Fallback and the unchanged command-write `>100 ms` discrepancy. Historical runtime FAIL was neither deleted nor promoted. Scientific simulation here does not demonstrate hardware timing, CR12 realtime control, a safe hardware command timeout or clinical safety. `RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` remains a hard milestone.

## Provenance and Git disposition

Exact case/options SHA256, per-run file SHA256, paths, statuses and scorer conditions are in `RAW_DATA_MANIFEST.json`; exact array/native comparison is in `HOST_DELAY_COMPARISON.json`. The five raw run directories total about 991 MB under ignored `results/scientific_execution_v1/`; they remain locally intact and are not part of a Git commit. No scientific variables, controller/plant parameters, configs, cost, task/safety threshold, 125° ROM assumption or algorithmic objective were changed. The new scientific execution assumption is ideal frozen simulation time; it is not a realtime guarantee.

Git actions: allowlist staging and one documentation commit; branch creation. No production staging/commit, push, merge, reset, stash, clean or deletion. The account-wide usage tool reported **35% used** at closeout (integer precision). The WSL scientific-equivalence test is **not authorized to proceed from this failed Mac validation**.

Recommended next step: approve a new versioned scientific acceptance contract that defines how the realtime `plan_age` condition is represented for frozen simulation while retaining scorer-v2 and historical realtime evidence; only then repair and run fresh validation cases.
