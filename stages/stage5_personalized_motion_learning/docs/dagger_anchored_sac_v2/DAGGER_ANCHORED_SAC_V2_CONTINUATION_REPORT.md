# DAgger-Anchored SAC Fine-Tuning v2 — authorized continuation

**STATUS: PAUSED_RESOURCE_GUARD; total collection 36,283/50,000.**

Same scientific method and training seed as v2. This is anchored SAC with explicit behavior constraints, not vanilla SAC. No DAgger/scratch retraining, failed v1 actor initialization, alternate algorithm, hardware, environment upgrade, system RAM/swap change or Git mutation.

## Resume and pending10k confirmation

Restored the original paused_exception_1791138081 state at21,283 collection steps: policy means, critics/targets, both optimizer states, active custom replay and immutable history, fixed alpha, sampler/Python/NumPy/Torch CPU/CUDA/env RNG, counters, last-good/best metadata. Component digests and 13,852-observation mean equality pass. A cold commissioned environment starts after restore; saved env RNG is assigned, but no in-flight physical rollback is claimed.

The pending10k independent best replay completed VALID, exact J_F1768.6785380664414. No new collection or actor/critic update occurred before confirmation; parent RNG is unchanged. Completed previous10k NATIVE/MATCHED/stochastic interactions were not replayed or double-counted. A new diagnostic actor construction initially consumed Torch CPU RNG; intercepted before any training update, repaired using deepcopy and explicit post-diagnostic RNG equality. Original saved state was restored again and the completed confirmation reused only after exact actor and trace hashes passed. This technical interception is not a scientific rescue. CONTINUATION_RESUME_AUDIT.json, RESUME_DIAGNOSTIC_REPAIR.json and PENDING_10K_CONFIRMATION.json preserve evidence.

## Authorized operational resource revision

Old stop criterion: new swap>128MiB alone. It previously paused at146.105MiB while WSL available2.654GiB and Windows commit headroom4.849GiB. Stable small swap is not sufficient evidence of ongoing degradation. User explicitly authorized versioned resource-only criteria; scientific/control requirements remain unchanged.

RESOURCE_POLICY_V2.json was frozen before resumed learning.45s sampling uses total process-tree PSS, main PSS, WSL available, Windows commit headroom, swap level and trend, online throughput, owner/system process counts and OOM counters. Sustained checks require3 time-separated same-lifecycle samples over>=90s. Evaluation tree working sets are not compared with training-only trees. Stable swap alone never stops.

Immediate stop: WSL available<.75GiB, Windows headroom<.75GiB, OOM counter increase or another heavy simulation. Existing allocation/process errors save state. Persistent stops include available<1.5GiB or headroom<2GiB, abnormal PSS/process growth, and sustained memory decline. Swap growth needs>=16MiB each interval and>=96MiB net plus memory/PSS deterioration;>=256MiB net sustained growth stops independently. PSS growth is compared only within the same root/evaluation/planner identities. Isolated net growth>=1GiB requires tree PSS>5.25GiB;>=512MiB with low headroom also stops. Throughput below25% historical12.906 steps/s over3 samples spanning90s stops; below50% additionally needs pressure. Exact current conditions are in RESOURCE_POLICY_V2.json. Operational versions V2.1 and V2.2 corrected restored-idle/active-physics and separate cold-worker pooling defects; all changes were frozen before further updates. Scientific thresholds were never changed.

Observed continuation resources: tree PSS peak5.363GiB (includes sole evaluation/physics child), main PSS peak2.507GiB; swap start/peak/last 7.328/12.570/12.570MiB; minimum WSL available1.887GiB and Windows commit headroom4.544GiB; median steps/s13.185743210484281; GPU device memory peak187MiB. Risk samples:3. No memory capacity expansion or cache-dropping intervention.

## Scientific contract and training settings remain frozen

R2 plant,55-D causal fixed observation scaling,2D target proposals,20ms policy period, commissioning-only model, reward, HOLD/RETURN reference handoff, phase/global timeouts, safety and all qualification requirements unchanged. Qualified student π0 remains immutable and is never an execution takeover. Teacher labels never become counterfactual RL actions; original proposals and safety execution remain separate. Historical full teacher and pure-student transitions remain immutable NATIVE data; MATCHED dynamics do not enter replay.

Actor lr1e-6, critic lr3e-4, actor every10 critic updates, gamma0.9998666755551605,tau.005, fixed alpha.001 and initial fixed log_std−10 unchanged. Exactly64 history+192 online transitions per256 batch;96 anchor states per phase. L_actor=L_SAC+λ E[sum(a_mean−π0)²]. Frozen decay schedule after20k learning points requires2 consecutive complete native checkpoints, .9 multiplier per5k and floor5,000. Any actual one-time rescue obeys previously frozen lr×.1/std×.25/λ×4 full-state restore, never resets spent interactions. Normal stochastic episode failure alone is not the deterministic capability-loss gate.

## Evaluation learning curve

Pure actor only, no teacher or normalization updates; cold independent OS processes and RNG. Every evaluation preserves all training RNG hashes. New best complete VALID results receive an extra independent replay. Same physical initial-condition protocol; deterministic repetitions are not independent training seeds or hidden-human robustness. Final capped checkpoint nominal point may exceed actual learning collection; table reports actual totals.

|Total collection|Actual learning collection|NATIVE VALID /2|MATCHED VALID /2|Stochastic VALID|Complete native J_F|OUT/HOLD/RETURN s|λ|
|---:|---:|---:|---:|---|---:|---|---:|
|11283|0|2|0|False|1950.0598136503165|9.990/9.990/9.965|10000.0|
|12283|1000|2|0|True|1948.9112198178955|10.000/9.970/9.960|10000.0|
|13283|2000|2|0|True|1907.1726931624994|9.970/9.955/9.460|10000.0|
|16283|5000|2|0|True|1950.8711130714294|9.980/9.990/9.985|10000.0|
|21283|10000|2|0|True|1768.6785380664414|9.975/6.580/9.990|10000.0|
|26283|15000|2|0|True|1949.392676472132|9.995/9.975/9.965|10000.0|
|31283|20000|2|0|True|1667.56747974847|9.950/4.740/9.970|10000.0|

![Learning curve](CONTINUATION_LEARNING_CURVE.png)

The dashed final point includes the two completed25k NATIVE replays (total36,283); its MATCHED/stochastic protocol is pending. Solid points have completed checkpoint protocols. Drift is plotted through the last fully evaluated checkpoint; per-evaluation drift evidence is retained separately.

## Confirmed best and fixed references

Best: total collection31283, nominal learning point20000, confirmed J_F1667.567480 N·s; OUT/HOLD/RETURN {'OUTBOUND': 9.95000000000523, 'HOLD': 4.740000000022633, 'RETURN': 9.970000000047605}; F peak118.698755N; M integral139.068894N·m·s, peak16.955681N·m; clearance0.007201987m. Settling/task gates:{'settled_OUTBOUND': True, 'completed_HOLD': True, 'completed_RETURN': True}; terminationCOMPLETE; safety modes{'TRACK': 4932}; rejected reference offers6; modification fraction0.004862236628849271. Full native certification and physical audits retained. MATCHED best exists:False.

|Method|Scope|VALID|J_F N·s|Duration s|F peak N|M integral/peak|Clearance m|
|---|---|---|---:|---:|---:|---|---:|
|legacy_predict_revision/baseline/frozen_student_NATIVE|NATIVE|True|1950.059814|29.945|118.534733|145.369534/16.958203|0.007228275|
|old_nominal|NATIVE|True|1237.487622|16.000|115.479119|79.039780/15.711377|0.006455440|
|fixed_hip_lead|NATIVE|True|877.722553|11.835|118.425398|74.426845/17.018579|0.006532101|
|cem_reference_transfer|NATIVE|True|1194.062007|15.420|124.364540|83.752228/18.092599|0.007407144|
|old_nominal|MATCHED|True|1438.613498|19.030|115.479119|100.417251/15.711377|0.006455226|
|fixed_hip_lead|MATCHED|True|1344.896796|19.015|118.425398|120.806727/17.018579|0.006532101|
|cem_reference_transfer|MATCHED|True|1428.142719|19.015|124.364540|107.068358/18.092599|0.007407143|
|legacy_predict_revision/checkpoint/a1_p20000_NATIVE_1|NATIVE|True|1667.567480|24.660|118.698755|139.068894/16.955681|0.007201987|

Confirmed inefficient-student improvement:14.486%. Gap above native strong fixed hip-leading:789.844927N·s. Compare only complete VALID rows in the same scope; native success is not matched success. Invalid partial force costs are unranked. Historical comparators retain same-wrapper scope and trace hashes, not new campaign replay claims.

Capability preservation, improving the inefficient student, and exceeding strong teacher are separate claim levels. Components were introduced jointly; no independent component causal contribution is established. Any HOLD time saving is recorded as duration saving, not pure coordination.

Phase decomposition versus student: {"force_integral_delta": -282.49233390184645, "phase_J_F_delta": {"OUTBOUND": -2.0054491253263222, "HOLD": -279.9229007047196, "RETURN": -0.5639840718002915}, "phase_time_delta": {"OUTBOUND": -0.040000000000190994, "HOLD": -5.250000000025068, "RETURN": 0.005000000000023874}, "phase_mean_force_baseline": {"OUTBOUND": 74.77857006278578, "HOLD": 53.328283792396846, "RETURN": 67.26265365086726}, "phase_mean_force_best": {"OUTBOUND": 74.87763475396153, "HOLD": 53.338956620814656, "RETURN": 67.17235301495434}, "interpretation": "descriptive phase costs and time-normalized force; neither duration savings nor mean-force changes isolate pure coordination causally"}

CONTINUATION_PHASE_COSTS.json also includes phase force/moment integrals and phase peaks for references. Mean phase force normalizes duration descriptively; neither this normalization nor cost improvement isolates a coordination mechanism. Original9.99s HOLD was traced to changing student target references and delayed full reference completion, not a confirmed clock bug; handoff rules remain unchanged.


Final resource-boundary pause: same process identities[56635, 59553, 59647], span93.263s, PSS growth1962.042MiB to5.362671GiB, available memory1.886604GiB; swap interval deltas[0.0, 0.0]MiB and OOM counter0. This met the frozen V2.2 growth/working-set boundary. It is a conservative operational pause, not proof of a persistent memory leak; evaluation cold-load/trace working-set growth remains a possible explanation. No further guard relaxation or simulation followed. Two earlier false-positive guard events are separately preserved in RESOURCE_LIFECYCLE_DIAGNOSIS.json and RESOURCE_PROCESS_IDENTITY_DIAGNOSIS.json.

Pending25k checkpoint: NATIVE2/2 full VALID, J_F1948.204496, OUT/HOLD/RETURN9.960/9.975/9.980s; MATCHED and stochastic evaluations are not run. No capability-loss rescue gate triggered. Cost and HOLD regressed versus the confirmed20k best; do not attribute that to lambda decay causally. Resume metadata remains last fully evaluated20k; future authorization must recover the exact36283 state and finish pending protocol before further updates. Remaining collection13,717, not a new50k budget.

## Negative evidence, updates and preservation

Any evaluated continuation checkpoint lost complete native mean capability:False. Full online failures:6/13; invalid evaluation rows:19. Stochastic success is limited evidence and can fluctuate even at low sigma. Match eligibility, F/M peaks and clearance are reported independently of J_F. All negative candidate checkpoints, traces and interrupted partial transitions are retained; no result exclusion to improve ranking.

Initial20k warm-start critic is finite but poor in return-scale agreement (held-out Qstart−9.176 versus realized discounted reward402.065; TD RMS8.060; Q-versus-realized-return RMSE446.224). Small training loss does not prove correct Q. Runtime gradient logging had a cadence mismatch; post-run fixed legal-batch gradients are supplemental evidence, not invented runtime norms. See original report and GRADIENT_SCALE_AUDIT.json plus the final offline gradient audit. Anchor/SAC opposing gradients indicate an optimization constraint; anchor was not dropped to win.

Final active-state actor/critic updates:2510/45010; rescue count0; cumulative collection36283; evaluation-only steps71043. Successful immutable history remains preserved; raw accumulated sampler counts (27-batch accounting omission retained){'history': 2878912, 'online': 8636736, 'OUTBOUND': 4418975, 'HOLD': 3914649, 'RETURN': 3182024}; exact reconstructed actual counts appear below. If a rescue restores learning counters, failed consumed interactions and logs remain; counters refer to the saved active learning state. Total original wall11.002h; continuation wall1.339h. Original start and12h deadline were not reset; original clock-gap evidence remains in the first report.

Final resumable state:`/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/checkpoints/continuation_paused_exception_1791143530` includes policy/critics/targets, both optimizer states, fixed alpha, actual custom replay, immutable-history hash, all sampler/global/env RNG, lambda/std/lr and counters/last-good/best metadata. Stable confirmed native actor:`/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/stable_actor_continuation_36283/confirmed_best_native_actor.pt`; immutable student fallback also retained. Full resume digest evidence is in CONTINUATION_FINAL_STATE_AUDIT.json. No in-flight physical rollback claimed.

Preservation PASS: 1064 protected original/v1 files and 582 pre-resume v2 physical files unchanged. Git HEAD/branch/index/cached-diff hashes unchanged. PREREGISTRATION.json, train.py and evaluate.py byte-identical. Common resource dispatch and pause checking changed under user authorization; resume orchestration and evidence tools are versioned. Original reports/logs are archived before metadata advances. No staging, commit, push or merge.


Additional best-versus-confirmed10k decomposition: {"old_10k_J_F": 1768.6785380664417, "best_J_F": 1667.5674797484699, "delta": -101.11105831797181, "phases": {"OUTBOUND": {"J_F_delta": -1.2992801799821336, "duration_delta_s": -0.02500000000011937, "old_mean_force_N": 74.82022516109181, "new_mean_force_N": 74.87763475396153, "algebraic_duration_term_Ns": -1.8712232489471017, "algebraic_mean_force_term_Ns": 0.5719430689648651}, "HOLD": {"J_F_delta": -98.04711923198113, "duration_delta_s": -1.8400000000087857, "old_mean_force_N": 53.32428170428183, "new_mean_force_N": 53.338956620814656, "algebraic_duration_term_Ns": -98.13017925955732, "algebraic_mean_force_term_Ns": 0.08306002757619138}, "RETURN": {"J_F_delta": -1.7646589060080942, "duration_delta_s": -0.020000000000095497, "old_mean_force_N": 67.2145163628723, "new_mean_force_N": 67.17235301495434, "algebraic_duration_term_Ns": -1.3438686937846833, "algebraic_mean_force_term_Ns": -0.4207902122232827}}, "interpretation": "Symmetric algebraic decomposition delta(t*f) = delta(t)*average(f) + delta(f)*average(t). Descriptive duration/mean-force terms, not isolated causal coordination contributions."}

Sampler accounting note: a prior v2 technical resume had omitted27 batches from accumulated statistics despite preserving their updates and sampler RNG. Independent index-generation replay verifies the exact saved end sampler state and reconstructs their actual phase coverage in RECOVERED_SAMPLE_ACCOUNTING.json. Active saved counters were not altered; report reconstructed history/online totals {'history': 2880640, 'online': 8641920, 'OUTBOUND': 4421550, 'HOLD': 3916915, 'RETURN': 3184095}. This is statistics recovery, not fabricated transitions or new learning.

Exact step coverage PASS: frozen collection1..11283 plus unique real archived online steps11284..36283, without gaps, duplicates or budget reset.

## Evidence paths and NEXT

- CONTINUATION_RESUME_AUDIT.json / PENDING_10K_CONFIRMATION.json / RESUME_DIAGNOSTIC_REPAIR.json: exact restore and before-update confirmation.
- RESOURCE_POLICY_REVISION.json / RESOURCE_POLICY_V2.json / RESOURCE_CONTINUATION.jsonl / CONTINUATION_RESOURCE_SUMMARY.json: old/new policy and continuous measurements.
- CONTINUATION_ALL_EVALUATIONS.json / CONTINUATION_NEGATIVES.json / CONTINUATION_ACTION_DRIFT.json / CONTINUATION_LEARNING_CURVE.csv/.png/.pdf: all complete and failed checkpoint metrics.
- CONTINUATION_PHASE_COSTS.json / UPDATES.jsonl / GRADIENT_SCALE_AUDIT.json / FINAL_TRANSITION_EVIDENCE_AUDIT.json: interaction-cost decomposition, loss and transition evidence.
- CONTINUATION_PRESERVATION.json / CONTINUATION_FINAL_STATE_AUDIT.json / CONTINUATION_ARCHIVE_MANIFEST.json: preservation and exact state hashes.

Recommendation: perform offline memory attribution of the cold evaluation/trace lifecycle before deciding whether to authorize continuation of the remaining13,717 collection steps; preserve the same50000 total and scientific contract.

STOP.
