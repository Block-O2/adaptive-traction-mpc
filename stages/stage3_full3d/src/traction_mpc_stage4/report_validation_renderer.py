"""Trace-only synchronized renderer for report-validation comparisons."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import savgol_filter

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2

from .report_validation import (
    canonical_json_sha256,
    load_report_validation_matrix,
    patient_spec_for_id,
    prepare_fresh_output_directory,
    report_root,
    sha256_file,
    write_strict_json,
)
from .report_generalization import (
    VISUALIZATION_EVIDENCE_CATEGORY,
    load_generalization_matrix,
    load_metric_definitions,
)


CONTROLLER_ORDER = (
    "pd_feedback",
    "pd_nominal_inverse_dynamics_ff",
    "fixed_mpc_prior_only",
    "trusted_adaptive_mpc",
)
GENERALIZATION_CONTROLLER_ORDER = (
    "pd_nominal_inverse_dynamics_ff",
    "fixed_mpc_prior_only",
    "trusted_adaptive_mpc",
)
CONTROLLER_LABELS = {
    "pd_feedback": "PD",
    "pd_nominal_inverse_dynamics_ff": "PD + nominal FF",
    "fixed_mpc_prior_only": "Fixed-model MPC",
    "trusted_adaptive_mpc": "Trusted adaptive MPC",
}
RENDERER_VERSION = "stage4_professor_report_manifest_renderer_v1"
RENDERER_SMOKE_CATEGORY = "non_scientific_renderer_smoke"


def mp4_supported() -> bool:
    return importlib.util.find_spec("imageio_ffmpeg") is not None


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _load_arm(
    case_dir: Path,
    controller_id: str,
    *,
    expected_trace_sha256: str | None = None,
) -> dict[str, Any]:
    arm_dir = Path(case_dir) / controller_id
    summary_path = arm_dir / f"{controller_id}.json"
    trace_path = arm_dir / f"{controller_id}_trace.npz"
    if not summary_path.is_file() or not trace_path.is_file():
        raise FileNotFoundError(f"missing renderer input for {controller_id}")
    trace_sha256 = sha256_file(trace_path)
    if expected_trace_sha256 is not None and trace_sha256 != expected_trace_sha256:
        raise ValueError(f"source trace SHA-256 mismatch for {controller_id}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with np.load(trace_path, allow_pickle=False) as archive:
        trace = {key: archive[key] for key in archive.files}
    required = {
        "time_s",
        "human_q_deg_god_view",
        "human_q_ref_deg",
        "robot_q_rad",
        "tracking_error_deg_god_view",
        "cuff_wrench_local_god_view",
        "reference_phase_time_s",
    }
    missing = required - set(trace)
    if missing:
        raise ValueError(f"renderer trace missing keys: {sorted(missing)}")
    provenance = summary.get("report_validation_provenance", {})
    if provenance.get("controller") != controller_id:
        raise ValueError("renderer controller label differs from provenance")
    return {
        "summary": summary,
        "trace": trace,
        "provenance": provenance,
        "summary_path": str(summary_path.resolve()),
        "trace_path": str(trace_path.resolve()),
        "trace_sha256": trace_sha256,
    }


def load_comparison_case(
    case_dir: Path,
    *,
    controller_order: tuple[str, ...] = CONTROLLER_ORDER,
    expected_trace_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    arms = {
        controller: _load_arm(
            case_dir,
            controller,
            expected_trace_sha256=(expected_trace_sha256 or {}).get(controller),
        )
        for controller in controller_order
    }
    patients = {item["provenance"]["patient"] for item in arms.values()}
    trajectories = {item["provenance"]["trajectory"] for item in arms.values()}
    clock_hashes = {
        item["provenance"]["reference_clock_sha256"] for item in arms.values()
    }
    if len(patients) != 1 or len(trajectories) != 1 or len(clock_hashes) != 1:
        raise ValueError("comparison arms do not share patient, trajectory, and clock")
    reference_hashes = {
        np.asarray(item["trace"]["reference_phase_time_s"]).tobytes()
        for item in arms.values()
    }
    if len(reference_hashes) != 1:
        raise ValueError("comparison arms do not contain identical reference histories")
    return {
        "arms": arms,
        "patient_id": patients.pop(),
        "trajectory_id": trajectories.pop(),
        "reference_clock_sha256": clock_hashes.pop(),
    }


def _leg_points(
    q_deg: np.ndarray,
    *,
    thigh_length_m: float,
    shank_length_m: float,
    origin: tuple[float, float],
    pixels_per_m: float,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    q1, q2 = np.radians(np.asarray(q_deg, dtype=float))
    hip = np.asarray(origin, dtype=float)
    knee = hip + pixels_per_m * thigh_length_m * np.array(
        [np.cos(q1), -np.sin(q1)]
    )
    ankle = knee + pixels_per_m * shank_length_m * np.array(
        [np.cos(q1 - q2), -np.sin(q1 - q2)]
    )
    return tuple(map(tuple, (hip, knee, ankle)))


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: tuple[int, int, int],
    width: int,
) -> None:
    start_array = np.asarray(start, dtype=float)
    delta = np.asarray(end, dtype=float) - start_array
    length = float(np.linalg.norm(delta))
    if length <= 1e-12:
        return
    unit = delta / length
    for offset in np.arange(0.0, length, 10.0):
        segment_start = start_array + offset * unit
        segment_end = start_array + min(offset + 6.0, length) * unit
        draw.line(
            [tuple(segment_start), tuple(segment_end)], fill=fill, width=width
        )


def _adaptive_state(
    controller_id: str, summary: dict[str, Any], time_s: float
) -> tuple[str, bool, float | None]:
    if controller_id == "pd_feedback":
        return "N/A", False, None
    if controller_id != "trusted_adaptive_mpc":
        return "PRIOR", False, None
    promotions = summary.get("hierarchical_trust", {}).get("control_promotions", [])
    applied_times = [float(item["promotion_time_s"]) for item in promotions]
    first = min(applied_times) if applied_times else None
    active = bool(first is not None and time_s >= first - 1e-12)
    just_promoted = bool(first is not None and abs(time_s - first) <= 0.35)
    return ("ADAPTIVE" if active else "PRIOR"), just_promoted, first


def _panel(
    scene: Image.Image,
    *,
    controller_id: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    index: int,
    frame_time_s: float,
    thigh_length_m: float,
    shank_length_m: float,
    held_after_termination: bool,
    panel_label: str | None = None,
    patient_label: str | None = None,
    live_acceleration_rad_s2: float | None = None,
) -> Image.Image:
    panel = scene.copy().convert("RGB")
    draw = ImageDraw.Draw(panel, "RGBA")
    width, height = panel.size
    draw.rectangle((0, 0, width, 82), fill=(15, 20, 28, 225))
    label = panel_label or CONTROLLER_LABELS[controller_id]
    draw.text((12, 7), label, font=_font(16, bold=True), fill=(245, 248, 252))
    if patient_label:
        draw.text((12, 29), patient_label, font=_font(10), fill=(176, 192, 207))
    tracking = float(np.linalg.norm(trace["tracking_error_deg_god_view"][index]))
    wrench = np.asarray(trace["cuff_wrench_local_god_view"][index], dtype=float)
    force = float(np.linalg.norm(wrench[:3]))
    state, promotion, first_promotion = _adaptive_state(
        controller_id, summary, frame_time_s
    )
    acceleration_text = (
        f"   |a|={live_acceleration_rad_s2:4.2f} rad/s2"
        if live_acceleration_rad_s2 is not None
        else ""
    )
    draw.text(
        (12, 49),
        f"e={tracking:4.2f} deg   |F|={force:5.1f} N{acceleration_text}   MODEL: {state}",
        font=_font(12),
        fill=(220, 228, 236),
    )
    if promotion:
        draw.rounded_rectangle(
            (width - 201, 7, width - 12, 31), radius=5, fill=(39, 174, 96, 235)
        )
        draw.text(
            (width - 193, 11),
            f"MODEL PROMOTED @ {first_promotion:.1f} s",
            font=_font(10, bold=True),
            fill=(255, 255, 255),
        )
    if held_after_termination:
        draw.rectangle((0, height - 28, width, height), fill=(155, 38, 38, 225))
        draw.text(
            (10, height - 23),
            f"TERMINATED: {summary['termination_reason']}",
            font=_font(11, bold=True),
            fill=(255, 255, 255),
        )

    inset = (10, height - 112, 164, height - 34)
    draw.rounded_rectangle(inset, radius=6, fill=(16, 22, 30, 205), outline=(95, 108, 124, 220))
    actual = _leg_points(
        trace["human_q_deg_god_view"][index],
        thigh_length_m=thigh_length_m,
        shank_length_m=shank_length_m,
        origin=(23.0, height - 51.0),
        pixels_per_m=125.0,
    )
    reference = _leg_points(
        trace["human_q_ref_deg"][index],
        thigh_length_m=thigh_length_m,
        shank_length_m=shank_length_m,
        origin=(23.0, height - 51.0),
        pixels_per_m=125.0,
    )
    for start, end in zip(reference[:-1], reference[1:], strict=True):
        _dashed_line(draw, start, end, fill=(83, 211, 255, 220), width=4)
    for start, end in zip(actual[:-1], actual[1:], strict=True):
        draw.line([start, end], fill=(255, 172, 70, 245), width=5)
    draw.text((18, height - 108), "solid actual / dashed reference", font=_font(9), fill=(225, 230, 236))
    return panel


def _schematic_scene(
    plant: CoupledUR10eHumanV2, *, width: int, height: int
) -> Image.Image:
    """Render a fixed FK projection when a GL framebuffer is unavailable."""

    image = Image.new("RGB", (width, height), (229, 235, 241))
    draw = ImageDraw.Draw(image, "RGBA")

    def project(point: np.ndarray) -> tuple[float, float]:
        x, y, z = np.asarray(point, dtype=float)
        u = x - 0.55 * y
        v = z + 0.18 * y
        return 90.0 + 255.0 * u, height - 42.0 - 255.0 * v

    draw.line((0, height - 35, width, height - 35), fill=(122, 145, 165, 255), width=5)
    robot_bodies = (
        "base",
        "shoulder_link",
        "upper_arm_link",
        "forearm_link",
        "wrist_1_link",
        "wrist_2_link",
        "wrist_3_link",
    )
    robot_points = [
        project(plant.data.xpos[plant.model.body(name).id]) for name in robot_bodies
    ]
    robot_points.append(project(plant.data.site_xpos[plant.attachment_site_id]))
    draw.line(robot_points, fill=(54, 92, 125, 255), width=10, joint="curve")
    for point in robot_points:
        draw.ellipse(
            (point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5),
            fill=(40, 69, 94, 255),
        )

    q1, q2 = plant.data.qpos[plant.human_qpos_indices]
    hip = np.array([0.0, 0.0, 0.062])
    knee = hip + np.array(
        [
            plant.human.thigh_length_m * np.cos(q1),
            0.0,
            plant.human.thigh_length_m * np.sin(q1),
        ]
    )
    ankle = knee + np.array(
        [
            plant.human.shank_length_m * np.cos(q1 - q2),
            0.0,
            plant.human.shank_length_m * np.sin(q1 - q2),
        ]
    )
    human_points = [project(value) for value in (hip, knee, ankle)]
    draw.line(human_points, fill=(224, 121, 45, 255), width=13, joint="curve")
    for point in human_points:
        draw.ellipse(
            (point[0] - 7, point[1] - 7, point[0] + 7, point[1] + 7),
            fill=(185, 80, 24, 255),
        )
    cuff = project(plant.data.site_xpos[plant.sleeve_site_id])
    draw.ellipse(
        (cuff[0] - 11, cuff[1] - 11, cuff[0] + 11, cuff[1] + 11),
        outline=(126, 48, 158, 255),
        width=6,
    )
    draw.text(
        (width - 156, height - 23),
        "MuJoCo FK schematic fallback",
        font=_font(9),
        fill=(62, 76, 90, 255),
    )
    return image


def _timeseries(
    comparison: dict[str, Any],
    output_png: Path,
    output_pdf: Path,
    *,
    controller_order: tuple[str, ...],
) -> None:
    canvas = Image.new("RGB", (900, 720), (250, 251, 252))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (40, 18),
        f"{comparison['patient_id']} | {comparison['trajectory_id']} | non-clinical simulation",
        font=_font(18, bold=True),
        fill=(28, 37, 47),
    )
    color_by_controller = {
        "pd_feedback": "#e67e22",
        "pd_nominal_inverse_dynamics_ff": "#8e44ad",
        "fixed_mpc_prior_only": "#2980b9",
        "trusted_adaptive_mpc": "#27ae60",
    }
    series: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    final_time = 0.0
    for controller_id in controller_order:
        trace = comparison["arms"][controller_id]["trace"]
        time = np.asarray(trace["time_s"])
        tracking = np.linalg.norm(trace["tracking_error_deg_god_view"], axis=1)
        wrench = np.asarray(trace["cuff_wrench_local_god_view"])
        series[controller_id] = (
            time,
            tracking,
            np.linalg.norm(wrench[:, :3], axis=1),
            np.linalg.norm(wrench[:, 3:], axis=1),
        )
        final_time = max(final_time, float(time[-1]))
    plot_specs = (
        ("tracking error [deg]", 1),
        ("cuff |F| [N]", 2),
        ("cuff |M| [Nm]", 3),
    )
    for plot_index, (label, value_index) in enumerate(plot_specs):
        box = (100, 75 + 200 * plot_index, 860, 235 + 200 * plot_index)
        draw.rectangle(box, outline=(112, 126, 140), width=1)
        draw.text((18, box[1] + 62), label, font=_font(12), fill=(49, 60, 72))
        maximum = max(
            float(np.max(values[value_index])) for values in series.values()
        )
        maximum = max(maximum, 1e-9)
        for controller_id in controller_order:
            color = color_by_controller[controller_id]
            time, *values = series[controller_id]
            samples = values[value_index - 1]
            if len(samples) > 760:
                indices = np.linspace(0, len(samples) - 1, 760).astype(int)
                time = time[indices]
                samples = samples[indices]
            xs = box[0] + (box[2] - box[0]) * time / max(final_time, 1e-12)
            ys = box[3] - (box[3] - box[1]) * samples / maximum
            points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]
            if len(points) >= 2:
                draw.line(points, fill=color, width=2)
        draw.text(
            (box[0] + 4, box[1] + 3),
            f"max {maximum:.3g}",
            font=_font(9),
            fill=(92, 104, 116),
        )
    draw.text((420, 684), "wall time [s]", font=_font(12), fill=(49, 60, 72))
    legend_x = 110
    for controller_id in controller_order:
        color = color_by_controller[controller_id]
        draw.line((legend_x, 55, legend_x + 22, 55), fill=color, width=3)
        draw.text(
            (legend_x + 27, 48),
            CONTROLLER_LABELS[controller_id],
            font=_font(9),
            fill=(49, 60, 72),
        )
        legend_x += 185
    canvas.save(output_png)
    canvas.save(output_pdf, "PDF", resolution=150.0)


def render_comparison(
    *,
    case_dir: Path,
    matrix_path: Path,
    output_dir: Path,
    fps: int = 8,
    max_frames: int | None = None,
    write_mp4: bool = False,
    controller_order: tuple[str, ...] = CONTROLLER_ORDER,
    visualization_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if fps <= 0:
        raise ValueError("renderer fps must be positive")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")
    if write_mp4 and not mp4_supported():
        raise RuntimeError("MP4 requested but imageio-ffmpeg is unavailable")
    matrix = load_report_validation_matrix(matrix_path)
    expected_trace_sha256 = (
        {
            item["controller_id"]: item["trace_sha256"]
            for item in visualization_provenance["source_artifacts"]
        }
        if visualization_provenance is not None
        else None
    )
    comparison = load_comparison_case(
        case_dir,
        controller_order=controller_order,
        expected_trace_sha256=expected_trace_sha256,
    )
    prepare_fresh_output_directory(output_dir)
    patient_spec, _ = patient_spec_for_id(
        matrix, matrix_path, comparison["patient_id"]
    )
    human = patient_spec.build_human()
    plant = CoupledUR10eHumanV2(human)
    first_trace = comparison["arms"][controller_order[0]]["trace"]
    plant.reset(np.radians(first_trace["human_q_deg_god_view"][0]))
    panel_width, panel_height = 480, 320
    plant.model.vis.global_.offwidth = panel_width
    plant.model.vis.global_.offheight = panel_height
    renderer: mujoco.Renderer | None = None
    renderer_backend = "mujoco_fixed_camera"
    try:
        renderer = mujoco.Renderer(
            plant.model, height=panel_height, width=panel_width
        )
    except Exception as error:  # CGL is unavailable in headless macOS sessions.
        renderer_backend = f"mujoco_fk_schematic_fallback:{type(error).__name__}"
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.lookat[:] = np.array([0.48, -0.28, 0.42])
    camera.distance = 2.85
    camera.azimuth = -45.0
    camera.elevation = -21.0

    final_time = max(
        float(item["trace"]["time_s"][-1]) for item in comparison["arms"].values()
    )
    frame_count = max(2, int(np.floor(final_time * fps)) + 1)
    if max_frames is not None:
        frame_count = min(frame_count, int(max_frames))
    frame_times = np.linspace(0.0, final_time, frame_count)
    frames: list[np.ndarray] = []
    try:
        for frame_time in frame_times:
            panels: list[Image.Image] = []
            for controller_id in controller_order:
                item = comparison["arms"][controller_id]
                trace = item["trace"]
                time = np.asarray(trace["time_s"])
                index = int(np.clip(np.searchsorted(time, frame_time, side="right") - 1, 0, len(time) - 1))
                plant.data.qpos[plant.human_qpos_indices] = np.radians(
                    trace["human_q_deg_god_view"][index]
                )
                plant.data.qpos[plant.robot_qpos_indices] = trace["robot_q_rad"][index]
                plant.data.qvel[:] = 0.0
                mujoco.mj_forward(plant.model, plant.data)
                if renderer is None:
                    scene = _schematic_scene(
                        plant, width=panel_width, height=panel_height
                    )
                else:
                    renderer.update_scene(plant.data, camera=camera)
                    scene = Image.fromarray(renderer.render())
                panels.append(
                    _panel(
                        scene,
                        controller_id=controller_id,
                        summary=item["summary"],
                        trace=trace,
                        index=index,
                        frame_time_s=float(frame_time),
                        thigh_length_m=human.thigh_length_m,
                        shank_length_m=human.shank_length_m,
                        held_after_termination=frame_time > float(time[-1]) + 1e-12,
                    )
                )
            row_count = int(np.ceil(len(panels) / 2.0))
            composite = Image.new(
                "RGB", (2 * panel_width, row_count * panel_height), (13, 18, 25)
            )
            for index, panel in enumerate(panels):
                composite.paste(
                    panel, ((index % 2) * panel_width, (index // 2) * panel_height)
                )
            frames.append(np.asarray(composite))
    finally:
        if renderer is not None:
            renderer.close()

    gif_path = Path(output_dir) / "comparison.gif"
    still_path = Path(output_dir) / "representative_still.png"
    timeseries_png = Path(output_dir) / "metrics_timeseries.png"
    timeseries_pdf = Path(output_dir) / "metrics_timeseries.pdf"
    imageio.mimsave(gif_path, frames, duration=1.0 / fps, loop=0)
    Image.fromarray(frames[len(frames) // 2]).save(still_path)
    _timeseries(
        comparison,
        timeseries_png,
        timeseries_pdf,
        controller_order=controller_order,
    )
    outputs = {
        "gif": str(gif_path),
        "still": str(still_path),
        "timeseries_png": str(timeseries_png),
        "timeseries_pdf": str(timeseries_pdf),
        "mp4": None,
    }
    if write_mp4:
        mp4_path = Path(output_dir) / "comparison.mp4"
        imageio.mimsave(mp4_path, frames, fps=fps)
        outputs["mp4"] = str(mp4_path)
    manifest = {
        "schema_version": "stage4_report_validation_renderer_manifest_v1",
        "case_dir": str(Path(case_dir).resolve()),
        "patient_id": comparison["patient_id"],
        "trajectory_id": comparison["trajectory_id"],
        "controllers": list(controller_order),
        "reference_clock_sha256": comparison["reference_clock_sha256"],
        "synchronized_wall_time": True,
        "fixed_camera": True,
        "renderer_backend": renderer_backend,
        "reference_actual_leg_overlay": True,
        "frame_count": len(frames),
        "fps": fps,
        "mp4_dependency_available": mp4_supported(),
        "outputs": outputs,
        "scientific_interpretation_permitted": False,
    }
    if visualization_provenance is not None:
        manifest.update(visualization_provenance)
    write_strict_json(Path(output_dir) / "renderer_manifest.json", manifest)
    return manifest


def render_generalization_comparison(
    *,
    case_dir: Path,
    source_phase_manifest_path: Path,
    generalization_matrix_path: Path,
    output_dir: Path,
    fps: int = 8,
    max_frames: int | None = None,
    write_mp4: bool = False,
) -> dict[str, Any]:
    """Render exact saved generalization traces without relabelling them."""

    generalization_matrix_path = Path(generalization_matrix_path).resolve()
    matrix = load_generalization_matrix(generalization_matrix_path)
    source_phase_manifest_path = Path(source_phase_manifest_path).resolve()
    source_manifest = json.loads(
        source_phase_manifest_path.read_text(encoding="utf-8")
    )
    if source_manifest.get("generalization_config_sha256") != sha256_file(
        generalization_matrix_path
    ):
        raise ValueError("source phase manifest belongs to a different study config")
    case_dir = Path(case_dir).resolve()
    matching = [
        item
        for item in source_manifest["arms"]
        if Path(item["output_dir"]).resolve().parent == case_dir
    ]
    if not matching:
        raise ValueError("case directory is absent from source phase manifest")
    controllers = tuple(
        controller
        for controller in GENERALIZATION_CONTROLLER_ORDER
        if any(item["controller_id"] == controller for item in matching)
    )
    if len(controllers) != len(matching):
        raise ValueError("source phase manifest contains duplicate or unknown controllers")
    source_artifacts = []
    for controller in controllers:
        item = next(value for value in matching if value["controller_id"] == controller)
        trace_path = Path(item["trace_path"]).resolve()
        if trace_path != case_dir / controller / f"{controller}_trace.npz":
            raise ValueError("source trace path does not match the selected case")
        if sha256_file(trace_path) != item["trace_sha256"]:
            raise ValueError(f"source trace SHA-256 mismatch for {controller}")
        source_artifacts.append(
            {
                "controller_id": controller,
                "source_evidence_category": source_manifest["evidence_category"],
                "trace_path": str(trace_path),
                "trace_sha256": item["trace_sha256"],
                "controller_fingerprint_sha256": item[
                    "controller_fingerprint_sha256"
                ],
                "generalization_arm_fingerprint_sha256": item[
                    "generalization_arm_fingerprint_sha256"
                ],
            }
        )
    validation_path = report_root(generalization_matrix_path) / matrix[
        "source_artifacts"
    ]["report_validation_v2_config"]["path"]
    provenance = {
        "schema_version": "stage4_professor_report_visualization_manifest_v1",
        "evidence_category": VISUALIZATION_EVIDENCE_CATEGORY,
        "source_evidence_relabelled": False,
        "generalization_config_sha256": sha256_file(generalization_matrix_path),
        "metric_config_sha256": matrix["source_artifacts"]["metric_schema"][
            "sha256"
        ],
        "source_phase_manifest_path": str(source_phase_manifest_path),
        "source_phase_manifest_sha256": sha256_file(source_phase_manifest_path),
        "source_artifacts": source_artifacts,
    }
    return render_comparison(
        case_dir=case_dir,
        matrix_path=validation_path,
        output_dir=output_dir,
        fps=fps,
        max_frames=max_frames,
        write_mp4=write_mp4,
        controller_order=controllers,
        visualization_provenance=provenance,
    )


def _frozen_acceleration_series(
    trace: dict[str, np.ndarray], definitions: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    """Return the frozen 50 Hz combined acceleration magnitude for display."""

    contract = definitions["motion_quality"]
    method = contract["offline_derivative_method"]
    stride = int(contract["subsample_stride"])
    phase = int(contract["subsample_phase_index"])
    time = np.asarray(trace["control_time_s"], dtype=float)[phase::stride]
    velocity = np.asarray(trace["control_estimated_state"], dtype=float)[
        phase::stride, 2:4
    ]
    acceleration = savgol_filter(
        velocity,
        window_length=int(method["window_length_samples"]),
        polyorder=int(method["polynomial_order"]),
        deriv=int(method["acceleration_derivative_order"]),
        delta=float(method["delta_s"]),
        axis=0,
        mode=str(method["boundary_mode"]),
    )
    magnitude = np.linalg.norm(acceleration, axis=1)
    if not np.all(np.isfinite(magnitude)):
        raise ValueError("frozen display acceleration contains non-finite values")
    return time, magnitude


def load_manifest_media_panels(
    *,
    visualization_manifest_path: Path,
    generalization_matrix_path: Path,
    media_set_id: str,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Load and verify arbitrary manifest-selected trace panels."""

    visualization_manifest_path = Path(visualization_manifest_path).resolve()
    manifest = json.loads(
        visualization_manifest_path.read_text(encoding="utf-8")
    )
    generalization_matrix_path = Path(generalization_matrix_path).resolve()
    matrix = load_generalization_matrix(generalization_matrix_path)
    matrix_hash = sha256_file(generalization_matrix_path)
    if manifest.get("evidence_category") != VISUALIZATION_EVIDENCE_CATEGORY:
        raise ValueError("visualization manifest has the wrong media category")
    if manifest.get("source_evidence_relabelled") is not False:
        raise ValueError("source evidence must not be relabelled")
    if manifest.get("generalization_config_sha256") != matrix_hash:
        raise ValueError("visualization manifest belongs to another config")
    if media_set_id not in manifest.get("media_sets", {}):
        raise ValueError(f"unknown visualization media set: {media_set_id}")
    selected = list(manifest["media_sets"][media_set_id]["items"])
    if media_set_id == "patient_generalization_comparison":
        if scene_id is None:
            raise ValueError("patient generalization requires a patient scene id")
        selected = [item for item in selected if item["patient_id"] == scene_id]
    elif scene_id is not None:
        raise ValueError("scene id is only valid for patient generalization")
    expected_count = {
        "main_adaptation_comparison": 2,
        "patient_generalization_comparison": 3,
        "trajectory_generalization_comparison": 3,
    }.get(media_set_id)
    if expected_count is None or len(selected) != expected_count:
        raise ValueError("visualization scene contains the wrong panel count")
    definitions, _, metric_hash = load_metric_definitions(
        matrix, generalization_matrix_path
    )
    if manifest.get("metric_config_sha256") != metric_hash:
        raise ValueError("visualization manifest metric hash mismatch")
    panels = []
    for item in selected:
        trace_path = Path(item["source_trace_path"]).resolve()
        summary_path = Path(item["source_summary_path"]).resolve()
        controller = item["controller_id"]
        if not trace_path.is_file() or not summary_path.is_file():
            raise FileNotFoundError(f"missing visualization source for {controller}")
        if sha256_file(trace_path) != item["source_trace_sha256"]:
            raise ValueError(f"source trace SHA-256 mismatch for {controller}")
        expected_trace_path = trace_path.parent / f"{controller}_trace.npz"
        expected_summary_path = trace_path.parent / f"{controller}.json"
        if trace_path != expected_trace_path or summary_path != expected_summary_path:
            raise ValueError("manifest source paths do not match the arm layout")
        loaded = _load_arm(
            trace_path.parent.parent,
            controller,
            expected_trace_sha256=item["source_trace_sha256"],
        )
        provenance = loaded["provenance"]
        for key, expected in (
            ("patient", item["patient_id"]),
            ("trajectory", item["trajectory_id"]),
            ("controller", controller),
            ("measurement_seed", int(item["measurement_seed"])),
            ("evidence_category", item["source_evidence_category"]),
            (
                "controller_fingerprint_sha256",
                item["controller_fingerprint_sha256"],
            ),
            ("generalization_config_sha256", matrix_hash),
            ("generalization_metric_config_sha256", metric_hash),
        ):
            if provenance.get(key) != expected:
                raise ValueError(f"manifest/provenance mismatch at {key}")
        if (
            item.get("intended_media_evidence_category")
            != VISUALIZATION_EVIDENCE_CATEGORY
            or item.get("source_evidence_relabelled") is not False
        ):
            raise ValueError("invalid source/media evidence separation")
        acceleration_time, acceleration_magnitude = _frozen_acceleration_series(
            loaded["trace"], definitions
        )
        panels.append(
            {
                **loaded,
                "source": item,
                "patient_id": item["patient_id"],
                "trajectory_id": item["trajectory_id"],
                "controller_id": controller,
                "measurement_seed": int(item["measurement_seed"]),
                "acceleration_time_s": acceleration_time,
                "acceleration_magnitude_rad_s2": acceleration_magnitude,
            }
        )
    if media_set_id == "trajectory_generalization_comparison":
        labels = [item["trajectory_id"] for item in panels]
    else:
        labels = [CONTROLLER_LABELS[item["controller_id"]] for item in panels]
    return {
        "media_set_id": media_set_id,
        "scene_id": scene_id,
        "layout": manifest["media_sets"][media_set_id]["layout"],
        "panels": panels,
        "panel_labels": labels,
        "visualization_manifest_path": str(visualization_manifest_path),
        "visualization_manifest_sha256": sha256_file(visualization_manifest_path),
        "generalization_matrix_path": str(generalization_matrix_path),
        "generalization_config_sha256": matrix_hash,
        "metric_config_sha256": metric_hash,
        "validation_matrix_path": str(
            (
                report_root(generalization_matrix_path)
                / matrix["source_artifacts"]["report_validation_v2_config"]["path"]
            ).resolve()
        ),
    }


def _safety_event_count(summary: dict[str, Any]) -> int:
    metrics = summary["report_generalization_metrics"]
    events = metrics["safety_and_constraint_events"]
    return int(
        int(events.get("force_gate_events", 0))
        + int(events.get("rom_event_samples", 0))
        + int(events.get("mpc_solver_failures", 0))
        + len(events.get("unintended_contact_pairs", []))
        + sum(int(value) for value in events.get("mujoco_warning_counts", {}).values())
    )


def _summary_card(
    *, panel: dict[str, Any], label: str, width: int, height: int
) -> Image.Image:
    card = Image.new("RGB", (width, height), (19, 25, 34))
    draw = ImageDraw.Draw(card)
    metrics = panel["summary"]["report_generalization_metrics"]
    draw.text((24, 24), label, font=_font(19, bold=True), fill=(244, 248, 252))
    draw.text(
        (24, 52),
        panel["patient_id"],
        font=_font(11),
        fill=(164, 183, 201),
    )
    rows = (
        ("Tracking RMSE", f"{float(metrics['tracking_rmse_deg']):.3f} deg"),
        ("Max tracking error", f"{float(metrics['tracking_max_error_deg']):.3f} deg"),
        (
            "Acceleration RMS",
            f"{float(metrics['combined_acceleration_rms_rad_s2']):.3f} rad/s2",
        ),
        ("Peak cuff force", f"{float(metrics['cuff_force_peak_n']):.1f} N"),
        (
            "Margin to 200 N",
            f"{float(metrics['minimum_force_gate_margin_n']):.1f} N",
        ),
        ("Safety events", str(_safety_event_count(panel["summary"]))),
    )
    y = 91
    for name, value in rows:
        draw.text((30, y), name, font=_font(12), fill=(190, 202, 214))
        draw.text((width - 205, y), value, font=_font(12, bold=True), fill=(245, 248, 252))
        y += 29
    if panel["controller_id"] == "trusted_adaptive_mpc":
        first = metrics.get("adaptive_first_promotion_wall_time_s")
        promotion = "No promotion" if first is None else f"{float(first):.2f} s"
        draw.text((30, y + 4), "First promotion", font=_font(12), fill=(190, 202, 214))
        draw.text((width - 205, y + 4), promotion, font=_font(12, bold=True), fill=(65, 206, 126))
    draw.text(
        (24, height - 30),
        "Simulation visualization; promoted model is control-effective, not anatomy truth.",
        font=_font(9),
        fill=(142, 158, 174),
    )
    return card


def _manifest_timeseries(
    scene: dict[str, Any], output_png: Path, output_pdf: Path
) -> None:
    width, height = 980, 760
    canvas = Image.new("RGB", (width, height), (250, 251, 252))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (40, 18),
        f"{scene['media_set_id']} | descriptive simulation visualization",
        font=_font(18, bold=True),
        fill=(28, 37, 47),
    )
    colors = ("#7d3c98", "#2471a3", "#239b56")
    series = []
    final_time = 0.0
    for panel in scene["panels"]:
        trace = panel["trace"]
        time = np.asarray(trace["time_s"], dtype=float)
        error = np.linalg.norm(trace["tracking_error_deg_god_view"], axis=1)
        force = np.linalg.norm(
            np.asarray(trace["cuff_wrench_local_god_view"], dtype=float)[:, :3],
            axis=1,
        )
        acceleration = np.interp(
            time,
            panel["acceleration_time_s"],
            panel["acceleration_magnitude_rad_s2"],
        )
        series.append((time, error, force, acceleration))
        final_time = max(final_time, float(time[-1]))
    specs = (
        ("tracking error [deg]", 1),
        ("cuff |F| [N]", 2),
        ("combined |a| [rad/s2]", 3),
    )
    for plot_index, (label, value_index) in enumerate(specs):
        box = (115, 85 + 205 * plot_index, 935, 245 + 205 * plot_index)
        draw.rectangle(box, outline=(112, 126, 140), width=1)
        draw.text((15, box[1] + 65), label, font=_font(11), fill=(49, 60, 72))
        maximum = max(float(np.max(item[value_index])) for item in series)
        maximum = max(maximum, 1e-9)
        for panel_index, (panel, values) in enumerate(
            zip(scene["panels"], series, strict=True)
        ):
            time = values[0]
            samples = values[value_index]
            if len(samples) > 820:
                indices = np.linspace(0, len(samples) - 1, 820).astype(int)
                time = time[indices]
                samples = samples[indices]
            xs = box[0] + (box[2] - box[0]) * time / max(final_time, 1e-12)
            ys = box[3] - (box[3] - box[1]) * samples / maximum
            points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]
            if len(points) >= 2:
                draw.line(points, fill=colors[panel_index], width=2)
            promotion = panel["summary"]["report_generalization_metrics"].get(
                "adaptive_first_promotion_wall_time_s"
            )
            if promotion is not None:
                x = box[0] + (box[2] - box[0]) * float(promotion) / max(final_time, 1e-12)
                draw.line((x, box[1], x, box[3]), fill=colors[panel_index], width=1)
        draw.text((box[0] + 4, box[1] + 3), f"max {maximum:.3g}", font=_font(9), fill=(92, 104, 116))
    legend_x = 115
    for index, label in enumerate(scene["panel_labels"]):
        draw.line((legend_x, 61, legend_x + 22, 61), fill=colors[index], width=3)
        draw.text((legend_x + 27, 54), label, font=_font(9), fill=(49, 60, 72))
        legend_x += 270
    draw.text((460, 715), "wall time [s]", font=_font(12), fill=(49, 60, 72))
    canvas.save(output_png)
    canvas.save(output_pdf, "PDF", resolution=150.0)


def render_manifest_media_set(
    *,
    visualization_manifest_path: Path,
    generalization_matrix_path: Path,
    media_set_id: str,
    output_dir: Path,
    scene_id: str | None = None,
    fps: int = 8,
    max_frames: int | None = None,
    write_mp4: bool = False,
    render_classification: str = VISUALIZATION_EVIDENCE_CATEGORY,
    generation_timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Render a verified manifest-selected multi-source media set."""

    if fps <= 0 or (max_frames is not None and max_frames <= 0):
        raise ValueError("renderer frame controls must be positive")
    if write_mp4 and not mp4_supported():
        raise RuntimeError("MP4 requested but imageio-ffmpeg is unavailable")
    if render_classification not in {
        VISUALIZATION_EVIDENCE_CATEGORY,
        RENDERER_SMOKE_CATEGORY,
    }:
        raise ValueError("unsupported renderer classification")
    scene = load_manifest_media_panels(
        visualization_manifest_path=visualization_manifest_path,
        generalization_matrix_path=generalization_matrix_path,
        media_set_id=media_set_id,
        scene_id=scene_id,
    )
    prepare_fresh_output_directory(output_dir)
    validation_matrix_path = Path(scene["validation_matrix_path"])
    validation_matrix = load_report_validation_matrix(validation_matrix_path)
    panel_width, panel_height = 480, 320
    renderers: list[mujoco.Renderer | None] = []
    plants = []
    humans = []
    backend_names = []
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.lookat[:] = np.array([0.48, -0.28, 0.42])
    camera.distance = 2.85
    camera.azimuth = -45.0
    camera.elevation = -21.0
    for panel in scene["panels"]:
        patient, _ = patient_spec_for_id(
            validation_matrix, validation_matrix_path, panel["patient_id"]
        )
        human = patient.build_human()
        plant = CoupledUR10eHumanV2(human)
        plant.reset(np.radians(panel["trace"]["human_q_deg_god_view"][0]))
        plant.model.vis.global_.offwidth = panel_width
        plant.model.vis.global_.offheight = panel_height
        try:
            renderer = mujoco.Renderer(
                plant.model, height=panel_height, width=panel_width
            )
            backend = "mujoco_fixed_camera"
        except Exception as error:
            renderer = None
            backend = f"mujoco_fk_schematic_fallback:{type(error).__name__}"
        plants.append(plant)
        humans.append(human)
        renderers.append(renderer)
        backend_names.append(backend)
    final_time = max(
        float(panel["trace"]["time_s"][-1]) for panel in scene["panels"]
    )
    motion_frame_count = max(2, int(np.floor(final_time * fps)) + 1)
    if max_frames is not None:
        motion_frame_count = min(motion_frame_count, int(max_frames))
    frame_times = np.linspace(0.0, final_time, motion_frame_count)
    first_promotions = [
        panel["summary"]["report_generalization_metrics"].get(
            "adaptive_first_promotion_wall_time_s"
        )
        for panel in scene["panels"]
    ]
    first_promotions = [float(value) for value in first_promotions if value is not None]
    if first_promotions and len(frame_times) >= 3:
        target = min(first_promotions)
        index = int(np.argmin(np.abs(frame_times[1:-1] - target))) + 1
        frame_times[index] = target
        frame_times = np.sort(frame_times)
    frames: list[np.ndarray] = []
    try:
        for frame_time in frame_times:
            images = []
            for index, panel in enumerate(scene["panels"]):
                trace = panel["trace"]
                time = np.asarray(trace["time_s"], dtype=float)
                sample = int(
                    np.clip(
                        np.searchsorted(time, frame_time, side="right") - 1,
                        0,
                        len(time) - 1,
                    )
                )
                plant = plants[index]
                plant.data.qpos[plant.human_qpos_indices] = np.radians(
                    trace["human_q_deg_god_view"][sample]
                )
                plant.data.qpos[plant.robot_qpos_indices] = trace["robot_q_rad"][sample]
                plant.data.qvel[:] = 0.0
                mujoco.mj_forward(plant.model, plant.data)
                renderer = renderers[index]
                if renderer is None:
                    base = _schematic_scene(
                        plant, width=panel_width, height=panel_height
                    )
                else:
                    renderer.update_scene(plant.data, camera=camera)
                    base = Image.fromarray(renderer.render())
                live_acceleration = float(
                    np.interp(
                        frame_time,
                        panel["acceleration_time_s"],
                        panel["acceleration_magnitude_rad_s2"],
                    )
                )
                images.append(
                    _panel(
                        base,
                        controller_id=panel["controller_id"],
                        summary=panel["summary"],
                        trace=trace,
                        index=sample,
                        frame_time_s=float(frame_time),
                        thigh_length_m=humans[index].thigh_length_m,
                        shank_length_m=humans[index].shank_length_m,
                        held_after_termination=frame_time > float(time[-1]) + 1e-12,
                        panel_label=scene["panel_labels"][index],
                        patient_label=panel["patient_id"],
                        live_acceleration_rad_s2=live_acceleration,
                    )
                )
            composite = Image.new(
                "RGB", (len(images) * panel_width, panel_height), (13, 18, 25)
            )
            for index, panel_image in enumerate(images):
                composite.paste(panel_image, (index * panel_width, 0))
            frames.append(np.asarray(composite))
    finally:
        for renderer in renderers:
            if renderer is not None:
                renderer.close()
    cards = [
        _summary_card(
            panel=panel,
            label=scene["panel_labels"][index],
            width=panel_width,
            height=panel_height,
        )
        for index, panel in enumerate(scene["panels"])
    ]
    end_card = Image.new(
        "RGB", (len(cards) * panel_width, panel_height), (13, 18, 25)
    )
    for index, card in enumerate(cards):
        end_card.paste(card, (index * panel_width, 0))
    end_card_frame_count = max(1, int(round(1.5 * fps)))
    frames.extend([np.asarray(end_card)] * end_card_frame_count)
    output_dir = Path(output_dir)
    gif_path = output_dir / "comparison.gif"
    still_path = output_dir / "representative_still.png"
    end_card_path = output_dir / "end_summary_card.png"
    timeseries_png = output_dir / "metrics_timeseries.png"
    timeseries_pdf = output_dir / "metrics_timeseries.pdf"
    imageio.mimsave(gif_path, frames, duration=1.0 / fps, loop=0)
    Image.fromarray(frames[max(0, motion_frame_count // 2)]).save(still_path)
    end_card.save(end_card_path)
    _manifest_timeseries(scene, timeseries_png, timeseries_pdf)
    outputs: dict[str, str | None] = {
        "gif": str(gif_path),
        "representative_still_png": str(still_path),
        "end_summary_card_png": str(end_card_path),
        "timeseries_png": str(timeseries_png),
        "timeseries_pdf": str(timeseries_pdf),
        "mp4": None,
    }
    if write_mp4:
        mp4_path = output_dir / "comparison.mp4"
        imageio.mimsave(mp4_path, frames, fps=fps)
        outputs["mp4"] = str(mp4_path)
    timestamp = generation_timestamp_utc or datetime.now(timezone.utc).isoformat()
    renderer_payload = {
        "renderer_version": RENDERER_VERSION,
        "fixed_camera": True,
        "fixed_panel_size": [panel_width, panel_height],
        "fps": fps,
        "live_acceleration_processing": "frozen_50_hz_savgol_acceleration_derivative_order_1",
        "live_overlay_fields": [
            "panel_label",
            "patient_label",
            "instantaneous_tracking_error_deg",
            "instantaneous_cuff_force_magnitude_n",
            "frozen_50_hz_acceleration_magnitude_rad_s2",
            "prior_or_adaptive_model_state",
            "first_promotion_marker_and_time",
        ],
        "live_overlay_excluded": [
            "cuff_moment",
            "jerk",
            "robot_torque",
            "prediction_rmse",
            "static_acceleration_rms",
        ],
        "end_card_duration_s": 1.5,
    }
    source_artifacts = []
    for index, panel in enumerate(scene["panels"]):
        metrics = panel["summary"]["report_generalization_metrics"]
        source_artifacts.append({
            "patient_id": panel["patient_id"],
            "trajectory_id": panel["trajectory_id"],
            "controller_id": panel["controller_id"],
            "measurement_seed": panel["measurement_seed"],
            "source_evidence_category": panel["source"]["source_evidence_category"],
            "source_trace_path": panel["source"]["source_trace_path"],
            "source_trace_sha256": panel["source"]["source_trace_sha256"],
            "controller_fingerprint_sha256": panel["source"][
                "controller_fingerprint_sha256"
            ],
            "rendered_human_geometry": {
                "thigh_length_m": float(humans[index].thigh_length_m),
                "shank_length_m": float(humans[index].shank_length_m),
            },
            "end_summary": {
                "tracking_rmse_deg": float(metrics["tracking_rmse_deg"]),
                "tracking_max_error_deg": float(metrics["tracking_max_error_deg"]),
                "combined_acceleration_rms_rad_s2": float(
                    metrics["combined_acceleration_rms_rad_s2"]
                ),
                "cuff_force_peak_n": float(metrics["cuff_force_peak_n"]),
                "minimum_force_gate_margin_n": float(
                    metrics["minimum_force_gate_margin_n"]
                ),
                "safety_event_count": _safety_event_count(panel["summary"]),
                "adaptive_first_promotion_wall_time_s": metrics.get(
                    "adaptive_first_promotion_wall_time_s"
                ),
            },
        })
    output_hashes = {
        key: sha256_file(Path(path))
        for key, path in outputs.items()
        if path is not None
    }
    manifest = {
        "schema_version": "stage4_professor_report_manifest_renderer_output_v1",
        "media_evidence_category": VISUALIZATION_EVIDENCE_CATEGORY,
        "render_classification": render_classification,
        "scientific_interpretation_permitted": False,
        "visualization_source_manifest_path": scene[
            "visualization_manifest_path"
        ],
        "visualization_source_manifest_sha256": scene[
            "visualization_manifest_sha256"
        ],
        "source_evidence_relabelled": False,
        "media_set_id": media_set_id,
        "scene_id": scene_id,
        "layout": scene["layout"],
        "source_artifacts": source_artifacts,
        "renderer": renderer_payload,
        "renderer_fingerprint_sha256": canonical_json_sha256(renderer_payload),
        "generation_timestamp_utc": timestamp,
        "renderer_backends": backend_names,
        "motion_frame_count": motion_frame_count,
        "end_card_frame_count": end_card_frame_count,
        "outputs": outputs,
        "output_sha256": output_hashes,
        "mp4_dependency_available": mp4_supported(),
    }
    write_strict_json(output_dir / "renderer_manifest.json", manifest)
    return manifest
