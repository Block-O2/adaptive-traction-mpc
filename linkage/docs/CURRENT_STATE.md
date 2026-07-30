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

## Agreed model decisions

- Positive knee flexion is defined with shank absolute angle
  \(\theta_{\mathrm{shank}}=q_1-q_2\).
- The new plant will use independently consistent \(M(q)\),
  \(C(q,\dot q)\), and \(G(q)\) derived for that coordinate convention.
- The first implementation will use one robot arm and only the shank contact
  point.
- The initial contact baseline will be damping-only.
- The actual robot control input will be selected from the real robot
  interface rather than assumed from the legacy reference.
- Required generalization is across rehabilitation trajectories and patient
  parameters, not across robot platforms.

## Architecture direction

- A planner/reference-manager plus short-horizon tracker remains the primary
  architectural candidate.
- This is an architectural direction, not an implemented or validated
  controller.
- Controller implementation has not started.
- No legacy equation will be silently corrected in the preserved professor
  baseline; the new plant will be implemented separately when authorized.

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

The current intake establishes the preserved reference, reproducible execution,
independent dynamics findings, and agreed direction. It does not implement the
new plant or controller, select a robot command interface, or validate the
future architecture.
