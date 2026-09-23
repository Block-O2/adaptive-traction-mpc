# Phase 0 — Assumption and Scope Recovery Audit

Builder status: complete, awaiting independent Auditor gate.

Audit checkout: branch `codex/stage5-architecture-recovery`, starting HEAD
`4caea258ec1450f082bb7cb8097cc1441bdf589f`. The working tree contained
protected pre-existing Stage 4/5 changes and artifacts; this audit did not edit
them.

## Executive finding

The repository does not support a simple Stage-1-to-Stage-5 story in which one
unchanged unknown-setup estimator was gradually reduced. Stage 1 is a generic
Spring2D identification/MPC foundation, Stage 2 establishes Human V2 mechanics,
and Stage 3 introduces the coupled 3-D robot/Human plant. A causal Human cuff
geometry/state estimator first becomes explicit in the Stage 4 one-shot
adaptive-control history at commit `242a6b5`.

The exact scope discontinuity is nevertheless clear. Stage 4 estimated a
five-parameter control geometry from cuff pose history. Stage 5 commit
`e6ea54b` introduced a deterministic baseline whose `FixedStage5Estimator`
overwrites that estimator with the same fixed geometry record used to construct
the plant and disables geometry and dynamic updates. Commit `d8911c4` then
documented the geometry estimator as inappropriate for the loaded-interface
boundary and made the accepted fixed Stage-5 geometry authoritative while Human
dynamic identification remained shadow-only. Subsequent dynamic-personalization
work can change beta, but the current q/dq, Jacobian, generalized-effect, and
HWMPC-clearance paths still depend on fixed session geometry.

This is a scope mismatch with the immutable recovery contract. It is not a
direct code path from a MuJoCo truth object into action selection, but matched
simulation uses shared exact constants on both sides of the plant/controller
boundary. That is an oracle-equivalent fixed-nominal assumption under hidden
setup variation.

## Evidence-backed timeline

| Stage / commit | Evidence | Geometry/task-state status |
|---|---|---|
| Stage 1 | `stages/stage1/src/traction_mpc/estimation/` and `models/spring2d_dynamics.py` | Generic Spring2D state/parameter estimation; not evidence of a Human joint-center/link/cuff estimator. |
| Stage 2 | Human V2 MATLAB/Python mechanics and oracle runners under `stages/stage2_linkage/` | Human geometry is a simulation model input; oracle results validate the model, not unknown-session recovery. |
| Stage 3 | `traction_mpc_stage3.human`, coupled plant, cuff adapter and robot interface | Fixed Human V2 and registered robot/cuff model become the coupled simulation plant. Calibration provenance is explicit, but Human session geometry is not estimated here. |
| Stage 4 `242a6b5` | `estimator_v2.py:143-257,275-553` | `PlanarCuffGeometry` supplies q/dq, Jacobian, wrench mapping and cuff pose; `AccumulatedCuffGeometryEstimator` fits hip-plane translation, thigh length and a 2-D knee-to-cuff vector from accumulated pose data. |
| Stage 4 closeout | `docs/research/CURRENT_STATE.md` architecture/measurement sections | Controller boundary is robot state, measured cuff pose/twist and wrench; Human truth is evaluation-only. Geometry estimator is shared across formal arms, while beta is a control-effective model rather than anatomical truth. |
| Stage 5 `e6ea54b` | `baseline_replay.py:48-108` | `FixedStage5Estimator` installs `STAGE5_GEOMETRY.world_from_human`, nominal thigh length and nominal cuff distance, disables both estimator updates, and labels the path fixed/no-learning. |
| Stage 5 `d8911c4` | `HUMAN_ID_ARCHITECTURE_AUDIT.md:9-20,22-46` | Stage-4 geometry estimation is explicitly bypassed; fixed Stage-5 geometry and interface-aware reconstruction become authoritative; Human ID is shadow-only. |
| Current working implementation | `goal_mpc_smoke.py:430-466,500-560,589-612,1004-1050`; `human_waypoint_scheduler.py:41-63,288-298,451-504` | Default plant, estimator, observer, controller model, and clearance checks still share fixed Stage-5 geometry/Human constants. Optional beta callbacks do not recover geometry. |

## Current controller data flow

```text
MuJoCo plant truth (evaluation world)
  |  sampled robot q/dq, robot-side attachment pose/twist, cuff F/T only
  v
CausalMeasurementLayer
  v
InterfaceAwareHumanStateObserver
  |  inverts a fixed provisional Kelvin-Voigt interface model
  v
estimated Human-side cuff pose/twist
  v
FixedStage5Estimator.geometry = fixed T_WH + fixed L1 + fixed knee-to-cuff sc
  |----------------------|--------------------------|
  v                      v                          v
estimated q/dq           J(q; L1,sc)                J^T wrench
  |                      |                          |
  +-----------> task state / acceleration / Human dynamic ID
  +-----------> Goal MPC / HWMPC state
                         +-----------> allocation and prediction

fixed STAGE5_HUMAN L2 + fixed T_WH
  +-----------> HWMPC shank/table clearance and waypoint feasibility

MuJoCo Human q/dq/qdd and plant-interface state
  +-----------> separately named evaluation traces/diagnostics
```

The measurement object itself omits Human truth, which is a valid boundary.
The problem is downstream provenance: the observer reconstructs Human-side
cuff state with fixed unmeasured interface parameters, then fixed registered
Human geometry converts it to control state and mappings.

## Complete truth/source matrix

`Current final class` describes the source if the present implementation were
deployed unchanged. `Required recovery class` is the minimum acceptable source
under the immutable contract.

| Quantity | Current source | Historical source | Deployment available? | Session-specific? | Current final class | Main consumers / consequence if wrong | Required recovery class |
|---|---|---|---:|---:|---|---|---|
| CR12 joint q/dq | robot measurement boundary | Stage 3/4 robot interface | yes, subject to hardware contract | no for structure; state varies | MEASURED | FK/Jacobian, low-level execution | MEASURED |
| Robot base `T_WB` | provisional config, `stage5_geometry_mechanics_v1.json:12-15` | registered surrogate placement | commissioning-calibratable, not currently measured | yes | FIXED_NOMINAL | plant placement, IK, collision geometry | CALIBRATED |
| Tool/cuff `T_EC` | provisional config lines 20-23 | Stage 3 identity / High-ROM 140 mm surrogate | commissioning-calibratable, not currently measured | setup/tool-specific | FIXED_NOMINAL | cuff pose, wrench reference, IK | CALIBRATED |
| Human base/hip `T_WH` | provisional config lines 16-19; loaded as a global in `geometry.py:99-111` | Stage 4 hip-plane part was estimated | no direct current measurement | yes | FIXED_NOMINAL | q, cuff pose, plant, waypoint clearance | CALIBRATED or ONLINE_ESTIMATED |
| Human motion-plane normal and in-plane sagittal zero/sign | fixed identity `T_WH` | Stage 4 estimated joint axis from cuff rotation but anchored the in-plane basis with an initial-q prior | the normal is motion-observable; absolute sagittal zero/sign needs calibration, a known pose, or separately proven dynamics | yes | FIXED_NOMINAL | absolute q1/dq convention, Jacobian basis, moment projection | CALIBRATED or ONLINE_ESTIMATED |
| Thigh length `L1` | `STAGE5_HUMAN` anthropometric nominal | Stage 4 estimator fitted it | not directly measured | yes | FIXED_NOMINAL | q, Jacobian, dynamics/clearance | CALIBRATED or ONLINE_ESTIMATED |
| Full shank length `L2` | `0.233*height` inherited by `STAGE5_HUMAN` | fixed Human V2; not output by Stage-4 geometry estimator | not from allowed cuff observations alone | yes | FIXED_NOMINAL | ankle/table clearance and Human dynamics interpretation | CALIBRATED, separately MEASURED, or a justified uncertainty-aware STRUCTURAL_PRIOR |
| Shank/capsule radius | fixed inherited geometry/config | fixed Human V2 collision surrogate | commissioning-calibratable; not currently measured | yes | FIXED_NOMINAL | hard table-clearance margin | CALIBRATED/MEASURED or justified conservative STRUCTURAL_PRIOR |
| Cuff fraction `f` | fixed 0.72, `human.py:12-30` | Stage 3 fixed 0.90; Stage 4 estimated only knee-to-cuff vector | not separately from `L2` using cuff kinematics | yes | FIXED_NOMINAL | cuff distance and attachment interpretation | CALIBRATED/MEASURED, or jointly identifiable with added information |
| Knee-to-cuff vector / distance `sc` | fixed `f*L2=0.2885472 m` | Stage 4 online-estimated 2-D cuff vector | observable from informative cuff pose motion after interface correction | yes | FIXED_NOMINAL | q/dq, cuff Jacobian, generalized effect, allocator | ONLINE_ESTIMATED or CALIBRATED |
| Cuff-to-shank angular offset | fixed zero in current geometry | Stage 4 cuff-vector angle was estimable | observable with informative pose motion | yes | FIXED_NOMINAL | q2, Jacobian orientation, moment mapping | ONLINE_ESTIMATED or CALIBRATED |
| Initial Human q/dq | reset at task start target; estimator constructed with the same q prior, `goal_mpc_smoke.py:438-452` | Stage 4 required an initial q prior | not directly measured in current boundary | yes | FIXED_NOMINAL-derived | estimator frame initialization, task validity, all control | ONLINE_ESTIMATED or CALIBRATED |
| Human q/dq over time | fixed-geometry `PlanarCuffGeometry.estimate_state` after interface inversion | Stage 4 used estimated geometry | conditionally observable | yes | FIXED_NOMINAL-derived | task state, dynamics, MPC, completion | ONLINE_ESTIMATED |
| Interface stiffness/damping/rest state | provisional nominal controller config, `controller_interface.py:36-127` | Stage 3/4 engineering model | not currently hardware calibrated | yes | FIXED_NOMINAL | Human-side cuff pose/twist inversion; error biases geometry and q/dq | CALIBRATED or ONLINE_ESTIMATED |
| Interface effective mass/inertia | provisional nominal controller config | Stage-5 engineering calculation from the surrogate model | not currently hardware calibrated | yes | FIXED_NOMINAL | nominal interface prediction and inversion dynamics | CALIBRATED or ONLINE_ESTIMATED |
| Cuff F/T | measurement boundary | Stage 4 measured/reconstructed wrench | yes, after sensor calibration | state varies | MEASURED | generalized effect, interface observer, monitoring | MEASURED with CALIBRATED frame/bias |
| Human translational Jacobian | fixed `L1,sc,plane`, `estimator_v2.py:190-201` | Stage 4 estimated-geometry Jacobian | computed | yes | FIXED_NOMINAL-derived | wrench mapping, allocator, dq, prediction | ONLINE_ESTIMATED-derived |
| Wrench-to-generalized effect | fixed Jacobian and joint axis, `estimator_v2.py:223-233` | Stage 4 estimated geometry | computed | yes | FIXED_NOMINAL-derived | dynamic ID, model update, support action | ONLINE_ESTIMATED-derived |
| Effective Human dynamics beta | nominal beta by default; some later experimental callbacks can publish updates | Stage 4 online estimated and trusted beta; early Stage 5 shadow only | observable only under adequate excitation/model validity | yes | FIXED_NOMINAL by default; ONLINE_ESTIMATED in opt-in experiments | HWMPC/Goal-MPC prediction, hold support | ONLINE_ESTIMATED with explicit invalid path |
| Passive rest angles/stiffness/damping | nominal values embedded in beta/ROM model; opt-in beta updates can change control-effective combinations | Stage 4 beta estimator | only control-effective combinations may be observable | yes | FIXED_NOMINAL by default | inverse dynamics, passive torque and support action | ONLINE_ESTIMATED control-effective representation or justified STRUCTURAL_PRIOR |
| Soft-limit margin/shape/boundary torque | fixed Human V2 engineering model | fixed Stage 2/3/4 contract | registered engineering prior, not patient calibrated | partly session-specific in reality | STRUCTURAL_PRIOR in simulation, unvalidated for deployment | contamination rejection, inverse dynamics near ROM boundary | STRUCTURAL_PRIOR only if explicitly retained; otherwise CALIBRATED |
| ROM/topology/joint order | Human V2 contract | Human V2 structural model | registered prior | not a per-session estimate in this campaign | STRUCTURAL_PRIOR | constraints and state semantics | STRUCTURAL_PRIOR |
| Bed/table plane and height | fixed world/table frame and Human hip height | Stage 2/3 contact scenario | commissioning-calibratable; not currently demonstrated | setup-specific | FIXED_NOMINAL | shank/table clearance and plant contact | CALIBRATED |
| Human/table clearance geometry | global `STAGE5_GEOMETRY` hip height and `STAGE5_HUMAN` L1/L2, `human_waypoint_scheduler.py:41-63` | not supplied by Stage-4 cuff geometry object | not currently measured | yes | FIXED_NOMINAL | hard waypoint feasibility | CALIBRATED/MEASURED or conservative uncertainty-aware STRUCTURAL_PRIOR |
| MuJoCo Human q/dq/qdd | plant observation / `plant.data` | evaluation truth | simulation-only | yes | SIMULATION_TRUTH, evaluation namespace | trace scoring and diagnostics at `goal_mpc_smoke.py:1051-1053,1480-1499` | HIDDEN_ORACLE / evaluation only |

No control-critical Human quantity remains unclassified in this audit. Several
are classified as unacceptable current `FIXED_NOMINAL` dependencies; Phase 0
classification is not a claim that the implementation already complies.

## Exact bypass and hidden-nominal points

1. `FixedStage5Estimator` inherits the Stage-4 estimator and then overwrites its
   geometry/prior/last-valid state with exact Stage-5 globals and disables
   updates (`baseline_replay.py:48-108`).
2. The default goal runtime constructs the plant with `STAGE5_HUMAN`, resets it
   at the task start target, and constructs the fixed estimator with that same
   target (`goal_mpc_smoke.py:430-454`).
3. Human-side cuff pose is recovered by inverting an immutable, explicitly
   provisional and not hardware-calibrated interface parameter record
   (`controller_interface.py:53-127,145-220`).
4. The observer calls `human_model.geometry.estimate_state`; the same geometry
   supplies Jacobians, generalized wrench effects, allocation and prediction.
5. The HWMPC scheduler bypasses model provenance for bed clearance by importing
   global `STAGE5_GEOMETRY` and defaulting to global `STAGE5_HUMAN`.
6. Stage-5 Human ID initially declared itself `shadow_only` and excluded the
   geometry estimator; later beta-authority work does not repair geometry.
7. Tests that assert no `truth` attribute at the controller boundary do not
   detect plant/controller equality through shared constants. Mismatch tests
   must vary geometry independently and require recovery or fail-loud behavior.

The repair adds a campaign-scoped `QuantityProvenance` guard that rejects
session-specific `FIXED_NOMINAL`, `SIMULATION_TRUTH`, or `HIDDEN_ORACLE`
sources. It is deliberately not wired into the existing controller because the
campaign is at a candidate identifiability hard stop. Focused tests demonstrate
both exact geometry gauges and the fail-loud provenance rule; they do not claim
the current production path has been repaired.

## Recovered architecture versus current implementation

The historical Stage-4 estimator is useful evidence, not a drop-in recovery:

- It estimates hip-plane translation, `L1`, and a knee-to-cuff vector and uses
  them consistently for q/dq, Jacobian and generalized effect.
- Its frame initialization depends on an initial q prior and its measurement
  assumes the measured attachment pose is Human-side cuff pose.
- Stage 5 added a finite loaded interface, so recovery must occur after a
  calibrated/estimated interface transform or jointly with it.
- It does not output full `L2`; current HWMPC clearance consumes full `L2`.

Therefore “restore Stage-4 estimator” alone cannot satisfy the Master Contract.

## Phase-1 identifiability issue exposed by Phase 0

For the planar model,

`p_c = p_hip + L1 e(q1) + sc e(q1-q2)`, where `sc = f L2`.

Cuff orientation supplies the shank angle. The cuff translational Jacobian and
the wrench-to-generalized-effect map also contain `L1` and `sc`, not `L2` and
`f` separately. For every legal alternative `L2'`, choosing
`f' = f L2 / L2'` produces identical cuff pose/twist, Jacobian and generalized
effect over every trajectory. The current control-effective beta model is an
independent base-parameter vector and does not impose an anatomical inverse map
that separates this kinematic equivalence.

The preregistered analytical audit in
`configs/architecture_recovery_v1/identifiability_audit_v1.json` constructs two
legal pairs:

- `(L2,f) = (0.40076 m, 0.72)`;
- `(L2',f') = (0.46 m, 0.6272765217)`.

Both give `sc=0.2885472 m`. Across five postures, cuff-pose, cuff-Jacobian and
generalized-effect residuals are exactly zero. The stacked observation
sensitivity to `[L2,f]` has rank 1 with singular values approximately
`[1.84256, 4.38e-17]`, while the ankle positions differ by 59.24 mm. The
current HWMPC hard clearance calculation uses ankle geometry and therefore
needs information not present in the allowed observation equivalence class.

This is a candidate hard identifiability stop. The independent Auditor must
confirm whether the allowed `STRUCTURAL_PRIOR` can legitimately supply a
bounded uncertainty-aware clearance representation without silently fixing
nominal anatomy. If not, the minimum resolution is one of:

- session measurement/calibration of full shank length or the ankle/joint
  center, plus cuff location;
- an additional observed anatomical landmark (for example registered ankle
  pose) sufficient to separate `L2` and `f`;
- an explicitly human-approved structural prior/uncertainty set and a robust
  HWMPC clearance consumer that remains valid for every member.

Changing or removing the hard clearance consumer merely to avoid this unknown
would be a contract change, not estimator recovery.

There is a second exact cuff-kinematic gauge for absolute `q1`. Rotate the
Human in-plane basis by any angle `gamma`, set `q1'=q1-gamma`, retain `q2`, and
rotate the coordinate representation of all planar geometry with the basis.
World cuff pose, twist and Jacobian remain unchanged. The historical estimator
fixes this gauge using `initial_q_prior_rad` when it constructs the plane basis
and origin (`estimator_v2.py:278-305,330-361`); the Stage-4 cold-start and
current Stage-5 runtime pass the same reference/reset pose as that prior. A
17-degree numerical gauge check is now included in the audit result. Gravity
and joint dynamics might break this gauge under an explicitly constrained
anatomical/dynamic model, but the existing geometry estimator does not perform
that joint inference and the control-effective beta model can confound the
interpretation. Claiming recovery would therefore require either a calibrated
Human sagittal zero/known-q pose or a separately preregistered joint
identifiability study.

## Phase 0 gate checklist

- Truth/source matrix: complete; no unclassified control-critical Human item.
- Current q/dq reconstruction: traced from measurement through interface
  inversion and fixed geometry.
- Jacobian/generalized effect: traced to the same fixed geometry object.
- Stage 1–5 timeline and bypass points: evidence-backed, with the important
  correction that the Human geometry estimator appears in Stage 4, not Stage 1.
- Current truth/fixed-nominal dependencies: enumerated.
- Independent Auditor confirmation: first review rejected the audit for the
  omitted q1 gauge and source rows; repair cycle 1 adds both, with final review
  pending.
- Truth-firewall audit guard: added and tested in the campaign namespace;
  production integration is intentionally blocked with the architecture.

No controller, model, scientific parameter, threshold, or historical result was
changed during Phase 0.
