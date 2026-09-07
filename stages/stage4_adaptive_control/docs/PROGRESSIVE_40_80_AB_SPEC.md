# Matched rigid/P1 40/80 exploratory A/B — frozen

New evidence branch; all prior strict numerical FAIL and exploratory 40/40 results remain unchanged. Evidence is diagnostic only, not numerical qualification, clinical safety evidence or a new capability classification.

Exactly two fresh-process runs: rigid 40/80, then registered P1 40/80. No 90/120. Both use 0.25 ms, 20 physics substeps per unchanged 5 ms low-level tick, exact de23ea3 Fixed MPC contract, suspended_high_rom, nominal High-ROM Human/model lock, 140 mm adapter, seed 44104, quintic reference/timing, allocator, robot, measurement behavior, Reference Manager, Safety Filter, BRAKE and force contracts. Only interface differs.

P1 remains K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad. No tuning, preload, rest-frame or timing change.

The relaxed-energy watchdog is copied exactly from PROGRESSIVE_RELAXED_AB_SPEC. Energy residual is logged, not an immediate stop for small relative startup residual. Four consecutive 50 ms windows are required for the frozen persistent-growth/amplitude criteria. Gross deformation remains 10 mm/10 deg; 3 mm/1 deg are engineering targets reported separately. Original ROM, structural and physical-safety stops remain active.

A rigid controller-boundary termination is saved and still admits the matched P1 run if its data are finite and complete up to the termination, because this experiment explicitly asks whether P1 changes BRAKE/feasibility behavior. A genuine nonfinite/corrupt implementation outcome blocks the pair. P1 is always the final run.

Registered formal COMPLETE/SAFE_INCOMPLETE retains the 0.06896926724078867 deg endpoint/return rule. Precision-only failure is not a stop. If full timing coverage is observed, report `full reference executed; precision criterion not met`. No settling time or new success threshold.

Outbound progress = clip((maximum reference phase - 1 s)/registered leg,0,1); return progress = clip((maximum reference phase - (2.5 s+leg))/leg,0,1). Target and end-return states use the first physics sample at/after the exact registered phase boundary, or are unavailable. This is descriptive progress only.

Detailed supervisor records include mode, decision status, feasible candidate count, braking rate, termination and safety-filter status. Offline truth/proxy comparison uses saved `estimated_human_q_deg` versus `human_q_deg_god_view`; truth is never supplied to the controller.

Postprocessing aligns q_ref/q_proxy/q_true, deformation, cuff acceleration, physical/command force and mode. Peak timing alignment is descriptive only; no causality claim. All raw/full or prefix data, process IDs, exact initial state, configuration and model-lock evidence are preserved. Everything remains uncommitted.
