# DEV-D case provenance and inclusion

DEV-D reuses the already versioned rigid-table `assembly_v2` mapping without
changing its 24 source setup/task keys, hidden dynamics, body dimensions, cuff
location or task coordinates. The authoritative per-case old-to-new geometry
and SHA-256 mapping is
`results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v2/OLD_TO_NEW_CASE_MAPPING.json`.
The original old-24 failed qualification is historical and remains in its old
denominator. DEV-D results are consumed DEVELOPMENT comparisons on the
revised assemblies; they are not paired identical-state causal branches or
fresh held-out evidence.

Twenty-three v2 cases pass the registered initial/endpoint geometry screen and
are eligible for physical DEV-D replay. The remaining
`balanced_ordinary_r02` is **retained as invalid**, not replaced. Its v2
initial sleeve signed distance is −2.513125 mm. The minimum vertical lift
needed for the predeclared +0.1 mm sleeve installation gap would require
total hidden hip shift +7.178067 mm, outside the registered +6 mm upper legal
placement. The table is an infinite collision plane; an x/y translation
cannot change this vertical sleeve–plane gap under the current fixed sagittal
setup. Static reset IK exists, so this is not merely an IK-search failure.
It is a generated setup incompatible with the current registered legal
placement range and initial cuff/tool envelope. Any future generator must
condition on that structural screen *before* admission; DEV-D does not alter
the old set or silently extend placement bounds.

The previously v1-invalid `balanced_near_upper_current_rom_r02` has a
separate v2 geometry-only installation correction: hip shift +3.650576 mm
gives +0.1 mm initial sleeve gap. DEV-D does execute this case. Its subsequent
actual sleeve penetration is a dynamic/initial-support result and must not be
retroactively used to move its hip farther upward.

For every physically run case, `dev_d_run_manifest.json` records the exact
case file/hash, assembly screen, controller flags, run command, and runner
outcome. `batch_status.json` records every selected key, including failures.
The independent old assembly mapping and old physical outcomes are not
overwritten.
