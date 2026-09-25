#!/usr/bin/env python3
"""Collect context-matched near-limit windows under unchanged Stage-5 semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.near_limit_shadow import (
    NearLimitShadowTarget,
    select_near_limit_shadow_targets,
)

from run_stage5_diagnostic_continuation_cases import _run_human_mismatch
from run_stage5_human_id_confidence_pacing_v1 import _load_config


RESULTS = STAGE5_ROOT / "results"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _select_targets(source: Path) -> tuple[NearLimitShadowTarget, ...]:
    source = source.resolve()
    with np.load(source / "trace.npz", allow_pickle=False) as trace:
        time = trace["time_s"]
        phase = trace["task_phase"]
        acceleration = trace["deployable_realized_acceleration_rad_s2"]
    summary = _read(source / "summary.json")
    limits = np.radians(
        summary["acceleration_semantics"]["registered_limit_deg_s2"]
    )
    return select_near_limit_shadow_targets(
        time_s=time,
        task_phase=phase,
        deployable_acceleration_rad_s2=acceleration,
        registered_limit_rad_s2=limits,
        high_level_steps=4,
        cycle_offsets=(2, 3),
        task_phases=("OUTBOUND",),
        source_trace=str(source.relative_to(STAGE5_ROOT)),
    )


def _case_record(
    *,
    name: str,
    role: str,
    source: Path,
    output: Path,
    targets: tuple[NearLimitShadowTarget, ...],
    summary: dict[str, Any],
) -> dict[str, Any]:
    source = source.resolve()
    output = output.resolve()
    collection = _read(output / "near_limit_diagnostic_continuations.json")
    if collection["captured_target_count"] != len(targets):
        raise RuntimeError(f"{name} did not capture every planned target")
    return {
        "case": name,
        "role": role,
        "selection_source": str(source.relative_to(STAGE5_ROOT)),
        "output": str(output.relative_to(STAGE5_ROOT)),
        "targets": [target.record() for target in targets],
        "planned_target_count": len(targets),
        "captured_target_count": collection["captured_target_count"],
        "authoritative_task_status": summary["task_status"],
        "authoritative_abort_reason": summary["abort_reason"],
        "authoritative_duration_s": summary["task_duration_s"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS / "near_limit_shadow_cases",
    )
    args = parser.parse_args()
    output_root = args.output_dir
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    confidence_root = RESULTS / "human_id_confidence_pacing_v1_attempt_01"
    post_abort_root = RESULTS / "diagnostic_continuation_cases_20260918_attempt_02"
    sources = {
        "nominal": confidence_root / "nominal" / "episode_01",
        "damping_plus_20pct": (
            confidence_root / "damping_plus_20pct" / "episode_01"
        ),
        "stiffness_plus_15pct": post_abort_root / "stiffness_plus_15pct",
        "mass_plus_8pct": post_abort_root / "mass_plus_8pct",
        "nominal_torque_smoke": (
            RESULTS
            / "transition_response_shadow_v2_minimum_cases_20260918_attempt_03"
            / "nominal_torque_smoke"
        ),
    }
    targets = {name: _select_targets(path) for name, path in sources.items()}
    if any(len(value) != 2 for value in targets.values()):
        raise RuntimeError("expected one OUTBOUND target at each +10/+15 ms context")

    config = _load_config()
    scales = {
        case["name"]: case["truth_scales_evaluation_only"]
        for case in config["cases"]
    }
    rows = []
    for name, role in (
        ("nominal", "benign_near_limit"),
        ("damping_plus_20pct", "benign_near_limit"),
        ("stiffness_plus_15pct", "human_mismatch_nonabort_state"),
        ("mass_plus_8pct", "human_mismatch_nonabort_state"),
    ):
        output = output_root / name
        summary = _run_human_mismatch(
            name=name,
            scales=scales[name],
            output_dir=output,
            config=config,
            near_limit_shadow_targets=targets[name],
            diagnostic_post_abort_continuation=False,
        )
        rows.append(
            _case_record(
                name=name,
                role=role,
                source=sources[name],
                output=output,
                targets=targets[name],
                summary=summary,
            )
        )

    name = "nominal_torque_smoke"
    output = output_root / name
    summary = run_goal_mpc_smoke(
        output,
        maximum_duration_s=0.5,
        plant_case_name="near_limit_shadow__nominal_torque_smoke",
        near_limit_shadow_targets=targets[name],
    )
    rows.append(
        _case_record(
            name=name,
            role="benign_comparable_command_load_context",
            source=sources[name],
            output=output,
            targets=targets[name],
            summary=summary,
        )
    )

    payload = {
        "schema": "stage5_near_limit_shadow_cases_v1",
        "evidence_category": "shadow_only_engineering_diagnostic",
        "shadow_only": True,
        "abort_authority_changed": False,
        "threshold_changed": False,
        "controller_semantics_changed": False,
        "scientific_parameters_changed": False,
        "selection": {
            "method": (
                "highest ranked nonterminal sample below the existing boundary "
                "within OUTBOUND and MPC-cycle offsets +10/+15 ms"
            ),
            "new_numeric_threshold": None,
            "positive_context_basis": (
                "CR12/Kt=1.3 aborts occurred at +15 ms and low_low_high at +10 ms"
            ),
        },
        "cases": rows,
    }
    _write(output_root / "near_limit_cases_summary.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
