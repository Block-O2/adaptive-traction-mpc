# Stage 5: Personalized Motion Learning

Stage 5 is a new workspace for repeated rehabilitation-motion research. It
does not modify or reinterpret the frozen Stage-4 scientific evidence.

The intended later research setting is a session of roughly 30 repetitions.
The first repetitions may use slow, conservative exploration; the research
target is rapid personalization in roughly 3--5 repetitions, followed by a
stable, standardized motion strategy with low interaction force. Later work
may optimize or learn the `q1`/`q2` coordination rather than only tracking a
prescribed joint trajectory. Cumulative physical interaction force over the
whole motion is a key future objective.

Model-based MPC/CEM and the existing executable screening, Safety Filter, and
BRAKE execution stack remain the foundation. Geometry v1 is complete. The
verified engineering configuration is frozen as `Stage-5 Plant v1`: a
high-stiffness translational interface plus finite rotational compliance for a
tightly strapped but not perfectly rigid cuff. It remains a provisional,
non-hardware-calibrated surrogate. The checkpoint contains no RL, trajectory
learning, clinical safety claim, or new force threshold.

## Current checkpoint

The loaded execution authority, acceleration semantics, and explicit
interface prediction state remain unified. The matched deterministic episode
now completes `OUTBOUND -> HOLD -> RETURN -> COMPLETE`. The runtime checkpoint
removes duplicated candidate-specific loaded/interface work without changing
control semantics: the final engineering run is 18.18 ms mean and 19.16 ms p95
for the 20 ms Goal-MPC period, with 2/202 isolated deadline misses. Its 37.43 ms
wall-clock maximum prevents a hard worst-case claim. Interface mismatch and
learning have not started.

- `configs/stage5_geometry_mechanics_v1.json`: single provisional parameter
  record and preserved geometry checkpoint.
- `configs/stage5_rigid_interface_candidates.json`: audited K/D candidate set.
- `configs/stage5_geometry_mechanics_v2.json`: frozen `Stage-5 Plant v1`
  engineering configuration; geometry is explicitly unchanged from v1.
- `src/traction_mpc_stage5/`: minimal Stage-5 layer that reuses the Stage-3
  robot, Human V2 mechanics, cuff interface, IK, and execution plant without
  editing Stage 3 or Stage 4.
- `configs/stage5_goal_task_v1.json` and `src/traction_mpc_stage5/task.py`:
  provisional, configuration-driven goal task plus pure immutable
  `OUTBOUND -> HOLD -> RETURN -> COMPLETE/ABORTED` state machine. It supplies
  no full joint trajectory, coordination ratio, path corridor, MPC, or RL
  behavior.
- `src/traction_mpc_stage5/task_observation.py`: immutable state/timestamp
  contract with a 20 ms staleness limit. Its direct robot-side pose helper is
  retained only for v1 regression/audit; v1.1 control receives its state from
  the interface-aware observer and contains no MuJoCo Human truth.
- `configs/stage5_controller_nominal_interface_v1.json` and
  `src/traction_mpc_stage5/controller_interface.py`: independent provisional
  controller nominal interface model, causal Human-side state observer, and
  batched spring-damper action-hold predictor. The controller module never
  imports or reads plant-truth interface parameters/state.
- `src/traction_mpc_stage5/goal_mpc.py`: first reference-free Human-space CEM
  adapter with phase target, goal/terminal cost, inherited action/slew and
  optional cuff terms, candidate-dependent execution screening, and terminal
  learned value fixed to zero. v1.3 propagates the controller-nominal
  translation/rotation interface and transmitted physical wrench through the
  full batched horizon. HOLD uses the `GoalTaskSpec` angle/velocity set with a
  safety-hard minimum-violation recovery fallback when the sampled set is
  temporarily unreachable; OUTBOUND/RETURN remain path-free.
- `src/traction_mpc_stage5/hold_stabilizer.py`: Stage-5-only loaded-equilibrium
  solver, deterministic local computed-torque HOLD controller, explicit loaded
  robot-pose execution adapter, and command-continuous MPC-to-HOLD handoff. It
  consumes only deployable Human/interface estimates and preserves the existing
  Safety Filter/BRAKE chain.
- `docs/GOAL_MPC_V1_ENGINEERING_SMOKE.md`: retained engineering-smoke result
  and blocker diagnosis. The current v1 reaches the physical force gate before
  task completion and is not a promoted baseline.
- `docs/GOAL_MPC_V1_CONSISTENCY_AUDIT.md`: synchronized state, force-chain,
  and runtime audit of the retained attempt-02 failure; no controller change
  or learning is introduced.
- `docs/GOAL_MPC_V11_ENGINEERING_REPORT.md`: v1.1 implementation and matched
  engineering result. Deterministic state/force/runtime issues are materially
  improved, but the unchanged objective does not sustain the 0.5 s HOLD and
  the episode ends at `TIMEOUT_HOLD`; mismatch execution and learning remain
  blocked.
- `docs/GOAL_MPC_V12_ENGINEERING_REPORT.md`: phase-aware objective definition
  and retained matched-model smoke. The added HOLD running costs reduce
  velocity oscillation but still do not satisfy the continuous 0.5 s HOLD;
  interface mismatch testing remains blocked.
- `docs/GOAL_MPC_V13_ENGINEERING_REPORT.md`: full-horizon nominal-interface
  rollout, completion-aligned HOLD-set semantics, retained matched smoke, and
  synchronized diagnosis. The matched episode still times out in HOLD because
  the simple interface drive surrogate does not predict future executable
  robot/feedback dynamics accurately enough; mismatch testing remains blocked.
- `docs/LOADED_HOLD_ENGINEERING_REPORT.md`: nonzero loaded equilibrium, local
  perturbation tests through 10 s, and actual Goal-MPC-arrival handoff. The
  matched smoke achieves a real continuous 0.5 s HOLD and enters RETURN; it
  intentionally stops there without redesigning RETURN.
- `docs/GOAL_MPC_COMPLETE_V1_ENGINEERING_REPORT.md`: first complete matched,
  non-learning `OUTBOUND -> HOLD -> RETURN -> COMPLETE` episode, including both
  command-continuous handoffs, the actual path, retained failed transition
  attempt, and complete force/state/runtime evidence.
- `docs/MOTION_ENVELOPE_COMPLETION_CHECKPOINT.md`: provisional independent
  q velocity/acceleration limits, evaluation-only completion-margin audit,
  Stage-5 hot-path optimization, and the retained matched `NO_SAFE_ACTION`
  startup result that blocks interface mismatch.
- `docs/SUPPORT_CENTERED_GOAL_MPC_CHECKPOINT.md`: Stage-1--4 support audit,
  Stage-5 `u_support + delta_u_motion` CEM parameterization, loaded time-zero
  initial condition, retained matched attempt, and the deterministic
  support/motion execution blocker. The attempt satisfies the motion envelope
  but moves away from the outbound goal and aborts before HOLD.
- `docs/SUPPORT_MOTION_EXECUTION_SEMANTICS_AUDIT.md`: exact Human-input
  equivalence check, complete Goal/HOLD reference-authority trace, and a
  same-snapshot five-branch 50 ms paired response. It confirms that the
  decomposition is mathematical, while the loaded-pose execution authority is
  inconsistent. No controller behavior is changed.
- `docs/LOADED_EXECUTION_AUTHORITY_V1.md`: unified loaded Human/robot cuff
  pose, twist, interface-state, and wrench-reference-point contract; exact
  support-only and paired-increment checks; and the retained matched
  `TASK_ACCELERATION_LIMIT` result. No MPC weight or motion-envelope value is
  changed.
- `docs/ACCELERATION_SEMANTICS_V1.md`: synchronized predicted, deployable
  realized, and evaluation-only acceleration meanings; saved-trace audit; and
  the retained matched `NO_SAFE_ACTION` result under unchanged limits.
- `docs/GOAL_MPC_FEASIBILITY_LOSS_AUDIT.md`: exact reconstruction of the
  0.440 s feasibility loss, shifted-plan and deterministic-continuation checks,
  and the interface predictor history-state mismatch that blocks a justified
  feasibility-retention mechanism.
- `docs/EXPLICIT_INTERFACE_PREDICTION_STATE_V1.md`: explicit, versioned
  interface/base-drive prediction state; cross-solve shifted-plan validation;
  and the first complete matched episode after removing hidden drive resets.
- `docs/GOAL_MPC_RUNTIME_OPTIMIZATION_V1.md`: before/after section profile,
  repeated-work invariance audit, semantic-equivalence evidence, final matched
  episode, deadline-miss count, and remaining runtime bottleneck.
- `docs/DETERMINISTIC_BASELINE_CHECKPOINT.md`: frozen pre-mismatch controller
  contract, compact evidence checksum, explicit non-learning boundary, and
  local evidence-retention policy.
- `scripts/run_stage5_geometry_validation.py`: engineering/smoke validation;
  it is not a formal scientific experiment.
- `tests/`: geometry, frame, mechanics, visualization, and regression checks.
- `docs/STAGE5_PLAN.md`: staged research direction and scope guardrails.
- `docs/STAGE5_RESEARCH_PLAN.md`: approximately 30-repetition research roadmap
  for online Human identification, goal-directed CEM-MPC, and a published
  long-term state value.
- `docs/STAGE5_TASK_CONTRACT.md`: outbound--hold--return task, true completion,
  force decomposition, objectives, and hard-constraint boundary.
- `docs/STAGE5_LEARNING_CONTROL_CONTRACT.md`: frozen estimator/MPC/value/safety
  responsibilities, transition-data schema, current interface audit, and the
  minimal Stage-5-only migration away from a prescribed trajectory.
- `docs/GEOMETRY_MECHANICS_REPORT.md`: audited baseline and observed validation
  results for this checkpoint.
- `docs/RIGID_INTERFACE_CALIBRATION.md`: mechanics audit, force/deformation
  scale, timestep evidence, ROM checks, selection, and limited replay results.

Regenerate the rigid-interface calibration (engineering/smoke evidence only):

```bash
MPLCONFIGDIR=/tmp/stage5_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_rigid_interface_calibration.py
```

Run the explicitly limited no-learning baseline replay:

```bash
MPLCONFIGDIR=/tmp/stage5_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_limited_baseline_replay.py
```

Run the reference-free Goal-MPC engineering smoke into a new output directory:

```bash
MPLCONFIGDIR=/tmp/stage5_goal_mpc_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_goal_mpc_smoke.py \
  --output-dir stages/stage5_personalized_motion_learning/results/goal_mpc_v13/new_attempt
```

Reproduce the focused attempt-02 consistency audit:

```bash
MPLCONFIGDIR=/tmp/stage5_goal_mpc_audit_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_goal_mpc_prediction_execution.py
```

Reproduce the small support/motion semantics audit into a new output directory:

```bash
MPLCONFIGDIR=/tmp/stage5_support_motion_audit_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_support_motion_semantics.py \
  --output-dir stages/stage5_personalized_motion_learning/results/support_motion_semantics_audit_v1/new_attempt
```

Reconstruct the focused Goal-MPC feasibility loss into a new diagnostic output:

```bash
MPLCONFIGDIR=/tmp/stage5_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_feasibility_loss.py \
  --output-dir stages/stage5_personalized_motion_learning/results/feasibility_retention_v1/new_reconstruction
```

Run the Stage-5 checks from the repository root:

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn pytest -q \
  stages/stage5_personalized_motion_learning/tests
```

Regenerate the engineering report data and schematics:

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_geometry_validation.py
```
