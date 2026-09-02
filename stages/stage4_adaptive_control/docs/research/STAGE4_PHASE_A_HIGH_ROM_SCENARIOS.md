# Phase-A High-ROM Engineering Scenario Contracts

Status: engineering scenario definition for interaction diagnosis only. Neither
scenario is a physiological, clinical, comfort, efficacy, or hardware model.

The canonical Human V2 dynamics, joint convention, masses, inertias, gravity,
passive elements, ROM variant, fixed hip pivot, robot model, 140 mm engineering
adapter, rigid six-constraint cuff weld, controller, allocator, command law, and
safety limits are identical in both scenarios. The canonical/default plant
remains unchanged.

## A. `lying_bed`

This is the existing and default coupled-plant scene.

- The bed is a fixed plane at the existing height.
- Human thigh and shank collision geoms have unilateral frictional contact with
  the bed using the existing friction, `solref`, and `solimp` values.
- The bed does not collide with the robot, adapter, or sleeve visual.
- The hip joint remains anchored at the existing world pose.

This scenario can therefore exchange normal and frictional contact forces
between the bed and either Human segment during large-ROM motion.

## B. `suspended_seated_like_high_rom`

This is an explicit opt-in engineering counterfactual for High-ROM diagnosis.

- The bed geom remains visible and at the same pose, but its collision type and
  affinity are both zero.
- Human thigh and shank therefore have no bed contact or bed support.
- No replacement seat, backrest, strap, pelvis support, or other external
  contact is invented.
- The existing fixed hip pivot remains the only proximal kinematic support;
  the rigid cuff/robot interaction remains the distal coupling.

The name “suspended/seated-like” denotes only the removal of lying-bed segment
support that may be inappropriate for a large-ROM engineering task. It does not
model seated anatomy or claim that a real seated or suspended person behaves
this way.

## Comparison contract

Phase-A scenario comparisons may differ only in whether Human segment-to-bed
contact is enabled. They keep the same pre-window state and already-issued
robot joint-torque command when performing the short interaction replay. This
isolates the immediate contact-law contribution but does not establish that the
same pre-window state would have been reached under a full suspended trajectory.

