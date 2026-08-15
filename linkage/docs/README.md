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
