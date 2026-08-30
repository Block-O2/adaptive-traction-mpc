from __future__ import annotations

import inspect
import numpy as np
from PIL import Image
import pytest

from traction_mpc_stage4.report_validation_video import (
    DEFAULT_CANVAS_SIZE,
    TEMPORAL_SAMPLING,
    _canvas_frame,
    _motion_frame_times,
    _panel_size_for_count,
    _real_scene_panel,
    _SceneRenderer,
    _title_card,
)


def test_video_sampling_uses_existing_renderer_time_grid() -> None:
    times = _motion_frame_times(32.0, 30)
    assert len(times) == 961
    assert times[0] == 0.0
    assert times[-1] == 32.0
    assert np.all(np.diff(times) > 0.0)
    assert "searchsorted(right)-1" in TEMPORAL_SAMPLING
    assert "no scientific-state interpolation" in TEMPORAL_SAMPLING


def test_video_canvas_and_chapter_card_have_exact_delivery_shape() -> None:
    panel = Image.new("RGB", (1440, 320), (240, 120, 10))
    canvas = _canvas_frame(panel, subtitle="Frozen settings")
    title = _title_card("Chapter 2", "+3% Segment Geometry", "Frozen settings")
    expected = (DEFAULT_CANVAS_SIZE[1], DEFAULT_CANVAS_SIZE[0], 3)
    assert canvas.shape == expected
    assert title.shape == expected
    assert canvas.dtype == np.uint8
    assert title.dtype == np.uint8
    assert np.any(canvas)
    assert np.any(title)


def test_real_scene_panel_sizes_use_full_hd_width() -> None:
    assert DEFAULT_CANVAS_SIZE == (1920, 1080)
    assert _panel_size_for_count(2) == (960, 720)
    assert _panel_size_for_count(3) == (640, 720)
    with pytest.raises(ValueError):
        _panel_size_for_count(1)


def test_final_video_path_contains_no_schematic_fallback() -> None:
    renderer_source = inspect.getsource(_SceneRenderer)
    overlay_source = inspect.getsource(_real_scene_panel)
    assert "_schematic_scene" not in renderer_source
    assert "fallback is prohibited" in renderer_source
    assert "_leg_points" not in overlay_source


@pytest.mark.parametrize("duration,fps", [(0.0, 30), (32.0, 0)])
def test_video_sampling_rejects_nonpositive_controls(duration: float, fps: int) -> None:
    with pytest.raises(ValueError):
        _motion_frame_times(duration, fps)
