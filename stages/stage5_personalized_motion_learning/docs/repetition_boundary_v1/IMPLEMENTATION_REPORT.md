# Repetition Boundary Architecture v1 implementation

The historical V1–V3 evidence and harness WIP were committed at `518c7b6` before creating `codex/repetition-boundary-v1`. The frozen contract is `REPETITION_BOUNDARY_CONTRACT.md`.

Persistent state: one native plant (Human and CR12 q/dq, time and applied command), personalized Human updater and model belief, causal observer, measurement layer and its filter/RNG/delivery state, physical command response history, session identity/index/history, and inert future value/replay/exploration fields. The latter are represented by `PersistentSessionState`; primary learned parameter freeze is reserved from repetition 6 onward, with RL inactive in this smoke.

Episode-local state: task phase, trajectory/reference history, planner requests/results, physics epoch receipts, supervisor, acceleration monitor, authority, scorer/trace, terminal hooks, command age and per-rep metrics. The new runtime is built from a narrow allowlist after the old epoch and planner close.

At COMPLETE, `advance_inter_rep_boundary` enters SETTLE then HOLD. It keeps the same plant and actually steps native physics under its existing command; at each 5 ms boundary it takes a new causal observation and checks the existing start set, reference rest, force/moment limits, CR12 velocity and clearance. It holds for a full 5 ms interval and caps total waiting at 2 s. It records native qpos/qvel, Human/CR12 q/dq, duration and measured wrench cost. A failed gate or timeout is a preserved failure.

The next epoch starts with fresh planning and reference objects. Its causal split monitor acquires a new 5 ms sample under the physical continuing command. A newly computed TRACK hold command is then actually applied at a new measurement source; that new receipt owns the next sample's reference before any task planner request. The prior terminal/support receipt remains physical history and is never relabeled TRACK. Command response history remains continuous using session-global response receipt IDs, while TRACK lookup uses episode-local physics receipt indices.

`J_F_task` integrates only task intervals. `J_F_session` adds outgoing explicit boundary SETTLE/HOLD cost and incoming bootstrap interaction cost; boundary force/moment integrals and durations remain separately visible. No force interaction is hidden by waiting.

Validation: 33 targeted deterministic/scientific timing tests PASS; one preserved failed smoke; one permitted repair cycle; then two complete identical-seed three-rep groups PASS with exact selected numerical repeatability. The raw manifest and fingerprint accompany this report. This validates only the low-ROM Scientific Simulation software boundary. It does not authorize the 30-rep baseline, headroom, RL or hardware work.
