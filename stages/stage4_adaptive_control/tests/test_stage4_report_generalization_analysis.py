from __future__ import annotations

import json
from pathlib import Path

import pytest

from traction_mpc_stage4.report_generalization_analysis import (
    audit_formal_generalization,
    generate_final_generalization_summary,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "configs/stage4_report_generalization_matrix.json"
FORMAL_ROOT = ROOT / "results/controller_validation/patient_generalization/study"
EXPECTED_OUTPUTS = {
    "aggregate_summary.json",
    "research_report.md",
    "main_absolute_metrics_table.md",
    "nominal_relative_degradation_table.md",
    "matched_controller_comparison_table.md",
    "tradeoff_audit.md",
}


def test_completed_formal_matrix_passes_final_integrity_audit() -> None:
    audit, records = audit_formal_generalization(
        matrix_path=MATRIX, formal_root=FORMAL_ROOT
    )
    assert audit["integrity_passed"] is True
    assert audit["arm_count"] == len(records) == 36
    assert audit["completion_count"] == 36
    assert audit["event_totals"] == {
        "force_gate_events": 0,
        "rom_event_samples": 0,
        "mpc_solver_failures": 0,
        "mujoco_warning_types": 0,
    }


def test_final_summary_is_strict_complete_and_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    left = generate_final_generalization_summary(
        matrix_path=MATRIX, formal_root=FORMAL_ROOT, output_dir=first
    )
    right = generate_final_generalization_summary(
        matrix_path=MATRIX, formal_root=FORMAL_ROOT, output_dir=second
    )
    assert {path.name for path in first.iterdir()} == EXPECTED_OUTPUTS
    assert {path.name for path in second.iterdir()} == EXPECTED_OUTPUTS
    assert json.loads((first / "aggregate_summary.json").read_text()) == left
    assert left == right
    assert len(left["arm_metrics"]) == 36
    assert len(left["cell_aggregates"]) == 12
    assert left["significance_tests_performed"] is False
    assert left["composite_generalization_score_created"] is False
    for name in EXPECTED_OUTPUTS:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_final_summary_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate_final_generalization_summary(
            matrix_path=MATRIX, formal_root=FORMAL_ROOT, output_dir=output
        )
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "preserve"
