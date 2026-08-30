from __future__ import annotations

import json
from pathlib import Path

import pytest

from traction_mpc_stage4.report_validation import run_structural_smoke
from traction_mpc_stage4.report_validation_renderer import (
    CONTROLLER_ORDER,
    load_comparison_case,
    mp4_supported,
    render_comparison,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "configs" / "stage4_report_validation_matrix.json"


@pytest.fixture(scope="module")
def rendered_smoke(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict, dict]:
    root = tmp_path_factory.mktemp("report_renderer")
    smoke_dir = root / "smoke"
    smoke = run_structural_smoke(
        matrix_path=MATRIX_PATH,
        output_dir=smoke_dir,
        duration_s=0.05,
    )
    render_dir = root / "render"
    manifest = render_comparison(
        case_dir=smoke_dir / "nominal_high_flexion",
        matrix_path=MATRIX_PATH,
        output_dir=render_dir,
        fps=4,
        max_frames=2,
    )
    return render_dir, smoke, manifest


def test_renderer_input_schema_requires_synchronized_four_arm_case(
    rendered_smoke: tuple[Path, dict, dict],
) -> None:
    render_dir, smoke, _ = rendered_smoke
    case_dir = Path(smoke["arms"][0]["output_dir"]).parent
    comparison = load_comparison_case(case_dir)
    assert tuple(comparison["arms"]) == CONTROLLER_ORDER
    assert comparison["patient_id"] == "nominal_reference"
    assert comparison["trajectory_id"] == "registered_high_flexion_23s"
    assert render_dir.is_dir()


def test_renderer_smoke_writes_gif_still_timeseries_and_manifest(
    rendered_smoke: tuple[Path, dict, dict],
) -> None:
    render_dir, _, manifest = rendered_smoke
    assert manifest["schema_version"] == (
        "stage4_report_validation_renderer_manifest_v1"
    )
    assert manifest["controllers"] == list(CONTROLLER_ORDER)
    assert manifest["synchronized_wall_time"] is True
    assert manifest["fixed_camera"] is True
    assert manifest["reference_actual_leg_overlay"] is True
    assert manifest["frame_count"] == 2
    assert manifest["scientific_interpretation_permitted"] is False
    for filename in (
        "comparison.gif",
        "representative_still.png",
        "metrics_timeseries.png",
        "metrics_timeseries.pdf",
        "renderer_manifest.json",
    ):
        assert (render_dir / filename).is_file()
        assert (render_dir / filename).stat().st_size > 0
    stored = json.loads((render_dir / "renderer_manifest.json").read_text())
    assert stored == manifest


def test_renderer_overwrite_and_optional_mp4_guards(
    rendered_smoke: tuple[Path, dict, dict], tmp_path: Path
) -> None:
    render_dir, smoke, _ = rendered_smoke
    case_dir = Path(smoke["arms"][0]["output_dir"]).parent
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        render_comparison(
            case_dir=case_dir,
            matrix_path=MATRIX_PATH,
            output_dir=render_dir,
            max_frames=1,
        )
    assert isinstance(mp4_supported(), bool)
    if not mp4_supported():
        with pytest.raises(RuntimeError, match="imageio-ffmpeg"):
            render_comparison(
                case_dir=case_dir,
                matrix_path=MATRIX_PATH,
                output_dir=tmp_path / "mp4",
                max_frames=1,
                write_mp4=True,
            )
