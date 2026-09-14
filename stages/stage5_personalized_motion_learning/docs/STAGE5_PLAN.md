# Stage-5 Research Plan

## Research direction

The eventual study is repeated rehabilitation motion, nominally about 30
repetitions per session. The first few repetitions may be deliberately slow
and conservative. The research goal is to personalize within roughly 3--5
repetitions and then converge toward a stable, standardized motion strategy
with low physical interaction force.

The final objective is broader than tracking one prescribed `q1`/`q2`
trajectory. Later Stage-5 work may optimize or learn the coordination between
`q1` and `q2`, with cumulative physical cuff interaction over the full motion
as an important objective. Model-based MPC/CEM and the established execution
and safety stack remain the base architecture.

This document makes no claim of clinical safety, treatment efficacy, hardware
qualification, or patient suitability. The 200 N value remains the Stage-4
simulation engineering target; it is not a clinical threshold.

## Ordered work phases

1. **Geometry v1 (complete).** Parameterize `W`, `B`, `H`, `E`, and `C`; place
   the robot beside the upper-middle shank; locate the cuff at 72% of shank
   length; and validate the perpendicular inverted-T tool interpretation.
2. **Rigid-interface calibration (complete).** Audit the inherited
   mechanics, calculate mass-based damping, sweep translational and rotational
   candidates, freeze the verified 25 kN/m and 320 Nm/rad pair as
   `Stage-5 Plant v1`, and perform two limited no-learning prescribed-trajectory
   sanity replays.
3. **Research/control contracts (current checkpoint).** Freeze the
   outbound--hold--return task semantics, estimator/MPC/value responsibility
   split, transition-data contract, and minimal Stage-5-only interface plan.
   No controller or learning behavior changes in this checkpoint.
4. **Measurement/calibration replacement.** Replace provisional values only
   after table, robot-base, hip, shank, adapter, and cuff dimensions are
   measured and frame-registered.
5. **Conservative repeated-motion protocol.** Define a separately reviewed
   Stage-5 Experiment Spec with small ROM, low speed, small perturbations, and
   explicit supervisory limits. No values are selected in this checkpoint.
6. **Personalization baseline.** Compare fixed model-based control with rapid
   session-level adaptation under matched cost, constraints, timing, and
   execution boundaries.
7. **Learning-augmented motion coordination.** Only after the earlier gates,
   study learned `q1`/`q2` coordination and cumulative interaction-force
   objectives. RL is not implemented in the geometry checkpoint.

## Exploration-safety intent (future work)

Future exploratory motion should start with small ROM, low speed, and small
trajectory/action perturbations. The supervisor should observe physical cuff
force, force slew/rapid rise, interface deformation, cuff pose error, and the
existing executable-screening/Safety-Filter/BRAKE status. Clearly bad motions
should be rejected or stopped immediately by a separately specified and
validated supervisory policy.

Any future lower exploration-stop threshold is a new Stage-5 supervisory
parameter. It must not redefine the registered Stage-4 200 N engineering
target. Stopping motion also does not by itself prove that a static hold is
feasible; hold, retreat, and load-transfer feasibility require their own model
and validation contract.

## Evidence policy

This checkpoint produces engineering/smoke evidence only. Formal experiments
remain user-run under an approved Experiment Spec. Stage-4 results, hashes,
labels, source artifacts, controller settings, and conclusions remain frozen.
