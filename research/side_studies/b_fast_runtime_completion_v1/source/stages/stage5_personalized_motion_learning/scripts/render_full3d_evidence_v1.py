#!/usr/bin/env python3
"""Render evaluation-only plots and state-replay videos for FULL-3D evidence.

The videos replay saved MuJoCo boundary states for inspection; they do not
advance the plant and are not used as scientific acceptance evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import matplotlib.pyplot as plt
import mujoco
import numpy as np
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN


def _load(run_dir: Path):
    return json.loads((run_dir / "summary.json").read_text()), np.load(
        run_dir / "trace.npz"
    )


def plot_nominal(run_dir: Path, output: Path) -> None:
    summary, trace = _load(run_dir)
    mask = trace["stage"] == "TASK"
    t = trace["time_s"][mask] - trace["time_s"][mask][0]
    q = np.degrees(trace["evaluation_only_human_state_rad_rad_s"][mask, :2])
    q_ref = np.degrees(trace["reference_q_rad"][mask])
    force = np.linalg.norm(trace["physical_cuff_force_world_n"][mask], axis=1)
    moment = np.linalg.norm(trace["physical_cuff_moment_world_nm"][mask], axis=1)
    adaptation = summary["adaptation_trace"]
    update_t = np.asarray([row["time_s"] for row in adaptation]) - trace["time_s"][mask][0]
    beta_step = np.asarray([row["beta_step_l2"] for row in adaptation])
    residual_step = np.asarray([row["residual_step_l2"] for row in adaptation])
    beta = np.asarray([row["beta_after"] for row in adaptation])

    fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=False)
    axes[0].plot(t, q[:, 0], label="hip measured")
    axes[0].plot(t, q_ref[:, 0], "--", label="hip reference")
    axes[0].plot(t, q[:, 1], label="knee measured")
    axes[0].plot(t, q_ref[:, 1], "--", label="knee reference")
    axes[0].set_ylabel("angle (deg)")
    axes[0].legend(ncol=2)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t, force, label="|cuff force|")
    axes[1].plot(t, moment, label="|cuff moment|")
    axes[1].set_ylabel("N or N m")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(update_t, beta[:, 3], label="beta[3]")
    axes[2].plot(update_t, beta[:, 4], label="beta[4]")
    axes[2].plot(update_t, beta[:, 5], label="beta[5]")
    axes[2].plot(update_t, beta[:, 10], label="beta[10]")
    axes[2].set_ylabel("selected beta")
    axes[2].legend(ncol=4)
    axes[2].grid(True, alpha=0.3)

    axes[3].semilogy(update_t, np.maximum(beta_step, 1e-12), label="beta step L2")
    axes[3].semilogy(
        update_t, np.maximum(residual_step, 1e-12), label="residual step L2"
    )
    axes[3].set_xlabel("task elapsed time (s)")
    axes[3].set_ylabel("update magnitude")
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)
    fig.suptitle("FULL-3D CR12 nominal timing-aware development case")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def render_replay(run_dir: Path, output: Path, fps: int = 15) -> None:
    _, trace = _load(run_dir)
    plant = Stage5CR12SensorBoundaryPlant(STAGE5_HUMAN)
    robot_body_ids = [
        plant.model.body(f"xMateCR12_{suffix}").id
        for suffix in ("base", "link1", "link2", "link3", "link4", "link5", "link6")
    ]
    human_body_ids = [plant.model.body(name).id for name in ("hip", "shank")]

    time_s = trace["time_s"]
    dt = float(np.median(np.diff(time_s))) if len(time_s) > 1 else 0.005
    stride = max(1, int(round(1.0 / (fps * dt))))
    indices = list(range(0, len(time_s), stride))
    if indices[-1] != len(time_s) - 1:
        indices.append(len(time_s) - 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with imageio.get_writer(output, fps=fps, codec="libx264", quality=8) as writer:
        for index in indices:
            plant.data.qpos[plant.human_qpos_indices] = trace[
                "evaluation_only_human_state_rad_rad_s"
            ][index, :2]
            plant.data.qvel[plant.human_dof_indices] = trace[
                "evaluation_only_human_state_rad_rad_s"
            ][index, 2:]
            plant.data.qpos[plant.robot_qpos_indices] = trace["cr12_q_rad"][index]
            plant.data.qvel[plant.robot_dof_indices] = trace["cr12_dq_rad_s"][index]
            plant.data.time = float(time_s[index])
            mujoco.mj_forward(plant.model, plant.data)
            robot = plant.data.xpos[robot_body_ids][:, [0, 2]]
            human = plant.data.xpos[human_body_ids][:, [0, 2]]
            cuff = plant.data.site_xpos[plant.sleeve_site_id][[0, 2]]
            tool = plant.data.site_xpos[plant.attachment_site_id][[0, 2]]
            force = trace["physical_cuff_force_world_n"][index][[0, 2]]

            fig, axis = plt.subplots(figsize=(8, 5), dpi=100)
            axis.axhspan(-0.03, 0.012, color="0.65", alpha=0.75, label="bed")
            axis.plot(robot[:, 0], robot[:, 1], "o-", lw=4, color="#2468a2", label="CR12")
            axis.plot([robot[-1, 0], tool[0]], [robot[-1, 1], tool[1]], "-", lw=5, color="#24a3a3")
            axis.plot(
                [human[0, 0], human[1, 0], cuff[0]],
                [human[0, 1], human[1, 1], cuff[1]],
                "o-",
                lw=7,
                color="#d17725",
                label="Human V2",
            )
            axis.plot([tool[0], cuff[0]], [tool[1], cuff[1]], "k--", lw=1.5, label="interface")
            axis.arrow(
                cuff[0], cuff[1], 0.0015 * force[0], 0.0015 * force[1],
                width=0.002, head_width=0.018, length_includes_head=True, color="#a92323",
            )
            axis.set_xlim(-0.12, 1.08)
            axis.set_ylim(-0.05, 0.92)
            axis.set_aspect("equal", adjustable="box")
            axis.set_xlabel("world x (m)")
            axis.set_ylabel("world z (m)")
            axis.grid(True, alpha=0.25)
            axis.legend(loc="upper left", ncol=2, fontsize=8)
            axis.set_title(
                f"Evaluation-only x-z projection replay: {run_dir.name}\n"
                f"t={time_s[index]:.3f}s | {trace['stage'][index]} | {trace['task_phase'][index]} | "
                f"|F|={np.linalg.norm(trace['physical_cuff_force_world_n'][index]):.1f} N",
                fontsize=9,
            )
            fig.tight_layout()
            fig.canvas.draw()
            writer.append_data(np.asarray(fig.canvas.buffer_rgba())[:, :, :3])
            plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nominal-run", type=Path, required=True)
    parser.add_argument("--diagnostic-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plot_nominal(args.nominal_run, args.output_dir / "nominal_trace_overview.png")
    render_replay(args.nominal_run, args.output_dir / "nominal_state_replay.mp4")
    render_replay(
        args.diagnostic_run, args.output_dir / "no_task_actuation_state_replay.mp4"
    )


if __name__ == "__main__":
    main()
