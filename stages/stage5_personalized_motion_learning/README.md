# Stage 5: Personalized Motion Learning

Interface-study status: **closed as a limited negative result**. The final
campaign remains `EXIT C`, Acceleration-Semantics V2 did not resolve the 5 ms
physical-transient underprediction, and runtime telemetry remains `B6 —
unresolved`. See `docs/INTERFACE_STUDY_CLOSEOUT.md` and its compact manifest.
Further interface identification/predictor work is paused pending CR-12/cuff
hardware evidence. Subsequent Human-ID work uses a fixed nominal Plant-v1
interface and fixed nominal controller interface model.

Human-ID shadow v1 now concludes **H-B — reparameterize/reduce**. The full
Stage-4 beta11 model is numerically full-rank on complete Stage-5 episodes but
practically almost perfectly correlated; a three-scale control-effective
projection is materially better conditioned. No Human model is applied to
control and no closed-loop A/B is preregistered. See
`docs/HUMAN_ID_ARCHITECTURE_AUDIT.md` and
`docs/HUMAN_ID_SHADOW_V1_RESULTS.md`.

The preregistered reduced three-scale shadow validation subsequently concludes
**R-C — Human ID not useful enough**. Complete episodes are well conditioned
in the reduced coordinates, but no challenger established embargoed future
publication support; three mismatch cases also hit the unchanged acceleration
envelope before useful qualification. Control remains nominal and frozen. See
`docs/HUMAN_ID_REDUCED_SHADOW_V1_RESULTS.md` and its compact JSON summary.

The separate multi-repetition confidence-pacing feasibility study concludes
**P-B — pacing helps, trust still too slow**. Historical Stage-4 confidence
defaults map only to a scalar Goal-MPC planning-velocity ceiling; they do not
create a reference clock or scale support, HOLD, or registered motion limits.
Stiffness+15% survives long enough for a shadow publication, but mass+8% and
the mixed mismatch still repeatedly abort at minimum pacing before collecting
clean fit blocks. All Goal-MPC episodes continue to use the fixed nominal Human
model. See `docs/HUMAN_ID_CONFIDENCE_PACING_V1.md` and its compact JSON summary.

A subsequent saved-trace-only signal-authority audit leaves the acceleration
monitor **A-MONITOR-UNRESOLVED**: 20 ms estimated-velocity history removes the
known Human-ID conservative aborts and detects the retained `Kt x0.7` event,
but misses the separate early 5 ms physical-transient stress event. The gamma
outcomes themselves are evidence-consistent, while a non-exercised
current-model-trust persistence edge case is classified
**P-TRUST-WIRING-GAP**. No monitor or pacing behavior is changed. See
`docs/ACCELERATION_PACING_SIGNAL_AUTHORITY_AUDIT.md`.

The isolated current-model trust persistence gap is now corrected and validated
as **T-A — TRUST PERSISTENCE FIX VALIDATED**.  Trust is binary and explicitly
owned by the Human model version used by Goal-MPC: neutral/inconclusive later
challenger evidence preserves already-earned support, explicit negative
current-model evidence may revoke it, and a new control-model version cannot
inherit it.  A nominal two-repetition A/B kept all controller and safety
settings fixed; the persistent arm retained support and ended Rep 2 at gamma
1.0, while shadow Human parameters remained excluded from control.  See
`docs/TRUST_PERSISTENCE_V1.md`.

The subsequent saved-trace-only Human-model update audit reuses the already
implemented Stage-4-style bounded step (`eta=0.10`, 3% of parameter span per
component) and explicitly separates current model, raw challenger, and
provisional bounded successor.  The actual bounded successor was already the
model evaluated by historical future validation.  Later saved data preserve a
useful mean direction for damping/stiffness, while the unchanged HAC rule keeps
all post-decision classifications NEUTRAL; no arbitrary threshold was added.
Decision: **U-A — BOUNDED UPDATE READY FOR ONE-STEP CLOSED-LOOP A/B**, design
only.  No Human model is applied to control in this checkpoint.  See
`docs/HUMAN_MODEL_BOUNDED_UPDATE_V1.md`.

The authorized damping +20% closed-loop A/B then applied exactly one causally
qualified bounded successor with gamma fixed at 0.5.  The transition was
versioned and command-continuous; both fixed and one-step arms completed with
no safety-chain event.  Although 26/29 genuinely later prediction blocks favored
the successor, the unchanged HAC scheduled looks remained NEUTRAL.  Decision:
**C-B — MECHANISM WORKS, EVIDENCE INSUFFICIENT**.  Progressive updates and
trust-driven pacing remain disabled.  See
`docs/HUMAN_MODEL_ONE_STEP_AB_V1.md`.

The frozen successor was then tested without refitting in three preregistered
paired controller-search realizations (`20260825`--`20260827`).  Exact reruns
of the original deterministic seed were explicitly excluded as new evidence.
All three rollout-level mean prediction differences favored the successor, as
did OUTBOUND and RETURN separately, while all unchanged within-run HAC tests
remained NEUTRAL.  All six arms completed without a registered safety-chain
event or motion-envelope violation.  Decision: **RPL-A — FROZEN SUCCESSOR
REPLICATED**, limited to this fixed damping +20% simulation condition.  This
does not authorize a second update in the present study; the first progressive
experiment is design-only.  See
`docs/HUMAN_MODEL_FROZEN_SUCCESSOR_REPLICATION_V1.md`.

The following progressive attempt stopped before any longitudinal execution
because the one-step authority could label a model `theta_1` while retaining
nominal theta internally.  That implementation stop is now addressed by an
immutable theta-bound model identity, explicit prior/current/candidate roles,
immediate-predecessor transition authority, repetition-boundary queuing,
versioned lineage and a post-update POSITIVE/NEUTRAL/NEGATIVE gate.  Decision:
**PA-A — PROGRESSIVE AUTHORITY READY** at the state-machine level only.  No
progressive MuJoCo session had run at that checkpoint, gamma remained 0.5, and
PA-A itself was not evidence of progressive personalization.  See
`docs/PROGRESSIVE_HUMAN_MODEL_AUTHORITY_V1.md`.

The first preregistered longitudinal A/B has now run from PA-A with five matched
seeds per arm.  All ten episodes completed.  The progressive arm applied four
repetition-boundary successors beyond theta_1; each newly active predecessor
received genuinely later POSITIVE support before the following activation.
Deployable-domain active-model loss decreased monotonically from
`0.00038295` to `0.00021518 Nms^2`, while gamma stayed exactly 0.5 and no
registered safety-chain event occurred.  Decision: **PP2-A — PROGRESSIVE
PERSONALIZATION FEASIBLE**, limited to the damping +20% simulation condition
and fixed nominal interface.  Goal-MPC still misses the 20 ms runtime target,
and the acceleration monitor remains unresolved.  See
`docs/PROGRESSIVE_PERSONALIZATION_LONGITUDINAL_V1.md` and its compact JSON
summary.

A fixed-snapshot runtime audit now isolates the persistent 75--80 ms-class
Goal-MPC regression.  The V2 5/10/15/20 ms coupled acceleration-prefix screen
is the dominant new control-time computation; a duplicate feasible-subset pass
was removed with exact cache reuse.  The matched snapshot improved from 92.06
to 53.45 ms mean with unchanged selected action/sequence and feasibility masks,
but remains above 20 ms, so the result is **RT-C** rather than real-time
readiness.  Saved PP2-A traces also show **U5**: repetition-boundary scheduling
dominates elapsed activation time, while alpha=0.10 limits per-update movement;
an offline alpha=0.25 comparison improves saved-future prediction but is not
closed-loop evidence.  See `docs/RUNTIME_AND_PP2_LATENCY_AUDIT_V1.md`.

Latest diagnostic checkpoint: Acceleration-Semantics V2 interval alignment was
implemented, but targeted validation stopped at the first historical-failure
case because the nominal loaded-interface predictor still underpredicted the
5 ms q2 transient. V2 is not ready for a new robustness campaign. The separate
long-session runtime audit remains B6 (unresolved). See
`docs/ACCELERATION_SEMANTICS_V2_DESIGN.md`,
`docs/ACCELERATION_SEMANTICS_V2_TARGETED_RESULTS.md`, and
`docs/RUNTIME_TELEMETRY_AUDIT_V2.md`. The historical Interface Robustness V1
result remains frozen as `EXIT C — STOP THIS IMPLEMENTATION`.

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
wall-clock maximum prevents a hard worst-case claim. The small Interface
Mismatch v1 sweep and subsequent negative identification evidence are retained.
The interface branch is closed with the final campaign fixed at EXIT C; new
work isolates shadow Human identification under the nominal interface. No
interface/Human adaptation in control, value learning, or RL is active.

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
- `configs/stage5_interface_mismatch_v1.json`,
  `src/traction_mpc_stage5/interface_mismatch.py`, and
  `scripts/run_stage5_interface_mismatch_v1.py`: frozen controller-nominal
  record, evaluation-only plant-truth OFAT matrix, compact aggregation, and
  structured t=0 rejection evidence. No controller retuning or learning is
  introduced.
- `src/traction_mpc_stage5/goal_mpc.py`: first reference-free Human-space CEM
  adapter with phase target, goal/terminal cost, inherited action/slew and
  optional cuff terms, candidate-dependent execution screening, and terminal
  learned value fixed to zero. v1.3 propagates the controller-nominal
  translation/rotation interface and transmitted physical wrench through the
  full batched horizon. HOLD uses the `GoalTaskSpec` angle/velocity set with a
  safety-hard minimum-violation recovery fallback when the sampled set is
  temporarily unreachable; OUTBOUND/RETURN remain path-free.
- `configs/stage5_human_id_confidence_pacing_v1.json`,
  `src/traction_mpc_stage5/confidence_pacing.py`, and
  `scripts/run_stage5_human_id_confidence_pacing_v1.py`: frozen historical-V1
  confidence defaults, scalar path-free planning pacing, and session-persistent
  reduced shadow Human-ID lifecycle. Identification information, current-model
  trust, and challenger publication remain distinct; publication is shadow-only.
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
- `docs/INTERFACE_MISMATCH_V1.md`: seven-run/nine-cell small parameter sweep,
  nominal checkpoint reproduction, state/force/motion/runtime degradation
  chain, and a bounded recommendation for a later structural-mismatch probe.
- `configs/stage5_interface_uncertainty_v1.json`,
  `src/traction_mpc_stage5/interface_uncertainty.py`, and
  `scripts/audit_stage5_interface_uncertainty_v1.py`: limited Kt/Kr/D
  operating-set proposal, nominal-plus-corner causal monitor, conservative
  task/motion decision semantics, and read-only saved-trace replay.
- `docs/INTERFACE_UNCERTAINTY_V1.md`: Mismatch v1 classification, false-
  negative/false-positive tradeoff, nominal counterfactual stopping result,
  and endpoint-B recommendation. No interface identifier or learner is added.
- `configs/stage5_interface_identification_v1.json`,
  `src/traction_mpc_stage5/interface_identification.py`, and
  `scripts/audit_stage5_interface_identification_v1.py`: truth-free service
  contract, bounded joint initial-state/parameter prediction-error MHE,
  data-only projected identifiability diagnostics, future-validation split,
  last-valid fallback, and an inactive one-challenger shadow-publication shell.
- `docs/INTERFACE_IDENTIFICATION_V1.md`: Stage-1/4 reuse audit, six dynamic
  saved-trace fits plus the retained `Kr x0.7` startup failure, phase/window/
  latent-state sensitivity, held-out prediction comparison, and endpoint-C
  decision. Raw robot pose/twist are now included in future trace diagnostics;
  the Goal-MPC and safety paths are unchanged.
- `scripts/audit_stage5_interface_model_form_v1.py` and
  `docs/INTERFACE_INFORMATION_VS_MODEL_FORM_V1.md`: exact-model synthetic
  recovery, true-parameter saved-plant closure, small local parameter
  landscapes, and the decision to correct the identification-side
  relative-kinematics predictor before designing new excitation. This audit is
  offline only; publication and every control path remain unchanged.
- `configs/stage5_interface_identification_predictor_v2.json`,
  `src/traction_mpc_stage5/interface_identification_v2.py`,
  `scripts/audit_stage5_interface_physical_predictor_v2.py`, and
  `docs/INTERFACE_IDENTIFICATION_PHYSICAL_PREDICTOR_V2.md`: identification-only
  coupled robot/Human relative-kinematics predictor, old-vs-v2 true-parameter
  closure, and pre-estimator parameter landscapes. Gate 1 improves, Gate 2
  rejects physical publication, so the existing estimator is not rerun and
  control remains frozen.
- `configs/stage5_interface_robustness_v1.json`,
  `src/traction_mpc_stage5/interface_robustness.py`, and
  `docs/INTERFACE_ROBUSTNESS_CLOSEOUT_V1.md`: engineering acceptance contract,
  read-only Mismatch-v1 re-score, fixed-model V1 with a 180 N planning reserve
  and path-free 15/25 deg/s MPC pacing, six-episode development result, and an
  explicit Kr-low boundary limitation. Interface ID and the former uncertainty
  bank have no online authority.
- `configs/stage5_interface_robustness_final_campaign_v1.json`: frozen core-box,
  boundary, and 30-episode repeatability protocol. Its status is
  `PREREGISTERED_NOT_AUTHORIZED` as a historical spec; the subsequently run
  frozen campaign and EXIT-C result are documented separately and are not
  rewritten by the config.
- `docs/INTERFACE_STUDY_CLOSEOUT.md` and
  `docs/INTERFACE_STUDY_CLOSEOUT_MANIFEST.json`: durable closeout of the full
  interface evidence chain as a limited negative result.
- `configs/stage5_human_id_shadow_v1.json`,
  `src/traction_mpc_stage5/human_identification.py`, and
  `scripts/run_stage5_human_id_shadow_v1.py`: fixed-interface, deployable-input,
  beta11 shadow service and the four-case diagnostic runner. Publication is
  versioned shadow-only and cannot affect Goal-MPC.
- `docs/HUMAN_ID_ARCHITECTURE_AUDIT.md`,
  `docs/HUMAN_ID_SHADOW_V1_RESULTS.md`, and its compact JSON summary: Stage-4
  reuse classification, task-local embargo/trust contract, phase-wise evidence,
  and the H-B decision to validate a reduced control-effective block before
  any closed-loop adaptation.
- `configs/stage5_human_id_reduced_shadow_v1.json`,
  `src/traction_mpc_stage5/human_identification_reduced.py`, and
  `scripts/run_stage5_human_id_reduced_shadow_v1.py`: frozen Stage-4
  beta11-to-scale3 mapping, bounded reduced shadow lifecycle, and the small
  fixed-interface matrix. `docs/HUMAN_ID_REDUCED_SHADOW_V1_RESULTS.md` records
  the R-C endpoint; no reduced publication entered control and no closed-loop
  A/B was preregistered.
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

Reproduce the offline Interface-ID information/model-form audit from saved
Mismatch-v1 traces (no MuJoCo run and no parameter publication):

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_interface_model_form_v1.py
```

Run the identification-only physical Predictor-v2 gates on the same saved
traces (Gate 3 stops automatically when the physical landscape gate fails):

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_interface_physical_predictor_v2.py
```

Re-score the saved deterministic/Mismatch-v1 traces under the interface
robustness contract without running MuJoCo:

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_interface_robustness_closeout.py \
  --output-dir stages/stage5_personalized_motion_learning/results/interface_robustness_closeout_v1/new_rescore
```

The six-episode V1 development command is retained for provenance, but its
budget has been exhausted and it must not be rerun as tuning. The separately
preregistered final campaign remains unauthorized.

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
