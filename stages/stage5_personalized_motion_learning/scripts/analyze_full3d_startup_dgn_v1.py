"""Read-only aligned startup diagnostics for preserved physical traces.

This script never imports the controller, reconstructs a new physical state,
or writes into a historical episode directory. It describes association and
event ordering; it does not by itself prove contact or model-switch causality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _first_time(times: np.ndarray, predicate: np.ndarray) -> float | None:
    indices = np.flatnonzero(predicate)
    return None if len(indices) == 0 else float(times[int(indices[0])])


def _episode(label: str, path: Path, plot_path: Path) -> dict:
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    config = json.loads((path / "config_snapshot.json").read_text(encoding="utf-8"))
    with np.load(path / "trace.npz", allow_pickle=False) as data:
        stage = data["stage"]
        comm = stage == "COMMISSIONING"
        task = stage == "TASK"
        t = np.asarray(data["time_s"][comm], dtype=float)
        q_ref = np.rad2deg(data["reference_q_rad"][comm])
        dq_ref = np.rad2deg(data["reference_dq_rad_s"][comm])
        estimate = np.rad2deg(data["estimated_human_state_rad_rad_s"][comm])
        truth = np.rad2deg(data["evaluation_only_human_state_rad_rad_s"][comm])
        contact = np.asarray(data["shank_bed_contact_evaluation_only"][comm], dtype=bool)
        force = np.linalg.norm(data["physical_cuff_force_world_n"][comm], axis=1)
        moment = np.linalg.norm(data["physical_cuff_moment_world_nm"][comm], axis=1)
        torque = np.linalg.norm(data["cr12_actuator_command_nm"][comm], axis=1)
        cuff_speed = np.linalg.norm(data["physical_cuff_linear_velocity_world_m_s"][comm], axis=1)
        cuff_position = data["physical_cuff_position_world_m"][comm]
        q_ref_task = np.rad2deg(data["reference_q_rad"][task])
        estimate_task = np.rad2deg(data["estimated_human_state_rad_rad_s"][task])
        truth_task = np.rad2deg(data["evaluation_only_human_state_rad_rad_s"][task])
        cuff_task = data["physical_cuff_position_world_m"][task]
        task_time = data["time_s"][task]
        task_beta = data["task_beta"].copy()
        task_residual = data["task_residual_weights_nm"].copy()
    q_tracking = np.abs(truth[:, :2] - q_ref)
    dq_tracking = np.abs(truth[:, 2:] - dq_ref)
    q_estimation = np.abs(estimate[:, :2] - truth[:, :2])
    q_tolerance = np.asarray(config["completion_angle_tolerance_deg"], dtype=float)
    dq_tolerance = np.asarray(config["completion_velocity_tolerance_deg_s"], dtype=float)
    first_contact = _first_time(t, contact)
    first_q_tracking = _first_time(t, np.any(q_tracking > q_tolerance, axis=1))
    first_dq_tracking = _first_time(t, np.any(dq_tracking > dq_tolerance, axis=1))
    first_q_estimation = _first_time(t, np.any(q_estimation > q_tolerance, axis=1))
    onset = {
        "contact_5ms_s": first_contact,
        "true_q_reference_error_over_existing_1deg_tolerance_s": first_q_tracking,
        "true_dq_reference_error_over_existing_2deg_s_tolerance_s": first_dq_tracking,
        "estimated_q_truth_error_over_existing_1deg_tolerance_s": first_q_estimation,
    }
    fit = summary["commissioning"]["geometry_fit"]
    record = {
        "label": label,
        "source_episode": str(path),
        "evidence": "stored_formal_case_reused_as_development_diagnostic"
                    if summary.get("evidence_category") == "formal_fresh_full3d_qualification"
                    else "development_comparison",
        "status": summary["status"],
        "abort_reason": summary["abort_reason"],
        "commissioning_boundary_count": int(len(t)),
        "task_boundary_count": int(len(task_time)),
        "commissioning_time_s": [float(t[0]), float(t[-1])],
        "handoff_time_s": None if len(task_time) == 0 else float(task_time[0]),
        "event_onsets": onset,
        "contact_at_initial_boundary": bool(contact[0]),
        "commissioning_5ms_contact_boundary_count": int(contact.sum()),
        "commissioning_contact_integrated_step_count_from_monitor":
            summary.get("qualification", {}).get("true_physics", {}).get(
                "shank_bed_contact_steps", {}).get("COMMISSIONING"),
        "commissioning_peak_cuff_force_n": float(force.max()),
        "commissioning_peak_cuff_moment_nm": float(moment.max()),
        "commissioning_peak_cr12_command_norm_nm": float(torque.max()),
        "commissioning_peak_cuff_speed_m_s": float(cuff_speed.max()),
        "initial": {
            "q_ref_deg": q_ref[0].tolist(),
            "q_true_deg": truth[0, :2].tolist(),
            "q_est_deg": estimate[0, :2].tolist(),
            "contact": bool(contact[0]),
            "cuff_force_n": float(force[0]),
        },
        "pre_fit_terminal": {
            "q_ref_deg": q_ref[-1].tolist(),
            "dq_ref_deg_s": dq_ref[-1].tolist(),
            "q_true_deg": truth[-1, :2].tolist(),
            "dq_true_deg_s": truth[-1, 2:].tolist(),
            "q_est_deg": estimate[-1, :2].tolist(),
            "dq_est_deg_s": estimate[-1, 2:].tolist(),
            "q_true_minus_ref_deg": (truth[-1, :2] - q_ref[-1]).tolist(),
            "q_est_minus_true_deg": (estimate[-1, :2] - truth[-1, :2]).tolist(),
            "cuff_position_world_m": cuff_position[-1].tolist(),
            "cuff_force_n": float(force[-1]),
            "cuff_moment_nm": float(moment[-1]),
            "last_executed_cr12_command_norm_nm": float(torque[-2]),
            "terminal_boundary_command_executed": False,
            "contact": bool(contact[-1]),
        },
        "fitted_handoff": None if len(task_time) == 0 else {
            "q_ref_deg": q_ref_task[0].tolist(),
            "q_true_deg": truth_task[0, :2].tolist(),
            "q_est_deg": estimate_task[0, :2].tolist(),
            "q_est_minus_prefit_deg": (estimate_task[0, :2] - estimate[-1, :2]).tolist(),
            "q_true_minus_prefit_deg": (truth_task[0, :2] - truth[-1, :2]).tolist(),
            "cuff_position_minus_prefit_m": (cuff_task[0] - cuff_position[-1]).tolist(),
            "beta": task_beta[0].tolist(),
            "residual_weights_nm": task_residual[0].tolist(),
        },
        "geometry_fit": {
            "accepted": fit["accepted"] if fit is not None else None,
            "reason": fit["reason"] if fit is not None else None,
            "condition_number_regularized_fit": fit["condition_number"] if fit is not None else None,
            "angular_span_rad": fit["angular_span_rad"] if fit is not None else None,
            "sample_count": fit["sample_count"] if fit is not None else None,
            "maximum_residual_m": fit["maximum_residual_m"] if fit is not None else None,
        },
        "plot": str(plot_path),
    }
    fig, axes = plt.subplots(5, 1, figsize=(12, 11), sharex=True)
    for joint in range(2):
        axes[joint].plot(t, q_ref[:, joint], "k--", lw=1.3, label="reference")
        axes[joint].plot(t, truth[:, joint], color="C0", lw=1.2, label="physical true")
        axes[joint].plot(t, estimate[:, joint], color="C1", lw=0.9, alpha=0.8,
                         label="deployable estimate")
        axes[joint].set_ylabel(f"q{joint+1} (deg)")
        axes[joint].legend(loc="best", ncol=3, fontsize=8)
    axes[2].plot(t, q_tracking.max(axis=1), label="max joint true/ref error")
    axes[2].plot(t, q_estimation.max(axis=1), label="max joint estimate/true error")
    axes[2].axhline(float(q_tolerance.max()), color="k", ls=":", label="existing 1 deg task tolerance")
    axes[2].set_ylabel("abs error (deg)")
    axes[2].legend(loc="best", fontsize=8)
    axes[3].plot(t, force, label="physical cuff force norm (N)")
    axes[3].plot(t, moment, label="physical cuff moment norm (Nm)")
    axes[3].fill_between(t, 0, np.maximum(force.max(), 1), where=contact, color="red",
                         alpha=0.17, label="5 ms shank-bed contact")
    axes[3].set_ylabel("wrench/contact")
    axes[3].legend(loc="best", fontsize=8)
    # The final commissioning boundary has no executed command and its saved
    # zero placeholder must not be plotted as a physical torque discontinuity.
    axes[4].plot(t[:-1], torque[:-1], label="executed CR12 command norm (Nm)")
    axes[4].plot(t, cuff_speed * 100.0, label="cuff speed ×100 (m/s)")
    axes[4].set_ylabel("command/speed")
    axes[4].set_xlabel("MuJoCo physical time (s)")
    axes[4].legend(loc="best", fontsize=8)
    for axis in axes:
        axis.axvline(float(t[-1]), color="purple", alpha=0.6, ls="-.")
        if first_contact is not None:
            axis.axvline(first_contact, color="red", alpha=0.5, ls=":")
        axis.grid(alpha=0.2)
    fig.suptitle(f"{label}: aligned physical commissioning; purple = fit/handoff")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", nargs=2, metavar=("LABEL", "PATH"),
                        action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    records = []
    for label, raw_path in args.episode:
        records.append(_episode(label, Path(raw_path), args.output / f"{label}.png"))
    (args.output / "aligned_summary.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"episodes": len(records), "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
