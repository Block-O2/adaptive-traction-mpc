"""CSV, plots, and synchronized GIF artifacts for M1 engineering smoke."""

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
from .experiment import CaseResult, result_metadata
from .model import build_mjcf


def write_case_artifacts(result: CaseResult, output_dir: Path, make_gif: bool = False) -> None:
    case_dir = output_dir / result.case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(case_dir / "timeseries.npz", **result.arrays)
    with (case_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(result_metadata(result), file, indent=2, allow_nan=False)
    _write_timeseries_csv(result, case_dir / "timeseries.csv")
    create_summary_plot(result, case_dir / "synchronized_timeseries.png")
    if make_gif:
        create_synchronized_gif(result, case_dir / "protective_mode_full_action.gif")


def write_experiment_summary(
    output_dir: Path,
    baseline: CaseResult,
    veto_probe: CaseResult,
    sensitivity: list[CaseResult],
    sensitivity_status: str,
) -> None:
    rows = [baseline.metrics, veto_probe.metrics, *[case.metrics for case in sensitivity]]
    fields = sorted({key for row in rows for key in row})
    with (output_dir / "concise_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "evidence_category": "engineering_smoke_not_authoritative",
        "baseline": baseline.metrics,
        "manual_veto_probe": veto_probe.metrics,
        "sensitivity_status": sensitivity_status,
        "sensitivity": [case.metrics for case in sensitivity],
        "model_assumptions": model_assumptions(baseline.config, baseline.parameters),
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, allow_nan=False)
    with (output_dir / "model_snapshot.xml").open("w", encoding="utf-8") as file:
        file.write(build_mjcf(baseline.parameters, baseline.config))


def model_assumptions(config: ProtectiveModeConfig, parameters: HumanV2Parameters) -> dict[str, Any]:
    return {
        "human": "Human V2 nominal geometry, mass, planar inertia, passive K/B, and ROM",
        "unused_3d_inertia": "Ixx=Izz=0.51*Iyy; planar Iyy is unchanged",
        "bed": "MuJoCo unilateral compliant plane contact; force comes only from contact solver",
        "robot": "0.5 kg planar x/z carriage with bounded motor and Cartesian PD servo adapter",
        "robot_api_status": "abstract actuator contract, not a hardware SDK/API claim",
        "cuff": "tension-only compliant spatial tendon with slack; not a resolved anatomical cuff",
        "interaction_force_sensor": "force reconstructed from MuJoCo tendon length/velocity and frozen constitutive law",
        "adaptive_identification": "not present",
        "force_veto_limit_n": config.force_veto_limit_n,
        "q_switch_deg": config.q_switch_deg,
        "q_terminal_deg": config.q_terminal_deg,
        "height_m": parameters.height_m,
        "body_mass_kg": parameters.body_mass_kg,
    }


def create_summary_plot(result: CaseResult, path: Path) -> None:
    a = result.arrays
    time = a["time_s"]
    fig, axes = plt.subplots(5, 1, figsize=(13, 13), sharex=True, constrained_layout=True)
    axes[0].plot(time, np.degrees(a["q_rad"][:, 1]), label="measured q2")
    axes[0].plot(time, np.degrees(a["q_reference_rad"][:, 1]), "--", label="command reference")
    axes[0].axhline(result.config.q_switch_deg, color="k", linestyle=":", label="q_switch")
    axes[0].axhline(result.config.q_terminal_deg, color="0.5", linestyle=":", label="terminal")
    axes[0].set_ylabel("q2 (deg)")
    axes[0].legend(loc="best", ncol=4)

    axes[1].plot(time, a["interaction_force_n"], label="interaction force")
    axes[1].plot(time, a["peak_interaction_force_n"], color="tab:red", alpha=0.45, label="substep peak")
    axes[1].axhline(result.config.force_veto_limit_n, color="k", linestyle="--", label="veto limit")
    axes[1].set_ylabel("force (N)")
    axes[1].legend(loc="best")

    axes[2].plot(time, a["bed_force_n"], label="bed force")
    axes[2].plot(time, a["peak_bed_force_n"], color="tab:red", alpha=0.45, label="substep peak bed force")
    axes[2].plot(time, 1000 * a["bed_penetration_m"], label="penetration (mm)")
    axes[2].set_ylabel("bed N / mm")
    axes[2].legend(loc="best")

    axes[3].plot(time, a["robot_position_m"][:, 0], label="robot x")
    axes[3].plot(time, a["robot_command_position_m"][:, 0], "--", label="x cmd")
    axes[3].plot(time, a["robot_position_m"][:, 1], label="robot z")
    axes[3].plot(time, a["robot_command_position_m"][:, 1], "--", label="z cmd")
    axes[3].set_ylabel("robot (m)")
    axes[3].legend(loc="best", ncol=4)

    codes, labels = _mode_codes(a["mode"])
    axes[4].step(time, codes, where="post")
    axes[4].set_yticks(np.arange(len(labels)), labels)
    axes[4].set_ylabel("mode")
    axes[4].set_xlabel("time (s)")
    fig.suptitle(f"{result.case_name}: {result.metrics['classification']}")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def create_synchronized_gif(result: CaseResult, path: Path) -> None:
    a = result.arrays
    frame_indices = np.unique(np.linspace(0, len(a["time_s"]) - 1, 150).astype(int))
    frames: list[Image.Image] = []
    p = result.parameters
    for index in frame_indices:
        fig = plt.figure(figsize=(12, 6.5), constrained_layout=True)
        layout = fig.add_gridspec(3, 2, width_ratios=(1.0, 1.45))
        mechanism = fig.add_subplot(layout[:, 0])
        q1, q2 = a["q_rad"][index]
        hip = np.array([0.0, result.config.hip_height_m])
        knee = hip + p.thigh_length_m * np.array([np.cos(q1), np.sin(q1)])
        ankle = knee + p.shank_length_m * np.array([np.cos(q1 - q2), np.sin(q1 - q2)])
        cuff = knee + p.cuff_location_m * np.array([np.cos(q1 - q2), np.sin(q1 - q2)])
        robot = a["robot_position_m"][index]
        command = a["robot_command_position_m"][index]
        mechanism.plot([-0.2, 1.1], [result.config.bed_height_m] * 2, "k-", linewidth=6)
        mechanism.plot([hip[0], knee[0], ankle[0]], [hip[1], knee[1], ankle[1]], "o-", linewidth=6)
        mechanism.plot([robot[0], cuff[0]], [robot[1], cuff[1]], color="tab:green", linewidth=3)
        mechanism.scatter(*robot, s=90, color="tab:green", label="robot EE")
        mechanism.scatter(*command, s=90, facecolors="none", edgecolors="tab:purple", label="EE command")
        mechanism.set_xlim(-0.1, 1.0)
        mechanism.set_ylim(-0.02, 0.65)
        mechanism.set_aspect("equal")
        mechanism.grid(True)
        mechanism.legend(loc="upper right")
        mechanism.set_title(
            f"t={a['time_s'][index]:.2f}s  {a['mode'][index]}\n"
            f"q2={np.degrees(q2):.2f}deg  Fint={a['interaction_force_n'][index]:.1f}N  "
            f"Fbed={a['bed_force_n'][index]:.1f}N"
        )

        q_ax = fig.add_subplot(layout[0, 1])
        force_ax = fig.add_subplot(layout[1, 1])
        bed_ax = fig.add_subplot(layout[2, 1])
        visible = slice(0, index + 1)
        q_ax.plot(a["time_s"][visible], np.degrees(a["q_rad"][visible, 1]), label="q2")
        q_ax.plot(a["time_s"][visible], np.degrees(a["q_reference_rad"][visible, 1]), "--", label="reference")
        q_ax.set_ylabel("q2 (deg)")
        q_ax.legend(loc="upper left")
        force_ax.plot(a["time_s"][visible], a["interaction_force_n"][visible])
        force_ax.axhline(result.config.force_veto_limit_n, color="r", linestyle="--")
        force_ax.set_ylabel("interaction (N)")
        bed_ax.plot(a["time_s"][visible], a["bed_force_n"][visible], label="bed force")
        bed_ax.plot(a["time_s"][visible], 1000 * a["bed_penetration_m"][visible], label="penetration mm")
        bed_ax.set_ylabel("bed N / mm")
        bed_ax.set_xlabel("time (s)")
        bed_ax.legend(loc="upper left")
        for axis in (q_ax, force_ax, bed_ax):
            axis.set_xlim(a["time_s"][0], a["time_s"][-1])
            axis.grid(True)
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        frames.append(Image.fromarray(rgba[..., :3].copy()))
        plt.close(fig)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=80, loop=0, optimize=True)


def _write_timeseries_csv(result: CaseResult, path: Path) -> None:
    a = result.arrays
    fields = [
        "time_s",
        "mode",
        "q1_deg",
        "q2_deg",
        "q1_ref_deg",
        "q2_ref_deg",
        "interaction_force_n",
        "bed_force_n",
        "bed_penetration_mm",
        "cuff_extension_mm",
        "robot_x_m",
        "robot_z_m",
        "robot_x_cmd_m",
        "robot_z_cmd_m",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for index, time_s in enumerate(a["time_s"]):
            writer.writerow(
                {
                    "time_s": time_s,
                    "mode": a["mode"][index],
                    "q1_deg": np.degrees(a["q_rad"][index, 0]),
                    "q2_deg": np.degrees(a["q_rad"][index, 1]),
                    "q1_ref_deg": np.degrees(a["q_reference_rad"][index, 0]),
                    "q2_ref_deg": np.degrees(a["q_reference_rad"][index, 1]),
                    "interaction_force_n": a["interaction_force_n"][index],
                    "bed_force_n": a["bed_force_n"][index],
                    "bed_penetration_mm": 1000 * a["bed_penetration_m"][index],
                    "cuff_extension_mm": 1000 * a["cuff_extension_m"][index],
                    "robot_x_m": a["robot_position_m"][index, 0],
                    "robot_z_m": a["robot_position_m"][index, 1],
                    "robot_x_cmd_m": a["robot_command_position_m"][index, 0],
                    "robot_z_cmd_m": a["robot_command_position_m"][index, 1],
                }
            )


def _mode_codes(modes: np.ndarray) -> tuple[np.ndarray, list[str]]:
    labels: list[str] = []
    codes = np.zeros(len(modes), dtype=int)
    for index, mode in enumerate(modes.tolist()):
        if mode not in labels:
            labels.append(mode)
        codes[index] = labels.index(mode)
    return codes, labels
