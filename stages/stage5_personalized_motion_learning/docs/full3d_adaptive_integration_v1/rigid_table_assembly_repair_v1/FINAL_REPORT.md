# Rigid-table assembly repair and unchanged-controller development replication v1/v2

**ASSEMBLY_REPAIR_PARTIAL**

This is a versioned DEVELOPMENT result on consumed historical cases, not fresh
full-3D qualification. The approved physical interpretation is a fixed hard
table with fixed hip. We removed the demonstrated fixed proximal thigh–table
overlap artifact without touching controller or contact-physics parameters,
then executed the actual coupled CR12–cuff–Human controller. Complete
assembly/path validity and reliable task completion remain unproven.

## What was assembled incorrectly; exactly what changed

The old frozen generator independently sampled hip vertical shift in
`[−6,+6] mm` around nominal geometric tangency. The fixed thigh capsule has a
50 mm radius and starts at the fixed hip; bed plane is `z=12 mm`, nominal hip
center `z=62 mm`. Therefore `g_proximal = z_hip − 50 − 12 mm = Δz_hip`.
Eleven of the historical 24 proposals embedded the fixed proximal capsule
0.329–5.967 mm into the table. Joint motion cannot release this overlap. The
previous diagnostic strongest case, −4.819128 mm, produced about 33.35 kN
simulated bed–thigh normal reaction throughout the 0.1 s new mechanical
prefix and historically through a 7.025 s commissioning prefix. This is a
simulation contact result, not a validated human load.

For a NEW version only, legal positive installation gap is 0.1–6 mm. A
`1e−9 m` numerical signed-distance tolerance remains distinct from the 0.1 mm
positive design gap. The historical negative shift is mirrored to its same
positive magnitude for a development counterpart; existing legal placements
stay exactly unchanged. Tangency is moved only to +0.1 mm. This rule was set
from fixed geometry and pre-controller solver evidence, not success outcomes.
Table, thigh/shank/cuff collider shapes, masks and contact parameters remain
unchanged. The simulator rebuilds Human placement, cuff target, robot initial
IK and fresh compliant-interface state; no old fitted belief or checkpoint is
reused. The historical case files, failed qualification and 33.35 kN record
remain intact.

All 24 old cases are in `assembly_v1/OLD_TO_NEW_CASE_MAPPING.json`, with
original/revised hashes and exact changes. Thirteen case JSONs are unchanged;
eleven differ only in hidden hip-z sign. Twenty-two pass the VERSIONED
initial/task-endpoint assembly screen. Two previously positive-thigh-gap
cases remain invalid: `balanced_near_upper_current_rom_r02` has a −1.773 mm
initial sleeve–table signed distance and `balanced_ordinary_r02` −2.513 mm.
The sleeve collision mask is off, but the modeled envelope geometrically
intersects the rigid table. They were not forced into execution and remain in
the 24-case denominator **for v1**. The screen does not call an IK-search failure proof
of physical infeasibility. A separate evaluation-only replay of 22 initial
and task-goal IK poses found maximum CR12-to-desired-cuff position/rotation
errors `3.33e−13 m` / `2.07e−13 rad` and minimum joint-limit margin
`1.858 rad`; these are static screen IK poses, not loaded-support executed
robot initial states, and do not certify intermediate robot paths.

An explicitly separate v2 geometry-only extension uses the v1 initial sleeve
gap, not any controller outcome, to calculate the minimum further upward
installation shift within the original +6 mm ceiling. It makes
`balanced_near_upper_current_rom_r02` initially valid by adding 1.873398 mm
to reach +3.650576 mm hip shift and +0.1 mm static sleeve gap. All 22
v1-valid case JSONs remain unchanged. `balanced_ordinary_r02` would need
+7.178067 mm total height and remains invalid. V2 therefore admits 23/24
initial/task-endpoint assemblies, not complete-path validity. See
`ENVELOPE_EXTENSION_V2.md` and the separate `assembly_v2/` mapping.

## Mechanical effect, separately from control performance

The pre-outcome static check measured about 1303.829 N initial thigh contact
at a deliberately invalid −1 mm gap, versus zero initial thigh contact at
0, +0.01, +0.05, +0.1 and +0.2 mm for the tested template. Exact tangency is
still excluded: historical nominal commissioning reached 195.003 N despite
nominal near-zero signed gap. In 0.1 s real MuJoCo stepping with zero robot
control but intact CR12/cuff/Human physics, the historical strongest case
remained at 33,353.295 N and 3335.330 N·s thigh normal impulse; its repaired
counterpart had zero thigh contact/force. This short unactuated prefix is
mechanical evidence, not controller success.

Across all 22 v1 finalized executed-session artifacts, the thigh–table pair
had 0 N peak, zero detected duration and zero normal impulse at every native
0.25 ms executed interval. Thus the specific fixed-overlap reaction
disappeared in the tested repaired assemblies. Shank–table contact did not:
peaks ranged up to 124.037 N, normal impulses 5.596–116.876 N·s and detected
duration 0.498–1.272 s. Moving-limb contact was not automatically forbidden
or silently treated as safe; the original monitoring/abort conditions remained.

The additional 5 ms executed-boundary geometry audit found positive minimum
thigh gap +0.329 mm, modeled cuff-bar–table +41.687 mm, adapter–table
+114.977 mm, modeled CR12 links 2–6 to table +125.773 mm, and those links
to Human +38.772 mm across these 22 traces. Base/link1 were inventoried at
reset, not included in this executed-path minimum. All 22 had some shank penetration during
commissioning (worst −1.221 mm). One had disabled-collision sleeve–table
overlap −0.479 mm during commissioning. These sampled distances do NOT prove
continuous-time collision freedom or real hardware envelope safety. The one
v2 supplemental physical session also had zero thigh–table contact over
28,080 native 0.25 ms intervals; its shank normal peak was 129.565 N and
impulse 124.444 N·s. A 5 ms path audit nevertheless measured a
collision-disabled sleeve–table distance of −3.132 mm. Static initial
sleeve clearance did not solve the dynamic envelope problem. We did not
choose another hip shift from that observed outcome.

## Unchanged-controller physical replication

Every executed case used `run_executed_case` with
`dev_a_recovery=True`, `dev_c_bumpless_transfer=False`, continual adaptive arm,
timing-aware physical planning-delay replay and `formal_qualification=False`.
The actual six-axis CR12 MuJoCo actuators drove the compliant cuff and Human;
new deployable observations fed the existing geometry/beta/residual and
waypoint controller. No Human generalized torque, ideal wrench or scripted
state motion replaced the plant. All 607 prior local source/config/model
dependency hashes still match the previous frozen baseline. We changed no
existing controller source, estimator law, beta cap/smoothing, candidate cost,
task, ROM, force/moment/acceleration/robot limit, contact physics, stale-plan
threshold or value hook.

| DEVELOPMENT cohort | Cases | Commissioning | Recovery succeeded | Task entered | Complete |
|---|---:|---:|---:|---:|---:|
| Historical DEV-A original assemblies | 24 | 24 | — | 15 | 2 |
| New initially/endpoint-valid revised assemblies | 22 | 22 | 22 | 22 | 5 |
| V1 remaining sleeve-invalid assemblies | 2 | not executed | — | — | — |
| V2 geometry-only supplement, formerly invalid | 1 | 1 | 0 | 0 | 0 |
| V2 still-initially-invalid case | 1 | not executed | — | — | — |

The final tested-set accounting is **23 distinct executed development cases:
23 commissioned, 22 reached task, 5 completed, 18 aborted; one of the old
24 remains initially invalid and unexecuted**. It consists of the v1
22-case batch plus one later, separately versioned v2 supplement—not one
fresh or homogeneous held-out 23-case campaign. The supplement finished
commissioning but its first ACTIVE_RECOVERY decision rejected all five
segments because the estimated origin's existing shank–table clearance was
−0.931382 mm. It aborted `ACTIVE_RECOVERY_NO_FEASIBLE_SEGMENT` before task;
the recovery planning call took 0.395 ms. No controller or physics parameter
was changed between v1 and v2.

Among the 11 reflected cases, old DEV-A had 4 task entries and 0 completions;
the revised development counterparts had 11 task entries and 3 completions.
Among 11 byte-identical legal cases, both old and new had 11 task entries and
2 completions. These are comparisons across changed physical assemblies,
not exact-state causal branches or independent held-out generalization. Five
of the 22 executed cases completed OUTBOUND/HOLD/RETURN, 17 aborted:
8 `STALE_PLAN_MAXIMUM_AGE`, 5 `NO_FEASIBLE_WAYPOINT` (shank–table geometry),
3 `TASK_VELOCITY_LIMIT`, 1 `SESSION_CLEARANCE_LIMIT`. No failure was removed.

The five completed cases had time-aligned task q RMSE (q1/q2, degrees):
`balanced_middle_r01` 0.889/0.994;
`elevated_start_ordinary_r01` 0.545/0.448;
`elevated_start_ordinary_r02` 0.647/0.523;
`hip_dominant_ordinary_r01` 0.713/0.334;
`hip_dominant_ordinary_r02` 0.672/0.359. The full-session recorded 5 ms
boundary physical cuff-force peaks across 22 were 109.403–159.471 N; maximum
recorded cuff moment was 22.792 Nm, and the executed-5-ms-control-interval cuff-force
integrals were 205.923–898.391 N·s (measured norm times each executed
control interval, not a native 0.25 ms cuff-force quadrature).
No recorded Human ROM or actual acceleration violation occurred; evaluated
robot command and velocity were at most 57.6% and 28.4% of their registered
limits, respectively. One deployable clearance monitor reached −0.0507 mm
and correctly aborted; the task-only true shank clearance diagnostic minimum
was +10.426 mm. These distinct quantities must not be conflated.

Adaptation was not replaced by static belief: task traces recorded 267
accepted beta updates and 10,242 residual updates in aggregate. This is
evidence of updates, not of convergence or model correctness. Early
commissioning remained problematic: every executed case's *prescribed*
commissioning reference has a static shank gap below the rigid table, from
−6.417 to −49.482 mm. The physical Human instead makes shallow contact;
median absolute end-of-commissioning q error is 0.759/1.780 degrees, worst
2.538/7.664 degrees. The original contract permitted commissioning shank
contact, so these are not retroactive formal failures. But the requested
reference is not fully realizable on the clarified hard table and may
contaminate identification/tracking interpretation. Its causal contribution
to all downstream failures is not yet established.

Timing remained an independent limit in the v1 22-case batch: 125 high-level planning calls had
median 60.028 ms, p90 98.310 ms, p95 101.908 ms, p99 120.689 ms and maximum
121.485 ms. Eight calls exceeded the unchanged 100 ms age contract, and eight
cases aborted stale-plan rather than silently activating a late result.
Physics advanced under controlled planning-delay replay; the simulator is not
claimed to be asynchronous hardware realtime. Runtime optimization and
controller retuning were outside this assembly-effect stage.

## Interpretation and next step

The fixed proximal overlap was a real model-assembly defect and its extreme
reaction was removed in all 23 tested revised sessions. That does **not** mean
the full current-domain controller is qualified: 18/23 executed sessions
failed, one old case was not made initially valid, the commissioning
reference asks for impossible hard-table postures, and two executed sleeve
envelopes intersect the table despite no collision response. The first
material divergence on a legitimate initial assembly occurs during
commissioning, before task control: requested shank geometry crosses the
fixed table, actual motion contacts the table and departs from that reference.
This mechanism precedes, but is not proven to cause, the later planner and
velocity aborts.

**Single recommended next control-development objective:** version and test a
rigid-table-feasible, feedback-observed commissioning reference path while
holding the adaptive estimator, task controller and physical limits fixed;
reassess model fit and downstream full-session behavior only after that
reference is physically realizable. This targets the admitted development
cases; it does not make the remaining initial sleeve-invalid setup eligible,
and it does not by itself resolve the observed dynamic sleeve overlaps. A
separate future assembly/geometry decision is needed before any full-24
claim. This task does not implement that next
stage, launch fresh qualification, extend ROM or train a value policy.

## Reproducibility and evidence links

- `SETUP_CONTRACT.md`: frozen new interpretation/rule; `DESIGN_AND_CHANGES.md`:
  mechanical and control-isolation decisions.
- `COMMANDS.md`: exact environment and commands;
  `CHANGED_FILES.md`: added paths and untouched dependencies.
- `assembly_v1/OLD_TO_NEW_CASE_MAPPING.json`, `STATIC_CONTACT_SWEEP.json`,
  `prefix_v1/PREFIX_CONTACT_RESULTS.json`: construction/probing and hashes.
- `ENVELOPE_EXTENSION_V2.md`, `assembly_v2/OLD_TO_NEW_CASE_MAPPING.json`,
  `supplemental_v2/balanced_near_upper_current_rom_r02/`, and
  `trajectory_geometry_supplemental_v2.json`: supplementary geometry-only
  extension, its failed physical run and sampled-path geometry.
- `representative_v1/`, `broad_old24_valid_v1/`: original full-session
  `summary.json`, aligned `trace.npz`, 0.25 ms `contact_intervals.npz`,
  `contact_summary.json`, per-run manifests and restart-safe batch state.
- `review_v1/DEVELOPMENT_SUMMARY.json` and `trajectory_geometry_broad_v1/`:
  independent read-only summary of all cases and sampled full-path geometry;
  `pose_consistency_v1/POSE_AUDIT.json`: endpoint CR12/cuff pose consistency.
- `REPRESENTATIVE_STATUS_CORRECTION.md`: preserves and explains one initial
  batch-status field extraction error. `AUDIT_REPORT.md`: independent review.

The local working tree still includes extensive pre-existing dirty/untracked
full-3D dependencies and is not clean-clone reproducible. Nothing was staged,
committed, pushed, reset, stashed, deleted or moved to another branch.
