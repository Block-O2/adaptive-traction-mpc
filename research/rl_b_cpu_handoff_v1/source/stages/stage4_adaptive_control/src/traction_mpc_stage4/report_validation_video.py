"""Final MP4 assembly from frozen report-visualization traces."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image, ImageDraw

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2

from .report_validation import (
    canonical_json_sha256,
    load_report_validation_matrix,
    patient_spec_for_id,
    sha256_file,
    write_strict_json,
)
from .report_validation_renderer import (
    RENDERER_VERSION,
    _adaptive_state,
    _font,
    _summary_card,
    load_manifest_media_panels,
    mp4_supported,
)

try:
    import imageio_ffmpeg
except ImportError:  # The generation entry point reports the exact missing backend.
    imageio_ffmpeg = None


VIDEO_RENDERER_VERSION = "stage4_professor_report_video_renderer_v1"
VIDEO_SCHEMA_VERSION = "stage4_professor_report_video_manifest_v1"
VIDEO_EVIDENCE_CATEGORY = "professor_report_visualization"
DEFAULT_FPS = 30
DEFAULT_CANVAS_SIZE = (1920, 1080)
PANEL_HEIGHT = 720
TEMPORAL_SAMPLING = (
    "existing renderer convention: linspace from 0 to the maximum frozen trace "
    "time with floor(duration*fps)+1 display frames; each display time selects "
    "the latest source sample at or before that time via searchsorted(right)-1; "
    "no scientific-state interpolation"
)


def _motion_frame_times(final_time_s: float, fps: int) -> np.ndarray:
    if not np.isfinite(final_time_s) or final_time_s <= 0.0 or fps <= 0:
        raise ValueError("video duration and fps must be positive and finite")
    count = max(2, int(np.floor(final_time_s * fps)) + 1)
    return np.linspace(0.0, final_time_s, count)


def _canvas_frame(
    image: Image.Image,
    *,
    subtitle: str | None,
    canvas_size: tuple[int, int] = DEFAULT_CANVAS_SIZE,
) -> np.ndarray:
    canvas = Image.new("RGB", canvas_size, (13, 18, 25))
    top = 96 if subtitle else 0
    available = (canvas_size[0], canvas_size[1] - top)
    scale = min(available[0] / image.width, available[1] / image.height)
    size = (
        max(2, int(round(image.width * scale)) // 2 * 2),
        max(2, int(round(image.height * scale)) // 2 * 2),
    )
    resized = image.resize(size, Image.Resampling.LANCZOS)
    x = (canvas_size[0] - size[0]) // 2
    y = top + (available[1] - size[1]) // 2
    canvas.paste(resized, (x, y))
    if subtitle:
        draw = ImageDraw.Draw(canvas)
        font = _font(24, bold=True)
        box = draw.multiline_textbbox((0, 0), subtitle, font=font, spacing=4)
        draw.multiline_text(
            ((canvas_size[0] - (box[2] - box[0])) // 2, 15),
            subtitle,
            font=font,
            fill=(220, 228, 236),
            spacing=4,
            align="center",
        )
    return np.asarray(canvas)


def _title_card(
    chapter: str,
    title: str,
    subtitle: str,
    *,
    canvas_size: tuple[int, int] = DEFAULT_CANVAS_SIZE,
) -> np.ndarray:
    card = Image.new("RGB", canvas_size, (13, 18, 25))
    draw = ImageDraw.Draw(card)
    chapter_font = _font(34, bold=True)
    title_font = _font(58, bold=True)
    subtitle_font = _font(24)
    for text, font, y, color in (
        (chapter, chapter_font, 225, (65, 206, 126)),
        (title, title_font, 292, (245, 248, 252)),
        (subtitle, subtitle_font, 395, (176, 192, 207)),
    ):
        box = draw.multiline_textbbox((0, 0), text, font=font, spacing=5)
        draw.multiline_text(
            ((canvas_size[0] - (box[2] - box[0])) // 2, y),
            text,
            font=font,
            fill=color,
            spacing=5,
            align="center",
        )
    return np.asarray(card)


def _panel_size_for_count(panel_count: int) -> tuple[int, int]:
    if panel_count not in {2, 3}:
        raise ValueError("final videos require two or three panels")
    return DEFAULT_CANVAS_SIZE[0] // panel_count, PANEL_HEIGHT


def _real_scene_panel(
    scene: Image.Image,
    *,
    panel_label: str,
    patient_label: str,
    controller_id: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    sample: int,
    frame_time_s: float,
) -> Image.Image:
    """Add compact metrics without introducing any schematic geometry."""

    panel = scene.copy().convert("RGB")
    draw = ImageDraw.Draw(panel, "RGBA")
    width, _ = panel.size
    draw.rectangle((0, 0, width, 112), fill=(15, 20, 28, 225))
    draw.text(
        (18, 10), panel_label, font=_font(24, bold=True), fill=(245, 248, 252)
    )
    draw.text((18, 43), patient_label, font=_font(15), fill=(176, 192, 207))
    tracking = float(np.linalg.norm(trace["tracking_error_deg_god_view"][sample]))
    force = float(
        np.linalg.norm(
            np.asarray(trace["cuff_wrench_local_god_view"][sample], dtype=float)[:3]
        )
    )
    state, promotion, first_promotion = _adaptive_state(
        controller_id, summary, frame_time_s
    )
    draw.text(
        (18, 74),
        f"e={tracking:4.2f} deg   |F|={force:5.1f} N   MODEL: {state}",
        font=_font(20),
        fill=(220, 228, 236),
    )
    if promotion:
        box_width = min(300, width - 30)
        draw.rounded_rectangle(
            (width - box_width - 15, 10, width - 15, 43),
            radius=7,
            fill=(39, 174, 96, 235),
        )
        draw.text(
            (width - box_width - 5, 16),
            f"MODEL PROMOTED @ {first_promotion:.1f} s",
            font=_font(15, bold=True),
            fill=(255, 255, 255),
        )
    return panel


class _SceneRenderer:
    """Stream frames using the accepted manifest-driven visual components."""

    def __init__(
        self,
        *,
        visualization_manifest_path: Path,
        generalization_matrix_path: Path,
        media_set_id: str,
        scene_id: str | None,
        panel_labels: list[str],
    ) -> None:
        self.scene = load_manifest_media_panels(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id=media_set_id,
            scene_id=scene_id,
        )
        if len(panel_labels) != len(self.scene["panels"]):
            raise ValueError("video panel label count mismatch")
        self.scene["panel_labels"] = panel_labels
        matrix_path = Path(self.scene["validation_matrix_path"])
        matrix = load_report_validation_matrix(matrix_path)
        self.panel_width, self.panel_height = _panel_size_for_count(
            len(self.scene["panels"])
        )
        self.renderers: list[mujoco.Renderer] = []
        self.plants: list[CoupledUR10eHumanV2] = []
        self.humans = []
        self.backends: list[str] = []
        self.camera = mujoco.MjvCamera()
        mujoco.mjv_defaultCamera(self.camera)
        self.camera.lookat[:] = np.array([0.48, -0.28, 0.42])
        self.camera.distance = 2.85
        self.camera.azimuth = -45.0
        self.camera.elevation = -21.0
        for panel in self.scene["panels"]:
            patient, _ = patient_spec_for_id(
                matrix, matrix_path, panel["patient_id"]
            )
            human = patient.build_human()
            plant = CoupledUR10eHumanV2(human)
            plant.reset(np.radians(panel["trace"]["human_q_deg_god_view"][0]))
            plant.model.vis.global_.offwidth = self.panel_width
            plant.model.vis.global_.offheight = self.panel_height
            try:
                renderer = mujoco.Renderer(
                    plant.model,
                    height=self.panel_height,
                    width=self.panel_width,
                )
            except Exception as error:
                for existing_renderer in self.renderers:
                    existing_renderer.close()
                raise RuntimeError(
                    "genuine MuJoCo 3D rendering is unavailable; schematic "
                    "fallback is prohibited"
                ) from error
            backend = "mujoco_renderer_fixed_camera_real_3d"
            self.humans.append(human)
            self.plants.append(plant)
            self.renderers.append(renderer)
            self.backends.append(backend)

    @property
    def final_time_s(self) -> float:
        return max(
            float(panel["trace"]["time_s"][-1])
            for panel in self.scene["panels"]
        )

    def frame_times(self, fps: int) -> np.ndarray:
        times = _motion_frame_times(self.final_time_s, fps)
        promotions = [
            panel["summary"]["report_generalization_metrics"].get(
                "adaptive_first_promotion_wall_time_s"
            )
            for panel in self.scene["panels"]
        ]
        promotions = [float(value) for value in promotions if value is not None]
        if promotions and len(times) >= 3:
            target = min(promotions)
            index = int(np.argmin(np.abs(times[1:-1] - target))) + 1
            times[index] = target
            times = np.sort(times)
        return times

    def render(self, frame_time_s: float, *, subtitle: str | None) -> np.ndarray:
        images = []
        for index, panel in enumerate(self.scene["panels"]):
            trace = panel["trace"]
            time = np.asarray(trace["time_s"], dtype=float)
            sample = int(
                np.clip(
                    np.searchsorted(time, frame_time_s, side="right") - 1,
                    0,
                    len(time) - 1,
                )
            )
            plant = self.plants[index]
            plant.data.qpos[plant.human_qpos_indices] = np.radians(
                trace["human_q_deg_god_view"][sample]
            )
            plant.data.qpos[plant.robot_qpos_indices] = trace["robot_q_rad"][sample]
            plant.data.qvel[:] = 0.0
            mujoco.mj_forward(plant.model, plant.data)
            renderer = self.renderers[index]
            renderer.update_scene(plant.data, camera=self.camera)
            base = Image.fromarray(renderer.render())
            images.append(
                _real_scene_panel(
                    base,
                    panel_label=self.scene["panel_labels"][index],
                    patient_label=panel["patient_id"],
                    controller_id=panel["controller_id"],
                    summary=panel["summary"],
                    trace=trace,
                    sample=sample,
                    frame_time_s=float(frame_time_s),
                )
            )
        row = Image.new(
            "RGB",
            (len(images) * self.panel_width, self.panel_height),
            (13, 18, 25),
        )
        for index, image in enumerate(images):
            row.paste(image, (index * self.panel_width, 0))
        return _canvas_frame(row, subtitle=subtitle)

    def summary(self, *, subtitle: str | None) -> np.ndarray:
        cards = [
            _summary_card(
                panel=panel,
                label=self.scene["panel_labels"][index],
                width=self.panel_width,
                height=self.panel_height,
            )
            for index, panel in enumerate(self.scene["panels"])
        ]
        row = Image.new(
            "RGB",
            (len(cards) * self.panel_width, self.panel_height),
            (13, 18, 25),
        )
        for index, card in enumerate(cards):
            row.paste(card, (index * self.panel_width, 0))
        return _canvas_frame(row, subtitle=subtitle)

    def provenance(self) -> dict[str, Any]:
        artifacts = []
        for index, panel in enumerate(self.scene["panels"]):
            artifacts.append(
                {
                    "panel_label": self.scene["panel_labels"][index],
                    "controller_id": panel["controller_id"],
                    "patient_id": panel["patient_id"],
                    "trajectory_id": panel["trajectory_id"],
                    "measurement_seed": panel["measurement_seed"],
                    "source_evidence_category": panel["source"][
                        "source_evidence_category"
                    ],
                    "source_summary_path": panel["source"]["source_summary_path"],
                    "source_trace_path": panel["source"]["source_trace_path"],
                    "source_trace_sha256": panel["source"]["source_trace_sha256"],
                    "controller_fingerprint_sha256": panel["source"][
                        "controller_fingerprint_sha256"
                    ],
                    "rendered_human_geometry": {
                        "thigh_length_m": float(self.humans[index].thigh_length_m),
                        "shank_length_m": float(self.humans[index].shank_length_m),
                    },
                }
            )
        return {
            "media_set_id": self.scene["media_set_id"],
            "scene_id": self.scene["scene_id"],
            "layout": self.scene["layout"],
            "source_artifacts": artifacts,
            "renderer_backends": self.backends,
        }

    def close(self) -> None:
        for renderer in self.renderers:
            renderer.close()


def _writer(path: Path, fps: int):
    return imageio.get_writer(
        path,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=None,
        ffmpeg_params=[
            "-crf",
            "20",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
            "-an",
        ],
    )


def _repeat(writer: Any, frame: np.ndarray, count: int) -> None:
    for _ in range(count):
        writer.append_data(frame)


def _render_single_scene_video(
    *,
    output_path: Path,
    renderer: _SceneRenderer,
    fps: int,
    subtitle: str | None,
    summary_duration_s: float,
) -> dict[str, Any]:
    times = renderer.frame_times(fps)
    writer = _writer(output_path, fps)
    try:
        for frame_time in times:
            writer.append_data(renderer.render(float(frame_time), subtitle=subtitle))
        summary_frames = int(round(summary_duration_s * fps))
        _repeat(writer, renderer.summary(subtitle=subtitle), summary_frames)
    finally:
        writer.close()
    frame_count = len(times) + summary_frames
    return {
        "motion_duration_s": float(len(times) / fps),
        "summary_duration_s": float(summary_frames / fps),
        "frame_count": int(frame_count),
        "duration_s": float(frame_count / fps),
        "scene": renderer.provenance(),
    }


def _render_chapter_video(
    *,
    output_path: Path,
    chapters: Iterable[tuple[str, str, _SceneRenderer]],
    fps: int,
    subtitle: str,
) -> dict[str, Any]:
    writer = _writer(output_path, fps)
    title_frames = int(round(1.5 * fps))
    summary_frames = int(round(1.5 * fps))
    transition_frames = int(round(0.25 * fps))
    transition = np.zeros((DEFAULT_CANVAS_SIZE[1], DEFAULT_CANVAS_SIZE[0], 3), dtype=np.uint8)
    chapter_records = []
    total_frames = 0
    chapter_list = list(chapters)
    try:
        for index, (chapter_number, title, renderer) in enumerate(chapter_list):
            _repeat(
                writer,
                _title_card(chapter_number, title, subtitle),
                title_frames,
            )
            times = renderer.frame_times(fps)
            for frame_time in times:
                writer.append_data(renderer.render(float(frame_time), subtitle=subtitle))
            _repeat(writer, renderer.summary(subtitle=subtitle), summary_frames)
            chapter_frames = title_frames + len(times) + summary_frames
            chapter_records.append(
                {
                    "chapter": chapter_number,
                    "title": title,
                    "title_duration_s": title_frames / fps,
                    "motion_duration_s": len(times) / fps,
                    "summary_duration_s": summary_frames / fps,
                    "chapter_duration_s": chapter_frames / fps,
                    "scene": renderer.provenance(),
                }
            )
            total_frames += chapter_frames
            if index + 1 < len(chapter_list):
                _repeat(writer, transition, transition_frames)
                total_frames += transition_frames
    finally:
        writer.close()
    return {
        "chapters": chapter_records,
        "transition_duration_s": transition_frames / fps,
        "frame_count": int(total_frames),
        "duration_s": float(total_frames / fps),
    }


def render_final_professor_videos(
    *,
    visualization_manifest_path: Path,
    generalization_matrix_path: Path,
    output_dir: Path,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Generate the three delivery MP4s atomically from frozen sources."""

    if not mp4_supported() or imageio_ffmpeg is None:
        raise RuntimeError("imageio-ffmpeg is required for final MP4 rendering")
    if fps not in {24, 30}:
        raise ValueError("final professor videos require 24 or 30 fps")
    visualization_manifest_path = Path(visualization_manifest_path).resolve()
    generalization_matrix_path = Path(generalization_matrix_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite final video output {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    renderers: list[_SceneRenderer] = []
    try:
        main = _SceneRenderer(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id="main_adaptation_comparison",
            scene_id=None,
            panel_labels=["Fixed MPC", "Adaptive MPC"],
        )
        renderers.append(main)
        nominal = _SceneRenderer(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id="patient_generalization_comparison",
            scene_id="nominal_reference",
            panel_labels=["PD+FF", "Fixed MPC", "Adaptive MPC"],
        )
        geometry = _SceneRenderer(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id="patient_generalization_comparison",
            scene_id="height_moderate_plus_03pct_report_only",
            panel_labels=["PD+FF", "Fixed MPC", "Adaptive MPC"],
        )
        mixed = _SceneRenderer(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id="patient_generalization_comparison",
            scene_id="registered_moderate_anchor",
            panel_labels=["PD+FF", "Fixed MPC", "Adaptive MPC"],
        )
        renderers.extend([nominal, geometry, mixed])
        trajectory = _SceneRenderer(
            visualization_manifest_path=visualization_manifest_path,
            generalization_matrix_path=generalization_matrix_path,
            media_set_id="trajectory_generalization_comparison",
            scene_id=None,
            panel_labels=["High Flexion", "Moderate ROM", "Hip Dominant"],
        )
        renderers.append(trajectory)

        outputs = {
            "01_Fixed_vs_Adaptive.mp4": _render_single_scene_video(
                output_path=temporary_dir / "01_Fixed_vs_Adaptive.mp4",
                renderer=main,
                fps=fps,
                subtitle=None,
                summary_duration_s=2.0,
            ),
            "02_Patient_Generalization.mp4": _render_chapter_video(
                output_path=temporary_dir / "02_Patient_Generalization.mp4",
                chapters=[
                    ("Chapter 1", "Nominal Patient", nominal),
                    ("Chapter 2", "+3% Segment Geometry", geometry),
                    ("Chapter 3", "Moderate Mixed Mismatch", mixed),
                ],
                fps=fps,
                subtitle=(
                    "Same frozen controller settings\n"
                    "No patient-specific retuning"
                ),
            ),
            "03_Trajectory_Generalization.mp4": _render_single_scene_video(
                output_path=temporary_dir / "03_Trajectory_Generalization.mp4",
                renderer=trajectory,
                fps=fps,
                subtitle=(
                    "Same frozen Adaptive MPC\nDifferent rehabilitation tasks"
                ),
                summary_duration_s=2.0,
            ),
        }
        encoding = {
            "container": "mp4",
            "codec": "H.264/AVC via libx264",
            "pixel_format": "yuv420p",
            "audio": False,
            "backend": "imageio-ffmpeg",
            "backend_version": version("imageio-ffmpeg"),
            "ffmpeg_version": imageio_ffmpeg.get_ffmpeg_version(),
            "fps": fps,
            "crf": 20,
            "preset": "medium",
            "faststart": True,
            "output_resolution": list(DEFAULT_CANVAS_SIZE),
        }
        renderer_contract = {
            "video_renderer_version": VIDEO_RENDERER_VERSION,
            "source_renderer_version": RENDERER_VERSION,
            "visualization_replay_only": True,
            "new_simulation_executed": False,
            "state_update_pipeline": "frozen qpos -> zero qvel -> mj_forward -> render",
            "real_mujoco_3d_required": True,
            "schematic_fallback_allowed": False,
            "mujoco_version": mujoco.__version__,
            "rendering_backend": "mujoco.Renderer with macOS CGL",
            "mjpython_used": bool(os.environ.get("MJPYTHON_BIN")),
            "fixed_camera": True,
            "panel_sizes": {
                "two_panel": list(_panel_size_for_count(2)),
                "three_panel": list(_panel_size_for_count(3)),
            },
            "output_canvas_size": list(DEFAULT_CANVAS_SIZE),
            "camera": {
                "lookat": [0.48, -0.28, 0.42],
                "distance": 2.85,
                "azimuth_deg": -45.0,
                "elevation_deg": -21.0,
            },
            "scene_content": [
                "UR10e surrogate MuJoCo mesh geometry",
                "Human V2 MuJoCo capsule geometry",
                "rigid sleeve/cuff geometry and connection",
                "bed/support plane",
                "MuJoCo lighting, shadows, and perspective",
            ],
            "canvas_resampling": "none for live 3D panel rows",
            "temporal_sampling": TEMPORAL_SAMPLING,
            "scientific_state_interpolation": False,
            "frozen_acceleration_processing": (
                "existing frozen 50 Hz Savitzky-Golay acceleration convention"
            ),
        }
        for filename, record in outputs.items():
            path = temporary_dir / filename
            record.update(
                {
                    "output_filename": filename,
                    "output_resolution": list(DEFAULT_CANVAS_SIZE),
                    "fps": fps,
                    "file_size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        manifest = {
            "schema_version": VIDEO_SCHEMA_VERSION,
            "media_evidence_category": VIDEO_EVIDENCE_CATEGORY,
            "statement": "visualization replay only, no new simulation",
            "scientific_interpretation_permitted": False,
            "source_evidence_relabelled": False,
            "visualization_source_manifest_path": str(
                visualization_manifest_path
            ),
            "visualization_source_manifest_sha256": sha256_file(
                visualization_manifest_path
            ),
            "generalization_matrix_path": str(generalization_matrix_path),
            "generalization_matrix_sha256": sha256_file(
                generalization_matrix_path
            ),
            "renderer": renderer_contract,
            "renderer_fingerprint_sha256": canonical_json_sha256(
                renderer_contract
            ),
            "encoding": encoding,
            "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "videos": outputs,
        }
        write_strict_json(temporary_dir / "video_manifest.json", manifest)
        temporary_dir.rename(output_dir)
        return manifest
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise
    finally:
        for renderer in renderers:
            renderer.close()
