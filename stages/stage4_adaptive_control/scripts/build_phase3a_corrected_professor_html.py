#!/usr/bin/env python3
"""Build the corrected single-file Phase-3A professor report.

The builder reads frozen saved states, renders them without advancing the
simulation, and embeds every video, figure, datum, style, and script in one
offline HTML file.  It never invokes MPC or runs a trajectory.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

import imageio.v2 as imageio
import imageio_ffmpeg
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
EVIDENCE = STAGE / "results/engineering_validation"
SUMMARY = STAGE / "results/summaries/phase3a_corrected_high_rom"
REPORT_SOURCES = SUMMARY / "report_sources"
OUTPUT = EVIDENCE / "PHASE3A_RIGID_VS_P1_PROFESSOR_REVIEW.html"
EVIDENCE_CHECKPOINT = "57633f4c6e3bd518f56964e7807e9d54dadb2058"
INITIAL_Q_DEG = np.array([5.0, 10.0])
CASES = {
    "40/80": {
        "rigid": REPORT_SOURCES / "40_80_rigid.npz",
        "P1": REPORT_SOURCES / "40_80_p1.npz",
        "endpoint": [40.0, 80.0],
        "primary": True,
    },
    "90/120": {
        "rigid": REPORT_SOURCES / "90_120_rigid.npz",
        "P1": REPORT_SOURCES / "90_120_p1.npz",
        "endpoint": [90.0, 120.0],
        "primary": False,
    },
    "120/120": {
        "rigid": REPORT_SOURCES / "120_120_rigid.npz",
        "P1": REPORT_SOURCES / "120_120_p1.npz",
        "endpoint": [120.0, 120.0],
        "primary": False,
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def load_cases() -> dict[str, dict[str, Any]]:
    reviewed = json.loads((SUMMARY / "corrected_baseline_comparison.json").read_text())["pairs"]
    cases: dict[str, dict[str, Any]] = {}
    for label, config in CASES.items():
        arms = {}
        for arm_name in ("rigid", "P1"):
            source = config[arm_name]
            compact = load_npz(source)
            arms[arm_name] = {
                "source": source,
                "trace": {
                    "time_s": compact["video_time_s"],
                    "human_q_deg_god_view": compact["video_human_q_deg"],
                    "human_q_ref_deg": compact["video_human_q_ref_deg"],
                    "reference_phase_time_s": compact["video_reference_phase_time_s"],
                    "executed_command_time_s": compact["video_time_s"],
                    "executed_command_force_total_n": compact["video_command_force_n"],
                    "robot_q_rad": compact["video_robot_q_rad"],
                },
                "mechanics": {
                    "time_s": compact["video_time_s"],
                    "force_R_world": compact["video_physical_force_n"],
                    "deformation_H": compact["video_deformation_H"],
                },
                "modes": {
                    "time_s": compact["video_time_s"],
                    "mode": compact["video_mode"],
                    "safety_filter_status": compact["video_safety_filter_status"],
                },
                "tracking": {
                    "time_s": compact["tracking_time_s"],
                    "q_deg": compact["tracking_q_deg"],
                    "ref_deg": compact["tracking_ref_deg"],
                },
                "force_overlay": {
                    "q_deg": compact["force_overlay_q_deg"],
                    "force_n": compact["force_overlay_force_n"],
                },
                # The reviewed aggregate adds postprocessed physical progress
                # to the hash-locked reused 40/80 Rigid result.
                "result": reviewed[label][arm_name],
            }
        cases[label] = {
            "label": label,
            "endpoint": np.asarray(config["endpoint"], dtype=float),
            "primary": bool(config["primary"]),
            "arms": arms,
        }
    return cases


def latest_index(times: np.ndarray, target: float) -> int:
    return int(np.clip(np.searchsorted(times, target, side="right") - 1, 0, len(times) - 1))


def display_mode(arm: dict[str, Any], time_s: float) -> str:
    modes = arm["modes"]
    index = latest_index(modes["time_s"], time_s)
    if str(modes["mode"][index]) == "BRAKE":
        return "BRAKE"
    status = str(modes["safety_filter_status"][index])
    if status == "SAFE_FILTERED":
        return "SAFE_FILTERED"
    if status == "FILTER_INFEASIBLE":
        return "BRAKE"
    return "TRACK"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    choices = [
        "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for name in choices:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def panel_overlay(scene: np.ndarray, case: dict[str, Any], arm_name: str, time_s: float) -> Image.Image:
    arm = case["arms"][arm_name]
    trace, mechanics = arm["trace"], arm["mechanics"]
    index = latest_index(trace["time_s"], time_s)
    mi = latest_index(mechanics["time_s"], time_s)
    ci = latest_index(trace["executed_command_time_s"], time_s)
    q = trace["human_q_deg_god_view"][index]
    ref = trace["human_q_ref_deg"][index]
    error = float(np.linalg.norm(q - ref))
    physical = float(np.linalg.norm(mechanics["force_R_world"][mi]))
    command = float(np.linalg.norm(trace["executed_command_force_total_n"][ci]))
    progress = 100.0 * np.clip(
        float(trace["reference_phase_time_s"][index]) / float(arm["result"]["planned_reference_duration_s"]),
        0.0,
        1.0,
    )
    deformation = 1000.0 * float(np.linalg.norm(mechanics["deformation_H"][mi])) if arm_name == "P1" else 0.0
    mode = display_mode(arm, time_s)
    colors = {"TRACK": (36, 128, 81), "SAFE_FILTERED": (178, 112, 0), "BRAKE": (182, 45, 55)}
    image = Image.fromarray(scene).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    draw.rectangle((0, 0, width, 108), fill=(255, 255, 255, 238))
    draw.line((0, 108, width, 108), fill=(45, 53, 59, 220), width=1)
    label = "Rigid NEW" if arm_name == "rigid" else "P1 NEW"
    draw.text((14, 9), label, font=font(18, True), fill=(18, 22, 25))
    bounds = draw.textbbox((0, 0), mode, font=font(13, True))
    badge_width = bounds[2] - bounds[0] + 18
    draw.rounded_rectangle((width - badge_width - 12, 8, width - 12, 33), radius=5, fill=(*colors[mode], 235))
    draw.text((width - badge_width - 3, 12), mode, font=font(13, True), fill=(255, 255, 255))
    draw.text((14, 39), f"q=[{q[0]:5.1f}, {q[1]:5.1f}]°   q_ref=[{ref[0]:5.1f}, {ref[1]:5.1f}]°", font=font(13), fill=(18, 22, 25))
    draw.text((14, 62), f"跟踪误差={error:5.2f}°   物理力={physical:6.1f} N   指令力={command:6.1f} N", font=font(13), fill=(18, 22, 25))
    deform_text = f"P1 变形={deformation:5.3f} mm" if arm_name == "P1" else "刚性接口"
    draw.text((14, 85), f"参考进度={progress:5.1f}%   {deform_text}", font=font(13), fill=(18, 22, 25))
    draw.rectangle((10, height - 8, width - 10, height - 4), fill=(210, 216, 220, 255))
    draw.rectangle((10, height - 8, 10 + (width - 20) * progress / 100.0, height - 4), fill=(*colors[mode], 255))
    return image


def render_case_video(case: dict[str, Any], plant: Any, temp_dir: Path) -> dict[str, Any]:
    primary = case["primary"]
    panel_width, panel_height = ((560, 390) if primary else (480, 340))
    fps = 10 if primary else 8
    plant.model.vis.global_.offwidth = panel_width
    plant.model.vis.global_.offheight = panel_height
    renderer = mujoco.Renderer(plant.model, height=panel_height, width=panel_width)
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.lookat[:] = np.array([0.48, -0.28, 0.42])
    camera.distance = 2.85
    camera.azimuth = -45.0
    camera.elevation = -21.0
    final_time = max(float(case["arms"][name]["trace"]["time_s"][-1]) for name in ("rigid", "P1"))
    frame_times = np.linspace(0.0, final_time, max(2, int(np.floor(final_time * fps)) + 1))
    video_path = temp_dir / f"corrected_{case['label'].replace('/', '_')}.mp4"
    writer = imageio.get_writer(
        video_path,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=None,
        ffmpeg_log_level="error",
        ffmpeg_params=["-crf", "29" if primary else "30", "-preset", "medium", "-movflags", "+faststart", "-an"],
    )
    poster = None
    try:
        for number, frame_time in enumerate(frame_times):
            panels = []
            for arm_name in ("rigid", "P1"):
                arm = case["arms"][arm_name]
                source_time = np.asarray(arm["trace"]["time_s"])
                sample_time = min(float(frame_time), float(source_time[-1]))
                index = latest_index(source_time, sample_time)
                plant.data.qpos[plant.human_qpos_indices] = np.radians(arm["trace"]["human_q_deg_god_view"][index])
                plant.data.qpos[plant.robot_qpos_indices] = arm["trace"]["robot_q_rad"][index]
                plant.data.qvel[:] = 0.0
                mujoco.mj_forward(plant.model, plant.data)
                renderer.update_scene(plant.data, camera=camera)
                panels.append(panel_overlay(renderer.render(), case, arm_name, sample_time))
            composite = Image.new("RGB", (2 * panel_width, panel_height), (255, 255, 255))
            composite.paste(panels[0], (0, 0))
            composite.paste(panels[1], (panel_width, 0))
            if poster is None:
                stream = io.BytesIO()
                composite.save(stream, format="JPEG", quality=80, optimize=True)
                poster = base64.b64encode(stream.getvalue()).decode("ascii")
            writer.append_data(np.asarray(composite))
            if number and number % max(1, len(frame_times) // 4) == 0:
                print(f"VIDEO {case['label']} {100 * number / len(frame_times):.0f}%", flush=True)
    finally:
        writer.close()
        renderer.close()
    frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(video_path))
    return {
        "data_uri": "data:video/mp4;base64," + base64.b64encode(video_path.read_bytes()).decode("ascii"),
        "poster_uri": "data:image/jpeg;base64," + poster,
        "byte_size": video_path.stat().st_size,
        "fps": fps,
        "frames": int(frames),
        "duration_s": float(seconds),
        "dimensions": [2 * panel_width, panel_height],
        "sha256": sha256(video_path),
    }


def compact_result(result: dict[str, Any], arm_name: str) -> dict[str, Any]:
    progress = result["physical_trajectory_completion"]
    counts = result["brake"]["safety_filter_status_counts"]
    data = {
        "formal": result["task"],
        "tracking": result["tracking_rmse_deg"],
        "endpoint": result["endpoint_error_deg"],
        "return": result["return_error_deg"],
        "outbound": progress["outbound_percent"],
        "return_pct": progress["return_percent"],
        "human_rms": result["control_feedback"]["human_level_allocator_force_n"]["rms"],
        "human_peak": result["control_feedback"]["human_level_allocator_force_n"]["peak"],
        "position_peak": result["control_feedback"]["position_force_n"]["peak"],
        "velocity_peak": result["control_feedback"]["velocity_force_n"]["peak"],
        "nominal_peak": result["nominal_executable_force_before_filter_n"]["peak"],
        "command_peak": result["command_force_n"]["peak"],
        "physical_rms": result["physical_force_n"]["rms"],
        "physical_peak": result["physical_force_n"]["peak"],
        "slew_rms": result["rates"]["physical_force_n_s"]["rms"],
        "slew_peak": result["rates"]["physical_force_n_s"]["peak"],
        "moment_peak": result["physical_moment_R_nm"]["peak"],
        "safe_filtered": counts["SAFE_FILTERED"],
        "filter_infeasible": counts["FILTER_INFEASIBLE"],
        "brake": result["brake"]["transition_count"],
        "nsa": result["no_safe_action_count"],
        "deformation_mm": result.get("deformation_peak_mm") if arm_name == "P1" else None,
        "rotation_deg": result.get("rotation_peak_deg") if arm_name == "P1" else None,
    }
    return data


def summary_data(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        label: {name: compact_result(case["arms"][name]["result"], name) for name in ("rigid", "P1")}
        for label, case in cases.items()
    }


def downsample_indices(length: int, maximum: int) -> np.ndarray:
    return np.unique(np.linspace(0, length - 1, min(length, maximum), dtype=int))


def tracking_payload(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for label, case in cases.items():
        output[label] = {"endpoint": case["endpoint"].tolist(), "arms": {}}
        for name in ("rigid", "P1"):
            tracking = case["arms"][name]["tracking"]
            output[label]["arms"][name] = {
                "t": np.round(tracking["time_s"], 4).tolist(),
                "q": np.round(tracking["q_deg"], 3).tolist(),
                "ref": np.round(tracking["ref_deg"], 3).tolist(),
            }
    return output


def force_map_payload() -> dict[str, Any]:
    with np.load(SUMMARY / "dense_force_maps.npz", allow_pickle=False) as archive:
        q1 = archive["q1_deg"]
        q2 = archive["q2_deg"]
        force = archive["static_registered_force_n"]
    return {
        "q1": q1.astype(int).tolist(),
        "q2": q2.astype(int).tolist(),
        "force": [[None if not np.isfinite(value) else round(float(value), 3) for value in row] for row in force],
        "minimum_n": round(float(np.nanmin(force)), 3),
        "maximum_n": round(float(np.nanmax(force)), 3),
        "thresholds_n": [200, 220, 250],
        "source": "dense_force_maps.npz; registered 1:1 cuff-aware allocator",
    }


def dynamic_force_payload(cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    colors = {"40/80": ["#1f5f99", "#c53f4b"], "90/120": ["#387d5d", "#d17827"], "120/120": ["#65459b", "#9d5ab3"]}
    curves = []
    for label, case in cases.items():
        for arm_index, name in enumerate(("rigid", "P1")):
            arm = case["arms"][name]
            q = arm["force_overlay"]["q_deg"]
            force = arm["force_overlay"]["force_n"]
            curves.append({
                "name": f"{label} {'Rigid NEW' if name == 'rigid' else 'P1 NEW'}",
                "color": colors[label][arm_index],
                "q1": np.round(q[:, 0], 2).tolist(),
                "q2": np.round(q[:, 1], 2).tolist(),
                "force": np.round(force, 2).tolist(),
            })
    return curves


def build_html(cases: dict[str, dict[str, Any]], videos: dict[str, dict[str, Any]], source_hashes: dict[str, str]) -> str:
    summary = summary_data(cases)
    tracking = tracking_payload(cases)
    force_map = force_map_payload()
    curves = dynamic_force_payload(cases)
    video_blocks = []
    captions = {
        "40/80": "Rigid NEW 已消除旧路径下的 BRAKE；P1 NEW 没有额外可行性优势，主要降低 force slew，但跟踪与稳定残差更大。",
        "90/120": "两侧都执行近完整往返且没有 BRAKE；P1 NEW 降低物理力峰值、moment 与瞬态，并略微改善 tracking RMSE。",
        "120/120": "两侧都执行接近完整往返且没有 BRAKE；旧 Rigid BRAKE 与旧 P1 约 222 N 事件均未复现，P1 NEW 主要降低 force slew。",
    }
    for label in CASES:
        video = videos[label]
        primary = " primary" if CASES[label]["primary"] else ""
        video_blocks.append(f'''<article class="video-card{primary}"><div class="kicker">{label} 匹配回放</div><video controls playsinline preload="metadata" poster="{video['poster_uri']}"><source src="{video['data_uri']}" type="video/mp4"></video><p>{html.escape(captions[label])}</p></article>''')
    rows = []
    for label in CASES:
        rigid, p1 = summary[label]["rigid"], summary[label]["P1"]
        rows.append(f'''<tr><th>{label}</th><td><b>{rigid['formal']}</b><small>物理去程/回程 {rigid['outbound']:.2f}% / {rigid['return_pct']:.2f}%<br>endpoint/return {rigid['endpoint']:.3f}° / {rigid['return']:.3f}°</small></td><td><b>{p1['formal']}</b><small>物理去程/回程 {p1['outbound']:.2f}% / {p1['return_pct']:.2f}%<br>endpoint/return {p1['endpoint']:.3f}° / {p1['return']:.3f}°</small></td><td>{rigid['tracking']:.3f}° / {p1['tracking']:.3f}°</td><td>{rigid['physical_peak']:.1f} / {p1['physical_peak']:.1f} N</td><td>{rigid['slew_rms']:.1f} / {p1['slew_rms']:.1f}</td><td>{rigid['moment_peak']:.1f} / {p1['moment_peak']:.1f}</td><td>{rigid['safe_filtered']}/{rigid['filter_infeasible']}/{rigid['brake']}/{rigid['nsa']}<br>{p1['safe_filtered']}/{p1['filter_infeasible']}/{p1['brake']}/{p1['nsa']}</td></tr>''')
    detailed = []
    for label in CASES:
        for name in ("rigid", "P1"):
            item = summary[label][name]
            deform = "—" if name == "rigid" else f"{item['deformation_mm']:.3f} mm / {item['rotation_deg']:.3f}°"
            detailed.append(f'''<tr><th>{label} {'Rigid NEW' if name == 'rigid' else 'P1 NEW'}</th><td>{item['human_rms']:.1f}/{item['human_peak']:.1f}</td><td>{item['position_peak']:.1f}</td><td>{item['velocity_peak']:.1f}</td><td>{item['nominal_peak']:.1f}</td><td>{item['command_peak']:.1f}</td><td>{item['physical_rms']:.1f}/{item['physical_peak']:.1f}</td><td>{deform}</td></tr>''')
    provenance = json.dumps({
        "evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "source_hashes": source_hashes,
        "videos": {key: {k: v for k, v in value.items() if not k.endswith("uri")} for key, value in videos.items()},
        "force_map": {"min_n": force_map["minimum_n"], "max_n": force_map["maximum_n"], "source": force_map["source"]},
    }, separators=(",", ":"))
    template = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Phase 3A｜Corrected High-ROM Baseline</title>
<style>:root{--ink:#15181b;--muted:#56616a;--line:#d9dee2;--paper:#fff;--wash:#f5f7f8;--blue:#1f5f99;--red:#c53f4b;--green:#287651;--amber:#a4650b}*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:16px/1.68 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",Arial,sans-serif}nav{position:sticky;top:0;z-index:5;display:flex;gap:18px;overflow:auto;padding:11px 22px;background:#fffffff2;border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}nav a{color:var(--muted);text-decoration:none;font-size:13px;white-space:nowrap}main{max-width:1180px;margin:auto;padding:30px 24px 80px}header{padding:50px 0 36px;border-bottom:1px solid var(--line)}h1{font-size:clamp(38px,6vw,68px);line-height:1.07;margin:10px 0 18px;max-width:1050px}h2{font-size:clamp(27px,4vw,42px);line-height:1.18;margin:0 0 12px}h3{font-size:20px;margin:0 0 8px}.kicker{color:var(--green);font-size:12px;font-weight:760;letter-spacing:.08em}.lead{font-size:20px;color:#344049;max-width:900px}.scope{display:inline-block;padding:8px 11px;background:var(--wash);border:1px solid var(--line);font-size:13px}.section{padding:52px 0;border-bottom:1px solid var(--line)}.intro{max-width:900px;color:var(--muted);margin:0 0 26px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}.flow,.card{border:1px solid var(--line);background:#fff;padding:20px;box-shadow:0 7px 20px #24313a0c}.flow-line{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:16px 0}.node{padding:7px 9px;background:var(--wash);border:1px solid var(--line);font-size:13px}.arrow{color:#75828a}.good{border-left:4px solid var(--green)}.history{border-left:4px solid var(--amber)}.video-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.video-card{padding:15px;border:1px solid var(--line);background:var(--wash)}.video-card.primary{grid-column:1/-1;border-color:#98a7b1}.video-card video{display:block;width:100%;margin:9px 0 11px;background:#111}.video-card p{margin:0;color:var(--muted)}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.toolbar button{border:1px solid var(--line);background:#fff;padding:8px 11px;color:var(--muted);font:inherit;cursor:pointer}.toolbar button.active,.toolbar button:hover{border-color:#75838c;color:#111;background:#f0f3f5}.canvas{border:1px solid var(--line);padding:10px;background:#fff;overflow:hidden}canvas{display:block;width:100%;height:auto}.landscape{display:grid;grid-template-columns:minmax(0,1fr) 255px;gap:18px}.controls{border:1px solid var(--line);padding:15px;background:var(--wash)}.controls label{display:block;font-size:13px;margin:7px 0}.note{padding:12px 14px;background:#fff8e8;border-left:4px solid var(--amber)}.table-wrap{overflow:auto;border:1px solid var(--line);margin:18px 0}table{border-collapse:collapse;width:100%;min-width:980px}th,td{padding:12px 11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}thead th{font-size:12px;color:var(--muted);background:var(--wash)}tbody th{white-space:nowrap}td small{display:block;color:var(--muted);margin-top:4px}.case-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.case{background:var(--wash);padding:15px;border-top:3px solid var(--line)}.case:nth-child(2){border-color:var(--green)}.bars{display:grid;gap:11px}.bar-row{display:grid;grid-template-columns:230px 1fr 95px;align-items:center;gap:12px}.track{height:14px;background:#e7ebee}.fill{height:100%;background:var(--blue)}.fill.tiny{min-width:2px}.fine{font-size:12px;color:#68747c}.diagnostic{display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:stretch}.diagnostic .card{box-shadow:none}.big-arrow{align-self:center;font-size:32px;color:#78848b}.conclusion{font-size:21px;max-width:920px}.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin-top:9px}.swatch{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:5px}details{margin-top:16px;color:var(--muted)}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}@media(max-width:820px){.grid2,.video-grid,.landscape,.case-grid,.diagnostic{grid-template-columns:1fr}.video-card.primary{grid-column:auto}.big-arrow{transform:rotate(90deg);justify-self:center}.bar-row{grid-template-columns:1fr}.scope{display:block}main{padding:20px 14px 60px}.section{padding:42px 0}}</style></head><body>
<nav><a href="#correction">测量契约修正</a><a href="#motion">同步运动</a><a href="#tracking">跟踪</a><a href="#force">力图谱</a><a href="#results">匹配结果</a><a href="#interpret">力分解</a><a href="#history">诊断历史</a><a href="#conclusion">结论</a></nav><main>
<header><div class="kicker">Phase 3A · Corrected High-ROM Baseline</div><h1>分离控制速度与估计速度后的 High-ROM 结果</h1><p class="lead">新的当前解释基于同一 Fixed MPC、同一 140 Ns/m 增益、同一 Safety Filter / BRAKE 和同一 200 N 工程目标。修正只改变 robot 低层平移速度反馈的测量来源；Human reconstruction、estimator 与 MPC measurement 仍保留原有平滑历史路径。</p><div class="scope">0.25 ms physics dt · 200 Hz control update · seed 44104 · 相同 Human/robot/geometry/trajectory · 仿真证据</div></header>

<section class="section" id="correction"><div class="kicker">A · 测量契约修正</div><h2>同一增益，改用 cuff-center 的低延迟 robot twist</h2><div class="grid2"><article class="flow history"><h3>旧执行路径｜诊断历史</h3><div class="flow-line"><span class="node">robot cuff pose</span><span class="arrow">→</span><span class="node">8 Hz low-pass</span><span class="arrow">→</span><span class="node">120 ms causal fit</span><span class="arrow">→</span><span class="node">140 Ns/m</span></div><p>该 history-derived velocity 进入 robot 低层 damping feedback，在旧 40/80 与 120/120 边界分别形成 83.14 N 与 135.49 N 的 velocity-feedback force，并参与触发 200 N executable boundary。</p></article><article class="flow good"><h3>NEW 执行路径｜当前基线</h3><div class="flow-line"><span class="node">RobotState q,dq</span><span class="arrow">→</span><span class="node">cuff-center Jacobian</span><span class="arrow">→</span><span class="node">WORLD twist</span><span class="arrow">→</span><span class="node">同一 140 Ns/m</span></div><p>控制反馈在既有 200 Hz 边界采样并 ZOH 5 ms；screening、Safety Filter、BRAKE 与最终执行共享同一 snapshot。旧平滑路径继续服务 Human state reconstruction、identification 与 MPC。</p></article></div><p class="note">Human MPC、140 Ns/m 增益、Safety Filter、BRAKE、200 N 工程目标、P1 参数、模型与轨迹均未改变。该结果支持测量契约修正后的仿真解释，不外推到临床或硬件能力。</p></section>

<section class="section" id="motion"><div class="kicker">B · 代表性运动</div><h2>Rigid NEW 与 P1 NEW 同步回放</h2><p class="intro">视频直接从冻结的 Human/robot state 渲染，没有推进 dynamics、调用 MPC 或生成新轨迹。每组共用时间轴，叠加 q、reference、tracking error、物理力、指令力、mode、reference progress 与 P1 deformation。</p><div class="video-grid">@@VIDEOS@@</div></section>

<section class="section" id="tracking"><div class="kicker">C · 跟踪行为</div><h2>q1-q2 路径与同步时间序列</h2><p class="intro">正式 COMPLETE / SAFE_INCOMPLETE 分类完整保留；物理去程、回程比例与残差同时显示，避免把严格 0.068969° 容差误读为“Human 没有完成运动”。</p><div class="toolbar" id="trackButtons"></div><div class="toolbar"><button id="trackPlay">暂停</button><button id="trackRestart">重新开始</button><span class="scope" id="trackTime"></span></div><div class="canvas"><canvas id="trackingCanvas" width="1120" height="570"></canvas></div><div class="legend"><span><i class="swatch" style="background:#272b2e"></i>reference</span><span><i class="swatch" style="background:#1f5f99"></i>Rigid NEW</span><span><i class="swatch" style="background:#c53f4b"></i>P1 NEW</span></div></section>

<section class="section" id="force"><div class="kicker">D · Engineering force landscape</div><h2>解析准静态曲面与观测动态轨迹</h2><p class="intro">曲面是 nominal Human V2 与注册 1:1 cuff-aware allocator 在 dq=0、ddq=0 下的 model-derived mechanics。动态曲线是 corrected closed-loop 轨迹中观测到的物理力，依赖速度、历史与执行状态；它们不是 q1、q2 的唯一函数。</p><p class="note"><b>200 N registered simulation engineering target — not a clinical safety threshold.</b> 该目标也不是已验证硬件极限。</p><div class="landscape"><div><div class="canvas"><canvas id="forceCanvas" width="900" height="620"></canvas></div><div class="canvas" style="margin-top:14px"><canvas id="marginCanvas" width="900" height="430"></canvas></div></div><aside class="controls"><h3>动态轨迹</h3><div id="curveControls"></div><p class="fine">拖动上图旋转，滚轮缩放。下图按 q1-q2 显示准静态 force map，并实际计算 200/220/250 N contour crossing。冻结 domain 内最大值 182.30 N，因此三条零余量 contour 均不存在。</p></aside></div></section>

<section class="section" id="results"><div class="kicker">E · Corrected matched comparison</div><h2>可行性边界消失后，P1 的独立作用</h2><div class="table-wrap"><table><thead><tr><th>轨迹</th><th>Rigid NEW</th><th>P1 NEW</th><th>tracking RMSE<br>R/P</th><th>physical peak<br>R/P</th><th>slew RMS<br>R/P N/s</th><th>moment peak<br>R/P Nm</th><th>SF/FI/BRAKE/NSA<br>Rigid / P1</th></tr></thead><tbody>@@ROWS@@</tbody></table></div><div class="case-grid"><article class="case"><h3>40/80</h3><p>Rigid NEW 已 COMPLETE。P1 NEW 没有新的 feasibility 优势；其 force slew 更低，但 tracking RMSE 与 settling residual 更大。</p></article><article class="case"><h3>90/120</h3><p>两侧均执行近完整往返且无 BRAKE。P1 NEW 将 physical peak 降低 11.40 N、moment peak 降低 7.67 Nm，并将 tracking RMSE 改善 0.185°。</p></article><article class="case"><h3>120/120</h3><p>两侧都执行接近完整轨迹且无 BRAKE。旧 rigid BRAKE 与旧 P1 约 222 N transient 均未持续到 corrected baseline；P1 NEW 主要降低 slew，并略微增加 tracking/settling 误差。</p></article></div><h3 style="margin-top:28px">执行层力链（RMS/peak 或 peak，N）</h3><div class="table-wrap"><table><thead><tr><th>case</th><th>Human demand<br>RMS/peak</th><th>position F<br>peak</th><th>velocity F<br>peak</th><th>nominal executable<br>peak</th><th>command<br>peak</th><th>physical<br>RMS/peak</th><th>P1 deformation<br>translation/rotation</th></tr></thead><tbody>@@DETAIL@@</tbody></table></div></section>

<section class="section" id="interpret"><div class="kicker">F · Model-based interpretability</div><h2>平均负担来自静态 Human mechanics，旧边界超额来自执行速度反馈</h2><p class="intro">以下是冻结四条旧 Rigid 轨迹的 Human-level vector decomposition 跨轨迹 RMS 中位数。分量保留向量方向，norm 比值不可当作可相加百分比。</p><div class="bars"><div class="bar-row"><b>static Human mechanics</b><div class="track"><div class="fill" style="width:69.5%"></div></div><span>97.26 N</span></div><div class="bar-row"><b>nominal reference dynamics</b><div class="track"><div class="fill tiny" style="width:.1%"></div></div><span>0.10 N</span></div><div class="bar-row"><b>tracking feedback / correction</b><div class="track"><div class="fill" style="width:5.8%"></div></div><span>8.12 N</span></div></div><div class="grid2" style="margin-top:24px"><article class="card"><h3>解析力图</h3><p>0–125° 的 q1-q2 稠密图中，注册 allocator 的 quasistatic translational force 为 0.06–182.30 N；整个有效 domain 都低于 200 N。nominal reference-dynamic increment 在冻结慢轨迹中可忽略。</p></article><article class="card"><h3>旧边界机制</h3><p>旧 40/80 与 120/120 在 FILTER_INFEASIBLE 前的 robot velocity-feedback force 分别为 83.14 N 和 135.49 N。corrected 测量路径下，对应新轨迹的 velocity-feedback peak 仅为 1.39 N 与 2.04 N，且不再发生 BRAKE。</p></article></div></section>

<section class="section" id="history"><div class="kicker">G · Diagnostic history</div><h2>旧结果保留，但不再作为当前 High-ROM 基线</h2><div class="diagnostic"><article class="card history"><h3>旧路径观察</h3><p>history-derived robot velocity → 大 velocity-feedback force → 200 N executable boundary → FILTER_INFEASIBLE / BRAKE。旧 P1 120/120 随后还出现约 222 N 物理接口 transient。</p></article><div class="big-arrow">→</div><article class="card good"><h3>corrected baseline</h3><p>separated low-latency robot velocity feedback → 相同 MPC / gain / safety target → 40/80 BRAKE 消失，120/120 可执行接近完整往返；旧 P1 222 N 事件也未复现。</p></article></div><p class="fine">旧 evidence 不被删除、重命名或重新判定。P1 早先的严格 numerical-qualification FAIL 继续保留；本报告不声称 P1 已取得数值资格。</p></section>

<section class="section" id="target"><div class="kicker">H · 200 N 的解释边界</div><h2>注册工程 stress-test target</h2><div class="grid2"><article class="card"><h3>它是什么</h3><p>为了跨历史实验保持一致而冻结的 simulation engineering target，用于观察 controller/execution stack 与 force budget 的相互作用。</p></article><article class="card"><h3>它不是什么</h3><p>不是临床 tissue-safety threshold，不是舒适度结论，也不是经过 hardware validation 的 actuator/cuff capability limit。</p></article></div></section>

<section class="section" id="conclusion"><div class="kicker">I · 当前结论</div><h2>corrected High-ROM baseline</h2><p class="conclusion">分离 robot 控制速度与估计速度后，旧 High-ROM command-feasibility boundary 不再是 corrected cases 的主要限制。P1 compliance 不是 High-ROM feasibility 的必要条件；其独立收益主要是稳定降低 force slew，并在 90/120 降低物理力峰值、moment 且略微改善 tracking。其他轨迹上，它会增加 deformation、settling 或 tracking 代价，因此收益仍然依赖 trajectory 与 history。</p><p>当前 simulation evidence 不能定义临床安全边界或硬件能力边界。</p><details><summary>离线与 provenance 信息</summary><p>证据检查点：<code>@@CHECKPOINT@@</code>。视频由冻结 state 可视化生成，没有运行 trajectory。所有数据、CSS、JavaScript、视频与 poster 均内嵌；文件不发起网络请求。</p><script type="application/json" id="provenance">@@PROVENANCE@@</script></details></section>
</main><script>(()=>{const tracking=@@TRACKING@@,atlas=@@ATLAS@@,curves=@@CURVES@@;
const tc=document.getElementById('trackingCanvas'),tx=tc.getContext('2d');let active='40/80',playing=true,offset=0,start=performance.now();const buttons=document.getElementById('trackButtons');Object.keys(tracking).forEach(k=>{const b=document.createElement('button');b.textContent=k;b.className=k===active?'active':'';b.onclick=()=>{active=k;offset=0;start=performance.now();[...buttons.children].forEach(x=>x.classList.toggle('active',x===b))};buttons.appendChild(b)});document.getElementById('trackPlay').onclick=e=>{playing=!playing;e.target.textContent=playing?'暂停':'播放';start=performance.now()};document.getElementById('trackRestart').onclick=()=>{offset=0;start=performance.now()};
function pick(a,t){let lo=0,hi=a.t.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(a.t[m]<=t)lo=m;else hi=m-1}return lo}function line(ctx,pts,map,color,width=2,dash=[]){ctx.beginPath();ctx.setLineDash(dash);pts.forEach((p,i)=>{const v=map(p);i?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1])});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();ctx.setLineDash([])}
function trackingFrame(now){const d=tracking[active],duration=Math.max(d.arms.rigid.t.at(-1),d.arms.P1.t.at(-1));if(playing){offset=(offset+(now-start)/1000)%duration;start=now}const time=offset;document.getElementById('trackTime').textContent=`${active} · t=${time.toFixed(2)}/${duration.toFixed(2)} s`;tx.fillStyle='#fff';tx.fillRect(0,0,tc.width,tc.height);const pad=64,top=48,w=470,h=450,all=[...d.arms.rigid.q,...d.arms.P1.q,...d.arms.rigid.ref],q1=all.map(v=>v[0]),q2=all.map(v=>v[1]),xmin=Math.min(...q1)-5,xmax=Math.max(...q1)+5,ymin=Math.min(...q2)-5,ymax=Math.max(...q2)+5,mapQ=p=>[pad+(p[0]-xmin)/(xmax-xmin)*w,top+h-(p[1]-ymin)/(ymax-ymin)*h];tx.strokeStyle='#aeb8bf';tx.strokeRect(pad,top,w,h);line(tx,d.arms.rigid.ref,mapQ,'#272b2e',3,[8,5]);line(tx,d.arms.rigid.q,mapQ,'#1f5f99',2);line(tx,d.arms.P1.q,mapQ,'#c53f4b',2);for(const [name,color] of [['rigid','#1f5f99'],['P1','#c53f4b']]){const i=pick(d.arms[name],time),p=mapQ(d.arms[name].q[i]);tx.beginPath();tx.arc(p[0],p[1],7,0,7);tx.fillStyle=color;tx.fill()}const ir=pick(d.arms.rigid,time),pr=mapQ(d.arms.rigid.ref[ir]);tx.beginPath();tx.arc(pr[0],pr[1],5,0,7);tx.fillStyle='#111';tx.fill();tx.fillStyle='#15181b';tx.font='bold 18px system-ui';tx.fillText('q1-q2 路径',pad,27);tx.font='13px system-ui';tx.fillText('q1 (deg)',pad+w/2-22,top+h+40);tx.save();tx.translate(18,top+h/2+28);tx.rotate(-Math.PI/2);tx.fillText('q2 (deg)',0,0);tx.restore();const rx=600,rw=470,rh=190,vals=[...d.arms.rigid.q.flat(),...d.arms.P1.q.flat(),...d.arms.rigid.ref.flat()],vmin=Math.min(...vals)-5,vmax=Math.max(...vals)+5;function tmap(t,v,y0){return[rx+t/duration*rw,y0+rh-(v-vmin)/(vmax-vmin)*rh]}for(let j=0;j<2;j++){const y0=48+j*245;tx.strokeStyle='#aeb8bf';tx.strokeRect(rx,y0,rw,rh);const map=p=>tmap(p[0],p[1],y0);line(tx,d.arms.rigid.t.map((t,i)=>[t,d.arms.rigid.ref[i][j]]),map,'#272b2e',2,[7,5]);line(tx,d.arms.rigid.t.map((t,i)=>[t,d.arms.rigid.q[i][j]]),map,'#1f5f99',2);line(tx,d.arms.P1.t.map((t,i)=>[t,d.arms.P1.q[i][j]]),map,'#c53f4b',2);const x=rx+time/duration*rw;tx.strokeStyle='#287651';tx.beginPath();tx.moveTo(x,y0);tx.lineTo(x,y0+rh);tx.stroke();tx.fillStyle='#15181b';tx.font='bold 17px system-ui';tx.fillText(`q${j+1}(t)`,rx,y0-13)}requestAnimationFrame(trackingFrame)}requestAnimationFrame(trackingFrame);
const fc=document.getElementById('forceCanvas'),fx=fc.getContext('2d'),mc=document.getElementById('marginCanvas'),mx=mc.getContext('2d'),controls=document.getElementById('curveControls');let yaw=-.72,pitch=.50,zoom=1,drag=false,last=[0,0];curves.forEach((c,i)=>{const l=document.createElement('label'),cb=document.createElement('input');cb.type='checkbox';cb.checked=true;cb.dataset.i=i;cb.onchange=()=>{drawForce();drawMargin()};l.append(cb,document.createTextNode(' '+c.name));l.style.color=c.color;controls.appendChild(l)});fc.onpointerdown=e=>{drag=true;last=[e.clientX,e.clientY];fc.setPointerCapture(e.pointerId)};fc.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-last[0])*.008;pitch=Math.max(-.2,Math.min(1.2,pitch+(e.clientY-last[1])*.006));last=[e.clientX,e.clientY];drawForce()};fc.onpointerup=()=>drag=false;fc.onwheel=e=>{e.preventDefault();zoom=Math.max(.65,Math.min(1.8,zoom*(e.deltaY>0?.92:1.08)));drawForce()};
function project(q1,q2,z){let x=(q1-62.5)/62.5,y=(q2-62.5)/62.5,zz=z/220-.35,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),X=cy*x-sy*y,Y=sy*x+cy*y,Z=zz,Y2=cp*Y-sp*Z,Z2=sp*Y+cp*Z;return[fc.width/2+X*330*zoom,fc.height/2+Y2*245*zoom-Z2*25]}function mesh(pts,color,width=1,alpha=1){if(!pts.length)return;fx.beginPath();pts.forEach((p,i)=>{const v=project(...p);i?fx.lineTo(...v):fx.moveTo(...v)});fx.strokeStyle=color;fx.globalAlpha=alpha;fx.lineWidth=width;fx.stroke();fx.globalAlpha=1}
function drawForce(){fx.fillStyle='#fff';fx.fillRect(0,0,fc.width,fc.height);for(let j=1;j<atlas.q2.length;j+=5){const p=[];for(let i=0;i<atlas.q1.length;i+=5){const z=atlas.force[j][i];if(z!=null)p.push([atlas.q1[i],atlas.q2[j],z])}mesh(p,'#aab4bb',1,.8)}for(let i=0;i<atlas.q1.length;i+=5){const p=[];for(let j=1;j<atlas.q2.length;j+=5){const z=atlas.force[j][i];if(z!=null)p.push([atlas.q1[i],atlas.q2[j],z])}mesh(p,'#aab4bb',1,.8)}mesh([[0,1,200],[125,1,200],[125,125,200],[0,125,200],[0,1,200]],'#a4650b',3,.95);controls.querySelectorAll('input').forEach(cb=>{if(!cb.checked)return;const c=curves[+cb.dataset.i];mesh(c.q1.map((q,i)=>[q,c.q2[i],c.force[i]]),c.color,2.5,1)});fx.fillStyle='#15181b';fx.font='bold 18px system-ui';fx.fillText('quasistatic surface + observed dynamic curves',22,29);fx.fillStyle='#875508';fx.font='13px system-ui';fx.fillText('200 N registered engineering target plane',22,51);fx.fillStyle='#56616a';fx.fillText('q1 →',760,586);fx.fillText('q2 →',90,540);fx.fillText('force ↑',55,90)}
function heatColor(v){const t=Math.max(0,Math.min(1,v/190));return`rgb(${Math.round(244-100*t)},${Math.round(248-82*t)},${Math.round(250-58*t)})`}function drawMargin(){mx.fillStyle='#fff';mx.fillRect(0,0,mc.width,mc.height);const l=65,t=45,w=700,h=330,s=2;for(let j=1;j<atlas.q2.length;j+=s)for(let i=0;i<atlas.q1.length;i+=s){const z=atlas.force[j][i];if(z==null)continue;mx.fillStyle=heatColor(z);mx.fillRect(l+atlas.q1[i]/125*w,t+h-atlas.q2[j]/125*h,w*s/126+1,h*s/126+1)}for(const threshold of atlas.thresholds_n){mx.strokeStyle=threshold===200?'#a4650b':threshold===220?'#7d568b':'#455c70';mx.lineWidth=2;for(let j=1;j<atlas.q2.length-1;j++)for(let i=0;i<atlas.q1.length-1;i++){const vals=[atlas.force[j][i],atlas.force[j][i+1],atlas.force[j+1][i],atlas.force[j+1][i+1]].filter(v=>v!=null);if(vals.length===4&&Math.min(...vals)<=threshold&&Math.max(...vals)>=threshold){mx.strokeRect(l+i/125*w,t+h-(j+1)/125*h,w/125+1,h/125+1)}}}controls.querySelectorAll('input').forEach(cb=>{if(!cb.checked)return;const c=curves[+cb.dataset.i];mx.beginPath();c.q1.forEach((q,i)=>{const x=l+q/125*w,y=t+h-c.q2[i]/125*h;i?mx.lineTo(x,y):mx.moveTo(x,y)});mx.strokeStyle=c.color;mx.lineWidth=1.7;mx.stroke()});mx.strokeStyle='#6f7b83';mx.strokeRect(l,t,w,h);mx.fillStyle='#15181b';mx.font='bold 18px system-ui';mx.fillText('准静态 force map 与 200 / 220 / 250 N contour 检查',22,27);mx.font='13px system-ui';mx.fillStyle='#56616a';mx.fillText('q1 (deg)',l+w/2-20,t+h+34);mx.save();mx.translate(19,t+h/2+30);mx.rotate(-Math.PI/2);mx.fillText('q2 (deg)',0,0);mx.restore();mx.fillStyle='#875508';mx.fillText(`max=${atlas.maximum_n.toFixed(2)} N；三条 threshold 均无 crossing`,780,75);for(let k=0;k<5;k++){mx.fillStyle=heatColor(k*47.5);mx.fillRect(790,105+k*35,18,18);mx.fillStyle='#56616a';mx.fillText(`${(k*47.5).toFixed(0)} N`,815,120+k*35)}}drawForce();drawMargin();
document.querySelectorAll('video').forEach(v=>v.addEventListener('error',()=>v.insertAdjacentHTML('afterend','<p style="color:#b4232d">当前浏览器无法解码内嵌 H.264 视频。</p>')));})();</script></body></html>'''
    return (template.replace("@@VIDEOS@@", "".join(video_blocks))
            .replace("@@ROWS@@", "".join(rows))
            .replace("@@DETAIL@@", "".join(detailed))
            .replace("@@CHECKPOINT@@", EVIDENCE_CHECKPOINT)
            .replace("@@TRACKING@@", json.dumps(tracking, separators=(",", ":")))
            .replace("@@ATLAS@@", json.dumps(force_map, separators=(",", ":")))
            .replace("@@CURVES@@", json.dumps(curves, separators=(",", ":")))
            .replace("@@PROVENANCE@@", provenance))


def verify_html(path: Path, videos: dict[str, dict[str, Any]], source_hashes: dict[str, str]) -> dict[str, Any]:
    content = path.read_text()
    assert content.count("<video ") == 3
    assert content.count("data:video/mp4;base64,") == 3
    assert content.count("data:image/jpeg;base64,") == 3
    for forbidden in ("https://", "http://", "fetch(", "XMLHttpRequest", "WebSocket", "src=\"/", "href=\"/"):
        assert forbidden not in content, forbidden
    for required in (
        "Rigid NEW 已消除旧路径下的 BRAKE",
        "旧 rigid BRAKE 与旧 P1 约 222 N transient 均未持续到 corrected baseline",
        "200 N registered simulation engineering target — not a clinical safety threshold.",
        "static Human mechanics",
        "三条 threshold 均无 crossing",
    ):
        assert required in content, required
    assert "刚性侧在回程进入 BRAKE，未能物理返回" not in content
    assert "@@" not in content
    assert force_map_payload()["maximum_n"] == 182.298
    embedded = re.findall(r"data:video/mp4;base64,([A-Za-z0-9+/=]+)", content)
    assert len(embedded) == 3
    with tempfile.TemporaryDirectory(prefix="phase3a_html_verify_", dir="/tmp") as temp:
        for index, payload in enumerate(embedded):
            target = Path(temp) / f"video_{index}.mp4"
            target.write_bytes(base64.b64decode(payload))
            frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(target))
            # Registered trajectory durations differ (about 19, 29, and 38 s).
            assert frames > 100 and seconds > 15.0
    for relative, expected in source_hashes.items():
        assert sha256(REPO / relative) == expected, relative
    return {
        "html_sha256": sha256(path),
        "html_bytes": path.stat().st_size,
        "embedded_video_count": 3,
        "embedded_poster_count": 3,
        "decoded_video_count": 3,
        "interactive_canvas_count": 3,
        "external_url_count": 0,
        "source_hash_count": len(source_hashes),
        "offline_static_checks": "PASS",
    }


def main() -> None:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", EVIDENCE_CHECKPOINT, "HEAD"], cwd=REPO)
    assert result.returncode == 0, EVIDENCE_CHECKPOINT
    cases = load_cases()
    source_hashes = {}
    for config in CASES.values():
        for name in ("rigid", "P1"):
            path = config[name]
            source_hashes[str(path.relative_to(REPO))] = sha256(path)
    for path in (
        REPORT_SOURCES / "manifest.json",
        SUMMARY / "dense_force_maps.npz",
        SUMMARY / "corrected_baseline_comparison.json",
        SUMMARY / "PROVENANCE.json",
        STAGE / "src/traction_mpc_stage4/phase3a_rendering.py",
    ):
        source_hashes[str(path.relative_to(REPO))] = sha256(path)
    sys.path.insert(0, str(REPO / "stages/stage3_full3d/src"))
    sys.path.insert(0, str(STAGE / "src"))
    from traction_mpc_stage4.phase3a_rendering import (
        create_phase3a_rigid_render_plant,
    )

    plant = create_phase3a_rigid_render_plant()
    plant.reset(np.radians(INITIAL_Q_DEG))
    videos = {}
    with tempfile.TemporaryDirectory(prefix="phase3a_corrected_media_", dir="/tmp") as temp:
        for label in CASES:
            print(f"VIDEO {label} START", flush=True)
            videos[label] = render_case_video(cases[label], plant, Path(temp))
            print(f"VIDEO {label} COMPLETE {videos[label]['byte_size'] / 1048576:.2f} MiB", flush=True)
    OUTPUT.write_text(build_html(cases, videos, source_hashes))
    verification = verify_html(OUTPUT, videos, source_hashes)
    print(json.dumps({"output": str(OUTPUT), "verification": verification, "videos": {key: {k: v for k, v in value.items() if not k.endswith("uri")} for key, value in videos.items()}}, indent=2), flush=True)


if __name__ == "__main__":
    main()
