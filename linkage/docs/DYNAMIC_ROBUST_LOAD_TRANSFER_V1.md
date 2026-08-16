# Dynamic Robust Load Transfer V1

## Question and scope

This stage asks whether the registered quasistatic support/suspension overlap
can be traversed by a closed-loop dynamic hybrid architecture under the
current Human Model V2, engineering bed abstraction, `+/-200 N` component
box, and 10 degree task tube. It does not establish clinical safety, mattress
validity, patient-distribution robustness, or hardware feasibility.

The nominal plant, gravity, passive torque, endpoint force map, original V2
geometric path, calibrated hip height, bed plane, unilateral Kelvin-Voigt bed
law, nominal bed stiffness, tube definition, component bound, and registered
uncertainty cases are unchanged.

## Two separate mechanics signals

The supervisor never treats the quasistatic envelope as a dynamic proof.

`robust_static_margin` is

```text
200 - max_registered_case ||F_hold(q, case)||_inf.
```

It reuses the exact 30-case deterministic uncertainty set registered by the
quasistatic sensitivity work. The fixed 20 N entry value is an engineering
capability trigger, not a clinical reserve.

`predicted_dynamic_margin` uses the nominal controller model and current
candidate reference:

```text
qdd_cmd = qdd_ref - Kp(q-q_ref) - Kd(qdot-qdot_ref)
tau_req = M(q)qdd_cmd + h(q,qdot) + G(q) + tau_passive(q,qdot)
predicted_dynamic_margin = 200 - ||F_req||_inf,
A(q)F_req = tau_req.
```

The implementation also records the component-bounded minimum-residual force
and torque residual when the exact solution lies outside the box or the map
loses rank. This makes dynamic force infeasibility observable rather than
silently clipping it.

## Hybrid sequence

The only success sequence is:

```text
BED_SUPPORTED_MOTION
-> TRANSFER_READY
-> LOAD_TAKEOVER
-> LIFTOFF
-> SUSPENDED_MOTION
-> RECONTACT
-> LOAD_RETURN
-> BED_SUPPORTED_RETURN
-> TASK_COMPLETE
```

- `BED_SUPPORTED_MOTION` starts at the unchanged `[5,10] deg` posture and
  advances the original rehabilitation path with real bed contact. It does
  not require robot-only feasibility and performs no hidden preposition. The
  actuator force already present at `t=0` is explicitly balanced against the
  selected true plant at that same posture and bed geometry. This is an
  initialization condition only. R1 Safe Takeover now holds that known
  applied command until the nominal demand enters a shared capture band, then
  performs a constraint-aware handover before exposing the unchanged nominal
  tracking path.
- `TRANSFER_READY` requires the measured posture to remain inside the tube,
  real bed support, no soft-limit action, small static residual, feasible
  current dynamic prediction, continuous commanded force, and at least 20 N
  registered static reserve for a stable guard interval.
- A deterministic tube-local transfer target is selected from mechanics. No
  posture or progress value is hard coded. Eligible candidates are ordered by
  registered reserve, nominal hold dynamic reserve, zero-velocity bed load,
  total robot force, axial force, force-command change, soft-zone clearance,
  path deviation, and joint coordinates.
- `LOAD_TAKEOVER` continues governed flexion while a continuous path-following
  blend decays the entry posture offset relative to the moving original
  geometric path and gradually
  removes controller bed credit. The plant bed force is never scaled: it
  decreases only through the real unilateral contact geometry/dynamics. If a
  guard erodes while bed support remains, both motion and unloading pause;
  unloading time does not advance during recovery.
- `LIFTOFF` requires stable physical loss of bed contact plus positive static
  and dynamic margins, bounded dynamic residual, no force saturation, no
  significant soft-limit torque, and acceptable force rate.
- `SUSPENDED_MOTION` resumes jerk-limited flexible progress on the existing
  force-aware tube plan. Dynamic or robust erosion first slows/pauses progress;
  persistent infeasibility receives an explicit failure classification.
- `RECONTACT` can only be entered after real unilateral bed contact is stable
  on the return path. It cannot be synthesized by a state flag or controller
  bed-force scaling. `RECONTACT` and `LOAD_RETURN` hold that physically
  established contact pose while controller bed credit is gradually restored
  and progress remains paused. They do not blend back toward a nominal pose
  that could remove the real unilateral contact. If bed support is not
  established before robot-only reserve is lost, the case is
  `LOAD_RETURN_FAILED`.
- `BED_SUPPORTED_RETURN` resumes the original return to `[5,10] deg` using a
  continuous path-following decay of the contact-posture offset. This avoids a
  hard reference jump while the bed, not suspended single-contact force,
  supports the near-horizontal terminal posture.

Terminal failures are kept distinct:
`TRANSFER_REGION_NOT_REACHED`, `LOAD_TAKEOVER_FAILED`,
`DYNAMIC_MARGIN_VIOLATION`, `LIFTOFF_INFEASIBLE`,
`SUSPENDED_INFEASIBLE`, `RECONTACT_FAILED`, `LOAD_RETURN_FAILED`,
`FORCE_BOUND_VIOLATION`, `SOFT_LIMIT_VIOLATION`,
`SAFE_TAKEOVER_TIMEOUT`, and `ABORTED`. Results also record whether a failure
occurred in `TAKEOVER`, `TRACKING`, `TRANSFER`, or `RETURN`.

## Nominal controller and perturbed plant separation

Stage 1 uses the nominal Human V2 as both controller model and plant. Stage 2
is conditional on nominal `TASK_COMPLETE`. Its mild, moderate, and adverse
plants are the already registered deterministic combined cases, while the
controller, dynamic predictor, and robust supervisor continue to receive only
the nominal model. No case-specific retuning is performed. These cases are
engineering sensitivity cases, not samples from a patient distribution.
The perturbed-plant dynamic demand and residual are computed only as offline
rollout logs; they are not fed back to the controller or supervisor.

## Logged evidence

Each rollout records actual/nominal/governed joint trajectories, task progress,
hybrid state, local robot force and force rate, real bed force and contact
count, controller bed credit, registered robust static reserve and worst case,
nominal exact and bounded dynamic force, bounded residual, force-map
conditioning, tube/ROM status, soft-limit torque, saturation, recovery, and
mechanically triggered events.
R1 additionally records startup mode/reason, nominal desired and candidate
forces, applied force, aggregate/per-component scaling, force gap, measured
soft margins, and nominal one-step predicted margins.
Before a rollout starts, the runner also writes a flattened
`initial_admissibility.csv` and per-case `initial_admissibility.txt` containing
true/model soft-zone values, ROM margins, physical bed support, true/model
equilibrium forces, the first controller command, force-bound margins, and
true/model first-command accelerations. A failed admissibility report prevents
the rollout from starting; no safety check is deferred or suppressed.
On return, the suspended state periodically searches the current tube for a
real-bed-contact candidate with positive static and dynamic reserve. It pauses
progress and blends toward the lowest-contact-load eligible candidate; the
state still remains suspended until actual unilateral contact is stable.

The formal runner creates one synchronized equal-axis GIF and the following
panels for every executed case:

- `state_timeline.png`
- `tracking_and_tube.png`
- `robot_force_and_bounds.png`
- `safe_takeover_diagnostics.png`
- `static_vs_dynamic_margin.png`
- `bed_robot_load_share.png`
- `transfer_events.png`
- `dynamic_residual.png`

Artifacts are written to a timestamped directory under:

```text
linkage/results/local/dynamic_robust_load_transfer_v1/
```

## Tests and execution boundary

Thirty-two tests cover progress in bed-supported motion, true task-coordinate
pause semantics, the 20 N guard,
separation of static and dynamic margins, absence of bed-force scaling,
takeover recovery, stable liftoff guards, suspended pause/failure behavior,
physical recontact, contact-preserving load return, continuous return-path
rejoin, deterministic registered cases, hard force bounds, controller/plant
model separation, the unchanged initial posture, plant-consistent initial
equilibrium, five-step mismatch startup behavior, R1 takeover safety for all
registered cases, zero-boundary prediction, no runtime plant-oracle
dependency, bounded timeout, force bounds, and exact nominal-controller bypass
in `TRACKING`.

R2A adds a controller-model parameter boundary without changing the default
nominal path. Its seven tests cover nominal equivalence, exact oracle mapping,
fixed parameters, preserved R1 traversal/safety, and absence of oracle mapping
from runtime safety logic. The diagnostic contract and pending formal gate are
documented in
[DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ORACLE_MODEL_R2A.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ORACLE_MODEL_R2A.md).

The R1 design, exact old 0--30 ms force/state chain, non-formal startup smoke,
and reviewed user-run formal result are documented in
[DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md).

The retained first formal-run initialization diagnosis, exact trigger samples,
minimal fix, and corrected formal result are documented in
[DYNAMIC_ROBUST_LOAD_TRANSFER_V1_INITIALIZATION_DIAGNOSIS.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_INITIALIZATION_DIAGNOSIS.md).

The corrected user-run formal directory is `20260815_161905`. All 117 retained
tests passed and all four initial-admissibility reports passed. Nominal again
reached `TASK_COMPLETE` in `22.442 s`. Mild, moderate, and adverse entered the
joint-1 lower soft zone after `0.026`, `0.026`, and `0.030 s`, respectively,
after the unchanged nominal controller moved away from each perturbed plant's
initialized equilibrium. These are physical safety terminations after valid
initialization, not solver failures, but they occur before meaningful task
progress and therefore do not characterize the later transfer path. Exact
values and interpretation are retained in the linked diagnosis.

The reviewed R1 formal directory is `20260815_171801`. Nominal retained the
full sequence and reached `TASK_COMPLETE` in `22.512 s`. Mild, moderate, and
adverse completed Safe Takeover and entered `TRACKING` at `3.876`, `3.074`,
and `3.358 s`. They later terminated in the tracking phase at `4.400`, `3.792`,
and `3.904 s`; none had a takeover soft/ROM/component-force violation. This
separates the remaining mismatch failures from initialization and handover.
Full metrics are retained in the R1 report.

The reviewed R2A oracle-model directory is `20260815_174540`. With fixed
`theta_model=theta_true`, mild completes the full task in `22.510 s`.
Moderate and adverse extend phase-aligned tracking survival from
`0.718/0.546 s` to `4.068/3.490 s`, but still terminate at the q2 lower soft
boundary before transfer. Oracle-model and realized dynamic margins coincide
exactly but retain strongly negative global minima. This is a Case-B partial
improvement: model mismatch matters and accurate dynamics alone is insufficient.
At that R2A review point, no R2B or R3 implementation was included. See the R2A
report for the full comparison and metric-definition interpretation.

R2B subsequently adds a nominal-start, bounded seven-parameter Windowed-NLS
controller-model update without changing R1 or the safety manager. Its
offline replay gate and non-formal startup smoke are documented in
[DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING_R2B.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING_R2B.md).
The reviewed formal directory is `20260816_083505`: nominal retains completion,
mild materially approaches oracle behavior and reaches recontact, moderate
improves only partially, and adverse remains nominal because its natural-data
window is rank deficient. No R3 logic is included.

The R1 startup smoke command is:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_dynamic_robust_load_transfer_v1_startup_smoke"
```

The formal command is:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_dynamic_robust_load_transfer_v1"
```

Under the repository experiment policy this long scientific run was executed
by the user after the mechanical tests passed. Any rerun remains reserved for
user execution. A poor or failed result must be preserved and reported; it
must not trigger hidden tuning, threshold selection, force-bound expansion,
tube expansion, or model changes.
