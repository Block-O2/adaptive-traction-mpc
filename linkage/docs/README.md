# Linkage Documentation Index

Use [CURRENT_STATE.md](CURRENT_STATE.md) as the single entry point for current
project status, accepted evidence, unresolved gates, and next-stage scope.
The categories below are navigational only; existing reports remain in place.

## Current

- [CURRENT_STATE.md](CURRENT_STATE.md) — authoritative current-state entry.
- [HUMAN_MODEL_V2.md](HUMAN_MODEL_V2.md) — current anthropometric/passive human
  model and oracle validation.
- [ROBOT_INTERFACE_AUDIT.md](ROBOT_INTERFACE_AUDIT.md) — current hardware and
  SDK evidence gate.
- [SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md](SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md)
  — current open-loop trajectory/contact-force preflight.
- [SINGLE_ARM_QUASISTATIC_FEASIBILITY_ATLAS.md](SINGLE_ARM_QUASISTATIC_FEASIBILITY_ATLAS.md)
  — current joint-workspace static holding-force and component-bound map.
- [NEAR_EXTENSION_FORCE_MODE_FEASIBILITY.md](NEAR_EXTENSION_FORCE_MODE_FEASIBILITY.md)
  — offline near-extension posture objectives and abstract support residual.
- [HYBRID_TUBE_FORCE_CONTROLLER_V1.md](HYBRID_TUBE_FORCE_CONTROLLER_V1.md)
  — implemented geometric-path, flexible-progress, and force-aware tube
  reference-manager contract and unsupported-initialization negative baseline.
- [BED_SUPPORTED_LOAD_TRANSFER_V1.md](BED_SUPPORTED_LOAD_TRANSFER_V1.md)
  — horizontal unilateral bed abstraction, load-transfer state machine, fixed
  calibration, tests, smoke boundary, and pending formal matrix.
- [ROBUST_FORCE_MARGIN_SENSITIVITY.md](ROBUST_FORCE_MARGIN_SENSITIVITY.md)
  — deterministic robot-only quasistatic sensitivity of the nominal 200 N
  preposition reserve and 5 N engineering guard.
- [ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md](ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md)
  — user-run full-path nominal/registered-robust liftoff boundaries and
  same-posture bed-overlap envelope.
- [DYNAMIC_ROBUST_LOAD_TRANSFER_V1.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1.md)
  — dynamic bed-to-suspended-to-bed supervisor, distinct static/dynamic
  margins, nominal-controller/perturbed-plant contract, and formal runner.
- [DYNAMIC_ROBUST_LOAD_TRANSFER_V1_INITIALIZATION_DIAGNOSIS.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_INITIALIZATION_DIAGNOSIS.md)
  — exact first-run Stage 2 soft-limit trigger, scenario-initialization fix,
  explicit admissibility contract, and corrected formal rerun boundary.
- [DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md)
  — exact old 0--30 ms handover chain, R1 safe-hold/takeover/tracking
  governor, deterministic tests, startup smoke evidence, and reviewed formal
  phase-separated result.
- [DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ORACLE_MODEL_R2A.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ORACLE_MODEL_R2A.md)
  — fixed true-model tracking diagnostic, preserved R1 boundary, parameter
  isolation, metrics, tests, and reviewed Case-B formal decision gate.
- [DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING_R2B.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING_R2B.md)
  — bounded seven-parameter Windowed-NLS, replay gate, nominal-start adaptive
  model boundary, startup smoke, diagnostics, and reviewed formal comparison.
- [R3_IDENTIFIABILITY_FAILURE_DECOMPOSITION.md](R3_IDENTIFIABILITY_FAILURE_DECOMPOSITION.md)
  — offline R2B window identifiability, moderate failure decomposition, mild
  recontact diagnosis, and evidence-separated next-step decisions.
- [NEAR_EXTENSION_PROTECTIVE_MODE.md](NEAR_EXTENSION_PROTECTIVE_MODE.md)
  — sanity-only low-speed kinematic takeoff/landing patch, force-veto command
  interface, q-switch evidence, and MuJoCo validation boundary.
- [MUJOCO_SLEEVE_ROBOT_V2.md](MUJOCO_SLEEVE_ROBOT_V2.md)
  — CR12 asset audit, CR12-like six-DoF engineering plant, bilateral sleeve,
  BED_START equilibrium, fixture topology probes, released dynamic-authority
  gates, and the retained low-angle negative result.
- [MUJOCO_CONTACT_CONSISTENT_FEASIBILITY_AUDIT.md](MUJOCO_CONTACT_CONSISTENT_FEASIBILITY_AUDIT.md)
  — offline candidate-path contact kinematics, complete Human V2 quasistatic
  load, unilateral reaction solve, force/rank timeline, and support-gap result.
- [MUJOCO_DYNAMIC_PROTECTIVE_TRANSITION_V1.md](MUJOCO_DYNAMIC_PROTECTIVE_TRANSITION_V1.md)
  — fixed 3-degree-floor dynamic primitive, explicit retained soft-limit
  dynamics, candidate target matrix, synchronized evidence, and startup-floor
  negative result.
- [Local results policy](../results/README.md) — ignored artifact and retention
  rules.

## Frozen evidence

These reports preserve historical setups, metrics, and interpretations. They
are evidence records rather than current implementation recommendations.
The V1 implementation associated with the physical-plant and ideal
endpoint-force reports is archived at annotated tag
`linkage-pre-v1-code-cleanup`.

- [MATLAB_CODE_AUDIT.md](MATLAB_CODE_AUDIT.md)
- [DYNAMICS_CONSISTENCY_AUDIT.md](DYNAMICS_CONSISTENCY_AUDIT.md)
- [PHYSICAL_PLANT_BASELINE.md](PHYSICAL_PLANT_BASELINE.md)
- [IDEAL_ENDPOINT_FORCE_BASELINE.md](IDEAL_ENDPOINT_FORCE_BASELINE.md)
- [SINGLE_ARM_V2_EQUILIBRIUM_BASELINE.md](SINGLE_ARM_V2_EQUILIBRIUM_BASELINE.md)
- [SINGLE_ARM_V2_DIAGNOSTIC_CLOSEOUT.md](SINGLE_ARM_V2_DIAGNOSTIC_CLOSEOUT.md)
- [Professor reference preservation note](../matlab/reference/README.md)

## Archived

- [SYSTEM_DEFINITION_DRAFT.md](SYSTEM_DEFINITION_DRAFT.md) — superseded,
  source-only reconstruction retained for history.
