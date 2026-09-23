# Architecture Recovery V2.2 Phase-3 Human-Waypoint Integration V2

Status: **SUPERSEDED AFTER INDEPENDENT NO-GO AUDIT**

V2 is preserved at result SHA
`c9fa1c0e6954458df1ce9d58cb4ea7f80ff9c69143d10ba301ebe50b85abc12b`.
The independent Auditor confirmed every V1 repair, all 14 checks, all 18
manifest hashes, HOLD reset, mechanics-driven selection, and the truth/RL/path
boundaries. It nevertheless issued NO-GO because the recorded adaptive state
omitted the numeric control-critical effective-geometry tuple, and the exact
test count needed a new unambiguous freeze. V2 remains non-authoritative
negative audit evidence. V3 records numeric geometry and seals the exact
declared 47-test suite without overwriting V2.

Evidence category: mechanical/software interface smoke, not a new formal
scientific experiment and not hardware evidence.

## Integrated production-shape pipeline

The opt-in `phase3_human_waypoint.py` adapter implements:

`fresh deployable state/history -> V2.2 adaptive belief -> direct-Delta-q
state-feedback HWMPC -> adaptive-model wrench mechanics screen -> deterministic
cost plus optional future value -> smooth reference -> feedback`.

The control-sufficient belief carries online-estimated effective geometry,
11-beta dynamics, and the frozen five-feature V2.2 state-residual weights. Its
public update API accepts only estimated q/dq/ddq and applied generalized
torque. Nonlinear soft-limit samples are explicitly excluded because the base
regressor does not contain that layer. Hidden setup/truth is not an accepted
input.

For each candidate schedule, the exact frozen `StateResidualHumanModel`
evaluates inverse dynamics and generalized-wrench allocation at 21 deterministic
samples under the retained `200 N / 60 Nm` simulation limits. This adaptive
screen can reject a candidate and change the selected waypoint, as covered by
an adversarial test. The legacy scheduler itself uses the supplied Human model
only for registered ROM bounds. Its shank/flat-bed clearance uses fixed
`STAGE5_GEOMETRY`/`STAGE5_HUMAN` classified as `STRUCTURAL_PRIOR`; that
clearance layer is not claimed to use online adaptive geometry.

Candidate generation remains direct two-joint waypoint increments from fresh
state. There is no fixed-r/path template, no outbound-path replay on return,
and no historical detailed 5--20 ms robot/interface predictor.

## Event-driven task semantics

The adapter composes the existing `GoalTaskState`/`transition_phase` state
machine with the adaptive waypoint planner. OUTBOUND does not end at a fixed
absolute time. Actual estimated arrival inside the position and velocity set
starts HOLD. Continuous valid HOLD dwell starts RETURN. Any invalid HOLD sample
resets dwell to zero. Actual estimated return/settling ends RETURN and marks
COMPLETE. Time is retained only for reference duration, update/replanning
cadence, hold dwell, runtime measurement, and timeout protection.

The smoke deliberately advanced `2.2 s` while still at the start state and
remained OUTBOUND, then produced the state-driven sequence
`OUTBOUND -> HOLD -> RETURN -> COMPLETE` only after settled state events.

## Value hook and complete transition records

The planner exposes
`V(state_or_belief, candidate_next_waypoint) -> finite scalar cost` after
deterministic feasibility and before candidate ranking. With no callable, the
term is exactly zero. A nonfinite future value fails loudly.

The event-driven wrapper now opens a causal pending transition when a waypoint
is selected and finalizes it only when the next deployable observation arrives.
Every finalized record contains observation, full deployable adaptive belief,
all candidates, selected and executed waypoint, local cost and terms, next
observation, completion/abort result, and versioned provenance. The V2 smoke
ended with three finalized records and no pending record.

No RL, value learning, imitation learning, model training, dataset fitting, or
policy update was performed.

## Frozen V2 validation artifact

Machine artifact:
`results/architecture_recovery_v2/phase3/phase3_human_waypoint_v2/result.json`,
SHA-256 `c9fa1c0e6954458df1ce9d58cb4ea7f80ff9c69143d10ba301ebe50b85abc12b`.
It was written once to the new V2 namespace after repairs and was not
overwritten.

All 14 interface checks passed, including the complete causal transition-record
contract. Three planning calls had mean/p95/max runtime
`41.84/64.03/64.51 ms` in synchronous desktop simulation. That is not a
hardware real-time result. Candidate-screen peaks in this mechanical fixture
stayed below `99.93 N / 21.90 Nm`.

The exact declared frozen-firewall, Phase-3, and legacy HWMPC suite passed
`47/47` on current source. The result seals 18 behavior/config/test files,
including the V2.2 model and estimator, scheduler, state machine, Stage-3/4
dependencies, Phase-3 tests, config, and validator.

## Explicit limitations

- simulation and interface validation only;
- no physical CR12 actuation, human testing, or sensor-frame calibration;
- no hardware deadline validation;
- no detailed robot reach/collision/torque prediction in this layer;
- acceleration-limit authority is marked unavailable at this four-state
  interface instead of being fabricated;
- scheduler bed clearance remains a fixed structural-prior model;
- the formal high-ROM claim remains bounded by Human-V2 `80/100 deg` ROM and
  the analytical shank/flat-bed mechanics model.
