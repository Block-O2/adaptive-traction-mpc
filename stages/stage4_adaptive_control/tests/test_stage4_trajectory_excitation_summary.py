from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results/robustness/trajectory_excitation/summary/aggregate_summary.json"
EXPECTED_SHA256 = "27f031ccba4099f387ee449669686e9b1148181eb4798b91fe610e2f7c44190b"


def test_canonical_trajectory_summary_hash_and_negative_result() -> None:
    assert hashlib.sha256(SUMMARY.read_bytes()).hexdigest() == EXPECTED_SHA256
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["integrity"]["trajectory_count"] == 6
    assert summary["integrity"]["arm_count"] == 12
    assert summary["integrity"]["anchor_replication"]["exact_trace_sha256_match"] is True
    assert summary["suite_summary"]["cases_with_any_control_promotion"] == 5
    assert summary["suite_summary"]["cases_with_shared_early_termination"] == 1
    assert summary["suite_summary"]["cases_with_any_recorded_safety_or_controller_event"] == 1

    by_id = {item["trajectory_id"]: item for item in summary["cases"]}
    knee = by_id["knee_dominant_low_hip_23s"]
    assert knee["trust_and_identification"]["promotion_count"] == 0
    assert knee["completion"]["prior_only"]["termination_reason"] == (
        "total_commanded_cuff_force_gate"
    )
    assert knee["completion"]["prior_only"]["progress_fraction"] == knee["completion"]["trusted_adaptive"]["progress_fraction"]
    anchor = by_id["registered_high_flexion_23s"]
    two_cycle = by_id["two_cycle_moderate_23s"]
    assert two_cycle["offline_excitation"]["condition_z"] > 50.0 * anchor["offline_excitation"]["condition_z"]
    assert two_cycle["trust_and_identification"]["first_control_promotion_time_s"] > anchor["trust_and_identification"]["first_control_promotion_time_s"]
    json.dumps(summary, allow_nan=False)
