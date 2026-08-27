"""Offline structured local-resolution audit around a saved MPC sequence."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N

from .mpc import HumanSpaceMPC


RELATIVE_COST_NEIGHBORHOODS = (0.0, 0.001, 0.0025, 0.005, 0.01, 0.02, 0.05, 0.10)


def _temporal_basis(horizon_steps: int) -> tuple[np.ndarray, tuple[str, ...]]:
    time = np.linspace(-1.0, 1.0, horizon_steps)
    raw = np.column_stack(
        [
            np.ones(horizon_steps),
            time,
            0.5 * (3.0 * time**2 - 1.0),
            0.5 * (5.0 * time**3 - 3.0 * time),
        ]
    )
    raw /= np.max(np.abs(raw), axis=0, keepdims=True)
    return raw, ("constant", "linear", "quadratic", "cubic")


def structured_perturbations(
    horizon_steps: int,
    local_envelope_nm: tuple[float, float],
) -> list[dict[str, Any]]:
    """Construct deterministic smooth perturbations inside a local box."""

    basis, basis_names = _temporal_basis(horizon_steps)
    envelope = np.asarray(local_envelope_nm, dtype=float)
    if np.any(envelope <= 0.0):
        raise ValueError("local perturbation envelope must be positive")
    directions: list[tuple[str, np.ndarray]] = []
    for order, basis_name in enumerate(basis_names):
        for joint, joint_name in enumerate(("hip", "knee")):
            direction = np.zeros((horizon_steps, 2))
            direction[:, joint] = basis[:, order] * envelope[joint]
            directions.append((f"{joint_name}_{basis_name}", direction))

    records: dict[bytes, dict[str, Any]] = {}

    def add(method: str, delta: np.ndarray, coefficients: dict[str, float]) -> None:
        perturbation = np.asarray(delta, dtype=float).copy()
        ratio = float(np.max(np.abs(perturbation) / envelope[np.newaxis, :]))
        if ratio > 1.0:
            perturbation /= ratio
        key = np.round(perturbation, decimals=12).tobytes()
        records.setdefault(
            key,
            {
                "method": method,
                "coefficients": coefficients,
                "delta_u_nm": perturbation,
                "maximum_abs_delta_per_joint_nm": np.max(
                    np.abs(perturbation), axis=0
                ).tolist(),
                "rms_delta_nm": float(np.sqrt(np.mean(perturbation**2))),
            },
        )

    add("registered_sequence", np.zeros((horizon_steps, 2)), {})
    sweep = np.linspace(-1.0, 1.0, 41)
    for name, direction in directions:
        for coefficient in sweep:
            add(
                "single_temporal_direction",
                coefficient * direction,
                {name: float(coefficient)},
            )

    pair_levels = (-1.0, -0.5, 0.0, 0.5, 1.0)
    selected_pairs: list[tuple[int, int]] = []
    # Cross-joint perturbations with identical temporal shape.
    for order in range(4):
        selected_pairs.append((2 * order, 2 * order + 1))
    # Adjacent temporal orders within each joint.
    for joint in range(2):
        for order in range(3):
            selected_pairs.append((2 * order + joint, 2 * (order + 1) + joint))
    for first, second in selected_pairs:
        first_name, first_direction = directions[first]
        second_name, second_direction = directions[second]
        for first_coefficient in pair_levels:
            for second_coefficient in pair_levels:
                add(
                    "paired_temporal_directions",
                    first_coefficient * first_direction
                    + second_coefficient * second_direction,
                    {
                        first_name: float(first_coefficient),
                        second_name: float(second_coefficient),
                    },
                )

    # Mixed half-envelope directions cover cross-order coupling without
    # becoming another high-dimensional random cloud.
    for first in range(len(directions)):
        for second in range(first + 1, len(directions)):
            for first_sign, second_sign in ((-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)):
                first_name, first_direction = directions[first]
                second_name, second_direction = directions[second]
                add(
                    "mixed_half_envelope_directions",
                    0.5 * first_sign * first_direction
                    + 0.5 * second_sign * second_direction,
                    {
                        first_name: 0.5 * first_sign,
                        second_name: 0.5 * second_sign,
                    },
                )
    return list(records.values())


def evaluate_local_sequence(
    controller: HumanSpaceMPC,
    *,
    state: np.ndarray,
    sequence: np.ndarray,
    previous_action: np.ndarray,
    q_ref: np.ndarray,
    dq_ref: np.ndarray,
    human: Any,
) -> dict[str, Any]:
    """Evaluate one sequence with the unchanged MPC model and constraints."""

    config = controller.config
    action = np.asarray(sequence, dtype=float)
    states = controller._rollout(np.asarray(state, dtype=float), action, human)[1:]
    q_scale = np.asarray(config.q_error_scale_rad)
    dq_scale = np.asarray(config.dq_error_scale_rad_s)
    action_scale = np.asarray(config.action_scale_nm)
    rate_scale = np.asarray(config.action_rate_scale_nm)
    q_cost = float(np.sum(((states[:, :2] - q_ref) / q_scale) ** 2))
    dq_cost = float(np.sum(((states[:, 2:] - dq_ref) / dq_scale) ** 2))
    action_cost = float(config.action_weight * np.sum((action / action_scale) ** 2))
    previous = np.vstack([np.asarray(previous_action), action[:-1]])
    action_slew_cost = float(
        config.action_rate_weight * np.sum(((action - previous) / rate_scale) ** 2)
    )
    allocations = [
        controller._allocate(item, predicted[:2], human)
        for item, predicted in zip(action, states, strict=True)
    ]
    force = np.asarray([item["force_norm_n"] for item in allocations], dtype=float)
    moment = np.asarray(
        [abs(float(np.asarray(item["sagittal_wrench"])[2])) for item in allocations]
    )
    surface = np.asarray(
        [item["cylindrical_surface_effort_n"] for item in allocations], dtype=float
    )
    wrenches = np.asarray([item["wrench_world"] for item in allocations], dtype=float)
    normalization_squared = config.interaction_force_normalization_n**2
    force_normalized = float(np.sum(force**2) / normalization_squared)
    surface_normalized = float(np.sum(surface**2) / normalization_squared)
    previous_wrench = np.asarray(
        controller._allocate(previous_action, np.asarray(state)[:2], human)[
            "wrench_world"
        ],
        dtype=float,
    )
    delta_wrench = np.diff(np.vstack([previous_wrench, wrenches]), axis=0)
    radius = controller.surface_model.config.radius_m
    slew_normalized = float(
        np.sum(delta_wrench[:, :3] ** 2)
        + np.sum(delta_wrench[:, 3:] ** 2) / radius**2
    ) / normalization_squared
    interaction_cost = float(
        config.resultant_force_weight * force_normalized
        + config.cylindrical_surface_effort_weight * surface_normalized
        + config.wrench_slew_weight * slew_normalized
    )
    tracking_cost = q_cost + dq_cost
    base_task_cost = tracking_cost + action_cost + action_slew_cost
    lower = states[:, :2] - np.asarray(human.q_min_rad)
    upper = np.asarray(human.q_max_rad) - states[:, :2]
    force_margin = CUFF_TRANSLATIONAL_FORCE_GATE_N - force
    minimum_margin = float(
        np.min(np.concatenate([lower.reshape(-1), upper.reshape(-1), force_margin]))
    )
    equality = np.asarray(
        [item.get("equality_residual_nm", 0.0) for item in allocations], dtype=float
    )
    return {
        "feasible": bool(minimum_margin >= -1e-9),
        "minimum_constraint_margin": minimum_margin,
        "tracking_cost": tracking_cost,
        "q_tracking_cost": q_cost,
        "dq_tracking_cost": dq_cost,
        "action_cost": action_cost,
        "action_slew_cost": action_slew_cost,
        "base_task_cost": base_task_cost,
        "interaction_cost": interaction_cost,
        "total_interaction_aware_cost": base_task_cost + interaction_cost,
        "resultant_force_n": {
            "peak": float(np.max(force)),
            "rms": float(np.sqrt(np.mean(force**2))),
        },
        "abs_sagittal_moment_nm": {
            "peak": float(np.max(moment)),
            "rms": float(np.sqrt(np.mean(moment**2))),
        },
        "cylindrical_surface_proxy_n": {
            "peak": float(np.max(surface)),
            "rms": float(np.sqrt(np.mean(surface**2))),
        },
        "interaction_components": {
            "resultant_force_cost": float(
                config.resultant_force_weight * force_normalized
            ),
            "cylindrical_surface_effort_cost": float(
                config.cylindrical_surface_effort_weight * surface_normalized
            ),
            "wrench_slew_cost": float(config.wrench_slew_weight * slew_normalized),
        },
        "maximum_allocation_equality_residual_nm": float(np.max(equality)),
    }


def _pareto_indices(records: list[dict[str, Any]]) -> list[int]:
    values = np.asarray(
        [
            [
                item["base_task_cost"],
                item["resultant_force_n"]["rms"],
                item["abs_sagittal_moment_nm"]["rms"],
                item["cylindrical_surface_proxy_n"]["rms"],
            ]
            for item in records
        ]
    )
    retained: list[int] = []
    for index, value in enumerate(values):
        dominated = np.any(
            np.all(values <= value + 1e-12, axis=1)
            & np.any(values < value - 1e-12, axis=1)
        )
        if not dominated:
            retained.append(index)
    return retained


def _compact(record: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: record[key]
        for key in (
            "method",
            "coefficients",
            "maximum_abs_delta_per_joint_nm",
            "rms_delta_nm",
            "feasible",
            "minimum_constraint_margin",
            "tracking_cost",
            "base_task_cost",
            "interaction_cost",
            "total_interaction_aware_cost",
            "resultant_force_n",
            "abs_sagittal_moment_nm",
            "cylindrical_surface_proxy_n",
        )
    }
    result["relative_change_vs_registered_sequence"] = {
        "tracking_cost": float(record["tracking_cost"] / baseline["tracking_cost"] - 1.0),
        "base_task_cost": float(record["base_task_cost"] / baseline["base_task_cost"] - 1.0),
        "interaction_cost": float(record["interaction_cost"] / baseline["interaction_cost"] - 1.0),
        "force_rms": float(
            record["resultant_force_n"]["rms"]
            / baseline["resultant_force_n"]["rms"]
            - 1.0
        ),
        "moment_rms": float(
            record["abs_sagittal_moment_nm"]["rms"]
            / baseline["abs_sagittal_moment_nm"]["rms"]
            - 1.0
        ),
        "surface_proxy_rms": float(
            record["cylindrical_surface_proxy_n"]["rms"]
            / baseline["cylindrical_surface_proxy_n"]["rms"]
            - 1.0
        ),
    }
    return result


def summarize_local_landscape(records: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(item for item in records if item["method"] == "registered_sequence")
    feasible = [item for item in records if item["feasible"]]
    neighborhoods: dict[str, Any] = {}
    for relative in RELATIVE_COST_NEIGHBORHOODS:
        allowed = baseline["base_task_cost"] * (1.0 + relative)
        local = [item for item in feasible if item["base_task_cost"] <= allowed + 1e-12]
        interaction_best = min(local, key=lambda item: item["interaction_cost"])
        surface_best = min(
            local, key=lambda item: item["cylindrical_surface_proxy_n"]["rms"]
        )
        neighborhoods[f"{100.0 * relative:.2f}_percent"] = {
            "relative_base_task_cost_neighborhood": relative,
            "candidate_count": len(local),
            "minimum_interaction_cost_candidate": _compact(
                interaction_best, baseline
            ),
            "minimum_surface_proxy_candidate": _compact(surface_best, baseline),
        }
    pareto = _pareto_indices(feasible)
    return {
        "candidate_count": len(records),
        "feasible_candidate_count": len(feasible),
        "baseline": _compact(baseline, baseline),
        "neighborhoods": neighborhoods,
        "pareto_candidate_count": len(pareto),
        "pareto_candidates": [_compact(feasible[index], baseline) for index in pareto],
        "minimum_constraint_margin": float(
            min(item["minimum_constraint_margin"] for item in feasible)
        ),
        "maximum_allocation_equality_residual_nm": float(
            max(item["maximum_allocation_equality_residual_nm"] for item in feasible)
        ),
    }
