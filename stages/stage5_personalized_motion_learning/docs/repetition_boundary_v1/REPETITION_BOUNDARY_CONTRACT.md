# Repetition Boundary Architecture v1 — frozen implementation contract

Status: frozen before implementation on branch `codex/repetition-boundary-v1`.
Baseline checkpoint: `518c7b6f44060f06518c080d2348c48e950c34e9`.
Scope: low-ROM Scientific Simulation, zero learned value, one continuous plant and three task repetitions. This is a software smoke, not hardware qualification.

## Ownership

| State | Policy at boundary |
| --- | --- |
| Session identity, repetition index, per-repetition outcomes, boundary history | Persist in the harness session record. |
| Native Human and CR12 q/dq, plant clock and applied physical command | Persist exactly; never teleport to nominal. Store native qpos/qvel and labeled Human/CR12 projections at terminal and settled boundaries. |
| Personalized Human model, updater and adaptation history | Persist the updater and its belief; snapshot the new model for each fresh episode controller. |
| Causal observer belief | Persist. Preserve its long-term belief; reseed only a short window if a measured discontinuity or invalid age requires it, recording that event. |
| Measurement filter/RNG/delivery state | Persist for causal continuity. Acquire new samples; never restamp an old sample. |
| Command response history | Persist as physical evidence, but label each receipt by epoch; do not use a prior episode receipt as a new TRACK source. |
| Value model parameters, replay/learning history, exploration state | Reserved persistent session fields, inert in zero-value mode. Reps 1–5 may later update; after rep 5 primary learned parameters freeze while sensing, feedback and safety stay live through reps 6–30. RL is out of scope now. |
| Task phase and OUTBOUND/HOLD/RETURN machine | New per episode. |
| Trajectory, reference and acceleration history | New per episode, seeded from a newly applied TRACK hold reference at the settled physical state. |
| Planner worker/request/result and activation hooks | New per episode. Prior outstanding work must be closed before transition. |
| Physics epoch, command receipts, scorer/transient force metrics, terminal flags, command-age bookkeeping | New per episode. An explicit boundary controller owns its own settle/hold samples and receipts. |
| Short execution filters | Reset/reseed on new episode only when required for valid source chronology; record provenance. |

## State machine and physical gate

`RETURN -> COMPLETE -> INTER_REP_SETTLE -> INTER_REP_HOLD -> INITIALIZE_NEXT -> OUTBOUND`.

After COMPLETE, close the episode planner and scientific epoch. Continue the same plant from its exact native terminal qpos/qvel and time. During SETTLE use actual native steps with the last physically applied support command, take fresh causal measurements and record cuff force/moment, Human and CR12 q/dq, reference velocity/acceleration, and clearance. Require task start q/dq tolerances, zero reference velocity/acceleration, force/moment and clearance within the existing task/safety limits. Do not modify those limits. HOLD requires at least one full 5 ms control interval with the gate still satisfied. A bounded maximum wait ends in a recorded failure, never a silent teleport. No fixed multi-second hardware wait is asserted.

The boundary''s command and receipt are not a task TRACK receipt. At the new episode epoch, construct a new controller/reference history, take a new measurement, compute and **apply** a fresh TRACK hold command using the settled measured state, and attach the new receipt''s q/dq/reference/mode to the source timestamp before the first planner request. Source sample time must be in the new epoch and owned by that applied receipt. No old terminal receipt or planner result is relabeled as new.

## Accounting and acceptance

`J_F_task` integrates measured cuff force over OUTBOUND+HOLD+RETURN only. `J_F_session` includes task plus the boundary SETTLE/HOLD force integral. Record boundary duration, force/moment integral and peaks separately; report the terminal boundary after each completed repetition when available. Boundary time and cost may not disappear from session metrics.

Before dynamic execution: deterministic persistence, freshness, q/dq continuity, receipt ownership, source/reference chronology, updater and inert RL fields, accounting, and Rep1→Rep2→Rep3 initialization lifecycle tests must pass. Then run one fresh three-rep smoke and one identical-seed/config repeat. Each rep requires COMPLETE, physical PASS, scientific PASS and scorer-v2 PASS; compare repeat results numerically. Preserve every failed run, raw-data manifest and hashes.

At most three repair cycles are allowed for boundary/orchestration/logging/lifecycle defects. Stop if a fix requires controller mathematics, Human dynamics, planner objective, safety thresholds, Scientific Mode semantics, scorer-v2 physical semantics, or major realtime architecture. Do not run 30-rep, headroom, RL or hardware work.
