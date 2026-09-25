# DEV-D rigid-table reference repair — versioned development contract

The physical support is a fixed hard table. A fixed proximal thigh collider
may not begin inside it. Moving-limb contact is not automatically prohibited,
but the reference generator must not intentionally request rigid-body
penetration. The previous rigid-table assembly v1/v2 cases and every failed
outcome remain unchanged. This stage is development simulation, not fresh
qualification.

Authorized changes are commissioning/recovery reference generation,
deployable path-level geometry checks, related logging/tests and a generic
generation-side setup repair if supported. First comparisons hold the geometry
estimator/priors, beta and residual learning, task MPC objective, DEV-C-off
state, CR12/cuff/Human plant, physical limits, contact parameters, 100 ms
stale-plan rule and zero value hook fixed. No hidden patient geometry or true
q/dq enters deployable action selection. The old24 cases are consumed
development evidence; no failed case is removed or silently replaced.

Working gate sequence: (1) synchronize requested/estimated/true paths and
locate first violation, (2) demonstrate deployable whole-path checking and
an informative feasible commissioning path on representative cases,
(3) test real CR12–cuff–Human execution and recovery, (4) only then run broad
development replication, (5) independent source/trace audit. If a frozen
adaptive or physical component must change, stop at the explicit scope
boundary rather than change it implicitly.
