#!/usr/bin/env python3
"""Audit or execute the preregistered Stage-5 alpha=0.10 vs 0.25 study.

The default mode is read-only and performs the PP2-A baseline-reuse audit.
The formal alpha=0.25 arm runs only with ``--execute-formal-arm-b``; repository
policy reserves that command for the user.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.model_update_alpha_comparison import (
    ALPHA_COMPARISON_CONFIG_PATH,
    ARM_ALPHAS,
    FROZEN_PP2_REP5_LOSS_NMS2,
    LONGITUDINAL_CEM_SEEDS,
    PP2_RESULT_PATH,
    baseline_reuse_audit,
    bounded_update_diagnostics,
    human_id_config_for_alpha,
    load_contract,
)
from traction_mpc_stage5.progressive_personalization import (
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
)

DEFAULT_OUTPUT = (
    STAGE5_ROOT / "results" / "model_update_alpha_comparison_v1_attempt_01"
)


def _strict_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _strict_jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _loss(row: dict[str, Any]) -> float | None:
    value = row["prediction"]["active_model"]["ALL_PHASES"].get(
        "mean_squared_loss_nms2"
    )
    return None if value is None else float(value)


def _transition_row(row: dict[str, Any]) -> dict[str, Any]:
    queued = row["authority_end"]["queued_update"]
    if queued is None:
        return {
            "repetition": int(row["repetition"]),
            "active_model_id": row["active_model_id"],
            "active_theta": row["active_theta"],
            "candidate_theta": None,
            "successor_theta": None,
            "update": None,
            "qualification_evidence": None,
            "post_update_evidence": row["authority_end"]["post_update_evidence"],
            "queued": False,
        }
    transition = queued["transition"]
    diagnostic = bounded_update_diagnostics(
        transition["predecessor_scales"],
        transition["candidate_scales"],
        model_update_alpha=float(transition["smoothing_alpha"]),
        maximum_per_scale_step=float(transition["maximum_step_per_parameter"][0]),
    )
    return {
        "repetition": int(row["repetition"]),
        "active_model_id": row["active_model_id"],
        "active_theta": row["active_theta"],
        "candidate_theta": transition["candidate_scales"],
        "successor_theta": transition["successor_scales"],
        "update": diagnostic,
        "qualification_evidence": {
            "evidence_id": queued["candidate_evidence_id"],
            "qualification_time_s": queued["qualification_time_s"],
            "predecessor_model_id": queued["predecessor_model_id"],
            "successor_model_id": queued["successor_model_id"],
        },
        "post_update_evidence": row["authority_end"]["post_update_evidence"],
        "queued": True,
    }


def _time_to_endpoint(rows: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed = 0.0
    for row in rows:
        elapsed += float(row["control"]["task_duration_s"])
        loss = _loss(row)
        if loss is not None and loss <= FROZEN_PP2_REP5_LOSS_NMS2:
            return {
                "reached": True,
                "repetition": int(row["repetition"]),
                "simulated_task_time_s": elapsed,
                "loss_nms2": loss,
            }
    return {
        "reached": False,
        "repetition": None,
        "simulated_task_time_s": elapsed,
        "loss_nms2": None if not rows else _loss(rows[-1]),
    }


def _comparison(
    arm_a_rows: list[dict[str, Any]],
    arm_b_rows: list[dict[str, Any]],
    evolution_b: dict[str, Any],
) -> dict[str, Any]:
    from run_stage5_progressive_personalization_longitudinal_v1 import (
        _episode_regression,
    )

    matched = []
    regression_reasons: list[list[str]] = []
    for arm_a, arm_b in zip(arm_a_rows, arm_b_rows, strict=False):
        reasons = _episode_regression(arm_a, arm_b)
        regression_reasons.append(reasons)
        matched.append(
            {
                "repetition": arm_b["repetition"],
                "seed": arm_b["cem_seed"],
                "alpha_0p10_loss_nms2": _loss(arm_a),
                "alpha_0p25_loss_nms2": _loss(arm_b),
                "alpha_0p25_minus_alpha_0p10_loss_nms2": (
                    None
                    if _loss(arm_a) is None or _loss(arm_b) is None
                    else _loss(arm_b) - _loss(arm_a)
                ),
                "alpha_0p10_status": arm_a["control"]["task_status"],
                "alpha_0p25_status": arm_b["control"]["task_status"],
                "closed_loop_regression_reasons": reasons,
                "alpha_0p10_duration_s": arm_a["control"]["task_duration_s"],
                "alpha_0p25_duration_s": arm_b["control"]["task_duration_s"],
                "alpha_0p10_force_integral_n_s": arm_a["control"][
                    "cumulative_physical_cuff_force_n_s"
                ],
                "alpha_0p25_force_integral_n_s": arm_b["control"][
                    "cumulative_physical_cuff_force_n_s"
                ],
            }
        )
    losses_b = [_loss(row) for row in arm_b_rows]
    applied_losses = [value for value in losses_b if value is not None]
    monotone_nonincreasing = all(
        later <= earlier + 1.0e-12
        for earlier, later in zip(applied_losses, applied_losses[1:])
    )
    negative = any(
        model["post_update_support"] == "negative"
        for model in evolution_b["models"]
    )
    oscillation = any(evolution_b["parameter_direction_oscillation"].values())
    regression = any(regression_reasons)
    all_complete = len(arm_b_rows) == 5 and all(
        row["control"]["task_status"] == "COMPLETE" for row in arm_b_rows
    )
    endpoint_a = _time_to_endpoint(arm_a_rows)
    endpoint_b = _time_to_endpoint(arm_b_rows)
    if negative or oscillation or regression or not monotone_nonincreasing:
        decision = "AS-C"
        label = "ALPHA 0.25 TOO AGGRESSIVE"
    elif (
        endpoint_b["reached"]
        and (
            int(endpoint_b["repetition"]) < int(endpoint_a["repetition"])
            or float(endpoint_b["simulated_task_time_s"])
            < float(endpoint_a["simulated_task_time_s"]) - 1.0e-12
        )
        and all_complete
    ):
        decision = "AS-A"
        label = "ALPHA 0.25 IMPROVES PERSONALIZATION SPEED"
    elif all_complete and not negative and not oscillation and not regression:
        decision = "AS-B"
        label = "ALPHA 0.25 ACCEPTABLE WITHOUT MATERIAL SPEED BENEFIT"
    else:
        decision = "AS-D"
        label = "RESULT INCONCLUSIVE"
    transitions = [_transition_row(row) for row in arm_b_rows]
    alpha_d_cap_count = sum(
        bool(item["update"]["step_cap_active"][2])
        for item in transitions
        if item["update"] is not None
    )
    qualified_transition_count = sum(
        item["update"] is not None for item in transitions
    )
    return {
        "matched_repetitions": matched,
        "endpoint": {
            "frozen_loss_nms2": FROZEN_PP2_REP5_LOSS_NMS2,
            "alpha_0p10": endpoint_a,
            "alpha_0p25": endpoint_b,
        },
        "alpha_0p25_transition_rows": transitions,
        "alpha_0p25_prediction_loss_monotone_nonincreasing": monotone_nonincreasing,
        "alpha_0p25_alpha_D_step_cap_binding_count": alpha_d_cap_count,
        "update_size_bottleneck_interpretation": (
            "0.03 step cap is the dominant early alpha_D update-size bottleneck"
            if qualified_transition_count > 0
            and alpha_d_cap_count * 2 >= qualified_transition_count
            else "model_update_alpha and cap effects remain transition-dependent"
        ),
        "decision": {"code": decision, "label": label},
    }


def _load_baseline_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload, payload["arms"]["progressive"]


def execute_formal_arm_b(output_dir: Path, baseline_path: Path) -> dict[str, Any]:
    """Execute only the new alpha=0.25 arm after the reuse audit passes."""

    from run_stage5_progressive_personalization_longitudinal_v1 import (
        _geometry,
        _parameter_evolution,
        _run_repetition,
    )

    contract = load_contract()
    audit = baseline_reuse_audit(baseline_path)
    if not audit["eligible"]:
        raise RuntimeError(f"Arm-A baseline reuse audit failed: {audit}")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline, arm_a_rows = _load_baseline_rows(baseline_path)
    alpha = ARM_ALPHAS["alpha_0p25"]
    session = ProgressiveLongitudinalSession(
        _geometry(),
        ProgressiveLongitudinalArm.PROGRESSIVE,
        session_id="alpha-comparison-v1-0p25",
        human_id_config=human_id_config_for_alpha(alpha),
    )
    rows: list[dict[str, Any]] = []
    session_time_s = 0.0
    reset_gap = float(
        contract["repetitions"]["physical_reset_gap_in_session_time_s"]
    )
    started = perf_counter()
    for repetition, seed in enumerate(LONGITUDINAL_CEM_SEEDS, start=1):
        row = _run_repetition(
            output_dir=output_dir,
            config=contract,
            session=session,
            repetition=repetition,
            seed=seed,
            session_time_s=session_time_s,
            prefix_backend="native",
        )
        rows.append(row)
        session_time_s += float(row["control"]["task_duration_s"]) + reset_gap
        print(
            json.dumps(
                {
                    "arm": "alpha_0p25",
                    "repetition": repetition,
                    "seed": seed,
                    "task_status": row["control"]["task_status"],
                    "active_theta": row["active_theta"],
                    "prediction_loss_nms2": _loss(row),
                    "queued": row["authority_end"]["queued_update"] is not None,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if row["control"]["task_status"] != "COMPLETE" or session.authority.progression_blocked:
            break
    evolution = _parameter_evolution(session)
    comparison = _comparison(arm_a_rows, rows, evolution)
    payload = _strict_jsonable(
        {
            "schema": "stage5_model_update_alpha_comparison_v1_results",
            "config_path": str(ALPHA_COMPARISON_CONFIG_PATH.relative_to(STAGE5_ROOT)),
            "formal_execution_requested_by_user": True,
            "only_scientific_variable": "model_update_alpha",
            "baseline_reuse_audit": audit,
            "arm_alpha_0p10": {
                "source": str(Path(baseline_path)),
                "reused_not_rerun": True,
                "decision": baseline["decision"],
                "repetition_count": len(arm_a_rows),
                "active_thetas": [row["active_theta"] for row in arm_a_rows],
                "prediction_losses_nms2": [_loss(row) for row in arm_a_rows],
            },
            "arm_alpha_0p25": {
                "model_update_alpha": alpha,
                "rows": rows,
                "parameter_evolution": evolution,
                "authority_summary": session.authority.summary(),
            },
            "comparison": comparison,
            "truth_available_to_online_authority": False,
            "gamma_fixed": 0.5,
            "prefix_backend": "native",
            "acceleration_monitor_changed": False,
            "total_new_arm_wall_time_s": perf_counter() - started,
        }
    )
    result_path = output_dir / "model_update_alpha_comparison_results.json"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["comparison"]["decision"], indent=2, sort_keys=True))
    return payload


def execute_formal_both_arms(output_dir: Path) -> dict[str, Any]:
    """Execute both preregistered arms fresh with matched seeds."""

    from run_stage5_progressive_personalization_longitudinal_v1 import (
        _geometry,
        _parameter_evolution,
        _run_repetition,
    )

    contract = load_contract()
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    sessions = {
        name: ProgressiveLongitudinalSession(
            _geometry(),
            ProgressiveLongitudinalArm.PROGRESSIVE,
            session_id=f"alpha-comparison-v1-{name}",
            human_id_config=human_id_config_for_alpha(alpha),
        )
        for name, alpha in ARM_ALPHAS.items()
    }
    rows_by_arm: dict[str, list[dict[str, Any]]] = {
        name: [] for name in ARM_ALPHAS
    }
    session_times = {name: 0.0 for name in ARM_ALPHAS}
    reset_gap = float(
        contract["repetitions"]["physical_reset_gap_in_session_time_s"]
    )
    started = perf_counter()
    for repetition, seed in enumerate(LONGITUDINAL_CEM_SEEDS, start=1):
        for arm_name in ARM_ALPHAS:
            session = sessions[arm_name]
            row = _run_repetition(
                output_dir=output_dir / arm_name,
                config=contract,
                session=session,
                repetition=repetition,
                seed=seed,
                session_time_s=session_times[arm_name],
                prefix_backend="native",
            )
            rows_by_arm[arm_name].append(row)
            session_times[arm_name] += (
                float(row["control"]["task_duration_s"]) + reset_gap
            )
            print(
                json.dumps(
                    {
                        "arm": arm_name,
                        "model_update_alpha": ARM_ALPHAS[arm_name],
                        "repetition": repetition,
                        "seed": seed,
                        "task_status": row["control"]["task_status"],
                        "active_theta": row["active_theta"],
                        "prediction_loss_nms2": _loss(row),
                        "post_update_support": row["authority_end"][
                            "post_update_support"
                        ],
                        "queued": row["authority_end"]["queued_update"]
                        is not None,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    evolution = {
        name: _parameter_evolution(session) for name, session in sessions.items()
    }
    comparison = _comparison(
        rows_by_arm["alpha_0p10"],
        rows_by_arm["alpha_0p25"],
        evolution["alpha_0p25"],
    )
    transitions = {
        name: [_transition_row(row) for row in rows]
        for name, rows in rows_by_arm.items()
    }
    qualified_b = sum(
        item["update"] is not None for item in transitions["alpha_0p25"]
    )
    alpha_d_cap_b = sum(
        bool(item["update"]["step_cap_active"][2])
        for item in transitions["alpha_0p25"]
        if item["update"] is not None
    )
    frequent_cap_binding = bool(
        qualified_b > 0 and alpha_d_cap_b * 2 >= qualified_b
    )
    comparison["cap_bottleneck_predeclared_rule"] = {
        "qualified_alpha_0p25_transitions": qualified_b,
        "alpha_D_cap_binding_count": alpha_d_cap_b,
        "frequent_binding": frequent_cap_binding,
        "rule": contract["cap_bottleneck_interpretation"][
            "frequent_binding_rule"
        ],
    }
    payload = _strict_jsonable(
        {
            "schema": "stage5_model_update_alpha_comparison_v1_results",
            "config_path": str(ALPHA_COMPARISON_CONFIG_PATH.relative_to(STAGE5_ROOT)),
            "formal_execution_explicitly_authorized_by_user": True,
            "both_arms_run_fresh": True,
            "only_scientific_variable": "model_update_alpha",
            "frozen_endpoint_nms2": FROZEN_PP2_REP5_LOSS_NMS2,
            "arms": {
                name: {
                    "model_update_alpha": ARM_ALPHAS[name],
                    "rows": rows_by_arm[name],
                    "parameter_evolution": evolution[name],
                    "transition_rows": transitions[name],
                    "authority_summary": sessions[name].authority.summary(),
                }
                for name in ARM_ALPHAS
            },
            "comparison": comparison,
            "truth_available_to_online_authority": False,
            "gamma_fixed": 0.5,
            "prefix_backend": "native",
            "acceleration_monitor_changed": False,
            "total_formal_wall_time_s": perf_counter() - started,
        }
    )
    result_path = output_dir / "model_update_alpha_comparison_results.json"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["comparison"]["decision"], indent=2, sort_keys=True))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=PP2_RESULT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--execute-formal-arm-b",
        action="store_true",
        help="run the preregistered alpha=0.25 arm; repository policy reserves this for the user",
    )
    parser.add_argument(
        "--execute-formal-both-arms",
        action="store_true",
        help="run both preregistered arms fresh with the matched seed schedule",
    )
    arguments = parser.parse_args()
    audit = baseline_reuse_audit(arguments.baseline)
    if arguments.execute_formal_arm_b and arguments.execute_formal_both_arms:
        parser.error("choose exactly one formal execution mode")
    if arguments.execute_formal_both_arms:
        execute_formal_both_arms(arguments.output_dir)
        return
    if not arguments.execute_formal_arm_b:
        print(json.dumps(_strict_jsonable(audit), indent=2, sort_keys=True))
        return
    execute_formal_arm_b(arguments.output_dir, arguments.baseline)


if __name__ == "__main__":
    main()
