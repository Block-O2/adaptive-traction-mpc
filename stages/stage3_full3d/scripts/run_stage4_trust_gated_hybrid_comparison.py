#!/usr/bin/env python3
"""Run one original-CEM versus dynamics-trust-gated hybrid engineering A/B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from run_stage4_hybrid_optimizer_comparison import (
    _phase_matched_metrics,
    _row,
)
from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.cuff_allocator import DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG
from traction_mpc_stage4.hybrid_optimizer import HybridHumanSpaceMPC
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.mpc import INTERACTION_AWARE_MPC_CONFIG, HumanSpaceMPC
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


ROLLOUT_DURATION_S = 32.0


class TrustGateReferenceExecution(ReferenceExecutionLayer):
    """Observe the existing trust state without changing confidence pacing."""

    def __init__(self, gate: dict[str, Any]) -> None:
        super().__init__(continuous_teaching_reference, confidence_aware=True)
        self.gate = gate

    def update_from_estimator(self, wall_time_s: float, estimator: Any, *args: Any) -> None:
        super().update_from_estimator(wall_time_s, estimator, *args)
        trusted_time = estimator.dynamic_identifier.trustworthy_time_s
        self.gate["dynamics_trusted"] = trusted_time is not None
        self.gate["trustworthy_time_s"] = trusted_time
        self.gate["latest_reference_phase_s"] = self.phase_time_s(wall_time_s)


class RecordingCEM(HumanSpaceMPC):
    def __init__(self) -> None:
        super().__init__(INTERACTION_AWARE_MPC_CONFIG)
        self.diagnostic_history: list[dict[str, Any]] = []

    def solve(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        action, diagnostics = super().solve(*args, **kwargs)
        self.diagnostic_history.append(diagnostics)
        return action, diagnostics


class RecordingGatedHybrid(HybridHumanSpaceMPC):
    def __init__(self, gate: dict[str, Any]) -> None:
        super().__init__(
            INTERACTION_AWARE_MPC_CONFIG,
            refinement_eligibility=lambda: bool(gate["dynamics_trusted"]),
        )
        self.gate = gate
        self.diagnostic_history: list[dict[str, Any]] = []

    def solve(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        action, diagnostics = super().solve(*args, **kwargs)
        record = dict(diagnostics)
        record["wall_time_s"] = float(args[1])
        record["reference_phase_s"] = float(
            self.gate.get("latest_reference_phase_s", 0.0)
        )
        self.diagnostic_history.append(record)
        return action, diagnostics


def _gated_optimizer_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [item for item in history if item["local_refinement"].get("eligible", False)]
    accepted = [item for item in eligible if item["local_refinement"]["accepted"]]
    relative = np.asarray(
        [
            item["local_refinement"].get("relative_objective_improvement", 0.0)
            for item in eligible
        ],
        dtype=float,
    )
    return {
        "ineligible_pretrust_call_count": len(history) - len(eligible),
        "eligible_posttrust_call_count": len(eligible),
        "accepted_posttrust_call_count": len(accepted),
        "accepted_posttrust_call_fraction": (
            float(len(accepted) / len(eligible)) if eligible else 0.0
        ),
        "first_eligible_wall_time_s": (
            None if not eligible else eligible[0]["wall_time_s"]
        ),
        "first_eligible_reference_phase_s": (
            None if not eligible else eligible[0]["reference_phase_s"]
        ),
        "mean_relative_objective_improvement_all_posttrust_calls": (
            float(np.mean(relative)) if len(relative) else 0.0
        ),
        "mean_relative_objective_improvement_accepted_posttrust_calls": (
            float(
                np.mean(
                    [
                        item["local_refinement"]["relative_objective_improvement"]
                        for item in accepted
                    ]
                )
            )
            if accepted
            else 0.0
        ),
        "maximum_relative_objective_improvement": (
            float(np.max(relative)) if len(relative) else 0.0
        ),
    }


def _write_summary(output_dir: Path, comparison: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 dynamics-trust-gated hybrid engineering A/B",
        "",
        "One registered engineering A/B. The only variable is local-refinement eligibility after the existing dynamics trust event.",
        "",
        "| mode | completion | tracking RMSE/max | force peak/RMS | moment peak/RMS | surface peak/RMS | MPC mean/p95 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["rows"]:
        completion = row["reference_completion_time_s"]
        runtime = row["optimizer"]["runtime_ms_per_call"]["external_total"]
        lines.append(
            f'| {row["mode"]} | '
            f'{"-" if completion is None else f"{completion:.3f} s"} | '
            f'{row["tracking"]["combined_rmse_deg"]:.3f}/'
            f'{row["tracking"]["combined_max_abs_error_deg"]:.3f} deg | '
            f'{row["cuff_force"]["peak"]["value"]:.2f}/'
            f'{row["cuff_force"]["rms_n"]:.2f} N | '
            f'{row["cuff_moment"]["peak"]["value"]:.2f}/'
            f'{row["cuff_moment"]["rms_nm"]:.2f} Nm | '
            f'{row["cylindrical_surface_proxy"]["peak"]["value"]:.2f}/'
            f'{row["cylindrical_surface_proxy"]["rms_n"]:.2f} N | '
            f'{runtime["mean"]:.1f}/{runtime["p95"]:.1f} ms |'
        )
    gated = comparison["gated_posttrust_optimizer"]
    lines.extend(
        [
            "",
            f'- pre-trust calls without local refinement: {gated["ineligible_pretrust_call_count"]}',
            f'- post-trust eligible/accepted calls: {gated["eligible_posttrust_call_count"]}/{gated["accepted_posttrust_call_count"]}',
            f'- mean post-trust objective improvement over all eligible calls: {100.0 * gated["mean_relative_objective_improvement_all_posttrust_calls"]:.3f}%',
        ]
    )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    ideal_case = sensor_realism_cases()[0]
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    rows: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    for mode in ("original_cem", "dynamics_trust_gated_hybrid"):
        gate: dict[str, Any] = {
            "dynamics_trusted": False,
            "trustworthy_time_s": None,
            "latest_reference_phase_s": 0.0,
        }
        execution = TrustGateReferenceExecution(gate)
        created: dict[str, Any] = {}

        def factory(mode: str = mode, gate: dict[str, Any] = gate) -> HumanSpaceMPC:
            controller: HumanSpaceMPC
            if mode == "original_cem":
                controller = RecordingCEM()
            else:
                controller = RecordingGatedHybrid(gate)
            created["controller"] = controller
            return controller

        summary, trace = run_sensor_realism_case(
            ideal_case,
            duration_s=ROLLOUT_DURATION_S,
            estimator_architecture="integral_minimal",
            result_case_name=mode,
            reference_fn=continuous_teaching_reference,
            trajectory_label="stage4_registered_continuous_high_flexion_23s",
            trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
            reference_execution=execution,
            mpc_factory=factory,
        )
        save_sensor_case(args.output_dir, summary, trace)
        controller = created["controller"]
        history = controller.diagnostic_history
        histories[mode] = history
        traces[mode] = trace
        rows.append(_row(mode, summary, trace, history, surface_model))

    if rows[0]["force_gate_n"] != rows[1]["force_gate_n"]:
        raise RuntimeError("A/B changed the force safety limit")
    comparison = {
        "evidence_category": "stage4_dynamics_trust_gated_hybrid_engineering_ab",
        "formal_experiment": False,
        "single_variable": "local_refinement_eligible_only_after_existing_dynamics_trust",
        "shared": {
            "global_cem": "unchanged",
            "mpc_objective": INTERACTION_AWARE_MPC_CONFIG.objective_contract(),
            "allocator": DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.as_dict(),
            "estimator_logic_bounds_and_gates": "unchanged",
            "confidence_pacing": "unchanged",
            "plant_trajectory_and_safety": "unchanged",
        },
        "rows": rows,
        "common_phase_comparison": _phase_matched_metrics(traces, surface_model),
        "gated_posttrust_optimizer": _gated_optimizer_summary(
            histories["dynamics_trust_gated_hybrid"]
        ),
        "tracking_corridor_or_tube_added": False,
        "active_exploration_added": False,
        "post_result_tuning": False,
    }
    (args.output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, comparison)


if __name__ == "__main__":
    main()
