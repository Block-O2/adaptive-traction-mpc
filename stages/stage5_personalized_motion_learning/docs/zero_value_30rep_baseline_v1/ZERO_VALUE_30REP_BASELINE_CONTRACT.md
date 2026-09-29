# Zero-value 30-repetition baseline v1 — frozen before formal execution

## Question and scope

Characterize measured cuff interaction during one continuous 30-repetition low-ROM Scientific Simulation session while the existing personalized Human model updates online and the learned waypoint value is exactly zero. This is descriptive baseline evidence. It does not establish a causal adaptation effect, RL improvement, statistical significance, or optimality.

Source: `codex/repetition-boundary-v1` at `f0d87e386caeaf88ddc0f52c5c8335e8efa71098`; frozen 618-file production fingerprint `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. Host: Y9000P Ubuntu WSL2. Use the frozen registered `balanced_ordinary_r01.json` case (SHA-256 `ceb33e9eeb243d49ad4bd1ad0a17637243219f3e058f4da0aaf2ed9fbf975b2d`), frozen `incremental_clearance_terminal_v9.json` options (SHA-256 `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb`), deterministic IK seed `20260918`, Python 3.10.21 and single-thread OMP/OPENBLAS/MKL settings.

## Session and state

One session contains exactly 30 repetitions. Every repetition executes OUTBOUND → HOLD → RETURN → COMPLETE. Each pair uses the validated INTER_REP_SETTLE → INTER_REP_HOLD boundary with the unchanged 2 s maximum wait and at least one 5 ms hold interval. The same physical plant, native Human and CR12 q/dq, simulation clock, measured-state layer, causal observer, command history, personalized Human updater and model belief persist. The task, planner, reference, scorer, scientific epoch and transient control objects are fresh each repetition. The next episode uses a fresh applied TRACK bootstrap and source receipt. No teleport, model reset, or hidden cross-repetition transient is allowed.

No RL learner, replay update, exploration, learned ranking, waypoint objective change, controller mathematics change, Human dynamics change, safety threshold change, or realtime/hardware work. The existing Human model update behavior remains unchanged. Every scored candidate has learned value 0; rejected/unscored candidates retain explicit null/unscored semantics. Log each candidate set, baseline score, selection, and executed waypoint. Any nonzero learned value or unexpected selection path fails the session.

## Quantities and attribution

For each repetition, `J_F_task = ∫ ||F_cuff_measured|| dt` over its OUTBOUND, HOLD and RETURN task intervals, using the validated left-interval measured-wrench integration. `J_F_session` adds its following explicit inter-repetition SETTLE/HOLD force integral. The next episode's fresh TRACK/bootstrap interaction is attributed to that incoming episode as in boundary v1, and shown separately. Repetition 30 has no following boundary, so its `J_F_session` includes task plus its own incoming bootstrap only. The same accounting applies to moment integral. Report task and session costs, peak cuff force and moment, cumulative moment, minimum clearance, task and phase durations, boundary durations, waypoint decisions and sequences, Human model sequence and parameters, Human/CR12 initial and final q/dq, completion and physical/scientific/scorer-v2 status.

## Gate and recovery

Each repetition must be COMPLETE with physical PASS, scientific PASS, scorer-v2 PASS, finite metrics, zero-value invariant, valid phase sequence, native q/dq continuity and clean lifecycle audit. Stop immediately on a real scientific/control failure, preserving all prior and failed data. Only a pure logging/reporting defect may be minimally repaired and resumed from a verified checkpoint without changing completed scientific state. If exact recovery cannot be shown, start a fresh, separately named session with the reason recorded; do not overwrite the failed attempt. Checkpoint after every completed repetition must contain enough persistent physical, Human/adaptation, causal measurement and command state for crash recovery, index, provenance and cumulative metrics, with a SHA-256 hash. No artificial restart in a successful run.

One formal 30-repetition session is planned. A tiny mechanical preflight may verify checkpoint serialization without inclusion as formal evidence. Do not run a second 30-repetition group. If unexplained internal nondeterminism appears, only a minimal targeted repeat is allowed.

## Analysis fixed in advance

Compare repetitions 1–5 with 6–30 descriptively using mean, median, sample standard deviation, min/max and relative mean change. Report all per-repetition task/session costs, force/moment peaks, model and waypoint progression. Natural variability comprises adjacent `ΔJ_F_task` and `ΔJ_F_session`, late-phase variance/standard deviation, waypoint selection variability, and model parameter drift. Check unusually long boundary waits individually; do not silently average them away. Report no causal or statistical claim. Preserve raw trajectories locally under ignored `results/`; commit only compact reviewed summaries, manifests, hashes and provenance. Final status is exactly COMPLETE, FAIL or PARTIAL under the names requested by the task.
