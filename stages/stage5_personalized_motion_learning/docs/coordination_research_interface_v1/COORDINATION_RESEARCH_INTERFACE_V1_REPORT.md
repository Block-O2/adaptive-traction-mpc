# Coordination Research Interface v1

**STATUS: BLOCKED_INTERFACE_EXECUTION.** E and V are blocked. This is not a COMPLETE work package. No training, value network, 100+ dataset, multi-Human work or hardware was started.

## B freeze and provenance

Starting branch `codex/dagger-to-sac-expert-v1`, HEAD `41cdddef117caa4b191a52129c4ff83e481fd5a8`. Work branch `codex/coordination-research-interface-v1`. Existing staged/untracked state preserved. No stage, commit, push, merge or reset. 370 source/config files and 266 historical files remain byte-identical.

B is the current unmodified `runtime_sac_expert_v1` old_nominal model controller, fresh deterministic commissioning-only nominal 120-degree Human, frozen beta/residual/estimated geometry during the task, existing phase manager and independent scientific evaluator. Config/source hashes, Human belief, exact reference tape and initial state are in B_FREEZE.json, HUMAN_MODEL_FREEZE.json, PROTECTED.json and CONTRACT.json.

Gate A PASS: all numeric reference/physical/force/moment arrays match exactly; matching absent-value masks and categorical arrays checked. J_F difference = 0 N s. B J_F = 1438.613498467487 N s; phase durations 9.005 / 1.020 / 9.005 s; physical audit PASS.

## Interface contract

Only normalized differential progress changes: `p_h = p_h^B + Delta_d`, `p_k = p_k^B - Delta_d`. Thus the common mode remains B. Residual zero reproduces B, including baseline asymmetry. Reference-phase endpoints define normalization; nominal task arrival/settle boxes remain separately frozen.

ResidualAction carries phase, normalized phase-clock location, current residual value/first/second derivative, arbitrary future PWL knots, horizon, version and provenance. Execution is explicitly quintic C2 through the knots. This is not an H1/H2/H3/H4 action space. OUTBOUND and RETURN schedules are independent. HOLD actions are rejected structurally. Endpoint residual/velocity/acceleration are zero; mid-phase updates inherit the existing residual C2 state. Scalar convenience actions, positive/negative lead, reversal and catch-up are supported.

Six schedule-contract tests PASS: endpoint C2, both signs/reversal/catch-up, repeated updates, invalid/HOLD/endpoint rejection, common-mode invariant and feasibility envelope, exact baseline knot values, independent RETURN. These are API tests, not physical expressivity PASS. Unit failure from interpolation roundoff at an exact stored knot was corrected by returning that stored tuple exactly; failed test log retained.

## Timing and safety

Main timing is R2: OUTBOUND/HOLD/RETURN minima 9/1/9 s, each actual duration <= minimum + 0.020 s. There is no post-task wait, HOLD trimming, faster-task cost reward or segment-count gate. The unmodified B and all 12 accepted B continuations satisfy the unchanged physical evaluator and R2 timing.

The new continuous tape path was rejected before actuation. The strict certificate checks normalized progress/ROM, analytic polynomial velocity/acceleration/jerk extrema, existing combined-body clearance and endpoint clearance floor, current-model mechanics and causal tracking-offset clearance. Rejected updates retain an existing certified continuation; an unqualified first phase aborts. Existing CR12 execution/receipt and realized force/moment/ROM/clearance layers remain inherited. No direct Human actuation API is present in the residual modules.

The initial whole-phase baseline tape reconstruction yields acceleration peaks approximately 241.84 / 403.07 rad/s² and jerk 502654.8 / 837758.0 rad/s³. It is rejected. This is a representation failure, not a measured Human acceleration violation and not authority to relax thresholds.

The reason is concrete: 10 OUTBOUND and 10 RETURN 5-ms intervals have unchanged B q but nonzero declared dq up to 0.34906585 rad/s. Those are native planning-wait/reference intent semantics. Treating the logged tuple as samples of a physical-phase-clock C2 spline invents large between-sample derivatives. Native scheduler/governor/wait ownership must be preserved; the tape interpolator is not a promotable pure-coordination executor. B source and safety/timing semantics were not changed to force a pass.

## Historical decomposition and expressivity

Two evidence scopes are explicitly separate. Original segment-MATCHED (1.3x original nominal segment durations) is not R2 MATCHED. The actual historical fixed/CEM winners and their own original baseline are read-only; the R2 fixed/CEM transfers are analyzed separately. No historical NATIVE cost is claimed reproduced.

| Scope/path | OUTBOUND common RMS | OUTBOUND coordination RMS | Common squared modal fraction |
|---|---:|---:|---:|
|fixed_hip_segment_MATCHED|0.000364|0.041529|0.007694%|
|CEM_segment_MATCHED|0.000687|0.064225|0.011454%|
|R2 fixed_hip_lead|0.168156|0.048386|92.35%|
|R2 cem_reference_transfer|0.039310|0.031120|61.47%|

Original segment-MATCHED fixed/CEM path differences are predominantly differential. R2 transfer differences contain substantial common-mode pacing despite nearly equal total phase durations. Modal fractions characterize trajectory differences; they are **not causal percentages of J_F benefit**.

Pure historical joint paths are fitted as d(m), then retimed to B m(t), rather than carrying over historical wall-clock pacing. Dense arbitrary knots are permitted. The small CEM RETURN backtracking is disclosed; sorted d(m) graph fitting is an approximation, not an exact multivalued path representation. Explicit endpoint-zero projections and full errors are retained.

| Historical path fit to current B | OUTBOUND normalized RMS | RETURN normalized RMS | Execution |
|---|---:|---:|---|
|fixed_hip_segment_MATCHED|0.000209|0.000091|BLOCKED|
|CEM_segment_MATCHED|0.000323|0.000091|BLOCKED|

Fits meet the prospectively specified 0.02 normalized RMS bound. The unconstrained fits also expose small normalized-progress excursions (up to approximately 0.0026 beyond an endpoint); the full ranges are retained in LEGACY_PATH_FITS.json and were not clipped. These fits are not feasible actions. Gate B/C still FAIL/BLOCKED: no complete accepted pure-coordination execution or matched force/moment/clearance comparison exists. Richer patterns are represented and C2 contract-tested, but are not promoted as physically executable.

## Full-state branching and continuation labels

Four live snapshots: early OUTBOUND 1 s, mid OUTBOUND 4.5 s, late OUTBOUND 7.5 s, mid RETURN 4.5 s. Each branches baseline/hip/knee once. Twelve completed continuation rollouts, one advancing physics owner at a time; parent waits for each child. Complete task validity 12/12; all J_F = 1438.6134984674875 N s, phase durations unchanged.

The safe branch mechanism is a Linux full-address-space fork after computational workers quiesce and the process has one live thread. MuJoCo integration state and mutable model, Human belief/updater, observer/estimator RNG and history, reference q/dq/ddq, phase/timers, residual/planner/safety/receipt ownership, prefix trajectory and cost state all remain in the clone. The manifest includes the native integration state mask/size and full Python graph; opaque lock/cache handles are explicitly listed as fork-preserved. Child pre-action and parent post-branch hashes match the starting snapshot. This is not q/dq-only copying.

CPython automatically reseeds global random after fork. The initial hash guard rejected that mismatch; failed pre-continuation probes were archived. The correction explicitly restores Python/NumPy global RNG before hashing. No mismatched branch was promoted. Snapshots are process-scoped and are not claimed to be portable serialized restart files.

All 8 nonzero requests were explicitly rejected by the current reference certifier and retained B. Thus baseline costs are correctly comparable but no distinct executed coordination consequence exists. Gate G PASS for process-scoped full-state branching; Gate H FAIL. These are rejection/fallback smoke records, not a value-training dataset.

Final labels retain snapshot hash, candidate and acceptance, horizon, declared versioned continuation policy, full commissioned Human-model hash including geometry, R2 timing, complete-task validity and complete/remaining J_F, force/moment/duration. The original individual labels remain; FINAL_CONTINUATION_LABELS.json adds the complete-model identity/source provenance. Meaning is remaining cost under declared continuation, Q^{pi_cont}; never Q* or V*. Training eligibility is false.

## Gate decisions

| Gate | Decision |
|---|---|
|A|PASS — zero reference/physical trajectory/metrics exactly B|
|B|BLOCKED / NOT PASS — fixed/CEM differential path fit; accepted historical pure execution blocked|
|C|BLOCKED / NOT PASS — R2 shared timing contract implemented; accepted pure-coordination timing not yet validated|
|D|PASS — HOLD action structurally forbidden; original B phase/dwell ownership|
|E|BLOCKED / NOT PASS — richer patterns only contract-tested; physical execution blocked|
|F|BLOCKED / NOT PASS — B unchanged and zero exact; new tape rejected by acceleration/jerk certificate|
|G|PASS — process-scoped complete-state fork; parent/child and parent post-branch hashes equal|
|H|BLOCKED / NOT PASS — 12 valid B continuations, 8 nonzero rejected; no distinguishable executed candidate outcomes|

**E READINESS: BLOCKED. V READINESS: BLOCKED.**

## Evidence, repairs and stop

Compact NPZ references/traces and losslessly verified gzip runtime artifacts are retained. Full-state snapshot manifests, 12 original continuation labels, final label audit, source/history hashes and failed attempts are retained. Source history distinguishes executed smoke modules from subsequent non-physics fixes. No historical evidence was deleted; only newly created raw JSON logs were replaced by verified lossless gzip copies.

Repairs: versioned runtime resource-root/importability for spawned planner; dataclass serialization and matching NaN masks; exact stored-knot tuple retrieval; inherited analytic proximal-thigh clearance bound; explicit Python/NumPy at-fork RNG restoration. No cost, physics, task duration, safety threshold or B controller parameter was tuned. Initial failed tape reconstruction, aborted/import probes, failed unit test and failed fork probes are retained.

Commands: preflight.py; capture_baseline.py; decompose.py; historical_segment_decomposition.py; fit_legacy.py; diagnose_reference.py; test_interface.py; prepare_branches.py; recover_branch_smoke.py; branching.py; finalize.py, through the existing `/home/hank/envs/adaptive-online-rl-v1/bin/python` with one-thread BLAS. No optimizer training ran. These are development/mechanical smoke evidence on one previously exposed nominal Human, not held-out or multi-Human scientific conclusions.

Exactly one recommendation: repair the residual realization around native B schedule/governor/wait ownership, preserving B common progress and exact zero behavior; do not start E proof or V data generation until the blocked execution gates pass.

STOP.
