# Matched rigid/P1 120/120 exploratory A/B — frozen

User-authorized exploratory diagnostic only. Provenance checkpoint `0435070a46f23140d08c94e4dab1b9a01244e9c9` contains the completed 90/120 evidence and the rigid 40/80-versus-90/120 mechanism audit. The previous strict compliant numerical-qualification FAIL remains unchanged; this pair does not establish numerical qualification, clinical safety, or a formal capability envelope.

Exactly two fresh-process runs: rigid 120/120, then registered P1 120/120. No third run or other trajectory. Both use 0.25 ms and 20 physics substeps per unchanged 5 ms control tick, the same de23ea3 Fixed MPC stack, `suspended_high_rom`, nominal High-ROM Human/model lock, 140 mm adapter, seed 44104, registered quintic reference timing, allocator, robot, measurement boundary, Reference Manager, Safety Filter, BRAKE and physical-force contracts. Only interface differs.

P1 remains K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad. No tuning, preload, rest-frame, timing, completion tolerance, solver, gain, force-limit, estimator or controller change.

Registered trajectory point: [120,120] deg, outbound/return 17.42424242424242 s each, initial/final hold 1.0 s, target hold 1.5 s, total reference phase 38.34848484848484 s, maximum physical simulation duration 76.7 s. The formal endpoint/return tolerance stays 0.06896926724078867 deg.

Precision-only `SAFE_INCOMPLETE` never stops execution. A rigid controller/safety termination is preserved and may admit matched P1 only when evidence through termination is finite and there is no warning, nonfinite state, runaway deformation/oscillation, persistent artificial positive-energy growth, implementation/reference-frame error, or corrupt evidence. Original hard force/ROM/structural safety remains active. P1 is final.

If rigid enters `FILTER_INFEASIBLE`/BRAKE, postprocessing must audit the critical window against the existing 40/80 mechanism: decompose nominal allocator versus feedback wrench, compute the torque-preserving nullspace minimum achievable force, and compare return states with rigid 40/80 and 90/120. Energy remains an exploratory guardrail only.
