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
- A separate physical human two-link MATLAB plant baseline is now implemented
  and validated without modifying the professor reference.
- The laboratory robot-interface audit is complete, but exact robot,
  controller, SDK, command modes, feedback, and rates remain unresolved
  pending hardware/nameplate and manufacturer-package evidence.
- An ideal single-shank-contact endpoint-force controller baseline is now
  implemented and evaluated as an actuator upper-bound study.
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

The intake, V1 plant, frozen single-contact negative baseline, interface audit,
Human Model V2, equilibrium-preserving V2 endpoint comparison, diagnostic
closeout, and open-loop trajectory feasibility study establish the preserved
reference, isolated human dynamics, unresolved hardware gate, and measured
single-contact force limitation. No real robot adapter/dynamics, NMPC,
adaptation, or clinically validated trajectory dataset has been integrated.
Planner/NMPC implementation remains gated by architecture and real
rehabilitation-context decisions. Future work must not edit or reinterpret
either historical endpoint-force result.
