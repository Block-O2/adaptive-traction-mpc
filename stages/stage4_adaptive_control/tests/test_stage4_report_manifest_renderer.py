from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage4.report_validation import sha256_file
from traction_mpc_stage4.report_validation_renderer import (
    RENDERER_SMOKE_CATEGORY,
    _adaptive_state,
    load_manifest_media_panels,
    render_manifest_media_set,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "configs/stage4_report_generalization_matrix.json"
SOURCES = (
    ROOT
    / "results/controller_validation/visualization_sources"
    / "visualization_source_manifest.json"
)


def test_manifest_loader_supports_all_three_final_layouts() -> None:
    main = load_manifest_media_panels(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="main_adaptation_comparison",
    )
    assert [item["controller_id"] for item in main["panels"]] == [
        "fixed_mpc_prior_only",
        "trusted_adaptive_mpc",
    ]
    patient = load_manifest_media_panels(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="patient_generalization_comparison",
        scene_id="height_moderate_plus_03pct_report_only",
    )
    assert len(patient["panels"]) == 3
    assert len({item["patient_id"] for item in patient["panels"]}) == 1
    trajectory = load_manifest_media_panels(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="trajectory_generalization_comparison",
    )
    assert len(trajectory["panels"]) == 3
    assert len({item["trajectory_id"] for item in trajectory["panels"]}) == 3
    assert len(
        {item["source"]["source_evidence_category"] for item in trajectory["panels"]}
    ) == 2
    for panel in trajectory["panels"]:
        frozen_rms = float(
            np.sqrt(np.mean(np.square(panel["acceleration_magnitude_rad_s2"])))
        )
        assert frozen_rms == pytest.approx(
            panel["summary"]["report_generalization_metrics"][
                "combined_acceleration_rms_rad_s2"
            ],
            abs=1e-12,
            rel=0.0,
        )


def test_manifest_loader_rejects_source_sha_mismatch(
    tmp_path: Path,
) -> None:
    payload = json.loads(SOURCES.read_text(encoding="utf-8"))
    payload["media_sets"]["main_adaptation_comparison"]["items"][0][
        "source_trace_sha256"
    ] = "0" * 64
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_manifest_media_panels(
            visualization_manifest_path=tampered,
            generalization_matrix_path=MATRIX,
            media_set_id="main_adaptation_comparison",
        )


def test_promotion_and_no_promotion_states_are_exact() -> None:
    main = load_manifest_media_panels(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="main_adaptation_comparison",
    )
    fixed, adaptive = main["panels"]
    first = adaptive["summary"]["report_generalization_metrics"][
        "adaptive_first_promotion_wall_time_s"
    ]
    assert _adaptive_state("fixed_mpc_prior_only", fixed["summary"], 20.0) == (
        "PRIOR",
        False,
        None,
    )
    assert _adaptive_state("trusted_adaptive_mpc", adaptive["summary"], first - 0.5)[0] == "PRIOR"
    assert _adaptive_state("trusted_adaptive_mpc", adaptive["summary"], first) == (
        "ADAPTIVE",
        True,
        first,
    )
    nominal = load_manifest_media_panels(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="patient_generalization_comparison",
        scene_id="nominal_reference",
    )
    no_promotion = next(
        item for item in nominal["panels"] if item["controller_id"] == "trusted_adaptive_mpc"
    )
    assert _adaptive_state(
        "trusted_adaptive_mpc", no_promotion["summary"], 32.0
    ) == ("PRIOR", False, None)


def test_manifest_renderer_outputs_provenance_end_card_and_geometry(
    tmp_path: Path,
) -> None:
    output = tmp_path / "render"
    result = render_manifest_media_set(
        visualization_manifest_path=SOURCES,
        generalization_matrix_path=MATRIX,
        media_set_id="patient_generalization_comparison",
        scene_id="height_moderate_plus_03pct_report_only",
        output_dir=output,
        fps=2,
        max_frames=2,
        render_classification=RENDERER_SMOKE_CATEGORY,
        generation_timestamp_utc="2026-08-29T00:00:00+00:00",
    )
    assert result["media_evidence_category"] == "professor_report_visualization"
    assert result["render_classification"] == RENDERER_SMOKE_CATEGORY
    assert len(result["source_artifacts"]) == 3
    assert all(
        item["source_evidence_category"] == "report_generalization_statistical"
        for item in result["source_artifacts"]
    )
    assert all(
        item["rendered_human_geometry"]["thigh_length_m"] > 0.4
        for item in result["source_artifacts"]
    )
    assert all(
        item["end_summary"]["minimum_force_gate_margin_n"]
        == 200.0 - item["end_summary"]["cuff_force_peak_n"]
        for item in result["source_artifacts"]
    )
    assert "cuff_moment" in result["renderer"]["live_overlay_excluded"]
    assert "static_acceleration_rms" in result["renderer"]["live_overlay_excluded"]
    for key, path in result["outputs"].items():
        if path is not None:
            assert Path(path).is_file()
            assert result["output_sha256"][key] == sha256_file(Path(path))
    with pytest.raises(FileExistsError):
        render_manifest_media_set(
            visualization_manifest_path=SOURCES,
            generalization_matrix_path=MATRIX,
            media_set_id="patient_generalization_comparison",
            scene_id="height_moderate_plus_03pct_report_only",
            output_dir=output,
            fps=2,
            max_frames=2,
            render_classification=RENDERER_SMOKE_CATEGORY,
        )


def test_render_metadata_and_outputs_are_deterministic_with_fixed_timestamp(
    tmp_path: Path,
) -> None:
    kwargs = {
        "visualization_manifest_path": SOURCES,
        "generalization_matrix_path": MATRIX,
        "media_set_id": "main_adaptation_comparison",
        "fps": 2,
        "max_frames": 2,
        "render_classification": RENDERER_SMOKE_CATEGORY,
        "generation_timestamp_utc": "2026-08-29T00:00:00+00:00",
    }
    left = render_manifest_media_set(output_dir=tmp_path / "left", **kwargs)
    right = render_manifest_media_set(output_dir=tmp_path / "right", **kwargs)
    assert left["renderer_fingerprint_sha256"] == right["renderer_fingerprint_sha256"]
    for key in (
        "gif",
        "representative_still_png",
        "end_summary_card_png",
        "timeseries_png",
    ):
        assert left["output_sha256"][key] == right["output_sha256"][key]
