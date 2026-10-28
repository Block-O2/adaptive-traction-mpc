#!/usr/bin/env python3
"""Render archived measurements; no environment, policy update, or physics calls."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/ihear-archive-mpl-cache")
import matplotlib.pyplot as plt
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def table(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    root, out = args.source_root, args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    v7 = root / "autonomous_learning_smoothness_v7"
    ids = ["DEVPC02_B", "DEVPC02_TRAD_COMBO"]
    checks, curves, receipt = [], {}, {"scope": "Read-only archive evidence numerical check; not an original full scorer replay or a new physical rollout", "inputs": []}
    fig, ax = plt.subplots(3, 2, figsize=(11, 10), sharex=True)
    colors = ["#34495e", "#007f75"]
    for ident, color in zip(ids, colors):
        native_path = v7 / "runtime/motion_series" / (ident + ".npz")
        trace_path = v7 / "runtime/source/results" / ident / "trace.npz"
        metrics_path = v7 / "analysis/native_metrics" / (ident + ".json")
        row = json.loads((v7 / "attempts" / (ident + "_RESULT.json")).read_text())
        metrics = json.loads(metrics_path.read_text())
        for p in [native_path, trace_path, metrics_path]:
            receipt["inputs"].append({"path": str(p.relative_to(root)), "sha256": sha(p)})
        with np.load(native_path, allow_pickle=False) as z:
            t, q, j = z["time_s"], np.degrees(z["true_q_rad"]), np.degrees(z["jerk_rad_s3"])
            elapsed = t - t[0]
        with np.load(trace_path, allow_pickle=False) as z:
            mask = z["stage"] == "TASK"
            tt = z["time_s"][mask]
            force = np.linalg.norm(z["physical_cuff_force_world_n"][mask], axis=1)
            moment = np.linalg.norm(z["physical_cuff_moment_world_nm"][mask], axis=1)
        jf, jm = float(force[:-1] @ np.diff(tt)), float(moment[:-1] @ np.diff(tt))
        jerk_rms = np.sqrt(np.mean(j * j, axis=0))
        assert abs(jf - row["JF"]) < 1e-8
        assert abs(jm - row["JM"]) < 1e-8
        assert np.max(np.abs(jerk_rms - metrics["native_motion"]["jerk_deg_s3"]["rms"])) < 1e-7
        assert np.max(abs(np.diff(t) - 0.00025)) < 1e-9
        assert abs((t[-1] - t[0]) - 19.03) < 1e-8
        checks.append(dict(id=ident, JF_N_s=jf, JM_Nm_s=jm, hip_jerk_RMS_deg_s3=jerk_rms[0], knee_jerk_RMS_deg_s3=jerk_rms[1], JF_error=jf-row["JF"], JM_error=jm-row["JM"], native_samples=len(t), duration_s=t[-1]-t[0], original_qualified=row["qualified"]))
        label = ident.replace("DEVPC02_", "")
        for k in range(2):
            ax[0, k].plot(elapsed, q[:, k], label=label, color=color, lw=0.8, rasterized=True)
            ax[1, k].plot(elapsed, j[:, k], label=label, color=color, lw=0.6, alpha=0.85, rasterized=True)
        ax[2, 0].plot(tt-tt[0], force, color=color, label=label, lw=0.8, rasterized=True)
        ax[2, 1].plot(tt-tt[0], moment, color=color, label=label, lw=0.8, rasterized=True)
        # A readable CSV with exact native observations at 5 ms; full .25 ms arrays are retained.
        ix = np.unique(np.r_[np.arange(0, len(t), 20), len(t)-1])
        curves[ident] = [dict(id=ident, TASK_time_s=float(elapsed[i]), hip_q_deg=float(q[i, 0]), knee_q_deg=float(q[i, 1]), hip_jerk_deg_s3=float(j[i, 0]), knee_jerk_deg_s3=float(j[i, 1])) for i in ix]
    titles = [("Hip position", "deg"), ("Knee position", "deg"), ("Hip native jerk", "deg/s³"), ("Knee native jerk", "deg/s³"), ("Measured cuff force norm", "N"), ("Measured cuff moment norm", "N m")]
    for a, (title, unit) in zip(ax.flat, titles):
        a.set_title(title)
        a.set_ylabel(unit)
        a.grid(alpha=0.2)
        a.set_xlim(0, 19.03)
        a.axvspan(9.005, 10.025, color="grey", alpha=0.08)
    for a in ax[-1]:
        a.set_xlabel("TASK elapsed time (s)")
    ax[0, 0].legend()
    fig.suptitle("Same-parent full 19.03 s TASK: B and TRAD_COMBO\nOriginal unfiltered 0.25 ms native motion; original 5 ms measured wrench")
    fig.tight_layout()
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / ("ARCHIVE_FULL_TASK_B_TRAD_COMBO." + ext), dpi=180)
    plt.close(fig)
    table(out / "ARCHIVE_NUMERIC_CHECK.csv", checks)
    table(out / "ARCHIVE_NATIVE_5MS_OBSERVATIONS.csv", sum(curves.values(), []))

    cp = root / "deep_learning_method_exploration_v8/families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0003/PPO_RAW.json"
    model = json.loads(cp.read_text())
    receipt["inputs"].append({"path": str(cp.relative_to(root)), "sha256": sha(cp)})
    training = []
    for batch in model["finished_batches"]:
        r = batch["result"]
        if r.get("status") != "COMPLETED_GENUINE_ON_POLICY_UPDATE":
            continue
        for step in r["steps"]:
            training.append(dict(arm="PPO_RAW", batch_id=batch["batch_id"], epoch=step["epoch"], loss=step["loss"], gradient_norm=step["gradient_norm"], reward_baseline=r["reward_baseline"], records=r["records"], data_semantics=r["data_semantics"]))
    assert len(training) == 6, "Expected two original 3-epoch committed PPO_RAW updates"
    table(out / "ARCHIVE_PPO_RAW_UPDATE_HISTORY.csv", training)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for batch_id in sorted(set(r["batch_id"] for r in training)):
        rr = [r for r in training if r["batch_id"] == batch_id]
        for a, key, title in zip(axes, ["loss", "gradient_norm"], ["Recorded surrogate loss", "Recorded gradient norm"]):
            a.plot([r["epoch"] for r in rr], [r[key] for r in rr], marker="o", label=f"batch {batch_id} (4 fresh records)")
            a.set_xlabel("Optimization epoch within batch")
            a.set_title(title)
            a.set_xticks([0, 1, 2])
            a.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    fig.suptitle("v8 PPO_RAW: two committed on-policy batches\nUpdate diagnostic only; not evidence of control improvement or convergence", fontsize=10)
    fig.tight_layout()
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / ("ARCHIVE_PPO_RAW_UPDATE_HISTORY." + ext), dpi=180)
    plt.close(fig)
    receipt.update(status="PASS", numerical_checks=checks, PPO_RAW_committed_batches=2, PPO_RAW_update_calls=6, PPO_RAW_zero_gradient_update_calls=sum(r["gradient_norm"] == 0 for r in training), fresh_records_in_this_arm=8, original_cancelled_batch_preserved_in_checkpoint=True)
    (out / "ARCHIVE_EVIDENCE_CHECK.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "out": str(out), "checked_complete_TASKs": len(checks), "PPO_RAW_committed_batches": 2}))


if __name__ == "__main__":
    main()
