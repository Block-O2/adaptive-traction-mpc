# PHASE_3_READY

Recorded: 2026-09-22, Asia/Shanghai.

## Outcome

The architecture-recovery campaign reached the authorized terminal condition.
Phase 1B--F is independently frozen, fresh V2.2 formal Phase 2 passed every
preregistered gate, and the recovered deployable adaptive belief now drives a
state-feedback Human-waypoint HWMPC interface with event-driven task semantics
and a clean future value-learning hook. No learning was trained.

## Recovery history and freeze

Earlier results are preserved rather than rewritten. Original V2 and V2.1 each
failed only the commissioning-only gate despite strong absolute tracking.
Recency-window, phase-bank, and residual-only development alternatives were
also preserved as negative/rejected evidence. The successful V2.2 revision
replaced only the constant task residual with bounded normalized-LMS weights
over `[1,q1_ROM,q2_ROM,dq1_sat,dq2_sat]`; continual beta remained active.

V2.2 passed all 31 development checks and an independent fragility/freeze
audit. Its fresh 168-row formal result passed 46/46 frozen checks. The narrowest
gate was commissioning-only median improvement: `21.3701%` against `20%`.
V2.2 completed `24/24` at median/p95 `0.477010/0.701653 deg` and
`172.948 N/29.955 Nm`; oracle completed `24/24`; fixed nominal `0/24`; wrong
geometry `4/24`; no dynamics adaptation `6/24`; commissioning-only `23/24`.
All V2.2 registered mechanics/supervisor/solver/safety event counts were zero.

The independent Auditor reproduced the exact paired matrix, all metrics and
gates, ten-file seal, 62 source snapshots, truth-firewall data flow, and
bounded adaptation telemetry. V2.1's non-gating median was `1.60%` better, so
no unsupported V2.2-over-V2.1 superiority claim is made.

## Phase-3 architecture

The new opt-in adapter exposes:

`deployable observation/history -> V2.2 adaptive belief -> fresh-state
Human-waypoint candidates -> adaptive mechanics feasibility -> deterministic
cost + optional value -> smooth reference -> feedback/replan`.

The adaptive wrench-mechanics screen is built from effective geometry, online
beta, and V2.2 state-residual weights. The full numeric effective geometry,
beta, weights, update counts, and provenance are retained in each adaptive
state record. Public updater inputs
are estimated q/dq/ddq and applied generalized torque only. Hidden truth is not
accepted. Candidate schedules are screened deterministically under the retained
simulation force/moment limits. The legacy scheduler uses the supplied model
only for registered ROM; its shank/bed clearance remains fixed Stage-5
`STRUCTURAL_PRIOR` geometry. Candidate generation remains direct two-joint
Delta-q, with no fixed-r path and no old detailed robot/interface predictor.

The task interface uses actual arrival/settling for OUTBOUND->HOLD, continuous
valid dwell for HOLD->RETURN, and actual return/settling for RETURN->COMPLETE.
Absolute `2.2/0.5/2.2 s` matched pacing does not own production transitions.

The value insertion point is
`V(state_or_belief,candidate_next_waypoint)`. It runs after feasibility and
before ranking and returns a finite scalar that defaults to exactly zero. A
pending record is finalized on the next deployable observation with the full
belief, candidates, selected/executed waypoint, local cost, completion/abort,
and provenance. No RL/value/imitation training occurred.

## Validation and limits

Versioned Phase-3 V3 mechanical/interface smoke passed 14/14 checks and demonstrated
`OUTBOUND -> HOLD -> RETURN -> COMPLETE` from state events, including remaining
OUTBOUND after an artificial `2.2 s` step without arrival. The combined frozen
V2 firewall, Phase-3, and legacy HWMPC regression run passed `47/47`.
The V3 artifact SHA is
`646f44dcf2c7fb9c695710a92eb3e9523fddd987cc69d3498a447d1effb9334a`;
all 19 sealed dependencies revalidated with zero mismatch.
The independent Auditor repeated the 14 checks, 19 hashes, causal-record audit,
and exact 47-test suite and issued the terminal PASS verdict.

Fresh formal high-ROM goals reached q1 `74.175 deg`, q2 `94.575 deg` inside
the verified `80/100 deg` Human-V2 ROM. This does not support 120--130 deg.
All results are simulation/offline only. The campaign did not validate physical
CR12 reach/collision/torque behavior, sensor-frame wrench calibration, hardware
deadlines, human safety, or clinical suitability.

## Repository and provenance

- Branch/HEAD stayed `codex/stage5-architecture-recovery` /
  `4caea258ec1450f082bb7cb8097cc1441bdf589f`.
- Pre-existing dirty/untracked work was preserved.
- Formal-run normalized status hash remained
  `af092bfd10b0c567eb863b84149d969a1c7eb6343e05b31e7699ad4e36ce48d0`.
- No branch switch, stage, commit, push, reset, stash, merge, or material-file
  deletion occurred.
- No physical actuation occurred.

## Recommended next step

Independently review and freeze a versioned Phase-4 data-collection contract
for the existing zero-default value hook before collecting any learning data.
