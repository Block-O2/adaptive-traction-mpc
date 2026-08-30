# Stage-4 evidence index

This directory is the compact entry point; detailed artifacts remain grouped
by scientific meaning.

- [Adaptive A/B](../robustness/adaptive_ab/comparison_summary.md)
- [Patient mismatch aggregate](../robustness/patient_mismatch/aggregate_summary.json)
- [Sensor robustness](../robustness/sensor_robustness/nominal_multiseed/research_report.md)
- [Trajectory excitation](../robustness/trajectory_excitation/summary/aggregate_summary.json)
- [Crossed replication](../robustness/crossed_replication/summary/research_report.md)
- [Controller baseline](../controller_validation/baseline_comparison/phase_manifest.json)
- [Patient generalization report](../controller_validation/patient_generalization/summary/research_report.md)
- [Failed PD-v1 gain selection](../negative_evidence/pd_gain_selection_v1/gain_selection_status.json)
- [External professor-video provenance](professor_video_manifest.json)

The full professor-delivery MP4s are intentionally stored outside Git. The
repository retains the real MuJoCo renderer, frozen source traces, provenance
manifest, and compact README media required to regenerate or inspect them.

Claim boundaries, hashes, and reproduction rules are maintained in the
[robustness evidence map](../../docs/research/STAGE4_EVIDENCE_MAP.md),
[report-validation evidence map](../../docs/research/STAGE4_REPORT_VALIDATION_EVIDENCE_MAP.md),
and [migration record](../../docs/STAGE4_REPOSITORY_MIGRATION.md).
