"""Resolve frozen Stage-4 artifact paths after repository reorganization.

Scientific configuration files retain their byte-exact preregistered path
strings and hashes. This module maps only their storage locations into the
semantic Stage-4 hierarchy; no scientific or runtime parameter is changed.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


# Longest prefixes are matched first. Keep synchronized with the migration
# manifest in ``docs/STAGE4_REPOSITORY_MIGRATION.json``.
LEGACY_ARTIFACT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd", "results/controller_validation/gain_selection"),
    ("results/stage4_report_generalization_statistical_summary_v1", "results/controller_validation/patient_generalization/summary"),
    ("results/stage4_report_generalization_statistical_formal_v1", "results/controller_validation/patient_generalization/study"),
    ("results/stage4_report_generalization_trajectory_demo_v1", "results/controller_validation/trajectory_generalization/demo_sources"),
    ("results/stage4_report_generalization_visualization_sources_v1", "results/controller_validation/visualization_sources"),
    ("results/stage4_trajectory_excitation_generalization_summary", "results/robustness/trajectory_excitation/summary"),
    ("results/stage4_trajectory_excitation_generalization_formal", "results/robustness/trajectory_excitation/formal"),
    ("results/stage4_crossed_excitation_replication_summary_final", "results/robustness/crossed_replication/summary"),
    ("results/stage4_crossed_excitation_replication_formal", "results/robustness/crossed_replication/formal"),
    ("results/stage4_nominal_sensor_decomposition_formal", "results/robustness/sensor_robustness/nominal_decomposition"),
    ("results/stage4_nominal_sensor_multiseed_formal", "results/robustness/sensor_robustness/nominal_multiseed"),
    ("results/stage4_patient_mismatch_robustness_formal", "results/robustness/patient_mismatch"),
    ("results/stage4_single_challenger_closed_loop_ab_formal", "results/robustness/adaptive_ab"),
    ("results/stage4_realtime_implementation_sprint_20260828", "results/robustness/realtime_replay"),
    ("results/stage4_report_validation_gain_tuning_formal", "results/negative_evidence/pd_gain_selection_v1"),
    ("results/stage4_report_validation_baseline_formal", "results/controller_validation/baseline_comparison"),
    ("results/stage4_report_validation_demo_only", "results/controller_validation/trajectory_generalization/demo_sources"),
    ("results/stage4_report_validation_visualization", "results/media/professor_visualizations"),
    ("results/stage4_professor_report_visualization_v1", "results/media/professor_visualizations"),
)


def canonical_artifact_relative_path(path: str | Path) -> Path:
    """Map a frozen Stage-4 relative artifact path to its current location."""

    source = PurePosixPath(Path(path).as_posix()).as_posix().rstrip("/")
    if source == (
        "results/stage4_patient_mismatch_robustness_formal/"
        "registered_formal_perturbed_anchor/prior_only_trace.npz"
    ):
        # Byte-identical to the registered adaptive A/B prior arm; retain one
        # canonical copy while preserving the frozen source hash.
        return Path("results/robustness/adaptive_ab/prior_only_trace.npz")
    if source == "results/stage4_trajectory_excitation_design_audit/audit.json":
        return Path("results/robustness/trajectory_excitation/design_audit.json")
    for old_prefix, new_prefix in LEGACY_ARTIFACT_PREFIXES:
        if source == old_prefix:
            return Path(new_prefix)
        if source.startswith(f"{old_prefix}/"):
            return Path(new_prefix + source[len(old_prefix) :])
    return Path(source)


def resolve_stage_artifact(stage_root: Path, path: str | Path) -> Path:
    """Resolve an absolute path directly or a migrated path under Stage 4."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(stage_root) / canonical_artifact_relative_path(candidate)).resolve()


def resolve_manifest_artifact(stage_root: Path, path: str | Path) -> Path:
    """Resolve stage-relative or repository-relative paths stored in manifests."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.parts and candidate.parts[0] == "stages":
        repo_root = Path(stage_root).resolve().parents[1]
        return (repo_root / candidate).resolve()
    return resolve_stage_artifact(stage_root, candidate)
