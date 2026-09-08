from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


STAGE = Path(__file__).resolve().parents[1]
SUMMARY = STAGE / "results/summaries/phase3a_corrected_high_rom"
SOURCES = SUMMARY / "report_sources"
SCRIPTS = STAGE / "scripts"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_report_sources_match_manifest_and_schema() -> None:
    manifest = json.loads((SOURCES / "manifest.json").read_text())
    assert manifest["scientific_settings_changed"] is False
    assert manifest["new_trajectory_runs"] == 0
    assert len(manifest["cases"]) == 6
    required = {
        "video_time_s",
        "video_human_q_deg",
        "video_human_q_ref_deg",
        "video_reference_phase_time_s",
        "video_command_force_n",
        "video_robot_q_rad",
        "video_physical_force_n",
        "video_deformation_H",
        "video_mode",
        "video_safety_filter_status",
        "tracking_time_s",
        "tracking_q_deg",
        "tracking_ref_deg",
        "force_overlay_q_deg",
        "force_overlay_force_n",
    }
    for item in manifest["cases"].values():
        path = SOURCES / item["file"]
        assert sha256(path) == item["sha256"]
        with np.load(path, allow_pickle=False) as archive:
            assert set(archive.files) == required
            assert len(archive["tracking_time_s"]) <= 700
            assert len(archive["force_overlay_force_n"]) <= 420


def test_final_tools_do_not_name_raw_campaign_directories() -> None:
    for filename in (
        "build_phase3a_corrected_professor_html.py",
        "build_phase3a_force_landscape.py",
    ):
        content = (SCRIPTS / filename).read_text()
        assert "corrected_baseline_p1_new_ab_20260908_v1" not in content
        assert "progressive_40_80_ab_20260907_v1" not in content
        assert "progressive_90_120_ab_20260907_v1" not in content
        assert "progressive_120_120_ab_20260907_v1" not in content


def test_force_landscape_matches_tracked_reference() -> None:
    module = load_script(
        "build_phase3a_force_landscape",
        SCRIPTS / "build_phase3a_force_landscape.py",
    )
    maps = module.dense_maps(module.model_from_compact_source())
    verification = module.verify_against_reference(maps)
    assert verification["reference_array_match"] == "PASS"
    assert verification["threshold_crossings"] == {
        "200": False,
        "220": False,
        "250": False,
    }
