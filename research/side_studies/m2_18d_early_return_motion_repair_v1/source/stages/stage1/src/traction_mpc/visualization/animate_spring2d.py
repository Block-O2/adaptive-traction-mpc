"""Visualization utilities for Spring2D environment rollouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter


def _series(history: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([row[key] for row in history], dtype=float)


def save_spring2d_animation(
    history: list[dict[str, Any]],
    params: dict[str, Any],
    out_path: Path,
    fps: int = 25,
) -> None:
    """Save a three-panel GIF for a Spring2D rollout."""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(history) < 2:
        raise ValueError("Need at least two history samples to animate.")

    t = _series(history, "t")
    theta = _series(history, "theta")
    omega = _series(history, "omega")
    r = _series(history, "r")
    delta_r = _series(history, "delta_r")
    I = _series(history, "I")
    spring_force = _series(history, "spring_force")
    gravity_torque = _series(history, "gravity_torque")
    angular_accel = _series(history, "angular_accel")
    radial_accel = _series(history, "radial_accel")
    base_x = _series(history, "base_x")
    base_a = _series(history, "base_a")
    base_ap = _series(history, "base_ap")
    r_ddot = _series(history, "r_ddot")
    omega_dot = _series(history, "omega_dot")
    F_tan = _series(history, "F_tan")
    F_rad = _series(history, "F_rad")
    contact_x = _series(history, "contact_x")
    contact_y = _series(history, "contact_y")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    ax_geo, ax_force, ax_info = axes
    fig.tight_layout(pad=2.5)

    all_x = np.concatenate([_series(history, "base_x"), _series(history, "tip_x"), contact_x])
    all_y = np.concatenate([_series(history, "base_y"), _series(history, "tip_y"), contact_y])
    margin = max(float(params["L0"]) * 0.35, 0.08)
    ax_geo.set_xlim(float(all_x.min()) - margin, float(all_x.max()) + margin)
    ax_geo.set_ylim(min(-margin, float(all_y.min()) - margin), float(all_y.max()) + margin)
    ax_geo.set_aspect("equal", adjustable="box")
    ax_geo.set_title("Geometry")
    ax_geo.set_xlabel("x [m]")
    ax_geo.set_ylabel("y [m]")

    base_track_y = float(params.get("base_y0", 0.0))
    base_track_margin = max(0.02, 0.1 * max(float(base_x.max() - base_x.min()), 0.01))
    ax_geo.plot(
        [float(base_x.min()) - base_track_margin, float(base_x.max()) + base_track_margin],
        [base_track_y, base_track_y],
        color="0.6",
        linestyle=":",
        linewidth=1.4,
        label="base slide track",
    )

    target = float(params["theta_target"])
    base0_x = float(params.get("base_x0", 0.0))
    base0_y = float(params.get("base_y0", 0.0))
    target_len = float(params["L0"]) * 1.15
    ax_geo.plot(
        [base0_x, base0_x + target_len * np.cos(target)],
        [base0_y, base0_y + target_len * np.sin(target)],
        color="tab:red",
        linestyle="--",
        linewidth=1.0,
        label="target angle",
    )

    rod_line, = ax_geo.plot([], [], color="tab:blue", linewidth=3, label="rod/spring")
    traj_line, = ax_geo.plot([], [], color="tab:green", linewidth=1.2, alpha=0.8, label="contact trajectory")
    base_dot, = ax_geo.plot([], [], "o", color="black", markersize=6, label="base")
    tip_dot, = ax_geo.plot([], [], "o", color="tab:blue", markersize=6, label="tip")
    contact_dot, = ax_geo.plot([], [], "o", color="tab:orange", markersize=6, label="contact")
    rad_arrow = ax_geo.quiver([], [], [], [], color="tab:purple", scale=8, width=0.006)
    tan_arrow = ax_geo.quiver([], [], [], [], color="tab:brown", scale=8, width=0.006)
    force_arrow = ax_geo.quiver([], [], [], [], color="tab:red", scale=120, width=0.006)
    gravity_arrow = ax_geo.quiver([], [], [], [], color="0.25", scale=60, width=0.005)
    ax_geo.legend(loc="upper left", fontsize=7)

    ax_force.set_title("Force History")
    ax_force.set_xlabel("time [s]")
    ax_force.set_ylabel("force [N]")
    ax_force.set_xlim(float(t[0]), max(float(t[-1]), 1e-6))
    force_lim = 1.2 * max(float(params["F_tan_max"]), float(params["F_rad_max"]), 1.0)
    ax_force.set_ylim(-force_lim, force_lim)
    ax_force.axhline(float(params["F_tan_max"]), color="tab:blue", linestyle=":", linewidth=0.9)
    ax_force.axhline(-float(params["F_tan_max"]), color="tab:blue", linestyle=":", linewidth=0.9)
    ax_force.axhline(float(params["F_rad_max"]), color="tab:orange", linestyle=":", linewidth=0.9)
    ax_force.axhline(-float(params["F_rad_max"]), color="tab:orange", linestyle=":", linewidth=0.9)
    F_tan_line, = ax_force.plot([], [], color="tab:blue", label="F_tan")
    F_rad_line, = ax_force.plot([], [], color="tab:orange", label="F_rad")
    ax_force.legend(loc="upper right", fontsize=8)

    ax_info.set_title("Physical Information")
    ax_info.axis("off")
    info_text = ax_info.text(0.02, 0.98, "", va="top", family="monospace", fontsize=9)

    stride = max(1, len(history) // 220)
    frames = list(range(0, len(history), stride))
    if frames[-1] != len(history) - 1:
        frames.append(len(history) - 1)

    def update(frame_idx: int):
        i = frames[frame_idx]
        row = history[i]
        base = np.array([row["base_x"], row["base_y"]])
        tip = np.array([row["tip_x"], row["tip_y"]])
        contact = np.array([row["contact_x"], row["contact_y"]])
        e_rad = np.array([row["e_rad_x"], row["e_rad_y"]])
        e_tan = np.array([row["e_tan_x"], row["e_tan_y"]])
        force = np.array([row["force_x"], row["force_y"]])

        rod_line.set_data([base[0], tip[0]], [base[1], tip[1]])
        traj_line.set_data(contact_x[: i + 1], contact_y[: i + 1])
        base_dot.set_data([base[0]], [base[1]])
        tip_dot.set_data([tip[0]], [tip[1]])
        contact_dot.set_data([contact[0]], [contact[1]])

        rad_arrow.set_offsets([contact])
        rad_arrow.set_UVC([0.12 * e_rad[0]], [0.12 * e_rad[1]])
        tan_arrow.set_offsets([contact])
        tan_arrow.set_UVC([0.12 * e_tan[0]], [0.12 * e_tan[1]])
        force_arrow.set_offsets([contact])
        force_arrow.set_UVC([0.02 * force[0]], [0.02 * force[1]])
        gravity_arrow.set_offsets([tip])
        gravity_arrow.set_UVC([0.0], [-0.18])

        F_tan_line.set_data(t[: i + 1], F_tan[: i + 1])
        F_rad_line.set_data(t[: i + 1], F_rad[: i + 1])

        info_text.set_text(
            "\n".join(
                [
                    f"t              {t[i]:7.3f} s",
                    f"theta          {np.degrees(theta[i]):7.2f} deg",
                    f"omega          {omega[i]:7.3f} rad/s",
                    f"r              {r[i]:7.3f} m",
                    f"delta_r        {delta_r[i] * 1000:7.2f} mm",
                    f"I(r)           {I[i]:7.4f}",
                    f"spring_force   {spring_force[i]:7.3f} N",
                    f"gravity_torque {gravity_torque[i]:7.3f} Nm",
                    f"base_x(theta)  {base_x[i]:7.3f} m",
                    f"a(theta)       {base_a[i]:7.3f} m/rad",
                    f"ap(theta)      {base_ap[i]:7.3f} m/rad2",
                    f"omega_dot      {omega_dot[i]:7.3f} rad/s^2",
                    f"r_ddot         {r_ddot[i]:7.3f} m/s^2",
                ]
            )
        )

        return (
            rod_line,
            traj_line,
            base_dot,
            tip_dot,
            contact_dot,
            rad_arrow,
            tan_arrow,
            force_arrow,
            gravity_arrow,
            F_tan_line,
            F_rad_line,
            info_text,
        )

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000 / fps, blit=False)
    anim.save(out_path, writer=PillowWriter(fps=fps), dpi=120)
    plt.close(fig)


def save_spring2d_summary(history: list[dict[str, Any]], params: dict[str, Any], out_path: Path) -> None:
    """Save static summary figure for a Spring2D rollout."""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t = _series(history, "t")

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes = axes.ravel()
    axes[0].plot(t, np.degrees(_series(history, "theta")), label="theta")
    axes[0].axhline(np.degrees(float(params["theta_target"])), color="tab:red", linestyle="--", label="target")
    axes[0].set_ylabel("angle [deg]")
    axes[0].legend()

    axes[1].plot(t, _series(history, "omega"))
    axes[1].set_ylabel("omega [rad/s]")

    axes[2].plot(t, 1000.0 * _series(history, "delta_r"))
    axes[2].axhline(1000.0 * float(params["delta_r_max"]), color="tab:red", linestyle=":")
    axes[2].axhline(-1000.0 * float(params["delta_r_max"]), color="tab:red", linestyle=":")
    axes[2].set_ylabel("delta_r [mm]")
    axes[2].set_xlabel("time [s]")

    axes[3].plot(t, _series(history, "F_tan"), label="F_tan")
    axes[3].plot(t, _series(history, "F_rad"), label="F_rad")
    axes[3].set_ylabel("force [N]")
    axes[3].set_xlabel("time [s]")
    axes[3].legend()

    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
