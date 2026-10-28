"""Frozen contract and reuse audit for the Stage-5 max-step comparison."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import STAGE5_ROOT
from .human_identification_reduced import Stage5ReducedHumanIDConfig
from .model_update_alpha_comparison import (
    FROZEN_PP2_REP5_LOSS_NMS2,
    human_id_config_for_alpha,
)
from .progressive_personalization import FROZEN_THETA_1, LONGITUDINAL_CEM_SEEDS


MAX_STEP_COMPARISON_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_model_update_max_step_comparison_v1.json"
)
ALPHA_FORMAL_RESULT_PATH = (
    STAGE5_ROOT
    / "results"
    / "model_update_alpha_comparison_v1_formal_attempt_01"
    / "model_update_alpha_comparison_results.json"
)
MAX_STEP_ARMS = {"step_0p03": 0.03, "step_0p04": 0.04, "step_0p05": 0.05}
FIXED_MODEL_UPDATE_ALPHA = 0.25


def load_max_step_contract(
    path: Path = MAX_STEP_COMPARISON_CONFIG_PATH,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_model_update_max_step_comparison_v1":
        raise ValueError("unexpected max-step comparison schema")
    if payload.get("status") != "PREREGISTERED_FORMAL_EXECUTION_AUTHORIZED":
        raise ValueError("max-step comparison is not authorized under its contract")
    if payload.get("only_scientific_variable") != "maximum_per_scale_step":
        raise ValueError("maximum_per_scale_step must be the only variable")
    if float(payload["fixed_model_update_alpha"]) != FIXED_MODEL_UPDATE_ALPHA:
        raise ValueError("model_update_alpha must remain exactly 0.25")
    observed = {
        name: float(arm["maximum_per_scale_step"])
        for name, arm in payload["arms"].items()
    }
    if observed != MAX_STEP_ARMS:
        raise ValueError("max-step arms changed")
    repetitions = payload["repetitions"]
    if repetitions["maximum_per_arm"] != 5:
        raise ValueError("max-step comparison requires five repetitions")
    if tuple(repetitions["matched_cem_seeds"]) != LONGITUDINAL_CEM_SEEDS:
        raise ValueError("matched seed schedule changed")
    if not np.array_equal(payload["initial_active_model"]["scales"], FROZEN_THETA_1):
        raise ValueError("max-step comparison must start at frozen theta_1")
    controller = payload["controller"]
    if controller["gamma"] != 0.5 or controller["gamma_dynamic"]:
        raise ValueError("max-step comparison requires fixed gamma=0.5")
    if controller["prefix_backend"] != "native":
        raise ValueError("max-step comparison requires native prefix backend")
    if controller["prefix_times_ms"] != [5, 10, 15, 20]:
        raise ValueError("registered prefix times changed")
    if (
        payload["human_identification"]["regularization_weight"] != 1.0e-3
        or payload["frozen_primary_endpoint"]["mean_squared_loss_nms2"]
        != FROZEN_PP2_REP5_LOSS_NMS2
    ):
        raise ValueError("Human-ID regularization or frozen endpoint changed")
    return payload


def human_id_config_for_max_step(
    maximum_per_scale_step: float,
    *,
    base: Stage5ReducedHumanIDConfig | None = None,
) -> Stage5ReducedHumanIDConfig:
    """Change only the maximum bounded step at fixed alpha=0.25."""

    step = float(maximum_per_scale_step)
    if step not in MAX_STEP_ARMS.values():
        raise ValueError("only preregistered maximum step values are allowed")
    alpha_config = (
        human_id_config_for_alpha(FIXED_MODEL_UPDATE_ALPHA)
        if base is None
        else replace(
            base,
            identifier=replace(
                base.identifier, smoothing_alpha=FIXED_MODEL_UPDATE_ALPHA
            ),
        )
    )
    return replace(
        alpha_config,
        identifier=replace(
            alpha_config.identifier,
            maximum_update_fraction_of_span=step,
        ),
    )


def step_config_equivalence() -> dict[str, Any]:
    configs = {
        name: human_id_config_for_max_step(step)
        for name, step in MAX_STEP_ARMS.items()
    }
    identifiers = {name: value.identifier for name, value in configs.items()}
    fields = tuple(next(iter(identifiers.values())).__dataclass_fields__)
    changed = [
        field
        for field in fields
        if len({getattr(value, field) for value in identifiers.values()}) > 1
    ]
    return {
        "changed_identifier_fields": changed,
        "all_smoothing_alpha_0p25": all(
            value.smoothing_alpha == FIXED_MODEL_UPDATE_ALPHA
            for value in identifiers.values()
        ),
        "trust_configs_equal": len({value.trust for value in configs.values()}) == 1,
    }


def baseline_step_0p03_reuse_audit(
    result_path: Path = ALPHA_FORMAL_RESULT_PATH,
    *,
    contract_path: Path = MAX_STEP_COMPARISON_CONFIG_PATH,
) -> dict[str, Any]:
    """Verify the formal alpha=0.25/step=0.03 arm is reusable as Arm A."""

    contract = load_max_step_contract(contract_path)
    path = Path(result_path)
    if not path.exists():
        return {
            "eligible": False,
            "reason": "formal alpha-comparison result is unavailable",
            "checks": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    arm = payload.get("arms", {}).get("alpha_0p25", {})
    rows = arm.get("rows", [])
    transitions = arm.get("transition_rows", [])
    checks = {
        "formal_both_arms_fresh": payload.get("both_arms_run_fresh") is True,
        "alpha_is_0p25": float(arm.get("model_update_alpha", -1.0))
        == FIXED_MODEL_UPDATE_ALPHA,
        "five_repetitions": len(rows) == 5,
        "same_seeds": tuple(int(row["cem_seed"]) for row in rows)
        == LONGITUDINAL_CEM_SEEDS,
        "same_theta_1_start": bool(rows)
        and np.array_equal(rows[0]["active_theta"], FROZEN_THETA_1),
        "step_is_0p03": len(transitions) == 5
        and all(
            item["update"] is not None
            and float(item["update"]["maximum_per_scale_step"])
            == MAX_STEP_ARMS["step_0p03"]
            for item in transitions
        ),
        "same_truth_boundary": payload.get("truth_available_to_online_authority")
        is False,
        "same_gamma": payload.get("gamma_fixed") == 0.5,
        "same_native_backend": payload.get("prefix_backend") == "native",
        "same_acceleration_monitor": payload.get("acceleration_monitor_changed")
        is False,
        "all_complete": all(
            row["control"]["task_status"] == "COMPLETE" for row in rows
        ),
        "no_registered_safety_event": all(
            row["control"]["mpc_failure_count"] == 0
            and row["control"]["force_gate_event_count"] == 0
            and row["control"]["brake_event_count"] == 0
            and row["control"]["maximum_safety_filter_intervention_coordinate_norm"]
            == 0.0
            and not row["control"]["mujoco_warning_counts"]
            for row in rows
        ),
        "same_controller_contract": contract["controller"]["gamma"] == 0.5
        and contract["controller"]["prefix_backend"] == "native",
    }
    return {
        "eligible": all(checks.values()),
        "reason": (
            "formal alpha=0.25 step=0.03 arm is an exact reusable Arm-A baseline"
            if all(checks.values())
            else "one or more Arm-A reuse checks failed"
        ),
        "checks": checks,
        "result_path": str(path),
        "active_thetas": [row["active_theta"] for row in rows],
        "prediction_losses_nms2": [
            row["prediction"]["active_model"]["ALL_PHASES"].get(
                "mean_squared_loss_nms2"
            )
            for row in rows
        ],
    }
