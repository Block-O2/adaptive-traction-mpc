# Planner runtime engineering study V1

Terminal status: `PLANNER_RUNTIME_QUALIFIED` (2026-09-23), limited to the declared
development runtime corpus and existing controlled simulation timing boundary.

Preserved integration status: `FULL3D_CORE_VALIDATED_TARGET_DOMAIN_INCOMPLETE`.
Branch: `codex/stage5-architecture-recovery`.
Starting HEAD: `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`.
No staging, commits, pushes, branch changes, resets, stashes or deletions authorized.

Contract: preserve task, model, adaptation, action lattice, checks, costs,
clearance floor, zero value and 100 ms stale-plan rejection. Development runtime
evidence only. No varied qualification or ROM expansion. Historical runs stay intact.

Plan: reconstruct attempts 12/13 with saved belief and previous action; profile
before changes; freeze smallest justified repair; compare all historical inputs
and deterministic edge cases; execute at least 400 isolated calls; only after
timing passes run 3 existing nominal timing-aware full-3D development regressions;
fresh-context independent audit; report all failures. Two repair/audit cycles
maximum before classifying remaining limitations. No scientific tuning.

Evidence: exact attempt13 decision10 reproduced 2083.883--2107.076 ms with
matching CPU time. return_dq_07 exhausts 1743 durations although its endpoint
is below the frozen endpoint floor. An endpoint necessary-condition early
rejection preserves all original checks and tolerances (1 nm guard routes
roundoff-adjacent cases through the original search). 46 paired old/new inputs
match to 1e-10. 552 shuffled repaired invocations: max 67.652042 ms, no deadline
miss. No scientific variable changed. Independent Auditor running.

Completed: three timing-aware nominal regressions COMPLETE, all trace checks
pass; 19 tests pass; independent fresh-context Auditor PASS. Injected 110 ms
delay correctly produces stale abort with zero task intervals. Corrected
attempt12 reconstruction matches attempt13; incorrect initial reconstruction
is preserved and explicitly rejected. REPORT.md contains all timing boundaries.

No further work in this study. Exactly one recommended next step: preregister
fresh varied full-3D qualification separately. No such qualification is started.
Branch/HEAD unchanged; no staging/commit/push/reset/stash/deletion.
