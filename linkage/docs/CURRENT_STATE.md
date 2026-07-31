# Linkage Project Current State

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

## Agreed model decisions

- Positive knee flexion is defined with shank absolute angle
  \(\theta_{\mathrm{shank}}=q_1-q_2\).
- The new plant uses independently consistent \(M(q)\),
  \(C(q,\dot q)\), and \(G(q)\) derived for that coordinate convention.
- The first implementation will use one robot arm and only the shank contact
  point.
- The initial contact baseline will be damping-only.
- The implemented first baseline has one shank contact point with a continuous
  local normal and damping-only interaction.
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
  architectural candidate.
- The planner/reference-manager plus short-horizon tracker remains an
  architectural direction; the implemented endpoint-force law is only a
  simple constrained baseline, not that full architecture.
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
- Twenty-four MATLAB tests pass: 15 retained plant tests and 9 endpoint-force
  tests.
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

## Physical plant baseline evidence

- The new \(q_1-q_2\) plant uses independently consistent \(M(q)\),
  \(h(q,\dot q)=C(q,\dot q)\dot q\), and \(G(q)\).
- Fifteen deterministic MATLAB tests cover mass-matrix properties, Coriolis
  consistency, the manipulator skew identity, the potential-energy gradient,
  contact kinematics and dissipativity, finite values, and RK4 convergence.
- All 15 tests pass in MATLAB R2025b Update 1.
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

The intake, physical plant, interface audit, and ideal endpoint-force baseline
now establish the preserved reference, tested human dynamics, unresolved
hardware-interface gate, and a measured single-contact force-control limit.
No real robot adapter/dynamics, NMPC, adaptation, or clinical trajectory
dataset has been integrated. The next decision is an approved controller
design review addressing scale-consistent regularization, equilibrium
preservation, and reference feasibility while the real robot evidence is
collected.
