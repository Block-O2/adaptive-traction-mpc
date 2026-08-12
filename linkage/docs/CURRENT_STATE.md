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
- Bed-Supported Load Transfer V1 adds 20 mechanics and guard tests, bringing
  the retained suite to 74 tests. Its formal 18-case matrix remains reserved
  for user execution.
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
