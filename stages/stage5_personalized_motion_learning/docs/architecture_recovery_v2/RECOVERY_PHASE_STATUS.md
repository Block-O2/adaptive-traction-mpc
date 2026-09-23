# Architecture Recovery V2 Phase Status

Terminal status: **PHASE_3_READY**.

Recorded: 2026-09-22, Asia/Shanghai.

## Campaign provenance

- Starting/current branch: `codex/stage5-architecture-recovery`.
- Starting/current HEAD: `4caea258ec1450f082bb7cb8097cc1441bdf589f`.
- Pre-existing dirty and untracked research state was preserved.
- Normalized formal-run status hash:
  `af092bfd10b0c567eb863b84149d969a1c7eb6343e05b31e7699ad4e36ce48d0`.
- No branch switch, stage, commit, push, reset, stash, merge, or deletion was
  performed. No physical robot or human experiment was performed.

## Phase gates

- Phase 0 reproduction: **PASS**, independently approved.
- Phase 1B--F freeze qualification: **PASS**, independently approved.
- Original V2 fresh formal: **PHASE_2_FAIL**, preserved.
- V2.1 fresh formal: **PHASE_2_FAIL**, preserved.
- V2.2 development/freeze/fragility audit: **PASS**, independently approved.
- V2.2 fresh formal Phase 2: **PHASE_2_PASS**, independently reproduced.
- Phase 3 adaptive Human-waypoint integration: **PASS** for the required
  mechanical/software interface, independently audited on V3;
  `PHASE_3_READY` reached.

## Formal V2.2 result

The seven-arm, 24-case paired matrix completed all 168 rows, and all 46 frozen
checks passed. V2.2 completed `24/24` with median/p95 full-horizon RMSE
`0.477010/0.701653 deg`, full-episode peaks `172.948 N/29.955 Nm`, and zero
registered ROM, analytical clearance, consistency, settle-timeout, solver,
supervisor, or safety events. It improved commissioning-only median by
`21.3701%`, just above the frozen `20%` branch. Oracle completed `24/24` at
`0.424069/0.622307 deg`; candidate-oracle median gap was `0.05294 deg`.

Fixed nominal completed `0/24`, wrong geometry plus adaptive dynamics `4/24`,
and no dynamics adaptation `6/24`. V2.1 remained a non-gating diagnostic and
had a `1.60%` lower median than V2.2; no V2.2-over-V2.1 superiority claim is
made.

The Auditor verified the 10-file execution seal, 62 source snapshots, all seed
pairing, finite/bounded residual telemetry, zero cap/projection hits, and no
deployable truth consumption. Formal result SHA is
`bef5169580a7038d51f5f402096cfe95545cdd8655c9e200b6c627770f446cf2`.

## Phase-3 interface

The frozen V2.2 adaptive belief now drives a deterministic wrench-mechanics
screen inside the existing state-feedback Human-waypoint planner. The legacy
scheduler uses its model only for registered ROM; shank/bed clearance remains
a fixed Stage-5 `STRUCTURAL_PRIOR`, not adaptive geometry. The
planner continues to generate direct two-joint waypoint increments from fresh
deployable state, without fixed-r paths or the old detailed robot/interface
predictor. The existing task state machine supplies event-driven semantics:
actual arrival/settling starts HOLD, continuous valid dwell starts RETURN, and
actual return/settling ends RETURN.

A clean `V(state_or_belief,candidate_next_waypoint)` hook ranks only feasible
candidates. Its absent/default contribution is exactly zero. Every adaptive
state record includes numeric effective geometry, beta, residual weights,
update counts and provenance; all belief,
candidate, mechanics, cost, and selection records are learning-ready. No RL,
value-learning, imitation-learning, or policy training occurred.

The versioned V3 Phase-3 mechanical/software artifact passed all 14 checks,
including causal next-observation transition finalization; the combined frozen
firewall, Phase-3, and legacy HWMPC tests passed `47/47`. This is simulation/interface readiness,
not hardware real-time, robot-reach, collision, physical cuff, or clinical
validation.

## High-ROM boundary

Fresh formal high-ROM goals covered q1 `66.244--74.175 deg` and q2
`82.234--94.575 deg`; V2.2 and oracle completed all 12 high-ROM cases with zero
registered ROM and analytical shank/flat-bed clearance events. The Human-V2
plant remains limited to `80/100 deg`; 120--130 deg remains outside the model
contract.

## Scientific-change ledger

- Frozen V2.2 change relative to V2.1: constant task residual replaced by the
  preregistered state-conditioned five-feature residual; continual beta and all
  other formal settings remained fixed.
- Phase-3 code change: integration/interface only; no Phase-2 source, formal
  gate, seed, threshold, cost weight, physical parameter, constraint, noise,
  target, solver, or rollout duration changed after formal freeze.
- Historical evidence and all negative runs remain preserved.
