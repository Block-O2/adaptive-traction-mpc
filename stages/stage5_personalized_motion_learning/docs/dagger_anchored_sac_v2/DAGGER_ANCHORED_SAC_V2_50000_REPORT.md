# DAgger-Anchored SAC Fine-Tuning v2 — 50,000-step closeout

**STATUS: COMPLETE_BUDGET_FINAL_VERIFIED. Training stopped at exactly50,000 total collection steps.**

Exact restore at36,283; remaining13,717 interactions completed once, without reset. Active updates actor/critic=3381/53727, rescue count=1. Initial frozen collection11,283 plus learning collection38,717. All failed and partial interactions remain budgeted. No further training authorized or launched.

## Resource root cause and operational repair

A+C: trace-to-JSON temporary copies with idle parent; streaming repair and complete child release verified; no persistent leak observed

Historical trigger: same group over93s, tree PSS+1.92GiB to5.36GiB; parent stable2.31GiB, evaluator final-interval growth1.55GiB, swap stable, no OOM. Original serializer recursively copied the entire payload and created a full indented JSON string, three calls around finalization. New version streams the identical payload fields/conversions with bounded256KiB buffering. No physics, timing, reward or learning code changed. Parent joins training physics before evaluation; cold evaluator and planner are reaped before the next owner. Field/value parity fixture passes; actual archive PSS and child-release evidence retained. This supports temporary allocation, not proof about all possible leaks.

Before-action harness defect: missing multiprocessing __main__ guard caused one reset-time child failure. Added guard, preserved failed directory and logs, no new collection or update, no rescue. See SPAWN_GUARD_REPAIR_36283.json. All earlier false guard events and36,283 pause remain in archived reports.

V3 resource policy: isolated PSS peak or quiet-mode throughput loss alone never stops. Same-phase persistent low memory, sustained swap/available deterioration, training PSS growth with pressure, OOM/allocation errors or process instability save state and stop. WSL/Windows system configuration unchanged. Original start/deadline preserved as historical; this new user-authorized continuation has a separate12h operational cutoff, without resetting consumed collection or original wall accounting.

Resources: {"samples": 187, "tree_PSS_peak_GiB": 4.106245040893555, "main_PSS_peak_GiB": 2.4105825424194336, "min_available_GiB": 3.1331138610839844, "min_commit_headroom_GiB": 4.5191802978515625, "swap_start_MiB": 16.59375, "swap_peak_MiB": 16.59375, "swap_last_MiB": 16.59375, "OOM_counter_increased": false, "risk_rows": [], "steps_per_s_median": 11.624265003793916, "steps_per_s_range": [10.109586922098526, 15.158539460879146], "GPU_peak_MiB": 185.0, "child_release_count": 43, "all_recorded_children_reaped": true, "stream_archive_passes": 132, "policy": {"version": "RESOURCE_POLICY_V3_STREAMING_LIFECYCLE_36283", "scope": "operational resource stop criterion only", "scientific_changes": [], "system_configuration_changes": [], "old_policy": "new swap >128 MiB alone stops; MemAvailable<1.5GiB and commit headroom<2GiB also stop", "reason": "User authorized diagnosis and minimal logging/lifecycle repair: end-of-evaluation full JSON conversion/string allocation coexisted with the idle training parent. Stream identical payload fields, join/reap sole physics child, and use sustained pressure rather than a PSS peak.", "sample_interval_s": 45, "trend_min_samples": 3, "trend_min_span_s": 90, "same_lifecycle_only": true, "stable_swap_level_alone_never_stops": true, "immediate": {"WSL_available_below_GiB": 0.75, "Windows_commit_headroom_below_GiB": 0.75, "oom_kill_counter_increase": true, "allocation_warning_or_process_error": "existing exception handler preserves complete state", "other_heavy_simulation": true}, "persistent": {"low_WSL_available_GiB": 1.5, "low_commit_headroom_GiB": 2.0, "process_tree_PSS_GiB": 6.0, "owned_process_count_over": 12, "system_count_growth_over": 100}, "trends": {"swap_per_interval_min_MiB": 16, "swap_net_min_MiB": 96, "rapid_swap_net_min_MiB": 256, "available_per_interval_decline_min_MiB": 64, "available_net_decline_min_MiB": 256, "PSS_net_abnormal_growth_MiB": 1024, "PSS_growth_with_low_memory_MiB": 512}, "throughput": {"reference_steps_per_s": 12.906312346315916, "warning_fraction": 0.5, "severe_fraction": 0.25, "requires_three_online_progress_samples_over_90s": true, "warning_needs_swap_or_memory_pressure": true}, "stop_action": "set append-only evidence and pause-request flag; policy boundary saves full state. Already-running independent evaluation finishes evidence before next dispatch. No resource expansion, cache dropping, budget reset or new algorithm.", "prior_wall_deadline_unchanged": false, "lifecycle_definition": "EVALUATION when evaluate.py child exists; TRAINING_ACTIVE only when multiprocessing spawn physics/planner child exists; otherwise RESTORED_IDLE. Do not compare initial physical allocation with restored-idle working sets.", "implementation_correction": "v2.1 compared different cold evaluation process identities. At26283 swap remained7.328MiB and available2.671GiB while tree4.584GiB was within measured normal cold evaluation workload. PSS-only abnormal growth now requires the same root/worker identities and exceeding5.25GiB, or concurrent low headroom for the existing512MiB rule. Global low-memory, OOM, swap-growth and throughput rules unchanged. All spent interactions and saved states preserved.", "PSS_same_process_identity_required": true, "PSS_isolated_growth_requires_tree_above_GiB": 5.25, "normal_measured_evaluation_tree_GiB": 4.584, "isolated_PSS_peak_never_stops": true, "throughput_only_never_stops": true, "operational_phase_markers": true, "continued_training_gate": "No OOM/allocation error; no sustained swap growth/available decline; no sustained same-training working-set growth; evaluation children released before subsequent physics. Cold evaluation phases and archive allocation are separate. Quiet-mode rate alone is not a stop.", "steady_training_PSS_min_samples": 5, "steady_training_PSS_min_span_s": 180, "steady_training_PSS_growth_MiB": 512, "steady_training_PSS_requires_pressure": true, "wall_authorization": "New explicit user instruction resumes the previously stopped campaign from36283 to50000, including final replays. Original start/deadline preserved; separate operational continuation deadline recorded, no scientific config or spent collection change."}}

## Frozen scientific contract and restoration

PREREGISTRATION.json SHA256=c5a41a4d6a481458c5f299b318c5226a278d2d733c0ca1eadac3cf2fe09c6a2c. train.py and evaluate.py byte-identical. R2 plant,55-D fixed normalization,2D tanh proposals,20ms timing, commissioned frozen Human, reward, safety/phase/global gates, MATCHED eligibility unchanged. Actor lr1e-6; critic lr3e-4; actor each10critic; alpha.001; fixed log_std−10; gamma.9998666755551605; tau.005; replay64legal history+192online; anchors96states/phase; unchanged preregistered lambda decay. Immutable pi0 and teacher are never execution takeovers. Labels are never reward/next-state RL transitions.

RESUME_36283_AUDIT.json confirms means onall13,852 frozen observations, networks/targets/optimizers/alpha, replay/history, global/sampler/env RNG, counters/best/lastgood. Existing25k NATIVE replays were reused only after actor and trace hashes matched; pendingMATCHED/stochastic completed before further updates. All cold evaluations check unchanged parent RNG. Cold environment reset is explicit; no in-flight physical rollback is claimed.

## Full checkpoint curve

|Total collection|Learning collection|NATIVE VALID /2|MATCHED VALID /2|Stochastic VALID|Native valid J_F|OUT/HOLD/RETURN s|lambda|
|---:|---:|---:|---:|---|---:|---|---:|
|11283|0|2|0|False|1950.0598136503165|9.990/9.990/9.965|10000.0|
|12283|1000|2|0|True|1948.9112198178955|10.000/9.970/9.960|10000.0|
|13283|2000|2|0|True|1907.1726931624994|9.970/9.955/9.460|10000.0|
|16283|5000|2|0|True|1950.8711130714294|9.980/9.990/9.985|10000.0|
|21283|10000|2|0|True|1768.6785380664414|9.975/6.580/9.990|10000.0|
|26283|15000|2|0|True|1949.392676472132|9.995/9.975/9.965|10000.0|
|31283|20000|2|0|True|1667.56747974847|9.950/4.740/9.970|10000.0|
|36283|25000|2|0|True|1948.2044955937586|9.960/9.975/9.980|9000.0|
|41283|30000|0|0|True|None|9.965/10.000/0.000|8100.000000000001|
|46283|35000|2|0|True|1879.9150755448777|9.980/8.700/9.960|36000.0|
|50000|38717|2|0|False|1802.6562657019704|9.990/7.200/9.990|36000.0|

![Learning curve](LEARNING_CURVE_50000.png)

## Final cold replays and same-scope comparators

Each student/best/final mean actor receives2NATIVE and2MATCHED cold replays. Each learner also has1NATIVE stochastic replay. Fixed references are prospectively replayed once per scope using their unchanged existing implementation; no new CEM search. Only complete VALID rows may be ranked within the same scope. MATCHED invalid force costs remain evidence, not eligible scores. Deterministic repetitions are not independent training seeds.

|Strategy|Scope|Stochastic|VALID|J_F N s (eligible only)|Physical recorded J_F|OUT/HOLD/RETURN s|F peak N|M integral/peak|Clearance m|
|---|---|---|---|---:|---:|---|---:|---|---:|
|frozen_DAgger_student|NATIVE|False|True|1950.059814|1950.059814|9.990/9.990/9.965|118.534733|145.369534/16.958203|0.007228275|
|frozen_DAgger_student|NATIVE|False|True|1950.059814|1950.059814|9.990/9.990/9.965|118.534733|145.369534/16.958203|0.007228275|
|frozen_DAgger_student|MATCHED|False|False|UNRANKED|1950.059814|9.990/9.990/9.965|118.534733|145.369534/16.958203|0.007228275|
|frozen_DAgger_student|MATCHED|False|False|UNRANKED|1950.059814|9.990/9.990/9.965|118.534733|145.369534/16.958203|0.007228275|
|confirmed_best|NATIVE|False|True|1667.567480|1667.567480|9.950/4.740/9.970|118.698755|139.068894/16.955681|0.007201987|
|confirmed_best|NATIVE|False|True|1667.567480|1667.567480|9.950/4.740/9.970|118.698755|139.068894/16.955681|0.007201987|
|confirmed_best|MATCHED|False|False|UNRANKED|1667.567480|9.950/4.740/9.970|118.698755|139.068894/16.955681|0.007201987|
|confirmed_best|MATCHED|False|False|UNRANKED|1667.567480|9.950/4.740/9.970|118.698755|139.068894/16.955681|0.007201987|
|confirmed_best|NATIVE|True|True|1883.019276|1883.019276|9.995/8.720/9.975|118.692531|144.007299/16.955637|0.007131727|
|final_50000|NATIVE|False|True|1802.656266|1802.656266|9.990/7.200/9.990|118.687281|142.348098/16.957610|0.007231915|
|final_50000|NATIVE|False|True|1802.656266|1802.656266|9.990/7.200/9.990|118.687281|142.348098/16.957610|0.007231915|
|final_50000|MATCHED|False|False|UNRANKED|1802.656266|9.990/7.200/9.990|118.687281|142.348098/16.957610|0.007231915|
|final_50000|MATCHED|False|False|UNRANKED|1802.656266|9.990/7.200/9.990|118.687281|142.348098/16.957610|0.007231915|
|final_50000|NATIVE|True|True|1860.281737|1860.281737|9.955/8.320/9.985|118.718692|143.580606/16.957592|0.007285424|
|intermediate_a1_p10000|NATIVE|False|True|1768.678538|1768.678538|9.975/6.580/9.990|118.666303|141.571229/16.957116|0.007192802|
|intermediate_a1_p10000|NATIVE|False|True|1768.678538|1768.678538|9.975/6.580/9.990|118.666303|141.571229/16.957116|0.007192802|
|intermediate_a1_p10000|MATCHED|False|False|UNRANKED|1768.678538|9.975/6.580/9.990|118.666303|141.571229/16.957116|0.007192802|
|intermediate_a1_p10000|MATCHED|False|False|UNRANKED|1768.678538|9.975/6.580/9.990|118.666303|141.571229/16.957116|0.007192802|
|intermediate_a1_p10000|NATIVE|True|True|1950.837186|1950.837186|10.000/9.995/9.970|118.503393|145.514829/16.957236|0.007156298|
|original_controller|NATIVE|False|True|1237.487622|1237.487622|7.525/1.020/7.455|115.479119|79.039780/15.711377|0.006455440|
|original_controller|MATCHED|False|True|1438.613498|1438.613498|9.005/1.020/9.005|115.479119|100.417251/15.711377|0.006455226|
|CEM|NATIVE|False|True|1194.062007|1194.062007|7.420/0.655/7.345|124.364540|83.752228/18.092599|0.007407144|
|CEM|MATCHED|False|True|1428.142719|1428.142719|9.005/1.005/9.005|124.364540|107.068358/18.092599|0.007407143|
|fixed_hip_leading|NATIVE|False|True|877.722553|877.722553|5.430/0.700/5.705|118.425398|74.426845/17.018579|0.006532101|
|fixed_hip_leading|MATCHED|False|True|1344.896796|1344.896796|9.005/1.005/9.005|118.425398|120.806727/17.018579|0.006532101|

Confirmed best total31283, learning point20000: J_F1667.567480; improvement over inefficient student14.486%; gap above native fixed hip-leading789.844927. Capability preservation, improving student and surpassing strong references are separate levels. Native success never implies matched eligibility.

Clearance in the table is the online/session estimate. The separately audited true physical clearance for the best is 0.012303915821362529 m; see ALL_EVALUATIONS_50000.json. The additional 10k intermediate actor was replayed because it is better than the 50k final actor.

## Duration and interaction cost attribution

Best versus student: {"total_J_F_delta": -282.49233390184645, "phases": {"OUTBOUND": {"duration_delta_s": -0.040000000000190994, "phase_J_F_delta": -2.0054491253263222, "old_mean_force_N": 74.77857006278578, "new_mean_force_N": 74.87763475396153, "algebraic_duration_term_Ns": -2.993124096349238, "algebraic_mean_force_term_Ns": 0.9876749710228061}, "HOLD": {"duration_delta_s": -5.250000000025068, "phase_J_F_delta": -279.9229007047196, "old_mean_force_N": 53.328283792396846, "new_mean_force_N": 53.338956620814656, "algebraic_duration_term_Ns": -280.0015060860172, "algebraic_mean_force_term_Ns": 0.07860538129754867}, "RETURN": {"duration_delta_s": 0.005000000000023874, "phase_J_F_delta": -0.5639840718002915, "old_mean_force_N": 67.26265365086726, "new_mean_force_N": 67.17235301495434, "algebraic_duration_term_Ns": 0.3360875166661588, "algebraic_mean_force_term_Ns": -0.9000715884663779}}, "duration_term_Ns": -282.6585426657002, "mean_force_term_Ns": 0.16620876385397687, "interpretation": "Symmetric algebraic duration/phase-mean-force decomposition; descriptive, not independent causal coordination attribution"}

Best versus confirmed10k: {"total_J_F_delta": -101.11105831797181, "phases": {"OUTBOUND": {"duration_delta_s": -0.02500000000011937, "phase_J_F_delta": -1.2992801799821336, "old_mean_force_N": 74.82022516109181, "new_mean_force_N": 74.87763475396153, "algebraic_duration_term_Ns": -1.8712232489471017, "algebraic_mean_force_term_Ns": 0.5719430689648651}, "HOLD": {"duration_delta_s": -1.8400000000087857, "phase_J_F_delta": -98.04711923198113, "old_mean_force_N": 53.32428170428183, "new_mean_force_N": 53.338956620814656, "algebraic_duration_term_Ns": -98.13017925955732, "algebraic_mean_force_term_Ns": 0.08306002757619138}, "RETURN": {"duration_delta_s": -0.020000000000095497, "phase_J_F_delta": -1.7646589060080942, "old_mean_force_N": 67.2145163628723, "new_mean_force_N": 67.17235301495434, "algebraic_duration_term_Ns": -1.3438686937846833, "algebraic_mean_force_term_Ns": -0.4207902122232827}}, "duration_term_Ns": -101.34527120228911, "mean_force_term_Ns": 0.23421288431777376, "interpretation": "Symmetric algebraic duration/phase-mean-force decomposition; descriptive, not independent causal coordination attribution"}

PHASE_COSTS_50000.json provides phase force/moment integrals and peaks. Duration and mean-force algebraic terms are descriptive; no independent causal contribution or pure coordination gain is claimed. Original9.99s HOLD diagnosis remains student/reference completion inefficiency, not a confirmed timer bug; no HOLD crop, extra wait or changed handoff rule.

Best versus student: force cost decreases by 282.492 N s. The symmetric descriptive duration term is -282.659 N s and phase-mean-force term 0.166 N s. HOLD accounts for -279.923 N s of the change. OUTBOUND and RETURN remain near their original durations; this is predominantly a duration saving, not demonstrated pure coordination improvement.

At 50k, the final actor has J_F=1802.656, HOLD=7.200s. Rescue35k to final improves cost, but the 20k best (HOLD4.740s) remains unbeaten; these sparse checkpoints cannot establish a plateau. The protocol's final stochastic evaluation failed RETURN; the additional final cold stochastic replay succeeded. Both are retained, so low noise is not a demonstrated safety or task-success guarantee.

## Negative results and limits

Native major-checkpoint ability preserved=False. Learning curve is evaluated at a few deterministic checkpoints and may regress; this does not prove every online stochastic episode succeeds. Final-actor result and best result are reported separately, with all intermediate failures retained. Initial critic return-scale agreement was poor (Qstart−9.176 vs realized discounted402.065; TD RMS8.060; Q/MC RMSE446.224). Loss alone does not prove Q reliability. Runtime gradient cadence mismatch is preserved; offline gradients are supplementary, not fabricated runtime logs. One training seed, no hidden setup robustness claim, no independent component causal attribution.

Sampling accounting: {"raw_saved": {"history": 3756800, "online": 11270400, "OUTBOUND": 5824531, "HOLD": 5095181, "RETURN": 4107488}, "reconstructed_actual": {"history": 3758528, "online": 11275584, "OUTBOUND": 5827106, "HOLD": 5097447, "RETURN": 4109559}, "known27batchoffset": true}. This recovers statistics only; sampler RNG, transitions and saved learning state are unchanged.

Final complete resumable state: `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/checkpoints/final_attempt_state`. Includes actor/critics/targets/optimizers/alpha/replay/history references/global/sampler/env RNG/counters/lambda/std/lastgood/best. Confirmed best, final actor and frozen student fallback in `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/stable_actor_50000`. Protected original/v1 and pre36,283 physical files pass hashes. Git branch/HEAD/index/cached diff unchanged; no staging/commit/push/merge/reset/deletion of evidence.

Wall time: newly authorized continuation2.363h; original-start cumulative13.803h (includes historical gaps). Steps/s measures active collection, not total campaign or final evaluation throughput.


## Capability failure and original rescue accounting

Rescue records: [{"unix": 1791148001.3049955, "restored": "/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/checkpoints/candidate_attempt_1_point_025000_budget_036283", "global_budget_not_rolled_back": 41283, "restored_replay_steps": 36283, "restored_updates": 45010, "actor_lr": 1e-07, "std": -11.38629436111989, "anchor_lambda": 36000.0, "fixed_alpha": 0.001, "environment": "new cold commissioned episode; persisted RNG restored after construction; no in-flight physics rollback"}]

Effective terminal learning settings: {"actor_lr": 1e-07, "log_std": -11.38629436111989, "alpha": 0.001, "anchor_lambda": 36000.0, "decay_enabled": false}. These are the original predeclared rescue multipliers, not a new tuning decision; no decay on rescue. The default frozen settings paragraph describes the first branch.

Active-state actor/critic updates3381/53727; gross executed updates including the retained failed branch3881/58727. Failed consumed interactions and updates are not erased by last-good restore. Task ability was NOT preserved throughout; final cold replay qualification is distinct from first-branch loss. Invalid partial costs are never promoted.
## Evidence and NEXT

- RESOURCE_ROOT_CAUSE_36283.json, RESOURCE_POLICY_V2.json, LIFECYCLE_36283.jsonl, RESOURCE_SUMMARY_50000.json: PID allocation/lifetime/release and policy evidence.
- RESUME_36283_AUDIT.json, FULL_STATE_AUDIT_50000.json, EXACT_BUDGET_AUDIT_50000.json, SAMPLE_COVERAGE_50000.json, FINAL_TRANSITION_EVIDENCE_AUDIT.json: exact state, budget and legal transitions.
- ALL_EVALUATIONS_50000.json, FINAL_VERIFICATION_50000.json, ACTION_DRIFT_50000.json, PHASE_COSTS_50000.json, LEARNING_CURVE_50000.csv/.png/.pdf: complete and negative results.
- PRESERVATION_50000.json, ARCHIVE_MANIFEST_50000.json: source/evidence/Git integrity.

Recommendation: preregister one next study assessing stochastic robustness of the confirmed best under the unchanged task; do not automatically extend training beyond50,000.

STOP.
