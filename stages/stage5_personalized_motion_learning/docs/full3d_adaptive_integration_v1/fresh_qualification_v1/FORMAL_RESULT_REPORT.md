# Fresh varied full-3D qualification V1 — formal result

**Terminal classification: `FULL3D_FRESH_FAILED_WITH_EVIDENCE`.** This is a
failed *current-domain* qualification, not a reduced-Human substitute and not
large-ROM validation. The controller did **not** demonstrate generalization:
there were zero complete OUTBOUND/HOLD/RETURN tasks in all three paired arms.
The three pre-step runner-exception cases are retained, not replaced; only
21/24 keys reached physical CR12 commissioning. The latter 21 alone contain
zero adaptive task completions. Independent result audit is recorded in
`FINAL_AUDIT.md`.

## Frozen provenance and domain

The pre-outcome contract is `PREREGISTRATION.md`. Its freeze manifest hashes
309 source/config/model/native-backend files at branch
`codex/stage5-architecture-recovery`, HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`; the manifest SHA-256 is
`8545edac3f6d2febbac1c129fc86021a3547b96c5d62dbeae41d23d84044fa9c`.
An independent Auditor drew uint64 seed `18386242844751736710` after freeze;
`SEED_MANIFEST.json` SHA-256 is
`e6352b342f63ac20582b631597ec37fbe5bc0e05ee840f6cd359ba8da44a3b9c`.
The full 24-case bundle and 34-proposal ledger regenerate exactly from the
frozen generator and seed (accepted 24, rejected 10, acceptance 70.59%). No
post-outcome exclusions, replacements, seed edits, source edits, controller
retuning or gate edits occurred.

The paired conditional domain is 4 task families (`balanced`,
`knee_dominant`, `hip_dominant`, `elevated_start`) × 3 current-ROM cells
(`ordinary`, `middle`, `near_upper_current_rom`) × 2 replicates. Each case
independently draws body mass 67–83 kg, height 1.68–1.76 m, thigh/shank length
scales 0.97–1.03, segment mass scales 0.90–1.10, COM fractions 0.40–0.47,
inertia-radius fractions 0.27–0.33, q1/q2 passive stiffness 7–13 Nm/rad,
damping 3.5–6.5 Nms/rad, rest offsets 3–8/7–14°, cuff fraction 0.69–0.75 of
the shank, and sagittal hip x/z shifts ±10/±6 mm. Start/goal jitter is
±1.5/±2°. All initial physical velocities are zero. Generation-side true
static clearance ≥2 mm, initial shank/bed noncontact and CR12 endpoint IK
condition acceptance; that is not a dynamic feasibility guarantee. Bed,
robot base, cuff compliance, observation model, task limits and current
Human ROM (q1 0–80°, q2 0–100°) remain registered. The current task API varies
task/goal profile and endogenously chosen quintic duration, not an externally
specified arbitrary speed waveform. This is explicitly *not* the future
120–130° study.

The paired arms use the same hidden case and physical commissioning: continual
beta+residual adaptation; commissioning-only with both task-period updates
frozen; and fixed-population geometry/beta/zero residual, without using the
commissioning fit. No oracle or learned value arm was run; the value hook was
zero. Simulation sensors provided robot q/dq, cuff pose/orientation, ideal
twist and physical interface wrench at 200 Hz, with zero configured noise,
bias and latency; ideal twist remains a transfer limitation. Hidden Human
state and geometry were confined to plant/generation/evaluation.

## Outcomes and failure taxonomy

| Arm | Complete / 24 | Physical commissioning / 24 | Started nonzero task / 24 | Aborts / exceptions |
|---|---:|---:|---:|---|
| Continual adaptive | 0 | 21 | 3 | 21 aborts, 3 pre-step exceptions |
| Commissioning-only | 0 | 21 | 3 | 21 aborts, 3 pre-step exceptions |
| Fixed population | 0 | 21 | 4 | 21 aborts, 3 pre-step exceptions |

Continual-adaptive and commissioning-only have the same mutually exclusive
failure counts: **17** commissioning handoffs not settled, **3** initial
support validation exceptions (`waypoint moves away from the registered phase
goal`), **1** deployable clearance abort at handoff, **1** no feasible
waypoint, **1** realized cuff-force limit, and **1** stale-plan deadline abort.
Fixed population has 15 handoff-not-settled, 3 initial-support exceptions,
3 deployable-clearance aborts, 1 no-feasible waypoint, 1 stale-plan abort and
1 OUTBOUND timeout. Every accepted case remains in all three denominators.

The three shared exceptions are `hip_dominant_near_upper_current_rom_r01`,
`elevated_start_ordinary_r02`, and `elevated_start_middle_r02`. They arise
in `_initialize_loaded_runtime` before any MuJoCo step; therefore do not
claim 24/24 physical rollouts. The frozen generation screen accepted static
mechanics but missed this initial-support task-validation precondition. This
is a protocol/executability failure, not evidence of physical controller
behavior on those three cases. The pre-registered accounting gate expressly
preserves runner exceptions; its `g1=true` means only that all 72 outcomes
were accounted for, **not** that all 72 were physically executed or that the
truth firewall was independently certified by that Boolean.

In the 17 adaptive handoff failures, the estimated state at the physical
handoff missed the frozen task start by median absolute q1/q2 errors
1.336°/3.843° (maximum 4.454°/8.797°), against 1° per-joint start/goal
tolerance. Median absolute dq errors were only 0.015/0.014°/s; the dominant
failure is position settling, not velocity. These failures came after physical
CR12-driven commissioning, not a scripted state jump. With task time 0 they
cannot inform task-period adaptation benefit. Commissioning shank/bed contact
was observed in all 21 physically commissioned adaptive cases (1,966–10,173
monitored observations per case); the pre-frozen task-period safety gate does
not count commissioning contact. This is a serious limitation for any broader
safety claim and is **not** concealed or retroactively made a new gate.

The three adaptive task-started cases failed as follows:

| Case | Task time | q / dq RMSE | Task cuff force integral | Peak physical force | Failure |
|---|---:|---:|---:|---:|---|
| `knee_dominant_middle_r02` | 2.555 s | 1.364° / 13.312°/s | 298.807 N·s | 147.486 N | no feasible waypoint; conservative predicted target endpoint clearance −7.746 mm while actual executed-path minimum was +26.166 mm |
| `knee_dominant_near_upper_current_rom_r02` | 1.975 s | 4.085° / 18.775°/s | 275.893 N·s | 200.017 N | realized cuff force exceeded frozen 200 N limit by 0.017 N; fail-closed |
| `hip_dominant_middle_r01` | 2.620 s | 0.746° / 6.821°/s | 287.518 N·s | 147.909 N | planner 108.069 ms >100 ms, stale plan rejected |

These RMSEs are explicit-boundary time-aligned *partial-task* tracking
diagnostics; there are no completed-case q/dq tracking statistics. The
partial-task q p95 absolute errors were 3.048°, 9.904°, 1.703° respectively.
No case reached a valid HOLD or RETURN. Terminal errors after an abort are not
interpreted as completed-return accuracy.

Across adaptive task intervals, actual physical cuff force integrals were
298.807, 275.893 and 287.518 N·s (sum 862.218 N·s); moment integrals were
27.020, 35.606 and 35.180 Nm·s. These are left-boundary wrench-norm sums
weighted by the actual physical interval duration, not an optimized learning
objective, and commissioning exposure is not included. The adaptive maximum
task/handoff measured force/moment were 200.017 N / 37.676 Nm. Maximum CR12
torque-command fraction was 0.816; recorded task ROM and actual acceleration
violations were zero in the 21 physical adaptive cases. The minimum
deployable predicted clearance was −6.689 mm at handoff; the evaluation-only
true physical minimum was −0.00743 mm with one task-boundary shank/bed contact
(`balanced_ordinary_r02`, before any task interval). Predicted and true
clearances are distinct and were never interchanged in controller inputs.

## Adaptation, timing, and frozen gates

Only three adaptive cases reached task-period updates. Together they made
15 beta proposals/15 accepted updates; 5 hit the frozen 3%-of-span per-update
cap; 352 nonzero residual updates were recorded. Last accepted beta-step L2
norms were 0.279, 0.164 and 0.159 in the three cases; hence these partial
episodes do **not** show settled adaptation, and some updates remained
step-limited. The other 21 cases provide no task-period beta convergence
evidence; physically commissioned cases still preserve their geometry fit,
beta initialization and residual/commissioning traces. Neither comparator
had task-period adaptive updates. The combined continual layer cannot be
credited with an improvement because no arm completed a case.

Across the 12 adaptive planning calls, compute-time mean/median/p90/p95/p99/
max were **70.134 / 64.012 / 99.419 / 103.410 / 107.137 / 108.069 ms**.
The worst call was in `hip_dominant_middle_r01`; the physical plant executed
the previous reference up to the 100 ms watchdog, then aborted with
`STALE_PLAN_MAXIMUM_AGE`. Adaptive had one deadline miss, and each comparator
also had one; **zero** stale plans were activated in any arm. Request-time
measurement age was recorded as 0 under the ideal synchronous 200 Hz sensor
model. This failure does not negate the earlier runtime-development result;
it shows the unchanged 100 ms end-to-end contract was not met on this fresh
conditional domain.

Frozen gate result from `ANALYSIS.json`: provenance/accounting `g1=true`
(subject to independent audit); completion/cell coverage, adaptive physical
safety, deadline, completed-case tracking, adaptation coverage, and paired
effect gates `g2`–`g7` are all **false**. The complete-case tracking gate is
unassessable numerically because there are zero complete cases and therefore
fails by its frozen rule. No unsupported adaptive-vs-oracle or survivor-only
claim is made.

## Reproduction, evidence, and scope

The sealed `formal_case_bundle_v1/generation_summary.json`, all 24 case JSONs,
34-proposal ledger and `formal_paired_v1/STATUS.json` are restart/review
anchors. `formal_paired_v1/ANALYSIS.json` contains every case×arm row and
frozen gates; individual arm directories contain `summary.json`, `trace.npz`,
config snapshot and learning transitions, or a preserved
`runner_exception.json`. `STATUS.md` records the exact formal command and
the development failures. Focused post-watchdog tests: 14 passed;
`git diff --check`: passed. Earlier development-only injected stale/no-feasible
diagnostics and nominal physical regression remain separate from formal data.

This worktree is not clean-clone reproducible: at least 80 of the 309 frozen
dependencies are not Git-tracked and another 10 tracked dependencies have
uncommitted modifications. `FREEZE_MANIFEST.json` holds the exact required
path/hash list; `FREEZE_GIT_STATUS.txt` holds the pre-outcome dirty snapshot.
Pre-existing unrelated Stage-4 work is left local. No file was staged,
committed, pushed, reset, stashed, deleted or branch-switched.

Qualification-preparation source changed before the seal:

- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py` and
  `cr12_plant.py` (physical case/arm execution, monitoring, timing and
  provenance);
- `src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py`
  and `phase3_human_waypoint.py` (diagnostic beta-step fields and fixed-nominal
  provenance); neither changed the frozen beta/residual law;
- `src/traction_mpc_stage5/fresh_qualification_v1/{__init__,scenario,domain,physics_monitor}.py`;
- `scripts/{run_fresh_full3d_case_v1,generate_fresh_full3d_cases_v1,freeze_fresh_full3d_v1,run_fresh_full3d_batch_v1,analyze_fresh_full3d_v1,test_fresh_full3d_watchdog_v1}.py`;
- `configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json`
  and `tests/fresh_qualification_v1/test_domain_and_firewall.py`.

The new documentation namespace contains this report, preregistration,
freeze/status/seed manifests and independent audit records. The new results
namespace contains development diagnostics, sealed case generation and
72 formal arm artifacts. These changes do not alter the historical nominal
attempts 11–14 or the runtime-study evidence. All scientific constraints,
candidate set, task, cost, value=0, 100 ms deadline, beta smoothing/cap and
physical CR12/cuff/Human plant remained unchanged. No RL, large-ROM or
hardware experiment occurred.

Exactly one recommended next step: run a **new versioned development-only
commissioning/handoff-and-case-executability diagnosis** before any fresh
qualification rerun, using separate development cases and a new future
held-out seed namespace; do not tune on these 24 formal cases.
