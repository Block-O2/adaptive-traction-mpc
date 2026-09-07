# Progressive 0.25 ms exploratory A/B — frozen before execution

The user explicitly authorizes a diagnostic override of the prior failed bench qualification. No numerical, capability, clinical or safety qualification is implied.

Baseline de23ea3, worktree HEAD 99169491ea1336d6af74e3b63318afba18c1e881. Exact frozen suspended_high_rom stack, nominal High-ROM Human, frozen population prior/geometry, 140 mm adapter, seed 44104, original controller/Reference Manager/Safety Filter/BRAKE and force contracts.

P1 only: K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad. Lowest registered small-motion stiffness; selected before any new task data. Fixed zero rest, registered cubic law and implementation exactly. No P2 fallback.

Both arms: dt=0.00025 s, original implicitfast/Newton settings, 20 physics integrations per unchanged 0.005 s low-level tick. Original sensor-realism function bytecode is reused with local CONTROL_SUBSTEPS binding. Only the compliant arm uses its already-registered robot-port sensor adapter. Sensor sampling, noise, gains and control cadence remain unchanged.

Order (fresh process/state for each): 40/40 rigid, 40/40 P1, 40/80 rigid, 40/80 P1, 90/120 rigid, 90/120 P1. Each point copies its exact baseline normalized trajectory timing and maximum duration. At most six runs; no repeated run or replay.

Stop campaign on MuJoCo warning/nonfinite state, mechanics inconsistency, ROM/robot-limit/structural contact event, global translation >3 mm or global rotation >1 deg. No centimeter-scale guard relaxation. Negative damping <−1e-10 W or U<−1e-12 J also stops. Positive energy residual >max(1e-10 J, 0.005*S) stops, where R=U-U0+integral(P_R+P_H+D)dt and S=max(running U, cumulative damping, running absolute net work). This reuses the registered positive-energy budget. Negative residual is retained as a numerical diagnostic; the known failed absolute 1% equivalence gate is not reinterpreted as passed. No post-result changes.

The observation-only experiment guard feeds the existing stop/break path after the unchanged force monitor. Raw generic termination is retained; diagnostic reason is reported separately. This guard does not adjust an action or apply a recovery controller.

If compliant 40/40 loses rigid COMPLETE or has any unsafe termination, stop before harder points. Ordinary 40/80 or 90/120 task incompletion without these stop conditions is a valid diagnostic observation. No extra recovery/retuning/trajectory is authorized.

Report all six scheduled rows, including NOT_RUN after an early stop. Per executed row preserve raw trace/summary, physics-rate mechanics, commands/modes, model-lock hashes, command/config, runtime and exact stop reason. Report task, prefix/full tracking RMSE, endpoint/return coverage, command/physical force RMS/peak/rate, transient classification, moments, global deformation, BRAKE/NO_SAFE_ACTION, acceleration/jerk, energy/damping. Correct inherited summary derivative assumptions only in postprocessing using actual dt. An open or confirmation-required force event has no extra replay permission and remains unresolved under the unchanged contract.

Only read-only preflight/reset checks and synthetic unit tests precede execution. No unregistered rollout. All evidence stays exploratory and uncommitted. The machine-readable JSON records exact parameters, thresholds, schedules, source and historical evidence SHA256.
