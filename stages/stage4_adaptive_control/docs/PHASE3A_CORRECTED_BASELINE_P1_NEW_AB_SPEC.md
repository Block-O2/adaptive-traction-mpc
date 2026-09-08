# Phase-3A corrected baseline: Rigid NEW vs P1 NEW

This is a user-authorized, preregistered exploratory comparison. Both arms use the separated low-latency robot joint/Jacobian cuff-center translational velocity feedback path. The scientific variable within each matched pair is only `rigid interface` versus registered `P1 progressive interface`.

The completed Rigid NEW 40/80 result is reused byte-for-byte from provenance checkpoint `0382d3a`; it is not rerun. The five fresh-process runs, in fixed order, are:

1. 40/80 P1 NEW
2. 90/120 Rigid NEW
3. 90/120 P1 NEW
4. 120/120 Rigid NEW
5. 120/120 P1 NEW

No 40/40, additional ROM point, replay, tuning, or threshold change is admitted. One invocation can execute only one new case.

Frozen across the study: 140 Ns/m translational gain, Human MPC and estimator, Reference Manager, Safety Filter, BRAKE, 200 N engineering target and transient policy, P1 parameters, 0.25 ms physics timestep, 200 Hz control update and 5 ms command ZOH, solver/integrator, seed 44104, trajectories and timing, Human/robot models, 140 mm adapter, geometry, and `freeze_control_geometry=True`. Rotational velocity feedback remains on its existing path.

The retained 0.06896926724078867 degree tolerance determines the formal classification. The report also records reference completion, conservative per-joint physical outbound/return progress, endpoint error, and return error; no additional practical PASS threshold is introduced.

Energy remains an exploratory guardrail. The previous strict P1 numerical-qualification FAIL is preserved and is not relabeled by this study. Results are exploratory simulation evidence, not clinical safety evidence or an authoritative capability boundary.

Repository policy reserves full scientific trajectories for manual user execution. Codex may freeze the contract and run implementation-level tests only.
