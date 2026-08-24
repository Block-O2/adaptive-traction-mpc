"""Professor-facing GIF rendering for the Stage-4 one-shot adaptive rollout."""

from __future__ import annotations

import json
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .cold_start import Stage4CoupledPlant, _true_case


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
            continue
    return ImageFont.load_default()


def _sparkline(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    values: np.ndarray,
    index: int,
    color: tuple[int, int, int],
    limit: float,
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=5, fill=(28, 35, 45), outline=(67, 78, 92))
    if index < 2:
        return
    start = max(0, index - 3000)
    samples = np.asarray(values[start : index + 1], dtype=float)
    if len(samples) > x1 - x0 - 8:
        sample_indices = np.linspace(0, len(samples) - 1, x1 - x0 - 8).astype(int)
        samples = samples[sample_indices]
    scale = max(float(limit), 1e-9)
    xs = np.linspace(x0 + 4, x1 - 4, len(samples))
    normalized = np.clip(samples / scale, 0.0, 1.0)
    ys = y1 - 4 - normalized * (y1 - y0 - 8)
    points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]
    if len(points) >= 2:
        draw.line(points, fill=color, width=2)


def render_one_shot_gif(
    summary_path: Path,
    trace_path: Path,
    output_path: Path,
    *,
    fps: int = 8,
    preview_path: Path | None = None,
) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with np.load(trace_path) as archive:
        trace = {name: archive[name] for name in archive.files}
    true_human, _ = _true_case(summary["true_human_case"])
    plant = Stage4CoupledPlant(true_human)
    plant.reset(np.radians(trace["human_q_deg_god_view"][0]))
    # Presentation-only framebuffer capacity; this does not alter dynamics,
    # contacts, controller state, or the recorded rollout.
    plant.model.vis.global_.offwidth = 720
    plant.model.vis.global_.offheight = 500
    renderer = mujoco.Renderer(plant.model, height=500, width=720)
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.lookat[:] = np.array([0.48, -0.28, 0.42])
    camera.distance = 2.85
    camera.azimuth = -45.0
    camera.elevation = -21.0

    time = trace["time_s"]
    force_norm = np.linalg.norm(trace["cuff_force_local_n"], axis=1)
    parasitic = np.linalg.norm(trace["cuff_force_local_n"][:, 1:], axis=1)
    torque_fraction = trace["robot_torque_limit_fraction"]
    tracking_error = np.linalg.norm(
        trace["human_q_deg_god_view"] - trace["human_q_ref_deg"], axis=1
    )
    geometry_time = summary["geometry_identifier"]["trustworthy_time_s"]
    dynamic_time = summary["dynamic_identifier"]["trustworthy_time_s"]
    simulation_dt = float(np.median(np.diff(time)))
    frame_stride = max(1, int(round(1.0 / (fps * simulation_dt))))
    frame_indices = list(range(0, len(time), frame_stride))
    if frame_indices[-1] != len(time) - 1:
        frame_indices.append(len(time) - 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(output_path, mode="I", duration=1.0 / fps, loop=0)
    first_composite: Image.Image | None = None
    title_font = _font(20, bold=True)
    header_font = _font(15, bold=True)
    body_font = _font(14)
    small_font = _font(12)
    try:
        for frame_index in frame_indices:
            plant.data.qpos[plant.human_qpos_indices] = np.radians(
                trace["human_q_deg_god_view"][frame_index]
            )
            plant.data.qpos[plant.robot_qpos_indices] = trace["robot_q_rad"][frame_index]
            plant.data.qvel[:] = 0.0
            mujoco.mj_forward(plant.model, plant.data)
            renderer.update_scene(plant.data, camera=camera)
            scene = Image.fromarray(renderer.render())
            composite = Image.new("RGB", (1000, 500), (18, 23, 31))
            composite.paste(scene, (0, 0))
            draw = ImageDraw.Draw(composite)
            draw.rectangle((720, 0, 999, 499), fill=(18, 23, 31))
            draw.text((738, 16), "STAGE 4  |  ONE-SHOT", font=title_font, fill=(240, 245, 250))
            draw.text((738, 43), "Population-prior Adaptive MPC", font=header_font, fill=(94, 201, 255))
            current_time = float(time[frame_index])
            draw.text((738, 72), f"t = {current_time:5.2f} s", font=header_font, fill=(235, 238, 242))
            actual = trace["human_q_deg_god_view"][frame_index]
            target = trace["human_q_ref_deg"][frame_index]
            draw.text((738, 102), f"Hip   {actual[0]:5.1f} / {target[0]:5.1f} deg", font=body_font, fill=(255, 201, 92))
            draw.text((738, 124), f"Knee  {actual[1]:5.1f} / {target[1]:5.1f} deg", font=body_font, fill=(255, 201, 92))
            draw.text((738, 154), f"Cuff |F|       {force_norm[frame_index]:6.1f} N", font=body_font, fill=(126, 231, 135))
            draw.text((738, 176), f"Parasitic F    {parasitic[frame_index]:6.1f} N", font=body_font, fill=(255, 146, 123))
            draw.text((738, 198), f"Robot torque   {100.0 * torque_fraction[frame_index]:6.1f} %", font=body_font, fill=(177, 156, 255))
            geometry_status = "TRUSTED" if geometry_time is not None and current_time >= geometry_time else "PRIOR / LEARNING"
            dynamic_status = "TRUSTED" if dynamic_time is not None and current_time >= dynamic_time else "PRIOR / LEARNING"
            draw.text((738, 230), f"Geometry: {geometry_status}", font=small_font, fill=(126, 231, 135) if geometry_status == "TRUSTED" else (210, 214, 220))
            draw.text((738, 250), f"Dynamics: {dynamic_status}", font=small_font, fill=(126, 231, 135) if dynamic_status == "TRUSTED" else (210, 214, 220))
            draw.text((738, 282), "Live history", font=header_font, fill=(235, 238, 242))
            _sparkline(draw, (738, 309, 982, 348), tracking_error, frame_index, (255, 201, 92), 2.0)
            draw.text((744, 313), "tracking error", font=small_font, fill=(220, 224, 230))
            _sparkline(draw, (738, 359, 982, 398), force_norm, frame_index, (126, 231, 135), 200.0)
            draw.text((744, 363), "cuff force / 200 N gate", font=small_font, fill=(220, 224, 230))
            _sparkline(draw, (738, 409, 982, 448), torque_fraction, frame_index, (177, 156, 255), 1.0)
            draw.text((744, 413), "robot torque fraction", font=small_font, fill=(220, 224, 230))
            draw.text((738, 470), "UR10e = simulation surrogate", font=small_font, fill=(174, 183, 194))
            if first_composite is None:
                first_composite = composite.copy()
            writer.append_data(np.asarray(composite))
    finally:
        writer.close()
        renderer.close()
    if preview_path is not None and first_composite is not None:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        first_composite.save(preview_path)
