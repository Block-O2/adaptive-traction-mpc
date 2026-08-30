# Stage-4 Professor-Report Generalization Study Spec

Status: **prospective demo-reuse amendment and infrastructure implementation;
no generalization formal rollout, trajectory-demo rollout, or final media
rendering has been executed**.

Frozen ancestry: `stage4-robustness-final-v1` at
`cc04765761d08ffaf1914f0236f0201d9c7e1475`.

Machine-readable contracts:

- [`configs/stage4_report_generalization_matrix.json`](../../configs/stage4_report_generalization_matrix.json)
- [`configs/stage4_report_generalization_metrics.json`](../../configs/stage4_report_generalization_metrics.json)

The v2 coupled-matrix PD lock remains frozen at
`results/controller_validation/gain_selection/frozen_pd_gains.json`
(artifact SHA-256
`b83a8ca4c84484fad9f3687263cae6c5c038a25c2512b8e1e182bffe6b0ceea1`).
No controller is retuned in this study.

### Prospective amendment before formal execution

The original design was frozen at matrix SHA-256
`66cf1757c083cfdc9fa1868e18cbc48b9fe9eb51c6971e8cea4b0adc10155e90`
and metric-definition SHA-256
`2795b23731832704f3e5414104d42afc4dfc5b4b8f4172b983c309dceb95606b`.
Before any formal generalization rollout, the demo policy is amended: demo
media is a rendering/use layer and may read an exact-match statistical trace
without re-executing dynamics. The source trace retains its original evidence
category; generated GIF/MP4/still/timeseries artifacts use
`professor_report_visualization` and record the source trace path and SHA-256.
Reuse requires exact patient, controller, trajectory, seed, external clock,
gain lock, controller/arm fingerprint, config, and runtime agreement.

The scientific 36-arm matrix is unchanged. D01-D12 now reuse the seed-44104
statistical arms. T01, T04, and T07 reuse the matching high-flexion Adaptive
statistical arms. Only T02, T03, T05, T06, T08, and T09 are new trajectory-demo
executions. The final unique execution count is therefore `36 + 6 = 42`.

The implementation audit also established that saved `control_time_s` and
`control_estimated_state` are 200 Hz, while the preregistered descriptor input
is 50 Hz. The prospective deterministic clarification is to select saved
indices `0,4,8,...` before applying the unchanged Savitzky-Golay parameters.
No metric, window, polynomial order, or derivative order is changed.

## 1. Question, claim boundary, and evidence boundary

The study asks whether one frozen controller, without patient-specific
retuning or a dedicated identification motion, maintains useful tracking and
constrained engineering interaction across patient dynamics, geometry, and
three preregistered measurement realizations. It also asks descriptively
whether trusted adaptation provides mismatch-dependent benefit over the same
fixed-model MPC.

This is a simulation generalization study, not a clinical efficacy, comfort,
tissue-safety, certification, or hardware-deployment study. Adaptive MPC is
not required to be best on every absolute metric. The primary question is
which controller maintains the most stable descriptive performance envelope
as mismatch increases. No composite generalization score is allowed.

Evidence categories remain explicit and non-interchangeable:

1. frozen Stage-4 authoritative historical evidence;
2. completed report-validation baseline evidence;
3. new report-generalization statistical evidence;
4. patient-visualization demo-only evidence;
5. trajectory-generalization demo-only evidence.

Historical and baseline artifacts are read-only. Demo results may illustrate
mechanisms but cannot be merged into the 36-run statistical dataset or old
Stage-4 evidence.

## 2. Frozen shared execution contract

Every main-study arm uses `registered_high_flexion_23s`, a 32 s rollout limit,
the frozen exogenous reference-phase replay, `noise_bias_drift_200hz`, the
existing causal sensor boundary and state/geometry estimator, the existing
11-base identifier and trust lifecycle, the same MuJoCo robot/Human plant,
rigid cuff, virtual-work wrench reconstruction, 1:1 memoryless cuff allocator,
measured Cartesian low level, actuator limits, force/ROM/contact gates, and
termination semantics.

All matched arms start from Human posture `[5 deg, 10 deg]` and the same
deterministic patient-specific robot IK reset. Controller state, estimator
state, plant state, and external clock are fresh for every arm. No controller
may alter the reference clock, trajectory, patient, sensor realization, or
initial-state convention. There is no controller-specific trajectory tuning,
patient-specific gain tuning, or identification probe.

The three controllers are:

| ID | report label | frozen distinction |
|---|---|---|
| `pd_nominal_inverse_dynamics_ff` | PD+FF | frozen v2 coupled torque PD plus population-prior inverse-dynamics feedforward |
| `fixed_mpc_prior_only` | Fixed MPC | frozen MPC with population-prior beta throughout |
| `trusted_adaptive_mpc` | Trusted Adaptive MPC | identical MPC using the prior until the existing trust rule promotes a retained incumbent |

Pure PD is deliberately absent from the main matrix. Its already completed
baseline table remains a lower-level reference.

## 3. Patients and prospective rationale

| role | exact patient | mismatch mechanism |
|---|---|---|
| P1 | `nominal_reference` | no mismatch |
| P2 | `mass_mild_plus_05pct` | isolated +5% total mass; all other patient scales unchanged |
| P3 | `height_moderate_plus_03pct_report_only` | isolated +3% height and both segment lengths; mass, COM fractions, passive terms, rest angles, and dimensionless sleeve location unchanged |
| P4 | `registered_moderate_anchor` | mixed +5% mass, altered thigh/shank COM, +10% passive stiffness, `[-2,-2] deg` rest offsets, and +2% sleeve-center scale |

P3 is defined only in the report-generalization contract. It must not be added
to or promoted into historical Stage-4 patient evidence. P4 is selected instead
of `registered_formal_perturbed_anchor` because P4 supplies a mixed dynamics,
equilibrium, and cuff-location contrast without also changing overall height.
This is more complementary to the isolated geometry P3 and avoids making both
non-nominal high-mismatch cases primarily height-changing cases.

These are engineering robustness variations, not clinical population ranges.

## 4. Measurement seeds and exact 36-run matrix

Seeds are exactly `44104`, `54113`, and `64122`: the first three entries of the
existing Stage-4 preregistered sequence. They are fixed before any new
generalization result and were not selected from report-validation outcomes.

Every row below expands to PD+FF, Fixed MPC, and Trusted Adaptive MPC:

| patient | seed 44104 | seed 54113 | seed 64122 | arms |
|---|---:|---:|---:|---:|
| `nominal_reference` | G01-G03 | G04-G06 | G07-G09 | 9 |
| `mass_mild_plus_05pct` | G10-G12 | G13-G15 | G16-G18 | 9 |
| `height_moderate_plus_03pct_report_only` | G19-G21 | G22-G24 | G25-G27 | 9 |
| `registered_moderate_anchor` | G28-G30 | G31-G33 | G34-G36 | 9 |
| total | 12 | 12 | 12 | 36 |

The machine contract enumerates every arm rather than relying only on an
implicit Cartesian product.

## 5. Primary metric definitions

### 5.1 Task performance

- combined tracking RMSE in degrees;
- maximum absolute tracking error across time and both joints in degrees;
- mechanical completion, termination reason, and reference progress.

Incomplete arms retain all data. Metrics are computed over realized samples,
and completion/progress is always shown; an incomplete arm is never silently
discarded.

### 5.2 Motion-quality proxies

The source is the existing causal Human joint-velocity estimate saved at 200 Hz
as `control_estimated_state[:,2:4]`. The frozen 50 Hz metric series is
`control_estimated_state[0::4,2:4]` with `control_time_s[0::4]`.
One offline method is frozen for all arms:

```text
scipy.signal.savgol_filter
window_length = 11 samples = 0.22 s
polyorder = 3
mode = "interp"
delta = 0.02 s
acceleration: deriv = 1 applied to estimated velocity
jerk:         deriv = 2 applied to estimated velocity
```

No controller-specific filtering or smoothing is permitted. The operation is
offline evaluation and is not fed back into any controller. Report hip and
knee acceleration RMS/peak in `rad/s^2`, hip and knee jerk RMS/peak in
`rad/s^3`, plus combined vector RMS for degradation comparisons. These are
motion-smoothness proxies only—not comfort or clinical safety.

### 5.3 Interaction and constraints

Report cuff translational-force norm RMS, peak, and linearly interpolated 95th
percentile; minimum force-gate margin `200 N - peak force`; cuff-moment norm RMS
and peak; six-joint robot torque RMS and peak vectors plus their global
summaries; all safety/constraint events; termination reason; and solver or
MuJoCo warnings.

The reconstructed physical cuff wrench is available only to offline simulated
plant evaluation. It is not clean state fed to the controller. Cuff moment and
force are engineering interaction quantities. The cylindrical surface proxy
is not pressure, tissue loading, comfort, or safety and is not a primary
metric. Cuff force rate is prospectively excluded because it is optional,
noise-sensitive, and unnecessary for the primary claim.

For Adaptive MPC also report promotion count, first promotion time, remaining
reference time and fraction at first promotion, and the saved combined
god-view torque-prediction RMSE when finite. Prediction RMSE must be explicitly
labelled offline God-view evaluation and never runtime controller information.

## 6. Generalization and matched comparisons

For every scalar error/load metric `E`, controller `c`, mismatch patient `p`,
and seed `s`:

```text
Delta_E(p,c,s) = E(p,c,s) - E(nominal_reference,c,s)
```

Positive delta means degradation for error/load metrics. At minimum this is
reported for tracking RMSE, maximum tracking error, combined acceleration RMS,
combined jerk RMS, cuff-force peak, and cuff-force RMS. Relative degradation
is `Delta_E / E_nominal` only when the matched nominal value is finite and its
absolute magnitude is at least `1e-12` in the declared unit; otherwise it is
reported as undefined. Absolute delta remains primary.

Each patient x controller cell reports arithmetic mean, sample standard
deviation (`ddof=1`), minimum, and maximum over the three seeds. Since `n=3`,
all summaries are descriptive: no significance test, confidence claim, or
population-level inference is authorized.

Matched same-seed tables report PD+FF versus Fixed MPC, Fixed MPC versus
Adaptive MPC, and
`E_fixed - E_adaptive` for error/load metrics so a positive value denotes a
lower Adaptive value. The report must state whether the observed adaptation
benefit grows, shrinks, or varies inconsistently with mismatch; it must not
require a monotonic or universal benefit.

## 7. Reuse audit and evidence semantics

The completed baseline has nine apparent numerical matches before considering
evidence semantics: seed 44104 for P1, P2, and P4 across the three controllers.
However, those source arms are explicitly `report_validation_scientific_baseline`,
whereas this target is a separately preregistered
`report_generalization_statistical` study. Because the requested reuse rule
requires evidence semantics as well as controller, patient, trajectory, seed,
clock, gain lock, fingerprints, hashes, and runtime to match, zero old arms are
classified reusable and all 36 statistical arms are new. This baseline-to-new-
study decision is unchanged by the visualization amendment.

This repeats nine deterministic configurations only because the evidence
contract explicitly requires a distinct category; it does not overwrite or
relabel the baseline artifacts. If the user later authorizes a cross-category
read-only bridge, that would require a prospective amendment before execution.

## 8. Demo-only matrices

### 8.1 Patient visualization

At fixed seed 44104 and `registered_high_flexion_23s`, retain PD+FF, Fixed MPC,
and Adaptive MPC for each P1-P4 patient: D01-D12. These are twelve read-only
references to exact statistical-study traces and require zero extra rollouts.

Planned scenes:

1. nominal: show that Adaptive does not unnecessarily promote when the prior
   remains adequate;
2. isolated geometry: show the longer patient anatomy with unchanged frozen
   controllers;
3. mixed mismatch: primary synchronized Fixed-versus-Adaptive comparison with
   the `PRIOR -> ADAPTIVE` transition;
4. isolated mass: optional short scene if it adds a visually clear contrast.

The statistical traces remain statistical evidence. Only the derived media is
`professor_report_visualization`; its provenance stores source paths and hashes.

### 8.2 Trajectory generalization

Use only frozen Trusted Adaptive MPC, seed 44104, patients P1, P3, and P4, and
all nine combinations of:

- `registered_high_flexion_23s`;
- `moderate_rom_23s`;
- `hip_dominant_low_knee_23s`.

These are T01-T09 in the machine contract. T01, T04, and T07 reuse exact
high-flexion Adaptive statistical traces. Only the six moderate-ROM and
hip-dominant arms are new executions. The purpose is the descriptive
statement “one frozen adaptive controller, different patients, different
rehabilitation tasks.” This is not a trajectory factorial statistical study.
New trajectory rollouts retain the trajectory-demo category, while reused
statistical traces retain their statistical category. Derived media alone uses
the visualization category.

## 9. Visualization storyboard

Matched videos use identical camera, playback speed, crop, colors, and time
axis. A split screen is preferred for Fixed-versus-Adaptive comparisons. The
overlay contains only:

- controller, patient, and trajectory;
- instantaneous tracking-error magnitude;
- cuff-force magnitude and cuff-moment magnitude;
- combined estimated acceleration magnitude as the single smoothness proxy;
- `PRIOR` or `ADAPTIVE` state;
- a promotion marker and timestamp when applicable.

The end card contains tracking RMSE, maximum tracking error, peak cuff force,
acceleration RMS or peak, and safety-event count. Do not overload the live
overlay with every metric. Required deliverables per principal scene are GIF,
still PNG, and a PDF-ready time-series figure; MP4 is added only if its encoder
dependency can be enabled cleanly. No media is rendered under this spec yet.

## 10. Cost and storage estimate

The amended reuse policy produces 36 new statistical and 6 new trajectory-demo
rollouts: 42 unique executions. At 32 simulated seconds each, the main
study is 1,152 simulated seconds (19.2 simulated minutes), and all planned
rollouts total 1,344 simulated seconds (22.4 simulated minutes).

Using completed baseline wall times, sequential execution is estimated at
about 17.2 minutes for the main study and about 20.6 minutes for all 42 arms;
plan 18-30 minutes to allow initialization and filesystem variation. Existing
traces average approximately 8.45 MiB per arm, giving about 305 MiB for the
main study and 355 MiB for all traces/JSON. Final GIF/MP4/still/time-series
media is budgeted at 200-500 MiB, giving a combined planning range of
approximately 555-855 MiB.

These are planning estimates, not execution results.

## 11. Stopping rules and concerns before implementation

No formal or demo run may start from this design-only state. Before execution:

1. the user approves this preregistration;
2. the implemented runner resolver for inline report-only P3 is validated
   without modifying the historical patient config;
3. new output roots are absent and overwrite protection is active;
4. new config and controller fingerprints are frozen;
5. metric extraction is tested against synthetic arrays only.

If any arm terminates or produces poor metrics, preserve it and report the
observation. Do not retune controllers, select seeds again, weaken gates,
change filtering, or replace the patient. A formal result is reviewed as
observed evidence; this spec does not predeclare a scientific PASS/FAIL label.
