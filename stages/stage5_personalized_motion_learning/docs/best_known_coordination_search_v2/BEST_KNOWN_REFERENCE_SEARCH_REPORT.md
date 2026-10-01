# Best-Known Coordination Reference Search v2

Finite-budget teacher generation complete. No RL or value model was trained. Original source, controller, Human dynamics, safety thresholds, planner objective and Scientific Mode remain fingerprint-identical.

|Condition|Arm|Baseline J_F|Best-known J_F|Benefit N·s|Benefit %|Gain over prior|Fixed-best gap|
|---|---|---:|---:|---:|---:|---:|---:|
|low_ordinary_early|MATCHED|599.082773|598.414598|0.668175|0.112|0.000000|0.6681750449918127|
|low_ordinary_early|NATIVE|501.521818|497.020323|4.501495|0.898|2.046778|4.501495014092825|
|balanced_high|MATCHED|1207.127793|1179.976442|27.151351|2.249|4.439510|27.151351491739888|
|balanced_high|NATIVE|942.010655|936.677211|5.333444|0.566|0.000000|5.333444456332359|
|variable_start_120|MATCHED|1521.938394|1473.621009|48.317385|3.175|0.168818|48.31738460399356|
|variable_start_120|NATIVE|1231.651956|1172.543336|59.108620|4.799|4.031168|59.108619591794195|
|sync_120|MATCHED|1529.600078|1465.626365|63.973714|4.182|2.794893|63.973713753769516|
|sync_120|NATIVE|1236.980854|1165.753400|71.227454|5.758|14.246618|71.22745352930838|
|hip_ordinary|MATCHED|766.820951|761.440631|5.380319|0.702|0.000000|5.380319302158455|
|hip_ordinary|NATIVE|631.130200|618.076149|13.054052|2.068|0.000000|13.054051832715459|

Recorded 621 attempted rollouts: {'VALID': 539, 'INTERRUPTED': 1, 'INFEASIBLE': 80, 'INVALID': 1}. Planned Phase A 60, CEM Phase B 540, confirmation/fixed comparison 20; separately preserved interrupted attempt and replacement are identified in the recovery log. Signed hip/knee, width/catch-up, per-phase offsets and smooth control coefficients have nominal dimensions 6/12/20. MATCHED independent dimensions are 4/10/18 because hip-lead and knee-lag are tied to preserve common progress; NATIVE dimensions remain 6/12/20. Each of three initializations has two generations of three candidates. This sparse finite envelope does not establish convergence.

Wall time 5.126 h; mean rollout 56.269 s, median 57.136 s; two concurrent simulations. Runtime includes offline search, not online latency optimization.

## Direct answers

1. Absolute best-known J_F is condition/arm specific; use the table. Comparing minima across different tasks is not meaningful.
2. Baseline improvements and percentages are in the table; MATCHED and NATIVE have separate baselines.
3. Additional Phase B budget improved 6 of 10 condition-arm rows relative to the prior+Phase-A incumbent. This is observed headroom, not an extrapolated limit.
4. Independent L2/L3 minima improve over L1 in 5 of 10 rows; inspect per-level sample counts and restart spread. Extra dimensions with no improvement do not prove the family exhausted.
5. No universal optimum is established. The exact common fixed descriptor, coverage and condition-specific gaps are in FIXED_PATTERN_SELECTION.json and FIXED_VS_SEARCH_BASELINE.md.
6. Condition-specific best parameters and feasibility differ; this supports condition-conditioned teacher targets, but it does not establish that a learned personalized policy beats a prospective fixed comparator.
7. The historical 40.627960 N·s is an improvement in sync_120 matched scheduling. Current sync/variable isolated improvements are [('variable_start_120', 48.31738460399356), ('sync_120', 63.973713753769516)]. There is no certified lower bound, so its distance to a search/global limit cannot be quantified. Budget/freedom gains and initialization disagreement mean saturation cannot be claimed.
8. Learn a low-dimensional coordination/chunk parameter action with phase, remaining progress and explicit pacing context, through the existing safety scheduler. A single next waypoint cannot describe lead duration/catch-up and OUTBOUND/RETURN asymmetry.
9. Larger RL complexity is not justified by this teacher search alone. First test fixed versus condition-indexed lookup and a simple supervised value/ranking learner on fresh supported starts; no learner is trained here.

## Learning readiness

State: deployable q/dq estimate and receipt-owned reference; phase/progress, start/goal/remaining ROM, previous declared chunk, estimated Human dynamics/geometry belief and confidence/residual/sample history, causal adaptation state, scheduler/governor and pacing context. Frozen physical condition ids and simulation Human truth are reproduction metadata, not deployable features.
Action: signed hip lead/knee lag, lead peak/width, phase offsets and optional smooth basis coefficients. Target: full remaining-task absolute J_F conditioned on declared continuation and timing; paired delta J against same-state/same-arm baseline is useful for ranking. Keep moment/clearance/intensity as separate constrained diagnostics, not a mixed reward. Full-task outcome cannot be replaced by first-waypoint force.

## Limits and evidence

All five conditions were previously used and are in-sample teacher-generation conditions, not fresh held-out patients. low_ordinary_early is an adaptation checkpoint of one session. Deterministic baseline/replay/confirmation is reproducibility, not independent subjects. MATCHED requires same segment count, each phase residual<=25ms, and declared target common-progress residual<=1e-9; valid pacing/common-progress-confounded outcomes remain in raw results and are excluded from isolated ranking. NATIVE effects may include timing. Initializations with infeasible candidates are retained.
Database entries may retain a stronger historical VALID reference. Such entries are separately sourced and never represented as a new v2 CEM discovery. Prior all-valid timing-confounded matched minima are preserved in CONDITION_COMPARISON.json, separate from isolated references.
CEM design context: [Pinneri et al., 2021](https://proceedings.mlr.press/v155/pinneri21a.html); smoothed diagonal CEM/elite memory used here, not a full iCEM implementation or a convergence guarantee.
RAW_DATA_MANIFEST.json records stored and original content hashes; raw JSON is losslessly compressed. Database manifest_hash is the campaign raw-manifest digest; rollout_result_sha256 identifies each result header. SEARCH_CONVERGENCE.csv includes new-only and prior-incumbent envelopes. Source fingerprints and contract fix all production/config/scientific semantics.

Additional audit: L2/L3 restarts share earlier best samples, so agreement of restart minima is correlated and is not independent convergence evidence. New levels are nested within v2; different historical smooth-basis families may not have an exact v2 parameter embedding. Legacy teacher chunks retain their nominal target descriptor and mapping status. Each new level has only 18 attempted evaluations per condition/arm.

Frozen-start teacher generation does not resolve the earlier value-learning native cross-repetition continuity blocker. Prospective learning should first validate continuation/state features and the fixed-versus-lookup comparator. No learner was run here.

The fixed-pattern comparator was selected by previously observed cross-condition coverage, then mean fractional benefit. Only descriptors evaluated across the represented conditions compete at full coverage; this is not an exhaustive optimization of all universal fixed patterns. No fixed-policy insufficiency or personalization necessity is proved.

The normalized beta-shaped offsets are continuous, endpoint-zero and smooth in the interior. General peak/width exponents do not guarantee C1 behavior at the normalized endpoints. Executed references are emitted through the unchanged quintic scheduler and its physical feasibility checks; reference and Human acceleration/jerk diagnostics concern that executed motion. No global derivative bound is claimed for the analytic offset shape.

Database J_F labels belong to the frozen task-start context and declared full-task continuation. They cannot be copied as remaining-cost labels for arbitrary intermediate states. A future remaining-value dataset needs supported state snapshots and continuation-conditioned rollouts; rejected/truncated candidates keep feasibility labels rather than being ranked by their partial force integral.

## Observed metric and fixed-comparator qualifications

The coverage-first universal fixed descriptor selected in both arms is neutral (all offsets zero), and its final costs reproduce the corresponding original baselines. The preregistered hip-leading descriptor remains a separate, often stronger comparator: its low-ROM MATCHED outbound timing residual is 30ms, exceeding the frozen 25ms guard, so it has only four-condition isolated coverage. These coverage restrictions do not prove neutral is the best possible universal policy. In sync_120 MATCHED, the preregistered fixed cost is 1488.972118 N s versus best-known 1465.626365 N s, a remaining gap of 23.345754 N s.

L2/L3 improve over the independently sampled L1 minimum in 1/5 MATCHED rows (variable-start, 1.501381 N s) and 4/5 NATIVE rows. L3 adds an improvement over L2 only for sync_120 NATIVE (25.736406 N s). Sparse samples, correlated incumbent reuse and distinct historical basis families prevent any dimensional saturation claim.

Every selected J_F-minimizing reference has a higher moment integral than its own baseline; this is a secondary-metric tradeoff, not an overall interaction improvement. Some NATIVE peak forces also increase while satisfying the original acceptance checks. Variable-start and sync_120 NATIVE shorten total task duration by 0.550s and 0.805s respectively, each including a 0.510s decrease in other task-phase duration. Their J_F gains therefore include pacing/hold effects. All selected MATCHED other-phase duration residuals are numerically zero; measured outbound/return residuals are at most 10ms. Small J_F differences should still be read with the fixed 5ms sampling and matched timing tolerance. Full numeric diagnostics are in REFERENCE_PACING_AND_METRIC_AUDIT.json.
