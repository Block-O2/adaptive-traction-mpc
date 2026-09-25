"""Static evaluation-only path figures from preserved DEV-D development traces."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from diagnose_rigid_table_reference_v1 import gaps
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


def trace_geometry(run: Path, case: Path):
    human, geometry, _, _ = hidden_plant(json.loads(case.read_text()))
    with np.load(run / "trace.npz", allow_pickle=True) as data:
        time = np.asarray(data["time_s"], dtype=float)
        stage = np.asarray(data["stage"])
        qref = np.asarray(data["reference_q_rad"], dtype=float)
        qtrue = np.asarray(data["evaluation_only_human_state_rad_rad_s"], dtype=float)[:, :2]
    return time, stage, qref, qtrue, gaps(qref, human, geometry), gaps(qtrue, human, geometry)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--old", type=Path, required=True)
    p.add_argument("--new", type=Path, required=True)
    p.add_argument("--near-upper-case", type=Path, required=True)
    p.add_argument("--near-upper-run", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(3, 2, figsize=(12, 9), sharex="col", constrained_layout=True)
    for col, (label, run) in enumerate((('old fixed reference', args.old),
                                        ('DEV-D feedback reference', args.new))):
        t, phase, qref, qtrue, requested, actual = trace_geometry(run, args.case)
        mask = phase == "COMMISSIONING"
        for row, joint in enumerate((0, 1)):
            ax = axes[row, col]
            ax.plot(t[mask], np.degrees(qref[mask, joint]), label="requested q")
            ax.plot(t[mask], np.degrees(qtrue[mask, joint]), label="actual q", alpha=0.8)
            ax.set_ylabel(f"q{joint+1} (deg)")
            ax.grid(alpha=0.25)
            ax.set_title(label if row == 0 else "")
        ax = axes[2, col]
        ax.plot(t[mask], 1000 * requested["shank"][mask], label="requested shank")
        ax.plot(t[mask], 1000 * actual["shank"][mask], label="actual shank")
        ax.plot(t[mask], 1000 * requested["sleeve"][mask], label="mapped sleeve from requested q")
        ax.plot(t[mask], 1000 * actual["sleeve"][mask], label="actual sleeve")
        ax.axhline(0, color="black", linewidth=1, label="hard table")
        ax.set_ylabel("signed margin (mm)")
        ax.set_xlabel("physical simulation time (s)")
        ax.grid(alpha=0.25)
    axes[2, 1].legend(loc="upper left", fontsize=8, ncol=2)
    fig.suptitle("Balanced-middle r01: requested vs physical path (hidden geometry, evaluation only)")
    fig.savefig(args.output_dir / "balanced_middle_old_vs_dev_d.png", dpi=160)
    plt.close(fig)

    case = json.loads(args.near_upper_case.read_text())
    human, geometry, _, _ = hidden_plant(case)
    with np.load(args.near_upper_run / "contact_intervals.npz", allow_pickle=True) as data:
        columns = list(data["columns"])
        rows = np.asarray(data["rows"], dtype=float)
    t = rows[:, columns.index("interval_end_s")]
    q = rows[:, [columns.index("qpos_0"), columns.index("qpos_1")]]
    sleeve = gaps(q, human, geometry)["sleeve"]
    abort = json.loads((args.near_upper_run / "dev_d_reference_abort.json").read_text())
    planned_min = abort["reference_events"][0]["minimum_path_m"]["sleeve_m"]
    fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
    ax.plot(t, 1000 * sleeve, label="actual physical sleeve from 0.25 ms q")
    ax.axhline(0, color="black", linewidth=1, label="hard table")
    ax.axhline(1000 * planned_min, linestyle="--", color="tab:green",
               label="deployable planned sleeve minimum (whole segment)")
    ax.axvline(abort["time_s"], linestyle=":", color="tab:red",
               label="deployable measured-gap abort")
    ax.set(xlabel="physical simulation time (s)", ylabel="sleeve signed margin (mm)",
           title="Near-upper r02: actual sleeve crosses despite nonpenetrating planned sleeve")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(args.output_dir / "near_upper_early_sleeve.png", dpi=160)
    plt.close(fig)
    print(json.dumps({"balanced_middle_figure": str(args.output_dir / "balanced_middle_old_vs_dev_d.png"),
                      "near_upper_figure": str(args.output_dir / "near_upper_early_sleeve.png"),
                      "near_upper_planned_min_sleeve_m": planned_min,
                      "near_upper_actual_min_sleeve_m": float(np.min(sleeve))}, indent=2))


if __name__ == "__main__":
    main()
