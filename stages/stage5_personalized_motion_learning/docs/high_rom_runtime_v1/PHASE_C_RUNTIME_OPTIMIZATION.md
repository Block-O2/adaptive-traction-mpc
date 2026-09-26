# High-ROM Stage C runtime optimization

**Status: `RUNTIME_TARGET_NOT_MET`.** The same candidate completed the development regression (original low ROM 23/23, fixed-start High ROM 10/10, variable-start High ROM 16/16), but it missed the runtime benchmark's frozen p95 compute, p95 activation and control-cycle miss targets. This is offline MuJoCo development evidence, not fresh qualification, continuous safety, hardware readiness or a real-time guarantee. Stage C stops here; no RL or new qualification was run.

## Baseline, scope and frozen measurements

The confirmed High-ROM source/config and 16-case evidence were hash-checked before a local checkpoint commit, `89798cb83af7c8da20e63963495ebbc068489e20`, on `codex/full3d-cr12-high-rom-v1`. The isolated worktree is `/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-runtime-v1`, branch `codex/full3d-cr12-high-rom-runtime-v1`, created from that commit. The confirmed worktree/branch remain unchanged. The runtime candidate in this worktree is uncommitted because it did not meet the runtime gate; no push, merge, reset, stash or clean occurred.

`BENCHMARK_SPEC.json`, `BASELINE_BENCHMARK.json` and `BENCHMARK_FREEZE.json` were saved before optimization. The 8-case benchmark includes two low-ROM cases, 100/100, 110/110, 120/120 synchronous and hip-leading cases, and two 120/120 variable starts. The later 49-case regression plan was frozen before its remaining runs. The physical step is 0.25 ms, the sensor/control grid 5 ms, adaptation grid 20 ms. Waypoint planning is triggered by the causal task/request state machine, rather than an invented periodic waypoint rate. Activated plans must have sample-to-activation age **<100 ms**. The timing ledger separates acquisition, snapshot/queue, worker compute, worker-to-main scheduling, validation/command construction, and actual/effective activation. A control miss is a skipped 5 ms poll grid; missed commands are never replayed.

## Profile and changes

Profiling the original 120° OUTBOUND snapshot found 10 candidate evaluations, 31 continuous clearance certificate calls, and scheduler/geometry checks dominating worker compute. The retained historical low-ROM tail was reproduced as an exploratory development diagnostic: TASK compute 4174/1800/1047 ms, three requests expired/dropped, no stale activation. Its first candidate evaluation attempted 1854 duration trials of one conservatively rejected path. This is a certificate/search long tail, not evidence of physical collision or mechanical infeasibility. The final candidate's identical three historical snapshots produce the same full decisions within the frozen `1e-10` tolerance and take 1886/1004/645 ms. Thus the long tail remains far above 100 ms; the original failed diagnostic is retained.

Three same-semantics implementation changes were made:

1. Reuse the scheduler's saved continuous clearance lower bound for the identical unshifted schedule in `terminal_reference.py`; keep the original fallback for other evaluators.
2. Batch the same inclusive quintic sample grid in NumPy in `human_waypoint_scheduler.py`.
3. Cache the geometry-independent, read-only certificate sample powers by sample count in `rigid_table_reference.py`.

The three fixed 120° OUTBOUND/HOLD/RETURN snapshots match the original complete decision records within absolute/relative `1e-10`; the three historical-tail snapshots do too. These tested inputs support numerical equivalence, not a formal proof for every possible state. Task, physical model, 125° engineering ROM assumption, safety limits, candidate set, 100 ms rule and truth firewall were unchanged. No checks were removed, and no controller/RL algorithm candidate was introduced.

## Runtime results

| Frozen 8-case metric | Confirmed baseline | Candidate 03 | Frozen target |
| --- | ---: | ---: | ---: |
| Worker planning compute mean / p95 / max | 23.605 / 41.849 / 44.395 ms | 18.676 / 33.372 / 34.619 ms | p95 ≤30, max ≤100 ms |
| Sample-to-activation mean / p95 / max | 37.884 / 63.992 / 69.275 ms | 33.291 / 55.609 / 59.668 ms | p95 ≤55 ms |
| Control misses / 5 ms grids | 5111 / 43246 (11.82%) | 13021 / 43239 (30.11%) | ratio decreases |
| Longest consecutive control miss | 19 | 19 | report |
| Request outcomes | 139 activated; 0 dropped/stale/stale-activated | 140 activated; 0 dropped/stale/stale-activated | 0 stale activation |

For the matched 49-case corpus, worker compute mean/p95/max changed from 22.931/41.847/43.887 to **18.484/32.832/34.205 ms**; sample-to-activation from 37.669/64.126/68.873 to **32.999/54.982/60.342 ms**. All candidate requests were activated (874); dropped, stale and stale-activated counts were zero. Candidate control misses were **57,739 / 246,996 grids (23.38%)**, versus historical baseline **34,521 / 247,642 (13.94%)**. The candidate's longest consecutive miss was 25 grids in `low_hip_dominant_middle_r01`.

The control miss comparison is sensitive to host conditions: a same-session rerun of the preserved old 120° synchronous source recorded 1863 misses, versus 1962 for candidate 03, while compute p95 improved 41.63→33.23 ms. This narrows the apparent cross-day miss gap but does not establish a miss improvement. The 8-case target still fails. Snapshot/queue and validation/command construction did not dominate the worker profile; in the 8-case candidate their weighted means were about 0.83 and 6.24 ms, worker-to-main scheduling about 6.80 ms. None is included in `compute_ms` alone. The remaining miss source needs controlled host-load and main-thread diagnosis. No dependable spare compute budget for future value inference can be certified from these results, especially with the retained second-scale tail.

## Function and safety regression

The single frozen candidate completed all **49/49** registered development cases: low ROM 23/23 on the original 80°/100° plant, fixed-start High ROM 10/10, and the original variable-start High ROM 16/16 on the 125° engineering model. Each passed the registered actual arrival, continuous native valid dwell ≥0.5 s, actual RETURN to its own start, phase/global timeout, force/moment/torque, motion, clearance, ROM/contact and <100 ms activation checks. Minimum native dwell was **0.520 s**; native monitor minimum shank clearance **5.952 mm**; 5 ms sampled measured sleeve gap **4.985 mm**; native monitor maxima were **131.276 N** and **18.159 Nm**. Maximum plan age was **60.342 ms**. There were zero native shank/table contact steps, ROM violations, phase-limit violations or stale activations.

Matched TASK estimation q RMSE changed from `[0.010414°, 0.010431°]` to `[0.010658°, 0.010677°]`; the absolute increase is about 0.00024° per joint. Mean TASK force integral changed from 1010.986 to 818.058 N·s. Runtime scheduling can change a closed-loop trajectory despite fixed-snapshot decision equivalence, so this is a measured development comparison, not an isolated causal claim about interaction quality.

The initial combined scorer accidentally applied the High-ROM 120° default goal to all low-ROM cases, producing an evaluation-only 0/23 false result. That JSON was retained as `CANDIDATE03_REGRESSION_INITIAL_SCORER_ERROR.json`. The Stage-C-only summarizer passes each original low-ROM case's registered goal; the corrected 49/49 is in `CANDIDATE03_REGRESSION.json`. No rollout, case, source candidate or threshold changed for that correction. Native q/dq nodes are recorded at 0.25 ms; the physics monitor supplies cumulative per-step load/clearance extrema; measured sleeve/kinematic trace is sampled at about 5 ms. These are distinct evidence types and do not prove between-step continuous safety or hardware suitability.

The sole independent read-only Auditor matched all 49 case payload hashes and found one source/option fingerprint set, 49/49 confirmed, no truth leakage in the checked deployable path, and no stale-plan rule changes. The Auditor accepted the development function/safety regression and fixed-snapshot numerical equivalence, and rejected the runtime gate because of the benchmark p95 and control miss results. No fresh qualification was attempted.

## Budget, commands, and restart point

The actual Codex weekly account bucket (10080-minute window; reset Unix `1790917420`) was **14% used at start, 18% at closeout**, a 4-point increase, below the +5/+6/+7/+8 local thresholds and outer 45% project stop. This reading is an account percentage, not inferred from run time or tokens. In-flight worker interruption is unverified; each MuJoCo case had a 300 s host monitor and STOP check, and the regression was dispatched in batches of at most three. The 64 new dynamic executions saved under `results/high_rom_runtime_v1/` consumed **2877.184 s summed host run time**, including two retained historical-tail aborts; the 49-case final regression consumed 2196.717 s. No paid API, model upgrade or hardware action occurred.

Exact per-case commands and hashes are in each `HIGH_ROM_CASE_RESULT.json`. Reproduce one case with `scripts/high_rom_v1/run_dev_case.py --case <frozen-case.json> --output <new-empty-dir> --plant-mode high_rom|low_rom --host-monitor-limit-s 300`. Recompute timing with `runtime_benchmark.py`, function/safety scoring with `summarize_runtime_regression.py`, and matched comparison with `compare_runtime_corpus.py`, using `/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python`. Key structured outputs are `CANDIDATE03_BENCHMARK.json`, `CANDIDATE03_REGRESSION.json`, `MATCHED_49_RUNTIME.json`, `FINAL_FINGERPRINTS.json` and `STATE.json`; raw evidence is under `results/high_rom_runtime_v1/` in this worktree.

**Next step:** continue Stage C development by profiling and addressing main-thread control-cycle misses under paired host-load conditions, then repeat the frozen runtime gate before considering any joint qualification. This task stops at `RUNTIME_TARGET_NOT_MET`.
