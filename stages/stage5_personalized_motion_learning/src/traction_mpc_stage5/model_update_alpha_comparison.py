"""Frozen contract helpers for the Stage-5 model-update-alpha comparison.

This module contains configuration and audit logic only.  It does not execute
MuJoCo episodes and plant truth never enters an online Human-ID decision.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import STAGE5_ROOT
from .human_identification_reduced import (
    ReducedScaleIdentifierConfig,
    Stage5ReducedHumanIDConfig,
)
from .progressive_personalization import FROZEN_THETA_1, LONGITUDINAL_CEM_SEEDS


ALPHA_COMPARISON_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_model_update_alpha_comparison_v1.json"
)
PP2_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_progressive_personalization_longitudinal_v1.json"
)
PP2_RESULT_PATH = (
    STAGE5_ROOT
    / "results"
    / "progressive_personalization_longitudinal_v1_attempt_01"
    / "progressive_personalization_results.json"
)
NATIVE_SUMMARY_PATH = STAGE5_ROOT / "docs" / "NATIVE_PREFIX_RUNTIME_V1_SUMMARY.json"

ARM_ALPHAS = {"alpha_0p10": 0.10, "alpha_0p25": 0.25}
FROZEN_PP2_REP5_LOSS_NMS2 = 0.00021518124214580563


def load_contract(path: Path = ALPHA_COMPARISON_CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_model_update_alpha_comparison_v1":
        raise ValueError("unexpected model-update-alpha comparison schema")
    if payload.get("status") != "PREREGISTERED_FORMAL_EXECUTION_AUTHORIZED":
        raise ValueError("alpha comparison must remain preregistered before execution")
    if payload.get("only_scientific_variable") != "model_update_alpha":
        raise ValueError("model_update_alpha must be the only scientific variable")
    observed = {
        name: float(values["model_update_alpha"])
        for name, values in payload["arms"].items()
    }
    if observed != ARM_ALPHAS:
        raise ValueError("alpha comparison arms changed")
    repetitions = payload["repetitions"]
    if repetitions["maximum_per_arm"] != 5:
        raise ValueError("alpha comparison is frozen at five repetitions")
    if tuple(repetitions["matched_cem_seeds"]) != LONGITUDINAL_CEM_SEEDS:
        raise ValueError("matched CEM seed schedule changed")
    if not np.array_equal(payload["initial_active_model"]["scales"], FROZEN_THETA_1):
        raise ValueError("alpha comparison must start from frozen theta_1")
    controller = payload["controller"]
    if controller["gamma"] != 0.5 or controller["gamma_dynamic"]:
        raise ValueError("alpha comparison requires fixed gamma=0.5")
    if controller["prefix_backend"] != "native":
        raise ValueError("alpha comparison requires the explicit native prefix backend")
    if controller["prefix_times_ms"] != [5, 10, 15, 20]:
        raise ValueError("registered prefix times changed")
    identifier = payload["human_identification"]
    if (
        identifier["lower_scales"] != [0.5, 0.5, 0.5]
        or identifier["upper_scales"] != [1.5, 1.5, 1.5]
        or identifier["maximum_per_scale_step"] != 0.03
        or identifier["maximum_step_fraction_of_span"] != 0.03
        or identifier["regularization_weight"] != 1.0e-3
    ):
        raise ValueError("frozen Human-ID bounds/cap/regularization changed")
    endpoint = float(payload["frozen_primary_endpoint"]["mean_squared_loss_nms2"])
    if endpoint != FROZEN_PP2_REP5_LOSS_NMS2:
        raise ValueError("frozen PP2-A endpoint changed")
    return payload


def human_id_config_for_alpha(
    model_update_alpha: float,
    *,
    base: Stage5ReducedHumanIDConfig = Stage5ReducedHumanIDConfig(),
) -> Stage5ReducedHumanIDConfig:
    """Change only the bounded model-update interpolation fraction."""

    alpha = float(model_update_alpha)
    if alpha not in ARM_ALPHAS.values():
        raise ValueError("only preregistered model_update_alpha values are allowed")
    identifier = replace(base.identifier, smoothing_alpha=alpha)
    return replace(base, identifier=identifier)


def bounded_update_diagnostics(
    predecessor: Any,
    candidate: Any,
    *,
    model_update_alpha: float,
    maximum_per_scale_step: float = 0.03,
    lower: float = 0.5,
    upper: float = 1.5,
) -> dict[str, Any]:
    """Return raw, requested, limited, and bound-clipped update components."""

    old = np.asarray(predecessor, dtype=float)
    proposed = np.asarray(candidate, dtype=float)
    if old.shape != (3,) or proposed.shape != (3,):
        raise ValueError("predecessor and candidate must be three-scale vectors")
    if not np.all(np.isfinite([*old, *proposed])):
        raise ValueError("predecessor and candidate must be finite")
    raw = proposed - old
    requested = float(model_update_alpha) * raw
    step_limited = np.clip(
        requested, -float(maximum_per_scale_step), float(maximum_per_scale_step)
    )
    successor = np.clip(old + step_limited, float(lower), float(upper))
    applied = successor - old
    cap_active = np.abs(requested) > float(maximum_per_scale_step) + 1.0e-15
    parameter_bound_active = ~np.isclose(
        old + step_limited, successor, atol=1.0e-15, rtol=0.0
    )
    larger_alpha_same_successor = np.zeros(3, dtype=bool)
    for index in range(3):
        if cap_active[index] and not parameter_bound_active[index]:
            larger_alpha_same_successor[index] = True
        elif parameter_bound_active[index]:
            larger_alpha_same_successor[index] = True
    return {
        "raw_candidate_displacement": raw.tolist(),
        "requested_smoothed_displacement": requested.tolist(),
        "actual_limited_displacement": applied.tolist(),
        "successor": successor.tolist(),
        "maximum_per_scale_step": float(maximum_per_scale_step),
        "step_cap_active": cap_active.tolist(),
        "parameter_bound_active": parameter_bound_active.tolist(),
        "larger_alpha_would_produce_same_component": (
            larger_alpha_same_successor.tolist()
        ),
    }


def baseline_reuse_audit(
    baseline_result_path: Path = PP2_RESULT_PATH,
    *,
    contract_path: Path = ALPHA_COMPARISON_CONFIG_PATH,
    pp2_config_path: Path = PP2_CONFIG_PATH,
    native_summary_path: Path = NATIVE_SUMMARY_PATH,
) -> dict[str, Any]:
    """Check the saved PP2-A progressive arm against the new frozen contract."""

    contract = load_contract(contract_path)
    pp2_config = json.loads(Path(pp2_config_path).read_text(encoding="utf-8"))
    native = json.loads(Path(native_summary_path).read_text(encoding="utf-8"))
    result_path = Path(baseline_result_path)
    if not result_path.exists():
        return {
            "eligible": False,
            "reason": "saved PP2-A result artifact is unavailable",
            "checks": {},
        }
    baseline = json.loads(result_path.read_text(encoding="utf-8"))
    progressive = baseline.get("arms", {}).get("progressive", [])
    observed_losses = [
        row["prediction"]["active_model"]["ALL_PHASES"].get(
            "mean_squared_loss_nms2"
        )
        for row in progressive
    ]
    observed_seeds = [int(row["cem_seed"]) for row in progressive]
    observed_starts = [row["active_theta"] for row in progressive[:1]]
    old_id = pp2_config["human_identification"]
    new_id = contract["human_identification"]
    old_controller = pp2_config["controller"]
    new_controller = contract["controller"]
    checks = {
        "pp2_decision_is_PP2_A": baseline.get("decision", {}).get("code") == "PP2-A",
        "five_progressive_repetitions": len(progressive) == 5,
        "same_theta_1_start": bool(observed_starts)
        and np.array_equal(observed_starts[0], FROZEN_THETA_1),
        "same_truth_condition": baseline.get("truth_condition_evaluation_only")
        == [1.0, 1.0, 1.2],
        "truth_excluded_online": baseline.get("truth_available_to_online_authority")
        is False,
        "same_seed_schedule": tuple(observed_seeds) == LONGITUDINAL_CEM_SEEDS,
        "same_fixed_gamma": baseline.get("gamma_fixed") == 0.5
        and old_controller["gamma"] == new_controller["gamma"] == 0.5,
        "same_task_and_planning_contract": all(
            old_controller[key] == new_controller[key]
            for key in (
                "base_planning_joint_velocity_ceiling_deg_s",
                "planning_physical_force_ceiling_n",
                "maximum_duration_s",
                "terminal_value",
            )
        ),
        "same_parameterization_bounds_cap_regularization": (
            old_id["parameterization"] == new_id["parameterization"]
            and old_id["lower_scales"] == new_id["lower_scales"]
            and old_id["upper_scales"] == new_id["upper_scales"]
            and old_id["maximum_step_fraction_of_span"]
            == new_id["maximum_step_fraction_of_span"]
            and old_id["regularization_weight"] == new_id["regularization_weight"]
        ),
        "arm_A_alpha_is_0p10": old_id["smoothing_alpha"]
        == ARM_ALPHAS["alpha_0p10"],
        "acceleration_monitor_unchanged": baseline.get(
            "acceleration_monitor_changed"
        )
        is False,
        "fixed_nominal_interface": baseline.get("interface_identification_active")
        is False,
        "native_backend_equivalence_proven": native.get("decision") == "NAT-A"
        and native.get("equivalence", {}).get("selected_action_exact") is True
        and native.get("equivalence", {}).get("candidate_feasibility_masks_exact")
        is True
        and native.get("episode_replay", {}).get("trace_equivalent") is True,
        "frozen_endpoint_exact": len(observed_losses) == 5
        and observed_losses[-1] == FROZEN_PP2_REP5_LOSS_NMS2,
    }
    return {
        "eligible": all(checks.values()),
        "reason": (
            "saved PP2-A alpha=0.10 progressive arm is an exact reusable baseline"
            if all(checks.values())
            else "one or more frozen semantic checks failed"
        ),
        "checks": checks,
        "baseline_result_path": str(result_path),
        "baseline_losses_nms2": observed_losses,
        "baseline_active_thetas": [row["active_theta"] for row in progressive],
        "native_backend_difference": (
            "allowed only through the NAT-A exact-decision/trace equivalence evidence"
        ),
    }


def config_equivalence_except_alpha() -> dict[str, Any]:
    """Expose the exact two-arm config difference for regression tests/reports."""

    arm_a = human_id_config_for_alpha(0.10)
    arm_b = human_id_config_for_alpha(0.25)
    a = arm_a.identifier
    b = arm_b.identifier
    fields = tuple(ReducedScaleIdentifierConfig.__dataclass_fields__)
    changed = [name for name in fields if getattr(a, name) != getattr(b, name)]
    return {
        "changed_identifier_fields": changed,
        "trust_configs_equal": arm_a.trust == arm_b.trust,
        "service_fields_equal_except_identifier": replace(
            arm_a, identifier=b
        )
        == arm_b,
    }
