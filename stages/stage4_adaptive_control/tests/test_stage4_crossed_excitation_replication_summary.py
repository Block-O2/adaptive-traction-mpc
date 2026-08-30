from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results/robustness/crossed_replication/summary/aggregate_summary.json"
EXPECTED_SHA256 = "14f5ffb94a4d261eade3601f661d46effa910bbbc2c53e7834a27ff85888e922"


def test_canonical_crossed_summary_hash_and_matched_slices() -> None:
    assert hashlib.sha256(SUMMARY.read_bytes()).hexdigest() == EXPECTED_SHA256
    aggregate = json.loads(SUMMARY.read_text(encoding="utf-8"))
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
    assert integrity["matrix_config_sha256"] == (
        "00019282e188a1dca8d182b15ad9dd74d44c33312be5ad88f2f2c73efe1bbc81"
    )
    assert suite["cases_with_control_promotion"] == 18
    assert suite["cases_completed_both_arms"] == 18
    assert suite["tracking_rmse_improved_count"] == 18
    assert suite["prediction_rmse_improved_count"] == 18
    assert suite["rmse_improved_but_max_error_worsened_count"] == 2

    trajectory = relationships["matched_trajectory_slices"]
    assert trajectory["contrast_count"] == 9
    assert trajectory["poorer_later_count"] == 7
    assert trajectory["same_promotion_time_count"] == 2
    assert trajectory["poorer_earlier_count"] == 0
    patient = relationships["matched_patient_slices"]
    assert patient["contrast_count"] == 9
    assert patient["stronger_has_larger_tracking_benefit_count"] == 6
    assert patient["stronger_has_larger_prediction_benefit_count"] == 9
    seed = relationships["matched_seed_slices"]
    assert seed["contrast_count"] == 9
    assert seed["promotion_status_changed_count"] == 0
    assert seed["promotion_time_absolute_difference_s"]["maximum"] == pytest.approx(5.54)
    json.dumps(aggregate, allow_nan=False)
