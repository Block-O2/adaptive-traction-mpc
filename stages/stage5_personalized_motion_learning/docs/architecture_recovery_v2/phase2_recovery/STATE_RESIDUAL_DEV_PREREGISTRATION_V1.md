# State-Conditioned Residual Development Preregistration V1

Status: **FROZEN BEFORE CASE GENERATION OR OUTCOMES**

## Hypothesis and candidate

V2.1's task-wide constant residual is under-expressive across a full
outbound/hold/return trajectory. Hard reference-phase banks were rejected
because they discarded useful global memory, while freezing beta was rejected
because it reduced tail and safety robustness. The candidate therefore keeps
the V2.1 continual beta update and replaces only the constant residual with a
smooth task-agnostic state map.

The fixed features are `[1, q1_ROM, q2_ROM, dq1_sat, dq2_sat]`. Positions are
affinely normalized by the registered Human-V2 ROM. Velocity uses
`dq/(v0 + abs(dq))` with frozen `v0 = 1 rad/s`. Inputs are estimated `q,dq`
only: no task, profile, phase, time, reference, goal, seed, hidden setup, or
simulation truth. The post-beta innovation is
`tau_previous - Y(q_previous,dq_previous,ddq_previous) beta_post`. A normalized
LMS update with frozen alpha `0.20` changes only the next action. Each output is
clipped to `+/-12 Nm` at observed and predicted horizon states; each coefficient
row is additionally projected to L2 norm 12 Nm. The state residual is a
control-effective representation, not an anatomical parameter estimate.

Stage-4 source, plant dynamics, commissioning, geometry, observations,
reference, hidden/generation domain, cost, horizon, constraints, solver, and
controller RNG remain unchanged.

## Matrix and frozen promotion rules

- 24 fresh paired development cases under `ARV2-P2-RECOVERY5-DEV1`;
- four profiles x standard/high ROM x three replicates;
- arms: state residual candidate, V2.1 constant residual, commissioning-only,
  and oracle;
- exactly 96 rollouts, full denominator, no replacement or exclusion;
- no feature or hyperparameter screening on these cases.

Promotion requires candidate completion not below V2.1, aggregate median RMSE
strictly lower than V2.1, and p95 RMSE no worse than V2.1. The unchanged
absolute gates are completion at least `0.90`, median RMSE at most `3 deg`, p95
RMSE at most `5 deg`, full-episode force at most `200 N`, full-episode moment at
most `60 Nm`, and zero ROM, clearance, solver, consistency, settle, or safety
events. Candidate and oracle must each provide 24/24 full-horizon metrics;
oracle must complete 24/24 and pass the same zero-event and `200 N / 60 Nm`
limits. The candidate must beat commissioning-only by at least 20% median or
0.25 completion rate and remain within `2.5 deg` median of oracle.

Weights and outputs must remain finite and bounded: both coefficient-row L2
norms at most 12 Nm and every residual output at most 12 Nm by construction.
Coefficient projection, observed-output clipping, prediction-dynamics
clipping, chosen-rollout clipping, coefficient norm/max step/total variation,
and residual max/variation/sign reversals must all be present and finite; cap
hits are reported as fragility evidence rather than silently excluded. Full-
denominator failures remain in every aggregate. No threshold may be weakened
after outcomes.
