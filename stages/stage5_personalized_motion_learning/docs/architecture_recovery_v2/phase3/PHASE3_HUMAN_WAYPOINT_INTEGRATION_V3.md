# Architecture Recovery V2.2 Phase-3 Human-Waypoint Integration V3

Status: **PASS — independently audited; PHASE_3_READY**

Evidence category: mechanical/software interface smoke, not a new formal
scientific experiment and not hardware evidence.

## Final repaired interface

The opt-in adapter implements:

`fresh deployable state/history -> complete V2.2 adaptive belief -> direct
Delta-q state-feedback HWMPC -> adaptive-model wrench mechanics screen ->
deterministic cost plus optional future value -> smooth reference -> feedback`.

The recorded adaptive belief now contains the finite numeric control-effective
geometry tuple (world planar basis, hip position, thigh length, and
knee-to-cuff vector), 11-beta dynamics, state-residual weights/limit, update
counts, sequence, and source categories. These are exactly the deployable model
inputs used to reconstruct the frozen `StateResidualHumanModel`; no hidden
plant or evaluation field is present.

Every candidate schedule is evaluated at 21 deterministic samples by adaptive
inverse dynamics and generalized-wrench allocation under the retained
`200 N / 60 Nm` simulation limits. An adversarial test proves this screen can
reject the nominal greedy candidate and select another feasible waypoint.

The legacy scheduler uses its supplied model only for registered Human ROM.
Its shank/flat-bed clearance uses fixed `STAGE5_GEOMETRY`/`STAGE5_HUMAN`,
explicitly classified as `STRUCTURAL_PRIOR`; that layer is not claimed to use
adaptive geometry. Candidate generation remains direct two-joint increments,
with no fixed-r/path replay or historical detailed robot/interface predictor.

## Event/task and learning-record semantics

Actual estimated arrival/settling starts HOLD, continuous valid dwell starts
RETURN, any invalid HOLD sample resets dwell to zero, and actual estimated
return/settling ends RETURN. Absolute matched-pacing times do not own phase
transitions.

The clean future hook is
`V(state_or_belief,candidate_next_waypoint) -> finite scalar cost`. It runs
after deterministic feasibility, defaults exactly to zero, and fails on a
nonfinite value. No training was performed.

When a waypoint is selected, the interface opens a pending causal transition.
Only the next deployable observation finalizes it. Each finalized record has
observation, complete deployable adaptive belief, candidates, selected/executed
waypoint, local cost/terms, next observation, completion/abort, and versioned
provenance. The smoke produced three finalized records and no pending record.

## Frozen V3 evidence

Machine artifact:
`results/architecture_recovery_v2/phase3/phase3_human_waypoint_v3/result.json`,
SHA-256 `646f44dcf2c7fb9c695710a92eb3e9523fddd987cc69d3498a447d1effb9334a`.
It was written once in the new V3 namespace.

All 14 interface checks passed. Three planning calls had mean/p95/max runtime
`42.20/64.91/65.48 ms` in synchronous desktop simulation. Candidate-screen
peaks stayed below `99.93 N / 21.90 Nm`. This is not hardware real-time
evidence.

The config freezes the exact three test files and expected collection count.
Collection returned 47 tests and the exact suite passed `47/47` in `47.55 s`.
The result seals 19 behavior/config/test files. A post-run verification found
zero manifest mismatches.

The independent Auditor separately confirmed the artifact SHA, 14/14 checks,
19/19 manifest hashes, all three finalized transitions, full numeric geometry,
causal next-observation linkage, state-driven semantics, mechanics-driven
selection, zero-default value hook/no training, and truth/path/predictor
boundaries. Its exact suite independently collected and passed `47/47` in
`47.41 s`.

Exact reproducibility command (the Stage-5 `scripts` path is required because
the state-feedback regression imports two script modules):

```bash
MPLCONFIGDIR=/tmp/arv2_phase3_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts \
conda run --no-capture-output -n mpc_learn python -m pytest -q \
  stages/stage5_personalized_motion_learning/tests/architecture_recovery_v2/test_functional_firewall.py \
  stages/stage5_personalized_motion_learning/tests/architecture_recovery_v2/test_phase3_human_waypoint.py \
  stages/stage5_personalized_motion_learning/tests/test_stage5_hwmpc_state_feedback_v1.py
```

## Limitations

- simulation/interface validation only;
- no physical CR12 actuation, human testing, or sensor-frame calibration;
- no hardware deadline, robot reach/collision/torque, physical cuff, or
  clinical validation;
- scheduler bed clearance remains a fixed structural-prior model;
- the formal high-ROM claim remains within Human-V2 `80/100 deg` ROM and the
  analytical shank/flat-bed mechanics family;
- no RL, value, imitation, or policy training occurred.
