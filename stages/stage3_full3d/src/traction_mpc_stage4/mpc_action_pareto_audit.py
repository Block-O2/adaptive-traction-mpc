"""Local Pareto summaries for audit-only MPC candidate captures."""

from __future__ import annotations

from typing import Any

import numpy as np


TRACKING_RELATIVE_BANDS = (0.01, 0.02, 0.05, 0.10)


def _metric(record: dict[str, Any], name: str) -> float:
    if name == "surface":
        return float(record["predicted_cylindrical_surface_proxy_n"]["rms"])
    if name == "force":
        return float(record["predicted_resultant_force_n"]["rms"])
    if name == "moment":
        return float(record["predicted_abs_sagittal_moment_nm"]["rms"])
    return float(record[name])


def _identity(record: dict[str, Any]) -> dict[str, int]:
    return {
        "iteration": int(record["iteration"]),
        "candidate_index": int(record["candidate_index"]),
    }


def compact_candidate(record: dict[str, Any]) -> dict[str, Any]:
    """Retain the fields needed to interpret a representative candidate."""

    return {
        **_identity(record),
        "first_generalized_torque_nm": record["first_generalized_torque_nm"],
        "tracking_cost": float(record["tracking_cost"]),
        "base_task_objective": float(record["base_task_objective"]),
        "registered_interaction_cost": float(record["registered_interaction_cost"]),
        "registered_interaction_total_objective": float(
            record["registered_interaction_total_objective"]
        ),
        "predicted_resultant_force_n": record["predicted_resultant_force_n"],
        "predicted_abs_sagittal_moment_nm": record[
            "predicted_abs_sagittal_moment_nm"
        ],
        "predicted_cylindrical_surface_proxy_n": record[
            "predicted_cylindrical_surface_proxy_n"
        ],
        "minimum_constraint_margin": float(record["minimum_constraint_margin"]),
    }


def pareto_indices(records: list[dict[str, Any]]) -> list[int]:
    """Return non-dominated indices in tracking/surface/force/moment space."""

    values = np.asarray(
        [
            [
                _metric(record, "tracking_cost"),
                _metric(record, "surface"),
                _metric(record, "force"),
                _metric(record, "moment"),
            ]
            for record in records
        ]
    )
    retained: list[int] = []
    for index, value in enumerate(values):
        weakly_better = np.all(values <= value + 1e-12, axis=1)
        strictly_better = np.any(values < value - 1e-12, axis=1)
        dominated = bool(np.any(weakly_better & strictly_better))
        if not dominated:
            retained.append(index)
    return retained


def _relative_reduction(reference: float, candidate: float) -> float:
    return float((reference - candidate) / max(abs(reference), 1e-12))


def summarize_candidate_call(
    capture: dict[str, Any],
    *,
    reference_phase_s: float,
    label: str,
) -> dict[str, Any]:
    """Summarize one sampled CEM call without introducing a decision threshold."""

    feasible = [item for item in capture["candidates"] if item["feasible"]]
    if not feasible:
        raise RuntimeError("representative CEM call has no feasible candidates")
    tracking_best = min(feasible, key=lambda item: item["tracking_cost"])
    base_best = min(feasible, key=lambda item: item["base_task_objective"])
    registered_best = min(
        feasible, key=lambda item: item["registered_interaction_total_objective"]
    )
    actual_best = min(feasible, key=lambda item: item["actual_total_objective"])
    pareto = pareto_indices(feasible)

    bands: dict[str, Any] = {}
    tracking_minimum = float(tracking_best["tracking_cost"])
    for relative_band in TRACKING_RELATIVE_BANDS:
        allowed = tracking_minimum * (1.0 + relative_band)
        near = [item for item in feasible if item["tracking_cost"] <= allowed + 1e-12]
        metric_best = {
            name: min(near, key=lambda item, name=name: _metric(item, name))
            for name in ("surface", "force", "moment")
        }
        joint_scores = [
            min(
                _relative_reduction(_metric(tracking_best, name), _metric(item, name))
                for name in ("surface", "force", "moment")
            )
            for item in near
        ]
        joint_best = near[int(np.argmax(joint_scores))]
        bands[f"{int(round(100 * relative_band))}_percent"] = {
            "candidate_count": len(near),
            "minimum_surface_candidate": compact_candidate(metric_best["surface"]),
            "minimum_force_candidate": compact_candidate(metric_best["force"]),
            "minimum_moment_candidate": compact_candidate(metric_best["moment"]),
            "best_joint_interaction_candidate": compact_candidate(joint_best),
            "reductions_vs_tracking_best": {
                name: _relative_reduction(
                    _metric(tracking_best, name), _metric(joint_best, name)
                )
                for name in ("surface", "force", "moment")
            },
            "surface_best_reduction_vs_tracking_best": _relative_reduction(
                _metric(tracking_best, "surface"),
                _metric(metric_best["surface"], "surface"),
            ),
        }

    base_order = sorted(feasible, key=lambda item: item["base_task_objective"])
    registered_order = sorted(
        feasible, key=lambda item: item["registered_interaction_total_objective"]
    )
    registered_identity = _identity(registered_best)
    base_identity = _identity(base_best)

    def rank_of(order: list[dict[str, Any]], identity: dict[str, int]) -> int:
        return next(
            index + 1
            for index, item in enumerate(order)
            if _identity(item) == identity
        )

    interaction = np.asarray(
        [item["registered_interaction_cost"] for item in feasible], dtype=float
    )
    task = np.asarray([item["base_task_objective"] for item in feasible], dtype=float)
    return {
        "label": label,
        "solve_index": int(capture["solve_index"]),
        "wall_time_s": float(capture["wall_time_s"]),
        "reference_phase_s": float(reference_phase_s),
        "sampled_candidate_count": len(capture["candidates"]),
        "feasible_candidate_count": len(feasible),
        "pareto_candidate_count": len(pareto),
        "pareto_candidates": [compact_candidate(feasible[index]) for index in pareto],
        "tracking_best": compact_candidate(tracking_best),
        "base_task_best": compact_candidate(base_best),
        "registered_interaction_best": compact_candidate(registered_best),
        "actual_optimizer_best": compact_candidate(actual_best),
        "tracking_bands": bands,
        "ranking": {
            "registered_best_rank_under_base_task": rank_of(
                base_order, registered_identity
            ),
            "base_best_rank_under_registered_objective": rank_of(
                registered_order, base_identity
            ),
            "base_and_registered_select_same_candidate": (
                base_identity == registered_identity
            ),
        },
        "cost_scale": {
            "base_task_objective_minimum": float(np.min(task)),
            "base_task_objective_median": float(np.median(task)),
            "registered_interaction_cost_minimum": float(np.min(interaction)),
            "registered_interaction_cost_median": float(np.median(interaction)),
            "registered_interaction_over_base_task_at_base_best": float(
                base_best["registered_interaction_cost"]
                / max(base_best["base_task_objective"], 1e-12)
            ),
            "registered_interaction_cost_span_over_base_task_span": float(
                np.ptp(interaction) / max(np.ptp(task), 1e-12)
            ),
        },
    }


def aggregate_call_summaries(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate threshold sweeps while keeping all individual calls visible."""

    aggregate: dict[str, Any] = {
        "representative_call_count": len(calls),
        "base_and_registered_same_selection_count": sum(
            item["ranking"]["base_and_registered_select_same_candidate"]
            for item in calls
        ),
    }
    for band in ("1_percent", "2_percent", "5_percent", "10_percent"):
        joint_reductions = [
            item["tracking_bands"][band]["reductions_vs_tracking_best"]
            for item in calls
        ]
        surface_best = [
            item["tracking_bands"][band][
                "surface_best_reduction_vs_tracking_best"
            ]
            for item in calls
        ]
        aggregate[band] = {
            "calls_with_at_least_10_percent_surface_reduction": int(
                np.count_nonzero(np.asarray(surface_best) >= 0.10)
            ),
            "calls_with_at_least_10_percent_joint_force_moment_surface_reduction": int(
                np.count_nonzero(
                    [
                        min(item.values()) >= 0.10
                        for item in joint_reductions
                    ]
                )
            ),
            "median_best_surface_reduction": float(np.median(surface_best)),
            "median_best_joint_minimum_reduction": float(
                np.median([min(item.values()) for item in joint_reductions])
            ),
        }
    return aggregate
