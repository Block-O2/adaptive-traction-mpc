"""Stage 10A read-only Spring2D dynamics and parameterization audit."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import casadi as ca
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_stage9b_nmpc_diagnosis import DiagnosticCasadiNMPC
from traction_mpc.models.spring2d_dynamics import compute_moving_base_terms, step_dynamics


REPLAY = PROJECT_ROOT / "results" / "stage9j_gap_decomposition" / "stage9j_replay.csv"
CONFIG = PROJECT_ROOT / "results" / "stage9j_gap_decomposition" / "stage9j_config_snapshot.json"
OUTPUT = PROJECT_ROOT / "results" / "stage10a_dynamics_audit"
PARAMETERS = ("m", "k", "b_r")
PARAM_SCALE = np.array([1.0, 450.0, 20.0], dtype=float)
AFFINE_SCALE = np.array([1.0, 450.0, 20.0], dtype=float)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def state(row: dict[str, str], source: str) -> np.ndarray:
    return np.array([float(row[f"{source}_{name}"]) for name in ("theta", "omega", "r", "r_dot")])


def action(row: dict[str, str]) -> np.ndarray:
    return np.array([float(row["F_tan"]), float(row["F_rad"])], dtype=float)


def parameter_vector(row: dict[str, str], source: str) -> np.ndarray:
    if source == "true":
        return np.array([float(row[f"true_{name}_param"]) for name in PARAMETERS], dtype=float)
    if source == "online":
        return np.array([float(row[f"online_{name}_hat"]) for name in PARAMETERS], dtype=float)
    raise ValueError(source)


def symbolic_map(model_params: dict[str, Any], dt: float) -> ca.Function:
    dyn = DiagnosticCasadiNMPC.__new__(DiagnosticCasadiNMPC)
    dyn.model_params = dict(model_params)
    dyn.prediction_dt = float(dt)
    x = ca.SX.sym("x", 4)
    u = ca.SX.sym("u", 2)
    p = ca.SX.sym("p", 3)
    phi = DiagnosticCasadiNMPC._rk4_symbolic(
        dyn,
        x,
        u,
        {"m": p[0], "k": p[1], "b_r": p[2]},
    )
    jac = ca.jacobian(phi, p)
    alpha = (phi[1] - x[1]) / float(dt)
    dalpha = ca.jacobian(alpha, p)
    return ca.Function("stage10a_phi", [x, u, p], [phi, jac, alpha, dalpha])


def numpy_prediction(
    x: np.ndarray,
    u: np.ndarray,
    p: np.ndarray,
    model_params: dict[str, Any],
    dt: float,
) -> np.ndarray:
    params = dict(model_params)
    params.update({name: float(value) for name, value in zip(PARAMETERS, p)})
    return step_dynamics(x, u, dt, params)


def finite_difference_alpha(
    x: np.ndarray,
    u: np.ndarray,
    p: np.ndarray,
    model_params: dict[str, Any],
    dt: float,
) -> np.ndarray:
    derivative = np.empty(3, dtype=float)
    for index in range(3):
        h = 1.0e-6 * max(abs(float(p[index])), float(PARAM_SCALE[index]), 1.0)
        plus = p.copy()
        minus = p.copy()
        plus[index] += h
        minus[index] -= h
        alpha_plus = (numpy_prediction(x, u, plus, model_params, dt)[1] - x[1]) / dt
        alpha_minus = (numpy_prediction(x, u, minus, model_params, dt)[1] - x[1]) / dt
        derivative[index] = (alpha_plus - alpha_minus) / (2.0 * h)
    return derivative


def affine_dynamics_check(
    x: np.ndarray,
    u: np.ndarray,
    p: np.ndarray,
    model_params: dict[str, Any],
) -> tuple[float, float, float]:
    params = dict(model_params)
    params.update({name: float(value) for name, value in zip(PARAMETERS, p)})
    terms = compute_moving_base_terms(x, u, params)
    m, k, b_r = p
    theta, omega, r, r_dot = x
    G = np.asarray(terms["M"], dtype=float) / m
    Q = np.asarray(terms["Q"], dtype=float)
    d = np.array([b_r * r_dot + k * (max(r, 1.0e-6) - params["L0"]), params["b_theta"] * omega])
    c = (np.asarray(terms["h"], dtype=float) - d) / m
    affine_rhs = (
        (1.0 / m) * (Q - np.array([0.0, params["b_theta"] * omega]))
        - (k / m) * np.array([max(r, 1.0e-6) - params["L0"], 0.0])
        - (b_r / m) * np.array([r_dot, 0.0])
        - c
    )
    affine_accel = np.linalg.solve(G, affine_rhs)
    implemented = np.array([terms["r_ddot"], terms["omega_dot"]], dtype=float)
    g11, g12, g22 = G[0, 0], G[0, 1], G[1, 1]
    geometry_inertia = g22 - g12 * g12 / g11
    mass_driver = float(np.linalg.norm(Q - d))
    return float(np.max(np.abs(affine_accel - implemented))), float(geometry_inertia), mass_driver


def percentile(values: list[float] | np.ndarray, q: float) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.percentile(arr, q)) if len(arr) else np.nan


def mean(values: list[float] | np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if len(arr) else np.nan


def maximum(values: list[float] | np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.max(arr)) if len(arr) else np.nan


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def column_correlation(jacobian: np.ndarray) -> np.ndarray:
    gram = jacobian.T @ jacobian
    norm = np.sqrt(np.maximum(np.diag(gram), 0.0))
    return np.divide(gram, np.outer(norm, norm), out=np.full((3, 3), np.nan), where=np.outer(norm, norm) > 0.0)


def affine_regressor(
    x: np.ndarray,
    u: np.ndarray,
    p: np.ndarray,
    model_params: dict[str, Any],
) -> np.ndarray:
    params = dict(model_params)
    params.update({name: float(value) for name, value in zip(PARAMETERS, p)})
    terms = compute_moving_base_terms(x, u, params)
    _, omega, r, r_dot = x
    delta_r = max(float(r), 1.0e-6) - float(params["L0"])
    return np.array(
        [
            [float(terms["Q_r"]), -delta_r, -float(r_dot)],
            [float(terms["Q_theta"]) - float(params["b_theta"]) * float(omega), 0.0, 0.0],
        ],
        dtype=float,
    )


def aggregate_sensitivity(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    conditions = sorted({str(row["condition"]) for row in records})
    for condition in conditions + ["all"]:
        subset = records if condition == "all" else [row for row in records if row["condition"] == condition]
        for index, parameter in enumerate(PARAMETERS):
            raw = np.abs([row["dalpha"][index] for row in subset])
            relative = np.abs([row["relative_dalpha"][index] for row in subset])
            threshold = percentile(relative, 90)
            high = [row for row in subset if abs(row["relative_dalpha"][index]) >= threshold]
            output.append(
                {
                    "condition": condition,
                    "parameter": parameter,
                    "n_transitions": len(subset),
                    "abs_dalpha_dp_mean": mean(raw),
                    "abs_dalpha_dp_p95": percentile(raw, 95),
                    "abs_dalpha_dp_max": maximum(raw),
                    "abs_relative_dalpha_mean": mean(relative),
                    "abs_relative_dalpha_p95": percentile(relative, 95),
                    "abs_relative_dalpha_max": maximum(relative),
                    "finite_difference_abs_error_max": maximum([row["fd_abs_error"][index] for row in subset]),
                    "finite_difference_scaled_error_max": maximum([row["fd_scaled_error"][index] for row in subset]),
                    "top10_abs_F_tan_mean": mean([row["abs_F_tan"] for row in high]),
                    "top10_abs_F_rad_mean": mean([row["abs_F_rad"] for row in high]),
                    "top10_abs_delta_r_mean": mean([row["abs_delta_r"] for row in high]),
                    "top10_abs_r_dot_mean": mean([row["abs_r_dot"] for row in high]),
                    "top10_abs_omega_mean": mean([row["abs_omega"] for row in high]),
                    "top10_mass_driver_mean": mean([row["mass_driver"] for row in high]),
                    "model_alpha_rmse": float(np.sqrt(mean([row["model_alpha_error"] ** 2 for row in subset]))),
                    "symbolic_numpy_state_max_abs": maximum([row["symbolic_numpy_error"] for row in subset]),
                    "planner_dt_symbolic_numpy_state_max_abs": maximum([row["planner_dt_symbolic_numpy_error"] for row in subset]),
                    "affine_acceleration_max_abs": maximum([row["affine_error"] for row in subset]),
                    "geometry_inertia_factor_min": float(np.min([row["geometry_inertia"] for row in subset])),
                    "geometry_inertia_factor_median": percentile([row["geometry_inertia"] for row in subset], 50),
                    "geometry_inertia_factor_max": float(np.max([row["geometry_inertia"] for row in subset])),
                }
            )
    return output


def aggregate_conditioning(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    conditions = sorted({str(row["condition"]) for row in windows})
    for condition in conditions + ["all"]:
        subset = windows if condition == "all" else [row for row in windows if row["condition"] == condition]
        output.append(
            {
                "condition": condition,
                "n_windows": len(subset),
                "rank3_fraction": mean([row["rank"] == 3 for row in subset]),
                "sigma_max_median": percentile([row["singular_values"][0] for row in subset], 50),
                "sigma_mid_median": percentile([row["singular_values"][1] for row in subset], 50),
                "sigma_min_mean": mean([row["singular_values"][2] for row in subset]),
                "sigma_min_median": percentile([row["singular_values"][2] for row in subset], 50),
                "sigma_min_p05": percentile([row["singular_values"][2] for row in subset], 5),
                "jacobian_condition_median": percentile([row["jacobian_condition"] for row in subset], 50),
                "jacobian_condition_p95": percentile([row["jacobian_condition"] for row in subset], 95),
                "jacobian_condition_max": maximum([row["jacobian_condition"] for row in subset]),
                "information_condition_median": percentile([row["information_condition"] for row in subset], 50),
                "information_condition_p95": percentile([row["information_condition"] for row in subset], 95),
                "abs_column_corr_m_k_mean": mean([abs(row["correlation"][0, 1]) for row in subset]),
                "abs_column_corr_m_k_p95": percentile([abs(row["correlation"][0, 1]) for row in subset], 95),
                "abs_column_corr_m_b_r_mean": mean([abs(row["correlation"][0, 2]) for row in subset]),
                "abs_column_corr_m_b_r_p95": percentile([abs(row["correlation"][0, 2]) for row in subset], 95),
                "abs_column_corr_k_b_r_mean": mean([abs(row["correlation"][1, 2]) for row in subset]),
                "abs_column_corr_k_b_r_p95": percentile([abs(row["correlation"][1, 2]) for row in subset], 95),
                "scaled_m_column_norm_median": percentile([row["column_norms"][0] for row in subset], 50),
                "scaled_k_column_norm_median": percentile([row["column_norms"][1] for row in subset], 50),
                "scaled_b_r_column_norm_median": percentile([row["column_norms"][2] for row in subset], 50),
                "affine_rank3_fraction": mean([row["affine_rank"] == 3 for row in subset]),
                "affine_sigma_min_median": percentile([row["affine_singular_values"][2] for row in subset], 50),
                "affine_condition_median": percentile([row["affine_condition"] for row in subset], 50),
                "affine_condition_p95": percentile([row["affine_condition"] for row in subset], 95),
                "affine_abs_corr_lambda_kappa_p95": percentile([abs(row["affine_correlation"][0, 1]) for row in subset], 95),
                "affine_abs_corr_lambda_beta_p95": percentile([abs(row["affine_correlation"][0, 2]) for row in subset], 95),
                "affine_abs_corr_kappa_beta_p95": percentile([abs(row["affine_correlation"][1, 2]) for row in subset], 95),
            }
        )
    return output


def save_figures(
    sensitivity_rows: list[dict[str, Any]],
    conditioning_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    output: Path,
) -> None:
    fig_dir = output / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    conditions = [row["condition"] for row in conditioning_rows if row["condition"] != "all"]
    x = np.arange(len(conditions))
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for index, parameter in enumerate(PARAMETERS):
        values = [next(row["abs_relative_dalpha_p95"] for row in sensitivity_rows if row["condition"] == c and row["parameter"] == parameter) for c in conditions]
        ax.bar(x + (index - 1) * 0.25, values, width=0.24, label=parameter)
    ax.set_xticks(x, conditions, rotation=25, ha="right")
    ax.set_ylabel("p95 |p d alpha / dp|")
    ax.set_title("Dimensionless discrete-alpha sensitivity by condition")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "01_relative_alpha_sensitivity_by_condition.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    cond = [row["jacobian_condition_p95"] for row in conditioning_rows if row["condition"] != "all"]
    affine_cond = [row["affine_condition_p95"] for row in conditioning_rows if row["condition"] != "all"]
    sigma = [row["sigma_min_median"] for row in conditioning_rows if row["condition"] != "all"]
    axes[0].bar(x - 0.18, cond, width=0.35, label="discrete NLS J")
    axes[0].bar(x + 0.18, affine_cond, width=0.35, label="affine EIV H")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("p95 cond(J_scaled)")
    axes[0].legend(fontsize=8)
    axes[1].bar(x, sigma)
    axes[1].set_yscale("log")
    axes[1].set_ylabel("median smallest singular value")
    for ax in axes:
        ax.set_xticks(x, conditions, rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Windowed identifier Jacobian conditioning")
    fig.tight_layout()
    fig.savefig(fig_dir / "02_identifier_jacobian_conditioning.png", dpi=160)
    plt.close(fig)

    stride = max(len(records) // 2500, 1)
    sample = records[::stride]
    drivers = ["mass_driver", "abs_delta_r", "abs_r_dot"]
    labels = ["||Q-d||", "|r-L0|", "|r_dot|"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for index, (parameter, driver, label) in enumerate(zip(PARAMETERS, drivers, labels)):
        axes[index].scatter(
            [row[driver] for row in sample],
            [abs(row["relative_dalpha"][index]) for row in sample],
            s=5,
            alpha=0.25,
        )
        axes[index].set_xlabel(label)
        axes[index].set_ylabel(f"|{parameter} d alpha/d{parameter}|")
        axes[index].grid(True, alpha=0.25)
    fig.suptitle("State/input regions associated with parameter sensitivity")
    fig.tight_layout()
    fig.savefig(fig_dir / "03_observability_regions.png", dpi=160)
    plt.close(fig)


def main() -> None:
    base = json.loads(CONFIG.read_text())
    model_params = dict(base["true_params"])
    dt = float(model_params["dt"])
    weights = np.asarray(base["identifier"]["state_weights"], dtype=float)
    regularization = float(base["identifier"]["lambda_reg"])
    map_fn = symbolic_map(model_params, dt)
    planner_dt = float(base["mpc_params"]["solver"]["prediction_dt"])
    planner_map_fn = symbolic_map(model_params, planner_dt)
    replay = read_rows(REPLAY)
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in replay:
        grouped[(row["condition"], int(row["seed"]))].append(row)
    records: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    for (condition, seed), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: int(row["step"]))
        local_jacobians: list[np.ndarray] = []
        local_affine_regressors: list[np.ndarray] = []
        for index in range(1, len(rows)):
            previous, current = rows[index - 1], rows[index]
            x_true = state(previous, "true")
            x_est = state(previous, "estimated")
            u = action(current)
            p_true = parameter_vector(current, "true")
            p_online = parameter_vector(previous, "online")
            phi, _, alpha_model, dalpha = map_fn(x_true, u, p_true)
            phi = np.asarray(phi, dtype=float).reshape(4)
            dalpha = np.asarray(dalpha, dtype=float).reshape(3)
            _, jac_est, _, _ = map_fn(x_est, u, p_online)
            jac_est = np.asarray(jac_est, dtype=float).reshape(4, 3)
            residual_jacobian = -(weights[:, None] * jac_est)
            scaled_residual_jacobian = residual_jacobian * PARAM_SCALE[None, :]
            local_jacobians.append(scaled_residual_jacobian)
            local_affine_regressors.append(affine_regressor(x_est, u, p_online, model_params) * AFFINE_SCALE[None, :])
            fd = finite_difference_alpha(x_true, u, p_true, model_params, dt)
            numpy_phi = numpy_prediction(x_true, u, p_true, model_params, dt)
            planner_phi = np.asarray(planner_map_fn(x_true, u, p_true)[0], dtype=float).reshape(4)
            planner_numpy_phi = numpy_prediction(x_true, u, p_true, model_params, planner_dt)
            true_alpha = (state(current, "true")[1] - x_true[1]) / dt
            affine_error, geometry_inertia, mass_driver = affine_dynamics_check(x_true, u, p_true, model_params)
            abs_error = np.abs(dalpha - fd)
            scaled_error = abs_error / np.maximum(1.0, np.maximum(np.abs(dalpha), np.abs(fd)))
            records.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "step": int(current["step"]),
                    "dalpha": dalpha,
                    "relative_dalpha": dalpha * p_true,
                    "fd_abs_error": abs_error,
                    "fd_scaled_error": scaled_error,
                    "model_alpha_error": float(alpha_model) - true_alpha,
                    "symbolic_numpy_error": float(np.max(np.abs(phi - numpy_phi))),
                    "planner_dt_symbolic_numpy_error": float(np.max(np.abs(planner_phi - planner_numpy_phi))),
                    "affine_error": affine_error,
                    "geometry_inertia": geometry_inertia,
                    "mass_driver": mass_driver,
                    "abs_F_tan": abs(float(u[0])),
                    "abs_F_rad": abs(float(u[1])),
                    "abs_delta_r": abs(float(x_true[2] - model_params["L0"])),
                    "abs_r_dot": abs(float(x_true[3])),
                    "abs_omega": abs(float(x_true[1])),
                }
            )
            step = int(current["step"])
            if step % int(base["identifier"]["update_interval"]) == 0 and len(local_jacobians) >= 2:
                J = np.vstack(local_jacobians[-int(base["identifier"]["window_size"]) :])
                singular = np.linalg.svd(J, compute_uv=False)
                rank = int(np.linalg.matrix_rank(J))
                condition_number = float(singular[0] / singular[-1]) if singular[-1] > 0 else np.inf
                information = J.T @ J + regularization * np.eye(3)
                H = np.vstack(local_affine_regressors[-int(base["identifier"]["window_size"]) :])
                affine_singular = np.linalg.svd(H, compute_uv=False)
                affine_condition = float(affine_singular[0] / affine_singular[-1]) if affine_singular[-1] > 0 else np.inf
                windows.append(
                    {
                        "condition": condition,
                        "seed": seed,
                        "step": step,
                        "rank": rank,
                        "singular_values": singular,
                        "jacobian_condition": condition_number,
                        "information_condition": float(np.linalg.cond(information)),
                        "correlation": column_correlation(J),
                        "column_norms": np.linalg.norm(J, axis=0),
                        "affine_rank": int(np.linalg.matrix_rank(H)),
                        "affine_singular_values": affine_singular,
                        "affine_condition": affine_condition,
                        "affine_correlation": column_correlation(H),
                    }
                )
    sensitivity_summary = aggregate_sensitivity(records)
    conditioning_summary = aggregate_conditioning(windows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "sensitivity_summary.csv", sensitivity_summary)
    write_csv(OUTPUT / "conditioning_summary.csv", conditioning_summary)
    save_figures(sensitivity_summary, conditioning_summary, records, OUTPUT)
    print(f"[stage10a] transitions={len(records)} windows={len(windows)}")
    print(f"[stage10a] sensitivity={OUTPUT / 'sensitivity_summary.csv'}")
    print(f"[stage10a] conditioning={OUTPUT / 'conditioning_summary.csv'}")


if __name__ == "__main__":
    main()
