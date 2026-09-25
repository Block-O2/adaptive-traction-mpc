# Geometry-only envelope extension v2

This is a supplementary DEVELOPMENT assembly rule, not a revision of the
historical cases or the v1 22-case controller batch. It was defined after the
v1 screen found two initially intersecting, collision-disabled sleeves. The
rule uses only pre-run static geometry. It reads no controller outcomes.

For an otherwise legal v1 case with initial sleeve–table signed distance below
the 0.1 mm installation clearance, raise its hip and rebuild the entire
CR12–cuff–Human assembly by exactly the deficit to 0.1 mm, **only if** the
result remains within the original +6 mm hip installation ceiling. Leave all
other cases byte-identical. This is not a controller-side correction or a
permission to move the hip in response to task failure.

`balanced_near_upper_current_rom_r02` needed +1.873398 mm on top of its
old +1.777177 mm placement; the resulting +3.650576 mm placement gives
0.1 mm static initial sleeve clearance and passes the unchanged initial/task
endpoint screen. `balanced_ordinary_r02` would require +7.178067 mm total,
beyond the +6 mm registered installation range, and remains invalid. Thus v2
maps all 24 historical cases, admits 23 initial/task-endpoint assemblies, and
does not force the remaining invalid case into execution. The 22 v1-valid
case JSON files are unchanged in v2.

The newly admitted case was rerun from fresh physical initialization with the
**unchanged** controller. It completed commissioning but the first active
recovery decision rejected all five candidate segments: the estimated origin
had existing shank–table geometry of −0.931382 mm. It did not enter task. The
0.25 ms physical-contact trace contains zero thigh–table force and a 129.565 N
peak shank–table normal reaction. A separate 5 ms sampled-path geometry check
found a disabled-collision sleeve–table distance of −3.132 mm during motion.
Static initial clearance therefore does **not** establish full-trajectory
envelope validity. No further lift was selected from this outcome; that would
be outcome-driven assembly tuning. The result remains a failed development
replication and keeps the final assembly status partial.

Artifacts: `assembly_v2/OLD_TO_NEW_CASE_MAPPING.json`,
`assembly_v2/ASSEMBLY_SUMMARY.json`,
`supplemental_v2/balanced_near_upper_current_rom_r02/`, and
`trajectory_geometry_supplemental_v2.json` under the versioned result root.
