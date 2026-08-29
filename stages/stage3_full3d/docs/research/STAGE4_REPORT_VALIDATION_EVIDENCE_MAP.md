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
| D. Formal baseline evidence | [`stage4_report_validation_baseline_formal`](../../results/stage4_report_validation_baseline_formal) | 4 patients x PD/PD+FF/Fixed/Adaptive = 16 arms |
| E. Formal generalization evidence | [`statistical_formal_v1`](../../results/stage4_report_generalization_statistical_formal_v1), [`statistical_summary_v1`](../../results/stage4_report_generalization_statistical_summary_v1) | 4 patients x 3 controllers x 3 seeds = 36 arms and audited summaries |
| F. Demo-only scientific traces | [`trajectory_demo_v1`](../../results/stage4_report_generalization_trajectory_demo_v1) | six new Adaptive trajectory demonstrations; three high-flexion sources remain statistical traces |
| G. Final visualizations | [`stage4_professor_report_visualization_v1`](../../results/stage4_professor_report_visualization_v1) | five canonical professor-facing media sets |
| H. Negative/amendment evidence | [`gain_tuning_formal`](../../results/stage4_report_validation_gain_tuning_formal), [`gain_tuning_formal_v2_coupled_pd`](../../results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd) | immutable failed v1 selection, prospective diagnosis/amendment, formal v2 lock |
| I. Reproducible generated outputs | aggregate tables/report and [`visualization_source_manifest.json`](../../results/stage4_report_generalization_visualization_sources_v1/visualization_source_manifest.json) | deterministic audit and media-source inventories |
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

Every final directory contains `comparison.gif`, `representative_still.png`,
`end_summary_card.png`, `metrics_timeseries.png`, `metrics_timeseries.pdf`, and
`renderer_manifest.json`:

1. [`main_adaptation`](../../results/stage4_professor_report_visualization_v1/main_adaptation): Fixed versus Adaptive, moderate mixed, seed 64122;
2. [`patient_nominal`](../../results/stage4_professor_report_visualization_v1/patient_nominal): PD+FF, Fixed, Adaptive;
3. [`patient_geometry`](../../results/stage4_professor_report_visualization_v1/patient_geometry): the same controllers at +3% geometry;
4. [`patient_moderate_mixed`](../../results/stage4_professor_report_visualization_v1/patient_moderate_mixed): the same controllers under mixed mismatch;
5. [`trajectory_moderate_mixed`](../../results/stage4_professor_report_visualization_v1/trajectory_moderate_mixed): frozen Adaptive across three tasks.

## Canonical hashes

| artifact | SHA-256 |
|---|---|
| Frozen Stage-4 tag/commit | `stage4-robustness-final-v1` / `cc04765761d08ffaf1914f0236f0201d9c7e1475` |
| Failed v1 gain-selection status | `e78cc4b6e5ed9fa8641d8232410298ada2b9dff90ce3a06fcea739b5aa0ef61f` |
| Active v2 report-validation config | `46c6e9552a205d73bc8567a6ebf7af8e1887ef53b16c7e81703b0568cd3d635f` |
| Frozen v2 gain artifact / payload | `b83a8ca4c84484fad9f3687263cae6c5c038a25c2512b8e1e182bffe6b0ceea1` / `b21ddb1b53c1c6e535d22e9158834b4d57b3e7c32c7e52f46edc22231e793458` |
| Baseline phase manifest | `80da82ca67178e7a5509b756b02e1268465f916d6e276282f48e139fdd89931d` |
| Generalization matrix / metrics | `f424c435572738b62e4f04ca8a708497ebdd7a240bd04d159050dd069eb0f4ae` / `64c4421090b3aa1125b841ad6109f7b3160e5df881668d82eb6bcb46b75827ac` |
| Statistical phase / aggregate | `139a1343d69b013c4b293cac14a06fd5c7c4f215e35b2f6b4a149dfd7bc4fa4e` / `a85356dd2515256fa9badecd3d4286f13584b47b4a2e823ba1663c29e1fbaa92` |
| Trajectory-demo phase manifest | `34ee716c74a4273248f8c39ee0d8ead88aa582fbda06627262ef5de52a7b17eb` |
| Visualization source manifest | `8725f05e80256ac696eb1477ea4a055ca313356fe1f6369a173e1905420fd1ef` |
| Renderer manifests: main / nominal / geometry | `7bac6a150199306ccc1a0e1430cd8fad945307c51c57fec6f3e6604773167e6f` / `be871fb9705fc77fc2772318f8721d04694e0a680ba6457a92dba091c7edf188` / `ba60176d50a54b8e8468862c4ad0b2cd540c0425bc2f9715c83d335e9e03ef30` |
| Renderer manifests: mixed patient / three trajectories | `e0bbfcb9cafa03d3f3c6c3c673de2705fd8e7982e1463493e05bf82f9a422641` / `f436296504fac68c442c65fd6ccc99b211a951078c65b5eaabf9106907fb45ff` |

Renderer manifests also record the source-manifest hash, original trace paths
and hashes, patient/controller/trajectory/seed, renderer fingerprint,
generation timestamp, and output-file hashes.

## Limits and next phase

All results are simulation-only. The UR10e is a surrogate; desktop replay is
not hardware hard-realtime validation. Nothing establishes comfort, tissue
loading, clinical safety, efficacy, certification, or universal controller
superiority. The next engineering phase is robot-only hardware preparation and
commissioning-boundary validation. Separately preregistered model-inadequacy or
controller-limit studies remain optional scientific work.
