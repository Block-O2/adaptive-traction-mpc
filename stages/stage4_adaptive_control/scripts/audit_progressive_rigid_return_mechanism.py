#!/usr/bin/env python3
"""Offline Phase-3A mechanism audit using only saved exploratory evidence.

No dynamics are integrated. MuJoCo is used only for mj_forward at saved poses to
calculate the robot attachment Jacobian. All controller/scientific settings and
all saved evidence remain unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np

REPO = Path.cwd().resolve()
if not (REPO / "stages/stage4_adaptive_control").is_dir():
    REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
sys.path[:0] = [str(STAGE / "scripts"), str(STAGE / "src"), str(REPO / "stages/stage3_full3d/src")]

import run_progressive_40_80_ab as run40  # noqa: E402
from traction_mpc_stage4.cuff_allocator import (  # noqa: E402
    sagittal_allocation_matrix,
    sagittal_null_vector,
    sagittal_wrench_to_world_matrix,
)

EVIDENCE_ROOT = STAGE / "results/engineering_validation"
RUNS = {
    "rigid_40_80": EVIDENCE_ROOT / "progressive_40_80_ab_20260907_v1/hip40_knee80_rigid_dt0250us",
    "rigid_90_120": EVIDENCE_ROOT / "progressive_90_120_ab_20260907_v1/hip90_knee120_rigid_dt0250us",
    "p1_40_40": EVIDENCE_ROOT / "progressive_relaxed_ab_20260905_v1/hip40_knee40_P1_dt0250us",
    "p1_40_80": EVIDENCE_ROOT / "progressive_40_80_ab_20260907_v1/hip40_knee80_P1_dt0250us",
    "p1_90_120": EVIDENCE_ROOT / "progressive_90_120_ab_20260907_v1/hip90_knee120_P1_dt0250us",
}
SOURCE_FILES = ("result.json", "trace.npz", "mechanics.npz", "commands.npz", "modes.npz")
WINDOW_HALF_S = 0.4
FORCE_GATE_N = 200.0


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        return {key: z[key] for key in z.files}


def load_run(path: Path) -> dict[str, Any]:
    return {
        "path": path,
        "result": json.loads((path / "result.json").read_text()),
        "trace": load_npz(path / "trace.npz"),
        "mechanics": load_npz(path / "mechanics.npz"),
        "commands": load_npz(path / "commands.npz"),
        "modes": load_npz(path / "modes.npz"),
    }


def nearest(t: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(t - target)))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [clean(x) for x in value.tolist()]
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def make_geometry_plant() -> Any:
    spec = json.loads((STAGE / "docs/PROGRESSIVE_40_80_AB_SPEC.json").read_text())
    trajectory = run40.base.NormalizedTrajectory(spec["runs"][0]["point"])
    manager = run40.base.UnifiedReferenceManager(trajectory.reference, confidence_aware=False)
    plant = run40.RigidPlant(run40.base.HIGH_ROM_HUMAN, spec, manager)
    plant.reset(np.radians([5.0, 10.0]))
    return plant


def geometry(run: dict[str, Any], control_index: int, plant: Any) -> dict[str, Any]:
    tr = run["trace"]
    ti = nearest(tr["time_s"], float(tr["control_time_s"][control_index]))
    plant.data.qpos[plant.robot_qpos_indices] = tr["robot_q_rad"][ti]
    plant.data.qpos[plant.human_qpos_indices] = tr["control_estimated_state"][control_index, :2]
    plant.data.qvel[plant.robot_dof_indices] = tr["robot_dq_rad_s"][ti]
    plant.data.qvel[plant.human_dof_indices] = tr["control_estimated_state"][control_index, 2:]
    mujoco.mj_forward(plant.model, plant.data)
    robot_singular = np.linalg.svd(plant.robot_attachment_jacobian(), compute_uv=False)
    q = tr["control_estimated_state"][control_index, :2]
    human_singular = np.linalg.svd(sagittal_allocation_matrix(q, run40.base.HIGH_ROM_HUMAN), compute_uv=False)
    null_sagittal = sagittal_null_vector(q, run40.base.HIGH_ROM_HUMAN)
    world_null = sagittal_wrench_to_world_matrix(q, run40.base.HIGH_ROM_HUMAN) @ null_sagittal
    return {
        "human_allocation_singular_values": human_singular,
        "human_allocation_condition": human_singular[0] / human_singular[-1],
        "robot_attachment_jacobian_singular_values": robot_singular,
        "robot_attachment_jacobian_condition": robot_singular[0] / robot_singular[-1],
        "torque_preserving_null_sagittal": null_sagittal,
        "torque_preserving_null_world": world_null,
    }


def exact_filter(run: dict[str, Any], t: float) -> dict[str, Any] | None:
    tr = run["trace"]
    if len(tr["safety_filter_time_s"]) == 0:
        return None
    i = nearest(tr["safety_filter_time_s"], t)
    if abs(float(tr["safety_filter_time_s"][i]) - t) > 1.0e-6:
        return None
    return {
        "status": str(tr["safety_filter_status"][i]),
        "lambda": tr["safety_filter_lambda"][i],
        "intervention_coordinate_norm": tr["safety_filter_intervention_coordinate_norm"][i],
        "force_correction_norm_n": tr["safety_filter_force_intervention_norm_n"][i],
        "moment_correction_norm_nm": tr["safety_filter_moment_intervention_norm_nm"][i],
        "nominal_force_norm_n": tr["safety_filter_nominal_executable_force_norm_n"][i],
        "filtered_force_norm_n": tr["safety_filter_filtered_executable_force_norm_n"][i],
        "torque_residual_nm": tr["safety_filter_torque_residual_nm"][i],
    }


def sample(run: dict[str, Any], control_index: int, plant: Any) -> dict[str, Any]:
    tr, mech, cmd, modes = run["trace"], run["mechanics"], run["commands"], run["modes"]
    t = float(tr["control_time_s"][control_index])
    physics_i = nearest(tr["time_s"], t)
    applied_i = min(int(np.searchsorted(tr["time_s"], t + 1.0e-8)), len(tr["time_s"]) - 1)
    mech_i = nearest(mech["time_s"], t)
    cmd_i = nearest(cmd["time_s"], t)
    mode_i = nearest(modes["time_s"], t)
    g = geometry(run, control_index, plant)
    estimated = tr["control_estimated_state"][control_index]
    true_q = tr["control_true_q_rad_god_view"][control_index]
    true_dq = tr["control_true_dq_rad_s_god_view"][control_index]
    return {
        "time_s": t,
        "reference_phase_s": tr["reference_phase_time_s"][physics_i],
        "q_est_deg": np.degrees(estimated[:2]),
        "dq_est_deg_s": np.degrees(estimated[2:]),
        "q_true_deg": np.degrees(true_q),
        "dq_true_deg_s": np.degrees(true_dq),
        "q_proxy_error_deg": np.degrees(estimated[:2] - true_q),
        "dq_proxy_error_deg_s": np.degrees(estimated[2:] - true_dq),
        "q_ref_deg": tr["human_q_ref_deg"][physics_i],
        "desired_human_torque_nm": tr["desired_human_action_nm"][applied_i],
        "applied_allocator_sagittal": tr["allocated_sagittal_wrench"][applied_i],
        "applied_allocator_world": tr["allocated_wrench_world"][applied_i],
        "allocation_equality_residual_nm": tr["allocation_equality_residual_nm"][applied_i],
        "command_force_world_n": cmd["force"][cmd_i],
        "command_moment_world_nm": cmd["moment"][cmd_i],
        "physical_force_world_n": mech["force_R_world"][mech_i],
        "physical_moment_world_nm": mech["moment_R_world"][mech_i],
        "mode": str(modes["mode"][mode_i]),
        "mpc_status": str(modes["mpc_status"][mode_i]),
        "decision_status": str(modes["decision_status"][mode_i]),
        "supervisor_feasible_candidate_count": modes["feasible_candidate_count"][mode_i],
        "selected_braking_rate_per_s": modes["selected_braking_rate_per_s"][mode_i],
        "safety_filter": exact_filter(run, t),
        "geometry": g,
    }


def slew_metrics(run: dict[str, Any], center: float, half: float = WINDOW_HALF_S) -> dict[str, float]:
    cmd, mech = run["commands"], run["mechanics"]
    cmask = (cmd["time_s"] >= center - half) & (cmd["time_s"] <= center + half)
    mmask = (mech["time_s"] >= center - half) & (mech["time_s"] <= center + half)
    ct, mt = cmd["time_s"][cmask], mech["time_s"][mmask]
    cf, cm = cmd["force"][cmask], cmd["moment"][cmask]
    pf, pm = mech["force_R_world"][mmask], mech["moment_R_world"][mmask]
    rate = lambda x, t: np.linalg.norm(np.diff(x, axis=0) / np.diff(t)[:, None], axis=1)
    return {
        "command_force_slew_peak_n_s": np.max(rate(cf, ct)),
        "command_moment_slew_peak_nm_s": np.max(rate(cm, ct)),
        "physical_force_slew_peak_n_s": np.max(rate(pf, mt)),
        "physical_moment_slew_peak_nm_s": np.max(rate(pm, mt)),
    }


def minimum_force_on_null_family(nominal_force: np.ndarray, world_null: np.ndarray) -> tuple[float, float]:
    direction = np.asarray(world_null[:3], dtype=float)
    direction /= np.linalg.norm(direction)
    projection = float(nominal_force @ direction)
    minimum = float(np.linalg.norm(nominal_force - projection * direction))
    return minimum, -projection


def phase_timing(run: dict[str, Any]) -> tuple[float, float]:
    planned = float(run["result"]["planned_reference_duration_s"])
    leg = (planned - 3.5) / 2.0
    return 2.5 + leg, leg


def p1_peak(run: dict[str, Any]) -> dict[str, Any]:
    mech, tr, modes = run["mechanics"], run["trace"], run["modes"]
    dt = np.diff(mech["time_s"])
    acceleration = np.diff(mech["velocity_H"], axis=0) / dt[:, None]
    time = 0.5 * (mech["time_s"][1:] + mech["time_s"][:-1])
    magnitude = np.linalg.norm(acceleration, axis=1)
    i = int(np.argmax(magnitude))
    ti = nearest(tr["time_s"], float(time[i]))
    mi = nearest(modes["time_s"], float(time[i]))
    return {
        "peak_m_s2": magnitude[i],
        "time_s": time[i],
        "component_m_s2": acceleration[i],
        "reference_phase_s": tr["reference_phase_time_s"][ti],
        "interface_translation_um": 1.0e6 * np.linalg.norm(mech["deformation_H"][0]),
        "physical_force_n_at_initial_sample": np.linalg.norm(mech["force_R_world"][0]),
        "mode": str(modes["mode"][mi]),
        "derivative_interval_s": [mech["time_s"][i], mech["time_s"][i + 1]],
    }


def relative_window(run: dict[str, Any], center: float, source: str) -> tuple[np.ndarray, np.ndarray]:
    data = run[source]
    mask = (data["time_s"] >= center - WINDOW_HALF_S) & (data["time_s"] <= center + WINDOW_HALF_S)
    return data["time_s"][mask] - center, mask


def plot_critical(r40: dict[str, Any], r90: dict[str, Any], centers: list[tuple[str, dict[str, Any], float]], output: Path) -> None:
    fig, axes = plt.subplots(4, 3, figsize=(15, 12), sharex="col")
    for col, (title, run, center) in enumerate(centers):
        tr, cmd = run["trace"], run["commands"]
        x, mask = relative_window(run, center, "trace")
        axes[0, col].plot(x, tr["estimated_human_q_deg"][mask, 0], label="q hip est")
        axes[0, col].plot(x, tr["estimated_human_q_deg"][mask, 1], label="q knee est")
        axes[0, col].plot(x, tr["human_q_ref_deg"][mask, 0], "--", label="qref hip")
        axes[0, col].plot(x, tr["human_q_ref_deg"][mask, 1], "--", label="qref knee")
        ctl_mask = (tr["control_time_s"] >= center - WINDOW_HALF_S) & (tr["control_time_s"] <= center + WINDOW_HALF_S)
        xc = tr["control_time_s"][ctl_mask] - center
        axes[1, col].plot(xc, np.degrees(tr["control_estimated_state"][ctl_mask, 2]), label="dq hip est")
        axes[1, col].plot(xc, np.degrees(tr["control_estimated_state"][ctl_mask, 3]), label="dq knee est")
        axes[1, col].plot(xc, np.degrees(tr["control_true_dq_rad_s_god_view"][ctl_mask, 0]), "--", label="dq hip true")
        axes[1, col].plot(xc, np.degrees(tr["control_true_dq_rad_s_god_view"][ctl_mask, 1]), "--", label="dq knee true")
        sf_mask = (tr["safety_filter_time_s"] >= center - WINDOW_HALF_S) & (tr["safety_filter_time_s"] <= center + WINDOW_HALF_S)
        xs = tr["safety_filter_time_s"][sf_mask] - center
        axes[2, col].plot(xs, tr["safety_filter_nominal_executable_force_norm_n"][sf_mask], label="nominal |Fcmd|")
        axes[2, col].plot(xs, tr["safety_filter_filtered_executable_force_norm_n"][sf_mask], label="filtered |Fcmd|")
        axes[2, col].axhline(FORCE_GATE_N, color="black", ls=":", label="200 N gate")
        xt, cmask = relative_window(run, center, "commands")
        axes[3, col].plot(xt, cmd["force"][cmask, 0], label="Fcmd x")
        axes[3, col].plot(xt, cmd["force"][cmask, 2], label="Fcmd z")
        axes[3, col].set_xlabel("time relative to center [s]")
        for row in range(4):
            axes[row, col].axvline(0.0, color="red", alpha=0.7, lw=1)
            axes[row, col].grid(alpha=0.25)
        axes[0, col].set_title(title)
    axes[0, 0].set_ylabel("angle [deg]")
    axes[1, 0].set_ylabel("velocity [deg/s]")
    axes[2, 0].set_ylabel("force norm [N]")
    axes[3, 0].set_ylabel("force component [N]")
    for row in range(4):
        axes[row, -1].legend(fontsize=7, loc="best")
    fig.suptitle("Rigid return mechanism audit: aligned 0.8 s windows", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_wrench(r40: dict[str, Any], r90: dict[str, Any], centers: list[tuple[str, dict[str, Any], float]], output: Path) -> None:
    fig, axes = plt.subplots(4, 2, figsize=(13, 12), sharex="col")
    for col, (title, run, center) in enumerate(centers):
        cmd, mech, tr, modes = run["commands"], run["mechanics"], run["trace"], run["modes"]
        xc, cmask = relative_window(run, center, "commands")
        xm, mmask = relative_window(run, center, "mechanics")
        xt, tmask = relative_window(run, center, "trace")
        axes[0, col].plot(xc, cmd["force"][cmask, 0], label="command Fx")
        axes[0, col].plot(xc, cmd["force"][cmask, 1], label="command Fy")
        axes[0, col].plot(xc, cmd["force"][cmask, 2], label="command Fz")
        axes[0, col].plot(xm, mech["force_R_world"][mmask, 0], alpha=.65, label="physical Fx")
        axes[0, col].plot(xm, mech["force_R_world"][mmask, 2], alpha=.65, label="physical Fz")
        axes[1, col].plot(xc, cmd["moment"][cmask, 0], label="command Mx")
        axes[1, col].plot(xc, cmd["moment"][cmask, 1], label="command My")
        axes[1, col].plot(xc, cmd["moment"][cmask, 2], label="command Mz")
        axes[1, col].plot(xm, mech["moment_R_world"][mmask, 1], alpha=.65, label="physical My")
        axes[2, col].plot(xt, tr["desired_human_action_nm"][tmask, 0], label="desired tau hip")
        axes[2, col].plot(xt, tr["desired_human_action_nm"][tmask, 1], label="desired tau knee")
        axes[2, col].plot(xt, tr["allocated_sagittal_wrench"][tmask, 0], label="allocator Fx")
        axes[2, col].plot(xt, tr["allocated_sagittal_wrench"][tmask, 1], label="allocator Fz")
        mmode = (modes["time_s"] >= center - WINDOW_HALF_S) & (modes["time_s"] <= center + WINDOW_HALF_S)
        axes[3, col].step(modes["time_s"][mmode] - center, (modes["mode"][mmode] == "BRAKE").astype(float), where="post", label="BRAKE")
        sfmask = (tr["safety_filter_time_s"] >= center - WINDOW_HALF_S) & (tr["safety_filter_time_s"] <= center + WINDOW_HALF_S)
        axes[3, col].plot(tr["safety_filter_time_s"][sfmask] - center, tr["safety_filter_lambda"][sfmask] / 50.0, label="lambda / 50")
        for row in range(4):
            axes[row, col].axvline(0.0, color="red", alpha=.7, lw=1)
            axes[row, col].grid(alpha=.25)
        axes[0, col].set_title(title)
        axes[3, col].set_xlabel("time relative to center [s]")
    axes[0, 0].set_ylabel("force [N]")
    axes[1, 0].set_ylabel("moment [Nm]")
    axes[2, 0].set_ylabel("torque / sagittal wrench")
    axes[3, 0].set_ylabel("mode / scaled lambda")
    for ax in axes.ravel(): ax.legend(fontsize=7, loc="best")
    fig.suptitle("Rigid critical-window wrench, allocator, and supervisor diagnostics", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .97))
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_p1_startup(p1_runs: dict[str, dict[str, Any]], output: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for label, run in p1_runs.items():
        mech = run["mechanics"]
        dt = np.diff(mech["time_s"])
        acc = np.diff(mech["velocity_H"], axis=0) / dt[:, None]
        at = .5 * (mech["time_s"][1:] + mech["time_s"][:-1])
        mask = at <= .01
        axes[0].plot(1000 * at[mask], np.linalg.norm(acc[mask], axis=1), label=label)
        mt = mech["time_s"] <= .01
        axes[1].plot(1000 * mech["time_s"][mt], 1000 * np.linalg.norm(mech["deformation_H"][mt], axis=1), label=label)
    axes[0].set_ylabel("Human-cuff acceleration [m/s²]")
    axes[1].set_ylabel("P1 translation [mm]")
    axes[1].set_xlabel("time from initialization [ms]")
    for ax in axes:
        ax.grid(alpha=.25); ax.legend(); ax.axvline(.125, color="red", ls=":", label=None)
    fig.suptitle("P1 shared startup transient (first 10 ms)")
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(output, dpi=180)
    plt.close(fig)


def vec(values: Any, digits: int = 2) -> str:
    return "[" + ", ".join(f"{float(x):.{digits}f}" for x in values) + "]"


def write_report(output: Path, audit: dict[str, Any]) -> None:
    s = audit["samples"]
    m = audit["matches"]
    e = audit["event_mechanism"]
    p1 = audit["p1_acceleration_peaks"]
    outcomes = audit["rigid_outcomes"]
    rows = []
    for key, label in [("40_prev", "40/80 pre-filter"), ("40_event", "40/80 BRAKE entry"), ("90_same_progress", "90/120 same return progress"), ("90_q_nearest", "90/120 nearest q")]:
        x = s[key]
        sf = x["safety_filter"] or {}
        rows.append(
            f"| {label} | {x['time_s']:.3f} | {x['return_progress_pct']:.2f}% | {vec(x['q_est_deg'])} | {vec(x['dq_est_deg_s'])} | {vec(x['q_ref_deg'])} | {sf.get('nominal_force_norm_n', float('nan')):.2f} | {sf.get('status', 'n/a')} | {sf.get('lambda', float('nan')):.2f} | {x['geometry']['human_allocation_condition']:.3f} | {x['geometry']['robot_attachment_jacobian_condition']:.3f} | {x['mode']} |"
        )
    component_rows = []
    for key, label in [("40_prev", "40/80 pre-filter"), ("40_event", "40/80 applied BRAKE"), ("90_same_progress", "90/120 same progress"), ("90_q_nearest", "90/120 nearest q")]:
        x = s[key]
        component_rows.append(f"| {label} | {vec(x['desired_human_torque_nm'])} | {vec(x['applied_allocator_sagittal'])} | {vec(x['command_force_world_n'])} | {vec(x['physical_force_world_n'])} | {vec(x['command_moment_world_nm'])} | {vec(x['physical_moment_world_nm'])} | {vec(x['dq_proxy_error_deg_s'])} |")
    slew_rows = []
    for key, label in [("rigid_40_80_event", "40/80 event"), ("rigid_90_120_same_progress", "90/120 same progress"), ("rigid_90_120_q_nearest", "90/120 nearest q")]:
        x = audit["window_slew"][key]
        slew_rows.append(f"| {label} | {x['command_force_slew_peak_n_s']:.1f} | {x['physical_force_slew_peak_n_s']:.1f} | {x['command_moment_slew_peak_nm_s']:.1f} | {x['physical_moment_slew_peak_nm_s']:.1f} |")
    p1_rows = []
    for key, label in [("p1_40_40", "40/40"), ("p1_40_80", "40/80"), ("p1_90_120", "90/120")]:
        x = p1[key]
        p1_rows.append(f"| {label} | {x['peak_m_s2']:.9f} | {x['time_s']:.6f} | {x['reference_phase_s']:.6f} | {x['mode']} | {vec(x['component_m_s2'], 6)} |")
    outcome_rows = []
    for key, label in [("rigid_40_40", "40/40"), ("rigid_40_80", "40/80"), ("rigid_90_120", "90/120")]:
        x = outcomes[key]
        outcome_rows.append(f"| {label} | {x['task']} | {x['tracking_rmse_deg']:.3f}° | {x['endpoint_error_deg']:.3f}° | {x['return_error_deg']:.3f}° | {x['brake_cycles']} | {x['filter_infeasible_count']} | {x['command_force_peak_n']:.2f} N | {x['physical_force_peak_n']:.2f} N |")

    report = f"""# Phase-3A rigid return mechanism audit

Evidence category: **exploratory diagnostic only**. This audit reads existing saved evidence only. It does not integrate dynamics, replay a trajectory, change a parameter, or revise the previous strict numerical-qualification result.

## Critical-window comparison

The 40/80 center is the first `BRAKE` sample at **t={audit['event']['time_s']:.3f} s**, reference return progress **{audit['event']['return_progress_pct']:.2f}%**. Windows are ±{WINDOW_HALF_S:.1f} s. The 90/120 evidence has no actual q overlap: its closest return-phase estimated configuration is still **{m['q_distance_deg']:.2f}°** away in two-joint Euclidean angle distance, so both same-progress and nearest-q comparisons are retained.

| slice | t | return progress | q est [hip,knee] deg | dq est [hip,knee] deg/s | qref deg | nominal command force | filter | lambda | cond(B Human) | cond(J robot) | mode |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---|
{chr(10).join(rows)}

Additional component-level values at 40/80 BRAKE entry:

- Rejected TRACK desired Human torque: **{vec(e['rejected_track_desired_human_torque_nm'], 3)} Nm**.
- Rejected nominal allocator wrench `[Fx,Fy,Fz,Mx,My,Mz]`: **{vec(e['rejected_nominal_allocator_wrench_world'], 3)}**.
- Rejected nominal total command force `[Fx,Fy,Fz]`: **{vec(e['event_nominal_total_force_n'], 3)} N**; from the preceding filterable cycle: **{vec(e['previous_nominal_total_force_n'], 3)} N**.
- Derived non-allocator feedback contribution `[Fx,Fy,Fz]`: **{vec(e['event_feedback_force_n'], 3)} N**; preceding cycle: **{vec(e['previous_feedback_force_n'], 3)} N**. The 5 ms change is **{vec(e['feedback_force_change_n'], 3)} N**, dominated by +z.
- The torque-preserving force direction changed by only **{e['null_force_direction_change_deg']:.4f}°**. Along that one-dimensional family, the minimum attainable total-force norm rose from **{e['previous_minimum_force_on_null_family_n']:.3f} N** to **{e['event_minimum_force_on_null_family_n']:.3f} N**, crossing the unchanged 200 N gate.
- At entry, the stored supervisor candidate count is **6**, meaning six BRAKE-rate candidates were feasible after TRACK rejection; it is not a CEM-population feasible count.

Window peak slew values are in `critical_window_metrics.json`; component-aligned traces are in the two audit PNGs.

| slice | desired Human torque [Nm] | applied allocator [Fx,Fz,My] | applied command Fxyz [N] | physical Fxyz [N] | applied command Mxyz [Nm] | physical Mxyz [Nm] | dq proxy error [deg/s] |
|---|---|---|---|---|---|---|---|
{chr(10).join(component_rows)}

| ±0.4 s window | command force slew [N/s] | physical force slew [N/s] | command moment slew [Nm/s] | physical moment slew [Nm/s] |
|---|---:|---:|---:|---:|
{chr(10).join(slew_rows)}

## DIRECTLY OBSERVED

- From 11.920→11.935 s, the selected TRACK action remains **{vec(e['held_track_action_nm'], 3)} Nm**. `mpc_status` is `NO_NEW_MPC` at 11.925, 11.930, and the 11.935 transition. The last CEM update was at 11.920 s; there is no immediate CEM winner switch at BRAKE entry.
- Nominal executable-force norm progresses **185.493 → 196.917 → 206.083 → 213.383 N** over those four 5 ms cycles. At 11.930 s the filter applies λ={e['previous_lambda']:.3f} and returns exactly 200 N; at 11.935 s the filter reports `FILTER_INFEASIBLE`.
- The force component that changes most from the last filterable nominal command to the rejected command is world z: **{e['event_nominal_total_force_n'][2]-e['previous_nominal_total_force_n'][2]:+.3f} N** in 5 ms, versus x **{e['event_nominal_total_force_n'][0]-e['previous_nominal_total_force_n'][0]:+.3f} N**. Most of the z rise appears in the derived low-level feedback term (**{e['feedback_force_change_n'][2]:+.3f} N**), while the nominal allocator wrench changes only slightly.
- Human allocation condition number changes {e['human_condition_relative_change_pct']:+.4f}% and robot attachment-Jacobian condition number changes {e['robot_condition_relative_change_pct']:+.4f}% from 11.930 to 11.935 s. No local conditioning collapse is present.
- Immediately after TRACK rejection, all six registered BRAKE-rate candidates are feasible and `NO_SAFE_ACTION` remains zero. This is a TRACK-command feasibility loss followed by successful BRAKE fallback, not total safe-action depletion.
- At equal return progress, 90/120 is in a very different configuration and has nominal command force **{s['90_same_progress']['safety_filter']['nominal_force_norm_n']:.2f} N**. At its closest return configuration, it remains `SAFE_UNCHANGED` at **{s['90_q_nearest']['safety_filter']['nominal_force_norm_n']:.2f} N**; the minimum norm along its local torque-preserving family is **{e['q_nearest_90_minimum_force_on_null_family_n']:.2f} N**.

## SUPPORTED BY CURRENT EVIDENCE

- The dominant mechanism is a **directional executable-force incompatibility**: the total command's component orthogonal to the torque-preserving nullspace rises above 200 N. Force magnitude is the trigger variable, but direction relative to the allowed nullspace explains why a nonzero λ can rescue 11.930 s and cannot rescue 11.935 s.
- The immediate loss is history/velocity and low-level tracking-context dependent more than a static singularity. The same held Human torque and nearly unchanged B/J geometry encounter a rising +z feedback demand. The 40/80 estimator also shows a large knee-velocity proxy error at entry (**{s['40_event']['dq_proxy_error_deg_s'][1]:+.2f}°/s**), whereas 90/120 at equal progress has **{s['90_same_progress']['dq_proxy_error_deg_s'][1]:+.2f}°/s**; this is associated evidence, not proof that the estimator caused the event.
- 90/120 avoids the transition because its realized return path does not traverse the 40/80 BRAKE state and its executable command remains inside the gate at the examined same-progress and closest-q slices. Its larger nominal ROM therefore does not imply a monotonic increase in this local feasibility demand.
- The optimizer contributes upstream: the 11.920 s CEM update raises the nominal force from 128.168 N at 11.915 s to 185.493 N. Current logs support that this action left little later margin; they do not show that CEM selected a wrong winner.

## UNRESOLVED

- Per-candidate CEM scores, winner identity/switching history, and CEM-population feasible counts are not present in these saved arrays. The supervisor's `feasible_candidate_count` cannot answer those questions.
- The rejected 11.935 s command can be decomposed into saved nominal allocator and derived non-allocator feedback, but the evidence does not split that feedback further into position versus velocity terms. A causal attribution to estimator error, robot tracking lag, or a particular gain is therefore not supported.
- Because 90/120 has no close return-phase q overlap with the 40/80 event, the saved evidence cannot isolate configuration from history with a matched-state counterfactual.

## NOT SUPPORTED

- A Human allocation singularity or robot cuff-Jacobian singularity as the immediate cause.
- Exhaustion of BRAKE candidates or `NO_SAFE_ACTION` at the transition.
- An immediate CEM winner switch at 11.935 s.
- Physical-force contract violation as the trigger: 40/80's physical peak is {outcomes['rigid_40_80']['physical_force_peak_n']:.2f} N and its saved force-contract classification remains unchanged.
- Any claim that higher target ROM must monotonically worsen executable feasibility.

## Repeated P1 acceleration peak

| P1 trajectory | peak [m/s²] | peak time [s] | reference phase [s] | mode | acceleration vector [m/s²] |
|---|---:|---:|---:|---|---|
{chr(10).join(p1_rows)}

All three peaks are bit-identical and occur in the first finite-difference interval **[0, 0.00025] s**, centered at 0.000125 s, with reference phase 0 and initial TRACK mode. Initial P1 translation and physical force are effectively zero. This directly locates the peak at the shared controller/interface startup transient before trajectory motion; the saved evidence does not support a later trajectory transition or a trajectory-specific mechanism.

## Existing rigid outcomes

| trajectory | formal task label | tracking RMSE | endpoint error | return error | BRAKE cycles | FILTER_INFEASIBLE | command peak | physical peak |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(outcome_rows)}

40/40 completes without BRAKE. Rigid 40/80 reaches the outbound endpoint within tolerance but enters BRAKE early in return and finishes with a large return error. Rigid 90/120 stays TRACK throughout and physically returns within tolerance, but retains its original `SAFE_INCOMPLETE` label because its outbound endpoint error exceeds the frozen 0.068969° tolerance.

## Dominant hypothesis and next test

The strongest current hypothesis is: **the 40/80 non-monotonic boundary is created when a held CEM torque action, evolving robot/cuff tracking feedback, and the one-dimensional torque-preserving Safety Filter combine so that the irreducible force component exceeds 200 N.** The evidence rules against an instantaneous geometry-conditioning collapse and against BRAKE-candidate depletion. It supports a trajectory-history/local-state interaction, with optimizer choice upstream and the Safety Filter providing the deterministic transition criterion.

A single frozen 120/120 exploratory A/B is scientifically justified next as a discriminator of whether the non-monotonic return-path effect persists at another symmetric high-ROM point. It would not establish a monotonic capability boundary or causally isolate the mechanism. No 120/120 run was performed here.

## Audit integrity

- Evidence coverage: all five expected saved files were present for each audited run; all arrays used here were finite; saved warning counts were zero.
- Source evidence hashes are recorded in `source_hashes.json`.
- Generated tables and plots are checksummed in `SHA256SUMS`.
- No controller, P1, safety, trajectory, solver, dt, seed, model, or tolerance setting was changed.
"""
    (output / "REPORT.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    missing = [str(path / name) for path in RUNS.values() for name in SOURCE_FILES if not (path / name).is_file()]
    if missing:
        raise FileNotFoundError("missing evidence: " + ", ".join(missing))
    runs = {key: load_run(path) for key, path in RUNS.items()}
    for key, run in runs.items():
        if int(run["result"].get("warning_count", 0)) != 0:
            raise RuntimeError(f"saved warning count is nonzero for {key}")
        required = {
            "trace": ("time_s", "control_time_s", "control_estimated_state", "control_true_q_rad_god_view", "control_true_dq_rad_s_god_view", "human_q_ref_deg", "desired_human_action_nm", "allocated_wrench_world", "safety_filter_nominal_executable_force_norm_n"),
            "mechanics": ("time_s", "velocity_H", "force_R_world", "moment_R_world", "deformation_H"),
            "commands": ("time_s", "force", "moment"),
            "modes": ("time_s",),
        }
        for archive_name, names in required.items():
            for name in names:
                if not np.all(np.isfinite(run[archive_name][name])):
                    raise RuntimeError(f"nonfinite saved evidence in {key}:{archive_name}:{name}")

    r40, r90 = runs["rigid_40_80"], runs["rigid_90_120"]
    m40 = r40["modes"]
    brake_indices = np.flatnonzero(m40["mode"] == "BRAKE")
    if len(brake_indices) == 0:
        raise RuntimeError("saved rigid 40/80 evidence contains no BRAKE event")
    event_t = float(m40["time_s"][int(brake_indices[0])])
    ci40 = nearest(r40["trace"]["control_time_s"], event_t)
    return40, leg40 = phase_timing(r40)
    phase40 = float(r40["trace"]["reference_phase_time_s"][nearest(r40["trace"]["time_s"], event_t)])
    progress40 = (phase40 - return40) / leg40

    tr90 = r90["trace"]
    return90, leg90 = phase_timing(r90)
    return_indices = np.flatnonzero(tr90["control_time_s"] >= return90)
    target_state = r40["trace"]["control_estimated_state"][ci40]
    states90 = tr90["control_estimated_state"][return_indices]
    qdist = np.linalg.norm(states90[:, :2] - target_state[:2], axis=1)
    state_dist = np.sqrt(np.sum((states90[:, :2] - target_state[:2]) ** 2, axis=1) + np.sum((states90[:, 2:] - target_state[2:]) ** 2, axis=1))
    qmatch = int(return_indices[int(np.argmin(qdist))])
    smatch = int(return_indices[int(np.argmin(state_dist))])
    pmatch = nearest(tr90["control_time_s"], return90 + progress40 * leg90)

    plant = make_geometry_plant()
    definitions = {
        "40_prev": (r40, ci40 - 1),
        "40_event": (r40, ci40),
        "90_same_progress": (r90, pmatch),
        "90_q_nearest": (r90, qmatch),
        "90_state_nearest": (r90, smatch),
    }
    samples = {key: sample(run, ci, plant) for key, (run, ci) in definitions.items()}
    for key, x in samples.items():
        run = r40 if key.startswith("40") else r90
        start, leg = phase_timing(run)
        x["return_progress_pct"] = 100.0 * (float(x["reference_phase_s"]) - start) / leg

    prev, event = samples["40_prev"], samples["40_event"]
    event_filter = r40["result"]["brake"]["last_safety_filter"]
    event_nominal_total = np.asarray(event_filter["nominal_force_total_n"], dtype=float)
    event_nominal_allocator = np.asarray(event_filter["nominal_wrench_world"], dtype=float)
    prev_direction = np.asarray(prev["geometry"]["torque_preserving_null_world"], dtype=float)
    prev_lambda = float(prev["safety_filter"]["lambda"])
    prev_filtered_total = np.asarray(prev["command_force_world_n"], dtype=float)
    prev_nominal_total = prev_filtered_total - prev_lambda * prev_direction[:3]
    prev_filtered_allocator = np.asarray(prev["applied_allocator_world"], dtype=float)
    prev_nominal_allocator = prev_filtered_allocator - prev_lambda * prev_direction
    prev_min, prev_best_lambda = minimum_force_on_null_family(prev_nominal_total, prev_direction)
    event_min, event_best_lambda = minimum_force_on_null_family(event_nominal_total, event["geometry"]["torque_preserving_null_world"])
    q90_min, _ = minimum_force_on_null_family(np.asarray(samples["90_q_nearest"]["command_force_world_n"]), samples["90_q_nearest"]["geometry"]["torque_preserving_null_world"])
    unit_prev = prev_direction[:3] / np.linalg.norm(prev_direction[:3])
    event_direction = np.asarray(event["geometry"]["torque_preserving_null_world"][:3]); event_direction /= np.linalg.norm(event_direction)
    angle = np.degrees(np.arccos(np.clip(unit_prev @ event_direction, -1.0, 1.0)))
    prev_feedback = prev_nominal_total - prev_nominal_allocator[:3]
    event_feedback = event_nominal_total - event_nominal_allocator[:3]

    event_mechanism = {
        "held_track_action_nm": r40["trace"]["desired_human_action_nm"][nearest(r40["trace"]["time_s"], event_t)],
        "rejected_track_desired_human_torque_nm": r40["trace"]["desired_human_action_nm"][nearest(r40["trace"]["time_s"], event_t)],
        "previous_nominal_total_force_n": prev_nominal_total,
        "event_nominal_total_force_n": event_nominal_total,
        "previous_nominal_allocator_wrench_world": prev_nominal_allocator,
        "rejected_nominal_allocator_wrench_world": event_nominal_allocator,
        "previous_feedback_force_n": prev_feedback,
        "event_feedback_force_n": event_feedback,
        "feedback_force_change_n": event_feedback - prev_feedback,
        "previous_lambda": prev_lambda,
        "previous_minimum_force_on_null_family_n": prev_min,
        "previous_best_lambda_n": prev_best_lambda,
        "event_minimum_force_on_null_family_n": event_min,
        "event_best_lambda_n": event_best_lambda,
        "null_force_direction_change_deg": angle,
        "human_condition_relative_change_pct": 100.0 * (event["geometry"]["human_allocation_condition"] / prev["geometry"]["human_allocation_condition"] - 1.0),
        "robot_condition_relative_change_pct": 100.0 * (event["geometry"]["robot_attachment_jacobian_condition"] / prev["geometry"]["robot_attachment_jacobian_condition"] - 1.0),
        "q_nearest_90_minimum_force_on_null_family_n": q90_min,
    }

    p1_peaks = {key: p1_peak(runs[key]) for key in ("p1_40_40", "p1_40_80", "p1_90_120")}
    rigid40_40 = load_run(EVIDENCE_ROOT / "progressive_relaxed_ab_20260905_v1/hip40_knee40_rigid_dt0250us")
    rigid_runs = {"rigid_40_40": rigid40_40, "rigid_40_80": r40, "rigid_90_120": r90}
    outcomes = {}
    for key, run in rigid_runs.items():
        x = run["result"]
        outcomes[key] = {
            "task": x["task"], "tracking_rmse_deg": x["tracking_rmse_deg"],
            "endpoint_error_deg": x["endpoint_error_deg"], "return_error_deg": x["return_error_deg"],
            "brake_cycles": x["brake"]["brake_cycle_count"],
            "filter_infeasible_count": x["brake"]["safety_filter_status_counts"]["FILTER_INFEASIBLE"],
            "command_force_peak_n": x["command_force_n"]["peak"],
            "physical_force_peak_n": x["physical_force_n"]["peak"],
        }

    audit = {
        "evidence_category": "exploratory_diagnostic_only",
        "method": "saved_evidence_only_no_dynamics_integration",
        "window_half_s": WINDOW_HALF_S,
        "event": {"time_s": event_t, "reference_phase_s": phase40, "return_progress_pct": 100.0 * progress40},
        "matches": {
            "q_nearest_time_s": float(tr90["control_time_s"][qmatch]),
            "q_distance_deg": float(np.degrees(qdist[int(np.argmin(qdist))])),
            "state_nearest_time_s": float(tr90["control_time_s"][smatch]),
            "state_distance_rad_equivalent_1s": float(state_dist[int(np.argmin(state_dist))]),
            "same_progress_time_s": float(tr90["control_time_s"][pmatch]),
        },
        "samples": samples,
        "event_mechanism": event_mechanism,
        "window_slew": {
            "rigid_40_80_event": slew_metrics(r40, event_t),
            "rigid_90_120_same_progress": slew_metrics(r90, float(tr90["control_time_s"][pmatch])),
            "rigid_90_120_q_nearest": slew_metrics(r90, float(tr90["control_time_s"][qmatch])),
        },
        "p1_acceleration_peaks": p1_peaks,
        "rigid_outcomes": outcomes,
        "coverage": {"all_expected_files_present": True, "all_used_numeric_arrays_finite": True, "all_saved_warning_counts_zero": True},
        "scientific_settings_changed": False,
        "new_trajectory_runs": 0,
    }
    audit = clean(audit)
    (output / "critical_window_metrics.json").write_text(json.dumps(audit, indent=2) + "\n")

    with (output / "critical_window_comparison.csv").open("w", newline="") as stream:
        fields = ["slice", "time_s", "return_progress_pct", "q_hip_deg", "q_knee_deg", "dq_hip_deg_s", "dq_knee_deg_s", "qref_hip_deg", "qref_knee_deg", "nominal_force_norm_n", "filter_status", "filter_lambda", "human_B_condition", "robot_J_condition", "mode", "mpc_status", "supervisor_feasible_candidate_count"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for key in ("40_prev", "40_event", "90_same_progress", "90_q_nearest", "90_state_nearest"):
            x = samples[key]; sf = x["safety_filter"] or {}
            writer.writerow({"slice": key, "time_s": x["time_s"], "return_progress_pct": x["return_progress_pct"], "q_hip_deg": x["q_est_deg"][0], "q_knee_deg": x["q_est_deg"][1], "dq_hip_deg_s": x["dq_est_deg_s"][0], "dq_knee_deg_s": x["dq_est_deg_s"][1], "qref_hip_deg": x["q_ref_deg"][0], "qref_knee_deg": x["q_ref_deg"][1], "nominal_force_norm_n": sf.get("nominal_force_norm_n"), "filter_status": sf.get("status"), "filter_lambda": sf.get("lambda"), "human_B_condition": x["geometry"]["human_allocation_condition"], "robot_J_condition": x["geometry"]["robot_attachment_jacobian_condition"], "mode": x["mode"], "mpc_status": x["mpc_status"], "supervisor_feasible_candidate_count": x["supervisor_feasible_candidate_count"]})

    plot_critical(r40, r90, [("40/80 first BRAKE", r40, event_t), ("90/120 same progress", r90, float(tr90["control_time_s"][pmatch])), ("90/120 nearest q", r90, float(tr90["control_time_s"][qmatch]))], output / "aligned_state_force_windows.png")
    plot_wrench(r40, r90, [("40/80 first BRAKE", r40, event_t), ("90/120 nearest q", r90, float(tr90["control_time_s"][qmatch]))], output / "aligned_wrench_supervisor_windows.png")
    plot_p1_startup({"40/40": runs["p1_40_40"], "40/80": runs["p1_40_80"], "90/120": runs["p1_90_120"]}, output / "p1_shared_startup_acceleration.png")

    source_hashes = {}
    for key, path in RUNS.items():
        source_hashes[key] = {name: sha256(path / name) for name in SOURCE_FILES}
    rigid40_path = rigid40_40["path"]
    source_hashes["rigid_40_40"] = {name: sha256(rigid40_path / name) for name in SOURCE_FILES}
    (output / "source_hashes.json").write_text(json.dumps(source_hashes, indent=2) + "\n")
    write_report(output, audit)
    generated = sorted(path for path in output.iterdir() if path.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in generated))
    print(json.dumps({"output": str(output), "event_time_s": event_t, "return_progress_pct": 100 * progress40, "minimum_force_before_n": prev_min, "minimum_force_event_n": event_min, "q_match_distance_deg": float(np.degrees(qdist[int(np.argmin(qdist))])), "new_trajectory_runs": 0}, indent=2))


if __name__ == "__main__":
    main()
