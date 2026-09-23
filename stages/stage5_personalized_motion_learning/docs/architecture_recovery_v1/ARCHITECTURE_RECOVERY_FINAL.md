BLOCKED_IDENTIFIABILITY

# Stage 5 Architecture Recovery V1 — Final Report

## 1. Executive interpretation

The campaign stopped correctly before estimator implementation or hidden-setup
formal control experiments. The current Stage-5 controller does not recover an
unknown Human setup: plant and controller share fixed session geometry, and the
controller reconstructs Human state through a provisional fixed interface
model. More importantly, the allowed cuff pose/twist and F/T observations do
not uniquely determine all geometry required by the current HWMPC hard
clearance calculation.

Two different legal full-shank-length/cuff-fraction pairs produce exactly the
same cuff pose, cuff Jacobian and generalized wrench effect for every motion,
but put the ankle 59.24 mm apart. Because HWMPC uses full shank/ankle geometry
for table clearance, advancing would require a new measurement/calibration or
an explicitly approved bounded anatomical prior. Substituting the existing
exact nominal anthropometric ratio would violate the contract.

## 2. Original architecture requirement

The recovered objective is:

`deployment observations -> session geometry/task-state estimate -> effective Human dynamic personalization -> state-feedback Human-waypoint MPC`.

Session-specific base placement, Human frame, link/control geometry, cuff
attachment, initial q/dq, Jacobians and wrench mappings may not terminate at
`FIXED_NOMINAL`, `SIMULATION_TRUTH`, or `HIDDEN_ORACLE`. Value learning and RL
were outside this campaign.

## 3. Exact Stage-1-to-Stage-5 scope drift

- Stage 1 is a generic Spring2D estimator/MPC foundation, not a Human geometry
  estimator.
- Stages 2–3 establish fixed Human V2 mechanics and the coupled 3-D robot/Human
  simulation.
- Stage 4 commit `242a6b5` introduces the causal accumulated cuff geometry
  estimator used for q/dq, Jacobian and generalized wrench mapping.
- Stage 5 commit `e6ea54b` introduces `FixedStage5Estimator`, overwrites that
  estimator with the same registered geometry used by the plant, and disables
  geometry/dynamic updates.
- Commit `d8911c4` explicitly classifies Stage-4 geometry estimation as
  inappropriate for the loaded interface, makes fixed Stage-5 geometry
  authoritative, and keeps Human ID shadow-only.
- Later beta-personalization work can change control-effective dynamics but
  does not recover session geometry. Current HWMPC clearance still imports
  global `STAGE5_GEOMETRY`/`STAGE5_HUMAN`.

The complete evidence and line-level flow are in
`PHASE0_ASSUMPTION_SCOPE_AUDIT.md`.

## 4. Assumptions and truth sources before recovery

Acceptable current sources are limited to measured robot state/cuff F/T and
registered structural ROM/topology. Unacceptable session dependencies include:

- provisional fixed `T_WB`, `T_WH`, `T_EC`;
- fixed sagittal basis and exact initial-q task pose;
- fixed `L1`, full `L2`, shank radius, cuff fraction/offset and knee-to-cuff
  distance;
- fixed interface stiffness, damping, rest state, effective mass and inertia;
- fixed bed/table geometry;
- nominal passive/rest/soft-limit mechanics unless an opt-in beta path replaces
  only the control-effective dynamic combinations.

MuJoCo q/dq/qdd and interface truth are logged in evaluation namespaces. The
primary violation is not a direct truth-object input; it is oracle-equivalent
plant/controller equality through shared constants.

## 5. Final assumptions and truth sources after recovery

No production estimator/controller source was promoted because the hard stop
precedes Phase 1. Therefore the current production truth sources remain
unchanged and noncompliant.

The campaign added an explicit source taxonomy and a fail-loud provenance guard
that permits only `MEASURED`, `CALIBRATED`, `ONLINE_ESTIMATED`, or
`STRUCTURAL_PRIOR` for session-specific deployable quantities. The guard is
campaign-scoped and intentionally not represented as integrated controller
protection.

## 6. Geometry/state estimator method and selection

No estimator method was selected for promotion. The Stage-4 structured
five-parameter cuff-geometry fit was audited as the best historical starting
point because it consistently supplies q/dq, the cuff Jacobian and generalized
wrench effect. It is not sufficient as-is: it assumes Human-side cuff pose,
anchors the sagittal basis with an exact initial-q prior, and estimates
knee-to-cuff distance rather than full shank length required by clearance.

Implementing or tuning an estimator after proving that its required output is
not identifiable would manufacture a false recovery result.

## 7. Identifiability findings

For planar Human V2 cuff kinematics,

`p_c = p_hip + L1 e(q1) + sc e(q1-q2)`, with `sc=f L2`.

Only `sc` enters cuff position, twist, translational Jacobian and `J^T w`.
The frozen analytical audit compared:

- `(L2,f)=(0.40076 m,0.72)`;
- `(L2',f')=(0.46 m,0.6272765217)`.

Both have `sc=0.2885472 m`. Results:

- stacked `[L2,f]` observation sensitivity rank: `1`;
- singular values: `[1.8425642, 4.3753e-17]`;
- maximum cuff-pose residual: `0 m`;
- maximum cuff-Jacobian residual: `0`;
- maximum generalized-effect residual: `0 Nm`;
- ankle-position difference: `59.24 mm`.

A second cuff-kinematic gauge rotates the in-plane basis by `gamma` while
shifting `q1` by `-gamma`. At `gamma=17 deg`, world cuff pose, orientation and
Jacobian residuals remained approximately `1.3e-16` to `2.3e-16`. A calibrated
sagittal zero/known-q pose can resolve that gauge; the current code silently
uses the exact reset q as its prior.

The `L2/f` ambiguity alone is sufficient for the terminal status because full
`L2` remains a hard-clearance input.

## 8. Dynamics interaction with geometry estimation

The current beta model is deliberately control-effective and does not provide a
validated inverse map to anatomy. Reusing beta to infer exact `L2` would add an
anatomical constraint not supported by the current contract. Conversely,
fitting beta on biased fixed geometry risks letting dynamic parameters absorb
geometry error. No dynamic model was promoted and no claim of joint recovery
was made.

Strict `L1=0.254h`, `L2=0.233h` relations could remove one ambiguity only if
explicitly approved as an exact session structural prior; repository history
shows they are simulator-family limitations, not deployment calibration
evidence.

## 9. Formal unknown-setup experiment design

Phase-1/2 formal held-out control experiments were not started. Their required
setup family could not be evaluated honestly while the deployable estimator
input/output map is structurally non-identifiable.

One preregistered deterministic analytical audit was run. Its allowed
observations, hidden evaluation quantities, equivalence rule, postures, pass
rule, failure rule and exclusion policy were frozen before execution.

## 10. Required A/B/C/D ablations

The Phase-2 ablations—A oracle geometry/oracle dynamics, B estimated
geometry/oracle dynamics, C estimated geometry/estimated dynamics, and D wrong
fixed nominal geometry—were not run. Phase 1 did not pass identifiability, so
running them would not constitute valid Phase-2 evidence.

## 11. Metrics and preregistered thresholds

The analytical failure rule required a rank-deficient `[L2,f]` observation map,
a distinct legal pair with identical cuff kinematics/generalized effects, and a
different control-critical downstream ankle location. Every condition was met.
The q1 gauge was also reproduced to numerical precision. No threshold was
changed after observing results.

Current hashes:

- immutable contract SHA-256:
  `d6a6bcffd6bc05e84016c9a903f8eefa9d41b6a2e42320030b0230015e096e05`;
- audit spec SHA-256:
  `2e12a112930a3c9600533b36ae948992a125d2ce0c486a30df26bcb058f9f489`;
- result SHA-256:
  `7f5fa59d6886d84f2d4f3c67f5bf880c51ce4531b37d532e92a8835cc4516a39`.

## 12. Auditor findings and repair cycles

The independent fresh-context Auditor rejected the first Phase-0 submission
because it omitted the absolute-q1 gauge and several control-critical source
rows. Builder repair cycle 1 added the gauge, shank radius, bed plane/height,
interface mass/inertia, passive/rest, soft-limit and sagittal-zero provenance,
plus mismatch/provenance tests.

Final Auditor verdict:

- Phase-0 audit completeness: PASS;
- current architecture: NONCOMPLIANT;
- terminal hard stop: `BLOCKED_IDENTIFIABILITY`.

No further repair cycle is scientifically justified without new information or
authority.

## 13. Remaining truth/fixed-nominal dependencies

All fixed dependencies listed in section 4 remain in the production path.
Most directly, fixed Human geometry supplies q/dq, Jacobian, wrench mapping and
clearance, while a provisional fixed interface model supplies Human-side cuff
pose/twist. The campaign guard is not integrated.

## 14. Phase-3 integration status

Not reached. Existing HWMPC can consume a model object, but the present path
does not meet the recovered source contract. `PHASE_3_READY` is false.

## 15. Runtime and computational limitations

No quota, wall-clock, MuJoCo, optimizer or external-network limitation caused
the stop. The first system Python lacked NumPy; the repository's existing
`mpc_learn` Conda environment was used. The stop is structural scientific
identifiability, not a tooling failure.

## 16. Related literature

No external work materially influenced the terminal decision. The result is an
exact invariance derived from repository equations and independently
reproduced. `RECOVERY_RELATED_WORK.md` and `recovery_refs.bib` therefore contain
no fabricated or decorative citations.

## 17. Files added or modified by this campaign

Added only inside the `architecture_recovery_v1` namespace:

- `docs/architecture_recovery_v1/ORIGINAL_SYSTEM_CONTRACT.md`
- `docs/architecture_recovery_v1/RECOVERY_PHASE_STATUS.md`
- `docs/architecture_recovery_v1/RECOVERY_AUDIT_LOG.md`
- `docs/architecture_recovery_v1/RECOVERY_RELATED_WORK.md`
- `docs/architecture_recovery_v1/recovery_refs.bib`
- `docs/architecture_recovery_v1/PHASE0_ASSUMPTION_SCOPE_AUDIT.md`
- `docs/architecture_recovery_v1/ARCHITECTURE_RECOVERY_FINAL.md`
- `configs/architecture_recovery_v1/README.md`
- `configs/architecture_recovery_v1/identifiability_audit_v1.json`
- `results/architecture_recovery_v1/README.md`
- `results/architecture_recovery_v1/identifiability_audit_v1/result.json`
- `scripts/architecture_recovery_v1/run_identifiability_audit.py`
- `src/traction_mpc_stage5/architecture_recovery_v1/__init__.py`
- `src/traction_mpc_stage5/architecture_recovery_v1/provenance.py`
- `tests/architecture_recovery_v1/test_identifiability_and_provenance.py`

No protected pre-existing file or historical result was modified by the
campaign.

## 18. Tests, checks and experiments run

- Analytical identifiability audit: PASS as an execution; scientific outcome
  `NON_IDENTIFIABLE`.
- Campaign provenance/equivalence suite: `4 passed`.
- Historical estimator + Stage-5 task observation/controller interface focused
  suite: `20 passed` after setting the repository source paths.
- Initial unscoped pytest invocation: collection failed because source-package
  paths were absent; preserved here as a tooling failure, then corrected without
  changing code.
- Modified Python compilation: passed in `mpc_learn`.
- JSON config/result validation: passed.
- Immutable contract hash recheck: passed unchanged.
- Independent Auditor reran the analytical audit and focused tests and obtained
  the same scientific result.

## 19. Git and repository status

- Starting branch: `codex/stage5-cr12-sim`.
- Starting/current HEAD: `4caea258ec1450f082bb7cb8097cc1441bdf589f`.
- Campaign branch: `codex/stage5-architecture-recovery`.
- The large modified/untracked Stage-4/5 working state predated this campaign
  and remains protected.
- Nothing was staged, committed, pushed, reset, stashed, or deleted.
- Scientific variables changed: none.
- Controller/estimator parameters or configs changed: none; only a new
  analytical audit spec was added.
- Assumptions changed: none. Unverified fixed assumptions were exposed rather
  than adopted.

## 20. Recommended next step

- Measure/calibrate full shank length or a distal ankle/joint-center landmark,
  cuff location, and a known Human sagittal zero pose for each session, then
  start a new versioned recovery campaign from Phase 1 with those quantities
  explicitly classified as `MEASURED`/`CALIBRATED`.
