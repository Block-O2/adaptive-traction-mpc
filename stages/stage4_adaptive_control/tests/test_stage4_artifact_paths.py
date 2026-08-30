from pathlib import Path

from traction_mpc_stage4.artifact_paths import (
    canonical_artifact_relative_path,
    resolve_stage_artifact,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_result_paths_resolve_to_semantic_stage4_locations() -> None:
    cases = {
        "results/stage4_single_challenger_closed_loop_ab_formal/prior_only_trace.npz": (
            "results/robustness/adaptive_ab/prior_only_trace.npz"
        ),
        "results/stage4_report_validation_gain_tuning_formal/gain_selection_status.json": (
            "results/negative_evidence/pd_gain_selection_v1/gain_selection_status.json"
        ),
        "results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd/frozen_pd_gains.json": (
            "results/controller_validation/gain_selection/frozen_pd_gains.json"
        ),
        "results/stage4_report_generalization_statistical_formal_v1/phase_manifest.json": (
            "results/controller_validation/patient_generalization/study/phase_manifest.json"
        ),
        "results/stage4_trajectory_excitation_design_audit/audit.json": (
            "results/robustness/trajectory_excitation/design_audit.json"
        ),
        "results/stage4_patient_mismatch_robustness_formal/registered_formal_perturbed_anchor/prior_only_trace.npz": (
            "results/robustness/adaptive_ab/prior_only_trace.npz"
        ),
    }
    for old, new in cases.items():
        assert canonical_artifact_relative_path(old) == Path(new)
        assert resolve_stage_artifact(STAGE_ROOT, old) == (STAGE_ROOT / new).resolve()


def test_current_paths_and_absolute_paths_are_stable(tmp_path: Path) -> None:
    current = Path("results/robustness/adaptive_ab/comparison_summary.json")
    assert canonical_artifact_relative_path(current) == current
    absolute = tmp_path / "artifact.json"
    assert resolve_stage_artifact(STAGE_ROOT, absolute) == absolute.resolve()
