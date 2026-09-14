from __future__ import annotations

import json

from traction_mpc_stage5.validation import run_stage5_validation


def test_stage5_engineering_validation_is_complete_and_labeled_smoke(tmp_path) -> None:
    report = run_stage5_validation(tmp_path)
    assert report["evidence_category"] == "smoke_engineering_validation_only"
    assert report["summary"]["all_representative_postures_reachable"]
    assert report["summary"]["all_timestep_probes_finite"]
    assert report["reachability_and_clearance"]["minimum_robot_arm_to_human_clearance_m"] > 0.0
    assert report["reachability_and_clearance"]["minimum_articulated_arm_to_bed_clearance_m"] > 0.0
    assert report["reachability_and_clearance"]["robot_self_contact_pairs"] == []
    assert report["summary"]["stage4_evidence_modified"] is False
    assert report["summary"]["learning_or_rl_implemented"] is False
    assert (tmp_path / "top_view_stage5_geometry.png").stat().st_size > 10_000
    assert (tmp_path / "inverted_t_cuff_closeup.png").stat().st_size > 10_000
    saved = json.loads((tmp_path / "validation_report.json").read_text())
    assert saved["geometry"]["bar_stem_dot_product"] == 0.0
