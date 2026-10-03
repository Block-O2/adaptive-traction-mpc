# Cuff location geometry audit

Nominal L2=.40076m; sleeve half-length .040m, radius .058m; cuff-bar half-length .040m, radius .012m; end-effector adapter .140m, connector .082m. ROM/placement/clearance thresholds unchanged.

| rho | knee-to-cuff m | sleeve axial interval m | initial sleeve gap mm | prospective result |
|---|---|---|---|---|
| 0.60 | 0.2404560 | [0.200456, 0.280456] | 5.953957 | feasible necessary geometry |
| 0.72 | 0.2885472 | [0.2485472, 0.3285472] | 1.762533 | feasible necessary geometry |
| 0.85 | 0.3406460 | [0.300646, 0.380646] | -2.778176 | PHYSICAL_SETUP_OUT_OF_SCOPE |
| 0.77 | 0.3085852 | [0.2685852, 0.3485852] | 0.016106 | feasible necessary geometry |

rho .85 was rejected before any dynamic arm because full sleeve penetrates the table. Predeclared descending .01 ordered values select .77. Final [.60,.72,.77] frozen in contract with case hashes. Full sleeve remains on shank; centers in distal half, also full sleeve inside distal half at these exact synthetic dimensions. Tiny installation margins at .60/.77 are not robust manufacturing tolerances. Sleeve collision-disabled, so analytic whole-cylinder check was required. Effective knee-to-cuff distance calibration is observable; full L2/rho separately is not.

Raw prescribed commissioning waypoints do not themselves define the realized safe reference. Existing DEV-D feedback projects them; literal unsafe waypoint gaps are retained as characterization and actual commissioning is NOT_RUN.
