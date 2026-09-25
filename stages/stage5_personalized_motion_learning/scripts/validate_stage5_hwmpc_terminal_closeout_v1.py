#!/usr/bin/env python3
"""Close out the opt-in dynamic HWMPC baseline with one terminal reserve change."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from export_stage5_hwmpc_state_feedback_dataset_v1 import export_dataset
from validate_stage5_hwmpc_matched_pacing_r_cost import _fixed_models
from validate_stage5_hwmpc_state_feedback_v1 import (
    _feedback_comparisons,
    _plot,
    _run_episode,
    _short_branch_checks,
)


SCHEMA = "stage5_hwmpc_terminal_closeout_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_terminal_closeout_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    planner = np.asarray(
        [
            decision["runtime_ms"]
            for case in cases
            for decision in case["controller"]["planner"]["decisions"]
        ],
        dtype=float,
    )
    execution_p95 = np.asarray(
        [case["five_ms_execution_runtime_ms"]["p95"] for case in cases], dtype=float
    )
    execution_max = np.asarray(
        [case["five_ms_execution_runtime_ms"]["maximum"] for case in cases],
        dtype=float,
    )
    return {
        "high_level_planner_ms": {
            "sample_count": int(len(planner)),
            "mean": float(np.mean(planner)),
            "p95": float(np.percentile(planner, 95)),
            "maximum": float(np.max(planner)),
        },
        "five_ms_execution_path_ms": {
            "episode_p95_min": float(np.min(execution_p95)),
            "episode_p95_max": float(np.max(execution_p95)),
            "maximum": float(np.max(execution_max)),
        },
    }


def _base_runtime(base: dict[str, Any]) -> dict[str, Any]:
    return _runtime_summary(list(base["episodes"]))


def _failure_reason(case: dict[str, Any]) -> str | None:
    termination = case["metrics"]["termination_reason"]
    if termination is not None:
        return str(termination)
    failed = [
        row["phase"]
        for row in case["controller"]["boundary_checks"]
        if not row["inside_existing_completion_criteria"]
    ]
    if failed:
        return "TERMINAL_COMPLETION_CRITERION_FAILED:" + ",".join(failed)
    return None


def _group_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episode_count": len(cases),
        "completed_count": sum(case["completed"] for case in cases),
        "completion_rate": float(np.mean([case["completed"] for case in cases])),
        "all_motion_and_execution_contracts_passed": all(
            case["motion_and_execution_contract_passed"] for case in cases
        ),
        "failure_causes": {
            case["episode"]["name"]: _failure_reason(case)
            for case in cases
            if not case["completed"]
        },
        "runtime": _runtime_summary(cases),
    }


def _coordination_coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    actions = [
        tuple(np.round(decision["executed_action_delta_q_rad"], 10))
        for case in cases
        for decision in case["controller"]["planner"]["decisions"]
    ]
    persistent = []
    for case in cases:
        decisions = case["controller"]["planner"]["decisions"]
        for left, right in zip(decisions, decisions[1:]):
            if (
                left["exploration_rank"] > 0
                and right["exploration_rank"] > 0
                and np.allclose(
                    left["executed_action_delta_q_rad"],
                    right["executed_action_delta_q_rad"],
                    atol=1.0e-10,
                    rtol=0.0,
                )
            ):
                persistent.append(case["episode"]["name"])
                break
    return {
        "distinct_direct_delta_q_action_count": len(set(actions)),
        "episodes_with_persistent_non_greedy_choice": sorted(set(persistent)),
        "fixed_r_or_path_template_used": False,
    }


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_terminal_closeout_v1":
        raise ValueError("unexpected terminal-closeout config schema")
    if config.get("status") != "FROZEN_AFTER_TC_C_DIAGNOSIS_BEFORE_FIX_VALIDATION":
        raise ValueError("terminal correction and validation set were not frozen")
    diagnosis = config["diagnosis"]
    base_config_path = Path(diagnosis["base_config"])
    base_result_path = Path(diagnosis["base_result"])
    if _sha256(base_config_path) != diagnosis["base_config_sha256"]:
        raise ValueError("frozen V1 base config hash changed")
    if _sha256(base_result_path) != diagnosis["base_result_sha256"]:
        raise ValueError("frozen V1 base result hash changed")
    base = json.loads(base_result_path.read_text(encoding="utf-8"))
    budget = config["bounded_test_budget"]
    fresh_specs = list(budget["fresh_validation_episodes"])
    if not 4 <= len(fresh_specs) <= int(budget["maximum_fresh_validation_episodes"]) <= 6:
        raise ValueError("fresh validation budget must remain between four and six")
    if {row["seed"] for row in fresh_specs} & {
        row["seed"] for row in budget["regression_episodes"]
    }:
        raise ValueError("fresh validation seeds overlap the regression set")

    truth_human, control_model, model_version = _fixed_models(config)
    branch_checks = _short_branch_checks(config, control_model)
    regression = [
        _run_episode(config, episode, truth_human, control_model, model_version)
        for episode in budget["regression_episodes"]
    ]
    fresh = [
        _run_episode(config, episode, truth_human, control_model, model_version)
        for episode in fresh_specs
    ]
    cases = regression + fresh
    regression_summary = _group_summary(regression)
    fresh_summary = _group_summary(fresh)
    coverage = _coordination_coverage(cases)
    all_safe = all(case["motion_and_execution_contract_passed"] for case in cases)
    original_failed_now_complete = bool(
        next(
            case
            for case in regression
            if case["episode"]["name"] == diagnosis["failed_episode"]
        )["completed"]
    )
    original_successes_preserved = all(
        case["completed"]
        for case in regression
        if case["episode"]["name"] != diagnosis["failed_episode"]
    )
    if (
        original_failed_now_complete
        and original_successes_preserved
        and fresh_summary["completed_count"] == fresh_summary["episode_count"]
        and all_safe
        and coverage["distinct_direct_delta_q_action_count"] >= 3
    ):
        conclusion = "TB-A — DYNAMIC WAYPOINT BASELINE CLOSED OUT FOR LEARNING-DATA GENERATION"
    elif original_failed_now_complete or regression_summary["completed_count"] > 5:
        conclusion = "TB-B — TERMINAL COMPLETION IMPROVED BUT BASELINE STILL NOT RELIABLE"
    else:
        conclusion = "TB-C — CURRENT STATE-FEEDBACK ACTION SPACE / TIMING CONTRACT NEEDS REDESIGN"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "terminal_closeout_paths_and_decisions.png"
    _plot(cases, plot_path)
    result = {
        "schema": SCHEMA,
        "evidence_category": config["evidence_category"],
        "conclusion": conclusion,
        "diagnosis": config["diagnosis"],
        "single_correction": config["single_correction"],
        "config": config,
        "fixed_control_human_model_version": model_version,
        "before_fix_runtime": _base_runtime(base),
        "after_fix_runtime": _runtime_summary(cases),
        "timing_semantics": config["timing_contract"],
        "short_branch_checks": branch_checks,
        "regression_summary": regression_summary,
        "fresh_validation_summary": fresh_summary,
        "original_failed_seed_now_completes": original_failed_now_complete,
        "original_five_successes_remain_successful": original_successes_preserved,
        "coordination_coverage": coverage,
        "feedback_dependence_comparisons": _feedback_comparisons(cases),
        "episodes": cases,
        "all_existing_motion_and_execution_contracts_passed": all_safe,
        "plot": str(plot_path),
        "scope_invariants": config["scope"],
        "limitations": [
            "bounded deterministic MuJoCo engineering evidence only",
            "synchronous simulation pauses physical time during high-level planning",
            "high-level wall-clock latency is not represented as plant delay",
            "provisional Stage-5 cuff/interface and CR12 actuator semantics",
            "no hardware realtime or formal safety claim",
        ],
    }
    result_path = output_dir / "terminal_closeout_validation.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    dataset_summary = export_dataset(
        result_path, output_dir / "learning_transitions_v1.jsonl"
    )
    print(
        json.dumps(
            {
                "conclusion": conclusion,
                "regression_summary": regression_summary,
                "fresh_validation_summary": fresh_summary,
                "original_failed_seed_now_completes": original_failed_now_complete,
                "original_five_successes_remain_successful": original_successes_preserved,
                "all_safe": all_safe,
                "coordination_coverage": coverage,
                "dataset_summary": dataset_summary,
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.config, arguments.output_dir)


if __name__ == "__main__":
    main()
