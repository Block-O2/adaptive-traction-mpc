# Current Timing Path Audit

- **waypoint segment duration** (human_waypoint_scheduler.py:_plan): Shortest feasible 5 ms registered-grid quintic duration under phase timeout, fixed fractional velocity and acceleration limits, ROM and continuous clearance; endpoint velocity and current emitted reference state enter the polynomial.
- **reference velocity/acceleration fractions** (incremental_clearance_terminal_v9.json:11-12; human_waypoint_scheduler.py:629-632): 0.5 velocity and 0.25 acceleration multiply original task joint limits; same fractions bound pass-through terminal velocity.
- **mechanics duration search** (human_waypoint_feedback_mpc.py:305-347): After mechanics screen rejects shortest reference-feasible schedule, if enabled, search longer 5 ms grid durations until a mechanics-feasible fixed-duration schedule is found.
- **receipt reference governor** (receipt_reference_governor.py:select/commit; runtime.py:3372-3444): Selects only receipt-history acceleration-feasible progress; deferred progress delays realized segment completion; runtime completion checks governor is_complete.
- **RSS/fallback** (runtime.py:2745-3144; safe_fallback.py): Rolling splice, prefetch, fallback and pass-through can alter realized timing while preserving certified reference and safety semantics.
- **terminal/HOLD/recovery** (runtime.py:2609-2846,3602-3644): Measured-state phase transitions, HOLD dwell, terminal commit, recovery and safe fallback can change total task time.
- **confidence/trust** (active runtime, planner, scheduler and v9 options source search): No confidence/trust gamma variable enters this active zero-value/safe-action scientific path; historical confidence pacing is outside it.

The active campaign has no confidence-driven gamma. The existing fixed-duration contract is a candidate for the matched arm, subject to closed-loop validation.
