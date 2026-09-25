# DEV-A recovery V1 — restart checkpoint

Date: 2026-09-23. Phase: **DEV-A complete**;
`DEV_A_PARTIAL_MODEL_OR_EXECUTION_LIMIT_REMAINS`. Final 24-case adaptive
development regression V2 and independent Auditor completed; V1 preserved.
Current
branch `codex/stage5-architecture-recovery`, HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. Entry
`git status --porcelain=v1 --untracked-files=all` counted 578 paths:
566 older dirty/untracked paths plus 12 DGN docs/scripts. No Git mutation is
authorized; none has occurred.

Authoritative local evidence is sibling `startup_dgn_v1/` (`DGN_COMPLETE`,
independent PASS). Historical formal qualification remains
`FULL3D_FRESH_FAILED_WITH_EVIDENCE`; its cases may be reused only as
development cases. Keep all geometry/beta/residual update laws, limits, plant,
task and 100 ms deadline unchanged. DEV-A source changes are uncommitted.

Source path reconstructed: `runtime.py::_initialize_loaded_runtime` applies
`HumanWaypointMPCShadowContractV1.prepare` task-progress validation to
`initial_support`; the commissioning loop then physically runs 7.02 s with
nominal model and ends at the registered start *reference*, fits/replays the
model, immediately activates new geometry/dynamics, and calls
`task.py::start_episode` without a physical recovery interval. Its task loop
already uses measured 5 ms q/dq PD. The relevant production files are
`human_waypoint_shadow.py` and `full3d_adaptive_integration_v1/runtime.py`.

Additional source-grounded pre-change check: on old DEV case
`balanced_ordinary_r01`, the accepted geometry fit maps the same task-start
q to a Human cuff position **16.97 mm** away from the nominal mapping. This
is an offline comparison of desired poses, not an observed actuator jump;
it makes a bumpless model/reference transition a real DEV-A requirement.

Implemented: non-task execution context preserves task-stage progress checks;
the three formerly pre-step cases now each executed 7.02 s / 28,080 MuJoCo
steps under unchanged commissioning before the old handoff failed. A versioned
ACTIVE_RECOVERY lifecycle now schedules from the *emitted* reference with a
fresh measured-error correction target, retains all scheduler/clearance and
mechanics checks, physically advances CR12+cuff+Human while planning, and
returns/settles at the original task start. The first recovery segment bridges
the old/new desired robot cuff pose with a C2 quintic; no Human state reset.
The beta/residual estimator law and cadence are untouched.

Targeted preserved evidence: `representative_v1/balanced_ordinary_r01` failed
under the initial measured-state-as-reference proposal; `representative_v2/`
recovered in 3.045 s, then task planner rejected an endpoint for the existing
conservative clearance contract. `targeted_v1/` recorded initial broad-offset
infeasibilities. `targeted_v2/hip_dominant_near_upper_current_rom_r01` (one
formerly pre-step case) and `hip_dominant_ordinary_r02` both recovered in
3.045 s, then failed downstream with a task stale-plan and OUTBOUND timeout,
respectively. `targeted_v2/balanced_ordinary_r02` is still fail-closed because
the starting emitted reference has −5.053 mm deployable clearance under the
fitted session contract. `nominal_development_v1` completed the full task
after recovery. These are consumed/development cases, not fresh qualification.

Known open item: despite a C2 desired cuff-pose bridge, fitted-model
activation is associated with a first 5 ms CR12 torque-command step up to 34.780 Nm,
allocated force/moment step up to 49.582 N / 9.730 Nm (balanced
near-upper-current-ROM R01). Do not claim action/wrench/torque bumplessness.

First complete 24-case `regression_v1/`: 24/24 initialization and
commissioning, 15/24 recovery success/task entry, 2/24 full task COMPLETE;
four stale-plan task aborts, no new formal qualification claim. This revealed
one unnecessary second zero-displacement recovery segment on nominal and
imprecise no-feasible labeling when the remaining 10 s window was too short.
Both lifecycle details were repaired without changing model/safety/task
semantics; `nominal_development_v2` completed with 1.525 s (rather than
3.035 s) recovery. `regression_v2/` is the final-source development replay:
24/24 physical commissioning, 15/24 recovery success and task entry, 2/24
full tasks COMPLETE, 22/24 aborts preserved. Final aggregate is
`regression_v2/regression_summary_v2.json`; the prior derived summary remains
preserved. The independent `AUDIT_REPORT.md` finds bounded development
evidence PASS but complete varied-task repair FAIL, highlights a 34.780 Nm
first fitted-model CR12 command step and correctly classifies five early
segment-budget timeouts. Focused tests 15/15, `py_compile`, and
`git diff --check` pass. No fresh qualification, DEV-B, large-ROM or learning
was started; no Git mutation.

One next stage only: a matched, versioned DEV-B first-divergence diagnostic
that separates Human-model, state-estimation, CR12 execution and cuff
transmission error while explicitly testing model-activation command
continuity. Do not treat DEV-A as a fresh generalization result.
