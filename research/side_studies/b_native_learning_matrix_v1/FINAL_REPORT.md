# B-Native Learning Matrix v1 — final report

STATUS: COMPLETE_STOPPED. 4.039 h; 151/240 physical attempts; 5.668 GiB under this isolated study.

学习直接接到冻结 B 后，在本已暴露人体的科学仿真中，Q 降低完整任务力积分，独立初始化/新合法前缀复验仍成立。G 没有稳定的额外力积分收益。真实 host-clock 执行未合格，不能认为已满足 B 在线时限，未进行 pilot 或硬件。

## Scope and scientific integrity

Primary `/home/hank/coding/adaptive-traction-mpc-learning` preserved including dirty worktree/index/head. No stage/commit/push/merge/reset/stash, framework reinstall or system setting changes. `RECOVERY_AUDIT.json` records source/hash/git checks. Frozen source snapshot imports are explicitly audited; old results were not copied as fresh labels.

B chain: causal commissioning/observer → original adaptive human-waypoint MPC/local predictions → native scheduler/quintic and receipt governor → original ROM/mechanics/clearance/tracking certificates and current-model revalidation → native simulated plant and fallback. Original HOLD/phase/terminal authority remains B. See `B_BOUNDARY.json` and `SOURCE.json`.

P Predictor/full repetition performance, known_model truth provisioning, research V_base, 2×8 CEM/SearchInterface and P-specific timing screening are excluded. Import firewall and runtime call stacks record 0 P full-performance calls for all 40 formal scientific runs. Native safety lookahead remains intact.

`B_ZERO_GATE.json` and `B_ZERO_CONTEXT_REPAIR_GATE.json`: full frozen B traces match exactly, including reference/physical fields and costs (no relaxed tolerance). CPU forks restore native MuJoCo/planner/observer/sensor/history/RNG state, and parents remain hash-identical after joined children. `BRANCH_GATE.json` and per-state snapshots retain evidence.

## Frozen method and data contracts

M0 original B; M1 same six ordinary plans plus original B current-segment score S; M2 same ordinary plans plus direct remaining-cost Q; M3 three ordinary/B/carry + three G heads with same S; M4 same mixed pool with Q. S uses original cloned native decide/_evaluate, not an invented repetition force predictor. Six online candidates everywhere; offline attribution union of nine is permanently outside fitting.

Q input 120D = 55D causal commissioned B information + 3 residual history + 30 masked candidate U + 30 masked legal carry + 2 issued counts. Output N·s of remaining current repetition, actual full executed J_F minus already measured prefix. Continuation commits declared K3 suffix with unchanged native accept/reject/fallback; completed suffix returns to B. No future truth, P base or next-repetition cost. Rolling re-selection and committed labels are analyzed separately. K3 knots are spatial points inside one native request, not three independent control steps.

First collection: three physical parents, four anchors each, six distinct coherent candidates each; duplicate initial/normal states leave nine distinct 55D causal state groups. Parent and branches stay together in train/dev; nominal 58D causal states and near duplicate dev states are excluded from fitting. Adjacent states and new RNG seeds are not new Humans. See `DATASET_AUDIT.json`, weight `TRAINING.json` and `DATASET.npz`. G has only two independent training anchor states and three development anchors after exclusions; coverage is weak.

One substantive development round, then an independent initialization on exactly the same train/dev data. Both dev-selected linear Q; independent 2×128 MLP and three-head 2×128 G fits were performed, but deterministic linear refitting is not a distinct learned Q. Model selection never uses final test outcomes. Q dev RMSE 8.524 N·s; regret 0 on three informative groups (five raw groups include two zero-spread duplicates). Deployment NumPy/GPU parity passes.

## Scientific closed-loop results

Eight paired runs per method across two versions: four nominal same-trajectory/search-seed replications plus four genuinely different legal deviation prefixes. Same physical initial state, commissioned belief, task, R2 evaluator, authority, six-candidate budget and matching group seed. Complete VALID tasks alone rank J_F.

| Method | VALID | J_F mean (N·s) | Moment integral mean (N·m·s) | Duration (s) | Paired J_F reduction | Worst coordinator (ms) |
|---|---:|---:|---:|---:|---:|---:|
| M0 | 8/8 | 1439.010 | 100.496 | 19.030 | NA% | 0.0 |
| M1 | 8/8 | 1443.430 | 100.043 | 19.030 | -0.313% | 315.6 |
| M2 | 8/8 | 1335.707 | 124.568 | 19.030 | 7.177% | 307.9 |
| M3 | 8/8 | 1443.762 | 99.800 | 19.030 | -0.335% | 306.9 |
| M4 | 8/8 | 1351.440 | 119.906 | 19.030 | 6.085% | 350.3 |

Per-version results remain separate in `ANALYSIS_v1.json`, `ANALYSIS_v1_repeat.json` and the two CSVs; `COMBINED_MATRIX.json` is a descriptive pooled summary, not a significance test. M0 and interface/non-learning search are reported separately. Moment rises under Q despite force reduction; this is a force–moment tradeoff, not an unqualified coordination improvement.

M2 nominal mean paired reduction 8.379%, legal deviation 5.976%; M4 6.517% / 5.652%. See SUBGROUP_SUMMARY.json for all methods and paired ranges.

Phase duration equality does not imply equal executed common progress. Each pair records OUT/HOLD/RETURN, peak force/moment, tracking, clearance, plan changes/accept/fallback and interpolated reference/physical common and differential wave RMS/peaks. No claim of arbitrary Human, noise or hardware generalization.

## Timing and actual host-clock execution

Source-grounded interior bridge is 40 ms; evaluator activation condition is independently 55 ms, generic command expiration 100 ms. Current public hook starts after native request at boundary, before snapshot/submit; no early-precompute authority has been established. Full path includes context, proposal generation, Q/G, native validation, submission/snapshot, native worker, current-model revalidation, receipt and activation. Baseline already consumes the margin; no invented 100 ms budget or retroactive action writes.

Scientific simulations freeze physical epochs during host computation and measure quality only. Actual original WallPhysicsSession was run for all five methods and repeated for M0/M2 after a mode-metadata logger repair. Seven actual runs all invalid: original B stale-at-apply and interface methods stale-command age. Failed/truncated J_F values are unranked. New M2 decision in the corrected retest is explicitly late-discarded to carry; unchanged native safety owns final fallback/abort.

M2 mean coordinator components (ms): context 29.643, generation 0.289, native validation/S 184.961, Q 0.096, submission 0.080, total 215.354. Repeated original candidate validation dominates the tiny Q inference. LATENCY_COMPONENT_SUMMARY.json records all methods, late fractions and Q/G invocation counters.

First five physical runs also failed post-execution metadata consistency because an old qualification helper hard-coded SCIENTIFIC_SIMULATION. Only that log constant was corrected to the actual summary mode. Original FAILED results and original metadata are retained; raw trace/archive hashes unchanged; offline rescore adds zero physical attempts. Two fresh actual retests have consistent mode and still fail physics/timing. `WALL_ANALYSIS_v1.json`, `WALL_RESCORE_v1.json`, `MODE_METADATA_REPAIR.json` and raw artifacts contain the distinction.

Pilot: NOT_RUN; actual host-clock execution not qualified; scientific force reduction alone cannot authorize adaptive online pilot. No hardware runs.

## Representative committed-suffix attribution

An already-exposed successful M2 path is recreated by legal native action replay, with exact causal-context and every final trace field equality required. At OUT2 and RETURN1, preserved ordinary six plus frozen G three are committed in CPU branches, not relabeled from the rolling controller. Diagnostic outcomes are never training data or independent final-test evidence.

- OUTBOUND 2: valid 8/9; Q top1 regret 3.241 N·s; S regret 42.290; G-best gain over ordinary 3.241; chosen committed minus rolling remaining 20.646 N·s.
- RETURN 1: valid 9/9; Q top1 regret 0.000 N·s; S regret 85.757; G-best gain over ordinary -25.431; chosen committed minus rolling remaining 0.000 N·s.

## Failures, resources and recovery

All failed imports, branch exceptions, invalid full/short tasks and retries count. Advisory context geometry rejection was caught without relaxing native B; exact zero regression passed afterward. One physically complete development branch failed original science version/activation criteria and is excluded from success labels. Unsafe short outcomes are never cheap positive labels. G-negative findings did not stop Q/nonlearning/independent/timing work.

Resources: 302 45-second samples, WSL MemAvailable min 5.52 GiB, Windows commit headroom min 3.10 GiB, owned PSS max 1.47 GiB; OOM delta 0; swap 80.0→80.0 MiB. Stable nonzero swap/low Windows available did not trigger an artificial global stop. GPU fitting runs separately without physics and retains peak RSS/CUDA allocation in each TRAINING.json. One physics owner; children joined; no unknown process killed, cache drop, WSL restart or RAM/swap changes.

Compute: 151 counted attempts; actual added simulation 2757.884 s, native steps 11031534; main model API lower bound 3086496; separate native worker calls lower bound 300027. Main and native-worker counts are not added because same-process calls may overlap. Unknown calls remain explicitly listed, including original failed geometry branch. Parent-inclusive wall and child wall are not double counted. Append-only original ledger plus corrections retained.

Compressed runtime logs are losslessly verified before removal of their generated uncompressed duplicates; no historical or unique evidence deleted. FINAL_MANIFEST.json hashes all retained essential source, weights, inputs, results, raw compressed logs, traces and code histories by streaming reads. Checkpoint/resume uses completed unique IDs and original deadline/cap; final closed state does not auto-start another project.

## One next recommendation

profile and reuse native context/candidate certification to reduce end-to-end latency, retaining original control/safety and bridge; then repeat actual host-clock qualification

Completed required boundary/zero/data/model/matrix work plus independent initialization/new paired groups, actual latency and causal attribution. Early close is because meaningful authorized work is complete; unmet online qualification is preserved as a negative result. STOP.
