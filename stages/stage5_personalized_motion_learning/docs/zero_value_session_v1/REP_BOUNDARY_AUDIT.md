# Zero-value Rep2/Rep3 boundary audit (V3)

## Scope and preserved evidence

Branch `codex/zero-value-session-v1` starts at `b2a8d3bb8716859bd3cad9f7e834b8f02112658f`. The V1 `session_smoke_01` and V2 `session_smoke_02` raw attempts and their reports remain unchanged. V2 Rep2's stack trace points to `AppliedReferenceMotionHistory.__init__` in `runtime.py` before task execution.

The registered case is `balanced_ordinary_r01`, case SHA-256 `ceb33e9eeb243d49ad4bd1ad0a17637243219f3e058f4da0aaf2ed9fbf975b2d`, with Scientific Simulation, deterministic IK seed 20260918, host delay 0, and unchanged recovery config.

## Static API and ownership trace

| Path | Contract and V3 audit result |
|---|---|
| Rep1 terminal → Rep2/3 entry | Previous scientific epoch must be inactive and prior lifecycle must have no outstanding plan; plant time must exactly match the published boundary. `_resume_session_runtime` enforces these checks before copying the allowlist. |
| Reference history | Existing constructor accepts `(clock, initial_q, initial_dq, initial_time_s)`. V2 resumed path supplied `(q,dq,ddq)`. V3 `_start_applied_reference_history` passes only q/dq/time and seeds resumed history at registered start; no lower-level history semantics changed. |
| Commissioning-only fields | V2 resumed path would next have read missing `initial_support_state` while constructing skipped commissioning waypoints. V3 applies that correction only on the initial repetition. No commissioning fit or active recovery is rerun on resume. |
| Measurement and estimator | Plant, measurement layer, causal observer, command-response history, updater, fit, and Human belief carry across episodes. The scientific epoch's initial capture now uses `initial=False` on resume, preserving measurement filter/RNG/delivery history while acquiring a fresh boundary observation. |
| Task and phase | `start_episode` constructs a new `GoalTaskState`; schedule, async pending request, phase transitions, arrival/dwell/RETURN state, and sensor task clock are per-call locals or newly created runtime fields. No previous task state is in the carryover allowlist. |
| Planner/reference | New contract, scheduler, planner, scientific physics epoch, `ScientificPlanLifecycle`, reference history, and episode epoch are built for each repetition. Previous plan/request/activation hooks and trajectory history are excluded by the carryover allowlist. |
| Scorer and metrics | New `FastTruePhysicsMonitor`, trace, task decisions, safety counter, force/moment accumulators, and per-repetition output directory. Scorer-v2 reads that repetition's files. No previous scorer result is reused. |
| Config, seed, index, logging | Harness checks frozen case hash and thread settings; all reps use the same case/config and one process. Distinct `rep_01`–`rep_03` directories and simulation-version episode epochs identify repetitions. Zero-value parser requires explicit score status, accepts only scored zero or explicitly unscored null, and rejects nonzero learned value. |
| Terminal hooks | Native physics epoch is caught up and marked inactive, runtime maintenance released, pending plan lifecycle closed, then summary/trace/artifacts are saved and session context published. The next repetition checks closure and native time before initialization. |

## Lightweight lifecycle evidence

`test_zero_value_session_lifecycle_v3.py` exercises the actual session glue helpers for Rep1 initialize/finalize → Rep2 initialize/finalize → Rep3 initialize/finalize with lightweight physics/lifecycle fakes. It calls the real applied-reference constructor. The test asserts preserved plant, updater sequence, observer, measurement layer, and command-response history; new contract/history/epoch/lifecycle; fresh episode IDs; no carried task/scorer/terminal objects; and rejection of an unclosed epoch or changed plant time. This is a contract/API test, not a substitute for MuJoCo execution.

## Remaining dynamic checks

The fresh V3 session must still demonstrate actual Rep2 and Rep3 task completion, physical/scientific/scorer-v2 PASS, exact native boundary continuity, model progression, fresh start reference, absent stale objects, zero-value logging, measured wrench integrals, and repeatability. If a new session glue/API/lifecycle failure occurs, stop without a fourth dynamic attempt and report `ZERO_VALUE_SESSION_BOUNDARY_AUDIT_REQUIRED`.

## V3 observed gap and required next audit

V3 Rep2 failed at the first task planning request in `receipt_reference_at_sample`: the fresh epoch records an applied continuing-support receipt without `mode=TRACK`, while the request requires a TRACK receipt at its immutable sensor source. The lightweight lifecycle test mocked physics/lifecycle and did not drive this receipt-to-request path. Audit the actual `WallPhysicsSession` initial receipt, prior terminal command and reference mode/provenance, `CausalMeasurementLayer` delivered sample timestamp, `AppliedReferenceMotionHistory` seed, `ScientificPlanLifecycle.request`, and `receipt_reference_at_sample` together. Add a deterministic cross-epoch receipt ownership test covering the first Rep2 and Rep3 task requests before considering any future dynamic authorization. Rep1→2 task completion/scoring and the entire Rep2→3 boundary remain unverified. V3 escalation forbids a fourth immediate dynamic attempt.
