"""Plots and summary tables for adaptive MPC condition comparisons."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row[key]) for row in rows], dtype=float)


def save_adaptive_mpc_conditions_comparison(
    condition_rows: dict[str, list[dict[str, Any]]],
    true_params: dict[str, Any],
    out_path: Path,
    mpc_constraints: dict[str, Any] | None = None,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 2, figsize=(14, 13), sharex=False)
    axes_flat = axes.ravel()

    panels = [
        ("theta", "theta [deg]", lambda rows: np.degrees(_series(rows, "theta"))),
        ("delta_r", "delta_r [mm]", lambda rows: 1000.0 * _series(rows, "delta_r")),
        ("F_tan", "F_tan [N]", lambda rows: _series(rows, "F_tan")),
        ("F_rad", "F_rad [N]", lambda rows: _series(rows, "F_rad")),
        ("m_hat", "m_hat [kg]", lambda rows: _series(rows, "m_hat")),
        ("k_hat", "k_hat [N/m]", lambda rows: _series(rows, "k_hat")),
        ("b_r_hat", "b_r_hat [N s/m]", lambda rows: _series(rows, "b_r_hat")),
        ("prediction_error", "one-step pred error", lambda rows: _series(rows, "prediction_error")),
    ]

    for ax, (name, ylabel, getter) in zip(axes_flat, panels):
        for condition, rows in condition_rows.items():
            ax.plot(_series(rows, "t"), getter(rows), label=condition)
        if name == "theta":
            ax.axhline(np.degrees(float(true_params["theta_target"])), color="black", linestyle=":", linewidth=1.0)
        elif name == "delta_r":
            limit = 1000.0 * float(true_params["delta_r_max"])
            ax.axhline(limit, color="black", linestyle=":", linewidth=1.0)
            ax.axhline(-limit, color="black", linestyle=":", linewidth=1.0)
        elif name == "F_tan":
            limit = float((mpc_constraints or {}).get("F_tan_max", true_params["F_tan_max"]))
            ax.axhline(limit, color="black", linestyle=":", linewidth=1.0)
            ax.axhline(-limit, color="black", linestyle=":", linewidth=1.0)
        elif name == "F_rad":
            limit = float((mpc_constraints or {}).get("F_rad_max", true_params["F_rad_max"]))
            ax.axhline(limit, color="black", linestyle=":", linewidth=1.0)
            ax.axhline(-limit, color="black", linestyle=":", linewidth=1.0)
        elif name == "m_hat":
            ax.axhline(float(true_params["m"]), color="black", linestyle=":", linewidth=1.0)
        elif name == "k_hat":
            ax.axhline(float(true_params["k"]), color="black", linestyle=":", linewidth=1.0)
        elif name == "b_r_hat":
            ax.axhline(float(true_params["b_r"]), color="black", linestyle=":", linewidth=1.0)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("time [s]")
        ax.grid(True, alpha=0.25)

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=max(1, len(labels)), frameon=False)
    fig.suptitle("Spring2D Adaptive MPC Conditions")
    fig.tight_layout(rect=(0.0, 0.05, 1.0, 0.98))
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def load_baseline_summary(path: Path) -> dict[str, dict[str, str]]:
    if not Path(path).exists():
        return {}
    with Path(path).open("r", newline="") as f:
        return {row["condition"]: row for row in csv.DictReader(f)}


def save_adaptive_mpc_summary_table(
    condition_rows: dict[str, list[dict[str, Any]]],
    true_params: dict[str, Any],
    out_path: Path,
    baseline_summary_path: Path | None = None,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    baseline = load_baseline_summary(baseline_summary_path) if baseline_summary_path else {}
    fields = [
        "condition",
        "done_reason",
        "target_reached",
        "final_theta_deg",
        "baseline_final_theta_deg",
        "theta_improvement_deg",
        "max_abs_delta_r_mm",
        "max_abs_omega",
        "max_abs_alpha",
        "max_abs_F_tan",
        "max_abs_F_rad",
        "final_m_hat",
        "final_k_hat",
        "final_b_r_hat",
        "final_m_mpc",
        "final_k_mpc",
        "final_b_r_mpc",
        "initial_prediction_error",
        "final_prediction_error",
        "prediction_error_ratio",
    ]
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for condition, rows in condition_rows.items():
            pred = _series(rows, "prediction_error")
            finite_pred = pred[np.isfinite(pred)]
            initial_pred = float(finite_pred[0]) if len(finite_pred) else np.nan
            final_pred = float(finite_pred[-1]) if len(finite_pred) else np.nan
            final = rows[-1]
            omegas = _series(rows, "omega")
            alpha = np.abs(_series(rows, "omega_dot"))
            final_theta_deg = float(np.degrees(float(final["theta"])))
            baseline_theta = np.nan
            if condition in baseline and baseline[condition].get("final_theta_deg", ""):
                baseline_theta = float(baseline[condition]["final_theta_deg"])
            writer.writerow(
                {
                    "condition": condition,
                    "done_reason": final.get("done_reason", ""),
                    "target_reached": final.get("target_reached", ""),
                    "final_theta_deg": final_theta_deg,
                    "baseline_final_theta_deg": baseline_theta,
                    "theta_improvement_deg": final_theta_deg - baseline_theta if np.isfinite(baseline_theta) else np.nan,
                    "max_abs_delta_r_mm": float(np.max(np.abs(_series(rows, "delta_r"))) * 1000.0),
                    "max_abs_omega": float(np.max(np.abs(omegas))),
                    "max_abs_alpha": float(np.max(alpha)),
                    "max_abs_F_tan": float(np.max(np.abs(_series(rows, "F_tan")))),
                    "max_abs_F_rad": float(np.max(np.abs(_series(rows, "F_rad")))),
                    "final_m_hat": float(final["m_hat"]),
                    "final_k_hat": float(final["k_hat"]),
                    "final_b_r_hat": float(final["b_r_hat"]),
                    "final_m_mpc": float(final["m_mpc"]),
                    "final_k_mpc": float(final["k_mpc"]),
                    "final_b_r_mpc": float(final["b_r_mpc"]),
                    "initial_prediction_error": initial_pred,
                    "final_prediction_error": final_pred,
                    "prediction_error_ratio": final_pred / initial_pred if initial_pred > 0 else np.nan,
                }
            )
