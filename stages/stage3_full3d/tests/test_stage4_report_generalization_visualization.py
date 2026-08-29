from __future__ import annotations

import json
from pathlib import Path

import pytest

from traction_mpc_stage4.report_generalization_visualization import (
    audit_trajectory_demo,
    build_visualization_source_manifest,
)
from traction_mpc_stage4.report_validation_renderer import load_comparison_case


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "configs/stage4_report_generalization_matrix.json"
STATISTICAL = ROOT / "results/stage4_report_generalization_statistical_formal_v1"
DEMO = ROOT / "results/stage4_report_generalization_trajectory_demo_v1"


def test_six_new_demo_runs_pass_integrity_audit() -> None:
    audit, records = audit_trajectory_demo(matrix_path=MATRIX, demo_root=DEMO)
    assert audit["integrity_passed"] is True
    assert audit["arm_count"] == len(records) == 6
    assert audit["actual_artifact_file_count"] == 25
    assert all(item["metrics"]["completion"] for item in records)
    assert all(not any(item["events"].values()) for item in records)


def test_visualization_manifest_is_read_only_complete_and_deterministic(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    left = build_visualization_source_manifest(
        matrix_path=MATRIX,
        statistical_root=STATISTICAL,
        demo_root=DEMO,
        output_dir=first,
    )
    right = build_visualization_source_manifest(
        matrix_path=MATRIX,
        statistical_root=STATISTICAL,
        demo_root=DEMO,
        output_dir=second,
    )
    assert left == right
    assert (first / "visualization_source_manifest.json").read_bytes() == (
        second / "visualization_source_manifest.json"
    ).read_bytes()
    assert json.loads(
        (first / "visualization_source_manifest.json").read_text()
    ) == left
    dataset = left["trajectory_generalization_dataset"]
    assert len(dataset["items"]) == dataset["case_count"] == 9
    assert sum(
        item["source_evidence_category"] == "report_generalization_statistical"
        for item in dataset["items"]
    ) == 3
    assert sum(
        item["source_evidence_category"] == "report_trajectory_demo_only"
        for item in dataset["items"]
    ) == 6
    assert left["source_traces_copied"] is False
    assert all(
        item["intended_media_evidence_category"]
        == "professor_report_visualization"
        for item in dataset["items"]
    )


def test_existing_renderer_accepts_main_and_patient_same_case_sets() -> None:
    mixed = STATISTICAL / (
        "registered_moderate_anchor__registered_high_flexion_23s__seed64122"
    )
    main = load_comparison_case(
        mixed,
        controller_order=("fixed_mpc_prior_only", "trusted_adaptive_mpc"),
    )
    assert len(main["arms"]) == 2
    for patient in (
        "nominal_reference",
        "height_moderate_plus_03pct_report_only",
        "registered_moderate_anchor",
    ):
        case = STATISTICAL / f"{patient}__registered_high_flexion_23s__seed44104"
        loaded = load_comparison_case(
            case,
            controller_order=(
                "pd_nominal_inverse_dynamics_ff",
                "fixed_mpc_prior_only",
                "trusted_adaptive_mpc",
            ),
        )
        assert len(loaded["arms"]) == 3


def test_visualization_manifest_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_visualization_source_manifest(
            matrix_path=MATRIX,
            statistical_root=STATISTICAL,
            demo_root=DEMO,
            output_dir=output,
        )
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "preserve"
