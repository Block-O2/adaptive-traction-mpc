BLOCKED_CONTRACT_CHANGE_REQUIRED

# Architecture Recovery V2 Final Report

## 1. Executive interpretation

The V2 campaign recovered a promising deployable, control-effective adaptive
MPC in development, but it did not earn a formal held-out or Phase-3-ready
claim. The strongest exact-source lying-bed development completed adaptive and
oracle `6/6`; adaptive median/p95 tracking RMSE were `0.6533/2.4187 deg`, with
`120.68 N / 25.72 Nm` full-episode peaks and zero registered-ROM, analytical
shank-bed-clearance, solver, safety, or causal-consistency events. Fixed nominal
completed `0/6` and adaptive geometry with fixed dynamics completed `1/6`.

The campaign stops because the immutable contract permits at most four material
repair cycles per major phase. The independent Auditor rejected an autonomous
Phase-1A/Phase-1B budget reset and classified the bed-domain, multirate-probe,
and conditional-refit revisions as material Phase-1 changes after the already
declared fourth cycle. A new physically feasible knee-led task definition and
fresh bed-valid Phase-2 study remain scientifically plausible, but they require
a human-approved, versioned contract amendment. This is not a demonstrated
control-sufficiency impossibility or method exhaustion.

## 2. What Stage 1--3 actually achieved

- Stage 1 implemented adaptive single-link Spring2D planning/tracking with UKF
  state estimation and online `[m,k,b_r]` estimates. Current-source replay
  completed `144/144` isolated runs; adaptive/oracle crossings were `24/24`
  and fixed was `0/24`, while the adverse true-acceleration tail remained.
- Stage 2 used fixed nominal planar Human-V2 inverse dynamics and rigid-cuff
  tracking. It did not implement the modern hidden-setup adaptive problem.
- Stage 3 provided a fixed-model coupled Human-V2/UR10e-surrogate execution
  foundation and explicitly deferred adaptation to Stage 4.
- Stage 4, not Stage 1--3, was the strongest historical multi-link adaptive
  controller. Original source at `ef1fe90e61c5981df8e934585780ce188d104ea4`
  reproduced both registered arms completing at `28.87 s`, first promotion at
  `9.72 s`, and tracking RMSE `0.765477 -> 0.713056 deg`.

Phase 0 passed independent audit. Historical limitations, including exact
initial-q startup, finite registered trajectories, fixed contact/setup
assumptions, and the lack of a broad unknown-task/unknown-setup proof, remain
part of the record.

## 3. Capability lost or bypassed by Stage 5

The Stage-5 baseline froze global Human geometry/dynamics and narrowed the task
while building deterministic goal-MPC and later waypoint/session prototypes.
It did not preserve Stage-4 online geometry and dynamics authority as a general
deployable path. Exact start targets, fixed placement, fixed cuff fraction, and
fixed Human parameters replaced the historical adaptive initialization path.

## 4. V1 identifiability finding and V2 treatment

V1 remains valid negative evidence: full shank length `L2` and cuff fraction
`f` are individually non-identifiable from the tested cuff channel when only
`sc=fL2` enters cuff pose/Jacobian/wrench mapping. V2 did not inject either
hidden value into control. It estimated the control-effective tuple
`(hip_x, hip_z, L1, sc)` and retained full `L2` only in the simulation/evaluation
path for analytical ankle/shank clearance. Absolute pre-fit q was not treated
as exactly known; the commissioning supervisor is an uncertainty-aware causal
consistency envelope, while hidden true ROM remains evaluation-only.

## 5. Final adaptive/control-sufficient representation

The development architecture uses:

- a first-pose population frame plus measured cuff pose/orientation history;
- a causal four-dimensional effective-geometry fit
  `(hip_x, hip_z, thigh_length, knee_to_cuff_distance)`;
- measured cuff twist for deployable q/dq reconstruction;
- an online bounded 11-base Human-V2 dynamics representation;
- conditional active-set regression: a boundary-limited coefficient remains at
  its last-valid value and correlated free coefficients are re-solved before
  residual and positive-definite-mass checks;
- a feasible-first Human-space CEM MPC with current-q wrench allocation;
- causal estimated-ROM/consistency aborts and separate evaluation-only hidden
  ROM/clearance termination.

Individual anatomy is not reconstructed when control does not require it.

## 6. Final architecture and data flow

`measured cuff pose/twist + applied wrench history -> effective geometry/state
-> bounded 11-beta update -> Human-space MPC -> generalized action -> estimated
geometry wrench allocation -> hidden plant (simulation only) -> next measured
observation`.

Hidden setup enters case generation and the hidden plant. It also enters the
explicit oracle and post-run evaluation. It does not enter adaptive geometry,
dynamics identification, candidate generation, MPC prediction, or action
selection. Controller randomness is fixed independently of setup/task RNG.

Commissioning runs at `100 Hz`; task MPC runs at `50 Hz`. The earlier `50 Hz`
commissioning implementation produced a discrete limit cycle and is preserved
as a failed result. Post-audit preview provenance now records the actual task
control interval rather than the stale `0.04 s` value.

## 7. Hidden setup/task domain

Development varied continuously: height scale `0.88--1.12`, mass scale
`0.78--1.28`, passive stiffness `0.65--1.45`, damping `0.70--1.35`, rest
offsets, COM scales, hip placement x `[-0.12,0.12] m`, hip height
`[0.045,0.16] m`, cuff fraction `[0.52,0.88]`, initial q1 `[6,18] deg`,
initial q2 `[10,28] deg`, task goals/durations, and standard/high-ROM flags.

The lying-bed development proposal was conditioned before execution on
analytical shank-capsule/flat-bed reference clearance >= `0.01 m`, oracle
static force <= `150 N`, and static moment <= `45 Nm`; runtime gates remained
`200 N / 60 Nm`. This is a conditional joint setup/task distribution. Proposal
RNG streams are independent, but accepted setup/task samples are not
statistically independent. All six v4 development samples were accepted on
attempt zero, so those six were not replacement-selected by the filter.

The clearance claim covers only a shank capsule and flat bed. It does not cover
contact dynamics, thigh/body/cuff collision, pressure/tissue safety, or robot
reach/torque.

## 8. Adaptation behavior

Geometry fit error was small in the passing development cases and dynamics
updates materially affected control. In the exact-source v4 matrix, adaptive
completed `6/6`; no-dynamics completed `1/6`; wrong geometry with adaptive
dynamics completed `0/6`. The result supports the need for both geometry and
dynamics adaptation in development, but it is not a formal generalization
claim.

## 9. Trajectory/reference generalization

Passing bed development covered coordinated, hip-lead, and two-rate profiles,
with smooth OUTBOUND/HOLD/RETURN motion, continuous goals and duration, standard
and high-ROM cases. It did not validate a physically feasible knee-led profile.
The original `knee_lead` semantic moved the knee to its goal while the hip
remained near its initial angle; bed-feasible generation exhausted 1000
attempts because that intermediate rotates the shank toward the bed. Removing
it from v4 was a development diagnosis, not authorization to silently shrink
the final formal task family.

## 10. High-ROM envelope

The unchanged verified Human-V2 plant hard limits are q1 <= `80 deg` and q2 <=
`100 deg`, with a `5 deg` soft-limit layer. Therefore the requested
`120--130 deg` target is outside this model and cannot be tested by disabling
constraints. The largest defensible target box investigated here was q1
`66--75 deg`, q2 `82--95 deg`. Three v4 high-ROM development cases completed
for adaptive/oracle with zero analytical shank-bed events. No formal held-out,
CR12, contact-dynamics, or clinical high-ROM claim was earned.

## 11. Formal held-out design and gates

The earlier `PHASE2_PREREGISTRATION_V1.md` and
`phase2_formal_unknown_setup_task_v1.json` are frozen but unexecuted. They
describe a suspended/no-bed benchmark, omit the final multirate provenance,
and cannot establish the required lying-bed claim. No Phase-2 held-out result
or seed was viewed.

A future amended preregistration would need fresh unviewed seeds, the explicit
conditional mechanics generator, all failures in the denominator, oracle and
adaptive complete metrics, zero event gates, median <= `3 deg`, p95 <= `5 deg`,
completion >= `0.90`, `200 N / 60 Nm` runtime gates, adaptive-oracle median gap
<= `2.5 deg`, and material comparisons against fixed, no-dynamics, and
wrong-geometry arms. The runner now contains the missing adaptive-versus-wrong-
geometry gate, but no new formal config was retroactively frozen or executed.

## 12. Comparison evidence

Exact-source bed development v4:

| Arm | Completion | Full-horizon median RMSE | p95 RMSE | Key outcome |
|---|---:|---:|---:|---|
| Oracle | 6/6 | 0.4070 deg | 0.5663 deg | zero events |
| Adaptive | 6/6 | 0.6533 deg | 2.4187 deg | zero events |
| Fixed nominal | 0/6 | incomplete baseline | incomplete baseline | 3 estimated-ROM aborts, 1 clearance event |
| Wrong geometry + adaptive dynamics | 0/6 | incomplete baseline | incomplete baseline | 3 estimated-ROM aborts |
| Effective geometry + fixed dynamics | 1/6 | 5.9036 deg | 9.8040 deg | zero ROM/clearance events, poor task completion |

The strongest historical Stage-4 baseline is reported separately because its
exact-initial-q, single registered setup/task contract is not case-wise
comparable to this hidden-setup domain.

## 13. Failure cases retained

The append-only failure ledger preserves numerical integration failures,
nonfinite MPC predictions, ROM-unsafe commissioning, computed-torque and
impedance probe failures, conditioning failures, moment-sign error, symmetric-
probe failure, false causal supervisor aborts, strict-JSON failure, bed
generation failure, commissioning handoff limit cycle, and correlated boundary-
fit rejection. In particular:

- bed v1: oracle `4/6`, adaptive `3/6`, no-dynamics `1/6`; `knee_lead`
  generation failed;
- bed v2: oracle `5/6`, adaptive `4/6`; seed 3101 entered the task around
  `[-39.8,-253.9] deg/s` and safely found no action;
- bed v3: oracle `6/6`, adaptive `4/6`, adaptive p95 `5.3217 deg`; the raw fit
  improvement was invalidated by post-hoc correlated-coordinate substitution;
- bed v4: development passed after multirate commissioning and conditional
  refit, without deleting or relabeling the preceding failures.

## 14. Independent Auditor and fragility review

The Auditor approved Phase 0, independently checked source/config hashes and v4
metrics, reran the focused suite, and found no deployable truth leak. The
Auditor nevertheless issued formal NO-GO and agreed on
`BLOCKED_CONTRACT_CHANGE_REQUIRED` because:

- the four-cycle Phase-1 cap cannot be reset autonomously;
- a new partial-knee-then-coordinated profile is a material versioned task
  definition requiring development evidence;
- the feasibility-conditioned domain and acceptance rate must be explicit;
- clearance claims must remain limited to analytical shank-capsule/flat-bed;
- Phase-2 V1 is the wrong environment contract.

The final stack is structured and interpretable: one geometry fit, one dynamics
identifier, one MPC, and explicit supervisors. No learned latent module,
set-valued MPC, dual-control layer, or hidden fallback was added. Failures are
detectable through fit rejection, consistency/ROM/clearance events, solver
status, wrench gates, and source/config provenance.

## 15. Literature used

Lu and Cannon (2023, DOI `10.1016/j.automatica.2023.110959`) supported bounded
persistent excitation but not a nonlinear guarantee. Parsi et al. (2023, DOI
`10.1016/j.ifacol.2023.10.1132`) informed the reserved dual/set-membership path,
which was not added. Yang, Choset and Manchester (2022, DOI
`10.1109/LRA.2022.3186501`) supported observable effective-geometry calibration.
Du et al. (2018, DOI `10.3389/frobt.2018.00116`) supported separating high-level
rehabilitation adaptation from lower-level tracking, without importing its
extra sensor assumptions.

## 16. Phase-3 Human-waypoint integration

Phase 3 was not started because Phase 2 did not pass. The existing opt-in
state-feedback Human-waypoint prototype was inspected as the intended target,
but the recovered V2 belief/model was not integrated into it. Therefore V2 does
not claim event-driven OUTBOUND/HOLD/RETURN completion, robot execution
feasibility, or Phase-3 readiness.

## 17. Future value-learning insertion point

No V2 candidate-value hook was implemented because Phase 3 was gated off. No
value learning, imitation learning, or RL was trained. The intended future API
remains `value(state_or_belief, candidate_next_waypoint)` alongside deterministic
cost/feasibility and learning-ready transition logging.

## 18. Runtime/computational limitations

The evidence is deterministic offline Python simulation on the `mpc_learn`
environment. Cuff twist is an ideal noiseless simulated derivative; this is a
hardware-transfer limitation. The development MPC uses 24 CEM candidates, two
iterations, horizon 8, 50 Hz task control, and 100 Hz commissioning. No real-
time hardware deadline, sensor latency/dropout, contact solver, or long-run
Monte Carlo reliability claim was validated.

## 19. Hardware-transfer limitations

No CR12 or other hardware was actuated. There was no human experiment. The
campaign does not establish CR12 reachability, joint torque, collision,
interface compliance, pressure/tissue safety, clinical safety, or patient
suitability. Bed/table geometry and full-shank clearance would require an
allowed calibration or conservative uncertainty contract on hardware.

## 20. Files changed

All campaign work is versioned under the new
`architecture_recovery_v2` docs/configs/results/scripts/source/tests namespace.
Key authored files are `effective_model.py`, `functional_benchmark.py`,
`run_functional_campaign.py`, three focused test modules, the Master Contract,
Phase-0 report, phase status, audit log, failure ledger, mechanics report,
related-work files, development/diagnostic/formal-v1 configs, and this final
report. Generated result directories preserve every completed and failed run,
source snapshots, manifests, commands, environment, Git state, rows, and
summaries. V1 and historical Stage artifacts were not rewritten.

## 21. Experiments, commands, and checks

- Recorded `git branch --show-current`, `git rev-parse HEAD`, and full
  `git status --short` before work.
- Reproduced original-source Stage-4 A/B and current-source Stage-1 Stage-9J.
- Ran the Phase-1 commissioning/diagnostic/development ladder and five-arm
  comparisons; all failures are recorded in `FAILURE_LEDGER.md`.
- Ran bed-feasible v1--v4 plus handoff and conditional-refit diagnostics.
- Final focused suite: `14 passed`.
- `py_compile`: passed for V2 source and runner.
- All V2 JSON files: parsed with `python -m json.tool`.
- `git diff --check`: passed.
- No formal Phase-2 held-out campaign was run.

## 22. Git and change-control state

- Starting/current branch: `codex/stage5-architecture-recovery`.
- Starting/current HEAD: `4caea258ec1450f082bb7cb8097cc1441bdf589f`.
- The pre-existing dirty/untracked worktree was preserved.
- Scientific variables changed in new versioned development artifacts: the
  analytical bed feasibility generator, `100 Hz` commissioning cadence, and
  conditional active-set dynamics refit.
- Explicitly unchanged: verified Human-V2 dynamics, hard/soft ROM, task MPC
  horizon/candidate/optimizer settings, task runtime force/moment gates, high-
  ROM goal box, bed height/radius, and historical/V1 evidence.
- No file was staged, committed, pushed, reset, stashed, merged, or deleted.

## 23. Exactly one recommended next step

Obtain human approval for a versioned contract amendment that either raises the
Phase-1 repair budget or creates a separately authorized bed/mechanics major
phase, while preserving the B1--B4 ledger and authorizing one versioned
physically feasible knee-led development study followed, only if it passes, by
a fresh bed-valid Phase-2 preregistration with unviewed seeds.
