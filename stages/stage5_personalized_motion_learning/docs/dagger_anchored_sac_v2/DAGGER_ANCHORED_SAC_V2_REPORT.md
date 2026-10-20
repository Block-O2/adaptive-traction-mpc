# DAgger-Anchored SAC Fine-Tuning v2

**STATUS: PAUSED_RESOURCE_RISK — 21,283 / 50,000 collection steps; the campaign is incomplete.**

The first 10,000 actor-learning collection steps were completed after 11,283 frozen-policy calibration/seed interactions. A resource monitor then observed 146.105 MiB new swap, exceeding the frozen 128 MiB guard. Training dispatch was stopped, the already-running independent evaluation finished, and the complete learning state was saved. No rescue, further physics, resource-threshold change, environment upgrade or WSL configuration change followed. The 12h clock was not extended.

This is explicitly **anchored SAC**, a method-development experiment with jointly introduced components. Their independent causal contributions are not established. One training seed; repeated deterministic cold replays verify reproducibility and are not independent training seeds.

## Starting point, preserved contract and source diagnosis

The immutable qualified pure DAgger student, rather than the failed v1 20k SAC actor, initialized the mean. v1 reports and actual actor, environment, R2 evaluator, task, reference and runtime sources were read before development. The R2 plant, 55-D fixed normalization, two target proposals, 20ms period, commissioning-only human model, reward, phase handoff, 30s global/10s phase deadlines and all physical/safety requirements remain unchanged. No DAgger/scratch retraining or alternate algorithm was run.

Confirmed v1 issues: its evaluation helper reseeded parent Python/NumPy/Torch CPU/CUDA streams; trained means drifted strongly and exploration varied substantially; qualified student native completion and matched ineligibility are reproducible. Fresh-critic mismatch and entropy influence remain plausible joint mechanisms, not uniquely identified causes. v1 negative checkpoints and all old evidence are preserved.

## Evaluation RNG isolation and exact initialization

Evaluation owns a separate OS process, cold commissioned environment and RNG. Inserting a real evaluation leaves parent Python, NumPy, Torch CPU/CUDA, buffer sampler and environment RNG digests unchanged. The next stochastic training action is bitwise identical to the no-evaluation clone. State restoration constructs only the counterfactual test; normal evaluations do not reseed or reset the training stream. Child seeds are distinct and logged, while the original initial-condition seed remains fixed. Training physics is closed and joined before evaluation dispatch: one physics owner.

Imported SAC deterministic pre-unscale means match the qualified actor bitwise on all 13,852 observations on the same device. Restoring the legacy BasePolicy.predict proposal path also reproduces native closed-loop J_F = 1950.0598136503165 exactly. A direct actor.forward implementation was initially mathematically equivalent but lost a float32 unscale roundtrip (max 5.96046e-8); it caused a retained HOLD timeout. That implementation defect was versioned and repaired before formal training. See RNG_ISOLATION.json, PREDICTION_PATH_DIAGNOSIS.json and FROZEN_STUDENT_BASELINE.json.

## RL transitions and imitation separation

HISTORY_RL.npz contains 22,843 immutable NATIVE transitions: real executed upper proposals from the DAgger mixed episodes plus six full successful pure-student episodes, including the complete 593-step teacher episode. Expert labels not executed are never paired with that transition reward/next state. Teacher executed-action metadata missing in the aggregate was recovered from its paired real action archive in the v2 copy. Raw proposal and safety executed action are separate. MATCHED dynamics never enter this replay.

IMITATION_ONLY.npz contains observation, expert label, phase and label-availability fields only; no RL reward/next state. The behavioral anchor uses immutable π0 means on those legal states, including failed/off-distribution DAgger student states, not just the original teacher trajectory. No teacher or π0 takeover occurs at execution.

Final transition audit: PASS across 55 files; exact next-observation proposal/safe-action echoes in the environment's float32 representation, phase labels and episode continuity; archived collection sum = 21,283. An initial float64 echo assertion exposed only 2.22e-16 inverse-map roundtrip precision in six legacy pure episodes, documented in ACTION_ECHO_DIAGNOSIS.json; no records changed.

Every critic batch actually samples 64 immutable history + 192 current-run transitions (25%/75%). Successful history is not overwritten. Current-run initialization is collected first; no 5,000-step uniform warmup. Sampling counts and OUTBOUND/HOLD/RETURN coverage are saved in UPDATES.jsonl and RESUMABLE_STATE_AUDIT.json.

## Why qualified-student HOLD lasts 9.99s

The recorded task dwell threshold is reached at task time 10.510s, shortly after HOLD entry at 9.990s. However, 99.84985% of HOLD trace nodes still have nonzero reference velocity. Changing student targets repeatedly replace the certified OTG reference; handoff also requires complete schedule, terminal q and zero dq/ddq. Late infeasible offers retain the last certified continuation, which finally settles near the phase deadline. This supports policy/reference-completion inefficiency, not a confirmed timer bug. No HOLD truncation, cropped trace, fabricated wait or timing-rule relaxation was used.

## Frozen critic, exploration and anchor settings

Fresh critics, targets and optimizers: gamma=0.999866675555161, tau=.005, critic lr=3e-4, 20,000 critic-only updates. Qualified mean and calibrated exploration remain bitwise frozen during warm start. Bellman next action and entropy come from the actual frozen policy; teacher trajectory returns are never treated as another policy's exact Q target. An excluded full frozen-policy episode is retained for value/TD/realized-return checks.

Held-out start Q: 0.0327 → -9.1762; realized discounted reward return 402.0652. TD RMS 13.3289 → 8.0597; Q-versus-realized-return RMSE 441.3732 → 446.2243. Final Q range [-46.421661376953125, 329.0753479003906]. This critic is finite but has poor return-scale agreement. A single successful realized reward return is not expected soft Q, and stochastic failures matter. Small training loss alone does not establish reliability. The preregistered warm budget was respected; ten small actor updates then passed complete native evaluation (J_F 1951.437342, slightly worse than student), permitting bounded learning without an invented exact-Q gate.

Qualified actor log_std was never trained by imitation: median latent std approximately [0.9620, 1.0156], unsuitable to inherit as conservative exploration. Exactly two prior candidates, log_std=-8 and -10, were calibrated. Initial duplicate-seed -8 successes are retained and consume 2,996 collection steps, but are not independent evidence. After fixing child-seed indexing, each candidate succeeded 1/2 independent stochastic episodes; -8 failed RETURN and -10 failed HOLD. Frozen -10 was selected by the preregistered lower-candidate fallback. Low noise is not proven safe or reliably successful.

Selected fixed log_std=-10 gives latent sigma=exp(-10), conservative target-angle 1σ bound 0.00283750deg; per-joint local median [0.00044311852203126185, 0.0004544485879682717]deg. EXPLORATION_UNITS_CORRECTED.json recalculates selected -10 units; the original calibration's first-candidate unit fields are retained rather than silently overwritten.

Fixed alpha=.001, no automatic target entropy. The Gaussian mean/log_std, tanh, action scaling and Jacobian-corrected log probability are consistent with SB3. No environment-external noise is paired with another policy distribution in loss.

L_actor = L_SAC + λ E[sum over action dimensions (a_mean(o) − π0(o))²]. Actor lr=1e-6; one actor update per ten critic updates; λ=10,000 and 96 anchor states per phase. Mean moves; log_std remains fixed. No lambda decay occurred in this run. Before 20k learning steps it stays fixed; afterward two consecutive complete native checkpoints are required for the frozen .9-per-5k decay with floor5,000. No requirement to reach zero.

Two actor losses are logged. Runtime gradient logging had a cadence mismatch and captured only the first norm pair; this is an evidence limitation, preserved rather than fabricated. GRADIENT_SCALE_AUDIT.json adds post-run fixed-batch gradients without weights, RNG or physics changes. At 1k/2k/5k/10k the weighted-anchor/SAC norm ratios are approximately .951/.870/1.238/1.230, with cosine near −.99. Q does not completely overwhelm the anchor on these probes, but opposing gradients indicate an optimization constraint; this is descriptive, not a causal ablation.

One rescue was preregistered: restore actor, critics, targets, optimizers, fixed alpha, replay, sampler/global/env RNG; actor lr×.1, std×.25, anchor×4, no decay. Restored physics starts a cold episode; it does not pretend an in-flight rollback. Failed interactions never leave the consumed budget. Rescue count is zero because no deterministic native capability-loss gate was reached.

## Checkpoint results

Pure actor, no teacher, no training/normalization updates. NATIVE is evaluated first; MATCHED uses the unchanged timing contract independently. Deterministic replicates share the original physical initial-condition protocol, and are not robustness across human conditions.

|Learning point|Total collection|NATIVE VALID|MATCHED VALID|Stochastic NATIVE|Native J_F (N·s)|OUT/HOLD/RETURN (s)|
|---:|---:|---:|---:|---|---:|---|
|0|11283|2/2|0/2|False|1950.059814|9.990/9.990/9.965|
|1000|12283|2/2|0/2|True|1948.911220|10.000/9.970/9.960|
|2000|13283|2/2|0/2|True|1907.172693|9.970/9.955/9.460|
|5000|16283|2/2|0/2|True|1950.871113|9.980/9.990/9.985|
|10000|21283|2/2|0/2|True|1768.678538|9.975/6.580/9.990|

The confirmed best remains the **2k** checkpoint: J_F 1907.172693, separately replay-confirmed. The **10k** candidate completed two independent cold deterministic native replays with J_F 1768.678538; both passed all complete native gates, and its separately seeded stochastic replay completed with J_F 1952.078475. The monitor stopped the parent before it could dispatch the additional preregistered new-best replay. Therefore 10k is a complete VALID candidate with **best promotion pending**, not the confirmed best. All five 10k protocol evaluations are retained and recovered into append-only logs.

MATCHED: 0/2 at every learning point, including 10k; physical completion alone does not meet the R2 timing contract (9/1/9 minima plus the unchanged .020s upper slack). Known student limitations were not used to block native learning or redefine qualification.

## Complete metrics and same-scope references

|Result|Scope|VALID|J_F N·s|Total s|F peak N|M integral N·m·s|M peak N·m|Clearance m|
|---|---|---|---:|---:|---:|---:|---:|---:|
|old_nominal|NATIVE|True|1237.487622|16.000|115.479119|79.039780|15.711377|0.006455440|
|fixed_hip_lead|NATIVE|True|877.722553|11.835|118.425398|74.426845|17.018579|0.006532101|
|cem_reference_transfer|NATIVE|True|1194.062007|15.420|124.364540|83.752228|18.092599|0.007407144|
|old_nominal|MATCHED|True|1438.613498|19.030|115.479119|100.417251|15.711377|0.006455226|
|fixed_hip_lead|MATCHED|True|1344.896796|19.015|118.425398|120.806727|17.018579|0.006532101|
|cem_reference_transfer|MATCHED|True|1428.142719|19.015|124.364540|107.068358|18.092599|0.007407143|
|legacy_predict_revision/baseline/frozen_student_NATIVE|NATIVE|True|1950.059814|29.945|118.534733|145.369534|16.958203|0.007228275|
|legacy_predict_revision/baseline/frozen_student_MATCHED|MATCHED|False|1950.059814|29.945|118.534733|145.369534|16.958203|0.007228275|
|legacy_predict_revision/checkpoint/a1_p2000_NATIVE_1|NATIVE|True|1907.172693|29.385|118.718386|138.914465|16.957609|0.007217280|
|legacy_predict_revision/checkpoint/a1_p10000_NATIVE_1|NATIVE|True|1768.678538|26.545|118.666303|141.571229|16.957116|0.007192802|
|legacy_predict_revision/checkpoint/a1_p10000_MATCHED_1|MATCHED|False|1768.678538|26.545|118.666303|141.571229|16.957116|0.007192802|
|legacy_predict_revision/checkpoint/a1_p10000_STOCHASTIC|NATIVE|True|1952.078475|29.980|118.412007|145.814497|16.957345|0.007227400|

Confirmed improvement over inefficient student: 2.199% (42.887120 N·s). Latest complete candidate improvement: 9.301% (181.381276 N·s), pending extra best confirmation. Confirmed best remains 1029.450140 N·s above native fixed hip-leading; latest candidate remains 890.955985 N·s above it. There is no valid matched learner result to compare with the 1344.896796 N·s matched reference. Native and matched costs never compete across scopes.

Capability is preserved at evaluated deterministic native checkpoints; there is a confirmed modest improvement over the inefficient student. Strong teacher performance is not exceeded. Latest HOLD falls from9.990 to6.580s; resulting force-integral savings include less elapsed HOLD. They are not described as pure coordination gains. PHASE_COST_DECOMPOSITION.json reports complete phase integrals and durations, with no discarded waiting.

10k candidate: OUTBOUND stopped/settled, HOLD and RETURN complete, termination COMPLETE; phase gates {'settled_OUTBOUND': True, 'completed_HOLD': True, 'completed_RETURN': True}; safety modes {'TRACK': 5309}; 5 reference offers rejected, modification fraction 0.003765. Its full certified and physical audits are retained. ACTION_DRIFT.json records proposal-vs-anchor target-angle RMSE/peaks by phase for every evaluation, including stochastic actions. F peak has not improved over the student, and clearance decreases slightly while remaining valid.

![Learning curve](LEARNING_CURVE.png)

## Negative evidence and repairs

15 invalid evaluations are retained and their partial force costs are unranked; 2 completed online episodes failed among 5 full episodes. Ordinary online HOLD/RETURN failures did not automatically stop learning. Stochastic success fluctuates: point0 failed RETURN; 1k/2k/5k/10k each succeeded once, which does not establish reliable stochastic execution. Calibration failures and duplicated RNG trials remain explicit. Critic return-scale validation is weak and training gains are nonmonotonic (5k regressed near baseline). MATCHED remains ineligible; strong references remain much better.

Engineering defects discovered inside v2 are versioned, with failed traces and source histories retained: exact prediction-path float32 mismatch; duplicate calibration child seeds; generic SAC.load optimizer-group mismatch with frozen log_std (resolved by identical construction + set_parameters); collection progress loop variable overwritten by predict return; best-result nested schema indexing. Interruptions saved learning/replay/RNG state; restores verified network/target/optimizer components and did not reset counts. The interrupted217-step physical episode was archived and followed by an explicit cold boundary. These are technical resumes of the same attempt, not hidden scientific rescues. IMPLEMENTATION_REPAIRS.jsonl, IMPLEMENTATION_RESUME.jsonl, RESTORE_COMPONENT_AUDIT.json and preserved exception checkpoints document them.

## Resource consumption, budgets and save state

Collection budget: 21,283 = 11,283 frozen calibration/seed + 10,000 learning; maximum50,000 was not reached. Evaluation-only interactions: 51,892, separately ledgered and not replayed except named calibration/seed collections in BUDGET.jsonl. Critic updates30,010 (20,000 warm +10,000 learning +10 small test); actor updates1,010. One attempt, zero rescues. Failed and duplicate data collection counts against the same total.

Observed online throughput median 12.906 steps/s, range [11.21374393200451, 16.810750845435468]; warm updates ~223/s. Peak main PSS 2.236GiB; peak new swap 146.105MiB; GPU device memory reading max 185MiB. Minimum WSL available 2.654GiB; minimum Windows commit headroom 4.849GiB. Resource checks did not all pass: the swap gate triggered this pause. After process exit memory was released; that does not erase the event or automatically restart training.

Training-pause wall time 9.207h; evidence-closeout wall 9.406h, within12h. A roughly6.95h launch/end clock gap occurred around an early frozen rollout while its recorded active host duration was ~126.5s. Host/WSL suspension is a possible explanation, not established. Wall budget includes this gap; there was no extension. RESOURCE_EXTERNAL.jsonl, RESOURCES.jsonl and WORKFLOW.log retain timestamps.

Resumable checkpoint: `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/dagger_anchored_sac_v2/checkpoints/paused_exception_1791138081`. It contains model.zip policy, critics/targets and both optimizer states, actor.pt, and resume.pt containing actual custom replay, immutable history hash, alpha configuration, sampler/Python/NumPy/Torch CPU/CUDA/env RNG, sample/counter state, lambda/std/lr and last-good/best metadata. RESUMABLE_STATE_AUDIT.json verifies saved components. Native SB3 replay buffer is unused; actual active replay is resume.pt. No in-flight physical rollback is claimed.

Protected old files rehashed unchanged: 1064. Git HEAD, branch, index bytes and cached binary diff hashes remain identical. No staging, commit, push or merge. Qualified student fallback and confirmed2k actor are separately frozen; latest10k and failed candidates remain available. Full-frequency key evaluations/failures are losslessly archived; successful training stores compact actual actions/transitions. Archive hashes are in ARCHIVE_MANIFEST.json.

## Evidence index and NEXT

- PREREGISTRATION.json / LOCK.json: frozen scientific settings and source revision hashes.
- RNG_ISOLATION.json / MECHANICAL_CHECKS.json: isolation, exact import and legal history checks.
- TRANSITION_AUDIT.json / FINAL_TRANSITION_EVIDENCE_AUDIT.json: history provenance and all stored proposal/next-state checks.
- HOLD_DIAGNOSIS.json: original complete HOLD causal trace analysis.
- CRITIC_DIAGNOSTIC_before/after.json / UPDATES.jsonl / GRADIENT_SCALE_AUDIT.json: critic, losses, phase samples and gradient evidence.
- ALL_EVALUATION_METRICS.json / EVALUATIONS.jsonl / NEGATIVE_RESULTS.json / ACTION_DRIFT.json: all scopes, safety/gates, failures and proposal drift.
- PHASE_COST_DECOMPOSITION.json / LEARNING_CURVE.csv/.png/.pdf: full phase cost/time evidence.
- RESOURCE_PAUSE_REQUEST.json / RESOURCE_PAUSE_CLOSEOUT.json / RESUMABLE_STATE_AUDIT.json: exact pause, completed evaluations and pending confirmation.
- FINAL_PRESERVATION.json / ARCHIVE_MANIFEST.json: readonly preservation and final evidence hashes.

Heavy simulation/training remains paused at the requested resource exception. If a later continuation is authorized and resources meet the original gates, use the complete paused learning state, retain21,283 consumed collection steps, and reconcile/finish pending10k capability bookkeeping and extra best replay before further actor updates. Do not blindly restart failed actors, reset budgets, loosen thresholds or automatically resume merely because memory fell after exit. The original12h run deadline is not extended by this closeout. This workflow stops here.

STOP.
