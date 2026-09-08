#!/usr/bin/env python3
"""Offline Human-force decomposition from frozen Phase-3A evidence.

This script never advances a plant or invokes MPC.  It evaluates the frozen
population-prior Human model and registered memoryless cuff allocator at saved
states, then compares those analytic counterfactuals with saved command and
physical wrenches.
"""
from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm
import numpy as np

plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
sys.path.insert(0, str(REPO / "stages/stage3_full3d/src"))
sys.path.insert(0, str(STAGE / "src"))

from traction_mpc_stage3.human import HUMAN  # noqa: E402
from traction_mpc_stage4.cuff_allocator import (  # noqa: E402
    CurrentForceMinimizingAllocator,
    default_engineering_cuff_allocator,
    sagittal_allocation_matrix,
)
from traction_mpc_stage4.dynamics_failure_audit import geometry_from_trace_vector  # noqa: E402
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel  # noqa: E402


OUTPUT = STAGE / "results/engineering_validation/offline_force_decomposition_20260907_v1"
FIGURES = OUTPUT / "figures"
INITIAL_Q_RAD = np.radians([5.0, 10.0])
HIGH_ROM_HUMAN = replace(
    HUMAN,
    q_min_rad=(0.0, 0.0),
    q_max_rad=(math.radians(125.0), math.radians(125.0)),
)
CASES = {
    "40/40": ("progressive_relaxed_ab_20260905_v1", "hip40_knee40"),
    "40/80": ("progressive_40_80_ab_20260907_v1", "hip40_knee80"),
    "90/120": ("progressive_90_120_ab_20260907_v1", "hip90_knee120"),
    "120/120": ("progressive_120_120_ab_20260907_v1", "hip120_knee120"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(clean(payload), indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def evidence_dir(label: str, arm: str) -> Path:
    root, stem = CASES[label]
    return STAGE / "results/engineering_validation" / root / f"{stem}_{arm}_dt0250us"


def load_arm(label: str, arm: str) -> dict[str, Any]:
    root = evidence_dir(label, arm)
    return {
        "root": root,
        "trace": load_npz(root / "trace.npz"),
        "mechanics": load_npz(root / "mechanics.npz"),
        "commands": load_npz(root / "commands.npz"),
        "modes": load_npz(root / "modes.npz"),
        "result": json.loads((root / "result.json").read_text()),
        "run_config": json.loads((root / "run_config.json").read_text()),
    }


def nearest_indices(source_time: np.ndarray, target_time: np.ndarray) -> np.ndarray:
    right = np.searchsorted(source_time, target_time, side="left")
    right = np.clip(right, 0, len(source_time) - 1)
    left = np.clip(right - 1, 0, len(source_time) - 1)
    choose_left = np.abs(source_time[left] - target_time) <= np.abs(source_time[right] - target_time)
    return np.where(choose_left, left, right)


def quintic(value: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = np.clip(np.asarray(value, dtype=float), 0.0, 1.0)
    return (
        10.0 * r**3 - 15.0 * r**4 + 6.0 * r**5,
        30.0 * r**2 - 60.0 * r**3 + 30.0 * r**4,
        60.0 * r - 180.0 * r**2 + 120.0 * r**3,
    )


def base_reference(point: dict[str, Any], phase: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    phase = np.asarray(phase, dtype=float)
    q = np.broadcast_to(INITIAL_Q_RAD, (len(phase), 2)).copy()
    dq = np.zeros_like(q)
    ddq = np.zeros_like(q)
    target = np.radians(point["endpoint_deg"])
    delta = target - INITIAL_Q_RAD
    leg = float(point["outbound_duration_s"])
    out = (phase > 1.0) & (phase < 1.0 + leg)
    hold = (phase >= 1.0 + leg) & (phase <= 2.5 + leg)
    ret = (phase > 2.5 + leg) & (phase < 2.5 + 2.0 * leg)
    if np.any(out):
        s, ds, dds = quintic((phase[out] - 1.0) / leg)
        q[out] = INITIAL_Q_RAD + s[:, None] * delta
        dq[out] = ds[:, None] * delta / leg
        ddq[out] = dds[:, None] * delta / leg**2
    q[hold] = target
    if np.any(ret):
        s, ds, dds = quintic((phase[ret] - 2.5 - leg) / leg)
        q[ret] = INITIAL_Q_RAD + (1.0 - s)[:, None] * delta
        dq[ret] = -ds[:, None] * delta / leg
        ddq[ret] = -dds[:, None] * delta / leg**2
    return q, dq, ddq


def coriolis_vector(q: np.ndarray, dq: np.ndarray, beta: np.ndarray) -> np.ndarray:
    q2 = float(q[1])
    dq1, dq2 = np.asarray(dq, dtype=float)
    coupling = float(beta[2])
    return np.array([
        coupling * math.sin(q2) * (-2.0 * dq1 * dq2 + dq2**2),
        coupling * math.sin(q2) * dq1**2,
    ])


def allocate(allocator: Any, torque: np.ndarray, q: np.ndarray, model: Any) -> np.ndarray:
    return np.asarray(allocator.allocate(torque, q, model)["wrench_world"], dtype=float)


def rms_norm(vectors: np.ndarray, time_s: np.ndarray) -> float:
    values = np.sum(np.asarray(vectors, dtype=float) ** 2, axis=1)
    duration = float(time_s[-1] - time_s[0])
    return float(np.sqrt(np.trapezoid(values, time_s) / duration)) if duration > 0 else float(np.sqrt(values[0]))


def vector_stats(vectors: np.ndarray, time_s: np.ndarray) -> dict[str, float]:
    norms = np.linalg.norm(vectors, axis=1)
    return {"rms": rms_norm(vectors, time_s), "peak": float(np.max(norms))}


def frozen_model(arm: dict[str, Any]) -> BaseParameterHumanModel:
    trace = arm["trace"]
    return BaseParameterHumanModel(
        geometry=geometry_from_trace_vector(trace["geometry_estimate"][0]),
        beta=np.asarray(trace["dynamic_base_estimate"][0], dtype=float),
        rom_human=HIGH_ROM_HUMAN,
    )


def decompose_rigid(label: str, arm: dict[str, Any], model: BaseParameterHumanModel) -> dict[str, Any]:
    trace, mechanics, commands = arm["trace"], arm["mechanics"], arm["commands"]
    t = np.asarray(trace["control_time_s"], dtype=float)
    ti = nearest_indices(trace["time_s"], t)
    mi = nearest_indices(mechanics["time_s"], t)
    ci = nearest_indices(commands["time_s"], t)
    q = np.asarray(trace["control_estimated_state"][:, :2], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"][ti], dtype=float)
    speed = np.asarray(trace["reference_speed_scale"][ti], dtype=float)
    speed_rate = np.asarray(trace["reference_speed_scale_rate_per_s"][ti], dtype=float)
    ref_q_base, ref_dq_base, ref_ddq_base = base_reference(arm["run_config"]["point"], phase)
    ref_dq = speed[:, None] * ref_dq_base
    ref_ddq = speed[:, None] ** 2 * ref_ddq_base + speed_rate[:, None] * ref_dq_base
    saved_ref = np.radians(trace["human_q_ref_deg"][ti])
    ref_q_error = float(np.max(np.abs(ref_q_base - saved_ref)))
    assert ref_q_error <= 2e-10, (label, ref_q_error)

    tau_total = np.asarray(trace["desired_human_action_nm"][ti], dtype=float)
    count = len(t)
    tau_static = np.empty((count, 2))
    tau_refdyn = np.empty((count, 2))
    w_static = np.empty((count, 6))
    w_static_refdyn = np.empty((count, 6))
    w_total = np.empty((count, 6))
    allocator = default_engineering_cuff_allocator()
    for index in range(count):
        qi = q[index]
        tau_static[index] = model.inverse_dynamics(qi, np.zeros(2), np.zeros(2))
        tau_refdyn[index] = model.mass_matrix(qi) @ ref_ddq[index]
        tau_refdyn[index] += coriolis_vector(qi, ref_dq[index], model.beta)
        w_static[index] = allocate(allocator, tau_static[index], qi, model)
        w_static_refdyn[index] = allocate(
            allocator, tau_static[index] + tau_refdyn[index], qi, model
        )
        w_total[index] = allocate(allocator, tau_total[index], qi, model)
    tau_feedback = tau_total - tau_static - tau_refdyn
    delta_refdyn = w_static_refdyn - w_static
    delta_feedback = w_total - w_static_refdyn
    closure = w_static + delta_refdyn + delta_feedback - w_total
    assert float(np.max(np.abs(closure))) < 1e-10

    command_wrench = np.column_stack([commands["force"][ci], commands["moment"][ci]])
    physical_wrench = np.column_stack([
        mechanics["force_R_world"][mi], mechanics["moment_R_world"][mi]
    ])
    recorded_allocator = np.asarray(trace["allocated_wrench_world"][ti], dtype=float)
    command_increment = command_wrench - w_total
    execution_residual = physical_wrench - command_wrench

    fields = {
        "static": w_static[:, :3],
        "refdyn_increment": delta_refdyn[:, :3],
        "feedback_increment": delta_feedback[:, :3],
        "human_total": w_total[:, :3],
        "command": command_wrench[:, :3],
        "physical": physical_wrench[:, :3],
        "command_minus_human_total": command_increment[:, :3],
        "execution_interface_residual": execution_residual[:, :3],
    }
    stats = {name: vector_stats(value, t) for name, value in fields.items()}
    command_stats = stats["command"]
    total_norm = np.linalg.norm(fields["human_total"], axis=1)
    peak_index = int(np.argmax(total_norm))
    for name, values in fields.items():
        stats[name]["at_human_total_peak"] = float(np.linalg.norm(values[peak_index]))
        stats[name]["rms_ratio_to_command"] = stats[name]["rms"] / command_stats["rms"]
        stats[name]["peak_ratio_to_command"] = stats[name]["peak"] / command_stats["peak"]

    first_brake = None
    modes = arm["modes"]
    if "safety_filter_status" in modes:
        hits = np.flatnonzero(modes["safety_filter_status"] == "FILTER_INFEASIBLE")
        if len(hits):
            first_brake = float(modes["time_s"][hits[0]])
    if first_brake is None:
        hits = np.flatnonzero(modes["mode"] == "BRAKE")
        if len(hits):
            first_brake = float(modes["time_s"][hits[0]])

    event_rows: list[dict[str, Any]] = []
    if first_brake is not None:
        event_control = int(np.searchsorted(t, first_brake, side="left"))
        event_control = min(event_control, len(t) - 1)
        for location, index in (
            ("penultimate_pre_event_control", max(0, event_control - 1)),
            ("last_pre_event_control", event_control),
        ):
            f_no_feedback = fields["static"][index] + fields["refdyn_increment"][index]
            f_total = fields["human_total"][index]
            unit_total = f_total / max(np.linalg.norm(f_total), 1e-12)
            sf_index = int(np.argmin(np.abs(trace["safety_filter_time_s"] - t[index])))
            sf_available = abs(float(trace["safety_filter_time_s"][sf_index]) - t[index]) <= 0.003
            event_rows.append({
                "case": label,
                "location": location,
                "time_s": float(t[index]),
                "event_time_s": first_brake,
                "static_force_n": float(np.linalg.norm(fields["static"][index])),
                "refdyn_increment_n": float(np.linalg.norm(fields["refdyn_increment"][index])),
                "feedback_increment_n": float(np.linalg.norm(fields["feedback_increment"][index])),
                "feedback_projection_on_total_n": float(fields["feedback_increment"][index] @ unit_total),
                "no_feedback_counterfactual_force_n": float(np.linalg.norm(f_no_feedback)),
                "human_total_force_n": float(np.linalg.norm(f_total)),
                "feedback_effect_on_total_norm_n": float(np.linalg.norm(f_total) - np.linalg.norm(f_no_feedback)),
                "command_force_n": float(np.linalg.norm(fields["command"][index])),
                "physical_force_n": float(np.linalg.norm(fields["physical"][index])),
                "command_minus_human_total_n": float(np.linalg.norm(fields["command_minus_human_total"][index])),
                "execution_interface_residual_n": float(np.linalg.norm(fields["execution_interface_residual"][index])),
                "safety_filter_status": str(trace["safety_filter_status"][sf_index]) if sf_available else "UNAVAILABLE",
                "nominal_executable_force_n": float(trace["safety_filter_nominal_executable_force_norm_n"][sf_index]) if sf_available else None,
                "filtered_executable_force_n": float(trace["safety_filter_filtered_executable_force_norm_n"][sf_index]) if sf_available else None,
            })

    pre_brake = np.ones(count, dtype=bool) if first_brake is None else t < first_brake - 1e-9
    allocator_difference = recorded_allocator[pre_brake] - w_total[pre_brake]
    allocation_regression = {
        "sample_count": int(np.count_nonzero(pre_brake)),
        "rms_wrench_difference": rms_norm(allocator_difference, t[pre_brake]),
        "peak_wrench_difference": float(np.max(np.linalg.norm(allocator_difference, axis=1))),
        "interpretation": (
            "Difference includes saved Safety-Filter nullspace changes and control-cycle/state alignment; "
            "it is not used as a Human torque-decomposition term."
        ),
    }
    np.savez_compressed(
        OUTPUT / f"trajectory_decomposition_{label.replace('/', '_')}.npz",
        time_s=t,
        q_control_rad=q,
        reference_q_rad=ref_q_base,
        reference_dq_rad_s=ref_dq,
        reference_ddq_rad_s2=ref_ddq,
        tau_static_nm=tau_static,
        tau_refdyn_nm=tau_refdyn,
        tau_feedback_nm=tau_feedback,
        w_static_world=w_static,
        w_static_plus_refdyn_world=w_static_refdyn,
        w_total_world=w_total,
        delta_w_refdyn_world=delta_refdyn,
        delta_w_feedback_world=delta_feedback,
        command_wrench_world=command_wrench,
        physical_wrench_world=physical_wrench,
        command_minus_human_total_world=command_increment,
        execution_interface_residual_world=execution_residual,
    )
    return {
        "time_s": t,
        "fields": fields,
        "stats": stats,
        "event_rows": event_rows,
        "first_brake_time_s": first_brake,
        "human_total_peak_time_s": float(t[peak_index]),
        "reference_q_reconstruction_max_abs_rad": ref_q_error,
        "vector_closure_max_abs": float(np.max(np.abs(closure))),
        "allocator_regression": allocation_regression,
    }


def execution_layer(label: str, arm_name: str, arm: dict[str, Any]) -> dict[str, Any]:
    mechanics, commands = arm["mechanics"], arm["commands"]
    t = np.asarray(mechanics["time_s"], dtype=float)
    command_time = np.asarray(commands["time_s"], dtype=float)
    command_index = np.searchsorted(command_time, t, side="right") - 1
    command_index = np.clip(command_index, 0, len(command_time) - 1)
    command_samples = np.column_stack([commands["force"], commands["moment"]])
    command = command_samples[command_index]
    physical = np.column_stack([mechanics["force_R_world"], mechanics["moment_R_world"]])
    residual = physical - command
    np.savez_compressed(
        OUTPUT / f"execution_layer_{label.replace('/', '_')}_{arm_name}.npz",
        time_s=t,
        command_index=command_index,
        command_wrench_world=command,
        physical_wrench_world=physical,
        execution_interface_residual_world=residual,
    )
    return {
        "time_s": t,
        "command_force": command[:, :3],
        "physical_force": physical[:, :3],
        "residual_force": residual[:, :3],
        "stats": {
            "command": vector_stats(command[:, :3], t),
            "physical": vector_stats(physical[:, :3], t),
            "execution_interface_residual": vector_stats(residual[:, :3], t),
        },
    }


def dense_maps(model: BaseParameterHumanModel) -> dict[str, np.ndarray]:
    q1_deg = np.arange(0.0, 125.0 + 1e-9, 1.0)
    q2_deg = np.arange(0.0, 125.0 + 1e-9, 1.0)
    shape = (len(q2_deg), len(q1_deg))
    outputs = {
        "static_registered_force_n": np.full(shape, np.nan),
        "static_minimum_translational_force_n": np.full(shape, np.nan),
        "translational_force_map_condition": np.full(shape, np.inf),
        "full_sagittal_allocation_condition": np.full(shape, np.inf),
        "unit_hip_acceleration_force_n_per_rad_s2": np.full(shape, np.nan),
        "unit_knee_acceleration_force_n_per_rad_s2": np.full(shape, np.nan),
    }
    registered = default_engineering_cuff_allocator()
    minimum = CurrentForceMinimizingAllocator()
    plane_x = model.geometry.plane_x_world
    plane_z = model.geometry.plane_z_world
    basis = np.column_stack([plane_x, plane_z])
    for j, q2 in enumerate(q2_deg):
        for i, q1 in enumerate(q1_deg):
            q = np.radians([q1, q2])
            static_tau = model.inverse_dynamics(q, np.zeros(2), np.zeros(2))
            force_map = model.geometry.translational_jacobian_world(q).T @ basis
            singular = np.linalg.svd(force_map, compute_uv=False)
            if singular[-1] > 1e-12:
                outputs["translational_force_map_condition"][j, i] = singular[0] / singular[-1]
            full = np.linalg.svd(sagittal_allocation_matrix(q, model), compute_uv=False)
            if full[-1] > 1e-12:
                outputs["full_sagittal_allocation_condition"][j, i] = full[0] / full[-1]
            try:
                outputs["static_registered_force_n"][j, i] = np.linalg.norm(
                    allocate(registered, static_tau, q, model)[:3]
                )
                outputs["static_minimum_translational_force_n"][j, i] = np.linalg.norm(
                    allocate(minimum, static_tau, q, model)[:3]
                )
                mass = model.mass_matrix(q)
                outputs["unit_hip_acceleration_force_n_per_rad_s2"][j, i] = np.linalg.norm(
                    allocate(registered, mass @ np.array([1.0, 0.0]), q, model)[:3]
                )
                outputs["unit_knee_acceleration_force_n_per_rad_s2"][j, i] = np.linalg.norm(
                    allocate(registered, mass @ np.array([0.0, 1.0]), q, model)[:3]
                )
            except (RuntimeError, ValueError, np.linalg.LinAlgError):
                pass
    outputs["q1_deg"] = q1_deg
    outputs["q2_deg"] = q2_deg
    for threshold in (200.0, 220.0, 250.0):
        outputs[f"registered_margin_{int(threshold)}n"] = threshold - outputs["static_registered_force_n"]
    return outputs


def save_dense_data(maps: dict[str, np.ndarray]) -> None:
    np.savez_compressed(OUTPUT / "dense_force_maps.npz", **maps)
    fields = [key for key in maps if key not in {"q1_deg", "q2_deg"}]
    with (OUTPUT / "dense_force_maps.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["q1_deg", "q2_deg", *fields])
        for j, q2 in enumerate(maps["q2_deg"]):
            for i, q1 in enumerate(maps["q1_deg"]):
                writer.writerow([q1, q2, *[maps[key][j, i] for key in fields]])


def image(map_value: np.ndarray, maps: dict[str, np.ndarray], title: str, label: str,
          *, log: bool = False, cmap: str = "viridis", ax: Any = None) -> Any:
    if ax is None:
        _, ax = plt.subplots(figsize=(7.0, 5.5))
    finite = np.asarray(map_value, dtype=float).copy()
    finite[~np.isfinite(finite)] = np.nan
    kwargs: dict[str, Any] = {"origin": "lower", "extent": [0, 125, 0, 125], "aspect": "equal", "cmap": cmap}
    if log:
        positive = finite[np.isfinite(finite) & (finite > 0)]
        kwargs["norm"] = LogNorm(vmin=max(float(np.percentile(positive, 2)), 1e-3), vmax=float(np.percentile(positive, 98)))
    artist = ax.imshow(finite, **kwargs)
    ax.set(xlabel="q1（deg）", ylabel="q2（deg）", title=title)
    plt.colorbar(artist, ax=ax, label=label, shrink=0.83)
    return ax


def plot_maps(maps: dict[str, np.ndarray]) -> None:
    q1, q2 = np.meshgrid(maps["q1_deg"], maps["q2_deg"])
    static = maps["static_registered_force_n"]
    fig = plt.figure(figsize=(9.2, 7.0))
    ax = fig.add_subplot(111, projection="3d")
    shown = np.clip(static, 0.0, 500.0)
    ax.plot_surface(q1, q2, shown, cmap="viridis", linewidth=0, antialiased=True, alpha=0.9)
    ax.plot_surface(q1[::8, ::8], q2[::8, ::8], np.full_like(q1[::8, ::8], 200.0), color="#d18b00", alpha=0.28)
    ax.set(xlabel="q1（deg）", ylabel="q2（deg）", zlabel="|F_static|（N）",
           title="注册 allocator 下的准静态力曲面\n解析/模型推导，不是动态闭环 capability")
    ax.set_zlim(0, 225)
    fig.text(0.02, 0.02, "200 N 为注册仿真工程目标，不是临床阈值；曲面保留完整静态数值。", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_dense_static_force_surface.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    for ax, threshold in zip(axes, (200, 220, 250), strict=True):
        margin = maps[f"registered_margin_{threshold}n"]
        shown_margin = np.clip(margin, -250.0, 250.0)
        artist = ax.imshow(shown_margin, origin="lower", extent=[0, 125, 0, 125], aspect="equal",
                           cmap="RdBu", norm=TwoSlopeNorm(vmin=-250, vcenter=0, vmax=250))
        if float(np.nanmin(static)) <= threshold <= float(np.nanmax(static)):
            ax.contour(q1, q2, static, levels=[threshold], colors="black", linewidths=1.4)
        else:
            ax.text(0.5, 0.05, "全域无零余量交叉", transform=ax.transAxes,
                    ha="center", va="bottom", fontsize=9,
                    bbox={"facecolor": "white", "edgecolor": "0.65", "alpha": 0.85})
        ax.set(title=f"{threshold} N margin", xlabel="q1（deg）", ylabel="q2（deg）")
        plt.colorbar(artist, ax=ax, label=f"{threshold} - |F_static|（N）", shrink=0.82)
    fig.suptitle("准静态工程力余量：黑线为零余量轮廓（若存在）")
    fig.savefig(FIGURES / "02_force_margin_contours.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), constrained_layout=True)
    image(maps["translational_force_map_condition"], maps, "平移 Human force map 条件数", "condition number", log=True, ax=axes[0])
    image(maps["full_sagittal_allocation_condition"], maps, "完整 [Fx,Fz,My] allocation 条件数", "condition number", log=True, ax=axes[1])
    fig.suptitle("局部映射条件性（解析/模型推导）")
    fig.savefig(FIGURES / "03_conditioning_maps.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), constrained_layout=True)
    image(maps["unit_hip_acceleration_force_n_per_rad_s2"], maps,
          "单位 hip 加速度的平移力敏感度", "N / (rad/s^2)", log=True, ax=axes[0])
    image(maps["unit_knee_acceleration_force_n_per_rad_s2"], maps,
          "单位 knee 加速度的平移力敏感度", "N / (rad/s^2)", log=True, ax=axes[1])
    fig.suptitle("注册 allocator 下的局部加速度敏感度")
    fig.savefig(FIGURES / "04_unit_acceleration_sensitivity.png", dpi=210)
    plt.close(fig)


def plot_dynamic_overlay(maps: dict[str, np.ndarray], arms: dict[str, dict[str, dict[str, Any]]]) -> None:
    q1, q2 = np.meshgrid(maps["q1_deg"], maps["q2_deg"])
    static = np.clip(maps["static_registered_force_n"], 0.0, 300.0)
    fig = plt.figure(figsize=(11.0, 8.0))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(q1, q2, static, cmap="Greys", alpha=0.42, linewidth=0)
    colors = {"40/40": "#2563a8", "40/80": "#c43d4b", "90/120": "#18794e", "120/120": "#7046a3"}
    for label in CASES:
        for arm_name, style in (("rigid", "-"), ("P1", "--")):
            arm = arms[label][arm_name]
            trace, mechanics = arm["trace"], arm["mechanics"]
            count = min(len(trace["human_q_deg_god_view"]), len(mechanics["force_R_world"]))
            idx = np.unique(np.linspace(0, count - 1, min(900, count), dtype=int))
            q = trace["human_q_deg_god_view"][idx]
            force = np.linalg.norm(mechanics["force_R_world"][idx], axis=1)
            ax.plot(q[:, 0], q[:, 1], force, style, color=colors[label], lw=1.6,
                    label=f"{label} {arm_name}")
    ax.set(xlabel="q1（deg）", ylabel="q2（deg）", zlabel="力（N）",
           title="准静态姿态曲面与已观测动态物理力轨迹")
    ax.set_zlim(0, 300)
    ax.legend(ncol=2, fontsize=8, loc="upper left")
    fig.text(0.02, 0.02, "灰色曲面是姿态-only F_static；彩色曲线是历史依赖的闭环观测，动态力不是 q1、q2 的唯一函数。", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / "05_dynamic_trajectories_on_analytic_map.png", dpi=210)
    plt.close(fig)


def plot_decomposition(
    label: str,
    rigid: dict[str, Any],
    rigid_execution: dict[str, Any],
    p1_execution: dict[str, Any],
) -> None:
    t, f = rigid["time_s"], rigid["fields"]
    fig, axes = plt.subplots(3, 1, figsize=(12.0, 8.6), sharex=True, constrained_layout=True)
    axes[0].plot(t, np.linalg.norm(f["static"], axis=1), label="|F_static|", lw=1.7)
    axes[0].plot(t, np.linalg.norm(f["refdyn_increment"], axis=1), label="|ΔF_refdyn|", lw=1.4)
    axes[0].plot(t, np.linalg.norm(f["feedback_increment"], axis=1), label="|ΔF_feedback|", lw=1.4)
    axes[0].plot(t, np.linalg.norm(f["human_total"], axis=1), label="|F_total|", color="black", lw=1.2)
    axes[0].set_ylabel("Human-level 力（N）")
    axes[0].legend(ncol=4, fontsize=8)
    axes[0].set_title(f"{label}：向量分解幅值（曲线不可按标量相加）")

    rt = rigid_execution["time_s"]
    pt = p1_execution["time_s"]
    axes[1].plot(rt, np.linalg.norm(rigid_execution["command_force"], axis=1), label="Rigid command", color="#2563a8")
    axes[1].plot(rt, np.linalg.norm(rigid_execution["physical_force"], axis=1), label="Rigid physical", color="#0f3f70", lw=1.2)
    axes[1].plot(pt, np.linalg.norm(p1_execution["command_force"], axis=1), label="P1 command", color="#c43d4b")
    axes[1].plot(pt, np.linalg.norm(p1_execution["physical_force"], axis=1), label="P1 physical", color="#7d1f29", lw=1.2)
    axes[1].axhline(200.0, color="#9a6200", ls="--", lw=1.0, label="200 N 工程目标")
    axes[1].set_ylabel("执行层力（N）")
    axes[1].legend(ncol=3, fontsize=8)

    axes[2].plot(rt, np.linalg.norm(rigid_execution["residual_force"], axis=1), label="Rigid |physical-command|", color="#2563a8")
    axes[2].plot(pt, np.linalg.norm(p1_execution["residual_force"], axis=1), label="P1 |physical-command|", color="#c43d4b")
    axes[2].plot(t, np.linalg.norm(f["command_minus_human_total"], axis=1), label="Rigid |command-F_total|", color="#18794e", alpha=0.85)
    axes[2].set(xlabel="时间（s）", ylabel="residual（N）")
    axes[2].legend(ncol=3, fontsize=8)
    if rigid["first_brake_time_s"] is not None:
        for ax in axes:
            ax.axvline(rigid["first_brake_time_s"], color="#b4232d", ls=":", lw=1.4)
    for ax in axes:
        ax.grid(True, alpha=0.2)
    fig.savefig(FIGURES / f"06_decomposition_{label.replace('/', '_')}.png", dpi=210)
    plt.close(fig)


def save_tables(
    rigid_results: dict[str, dict[str, Any]],
    rigid_execution: dict[str, dict[str, Any]],
    p1_execution: dict[str, dict[str, Any]],
) -> None:
    with (OUTPUT / "trajectory_component_summary.csv").open("w", newline="") as stream:
        fields = ["case", "component", "rms_n", "peak_n", "at_human_total_peak_n", "rms_ratio_to_command", "peak_ratio_to_command"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for label, result in rigid_results.items():
            for component, stats in result["stats"].items():
                writer.writerow({"case": label, "component": component,
                                 "rms_n": stats["rms"], "peak_n": stats["peak"],
                                 "at_human_total_peak_n": stats["at_human_total_peak"],
                                 "rms_ratio_to_command": stats["rms_ratio_to_command"],
                                 "peak_ratio_to_command": stats["peak_ratio_to_command"]})
    event_rows = [row for result in rigid_results.values() for row in result["event_rows"]]
    if event_rows:
        with (OUTPUT / "boundary_event_summary.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(event_rows[0]))
            writer.writeheader(); writer.writerows(event_rows)
    with (OUTPUT / "execution_layer_summary.csv").open("w", newline="") as stream:
        fields = ["case", "arm", "component", "rms_n", "peak_n"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for arm_name, results in (("rigid", rigid_execution), ("P1", p1_execution)):
            for label, result in results.items():
                for component, stats in result["stats"].items():
                    writer.writerow({"case": label, "arm": arm_name, "component": component,
                                     "rms_n": stats["rms"], "peak_n": stats["peak"]})


def build_report(summary: dict[str, Any]) -> str:
    rigid = summary["rigid"]
    rigid_execution = summary["rigid_execution"]
    p1_execution = summary["p1_execution_only"]
    rows = []
    for label in CASES:
        s = rigid[label]["stats"]
        rows.append(
            f"| {label} | {s['static']['rms']:.2f}/{s['static']['peak']:.2f} | "
            f"{s['refdyn_increment']['rms']:.2f}/{s['refdyn_increment']['peak']:.2f} | "
            f"{s['feedback_increment']['rms']:.2f}/{s['feedback_increment']['peak']:.2f} | "
            f"{s['human_total']['rms']:.2f}/{s['human_total']['peak']:.2f} |"
        )
    execution_rows = []
    for label in CASES:
        for arm_name, result in (("Rigid", rigid_execution[label]), ("P1", p1_execution[label])):
            s = result["stats"]
            execution_rows.append(
                f"| {label} | {arm_name} | {s['command']['rms']:.2f}/{s['command']['peak']:.2f} | "
                f"{s['physical']['rms']:.2f}/{s['physical']['peak']:.2f} | "
                f"{s['execution_interface_residual']['rms']:.2f}/{s['execution_interface_residual']['peak']:.2f} |"
            )
    event_lines = []
    for row in summary["boundary_events"]:
        event_lines.append(
            f"| {row['case']} {row['location']} | {row['time_s']:.3f} | {row['static_force_n']:.2f} | "
            f"{row['refdyn_increment_n']:.2f} | {row['feedback_increment_n']:.2f} | "
            f"{row['feedback_projection_on_total_n']:.2f} | {row['no_feedback_counterfactual_force_n']:.2f} | "
            f"{row['human_total_force_n']:.2f} | {row['command_force_n']:.2f} | "
            f"{row['nominal_executable_force_n'] if row['nominal_executable_force_n'] is not None else 'n/a'} |"
        )
    static_rms = np.array([rigid[label]["stats"]["static"]["rms"] for label in CASES])
    ref_rms = np.array([rigid[label]["stats"]["refdyn_increment"]["rms"] for label in CASES])
    fb_rms = np.array([rigid[label]["stats"]["feedback_increment"]["rms"] for label in CASES])
    command_rms = np.array([rigid[label]["stats"]["command"]["rms"] for label in CASES])
    map_stats = summary["dense_maps"]
    static_map = map_stats["static_registered_force_n"]
    margin_200 = map_stats["registered_margin_200n"]
    hip_sensitivity = map_stats["unit_hip_acceleration_force_n_per_rad_s2"]
    knee_sensitivity = map_stats["unit_knee_acceleration_force_n_per_rad_s2"]
    return f"""# Phase 3A 离线模型力分解与稠密力图谱

证据类别：**offline analytic/model-derived diagnostic**。本分析只读取冻结的四组 Rigid/P1 证据，没有运行新轨迹、推进 plant、调用 MPC 或修改任何科学设置。

## 定义与边界

- Human-level 计算使用冻结 population-prior Human model、control estimated q、已保存 reference phase/speed/rate，以及注册的 1:1 cuff-aware memoryless allocator。
- `tau_static = G(q) + tau_passive(q,0)`；`tau_refdyn = M(q)qdd_ref + C(q,dq_ref)dq_ref`；`tau_feedback = tau_des - tau_static - tau_refdyn`。
- allocator 在固定 q 下是线性的，因此 `w_total = w_static + delta_w_refdyn + delta_w_feedback` 在向量层闭合；三个向量的 norm 不可直接相加。
- `physical-command` 是独立的 execution/interface residual。P1 spring/damping 只出现在该执行层比较中，没有被塞进 Human torque 分解。
- `tau_feedback` 是按上述排除式定义的 correction bucket；它包含所有未被 static 与 nominal reference dynamics 解释的 MPC demand，不能进一步等同于某一个单独 cost term。

## Rigid 轨迹分解

数值均为 RMS/peak，单位 N。Human-level 表在 control 时刻计算；`feedback` 的原始 peak 均出现在 t=0 初始化点（85.63 N），因此轨迹边界解释以下面的事件表为准。

| 轨迹 | F_static | delta F_refdyn | delta F_feedback | Human F_total |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

分量相对 command RMS 的跨轨迹中位比值为：static **{np.median(static_rms/command_rms):.3f}**、reference dynamics **{np.median(ref_rms/command_rms):.3f}**、feedback/correction **{np.median(fb_rms/command_rms):.3f}**。这些是 magnitude ratio，不是可相加百分比。

## 执行与接口层

下表在完整 physics 采样率上把已保存 command 以零阶保持方式对齐，因而保留了 P1 120/120 的 222.22 N 终止瞬态。

| 轨迹 | 接口 | command RMS/peak | physical RMS/peak | physical-command RMS/peak |
|---|---|---:|---:|---:|
{chr(10).join(execution_rows)}

`physical-command` 是 world-frame 向量差的 norm。它不能只凭幅值被解释成 spring 或 damping；P1 的详细 spring/damping 分解仍以既有 120/120 事件审计为准。

## 200 N 可行性边界附近

| 位置 | t (s) | static | refdyn | feedback | feedback 沿 total 投影 | 无 feedback 反事实 | Human total | command | Safety nominal executable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(event_lines)}

这里同时列出 feedback 向量幅值、沿 total-force 方向的投影和移除 feedback 后的反事实 norm，避免把向量 norm 当成可加标量。Safety Filter 的 `nominal executable` 是保存诊断，不属于 Human-level allocator 分解。

## 稠密数学图谱

- domain：q1、q2 各 0–125°，1° 网格；q2=0° 的奇异点保留为 NaN/Inf。
- `static_registered_force_n` 使用注册 1:1 cuff-aware allocator，是轨迹分解的 F_static。
- `static_minimum_translational_force_n` 使用同一 Human torque 约束下的纯最小平移力 allocator，只作为数学下界对照。
- 200/220/250 N 图是 static registered force 的工程余量，不是动态 closed-loop capability，也不是临床阈值。
- conditioning 同时给出 2×2 translational force map 与完整 2×3 sagittal allocation map。
- hip/knee sensitivity 表示 1 rad/s² 单关节加速度增量经注册 allocator 产生的平移力 norm。
- 没有生成单一“200 N acceleration authority”图，因为正负加速度方向、另一关节协同、背景 static wrench 与 moment 约束会产生多个不同而都合理的定义。
- 注册 allocator 的 static force 全域为 **{static_map['minimum']:.2f}–{static_map['maximum']:.2f} N**；最小 200 N static margin 仍为 **{margin_200['minimum']:.2f} N**，所以 200/220/250 N 图均没有零余量交叉线。
- 单位 1 rad/s² 敏感度：hip **{hip_sensitivity['minimum']:.2f}–{hip_sensitivity['maximum']:.2f} N**，knee **{knee_sensitivity['minimum']:.2f}–{knee_sensitivity['maximum']:.2f} N**。

## 解释

### DIRECTLY DERIVED

- 四条 Rigid 轨迹的 static、reference-dynamic、feedback/correction wrench 分量均按同一 world frame 重建，并在向量层闭合。
- 跨轨迹 RMS 中位数：static **{np.median(static_rms):.2f} N**，nominal reference dynamics **{np.median(ref_rms):.2f} N**，feedback/correction **{np.median(fb_rms):.2f} N**。
- A：在 RMS 尺度上，static mechanics 是主要负担：四条轨迹为 **90.07–103.18 N**，相当于 command RMS 的 **78.7%–99.7%**。但它单独不解释 rigid 边界失效。
- B：nominal trajectory dynamics 很小：RMS **0.09–0.26 N**，全轨迹 peak **0.64 N**；在本冻结慢轨迹下不是主要项。
- C：feedback/correction 平常为 **5.91–12.64 N RMS**，但在边界前可沿 total-force 方向增加约 **38 N**，不能视为始终微小的扰动。原始 85.63 N peak 是 t=0 初始化点。
- 稠密图谱显示的是解析 Human mechanics 与 allocator 几何，不是动态能力边界。

### SUPPORTED BY CURRENT EVIDENCE

- D：40/80 在 BRAKE 前，移除 feedback 的反事实为 **104.87 N**，加入 feedback 后 Human total 为 **143.23 N**；同一周期保存的 nominal executable 已达 **206.08 N**。120/120 也出现 feedback 向量方向翻转，并把 Human total 从约 **81.57 N** 推到约 **120.07 N**，随后 command/Safety nominal 超过 200 N。两次 crossing 都不是 static 或 nominal reference acceleration 单独造成；feedback 是触发链的重要部分，剩余放大出现在 robot execution/Safety Filter 层。
- E：当前证据支持 controller/execution stack 在 High-ROM 边界附近对 command force 有实质放大：Human total 尚低于 200 N 时，command/Safety nominal 已触及或越过 200 N。这里的“controller/execution stack”不能再细分为 MPC cost、robot pose/twist feedback、nullspace 或 Safety Filter 的单独因果份额。
- Rigid 的 `command - Human F_total` 与 `physical - command` 表明 Human torque demand 之外仍存在 robot execution feedback、Safety Filter/nullspace 选择和 plant/interface transient。
- P1 的 execution residual 包含 spring/damping/interface state；当前数据支持执行层差异，但不支持把它重新归因到 Human static/refdyn/feedback 三项。

### UNRESOLVED

- 该排除式不能把 `tau_feedback` 继续分解为 MPC cost、state-estimation error、passive velocity term或 optimizer switching 的独立因果贡献。
- 仅凭保存轨迹不能建立放宽 force budget 后 120/120 的完整 continuation，也不能建立 hardware 或 clinical capability。

### NOT SUPPORTED

- 不支持把 dynamic physical force 当作 q1、q2 的唯一函数。
- 不支持把任何分量 ratio 当作可相加的“贡献百分比”。
- 不支持“模型方法优于 RL”或任何临床安全结论。

## 建议

三项候选中建议选择 **2. controller-side investigation**。聚焦 40/80 与 120/120 的 Human feedback/correction、robot pose/twist execution feedback、allocator/nullspace 与 Safety Filter 可行性之间的分层关系。当前离线结果已经排除 static mechanics 与 nominal trajectory acceleration 作为 200 N crossing 的单独解释；直接放宽 120/120 force budget 会改变终止边界，却不能解决剩余归因。完成这一层离线或极小局部审计后，再决定是否预注册 relaxed 120/120 continuation。
"""


def main() -> None:
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True, text=True, capture_output=True
    ).stdout.strip()
    expected_head = "5452d09c6ab7d2c17dda78dadb65c7e28c381c95"
    if current_head != expected_head:
        raise RuntimeError(f"frozen evidence HEAD mismatch: expected {expected_head}, got {current_head}")
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    FIGURES.mkdir(parents=True)
    arms = {label: {arm: load_arm(label, arm) for arm in ("rigid", "P1")} for label in CASES}

    fingerprints = []
    source_hashes: dict[str, str] = {}
    for label in CASES:
        for arm_name in ("rigid", "P1"):
            arm = arms[label][arm_name]
            trace = arm["trace"]
            fingerprints.append(np.concatenate([trace["dynamic_base_estimate"][0], trace["geometry_estimate"][0]]))
            for filename in ("trace.npz", "mechanics.npz", "commands.npz", "modes.npz", "result.json", "run_config.json"):
                path = arm["root"] / filename
                source_hashes[str(path.relative_to(REPO))] = sha256(path)
    for fingerprint in fingerprints[1:]:
        np.testing.assert_allclose(fingerprint, fingerprints[0], rtol=0.0, atol=1e-12)
    model = frozen_model(arms["40/40"]["rigid"])

    rigid_results = {}
    rigid_execution_results = {}
    p1_execution_results = {}
    for label in CASES:
        print(f"DECOMPOSE {label}", flush=True)
        rigid_results[label] = decompose_rigid(label, arms[label]["rigid"], model)
        rigid_execution_results[label] = execution_layer(label, "rigid", arms[label]["rigid"])
        p1_execution_results[label] = execution_layer(label, "P1", arms[label]["P1"])
        plot_decomposition(
            label, rigid_results[label], rigid_execution_results[label], p1_execution_results[label]
        )
    print("DENSE MAPS", flush=True)
    maps = dense_maps(model)
    save_dense_data(maps)
    plot_maps(maps)
    plot_dynamic_overlay(maps, arms)
    save_tables(rigid_results, rigid_execution_results, p1_execution_results)

    serial_rigid = {
        label: {key: value for key, value in result.items() if key not in {"time_s", "fields", "event_rows"}}
        for label, result in rigid_results.items()
    }
    serial_rigid_execution = {
        label: {"stats": result["stats"]} for label, result in rigid_execution_results.items()
    }
    serial_p1 = {label: {"stats": result["stats"]} for label, result in p1_execution_results.items()}
    events = [row for result in rigid_results.values() for row in result["event_rows"]]
    map_summary = {
        key: {
            "finite_count": int(np.count_nonzero(np.isfinite(value))),
            "minimum": float(np.min(value[np.isfinite(value)])) if np.any(np.isfinite(value)) else None,
            "median": float(np.median(value[np.isfinite(value)])) if np.any(np.isfinite(value)) else None,
            "maximum": float(np.max(value[np.isfinite(value)])) if np.any(np.isfinite(value)) else None,
        }
        for key, value in maps.items() if key not in {"q1_deg", "q2_deg"}
    }
    summary = {
        "schema": "phase3a_offline_force_decomposition_v1",
        "evidence_category": "offline_analytic_model_derived_diagnostic",
        "source_head": expected_head,
        "new_trajectory_runs": 0,
        "scientific_settings_changed": False,
        "frame": "world; wrench ordering [Fx,Fy,Fz,Mx,My,Mz]",
        "torque_decomposition": {
            "static": "G(q)+tau_passive(q,0)",
            "reference_dynamic": "M(q)qdd_ref+C(q,dq_ref)dq_ref",
            "feedback": "tau_des-static-reference_dynamic",
            "norm_warning": "vector contributions close exactly; norms and ratios are not additive percentages",
        },
        "rigid": serial_rigid,
        "rigid_execution": serial_rigid_execution,
        "p1_execution_only": serial_p1,
        "boundary_events": events,
        "dense_maps": map_summary,
        "source_hashes": source_hashes,
    }
    write_json(OUTPUT / "summary.json", summary)
    (OUTPUT / "REPORT.md").write_text(build_report(summary))
    write_json(OUTPUT / "manifest.json", {
        "script": str(Path(__file__).relative_to(REPO)),
        "script_sha256": sha256(Path(__file__)),
        "source_hashes": source_hashes,
        "outputs": sorted(str(path.relative_to(OUTPUT)) for path in OUTPUT.rglob("*") if path.is_file()),
    })
    print(json.dumps({
        "output": str(OUTPUT),
        "figures": len(list(FIGURES.glob("*.png"))),
        "boundary_rows": len(events),
        "grid_shape": list(maps["static_registered_force_n"].shape),
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
