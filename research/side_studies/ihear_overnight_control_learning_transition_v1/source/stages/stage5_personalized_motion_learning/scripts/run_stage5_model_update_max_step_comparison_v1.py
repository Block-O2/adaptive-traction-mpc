#!/usr/bin/env python3
"""Audit or execute the formal Stage-5 max-step comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.model_update_alpha_comparison import (
    FROZEN_PP2_REP5_LOSS_NMS2,
)
from traction_mpc_stage5.model_update_max_step_comparison import (
    ALPHA_FORMAL_RESULT_PATH,
    FIXED_MODEL_UPDATE_ALPHA,
    LONGITUDINAL_CEM_SEEDS,
    MAX_STEP_ARMS,
    MAX_STEP_COMPARISON_CONFIG_PATH,
    baseline_step_0p03_reuse_audit,
    human_id_config_for_max_step,
    load_max_step_contract,
)
from traction_mpc_stage5.progressive_personalization import (
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
)

from run_stage5_model_update_alpha_comparison_v1 import (
    _strict_jsonable,
    _time_to_endpoint,
    _transition_row,
)


DEFAULT_OUTPUT = (
    STAGE5_ROOT / "results" / "model_update_max_step_comparison_v1_formal_attempt_01"
)


def _loss(row: dict[str, Any]) -> float | None:
    value = row["prediction"]["active_model"]["ALL_PHASES"].get(
        "mean_squared_loss_nms2"
    )
    return None if value is None else float(value)


def _arm_diagnostics(
    *,
    name: str,
    rows: list[dict[str, Any]],
    evolution: dict[str, Any],
    transitions: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    from run_stage5_progressive_personalization_longitudinal_v1 import (
        _episode_regression,
    )

    losses = [_loss(row) for row in rows]
    finite_losses = [value for value in losses if value is not None]
    monotone = len(finite_losses) == len(rows) and all(
        later <= earlier + 1.0e-12
        for earlier, later in zip(finite_losses, finite_losses[1:])
    )
    negative = any(
        model["post_update_support"] == "negative"
        for model in evolution["models"]
    )
    oscillation = any(evolution["parameter_direction_oscillation"].values())
    regression_reasons = (
        [[] for _ in rows]
        if name == "step_0p03"
        else [
            _episode_regression(a, b)
            for a, b in zip(baseline_rows, rows, strict=True)
        ]
    )
    cap_counts = [0, 0, 0]
    qualified = 0
    for transition in transitions:
        update = transition["update"]
        if update is None:
            continue
        qualified += 1
        for index, active in enumerate(update["step_cap_active"]):
            cap_counts[index] += int(bool(active))
    all_complete = len(rows) == 5 and all(
        row["control"]["task_status"] == "COMPLETE" for row in rows
    )
    acceptable = bool(
        all_complete
        and not negative
        and not oscillation
        and monotone
        and not any(regression_reasons)
    )
    return {
        "prediction_losses_nms2": losses,
        "prediction_loss_monotone_nonincreasing": monotone,
        "endpoint": _time_to_endpoint(rows),
        "all_complete": all_complete,
        "negative_post_update_evidence": negative,
        "parameter_oscillation": oscillation,
        "closed_loop_regression_reasons_vs_step_0p03": regression_reasons,
        "qualified_transition_count": qualified,
        "step_cap_binding_count_M_K_D": cap_counts,
        "effectively_uncapped": qualified > 0 and not any(cap_counts),
        "acceptable": acceptable,
    }


def _material_benefit(
    smaller_rows: list[dict[str, Any]],
    smaller: dict[str, Any],
    larger_rows: list[dict[str, Any]],
    larger: dict[str, Any],
) -> dict[str, Any]:
    if not smaller["acceptable"] or not larger["acceptable"]:
        return {"material": False, "reason": "one arm is not acceptable"}
    small_endpoint = smaller["endpoint"]
    large_endpoint = larger["endpoint"]
    if not large_endpoint["reached"]:
        return {"material": False, "reason": "larger cap did not reach endpoint"}
    if not small_endpoint["reached"]:
        return {"material": True, "reason": "only larger cap reached endpoint"}
    if int(large_endpoint["repetition"]) < int(small_endpoint["repetition"]):
        return {"material": True, "reason": "fewer repetitions to endpoint"}
    if int(large_endpoint["repetition"]) > int(small_endpoint["repetition"]):
        return {"material": False, "reason": "more repetitions to endpoint"}
    repetition = int(large_endpoint["repetition"])
    small_loss = _loss(smaller_rows[repetition - 1])
    large_loss = _loss(larger_rows[repetition - 1])
    assert small_loss is not None and large_loss is not None
    relative_improvement = (small_loss - large_loss) / small_loss
    return {
        "material": relative_improvement >= 0.10,
        "reason": (
            "same endpoint repetition with at least 10 percent lower loss"
            if relative_improvement >= 0.10
            else "same endpoint repetition without 10 percent lower loss"
        ),
        "endpoint_repetition": repetition,
        "relative_loss_improvement": float(relative_improvement),
    }


def _decision(
    rows: dict[str, list[dict[str, Any]]],
    diagnostics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if any(len(rows[name]) != 5 for name in MAX_STEP_ARMS):
        return {"code": "INCONCLUSIVE", "label": "EVIDENCE IS INCONCLUSIVE"}
    b_vs_a = _material_benefit(
        rows["step_0p03"],
        diagnostics["step_0p03"],
        rows["step_0p04"],
        diagnostics["step_0p04"],
    )
    c_vs_b = _material_benefit(
        rows["step_0p04"],
        diagnostics["step_0p04"],
        rows["step_0p05"],
        diagnostics["step_0p05"],
    )
    c_vs_a = _material_benefit(
        rows["step_0p03"],
        diagnostics["step_0p03"],
        rows["step_0p05"],
        diagnostics["step_0p05"],
    )
    if c_vs_b["material"] and diagnostics["step_0p05"]["acceptable"]:
        code = "STEP_0P05_ADDITIONAL_JUSTIFIED_BENEFIT"
        label = "0.05 gives additional justified benefit"
    elif b_vs_a["material"] and diagnostics["step_0p04"]["acceptable"]:
        code = "STEP_0P04_BEST_SPEED_STABILITY_TRADEOFF"
        label = "0.04 gives the best speed/stability tradeoff"
    elif c_vs_a["material"] and diagnostics["step_0p05"]["acceptable"]:
        code = "STEP_0P05_ADDITIONAL_JUSTIFIED_BENEFIT"
        label = "0.05 gives additional justified benefit"
    elif all(diagnostics[name]["acceptable"] for name in MAX_STEP_ARMS):
        code = "STEP_0P03_REMAINS_PREFERABLE"
        label = "0.03 remains preferable"
    else:
        code = "INCONCLUSIVE"
        label = "evidence is inconclusive"
    return {
        "code": code,
        "label": label,
        "material_benefit": {
            "step_0p04_vs_0p03": b_vs_a,
            "step_0p05_vs_0p04": c_vs_b,
            "step_0p05_vs_0p03": c_vs_a,
        },
    }


def execute_formal_fresh_b_c(
    output_dir: Path,
    baseline_path: Path = ALPHA_FORMAL_RESULT_PATH,
) -> dict[str, Any]:
    """Reuse audited step=0.03 and freshly execute step=0.04/0.05."""

    from run_stage5_progressive_personalization_longitudinal_v1 import (
        _geometry,
        _parameter_evolution,
        _run_repetition,
    )

    contract = load_max_step_contract()
    audit = baseline_step_0p03_reuse_audit(baseline_path)
    if not audit["eligible"]:
        raise RuntimeError(f"step=0.03 reuse audit failed: {audit}")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_payload = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    baseline_arm = baseline_payload["arms"]["alpha_0p25"]
    rows_by_arm: dict[str, list[dict[str, Any]]] = {
        "step_0p03": baseline_arm["rows"],
        "step_0p04": [],
        "step_0p05": [],
    }
    sessions = {
        name: ProgressiveLongitudinalSession(
            _geometry(),
            ProgressiveLongitudinalArm.PROGRESSIVE,
            session_id=f"max-step-v1-{name}",
            human_id_config=human_id_config_for_max_step(MAX_STEP_ARMS[name]),
        )
        for name in ("step_0p04", "step_0p05")
    }
    session_times = {name: 0.0 for name in sessions}
    reset_gap = float(
        contract["repetitions"]["physical_reset_gap_in_session_time_s"]
    )
    started = perf_counter()
    for repetition, seed in enumerate(LONGITUDINAL_CEM_SEEDS, start=1):
        for name in ("step_0p04", "step_0p05"):
            session = sessions[name]
            row = _run_repetition(
                output_dir=output_dir / name,
                config=contract,
                session=session,
                repetition=repetition,
                seed=seed,
                session_time_s=session_times[name],
                prefix_backend="native",
            )
            rows_by_arm[name].append(row)
            session_times[name] += (
                float(row["control"]["task_duration_s"]) + reset_gap
            )
            print(
                json.dumps(
                    {
                        "arm": name,
                        "maximum_per_scale_step": MAX_STEP_ARMS[name],
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
        "step_0p03": baseline_arm["parameter_evolution"],
        **{
            name: _parameter_evolution(session) for name, session in sessions.items()
        },
    }
    transitions = {
        "step_0p03": baseline_arm["transition_rows"],
        **{
            name: [_transition_row(row) for row in rows_by_arm[name]]
            for name in sessions
        },
    }
    diagnostics = {
        name: _arm_diagnostics(
            name=name,
            rows=rows_by_arm[name],
            evolution=evolution[name],
            transitions=transitions[name],
            baseline_rows=rows_by_arm["step_0p03"],
        )
        for name in MAX_STEP_ARMS
    }
    decision = _decision(rows_by_arm, diagnostics)
    payload = _strict_jsonable(
        {
            "schema": "stage5_model_update_max_step_comparison_v1_results",
            "config_path": str(
                MAX_STEP_COMPARISON_CONFIG_PATH.relative_to(STAGE5_ROOT)
            ),
            "formal_execution_explicitly_authorized_by_user": True,
            "only_scientific_variable": "maximum_per_scale_step",
            "fixed_model_update_alpha": FIXED_MODEL_UPDATE_ALPHA,
            "step_0p03_reuse_audit": audit,
            "frozen_endpoint_nms2": FROZEN_PP2_REP5_LOSS_NMS2,
            "arms": {
                name: {
                    "maximum_per_scale_step": MAX_STEP_ARMS[name],
                    "execution": (
                        "reused_exact_formal_alpha_comparison_arm"
                        if name == "step_0p03"
                        else "fresh_formal_execution"
                    ),
                    "rows": rows_by_arm[name],
                    "parameter_evolution": evolution[name],
                    "transition_rows": transitions[name],
                    "diagnostics": diagnostics[name],
                    "authority_summary": (
                        baseline_arm["authority_summary"]
                        if name == "step_0p03"
                        else sessions[name].authority.summary()
                    ),
                }
                for name in MAX_STEP_ARMS
            },
            "decision": decision,
            "truth_available_to_online_authority": False,
            "gamma_fixed": 0.5,
            "prefix_backend": "native",
            "acceleration_monitor_changed": False,
            "fresh_B_C_wall_time_s": perf_counter() - started,
        }
    )
    result_path = output_dir / "model_update_max_step_comparison_results.json"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, indent=2, sort_keys=True), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=ALPHA_FORMAL_RESULT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--execute-formal-fresh-b-c",
        action="store_true",
        help="reuse audited step=0.03 and freshly execute step=0.04 and 0.05",
    )
    arguments = parser.parse_args()
    audit = baseline_step_0p03_reuse_audit(arguments.baseline)
    if not arguments.execute_formal_fresh_b_c:
        print(json.dumps(_strict_jsonable(audit), indent=2, sort_keys=True))
        return
    execute_formal_fresh_b_c(arguments.output_dir, arguments.baseline)


if __name__ == "__main__":
    main()
