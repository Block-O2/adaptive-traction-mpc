"""Artifacts for the MuJoCo M1.5 physical-interface diagnostics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .config import HumanV2Parameters, ProtectiveModeConfig
from .physical_interface_m15 import DiagnosticResult


def write_m15_artifacts(
    output_dir: Path,
    equilibrium: DiagnosticResult,
    probes: list[DiagnosticResult],
    summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_result(output_dir, equilibrium)
    for probe in probes:
        _write_result(output_dir, probe)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, allow_nan=False)
    _write_comparison_csv(output_dir / "concise_comparison.csv", probes)
    create_equilibrium_plot(equilibrium, output_dir / "bed_start_equilibrium.png")
    create_authority_plot(probes, output_dir / "authority_comparison.png")
    representative = {
        (result.metrics["interface"], result.metrics["requested_q2_deg"], result.metrics["direction"]): result
        for result in probes
    }
    create_authority_gif(
        representative[("tension_only", 20.0, "flexion")],
        representative[("bilateral_point", 20.0, "flexion")],
        output_dir / "authority_probe_20deg_flexion.gif",
    )


def _write_result(output_dir: Path, result: DiagnosticResult) -> None:
    np.savez_compressed(output_dir / f"{result.name}.npz", **result.arrays)
    with (output_dir / f"{result.name}.json").open("w", encoding="utf-8") as file:
        json.dump(result.metrics, file, indent=2, allow_nan=False)


def _write_comparison_csv(path: Path, probes: list[DiagnosticResult]) -> None:
    rows = [result.metrics for result in probes]
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def create_equilibrium_plot(result: DiagnosticResult, path: Path) -> None:
    arrays = result.arrays
    time = arrays["time_s"]
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True, constrained_layout=True)
    axes[0].plot(time, np.degrees(arrays["q_rad"][:, 0]), label="q1")
    axes[0].plot(time, np.degrees(arrays["q_rad"][:, 1]), label="q2")
    axes[0].axhline(2.0, color="k", linestyle="--", label="requested q2")
    axes[0].set_ylabel("angle (deg)")
    axes[0].legend()
    axes[1].plot(time, np.degrees(arrays["dq_rad_s"][:, 0]), label="dq1")
    axes[1].plot(time, np.degrees(arrays["dq_rad_s"][:, 1]), label="dq2")
    axes[1].set_ylabel("speed (deg/s)")
    axes[1].legend()
    axes[2].plot(time, arrays["bed_force_n"], label="bed force")
    axes[2].plot(time, arrays["peak_bed_force_n"], alpha=0.5, label="substep peak")
    axes[2].set_ylabel("bed force (N)")
    axes[2].legend()
    axes[3].plot(time, 1000 * arrays["bed_penetration_m"], label="penetration")
    axes[3].step(time, arrays["bed_contact_count"], where="post", label="contact count")
    axes[3].set_ylabel("mm / count")
    axes[3].set_xlabel("time (s)")
    axes[3].legend()
    fig.suptitle(f"BED_START: {result.metrics['classification']}")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def create_authority_plot(probes: list[DiagnosticResult], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    markers = {"flexion": "o", "extension": "s"}
    colors = {"tension_only": "tab:orange", "bilateral_point": "tab:blue"}
    for interface in ("tension_only", "bilateral_point"):
        for direction in ("flexion", "extension"):
            cases = sorted(
                (
                    result.metrics
                    for result in probes
                    if result.metrics["interface"] == interface
                    and result.metrics["direction"] == direction
                ),
                key=lambda item: item["requested_q2_deg"],
            )
            q = [item["requested_q2_deg"] for item in cases]
            label = f"{interface} / {direction}"
            style = dict(marker=markers[direction], color=colors[interface], label=label)
            axes[0, 0].plot(q, [item["hold_final_q2_deg"] for item in cases], **style)
            axes[0, 1].plot(
                q, [item["effective_delta_q2_deg_per_mm"] for item in cases], **style
            )
            axes[1, 0].plot(q, [item["motion_absorbed_by_interface_ratio"] for item in cases], **style)
            axes[1, 1].plot(q, [item["peak_interaction_force_n"] for item in cases], **style)
    axes[0, 0].plot([2, 10, 20, 30], [2, 10, 20, 30], "k--", label="requested")
    axes[0, 0].set_ylabel("hold rollout q2 at 1 s (deg)")
    axes[0, 1].axhline(0.0, color="k", linestyle="--")
    axes[0, 1].set_ylabel("paired Δq2/Δx (deg/mm)")
    axes[1, 0].axhline(0.5, color="k", linestyle="--", label="majority absorbed")
    axes[1, 0].set_ylabel("interface deformation / robot Δx")
    axes[1, 1].axhline(200.0, color="k", linestyle="--", label="force veto")
    axes[1, 1].set_ylabel("peak interaction force (N)")
    for axis in axes.flat:
        axis.set_xlabel("requested initial q2 (deg)")
        axis.grid(True)
        axis.legend(fontsize=8)
    fig.suptitle("M1.5 paired local actuator-authority probes")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def create_authority_gif(
    tension: DiagnosticResult,
    bilateral: DiagnosticResult,
    path: Path,
) -> None:
    frame_indices = np.unique(np.linspace(0, len(tension.arrays["time_s"]) - 1, 80).astype(int))
    frames: list[Image.Image] = []
    parameters = HumanV2Parameters()
    config = ProtectiveModeConfig()
    for index in frame_indices:
        fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
        for column, result in enumerate((tension, bilateral)):
            arrays = result.arrays
            q1, q2 = arrays["q_rad"][index]
            hip = np.array([0.0, config.hip_height_m])
            knee = hip + parameters.thigh_length_m * np.array([np.cos(q1), np.sin(q1)])
            ankle = knee + parameters.shank_length_m * np.array(
                [np.cos(q1 - q2), np.sin(q1 - q2)]
            )
            cuff = knee + parameters.cuff_location_m * np.array(
                [np.cos(q1 - q2), np.sin(q1 - q2)]
            )
            robot = arrays["robot_position_m"][index]
            mechanism = axes[0, column]
            mechanism.plot([-0.1, 1.0], [config.bed_height_m] * 2, "k-", linewidth=5)
            mechanism.plot(
                [hip[0], knee[0], ankle[0]], [hip[1], knee[1], ankle[1]], "o-", linewidth=5
            )
            mechanism.plot([robot[0], cuff[0]], [robot[1], cuff[1]], color="tab:green")
            mechanism.scatter(*robot, color="tab:green", s=60)
            mechanism.set_xlim(-0.1, 1.0)
            mechanism.set_ylim(-0.03, 0.42)
            mechanism.set_aspect("equal")
            mechanism.grid(True)
            mechanism.set_title(
                f"{result.metrics['interface']}\n"
                f"q2={np.degrees(q2):.2f} deg, F={arrays['interaction_force_n'][index]:.1f} N"
            )
            trace = axes[1, column]
            visible = slice(0, index + 1)
            trace.plot(
                arrays["time_s"][visible],
                np.degrees(arrays["q_rad"][visible, 1]),
                label="probe q2",
            )
            trace.plot(
                arrays["time_s"][visible],
                np.degrees(arrays["hold_q_rad"][visible, 1]),
                "--",
                label="paired hold q2",
            )
            trace.set_xlim(arrays["time_s"][0], arrays["time_s"][-1])
            trace.set_ylim(-3, 22)
            trace.set_xlabel("time (s)")
            trace.set_ylabel("q2 (deg)")
            trace.grid(True)
            trace.legend()
        fig.suptitle("20 deg flexion-direction authority probe (initial posture is not equilibrium)")
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        frames.append(Image.fromarray(rgba[..., :3].copy()))
        plt.close(fig)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True,
    )
