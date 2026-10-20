# DAgger-to-SAC Expert Pipeline v1

STATUS: SAC_ABILITY_LOST

User-authorized autonomous nominal Human simulation campaign. No new Human holdout: repeated deterministic rollouts demonstrate reproducibility on the exposed nominal case, not statistical robustness.

Starting branch: codex/action-representation-switch-audit-v1; campaign branch: codex/dagger-to-sac-expert-v1; HEAD: 41cdddef117caa4b191a52129c4ff83e481fd5a8.

## Expert

The expert query accepts only the normalized 55-D causal observation. It reuses hip-leading knee-preview intent and the current robust terminal reference, with release keyed to estimated/current-reference hip posture rather than the archived 1.5-second trajectory clock. Thresholds were calibrated once from archived deployable teacher posture before the gate. No simulator, original trajectory index, future observation/force or hidden Human truth enters the query.

|Continuation|Prefix steps|First certified status|Full independent VALID|J_F (N s)|Duration (s)|
|---|---:|---|---|---:|---:|
|nominal|0|ACCEPTED|True|877.722563|11.835|
|bc_20261004_prefix_75|75|ACCEPTED|True|869.640428|11.835|
|bc_20261005_prefix_150|150|ACCEPTED|True|872.896149|11.835|
|bc_20261006_prefix_300|300|ACCEPTED|True|928.284700|12.545|

BC prefixes reproduce archived observations exactly with their actual student actions; the expert then continues that live physics owner. No reset to teacher is used. At the late prefix, the 2-second continuation has already entered RETURN, so outbound progress decreases appropriately; full VALID confirms recovery.

## DAgger

Native SB3 deterministic actor, 55→256→256→2, fresh initialization. Initial full VALID teacher data; all visited collection observations receive causal expert labels. Beta is fixed at .5/.25/.1/0/0/0/0/0. Adam, learning rate .0003, 18000 initial and per-round updates, batches of 96 per phase (288 total). Fixed final-update weights; no validation-gate stop or result-conditioned hyperparameter changes. Failed/difficult states are kept. Per-transition archives include label, actual raw action, realized action, phase, round, terminal outcome and stated mixture. Episode outcomes under a mixture are not per-state expert counterfactual recovery results.

|Round|Beta|Dataset states|Collection VALID|Pure student VALID|Consecutive 3/3 rounds|
|---:|---:|---:|---:|---:|---:|
|1|0.5|2900|0/3|0/3|0|
|2|0.25|5865|0/3|0/3|0|
|3|0.1|9358|1/3|3/3|1|
|4|0|13852|3/3|3/3|2|

First pure-student VALID round: 3. Final student metrics (unranked when INVALID): `{"valid": true, "J_F": 1950.0598136503165, "force_peak": 118.53473316262449, "moment_integral": 145.36953443643867, "moment_peak": 16.95820312030705, "duration_s": 29.945000000100706, "clearance": 0.007228274556562411, "gates": {"settled_OUTBOUND": true, "completed_HOLD": true, "RETURN_entered": true, "completed_RETURN": true, "independent_VALID": true}}`.

## SAC

Started: True; online steps: 20000.
SAC is eligible only after two consecutive 3/3 pure-student rounds. Actor mean identity, fresh critics/target critics/optimizers, actual executed transition replay semantics, no uniform random warmup, fixed demo/online ratio and every-10k capability preservation checks are specified in PREREGISTRATION.json. Formal SAC runtime evidence exists only if SAC was actually entered.

## VALID-only comparators

|Method|Scope|VALID|J_F (N s)|Duration (s)|Evidence|
|---|---|---|---:|---:|---|
|old_nominal|NATIVE|True|1237.487622|16.000|frozen historical same-wrapper R2, not a new replay this campaign|
|fixed_hip_lead|NATIVE|True|877.722553|11.835|frozen historical same-wrapper R2, not a new replay this campaign|
|cem_reference_transfer|NATIVE|True|1194.062007|15.420|frozen historical same-wrapper R2, not a new replay this campaign|
|old_nominal|MATCHED|True|1438.613498|19.030|frozen historical same-wrapper R2, not a new replay this campaign|
|fixed_hip_lead|MATCHED|True|1344.896796|19.015|frozen historical same-wrapper R2, not a new replay this campaign|
|cem_reference_transfer|MATCHED|True|1428.142719|19.015|frozen historical same-wrapper R2, not a new replay this campaign|
|DAgger_student|NATIVE|True|1950.059814|29.945|current pure-student qualification|

Historical comparator traces/hashes and source labels remain distinct from new replays. NATIVE and MATCHED rankings are separate; INVALID policy force integrals never establish an improvement. Current campaign contains no CEM search and makes no global-optimum claim.

## Failure evidence and interpretation

Unchanged evaluator failure counts: `{"summary_complete": 14, "transition_order": 14, "true_return": 13, "phase_timeouts": 6, "not_complete": 14}`.
Recovery-gate success establishes the tested expert interface. Unqualified student performance cannot by itself establish observation/action impossibility. See FAILURE_DIAGNOSIS.json for every failed collection/evaluation, not just the most favorable result.

## Preservation, runtime and verification

Historical files rehashed: 2146; preservation PASS: True. No old result was rewritten. Preexisting Git index and HEAD are unchanged; no stage, commit, push, merge, reset or stash.
CPU MuJoCo single-owner execution; CUDA imitation/SAC optimization. Reuses the repaired process ownership / memory monitor, with host commit headroom and swap-growth gates. Science hashes, preregistration hash, executable hashes, exact seed/config/environment, native actor/optimizer/RNG checkpoints, aggregated datasets, replay (if SAC started) and evaluation summaries are retained. Raw key success/failure traces are losslessly compressed with hash verification.
Commands: preflight.py; expert_gate.py; mechanical_checks.py; workflow.py (conditional dagger.py then sac.py); finish.py. Python compile and the mechanical state-sensitivity, action-transform, beta-schedule and mixed-replay ratio checks are in MECHANICAL_CHECKS.json. No independent Auditor agent was dispatched; source/data-flow and preservation audits run in the single agent.

## Next

Audit the saved last-good and ability-loss SAC checkpoints before further actor optimization.

STOP.

## Post-run tracking and safety measurements

All expert and student traces were independently hash-checked. Causal q/dq tracking RMS/peaks, exact safety-mode counts, action interventions, terminal reason, moment integral, F/M peaks and clearance are in TRACKING_SAFETY_AND_ACTION_DIAGNOSIS.json. Pure-student expert disagreement is computed offline only after each evaluation finished; it changes no execution, learning labels or gate.

Final pure-student endpoint diagnostic: `{"name": "round_04/evaluation_1", "scope": "NATIVE", "valid": true, "causal_tracking_q_time_RMS_deg": [0.40405383339041895, 0.886652052186532], "causal_tracking_q_peak_deg": [1.1076338493355327, 2.1622251714324934], "causal_tracking_dq_time_RMS_deg_s": [1.12385539391601, 2.444102138060975], "time_weighted_tracking_defined": true, "safety_mode_sample_counts": {"": 1, "TRACK": 5989}, "session_safety_mode_counts": {"TRACK": 5989}, "action_interventions": 10, "moment_integral": 145.36953443643867, "force_peak": 118.53473316262449, "moment_peak": 16.95820312030705, "clearance": 0.007228274556562411, "termination": "COMPLETE", "post_run_expert_comparison": true, "expert_execution_changed": false, "mean_action_error_RMSE": 0.024446627125144005, "phase_action_error_RMSE": {"OUTBOUND": 0.042250871658325195, "HOLD": 0.0021094882395118475, "RETURN": 0.001461497275158763}, "final_1s_target_span_deg": [0.1156441867351532, 0.06967410445213318], "final_1s_exact_action_changes": 49, "final_estimated_q_deg": [5.560507823857998, 9.398229976975381], "final_estimated_dq_deg_s": [0.2226499346137897, 0.45361736803087643], "final_reference_q_deg": [5.5738091468811035, 9.434938430786133], "final_reference_dq_deg_s": [0.0, 3.975693351829396e-16], "endpoint_settlement_diagnostic_only": true}`.

Small continuously varying absolute targets can repeatedly replace an OTG continuation. If the final diagnostics show this, it is a learned-command / reference-completion interaction within the frozen interface, not proof of insufficient observation or neural capacity. This campaign does not change that interface to force success.

## SAC post-stop checkpoint diagnosis

SAC_STOP_CHECKPOINT_DIAGNOSIS.json compares the qualified start and every 10k checkpoint on the same 13,852 archived causal observations. This is offline inference only, with no new physics or updates. It records mean action drift, latent/effective action std, entropy coefficient, per-phase current-critic values and finite-weight checks. Q-value differences are learned-model diagnostics, not independent physical evidence.

Step 0: mean action drift RMSE 0.000000, alpha 1.000000, median latent std [0.018315639346837997, 0.018315639346837997], finite weights True.

Step 10000: mean action drift RMSE 0.732999, alpha 0.430492, median latent std [0.5922055840492249, 0.5785360932350159], finite weights True.

Step 20000: mean action drift RMSE 0.909472, alpha 0.292121, median latent std [0.22339454293251038, 0.4910997748374939], finite weights True.

The repeated task-ability loss can be attributed descriptively to changed actor behavior. These observational diagnostics cannot separately prove entropy, critic error or replay weighting as the unique cause. The qualified student remains saved; no global optimum or interface impossibility is claimed.

## Final audit and success preservation

|Online steps|NATIVE VALID|MATCHED VALID|Demo fraction|
|---:|---:|---:|---:|
|10000|0/3|0/3|0.25|
|20000|0/3|0/3|0.25|

The two consecutive zero-success NATIVE checkpoints trigger the prospectively frozen ability-loss gate. Actor fine-tuning is frozen at 20,000 online steps; no automatic restart occurs. No fine-tuned SAC checkpoint is independently VALID, so both best VALID NATIVE and best VALID MATCHED are absent. The preserved last-good is the qualified initialization, not an alleged SAC improvement.

Qualified student MATCHED baseline: 0/3 R2 VALID, though all three complete the physical task. Phase times exceed matched eligibility. Student NATIVE phases are OUTBOUND 9.990 s, HOLD 9.990 s, RETURN 9.965 s; the long dwell/reference completion makes its NATIVE interaction integral much larger than fixed hip-leading.

Final evidence audit PASS. Dataset phase counts: {'OUTBOUND': 5668, 'HOLD': 4902, 'RETURN': 3282}. Replay contains 28991 seed-plus-online transitions (8,991 seeds + 20,000 online), plus the separate 13,852-transition immutable demo pool. Actual raw environment actions define replay transitions. Actor/optimizers/targets/replay/RNG and all archived raw evidence have a SHA256 manifest. No difficult state was removed. The repaired process ownership/host-memory monitor passed the final check.

One evaluator-orchestration omission was repaired before SAC began: the sequential qualified-student MATCHED baseline hook. Original source and repair hashes are preserved in IMPLEMENTATION_REPAIR_COMPARATOR_HOOK.json; no training parameter, gate, expert or R2 evaluator changed. CPU actor creation uses fixed seeds at evaluation boundaries; this makes the subsequent RNG stream restart reproducible and is a limitation of this v1 orchestration, not evidence of a standard SAC convergence guarantee.

Wall time about 2.05 h: the scientific stop gate, not a lowered training target or resource limit, ends the 100k maximum budget early. Source/index/HEAD and historical comparator hashes remain intact; no staging, commit or push.
