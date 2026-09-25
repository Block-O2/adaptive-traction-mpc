# DGN V1 — causal questions and smallest discriminating checks

All original formal V1 cases are now *development diagnostic* material only.
No original result is rewritten or relabeled as new held-out evidence. The
baseline is the local source in `SOURCE_SNAPSHOT.md`; controller parameters,
plant, task, thresholds and 100 ms rule are fixed. New output paths use
`results/full3d_adaptive_integration_v1/startup_dgn_v1/`.

## Group A — source and stored-trace alignment (no rerun)

Hypotheses: (A1) a software initial-support predicate rejects otherwise
assembled CR12 configurations; (A2) the 17 commissioning handoffs miss the
registered start because true motion did not follow the emitted reference;
(A3) a model-switch-induced q estimate jump, rather than physical motion,
creates the handoff label; (A4) bed contact precedes the first material
tracking divergence and may corrupt free-motion identification.

Manipulation: none. Read three shared exception tracebacks, representative
failed-case physical traces, the nominal development comparison, and source.
Align q/dq reference, estimated/true q/dq, CR12 torque, cuff pose/twist/wrench,
contact, fit/updates and handoff by physical timestamp. First-divergence
criterion is the *existing* 1 deg angle/2 deg/s velocity task-start tolerance,
used descriptively, not a new control threshold. The ordering of onset, not
mere co-occurrence, will discriminate A2/A4. A3 predicts a qhat discontinuity
at fitting with no corresponding qtrue movement. Stored 5 ms contact flags
cannot provide exact 0.25 ms onset or bed normal load, so those remain open
unless a single focused physical instrumentation run is justified.

## Group B — targeted baseline physical replay only if Group A is ambiguous

Candidate: one failed handoff case and one nominal development case, never the
whole 72-arm campaign. Instrument evaluation-only bed contact force/impulse,
model-activation before/after qhat/command and reference continuity without
changing baseline decisions. Fixed: same local source, case, plant, prior,
task, controller parameters, 5 ms/0.25 ms stepping. Evidence label:
development diagnostic; planner wall time is not compared as production
runtime when instrumentation adds overhead. Compare physical state/trace to
the saved formal baseline; if exact replay differs, disclose the mismatch.

## Group C — isolated counterfactual only if causal distinction remains

Possible one-at-a-time, nondeployable variants: post-hoc oracle-state
substitution at the same saved boundary to separate estimator error from
physical reference error; frozen-model versus fitted-model continuation;
reference-anchor predicate evaluation on saved state. These must not become
production defaults or be described as qualification. Exact saved-state
branching needs MuJoCo/controller/reference/estimator/RNG/pending-plan state;
absent that, a matched rerun is not an exact branch.

Stop when the major mechanisms and one justified DEV decision are supported.
Do not infer dynamic inability from a predicate/IK rejection, and do not
declare contact causal merely because contact is present.
