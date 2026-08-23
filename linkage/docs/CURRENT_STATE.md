# Linkage Project Current State

This document is the single entry point for the current linkage research
status, accepted evidence, unresolved gates, and next-stage scope. The
[documentation index](README.md) separates current guidance from frozen and
archived reports. Stage-specific reports preserve the metrics and conclusions
observed at that stage; they do not independently override this state summary.

## Phase status

- The single-link Spring2D phase is closed and tagged
  `single-link-spring2d-v1`.
- The professor-supplied `singleArmDual.m` is retained unchanged as a
  legacy/reference baseline.
- The preserved source remains ignored at
  `linkage/matlab/reference/professor_original/singleArmDual.m` and is not
  added by the intake commit.
- The reference baseline runs successfully in MATLAB R2025b Update 1 through
  `linkage/matlab/runners/run_professor_reference_capture.m`.
- The independent dynamics-consistency audit is accepted.
- Publishing permission is no longer a blocker for the intake branch and its
  detailed derived documentation.
- A separate physical human two-link MATLAB plant baseline was implemented and
  validated without modifying the professor reference. Its V1 implementation,
  runners, and tests are archived at tag `linkage-pre-v1-code-cleanup`; its
  frozen report and ignored local results remain available.
- The laboratory robot-interface audit is complete, but exact robot,
  controller, SDK, command modes, feedback, and rates remain unresolved
  pending hardware/nameplate and manufacturer-package evidence.
- An ideal single-shank-contact endpoint-force controller baseline was
  implemented and evaluated as an actuator upper-bound study. Its V1
  implementation, runners, and tests are archived at tag
  `linkage-pre-v1-code-cleanup`.
- That endpoint-force version is frozen as the **single-contact negative
  baseline**. Its historical parameters, metrics, generated-result meaning,
  and interpretation must not be rewritten by later model/controller work.
- A parallel anthropometric Human Two-Link Model V2 is implemented and
  validated without modifying V1 or the frozen negative baseline.
- An isolated equilibrium-preserving single-arm V2 endpoint-force baseline
  is implemented and evaluated without modifying those frozen baselines.
- The single-arm V2 equilibrium study is closed out: the controller and ideal
  mathematical authority are confirmed, while the unsupported ±80 N
  architecture is infeasible at reference level.
- An open-loop trajectory/contact-force feasibility study is complete. It
  confirms that the current V2 reference is a contact-independent joint-space
  validation trajectory, that the translated professor reference reaches an
  exactly rank-deficient extended-knee posture under the current single distal
  contact model, and that a minimal force-aware waypoint candidate reduces
  force RMS but not the endpoint-dominated peak force.

## Active implementation and regression

- The retained active implementation is Human Model V2 under
  `linkage/matlab/src/human_two_link_v2/`, the single-arm V2 force
  map/equilibrium implementation under
  `linkage/matlab/src/single_arm_v2_equilibrium/`, the open-loop trajectory
  feasibility runner, and the quasistatic feasibility-atlas diagnostic.
- The canonical retained test entry is
  `linkage/matlab/runners/run_linkage_tests.m`. It runs only the V2 and
  single-arm V2 equilibrium/atlas tests and reports aggregate passed, failed,
  and incomplete counts.
- The current force-mode-stage retained suite contains 44 tests: the previous
  39 retained V2/equilibrium/atlas tests and five near-extension mechanics
  tests.
- Hybrid Tube Force Controller V1 adds ten implementation-contract tests,
  bringing the retained suite to 54 tests. Its user-run formal matrix is
  retained as an unsupported-initialization negative baseline.
- Bed-Supported Load Transfer V1 adds 44 mechanics, guard, and quasistatic
  diagnostic tests, bringing the retained suite to 98 tests. Its formal
  18-case matrix remains reserved
  for user execution.
- Dynamic Robust Load Transfer V1 originally added 19 supervisor,
  initialization, and model-boundary tests, bringing the retained suite to
  117 tests. R1 Safe Takeover adds six deterministic handover tests; the
  current retained suite completed with `123/123` passing. Its first
  user-run formal directory retained a valid nominal completion but invalid
  Stage 2 initialization exits. The corrected suite completed with 117/117
  tests, and the corrected formal directory retained valid initial-admissibility
  reports for all four cases. Nominal again completed; all three mismatch cases
  reached physical joint-1 soft-limit termination within 0.026--0.030 s.
  The R1 non-formal 4 s startup smoke reached `TRACKING` in all four cases
  without takeover soft/ROM violation. The reviewed R1 formal directory
  `20260815_171801` confirms nominal `TASK_COMPLETE` in `22.512 s`; all three
  mismatch cases safely entered `TRACKING` and later produced tracking-phase
  soft-limit exits before transfer.
- R2A Oracle Model Feasibility Gate now provides an isolated fixed
  `controller_model` boundary and a dedicated formal runner. The default path
  remains nominal-model tracking; oracle cases set the controller model equal
  to the fixed true case parameters from `t=0` while preserving R1, the task,
  supervisor, plant, limits, and stopping rules. Seven deterministic tests
  bring the Dynamic Robust V1 suite to 32 tests and the retained aggregate to
  130 tests; the full suite completed with `130/130` passing. The reviewed
  user-run oracle directory `20260815_174540` is a Case-B partial improvement:
  oracle mild completes, while moderate/adverse increase phase-aligned
  tracking survival to `4.068/3.490 s` but still terminate at the q2 lower
  soft boundary before transfer. Exact oracle and realized dynamic margins
  coincide yet remain strongly negative, so that global robot-only demand
  metric is not a parameter-mismatch residual. At that R2A review point, no
  adaptive tracking was implemented.
- R2B Windowed-NLS Adaptive Tracking now has a seven-parameter registered
  mismatch model, exact-discrete 0.2 s window, fixed 1 Hz update cadence,
  rank/condition/fit/bounds gates, bounded accepted-model updates, and safe
  last-model fallback. The reviewed offline replay gate `20260815_182639`
  retains zero nominal drift, improves mild/moderate parameter error, and
  rejects all adverse updates because its pre-failure natural data remain
  rank deficient. The six-second smoke `20260815_183824` preserves R1 and all
  existing safety checks without estimator corruption. Ten R2B tests bring
  the Dynamic Robust V1 group to 42 tests and the retained aggregate to 140;
  the full suite completed with `140/140` passing. The reviewed formal
  directory `20260816_083505` retains exact nominal completion. Adaptive mild
  reaches transfer and closes 72.44% of the progress gap and 95.06% of the
  tracking-survival gap, then reaches `RECONTACT` but times out before stable
  contact. Moderate closes 34.16% of the progress gap but only 7.04% of the
  survival gap before the same q2 soft boundary. Adverse accepts no update
  because natural data remain rank deficient and exactly retains the R1
  endpoint. No estimator solve fails or corrupts the accepted model. The R2B
  closed-loop evaluation scope is complete.
- R3A Identifiability and Failure-Mode Decomposition is complete as an offline
  audit of the frozen R1 `20260815_171801`, R2A `20260815_174540`, and R2B
  `20260816_083505` formal MAT files. It reconstructs every R2B 100-transition
  identifier window without changing Windowed NLS or running a new closed-loop
  trajectory. The reviewed output is
  `linkage/results/local/r3_identifiability_failure_decomposition/20260816_093111`.
  Adverse attempt ranks are `5/4/4`; the final spectrum has four strong
  directions and three effectively null directions, while the stacked
  condition `2.84e11` remains far beyond the unchanged R2B gate. Strong
  correlations show that those four directions are parameter combinations,
  not four independently identified physical parameters. Moderate is a mixed
  estimator-history and oracle-level q2 feasibility failure: the adaptive
  same-state model approaches the true model by termination, but adaptive and
  oracle still reach the same q2 lower soft boundary. Mild recontact is genuine
  continuous contact without chatter; it settles near `1.834 N`, below the
  unchanged `2 N` stability threshold, while oracle remains above threshold
  and completes. Ten R3A tests bring the retained aggregate to 150; the full
  suite completed with `150/150` passing, zero failed and zero incomplete in
  `224.9304 s`. R3A implements no controller, estimator replacement, safety
  layer, or scientific-parameter change.
- Near-Extension Protective Mode is the active engineering-validation mainline
  on `agent/near-extension-protective-mode`, based on clean post-R3A main
  `f781980`. R3B/R3C remain isolated Draft PRs and the R4 diagnostic checkpoint
  is also excluded from this branch ancestry. The MATLAB version implements a
  sanity-only command router:
  `BED_START -> KINEMATIC_TAKEOFF -> BLEND_TO_NORMAL -> NORMAL_REHAB` and
  `NORMAL_REHAB -> BLEND_TO_LANDING -> KINEMATIC_LANDING -> TERMINAL`.
  It captures measured state into one C2 quintic patch, lands at q2 = 2 degrees,
  bypasses force inversion in the kinematic segment, retains the unchanged
  200 N component force veto, and delegates normal operation exactly to the
  existing controller. The engineering recommendation `q_switch = 30 deg`
  corresponds approximately to the frozen strict-path 10 N registered-reserve
  boundary at q2 = 29.536 degrees; it is not a clinical threshold. The sanity
  trajectory reports exact state sequences, zero landing capture jump,
  takeoff q/dq handoff mismatch below `7.2e-14`, terminal q2 = 2 degrees, zero
  near-extension force-inversion calls, a latched veto, and exact normal-law
  delegation. Nine new tests bring the retained aggregate to 159; the full
  suite completed with `159/159` passing, zero failed and zero incomplete in
  `222.5698 s`. Real position/velocity-controlled contact remains unvalidated
  and is reserved for MuJoCo after the robot/contact interface is specified.
- MuJoCo Protective Mode V1 is implemented on
  `agent/mujoco-protective-mode-v1` as a minimal nominal Human V2, unilateral
  bed, tension-only compliant cuff, and bounded x/z servo engineering smoke.
  The 30-degree baseline retains the full command sequence but is a physical
  negative result: takeoff ends near q2 = -0.073 degrees rather than 30
  degrees, terminal settles near 0.714 degrees rather than 2 degrees, cuff
  extension reaches 97.86 mm, interaction force reaches 176.15 N, and 49 bed
  contact transitions expose chatter. No automatic 200 N veto occurs. A
  separately labeled manual-veto probe verifies the braking route but starts
  from an already stalled knee and is not moving-limb braking evidence. The
  20/25/30/32.5-degree sensitivity is intentionally skipped because the
  baseline mechanical-completeness gate is not met. No parameter or contact
  tuning is folded back after this result; a justified real robot/cuff/load
  path is required before reconnecting the normal force-aware controller or
  Windowed NLS.
- M1.5 physical-interface diagnostics retain that failure without controller
  tuning. The unchanged 2-degree BED_START settles at q2=0.714 degrees after
  a 481 N initial contact peak; individual contact points switch during the
  first second but are steady in the final two seconds.
- Paired 2 mm probes at 2/10/20/30 degrees show that the V1 tension-only
  tendon absorbs 68--99% of incremental robot motion as interface deformation.
  A same-parameter bilateral MuJoCo point-connection hypothesis improves
  translational coupling at 20/30 degrees, but all requested postures collapse
  and both-direction signed knee authority remains wrong.
- The physical gate therefore blocks a new 2-to-30-to-2 rollout and q-switch
  sensitivity. This is evidence against the present simulated interface, not
  against kinematic protective mode. Detailed assumptions and metrics:
  [MUJOCO_PHYSICAL_INTERFACE_M15.md](MUJOCO_PHYSICAL_INTERFACE_M15.md)
- Twenty M1.5 contracts bring the repository Python suite to 128 passing
  tests; bytecode compilation and diff whitespace checks pass.
- Existing V2/equilibrium-specific test runners remain for their documented
  stage-level uses. Historical 15/24/42/57 counts below describe the suites at
  those stages, not the current retained suite size.
- The removed V1 implementation is recoverable without rewritten history from
  annotated tag `linkage-pre-v1-code-cleanup`.

## Agreed model decisions

- Positive knee flexion is defined with shank absolute angle
  \(\theta_{\mathrm{shank}}=q_1-q_2\).
- The new plant uses independently consistent \(M(q)\),
  \(C(q,\dot q)\), and \(G(q)\) derived for that coordinate convention.
- The first implementation will use one robot arm and only the shank contact
  point.
- The historical V1 physical-contact baseline uses one shank contact point
  with a continuous local normal and damping-only interaction.
- The actual robot control input will be selected from the real robot
  interface rather than assumed from the legacy reference.
- Required generalization is across rehabilitation trajectories and patient
  parameters, not across robot platforms.
- The ideal endpoint-force baseline commands
  \(u=[F_t,F_n]^\mathsf{T}\), maps it through
  \(F_{\mathrm{world}}=[t\ n]u\) and
  \(\tau_{\mathrm{contact}}=J_c^\mathsf{T}F_{\mathrm{world}}\), and applies no
  direct human joint torque.

## Architecture direction

- A planner/reference-manager plus short-horizon tracker remains the primary
  architectural direction; the implemented endpoint-force laws are constrained
  baselines, not that full architecture.
- The implemented computed-torque PD law is only an oracle plant-validation
  controller using the true parameters and abstract human generalized torque.
- A real-robot controller/adapter has not started because the supported robot
  command and feedback contract remains unresolved.
- No legacy equation will be silently corrected in the preserved professor
  baseline; the new plant is maintained as a separate implementation.
- Dynamic Robust Load Transfer V1 implements the approved full-cycle hybrid
  sequence for the fixed 200 N / 10 degree engineering case. The supervisor
  keeps registered quasistatic reserve separate from nominal dynamic force
  prediction, uses real unilateral bed contact, and never scales plant bed
  force. The first Stage 2 run ended at the initialization boundary because a
  nominal equilibrium force was reused for perturbed plants at zero joint-1
  soft-zone clearance; it is retained as diagnostic history, not robustness
  evidence. The initialization-only force is now plant-consistent and logged,
  and the corrected formal run shows that the unchanged nominal controller
  subsequently drives all three perturbed plants back across that boundary
  before meaningful task progress. These are physical safety terminations after
  valid initialization, not solver failures; they do not characterize the later
  transfer path. R1 now inserts an explicit safe hold and constraint-aware
  handover before the unchanged nominal tracking path. Its startup smoke
  removes the old 26--30 ms takeover exit. The reviewed formal run confirms
  that the remaining mismatch exits occur later in tracking, not during
  initialization or takeover. See
  [DYNAMIC_ROBUST_LOAD_TRANSFER_V1.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1.md).

## Ideal endpoint-force evidence

- A deterministic active-set/boundary-enumeration solver implements the
  two-input force/slew-bounded regularized least-squares controller without
  Optimization Toolbox.
- Historical endpoint-force-stage snapshot: 24 MATLAB tests passed, comprising
  15 retained plant tests and 9 endpoint-force tests.
- All 9 endpoint-force and 9 oracle comparison rollouts finish without
  nonfinite dynamics signals.
- With one fixed parameter set, only the tall/heavy profile tracks the
  knee-dominant and coordinated normal tasks without joint/velocity-limit
  samples. Nominal and short/light enter a poorly conditioned region and have
  large tracking errors; no per-profile tuning is applied.
- All three deliberately conflicting cases expose the intended capability
  boundary through large error, poor conditioning, residual, saturation
  and/or limit violations; these are scientific outcomes, not runtime errors.
- Generated MAT/CSV/log/GIF evidence remains ignored under
  `linkage/results/local/ideal_endpoint_force_baseline/`.
- The corresponding V1 source, runners, and tests are archived at tag
  `linkage-pre-v1-code-cleanup`; the report metrics and conclusions remain
  frozen.
- Methods and observed results:
  [IDEAL_ENDPOINT_FORCE_BASELINE.md](IDEAL_ENDPOINT_FORCE_BASELINE.md)

## Human Model V2 evidence

- V2 uses isolated `human_two_link_v2_*` functions and preserves the same
  (q_1,q_2,\phi=q_1-q_2) coordinate convention.
- Nominal adult parameters are constructed from height 1.72 m and mass 75 kg
  using documented anthropometric length, mass, COM, and inertia fractions;
  arbitrary positive finite height/mass inputs remain supported.
- The passive resistance is consistently defined on the dynamics left side
  with positive-semidefinite damping. Smooth ROM soft limits apply no hard
  clipping and remain inactive on the nominal trajectory.
- `slow_passive_flexion_v2` is a 16 s SmartSling-range-inspired synchronous
  slow engineering trajectory, not a clinical protocol or therapist
  demonstration.
- The nominal exact-model oracle achieves RMSE
  (7.18\times10^{-10}/2.74\times10^{-9}) degrees with zero ROM violation,
  zero soft-limit activation, and zero nonfinite values.
- Historical Human Model V2-stage snapshot: all 42 MATLAB tests passed,
  comprising 24 retained V1/endpoint tests and 18 V2 tests.
- Generated evidence remains ignored under
  `linkage/results/local/human_model_v2/`.
- Model, assumptions, metrics, and source separation:
  [HUMAN_MODEL_V2.md](HUMAN_MODEL_V2.md)

## Single-arm V2 equilibrium evidence

- The analytic local-force map is
  \(A=[-L_1\sin q_2,\ L_1\cos q_2+s_c;\ 0,-s_c]\), with
  \(\det A=L_1s_c\sin q_2\); implementation uses SVD and records mapping
  conditioning rather than forming an inverse.
- Reference preflight finds a 316.55 N peak ideal force and zero feasible
  samples under the fixed ±80 N component bound. Static support dominates the
  dynamic increment.
- The ideal-authority case completes with 0.00234/0.00616 degree RMSE, no
  force or slew saturation, and numerical-precision torque residual, but it
  still activates the V2 soft limit during 473 return samples.
- The engineering-bound case completes numerically but is force-limited from
  the initial hold, with 10.81/52.48 degree RMSE, 97.85% hard saturation, and
  8.19 N m RMS torque residual. This is constraint infeasibility, not a
  runtime error.
- Historical equilibrium-stage snapshot: all 57 MATLAB tests passed,
  comprising 42 retained tests and 15 new equilibrium tests.
- The specified ideal acceptance criteria are not fully met; the project is
  not yet eligible to move to fixed-model planner/NMPC implementation.
- The 473-sample ideal soft-limit boundary phenomenon has not received an
  independent penetration/torque audit and remains unresolved.
- NMPC work is paused pending an architecture decision and confirmation of
  the real rehabilitation posture, support, contact, and hardware context.
- Generated evidence remains ignored under
  `linkage/results/local/single_arm_v2_equilibrium_baseline/`.
- Methods and observed results:
  [SINGLE_ARM_V2_EQUILIBRIUM_BASELINE.md](SINGLE_ARM_V2_EQUILIBRIUM_BASELINE.md)
- Minimal diagnostic closeout:
  [SINGLE_ARM_V2_DIAGNOSTIC_CLOSEOUT.md](SINGLE_ARM_V2_DIAGNOSTIC_CLOSEOUT.md)

## Single-arm trajectory feasibility evidence

- The current V2 `[5;10]` to `[45;84]` degree reference uses a shared quintic
  progress and was created for plant/oracle validation, not contact-force or
  conditioning feasibility.
- Under the present single distal contact and Human Model V2 assumptions, the
  current reference requires a 316.551 N peak ideal force; static support
  dominates its dynamic generalized-torque increment.
- The professor reference can be translated without a coordinate ambiguity,
  but that diagnostic is not a reproduction of the original two-contact,
  direct-joint-torque experiment. It reaches `q2=0`, where the current
  single-contact force map is rank deficient.
- The fixed-grid force-aware candidate preserves the current start, target ROM,
  duration, and slow speed/acceleration bounds. It reduces force RMS from
  198.090 N to 160.076 N (19.2%) but reduces peak force by only 0.052%, because
  the unchanged low-flexion endpoint retains the same static lower bound.
- This was an open-loop inverse-dynamics/contact-force preflight. No closed-loop
  tracking or GIF was generated, and it does not establish clinical efficacy.
- Methods, artifacts, and bounded conclusions:
  [SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md](SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md)

## Single-arm quasistatic feasibility atlas

- The nominal `q1=0:1:80 deg`, `q2=0:1:100 deg` posture scan retains the
  current Human Model V2, passive torque, contact position, and force map.
- `q2=0` is explicitly rank deficient and has no fabricated finite exact
  force. Across the nonsingular grid, the exact holding-force residual stays
  below `3.57e-14 N m`.
- The finite force range is `18.466 N` to `4432.666 N`; the maximum occurs at
  `[0,1] deg`, while all sampled points at or above `300 N` lie within
  `q2=1..19 deg`. This localizes the largest amplification to low knee
  flexion under the frozen model/contact assumptions.
- The current V2 start `[5,10] deg` requires
  `F_parallel=-315.030 N`, `F_perp=21.011 N`, and `315.730 N` total, whereas
  `[45,84] deg` requires `103.484 N` total and is much better conditioned.
- Along the current V2 reference, the quasistatic peak is approximately
  `315.73 N` at the shared start/end pose `[5,10] deg`. It is dominated by
  `F_parallel`, with a much smaller `F_perp`, and places the reference start in
  the mechanically unfavorable low-flexion/near-extension region.
- Exact feasible fractions over all 8,181 samples are 2.4569%, 57.1691%, and
  83.4372% for the `+/-80`, `+/-120`, and `+/-200 N` component boxes. The
  start is infeasible under all three; the peak is feasible under 120 N and
  200 N but not 80 N.
- This is a quasistatic mechanical diagnostic only. It does not establish
  closed-loop controllability, comfort, clinical safety, or an architecture
  decision; professor and hardware confirmation remain required.
- The 80 N, 120 N, and 200 N limits are engineering comparison bounds, not
  clinical safety standards, and the atlas does not establish failure of the
  single-arm architecture. Before further NMPC/controller tuning, the next
  stage must first confirm trajectory strictness, permitted safety
  intervention, and the operating envelope.
- Methods and bounded interpretation:
  [SINGLE_ARM_QUASISTATIC_FEASIBILITY_ATLAS.md](SINGLE_ARM_QUASISTATIC_FEASIBILITY_ATLAS.md)

## Near-extension force-mode feasibility

- An offline quasistatic scan tests the proposed relaxation of strict
  hip-knee coordination near extension. It is a mechanics study, not a
  controller, NMPC, safety supervisor, or closed-loop experiment.
- At the frozen `[5,10] deg` posture, the static force remains `315.730 N`.
  Searching hip posture at the same `q2=10 deg` selects `q1=0 deg`, reducing
  `abs(F_parallel)` from `315.030 N` to `22.992 N` and total force to
  `30.985 N`.
- The posture solution is boundary-seeking rather than a smooth policy:
  optimum `abs(F_parallel)` rises to `189.492 N` at `q2=2 deg` and
  `218.476 N` at `q2=1 deg`, where the selected hip posture jumps to
  `q1=79 deg`. At `q2=0`, the map remains rank deficient with no finite exact
  suspended single-contact solution.
- Under the 80 N, 120 N, and 200 N engineering component bounds, the current
  V2 return has peak abstract support residuals of 7.398, 6.139, and
  3.621 N m, respectively, all knee-dominated. The minimum-axial-force
  posture curve confines nonzero residual to `q2=1..5`, `1..4`, and `1 deg`,
  with much smaller peaks of 0.949, 0.572, and 0.058 N m.
- The residual is generalized torque that must be carried by unspecified
  external load transfer; it is not a bed-contact force or a concrete support
  model. The force bounds are not clinical safety thresholds.
- Force-mode posture adjustment can mitigate much of the positive-flexion
  demand but does not remove near-zero rank/force limitations. Before further
  controller work, the project must confirm trajectory strictness, permitted
  safety intervention, and operating envelope. A specific load-transfer model
  is warranted only if the required envelope includes the residual-producing
  low-flexion region.
- Methods and bounded conclusion:
  [NEAR_EXTENSION_FORCE_MODE_FEASIBILITY.md](NEAR_EXTENSION_FORCE_MODE_FEASIBILITY.md)

## Hybrid tube force controller V1

- The first task-level closed-loop implementation retains the frozen V2
  geometric path while adding monotone flexible progress, a continuous
  component-wise trajectory tube, a deterministic force-aware spatial
  reference plan, and terminal task-set classification.
- Tube caps of 0, 5, and 10 degrees and force-component bounds of 80, 120, and
  200 N are engineering sensitivity cases, not clinical tolerances or safety
  limits. Force/hold feasibility is prioritized over nominal path fidelity,
  and bounded torque residual remains explicit.
- The existing Human Model V2, passive model, distal force map, equilibrium
  controller, and original V2 reference files remain unchanged. V1 does not
  implement bed contact, load transfer, retreat, CBF, NMPC, or a complete
  safety supervisor.
- The implementation and its mechanical contract tests are present, but the
  first formal 12-case dynamic matrix was run by the user. It confirms that
  the frozen `[5,10] deg` fully suspended initialization is infeasible under
  all three engineering force boxes. The corrected manager now returns
  `INITIAL_SUPPORT_REQUIRED` before integration instead of allowing drift and
  later labeling the state `TRANSFER_REQUIRED`.
- The mathematical frame is +x right/+y up with q1 measured from +x, so q1=0
  is horizontal and `[5,10] deg` is nearly horizontal. The initial GIF used a
  sine/cosine-swapped drawing convention; only the visualization was wrong.
- This is an unsupported/suspended initialization negative baseline, not a
  rejection of the tube formulation with an explicit support/load-transfer
  phase.
- This stage addresses only the suspended single-contact path to the existing
  V2 terminal region. It does not establish safe full extension; the
  structural rank loss at `q2=0` remains, and any required external load
  transfer must be modeled separately in a later stage.
- Formulation, runner, validation boundary, and formal command:
  [HYBRID_TUBE_FORCE_CONTROLLER_V1.md](HYBRID_TUBE_FORCE_CONTROLLER_V1.md)

## Bed-supported load transfer V1

- The mathematical frame remains +x right/+y up with q1 measured from +x;
  q1=0 is horizontal and `[5,10] deg` is a nearly horizontal supine posture.
  No Human Model V2 equation or gravity convention was rotated.
- A horizontal `y=0` unilateral Kelvin-Voigt bed abstraction now acts through
  eight fixed, uniformly spaced lower-surface candidates. It has no tensile
  force or tangential friction, and bed/robot forces and generalized torques
  are recorded separately.
- A deterministic nominal-bed calibration fixes `h_hip=0.06825 m` for all
  stiffness sensitivities. At the nominal initial posture the bed supplies
  `152.540 N` total normal force and the remaining exact robot force is
  `[-8.543,21.011] N` (`22.681 N` norm), with numerical-zero torque balance.
- The eight-mode implementation adds bed-supported `SUPPORTED_PREPOSITION`
  before load takeover, followed by guarded liftoff, suspended motion,
  re-contact, load return, and release. Formal task progress stays at `s=0`
  during preposition. Liftoff
  requires both near-zero bed force and exact bounded robot-only hold
  feasibility; failed handoffs retain explicit failure classifications.
- The six nominal-bed smoke cases produced no liftoff. Five tubes contained no
  robust robot-only preposition. The 200 N/10 degree case reached the
  enumerated `[7,20] deg` target and entered `LOAD_TAKEOVER`, but a small
  dynamic posture deviation reduced its fixed force margin below 5 N; it
  returned `PREPOSITION_INFEASIBLE`. There was no soft-limit activation, ROM
  violation, or boundary-seeking. No parameter was tuned.
- This smoke does not justify the formal matrix. Wider task freedom, a
  different support strategy, or an architecture change requires explicit
  review before another dynamic study.
- The formal 5/10 degree by 80/120/200 N by three-stiffness dynamic matrix and
  GIF generation remain reserved for user execution.
- Model, calibration, guards, assumptions, and formal command:
  [BED_SUPPORTED_LOAD_TRANSFER_V1.md](BED_SUPPORTED_LOAD_TRANSFER_V1.md)

## Robust force-margin sensitivity

- The robot-only dense map retains nominal 200 N / 10 degree margins of
  `10.554 N` at `[5,20] deg` and `9.515 N` at the practical `[7,20] deg`
  posture. The latter gives up only `1.039 N` while retaining 2 degrees of
  soft-limit clearance.
- A validated sensitivity-only parameter override evaluates mass, independent
  thigh/shank COM locations, passive stiffness, independent/same-direction
  rest angles, and robot contact location without modifying the Human V2
  constructor or copying its dynamics formulas.
- The worst one-at-a-time case is `+10%` mass: the 200 N margin becomes
  `-6.803 N` at `[7,20] deg` and `-5.893 N` at `[5,20] deg`.
- Layer-1-selected mild, moderate, and adverse deterministic combinations give
  `[7,20] deg` margins of `-5.975`, `-17.969`, and `-39.092 N`; all are
  engineering stress cases, not patient distributions.
- The approximately 1 N `[5,20]` advantage does not change the robustness
  class, so `[7,20]` remains the more defensible practical posture because of
  its soft-limit clearance.
- A 5 N cutoff filters several registered cases when their required force is
  evaluated, but nominal 5 N reserve is clearly insufficient as an uncertainty
  allowance under this sensitivity set. This is not a clinical safety result.
- The nominal 200 N result alone does not justify a dynamic takeover experiment
  as robustness evidence. No controller, guard, force bound, tube, bed model,
  or nominal Human V2 parameter was changed, and no dynamic matrix was run.
- Cases, deterministic combination rule, artifacts, and bounded conclusion:
  [ROBUST_FORCE_MARGIN_SENSITIVITY.md](ROBUST_FORCE_MARGIN_SENSITIVITY.md)

## Robust suspended feasibility envelope

- A deterministic quasistatic implementation covers the frozen outbound
  `[5,10]` to `[45,84] deg` geometry, strict/5/10 degree tubes, and
  80/120/200 N component boxes.
- It reuses the complete registered one-at-a-time and mild/moderate/adverse
  engineering uncertainty set, excludes ROM/rank/soft-active candidates from
  recommendations, and refines threshold crossings locally.
- Bed availability uses the unchanged nominal calibration and retained contact
  threshold. Transfer overlap requires bed support and registered-robust
  robot-only reserve at the same candidate posture; unrelated postures are not
  combined.
- Eleven contract tests bring the retained suite to 98 passing tests, and the
  new source/runner have zero MATLAB `checkcode` issues.
- The user-run envelope finds no nominal 80 N region and no registered-robust
  80 N or 120 N suspended region. At peak flexion, the best 120 N robust
  margin remains `-0.224 N` even with the 10 degree tube.
- The 200 N robust zero-margin entries are `s=0.230`, `0.198`, and `0.108`
  for strict, 5 degree, and 10 degree tubes. Their same-posture bed-overlap
  intervals end at `s=0.394`, `0.414`, and `0.432`, so all three have one
  continuous quasistatic transfer window and no support gap.
- All 51 reached refined boundaries satisfy the recorded numerical convergence
  criteria. The result remains quasistatic engineering evidence and does not
  prove dynamic liftoff/recontact, clinical safety, or mattress validity.
- Registered method, detailed boundaries, artifacts, and reproduction command:
  [ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md](ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md)

## Physical plant baseline evidence

- The new \(q_1-q_2\) plant uses independently consistent \(M(q)\),
  \(h(q,\dot q)=C(q,\dot q)\dot q\), and \(G(q)\).
- The historical physical-plant-stage suite contained 15 deterministic MATLAB
  tests covering mass-matrix properties, Coriolis
  consistency, the manipulator skew identity, the potential-energy gradient,
  contact kinematics and dissipativity, finite values, and RK4 convergence.
- All 15 passed in MATLAB R2025b Update 1 at that stage.
- The deterministic three-trajectory by three-profile by two-contact-mode
  matrix completed 18/18 runs with no joint-limit, velocity-limit,
  dissipativity, or finite-value violations.
- Generated evidence remains ignored under
  `linkage/results/local/human_two_link_baseline/`.
- The corresponding V1 source, runners, and tests are archived at tag
  `linkage-pre-v1-code-cleanup`; the report metrics and conclusions remain
  frozen.
- Baseline methods and observed results:
  [PHYSICAL_PLANT_BASELINE.md](PHYSICAL_PLANT_BASELINE.md)

## Reproduced reference evidence

- Preservation SHA-256:
  `b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f`
- MATLAB version: `25.2.0.3042426 (R2025b) Update 1`
- Baseline execution: exit code 0, 191 captured workspace variables, three
  captured figures, and no source runtime error.
- Generated results remain ignored under
  `linkage/results/local/professor_reference_baseline/`.
- Source/execution audit: [MATLAB_CODE_AUDIT.md](MATLAB_CODE_AUDIT.md)
- Independent dynamics audit:
  [DYNAMICS_CONSISTENCY_AUDIT.md](DYNAMICS_CONSISTENCY_AUDIT.md)
- Earlier system reconstruction:
  [SYSTEM_DEFINITION_DRAFT.md](SYSTEM_DEFINITION_DRAFT.md)

## Scope boundary

The intake, archived V1 plant, frozen single-contact negative baseline,
interface audit,
Human Model V2, equilibrium-preserving V2 endpoint comparison, diagnostic
closeout, and open-loop trajectory feasibility study establish the preserved
reference, isolated human dynamics, unresolved hardware gate, and measured
single-contact force limitation. No real robot adapter/dynamics, NMPC,
adaptation, or clinically validated trajectory dataset has been integrated.
Planner/NMPC implementation remains gated by architecture and real
rehabilitation-context decisions. Future work must not edit or reinterpret
either historical endpoint-force result.
