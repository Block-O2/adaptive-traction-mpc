# Commissioning-Beta Plus Residual Development Preregistration V1

Status: **FROZEN BEFORE CASE GENERATION OR OUTCOMES**

The hypothesis is that simultaneous task-phase beta refitting and residual
adaptation create two competing representations for the same generalized
torque mismatch. The candidate freezes beta exactly at task handoff and adapts
only the bounded task-wide residual. Every eligible causal sample uses
`tau_previous - Y_previous beta_commissioned`. It performs zero task
`dynamics.observe` calls and zero task beta updates.

Residual alpha `0.20`, component cap `+/-12 Nm`, commissioning, geometry,
observations, reference, hidden/generation domain, MPC cost, horizon,
constraints, solver, and all mechanics limits remain unchanged. The rejected
phase-bank state is not used.

- 24 fresh paired development cases under `ARV2-P2-RECOVERY4-DEV1`;
- four profiles x standard/high ROM x three replicates;
- arms: residual-only candidate, V2.1 combined beta+residual, commissioning-only,
  and oracle;
- exactly 96 rollouts, full denominator, no replacement or exclusion.

Promotion requires: candidate completion not below V2.1; candidate median
strictly lower and p95 no worse than V2.1; at least 20% median benefit or 0.25
completion advantage against commissioning; unchanged completion, tracking,
oracle-gap, wrench, clearance, ROM, consistency, settle, solver, safety, and
finite/bounded-residual gates; and exactly zero candidate task beta attempts
and accepted updates. Simplicity is considered only if every performance
condition passes. No parameter or threshold may be tuned on this set.

