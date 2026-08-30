# Stage-4 Report-Validation Evidence Map

Status: **closed professor-report simulation evidence package**. This package
starts from the immutable `stage4-robustness-final-v1` tag at
`cc04765761d08ffaf1914f0236f0201d9c7e1475`; it does not modify or relabel that
historical Stage-4 checkpoint.

## Evidence classification and retained inventory

| class | retained material | role |
|---|---|---|
| A. Canonical implementation | `src/traction_mpc_stage4/report_validation*.py`, `report_generalization*.py`; matching scripts | frozen execution, audit, source-manifest and trace-only rendering paths |
| B. Canonical configs/specs | `configs/stage4_report_validation_matrix*.json`, `stage4_report_generalization_*.json`; report-validation/generalization specs | machine and human preregistration contracts |
| C. Essential tests | `tests/test_stage4_report_validation*.py`, `test_stage4_report_generalization*.py`, `test_stage4_report_manifest_renderer.py` | action-path, config, evidence, audit and renderer regressions |
| D. Formal baseline evidence | [`stage4_report_validation_baseline_formal`](../../results/controller_validation/baseline_comparison) | 4 patients x PD/PD+FF/Fixed/Adaptive = 16 arms |
| E. Formal generalization evidence | [`statistical_formal_v1`](../../results/controller_validation/patient_generalization/study), [`statistical_summary_v1`](../../results/controller_validation/patient_generalization/summary) | 4 patients x 3 controllers x 3 seeds = 36 arms and audited summaries |
| F. Demo-only scientific traces | [`trajectory_demo_v1`](../../results/controller_validation/trajectory_generalization/demo_sources) | six new Adaptive trajectory demonstrations; three high-flexion sources remain statistical traces |
| G. Final visualizations | [`professor_video_manifest.json`](../../results/summaries/professor_video_manifest.json) | provenance for three accepted external professor-delivery MuJoCo MP4s; renderer and README media remain tracked |
| H. Negative/amendment evidence | [`gain_tuning_formal`](../../results/negative_evidence/pd_gain_selection_v1), [`gain_tuning_formal_v2_coupled_pd`](../../results/controller_validation/gain_selection) | immutable failed v1 selection, prospective diagnosis/amendment, formal v2 lock |
| I. Reproducible generated outputs | aggregate tables/report and [`visualization_source_manifest.json`](../../results/controller_validation/visualization_sources/visualization_source_manifest.json) | deterministic audit and media-source inventories |
| J. Smoke/debug/temp | removed structural-generalization and renderer-smoke roots | reproducible, non-scientific, superseded artifacts |
| K. Uncertain | none removed | preservation was preferred whenever scientific or audit value was plausible |

## PD baseline development: v1 to v2

The v1 nine-candidate tuning was formally executed first. All nine diagonal
torque-PD candidates crossed the unchanged cuff-force gates, so no v1 lock was
created. Diagnosis found no wiring, unit, sign, reference, allocator, geometry,
or initialization bug. The scientific construction had dropped the hip-knee
cross terms when converting the Stage-3
`M(q) [Kp_a e_q + Kd_a e_dq]` feedback into constant torque gains.

The prospective v2 amendment retained the complete nominal-inertia-derived
coupled matrices at the fixed nominal initial configuration, without evaluating
`M(q)` online. Formal v2 selection kept the same 3 x 3 scale grid and chose
`kp_1.5__kd_0.5`. PD and PD+FF share that lock; PD+FF alone adds population-prior
reference inverse dynamics. This is an amendment chain, not rewritten history.

## Baseline and patient generalization

The formal 16-arm baseline makes the controller ladder visible. Pure PD is a
weak tracking baseline. PD+FF supplies the strongest absolute tracking baseline
in the later generalization cells, while Fixed MPC consistently reduces the
offline acceleration/jerk descriptors. Across the audited 36-arm study,
Adaptive improves or matches Fixed tracking in all matched patient/seed cells,
with the clearest mean benefit for the moderate mixed patient. Adaptive is not
claimed to dominate every metric or PD+FF on absolute tracking.

The generalization matrix uses four simulated patients, three frozen
controllers, and three preregistered seeds, with no patient-specific retuning.
All 36 arms completed, reached full reference progress, and recorded no force,
ROM, contact, solver, or MuJoCo-warning event. The evidence supports a useful
no-retuning performance envelope within the tested simulation family; the
comprehensive superiority claim is only conditionally supported and `n=3` is
descriptive.

## Motion, interaction, and adaptation semantics

The MPC controllers have a consistent acceleration/jerk advantage over PD+FF.
These are deterministic offline smoothness descriptors from the frozen 50 Hz
Savitzky-Golay convention, not comfort or clinical-safety measurements.

Force margins remain positive and recorded constraint-event counts are zero.
Interaction changes are mixed: Adaptive can slightly increase cuff force or
robot effort while improving tracking, so no load-reduction claim is made.
Cuff quantities are engineering interaction measures; the surface proxy is not
pressure or tissue loading.

The retained beta is a trust-gated **control-effective model**, not recovered
physical anatomy. Nominal runs can promote because identification/trust may
compensate sensing or model nuisance. Promotion means the retained model passed
the frozen causal qualification rule, not that patient parameters were found.

## Trajectory generalization and final media

The trajectory package uses the same frozen Adaptive MPC, seed `44104`, for
high-flexion, moderate-ROM, and hip-dominant tasks. Six new demo traces combine
through read-only provenance with three matching high-flexion statistical
traces. The source manifest stores original paths, hashes, fingerprints,
categories, and promotion data without copying traces.

The rejected schematic media were removed. The accepted full MP4 delivery is
stored externally with the professor report and is intentionally not tracked
by Git. Its retained provenance manifest records:

1. `01_Fixed_vs_Adaptive.mp4`: synchronized Fixed versus Adaptive, moderate mixed, seed 64122;
2. `02_Patient_Generalization.mp4`: PD+FF, Fixed, and Adaptive across selected patients;
3. `03_Trajectory_Generalization.mp4`: frozen Adaptive across three tasks.

All three are genuine MuJoCo 3D trace replays. The renderer performs no
controller rollout, state interpolation, or schematic fallback.

## Canonical hashes

| artifact | SHA-256 |
|---|---|
| Frozen Stage-4 tag/commit | `stage4-robustness-final-v1` / `cc04765761d08ffaf1914f0236f0201d9c7e1475` |
| Failed v1 gain-selection status | `e78cc4b6e5ed9fa8641d8232410298ada2b9dff90ce3a06fcea739b5aa0ef61f` |
| Active v2 report-validation config | `46c6e9552a205d73bc8567a6ebf7af8e1887ef53b16c7e81703b0568cd3d635f` |
| Frozen v2 gain artifact / payload | `b83a8ca4c84484fad9f3687263cae6c5c038a25c2512b8e1e182bffe6b0ceea1` / `b21ddb1b53c1c6e535d22e9158834b4d57b3e7c32c7e52f46edc22231e793458` |
| Baseline phase manifest, path-normalized | `f32c659b04981170237eb25dc060bc1232f3f6e705846c83eab66b88c76422cc` |
| Generalization matrix / metrics | `f424c435572738b62e4f04ca8a708497ebdd7a240bd04d159050dd069eb0f4ae` / `64c4421090b3aa1125b841ad6109f7b3160e5df881668d82eb6bcb46b75827ac` |
| Statistical phase / aggregate, path-normalized | `4dfb13ee870bb802e76e762e77fb0e083fe952b91f5aa9be02cbec48dea4df08` / `c6649ea25c667600e2f11b14ae1a880426423686a8c9838aabebea6d58b06644` |
| Trajectory-demo phase manifest, path-normalized | `328190fd1b895ba8da8a2ca69380bf08db7dd273290df938346f810a5728d8d2` |
| Visualization source manifest, path-normalized | `d9a7bd04d54c65001094b14baf8d5581d8d330e61fda8387036c3ed2972ed2d4` |
| Real MP4: Fixed/Adaptive | `cd7cba26a03d2dd8851598916bcaa4e0db6901e6d9e03427f57cd734723fc6b0` |
| Real MP4: patient / trajectory | `1b9f9e3f14ac29d5c522b9e830c822d0e28686abb593fa5e467df77196953b0e` / `2845ce8115634e3f60cf458ff4a11326f843f11d9585c95625782df904c623c7` |

The old and new hashes for every metadata-only path rewrite are recorded in
[`STAGE4_REPOSITORY_MIGRATION.json`](../STAGE4_REPOSITORY_MIGRATION.json).

## Limits and next phase

All results are simulation-only. The UR10e is a surrogate; desktop replay is
not hardware hard-realtime validation. Nothing establishes comfort, tissue
loading, clinical safety, efficacy, certification, or universal controller
superiority. The next engineering phase is robot-only hardware preparation and
commissioning-boundary validation. Separately preregistered model-inadequacy or
controller-limit studies remain optional scientific work.
