#!/usr/bin/env python3
"""Export causal learning-ready transitions from one bounded feedback-HWMPC result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def export_dataset(source: Path, output: Path) -> dict[str, Any]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") not in {
        "stage5_hwmpc_state_feedback_validation_v1",
        "stage5_hwmpc_terminal_closeout_validation_v1",
        "stage5_hwmpc_state_triggered_terminal_validation_v1",
    }:
        raise ValueError("unexpected state-feedback validation schema")
    rows: list[dict[str, Any]] = []
    for case in payload["episodes"]:
        boundary_pass = {
            row["phase"]: bool(row["inside_existing_completion_criteria"])
            for row in case["controller"]["boundary_checks"]
        }
        rollout_completed = bool(case["completed"])
        rollout_reason = case["metrics"]["termination_reason"]
        if rollout_reason is None and not rollout_completed:
            failed = [phase for phase, passed in boundary_pass.items() if not passed]
            rollout_reason = "TERMINAL_COMPLETION_CRITERION_FAILED:" + ",".join(failed)
        for transition in case["controller"]["learning_records"]:
            row = dict(transition)
            contract_passed = bool(
                case.get("motion_and_execution_contract_passed", True)
            )
            row["rollout_completed"] = rollout_completed
            row["rollout_motion_and_execution_contract_passed"] = contract_passed
            row["phase_terminal_criteria_passed"] = boundary_pass.get(row["phase"])
            row["rollout_rejection_or_stop_reason"] = rollout_reason
            row["rollout_complete_force_integral_n_s"] = case["interaction"][
                "integral_cuff_force_n_s"
            ]
            row["cost_eligible_as_completed_success"] = bool(
                rollout_completed and contract_passed
            )
            row["mujoco_truth_used_online"] = False
            rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return {
        "source": str(source),
        "output": str(output),
        "transition_count": len(rows),
        "completed_rollout_transition_count": sum(
            bool(row["rollout_completed"]) for row in rows
        ),
        "failed_rollout_transition_count": sum(
            not bool(row["rollout_completed"]) for row in rows
        ),
        "missing_next_observation_count": sum(
            "next_observation_rad_rad_s" not in row for row in rows
        ),
        "failure_rows_retained": any(
            not bool(row["cost_eligible_as_completed_success"]) for row in rows
        ),
        "ineligible_success_row_count": sum(
            not bool(row["cost_eligible_as_completed_success"]) for row in rows
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(export_dataset(arguments.source, arguments.output), indent=2))


if __name__ == "__main__":
    main()
