# Stage-4 Professor-Report Validation Experiment Spec

Status: **approved v2 preregistration amendment; formal v2 gain tuning has not
yet been executed; benchmark, demo, and final rendering remain unauthorized**.

Frozen ancestry: `stage4-robustness-final-v1` at
`cc04765761d08ffaf1914f0236f0201d9c7e1475`.

Machine-readable contracts:

- immutable v1: [`configs/stage4_report_validation_matrix.json`](../../configs/stage4_report_validation_matrix.json);
- active v2 amendment: [`configs/stage4_report_validation_matrix_v2_coupled_pd.json`](../../configs/stage4_report_validation_matrix_v2_coupled_pd.json).

## 0. Prospective v2 amendment and immutable v1 history

The v1 nine-candidate PD gain selection was formally executed before this
amendment. All nine candidates were mechanically ineligible because they
triggered the unchanged cuff-force safety gates. No v1 gain lock was created.
The complete v1 output root remains immutable at
`results/stage4_report_validation_gain_tuning_formal`. Its status artifact is:

```text
results/stage4_report_validation_gain_tuning_formal/gain_selection_status.json
SHA-256: e78cc4b6e5ed9fa8641d8232410298ada2b9dff90ce3a06fcea739b5aa0ef61f
```

Read-only diagnosis found no implementation, wiring, reference-clock, unit,
sign, allocator, geometry, or fresh-state error. The v1 scientific design had
instead retained only the diagonal entries of `M(q0) diag(K)`, discarding the
nominal hip-knee inertial cross-coupling in the frozen Stage-3
computed-acceleration feedback. This v2 amendment was defined prospectively
before any v2 formal gain-selection or benchmark result. It does not relabel,
rewrite, or remove the failed v1 evidence.

## 1. Scope and evidence boundary

This phase asks a professor-facing controller question:

> What incremental performance change is observed when the shared controller
> stack adds (1) Human-space feedback, (2) nominal inverse-dynamics
> feedforward, (3) predictive control, and (4) patient-specific trusted
> control-effective dynamics adaptation?

The planned contrasts are sequential and descriptive:

1. `pd_nominal_inverse_dynamics_ff - pd_feedback`: nominal feedforward;
2. `fixed_mpc_prior_only - pd_nominal_inverse_dynamics_ff`: predictive
   optimization under the population-prior dynamics;
3. `trusted_adaptive_mpc - fixed_mpc_prior_only`: trust-gated retained-beta
   adaptation beyond the common causal geometry estimator.

These contrasts do not prove that the components are independent in a
nonlinear constrained plant. They must be reported with raw arm metrics,
termination reasons, and safety events rather than only with percentage
improvements.

Three evidence categories remain separate:

| category | role | may become Stage-4 canonical evidence? |
|---|---|---|
| existing authoritative Stage-4 | frozen context, provenance, and one read-only reference-clock trace | no mutation or relabeling |
| report-validation scientific baseline | new four-controller comparison after gain lock | only report-validation evidence, never silently Stage-4 evidence |
| visualization/demo-only | communication scenes and renders | no |

The nine nominal gain-selection rollouts are selection evidence only and are
excluded from the primary controller comparison. Existing Stage-4 performance
values are not reused in the new benchmark because the four-controller runner
and shared exogenous reference clock create a new controller fingerprint.

## 2. Shared plant and action boundary

All four controllers produce the same interface quantity: a two-vector of
desired Human generalized cuff action, `tau_h` in Nm. The unchanged registered
1:1 cuff-aware allocator solves the rigid-cuff equality
`B(q_hat) [Fx, Fz, My]^T = tau_h` and produces a six-dimensional world cuff
wrench. That wrench enters
`SensorBoundaryStage4Plant.apply_measured_nominal_cartesian_control` as the
feedforward wrench.

The common robot low level then adds its existing Cartesian pose/velocity
feedback, maps the total wrench through the robot attachment Jacobian, adds
MuJoCo bias torque and the existing posture nullspace term, and applies the
existing robot actuator limits. Thus, “PD” below means the **additional
Human-space high-level PD action**; it does not remove the shared robot
Cartesian servo. The shared low-level servo must be named explicitly in every
report figure and methods description.

All arms retain the same:

- MuJoCo UR10e surrogate, Human V2, bed/contact and rigid cuff;
- 1 ms simulation step, 5 ms robot low-level period, and 20 ms high-level
  action period;
- causal robot/cuff measurement boundary and `noise_bias_drift_200hz`, seed
  `44104`;
- causal state/geometry estimator and 11-base identifier/trust lifecycle;
- registered memoryless 1:1 cuff allocator;
- force gate, ROM/contact checks, robot limits, torque clipping, and termination
  semantics;
- initial Human posture `[5 deg, 10 deg]` and the corresponding deterministic
  robot IK reset.

No controller receives clean Human state or true patient parameters. The
identifier/trust lifecycle runs as a diagnostic sidecar for PD and PD+FF, but
qualified beta never enters those actions. The fixed MPC uses the population
prior for the entire rollout. Only trusted adaptive MPC may apply an existing
qualified incumbent beta.

## 3. Controller definitions

Let `e_q = q_ref - q_hat` and `e_dq = dq_ref - dq_hat`. All quantities are
evaluated at the same exogenous reference phase and causal state estimate.

| controller | exact Human-space action | model use | adaptive state label |
|---|---|---|---|
| PD | `kp_scale Kp_tau_matrix e_q + kd_scale Kd_tau_matrix e_dq` | constant nominal-inertia-derived coupled torque PD; no runtime dynamics model in the action; shared estimated geometry remains necessary for sensing/allocation | `N/A` |
| PD + nominal inverse-dynamics FF | PD action plus `tau_prior(q_ref,dq_ref,ddq_ref)` | fixed population-prior inverse dynamics and shared causal geometry | `PRIOR` |
| fixed MPC / prior-only MPC | first action of the frozen feasible-first batched CEM MPC | frozen population-prior beta throughout; existing qualification is diagnostic only | `PRIOR` |
| trusted adaptive MPC | first action of the same frozen feasible-first batched CEM MPC | population prior until existing trust promotion, then retained incumbent beta | `PRIOR` then `ACTIVE` |
| optional oracle MPC | same MPC with clean true patient model | non-deployable God-view upper bound | not included or authorized |

The MPC horizon, candidates, iterations, elites, seed, objective weights,
constraints, allocator, and safety gates remain frozen. In particular, all
three interaction-objective weights remain zero; Stage-4 is not retuned.

For PD+FF, the feedforward is evaluated at the reference state, not the
measured error state. This keeps the added term interpretable as nominal task
demand rather than hiding extra model-based feedback inside it. The PD and
PD+FF arms use exactly the same selected `Kp_tau` and `Kd_tau`.

## 4. Reference-clock fairness

Controller-dependent confidence pacing would expose the arms to different
time histories after their measurements diverge. The report benchmark instead
replays one exogenous phase clock to every arm. It reads only `time_s` and
`reference_phase_time_s` from the frozen formal prior-only trace:

```text
results/stage4_patient_mismatch_robustness_formal/
  registered_formal_perturbed_anchor/prior_only_trace.npz
SHA-256: 2ef8e9b9b34b20bebed9c02f562e39240cb912424c4ebc24edaa48b81ee981b2
```

For a trajectory of duration `T`, the replayed phase is
`clip(source_phase(t) * T / 23, 0, T)` with linear interpolation on the
recorded wall-time grid. The trace is used only as a read-only clock—not as
performance evidence. No controller state, trust output, tracking error, or
oracle quantity can modify this clock. All selected trajectories are 23 s, so
the scale is one in this preregistration.

This choice intentionally makes the new report-validation fingerprint differ
from authoritative confidence-paced Stage-4 evidence. It permits a stricter
same-reference comparison while preserving the original evidence unchanged.

## 5. One-time nominal PD gain selection

PD gains are selected once, before mismatch comparison, using only:

- patient: `nominal_reference`;
- trajectory: `moderate_rom_23s`;
- sensor realization: `noise_bias_drift_200hz`, seed `44104`;
- controller: PD only;
- the same plant, clock, allocator, low level, limits, and safety gates used by
  the benchmark.

The v1 diagonal construction is retired but retained in the immutable v1
contract and failed evidence. V2 preserves the full nominal inertial coupling
at the fixed initial configuration only. With
`q0 = [5 deg, 10 deg]`, `Kp_a = diag([180,140])`, and
`Kd_a = diag([28,22])`, the constant base matrices are:

```text
Kp_tau_matrix = M(q0) Kp_a
 = [[381.2577801496745,  -74.5250088544332],
    [-95.8178685271284,   27.815317728811202]] Nm/rad

Kd_tau_matrix = M(q0) Kd_a
 = [[ 59.30676580106047, -11.711072819982359],
    [-14.905001770886638,  4.37097850024176]] Nm s/rad
```

These are frozen `2 x 2` constants. Runtime PD must use matrix multiplication
and must not evaluate `M(q)`, inverse dynamics, or any other Human dynamics
model. This is **constant nominal-inertia-derived coupled torque PD**. PD+FF
uses the same matrix feedback plus the existing population-prior inverse
dynamics evaluated at the reference state. It is not runtime mass-matrix
feedback and not computed-acceleration control.

The only candidates are the 3 x 3 product of
`kp_scale in {0.5, 1.0, 1.5}` and
`kd_scale in {0.5, 1.0, 1.5}`. There are exactly nine tuning rollouts.

A candidate is mechanically eligible only if it completes, reaches reference
progress 1, records no safety event, and provides finite required metrics.
Eligible candidates are ordered by:

1. tracking combined RMSE;
2. maximum absolute tracking error;
3. cuff-force RMS;
4. lower `kp_scale`;
5. lower `kd_scale`.

Numeric ties use absolute tolerance `1e-12`. The selected gains and the full
candidate table must be written to
`results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd/frozen_pd_gains.json`;
the benchmark runner must require its SHA-256. The same gains are then frozen
for PD and PD+FF for every patient and trajectory.

If no v2 candidate is mechanically eligible, preserve all v2 outputs, stop, and ask
the user for a new scientific decision. Do not expand the grid, weaken a gate,
or tune on a mismatch case.

## 6. Exact patient cases

The scientific benchmark uses four existing, already defined cases:

| patient | interpretation | exact changes from population prior |
|---|---|---|
| `nominal_reference` | zero-mismatch sanity reference | all scales 1; rest offsets 0 |
| `mass_mild_plus_05pct` | isolated mass change | body mass `1.05`; all other scales unchanged |
| `registered_moderate_anchor` | moderate mixed mismatch | mass `1.05`, thigh COM `1.05`, shank COM `0.95`, stiffness `1.10`, rest `[-2,-2] deg`, sleeve center `1.02` |
| `registered_formal_perturbed_anchor` | stronger/formal mixed geometry mismatch | height `1.06`, mass `1.08`, thigh COM `1.04`, shank COM `0.96`, stiffness `1.15`, rest `[-2,+3] deg`, sleeve center `0.94` |

The demo matrix additionally defines one report-only isolated geometry case
because the frozen patient suite contains no isolated height/leg-length case:

`height_moderate_plus_03pct_report_only` scales height, and therefore both
segment lengths, by `1.03` while holding total mass, COM fractions, passive
stiffness/damping, rest angles, and dimensionless sleeve location at their
nominal definitions. It is an engineering illustration, not a clinical range
claim, and must never be inserted into the old Stage-4 patient config or
canonical evidence.

## 7. Exact trajectories

Only these existing trajectory definitions are selected:

| trajectory | professor-facing interpretation | use |
|---|---|---|
| `registered_high_flexion_23s` | staged hip/knee flexion, high-flexion hold, staged return | primary benchmark and nominal visualization |
| `hip_dominant_low_knee_23s` | straight-leg-raise-like hip-dominant task with the knee near, but not at, zero flexion | isolated-geometry visualization |
| `moderate_rom_23s` | same staged flexion-return pattern at 60% joint excursion | gain selection and moderate-mixed visualization |

`two_cycle_moderate_23s` remains mechanism/robustness evidence and is excluded
from the main professor-facing matrix.

## 8. Exact experiment matrices and counts

### 8.1 Scientific benchmark

Each row below is crossed with all four controllers, trajectory
`registered_high_flexion_23s`, and measurement seed `44104`.

| benchmark row | patient | controller arms | new rollouts |
|---|---|---:|---:|
| B1 | `nominal_reference` | 4 | 4 |
| B2 | `mass_mild_plus_05pct` | 4 | 4 |
| B3 | `registered_moderate_anchor` | 4 | 4 |
| B4 | `registered_formal_perturbed_anchor` | 4 | 4 |
| total | 4 patients x 1 trajectory x 1 seed | 16 | 16 |

There is no authoritative-result reuse in these 16 arms. Historical Stage-4
results may be shown separately as context only.

### 8.2 Visualization/demo matrix

Each scene contains synchronized panels for all four controllers.

| scene | patient | trajectory | data source | new rollouts |
|---|---|---|---|---:|
| V1 nominal high flexion | `nominal_reference` | `registered_high_flexion_23s` | exact B1 reuse | 0 |
| V2 isolated geometry SLR-like | `height_moderate_plus_03pct_report_only` | `hip_dominant_low_knee_23s` | demo-only | 4 |
| V3 moderate mixed moderate ROM | `registered_moderate_anchor` | `moderate_rom_23s` | demo-only | 4 |
| total | 3 scenes | 3 selected trajectories | 12 logical arms | 8 |

Exact unique control rollouts are therefore:

```text
9 gain-selection + 16 scientific benchmark + 8 new demo-only = 33
```

The optional oracle contributes zero rollouts. No additional seeds, patients,
trajectories, or ablations may be added without revising and re-approving this
spec before execution.

## 9. Metrics and reporting

Metrics use samples whose reference phase is within the selected task.

- Tracking combined RMSE: square root of the mean squared joint-angle error
  over time and both Human joints, in degrees.
- Maximum tracking error: maximum absolute joint-angle error over time and both
  joints, in degrees.
- Completion/progress: first wall time that reference phase reaches task
  duration, and `min(1, final_phase / duration)`.
- Cuff force peak/RMS: peak and RMS of the norm of the reconstructed 3D cuff
  force, in N.
- Cuff moment peak/RMS: peak and RMS of the norm of the reconstructed 3D cuff
  moment, in Nm.
- Robot torque: per-joint and global peak absolute commanded torque; retain RMS
  per joint as a diagnostic.
- Safety: raw event counts, termination reason, ROM/contact records, force-gate
  events, and torque saturation counts. Do not collapse these into an
  independently invented scientific PASS/FAIL threshold.
- Runtime: rollout wall time, high-level controller compute mean/p95/max, solve
  count, achieved controller frequency, and failure count where meaningful.
- Adaptive-only: first promotion actually applied to control, God-view offline
  retained-model torque-prediction RMSE, and remaining reference duration at
  first applied promotion.

The cylindrical surface-load proxy may be preserved as a secondary descriptive
diagnostic. It is a minimum-norm mathematical proxy—not pressure, comfort,
tissue load, injury risk, or a clinical safety outcome.

Every comparison table must show all four raw arms before sequential deltas.
Poor tracking, incomplete progress, safety termination, worse maximum error,
or non-promotion must remain visible and must not trigger automatic tuning.

## 10. Reusable visualization storyboard

The later renderer consumes saved traces; it must not rerun or change the
controller.

1. Use a 2 x 2 controller grid in the fixed order PD, PD+FF, fixed MPC,
   adaptive MPC.
2. Use one frozen oblique sagittal camera, identical model colors, 30 fps,
   wall-time axis, and playback speed for every panel.
3. Show the complete Human, robot, and cuff. Render the actual leg solid and
   the current reference leg as a translucent ghost.
4. Keep the overlay minimal: controller name, instantaneous combined tracking
   error, cuff-force norm, cuff-moment norm, and `N/A`, `PRIOR`, or `ACTIVE`.
   Flash a promotion marker only when a promotion is actually applied.
5. If an arm terminates early, hold its last valid frame and show the exact
   termination reason. Never loop, omit, or time-warp the failed arm.
6. Produce per scene: quick GIF; MP4 only if the existing rendering stack
   supports it without a new dependency; representative still PNG; and aligned
   timeseries PNG/PDF for the written report.

No final media is generated during preregistration.

## 11. Runtime and storage budget

Existing formal Stage-4 MPC arms at the frozen checkpoint took approximately
35.3–36.5 wall seconds for a 32 s allowance. Existing compressed traces are
about 8.9 MB per arm. On that evidence, the 33 unique rollouts are budgeted at:

- approximately 20–30 minutes serial control runtime, excluding environment
  startup and later rendering;
- approximately 0.35 GB for raw traces, JSON, summaries, and gain-lock data;
- approximately 0.45–0.60 GB total after three GIF/MP4/still/timeseries scene
  packages.

These are planning estimates, not runtime guarantees. The first authorized
structural smoke should record actual timing without changing the matrix.

## 12. Implemented wiring and formal commands reserved for the user

The report-validation runner and renderer are implemented. Formal execution
remains user-only. The next formal command, after structural validation, is:

```bash
cd stages/stage3_full3d

PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase gain-tuning \
  --output-dir results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd
```

Only after the resulting v2 gain lock is reviewed may the user separately run:

```bash
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase benchmark \
  --gain-lock results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd/frozen_pd_gains.json \
  --output-dir results/stage4_report_validation_baseline_formal

PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase demo \
  --gain-lock results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd/frozen_pd_gains.json \
  --output-dir results/stage4_report_validation_demo_only
```

The benchmark and demo commands are not authorized until a reviewed v2 gain
lock exists. Each phase must refuse to overwrite
an existing output directory and must record the config hash, code commit,
working-tree state, command, gain-lock hash, source-artifact hashes, summaries,
and per-arm traces.

## 13. Required checks before wiring is approved

- Prove that all four arms share the same exogenous phase samples, sensor
  realization, initial states, allocator, low-level gains, and safety limits.
- Prove that PD and PD+FF use the frozen gain-lock artifact and that no other
  gain source exists.
- Prove that fixed MPC keeps population-prior beta constant and adaptive MPC
  retains the existing promotion semantics.
- Prove that PD/PD+FF qualified sidecar estimates cannot enter their actions.
- Preserve exact command/action/wrench/robot-torque traces so the Human-space
  injection boundary is auditable.
- Keep gain-selection, benchmark, demo, and authoritative artifact roots
  disjoint.
- Verify the 9/16/8 run counts from the machine-readable matrix before any
  rollout begins.

## 14. Pre-wiring scientific concern

The comparison can isolate trusted **dynamic beta** adaptation only beyond the
geometry estimator shared by all four arms. It cannot be described as the
total benefit of all patient personalization. In addition, the common robot
Cartesian servo means PD is not an open-loop plant; it is the simplest added
Human-space feedback baseline on top of shared low-level robot feedback.

The hip-dominant trajectory keeps the knee near extension. Existing mechanics
show that transmission degrades toward exact extension, so wiring must retain
the force gate and report any early termination rather than weakening the task
or safety logic. No fixed clinical safety interpretation is attached to this
simulation gate.
