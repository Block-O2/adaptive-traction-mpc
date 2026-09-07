# Matched rigid/P1 90/120 exploratory A/B — frozen

User-authorized exploratory diagnostic only. Checkpoint `5e3800ae6570c45b125e74ea678cdf2b72f48d69` contains the preserved 40/40 and 40/80 evidence. The previous strict compliant numerical-qualification FAIL remains unchanged; this experiment does not establish numerical qualification, clinical safety, or a formal capability envelope.

Exactly two fresh-process runs: rigid 90/120, then registered P1 90/120. No 120/120 or other trajectory. Both use 0.25 ms and 20 physics substeps per unchanged 5 ms control tick, the same de23ea3 Fixed MPC stack, `suspended_high_rom`, nominal High-ROM Human/model lock, 140 mm adapter, seed 44104, registered quintic reference timing, allocator, robot, measurement boundary, Reference Manager, Safety Filter, BRAKE and physical-force contracts. Only interface differs.

P1 remains K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad. No tuning, preload, rest-frame, timing, completion tolerance, solver, gain, force-limit, estimator or controller change.

Registered trajectory point: [90,120] deg, outbound/return 12.878787878787875 s each, initial/final hold 1.0 s, target hold 1.5 s, total reference phase 29.25757575757575 s, maximum physical simulation duration 58.52 s. The formal endpoint/return tolerance stays 0.06896926724078867 deg.

Precision-only `SAFE_INCOMPLETE` never stops execution. A rigid controller/safety termination is preserved and may admit matched P1 only when evidence through termination is finite and there is no warning, nonfinite state, runaway deformation/oscillation, persistent artificial positive-energy growth, implementation/reference-frame error, or corrupt evidence. Original hard force/ROM/structural safety remains active. P1 is final.

Report formal classification separately from outbound/return phase coverage and physical target/return progress. Energy residual is an exploratory diagnostic guardrail using the already frozen four-window policy; no threshold is changed after results. Stop after the two runs.
