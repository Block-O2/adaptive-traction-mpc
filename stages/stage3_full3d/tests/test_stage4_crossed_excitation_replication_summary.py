from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.summarize_stage4_crossed_excitation_replication import (
    build_aggregate,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]


def _aggregate() -> dict:
    return build_aggregate(
        matrix_config=ROOT
        / "configs"
        / "stage4_crossed_excitation_replication.json",
        patient_config=ROOT / "configs" / "stage4_patient_mismatch_cases.json",
        trajectory_config=ROOT
        / "configs"
        / "stage4_trajectory_excitation_suite.json",
        excitation_audit_path=ROOT
        / "results"
        / "stage4_trajectory_excitation_design_audit"
        / "audit.json",
        new_result_root=ROOT
        / "results"
        / "stage4_crossed_excitation_replication_formal",
    )


def test_completed_crossed_replication_integrity_and_matched_slices(
    tmp_path: Path,
) -> None:
    aggregate = _aggregate()
    integrity = aggregate["integrity"]
    suite = aggregate["suite_summary"]
    relationships = aggregate["relationships"]

    assert integrity["verdict"] == "mechanically_complete_and_internally_consistent"
    assert integrity["matrix_pair_count"] == 18
    assert integrity["arm_count"] == 36
    assert integrity["new_pair_count"] == 16
    assert integrity["reused_pair_count"] == 2
    assert integrity["reused_artifact_hashes_reverified"] is True
    assert integrity["all_pre_promotion_ab_isolation_checks_passed"] is True
    assert integrity["all_initial_states_and_estimator_trust_state_fresh"] is True
    assert integrity["matrix_config_sha256"] == (
        "00019282e188a1dca8d182b15ad9dd74d44c33312be5ad88f2f2c73efe1bbc81"
    )

    assert suite["cases_with_control_promotion"] == 18
    assert suite["cases_without_control_promotion"] == 0
    assert suite["cases_completed_both_arms"] == 18
    assert suite["cases_with_early_termination"] == 0
    assert suite["tracking_rmse_improved_count"] == 18
    assert suite["prediction_rmse_improved_count"] == 18
    assert suite["rmse_improved_but_max_error_worsened_count"] == 2

    trajectory = relationships["matched_trajectory_slices"]
    assert trajectory["contrast_count"] == 9
    assert trajectory["poorer_later_count"] == 7
    assert trajectory["same_promotion_time_count"] == 2
    assert trajectory["poorer_earlier_count"] == 0
    assert all(
        item["promotion_pattern"] == "poorer_later"
        for item in trajectory["anchor_vs_two_cycle"]
    )

    patient = relationships["matched_patient_slices"]
    assert patient["contrast_count"] == 9
    assert patient["stronger_has_larger_tracking_benefit_count"] == 6
    assert patient["stronger_has_larger_prediction_benefit_count"] == 9

    seed = relationships["matched_seed_slices"]
    assert seed["contrast_count"] == 9
    assert seed["promotion_status_changed_count"] == 0
    assert seed["promotion_time_absolute_difference_s"]["maximum"] == pytest.approx(
        5.54
    )
    assert relationships["benefit_sign_concordance_count"] == 18

    groups = aggregate["group_summaries"]["by_trajectory"]
    assert groups["two_cycle_moderate_23s"]["first_promotion_time_s"][
        "mean"
    ] > groups["registered_high_flexion_23s"]["first_promotion_time_s"]["mean"]

    json.dumps(aggregate, allow_nan=False)
    output_dir = tmp_path / "summary"
    write_outputs(aggregate, output_dir)
    assert {path.name for path in output_dir.iterdir()} == {
        "aggregate_summary.json",
        "main_comparison_table.md",
        "research_report.md",
    }
    json.loads((output_dir / "aggregate_summary.json").read_text(encoding="utf-8"))
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_outputs(aggregate, output_dir)
