from __future__ import annotations

import json
from pathlib import Path

from scripts.run_stage4_patient_mismatch_robustness import _strict_json
from scripts.summarize_stage4_trajectory_excitation_generalization import (
    build_summary,
    write_report,
)


ROOT = Path(__file__).resolve().parents[1]


def test_completed_trajectory_suite_audit_and_negative_results(tmp_path: Path) -> None:
    summary = _strict_json(
        build_summary(
            trajectory_config=ROOT
            / "configs"
            / "stage4_trajectory_excitation_suite.json",
            patient_config=ROOT / "configs" / "stage4_patient_mismatch_cases.json",
            excitation_audit_path=ROOT
            / "results"
            / "stage4_trajectory_excitation_design_audit"
            / "audit.json",
            formal_result_dir=ROOT
            / "results"
            / "stage4_trajectory_excitation_generalization_formal",
            earlier_anchor_result_dir=ROOT
            / "results"
            / "stage4_single_challenger_closed_loop_ab_formal",
        )
    )
    assert summary["integrity"]["trajectory_count"] == 6
    assert summary["integrity"]["arm_count"] == 12
    assert summary["integrity"]["anchor_replication"][
        "exact_trace_sha256_match"
    ] is True
    assert summary["suite_summary"]["cases_with_any_control_promotion"] == 5
    assert summary["suite_summary"]["cases_with_shared_early_termination"] == 1
    assert summary["suite_summary"][
        "cases_with_any_recorded_safety_or_controller_event"
    ] == 1

    by_id = {item["trajectory_id"]: item for item in summary["cases"]}
    knee = by_id["knee_dominant_low_hip_23s"]
    assert knee["trust_and_identification"]["promotion_count"] == 0
    assert knee["completion"]["prior_only"]["termination_reason"] == (
        "total_commanded_cuff_force_gate"
    )
    assert knee["completion"]["prior_only"]["progress_fraction"] == knee[
        "completion"
    ]["trusted_adaptive"]["progress_fraction"]

    anchor = by_id["registered_high_flexion_23s"]
    two_cycle = by_id["two_cycle_moderate_23s"]
    assert two_cycle["offline_excitation"]["condition_z"] > 50.0 * anchor[
        "offline_excitation"
    ]["condition_z"]
    assert two_cycle["trust_and_identification"][
        "first_control_promotion_time_s"
    ] > anchor["trust_and_identification"]["first_control_promotion_time_s"]
    assert two_cycle["trust_and_identification"]["active_bound_pressure"][
        "maximum_active_bound_count"
    ] == 6

    json.dumps(summary, allow_nan=False)
    report = tmp_path / "report.md"
    write_report(report, summary)
    text = report.read_text(encoding="utf-8")
    assert "conditionally supported but limited" in text
    assert "shared controller/safety event" in text
    assert "All arms completed" not in text
