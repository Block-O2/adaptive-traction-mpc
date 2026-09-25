# Restart state

Phase: DEVELOPMENT_REPLICATION_COMPLETE; terminal classification `ASSEMBLY_REPAIR_PARTIAL`.

Branch: `codex/stage5-architecture-recovery`.
Start HEAD: `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`.
Start `git status --short`: 237 entries (unrelated and earlier full-3D local
dependencies preserved; use initial and final manifests for complete lists).

Completed: original 24 cases mapped without overwriting historical cases.
The mapping reports 11 previously negative fixed proximal gaps; 22 revised
assemblies pass initial/static/endpoint checks. Two *unchanged* old cases,
`balanced_near_upper_current_rom_r02` and `balanced_ordinary_r02`, reveal
disabled-collision sleeve–table signed distances of −1.773 and −2.513 mm and
are not executed under this version.  The old strongest −4.819 mm case has a
versioned +4.819 mm counterpart. In 0.1 s actual unactuated MuJoCo stepping,
old strongest thigh peak was 33,353.295 N while repaired strongest, unchanged
legal comparison, and +0.1 mm nominal reference had 0 thigh contact/force.

Representative full unchanged-controller runs (real CR12–cuff–Human, timing
replay, DEV-A on, DEV-C off): `balanced_middle_r01` COMPLETE;
`balanced_near_upper_current_rom_r01` ABORTED TASK_VELOCITY_LIMIT;
`balanced_ordinary_r01` ABORTED NO_FEASIBLE_WAYPOINT;
`nominal_reference_rigid_table_v1` COMPLETE. All four had 0 N thigh–table
contact peak. These are development comparisons only.

Completed v1 broad development replay: 22/22 commissioning, recovery and
task entries; 5 full task completions, 17 aborts (8 stale-plan, 5 waypoint
geometry, 3 velocity, 1 clearance). All 22 native 0.25 ms contact traces
have zero thigh–table force. The original 33.35 kN fixed-overlap diagnostic
remains preserved separately.

Completed v2 geometry-only extension: one initially sleeve-invalid case was
raised the minimum +1.873398 mm within the old +6 mm bound, then freshly
initialized and physically run. It commissioned but aborted at first active
recovery decision due to −0.931382 mm estimated-origin shank geometry. It
did not enter task; thigh contact remained zero over 28,080 physical
intervals, while a disabled-collision sleeve gap later reached −3.132480 mm.
The other case needs +7.178067 mm by this vertical rule and remains invalid.
Across v1 broad22 plus v2 supplement1: 23 commissioned, 22 task entries,
5 complete, 18 aborted; one original case unexecuted. These are consumed
DEVELOPMENT cases, not fresh qualification or one homogeneous frozen batch.

Independent Auditor reviewed source and saved data, independently recomputed
contact intervals, mapping hashes, static poses and sampled v2 sleeve path;
it did not run time-stepped simulation or tests. `AUDIT_REPORT.md` records
its disposition and limits. `COMMANDS.md` and `FINAL_REPORT.md` contain exact
reproduction and interpretation. No controller or historical asset changed.

Next single control-development objective: a rigid-table-feasible,
feedback-observed commissioning path with estimator/task controller/limits
held fixed. Do not proceed to fresh qualification or controller redesign in
this stage. No batch is running; no completed artifact should be overwritten.
