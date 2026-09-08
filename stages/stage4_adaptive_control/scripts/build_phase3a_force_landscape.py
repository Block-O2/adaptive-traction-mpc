#!/usr/bin/env python3
"""Build the final analytic High-ROM force landscape from compact inputs."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm
import numpy as np

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
SUMMARY = STAGE / "results/summaries/phase3a_corrected_high_rom"
SOURCES = SUMMARY / "report_sources"
sys.path.insert(0, str(REPO / "stages/stage3_full3d/src"))
sys.path.insert(0, str(STAGE / "src"))

from traction_mpc_stage3.human import HUMAN  # noqa: E402
from traction_mpc_stage4.cuff_allocator import (  # noqa: E402
    CurrentForceMinimizingAllocator,
    default_engineering_cuff_allocator,
    sagittal_allocation_matrix,
)
from traction_mpc_stage4.dynamics_failure_audit import geometry_from_trace_vector  # noqa: E402
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel  # noqa: E402

HIGH_ROM_HUMAN = replace(
    HUMAN,
    q_min_rad=(0.0, 0.0),
    q_max_rad=(math.radians(125.0), math.radians(125.0)),
)
OVERLAYS = {
    "40/80 Rigid NEW": ("40_80_rigid.npz", "#2563a8", "-"),
    "40/80 P1 NEW": ("40_80_p1.npz", "#2563a8", "--"),
    "90/120 Rigid NEW": ("90_120_rigid.npz", "#18794e", "-"),
    "90/120 P1 NEW": ("90_120_p1.npz", "#18794e", "--"),
    "120/120 Rigid NEW": ("120_120_rigid.npz", "#7046a3", "-"),
    "120/120 P1 NEW": ("120_120_p1.npz", "#7046a3", "--"),
}


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def model_from_compact_source() -> BaseParameterHumanModel:
    source = load_npz(SOURCES / "force_model_inputs.npz")
    return BaseParameterHumanModel(
        geometry=geometry_from_trace_vector(source["geometry_estimate"]),
        beta=np.asarray(source["dynamic_base_estimate"], dtype=float),
        rom_human=HIGH_ROM_HUMAN,
    )


def allocate(allocator: Any, torque: np.ndarray, q: np.ndarray, model: Any) -> np.ndarray:
    return np.asarray(allocator.allocate(torque, q, model)["wrench_world"], dtype=float)


def dense_maps(model: BaseParameterHumanModel) -> dict[str, np.ndarray]:
    q1_deg = np.arange(0.0, 125.0 + 1e-9, 1.0)
    q2_deg = np.arange(0.0, 125.0 + 1e-9, 1.0)
    shape = (len(q2_deg), len(q1_deg))
    outputs = {
        "static_registered_force_n": np.full(shape, np.nan),
        "static_minimum_translational_force_n": np.full(shape, np.nan),
        "translational_force_map_condition": np.full(shape, np.inf),
        "full_sagittal_allocation_condition": np.full(shape, np.inf),
        "unit_hip_acceleration_force_n_per_rad_s2": np.full(shape, np.nan),
        "unit_knee_acceleration_force_n_per_rad_s2": np.full(shape, np.nan),
    }
    registered = default_engineering_cuff_allocator()
    minimum = CurrentForceMinimizingAllocator()
    basis = np.column_stack([model.geometry.plane_x_world, model.geometry.plane_z_world])
    for j, q2 in enumerate(q2_deg):
        for i, q1 in enumerate(q1_deg):
            q = np.radians([q1, q2])
            static_tau = model.inverse_dynamics(q, np.zeros(2), np.zeros(2))
            force_map = model.geometry.translational_jacobian_world(q).T @ basis
            singular = np.linalg.svd(force_map, compute_uv=False)
            if singular[-1] > 1e-12:
                outputs["translational_force_map_condition"][j, i] = singular[0] / singular[-1]
            full = np.linalg.svd(sagittal_allocation_matrix(q, model), compute_uv=False)
            if full[-1] > 1e-12:
                outputs["full_sagittal_allocation_condition"][j, i] = full[0] / full[-1]
            try:
                outputs["static_registered_force_n"][j, i] = np.linalg.norm(
                    allocate(registered, static_tau, q, model)[:3]
                )
                outputs["static_minimum_translational_force_n"][j, i] = np.linalg.norm(
                    allocate(minimum, static_tau, q, model)[:3]
                )
                mass = model.mass_matrix(q)
                outputs["unit_hip_acceleration_force_n_per_rad_s2"][j, i] = np.linalg.norm(
                    allocate(registered, mass @ np.array([1.0, 0.0]), q, model)[:3]
                )
                outputs["unit_knee_acceleration_force_n_per_rad_s2"][j, i] = np.linalg.norm(
                    allocate(registered, mass @ np.array([0.0, 1.0]), q, model)[:3]
                )
            except (RuntimeError, ValueError, np.linalg.LinAlgError):
                pass
    outputs["q1_deg"] = q1_deg
    outputs["q2_deg"] = q2_deg
    for threshold in (200.0, 220.0, 250.0):
        outputs[f"registered_margin_{int(threshold)}n"] = (
            threshold - outputs["static_registered_force_n"]
        )
    return outputs


def save_dense_data(maps: dict[str, np.ndarray], output: Path) -> None:
    np.savez_compressed(output / "dense_force_maps.npz", **maps)
    fields = [key for key in maps if key not in {"q1_deg", "q2_deg"}]
    with (output / "dense_force_maps.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["q1_deg", "q2_deg", *fields])
        for j, q2 in enumerate(maps["q2_deg"]):
            for i, q1 in enumerate(maps["q1_deg"]):
                writer.writerow([q1, q2, *[maps[key][j, i] for key in fields]])


def heatmap(
    values: np.ndarray,
    title: str,
    label: str,
    *,
    logarithmic: bool,
    ax: Any,
) -> None:
    finite = np.asarray(values, dtype=float).copy()
    finite[~np.isfinite(finite)] = np.nan
    kwargs: dict[str, Any] = {
        "origin": "lower",
        "extent": [0, 125, 0, 125],
        "aspect": "equal",
        "cmap": "viridis",
    }
    if logarithmic:
        positive = finite[np.isfinite(finite) & (finite > 0)]
        kwargs["norm"] = LogNorm(
            vmin=max(float(np.percentile(positive, 2)), 1e-3),
            vmax=float(np.percentile(positive, 98)),
        )
    artist = ax.imshow(finite, **kwargs)
    ax.set(xlabel="q1 (deg)", ylabel="q2 (deg)", title=title)
    plt.colorbar(artist, ax=ax, label=label, shrink=0.83)


def plot_dense_maps(maps: dict[str, np.ndarray], figures: Path) -> None:
    q1, q2 = np.meshgrid(maps["q1_deg"], maps["q2_deg"])
    static = maps["static_registered_force_n"]
    fig = plt.figure(figsize=(9.2, 7.0))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(q1, q2, np.clip(static, 0.0, 500.0), cmap="viridis", linewidth=0)
    ax.plot_surface(
        q1[::8, ::8],
        q2[::8, ::8],
        np.full_like(q1[::8, ::8], 200.0),
        color="#d18b00",
        alpha=0.28,
    )
    ax.set(
        xlabel="q1 (deg)",
        ylabel="q2 (deg)",
        zlabel="|F_static| (N)",
        title="Registered allocator quasistatic force surface",
    )
    ax.set_zlim(0, 225)
    fig.text(
        0.02,
        0.02,
        "200 N is a registered simulation engineering target, not a clinical threshold.",
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(figures / "01_dense_static_force_surface.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    for ax, threshold in zip(axes, (200, 220, 250), strict=True):
        margin = maps[f"registered_margin_{threshold}n"]
        artist = ax.imshow(
            np.clip(margin, -250.0, 250.0),
            origin="lower",
            extent=[0, 125, 0, 125],
            aspect="equal",
            cmap="RdBu",
            norm=TwoSlopeNorm(vmin=-250, vcenter=0, vmax=250),
        )
        if float(np.nanmin(static)) <= threshold <= float(np.nanmax(static)):
            ax.contour(q1, q2, static, levels=[threshold], colors="black", linewidths=1.4)
        else:
            ax.text(
                0.5,
                0.05,
                "no zero-margin crossing",
                transform=ax.transAxes,
                ha="center",
                va="bottom",
            )
        ax.set(title=f"{threshold} N margin", xlabel="q1 (deg)", ylabel="q2 (deg)")
        plt.colorbar(artist, ax=ax, label=f"{threshold} - |F_static| (N)", shrink=0.82)
    fig.suptitle("Quasistatic engineering force margins")
    fig.savefig(figures / "02_force_margin_contours.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), constrained_layout=True)
    heatmap(
        maps["translational_force_map_condition"],
        "Translational Human force-map conditioning",
        "condition number",
        logarithmic=True,
        ax=axes[0],
    )
    heatmap(
        maps["full_sagittal_allocation_condition"],
        "Full [Fx,Fz,My] allocation conditioning",
        "condition number",
        logarithmic=True,
        ax=axes[1],
    )
    fig.savefig(figures / "03_conditioning_maps.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), constrained_layout=True)
    heatmap(
        maps["unit_hip_acceleration_force_n_per_rad_s2"],
        "Unit hip-acceleration force sensitivity",
        "N / (rad/s^2)",
        logarithmic=True,
        ax=axes[0],
    )
    heatmap(
        maps["unit_knee_acceleration_force_n_per_rad_s2"],
        "Unit knee-acceleration force sensitivity",
        "N / (rad/s^2)",
        logarithmic=True,
        ax=axes[1],
    )
    fig.savefig(figures / "04_unit_acceleration_sensitivity.png", dpi=210)
    plt.close(fig)


def plot_corrected_overlays(maps: dict[str, np.ndarray], figures: Path) -> None:
    q1, q2 = np.meshgrid(maps["q1_deg"], maps["q2_deg"])
    fig = plt.figure(figsize=(9.5, 7.2))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        q1,
        q2,
        np.clip(maps["static_registered_force_n"], 0.0, 500.0),
        cmap="Greys",
        linewidth=0,
        alpha=0.72,
    )
    for label, (filename, color, linestyle) in OVERLAYS.items():
        source = load_npz(SOURCES / filename)
        q = source["force_overlay_q_deg"]
        force = source["force_overlay_force_n"]
        ax.plot(q[:, 0], q[:, 1], force, color=color, linestyle=linestyle, label=label)
    ax.set(
        xlabel="q1 (deg)",
        ylabel="q2 (deg)",
        zlabel="force (N)",
        title="Analytic quasistatic surface with corrected dynamic overlays",
    )
    ax.set_zlim(0, 225)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(figures / "05_corrected_dynamic_overlays.png", dpi=210)
    plt.close(fig)


def verify_against_reference(maps: dict[str, np.ndarray]) -> dict[str, Any]:
    reference = load_npz(SUMMARY / "dense_force_maps.npz")
    if set(reference) != set(maps):
        raise AssertionError("dense force-map key set changed")
    for key in reference:
        np.testing.assert_allclose(
            maps[key],
            reference[key],
            rtol=0.0,
            atol=1e-12,
            equal_nan=True,
            err_msg=key,
        )
    static = maps["static_registered_force_n"]
    return {
        "grid_shape": list(static.shape),
        "minimum_n": float(np.nanmin(static)),
        "maximum_n": float(np.nanmax(static)),
        "threshold_crossings": {
            str(threshold): bool(
                float(np.nanmin(static)) <= threshold <= float(np.nanmax(static))
            )
            for threshold in (200, 220, 250)
        },
        "reference_array_match": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination for regenerated NPZ, CSV, figures, and verification JSON.",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    maps = dense_maps(model_from_compact_source())
    verification = verify_against_reference(maps)
    save_dense_data(maps, output)
    plot_dense_maps(maps, figures)
    plot_corrected_overlays(maps, figures)
    payload = {
        "schema": "phase3a_final_force_landscape_verification_v1",
        "source": str(SOURCES.relative_to(REPO)),
        "scientific_settings_changed": False,
        "new_trajectory_runs": 0,
        **verification,
        "outputs": sorted(
            str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
        ),
    }
    (output / "verification.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"output": str(output), **verification}, indent=2))


if __name__ == "__main__":
    main()
