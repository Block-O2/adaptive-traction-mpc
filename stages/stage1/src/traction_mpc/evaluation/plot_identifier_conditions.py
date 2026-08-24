"""Plots and summary tables for identifier condition comparisons."""

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


def save_identifier_conditions_comparison(
    condition_rows: dict[str, list[dict[str, Any]]],
    true_params: dict[str, Any],
    out_path: Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 2, figsize=(14, 13), sharex=False)
    axes_flat = axes.ravel()

    panels = [
        ("theta", "theta [deg]", lambda rows: np.degrees(_series(rows, "theta"))),
        ("delta_r", "delta_r [mm]", lambda rows: 1000.0 * _series(rows, "delta_r")),
        ("m_hat", "m_hat [kg]", lambda rows: _series(rows, "m_hat")),
        ("k_hat", "k_hat [N/m]", lambda rows: _series(rows, "k_hat")),
        ("b_r_hat", "b_r_hat [N s/m]", lambda rows: _series(rows, "b_r_hat")),
        ("prediction_error", "one-step pred error", lambda rows: _series(rows, "prediction_error")),
    ]

    for ax, (name, ylabel, getter) in zip(axes_flat, panels):
        for condition, rows in condition_rows.items():
            t = _series(rows, "t")
            ax.plot(t, getter(rows), label=condition)
        if name == "m_hat":
            ax.axhline(float(true_params["m"]), color="black", linestyle=":", linewidth=1.0, label="true")
        elif name == "k_hat":
            ax.axhline(float(true_params["k"]), color="black", linestyle=":", linewidth=1.0, label="true")
        elif name == "b_r_hat":
            ax.axhline(float(true_params["b_r"]), color="black", linestyle=":", linewidth=1.0, label="true")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)

    axes_flat[6].axis("off")
    handles, labels = axes_flat[0].get_legend_handles_labels()
    axes_flat[6].legend(handles, labels, loc="center", frameon=False)
    axes_flat[7].axis("off")
    for ax in axes_flat[:6]:
        ax.set_xlabel("time [s]")

    fig.suptitle("Spring2D Identifier Conditions")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def save_identifier_summary_table(
    condition_rows: dict[str, list[dict[str, Any]]],
    true_params: dict[str, Any],
    out_path: Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition",
        "done_reason",
        "final_theta_deg",
        "max_abs_delta_r_mm",
        "final_m_hat",
        "final_k_hat",
        "final_b_r_hat",
        "m_error",
        "k_error",
        "b_r_error",
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
            writer.writerow(
                {
                    "condition": condition,
                    "done_reason": final.get("done_reason", ""),
                    "final_theta_deg": float(np.degrees(float(final["theta"]))),
                    "max_abs_delta_r_mm": float(np.max(np.abs(_series(rows, "delta_r"))) * 1000.0),
                    "final_m_hat": float(final["m_hat"]),
                    "final_k_hat": float(final["k_hat"]),
                    "final_b_r_hat": float(final["b_r_hat"]),
                    "m_error": float(final["m_hat"]) - float(true_params["m"]),
                    "k_error": float(final["k_hat"]) - float(true_params["k"]),
                    "b_r_error": float(final["b_r_hat"]) - float(true_params["b_r"]),
                    "initial_prediction_error": initial_pred,
                    "final_prediction_error": final_pred,
                    "prediction_error_ratio": final_pred / initial_pred if initial_pred > 0 else np.nan,
                }
            )
