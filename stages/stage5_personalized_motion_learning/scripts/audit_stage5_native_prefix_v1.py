#!/usr/bin/env python3
"""Strict semantic audit for the optional Stage-5 native prefix recurrence."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.human_model_replication import _model


RUNTIME_PATH = Path(__file__).with_name("audit_stage5_runtime_regression_v3.py")
SPEC = importlib.util.spec_from_file_location("stage5_runtime_for_native_v1", RUNTIME_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)

ABSOLUTE_TOLERANCE = 1.0e-11
PROGRESSIVE_THETA_5 = (
    0.999984460611625,
    1.000264489157326,
    1.087992468652811,
)


def _max_abs(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def _max_relative(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    mask = np.abs(a) > 1.0e-12
    if not np.any(mask):
        return 0.0
    return float(np.max(np.abs((a[mask] - b[mask]) / a[mask])))


def _solve(snapshot: dict[str, Any], mode: str):
    state = deepcopy(snapshot["mpc_snapshot"])
    state["_runtime_equivalence_population_audit"] = True
    action, diagnostics, _, _, preview = RUNTIME.one_solve(
        snapshot,
        state,
        mode,
        capture_prefix_diagnostics=True,
        capture_prefix_substeps=True,
    )
    return {
        "action": action,
        "diagnostics": diagnostics,
        "sequence": snapshot["mpc"].last_sequence.copy(),
        "records": deepcopy(snapshot["mpc"]._runtime_equivalence_population_records),
        "preview": preview,
    }


def _population_predictions(preview: Any, candidate_count: int) -> list[Any]:
    return [
        prediction
        for actions, prediction in preview._screen_cache
        if len(actions) == candidate_count
    ]


def _compare_full_solve(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    reference = _solve(snapshot, "v2_prefix")
    native = _solve(snapshot, "v2_prefix_native")
    candidate_count = snapshot["mpc"].config.candidate_count
    reference_populations = _population_predictions(
        reference["preview"], candidate_count
    )
    native_populations = _population_predictions(native["preview"], candidate_count)
    if len(reference_populations) != len(native_populations):
        raise RuntimeError("reference/native CEM population count differs")
    if len(reference["records"]) != len(native["records"]):
        raise RuntimeError("reference/native population audit count differs")

    prefix_fields = (
        "predicted_prefix_states_rad_rad_s",
        "predicted_prefix_acceleration_rad_s2",
        "prefix_acceleration_margin_rad_s2",
        "predicted_prefix_interface_displacement_human_m",
        "predicted_prefix_interface_velocity_human_m_s",
        "predicted_prefix_interface_rotation_human_rad",
        "predicted_prefix_interface_angular_velocity_human_rad_s",
        "predicted_prefix_executable_wrench_world",
    )
    population_rows: list[dict[str, Any]] = []
    for ref, compiled in zip(
        reference_populations, native_populations, strict=True
    ):
        row: dict[str, Any] = {
            "feasibility_mask_exact": bool(
                np.array_equal(ref.feasible, compiled.feasible)
            ),
            "prefix_feasibility_exact": bool(
                np.array_equal(
                    ref.prefix_acceleration_feasible,
                    compiled.prefix_acceleration_feasible,
                )
            ),
            "prefix_times_exact": bool(
                np.array_equal(ref.prefix_times_s, compiled.prefix_times_s)
            ),
            "executable_force_exact": bool(
                np.array_equal(
                    ref.executable_batch.force_total_n,
                    compiled.executable_batch.force_total_n,
                )
            ),
            "executable_moment_exact": bool(
                np.array_equal(
                    ref.executable_batch.moment_total_nm,
                    compiled.executable_batch.moment_total_nm,
                )
            ),
        }
        for field in prefix_fields:
            row[f"{field}_max_abs_difference"] = _max_abs(
                getattr(ref, field), getattr(compiled, field)
            )
        population_rows.append(row)

    record_rows = []
    elite_count = snapshot["mpc"].config.elite_count
    for ref, compiled in zip(reference["records"], native["records"], strict=True):
        record_rows.append(
            {
                "candidate_actions_exact": bool(
                    np.array_equal(ref["candidates_nm"], compiled["candidates_nm"])
                ),
                "cost_max_abs_difference": _max_abs(ref["cost"], compiled["cost"]),
                "margin_max_abs_difference": _max_abs(
                    ref["margin"], compiled["margin"]
                ),
                "predicted_state_max_abs_difference": _max_abs(
                    ref["predicted_states"], compiled["predicted_states"]
                ),
                "elite_indices_exact": bool(
                    np.array_equal(
                        np.argsort(ref["cost"])[:elite_count],
                        np.argsort(compiled["cost"])[:elite_count],
                    )
                ),
            }
        )

    diagnostics_fields = (
        "status",
        "first_action_feasible_candidates_per_iteration",
        "first_action_filter_statuses_per_iteration",
        "selected_executable_command",
        "selected_safety_filter",
    )
    diagnostics_exact = {
        field: reference["diagnostics"][field] == native["diagnostics"][field]
        for field in diagnostics_fields
    }
    maxima = [
        _max_abs(reference["action"], native["action"]),
        _max_abs(reference["sequence"], native["sequence"]),
        *[
            float(value)
            for row in population_rows
            for key, value in row.items()
            if key.endswith("_max_abs_difference")
        ],
        *[
            float(value)
            for row in record_rows
            for key, value in row.items()
            if key.endswith("_max_abs_difference")
        ],
    ]
    passed = bool(
        max(maxima) <= ABSOLUTE_TOLERANCE
        and all(diagnostics_exact.values())
        and all(
            row["feasibility_mask_exact"]
            and row["prefix_feasibility_exact"]
            and row["prefix_times_exact"]
            and row["executable_force_exact"]
            and row["executable_moment_exact"]
            for row in population_rows
        )
        and all(
            row["candidate_actions_exact"] and row["elite_indices_exact"]
            for row in record_rows
        )
    )
    return {
        "label": label,
        "passed": passed,
        "selected_action_max_abs_difference": maxima[0],
        "selected_sequence_max_abs_difference": maxima[1],
        "maximum_numeric_difference": max(maxima),
        "diagnostics_exact": diagnostics_exact,
        "populations": population_rows,
        "cem_iterations": record_rows,
    }


def _saved_event_rows() -> list[dict[str, Any]]:
    audit_path = (
        STAGE5_ROOT
        / "results"
        / "acceleration_pacing_signal_audit_v1_attempt_02"
        / "acceleration_signal_audit.json"
    )
    audit = json.loads(audit_path.read_text())
    required = {
        "mass_plus_8pct_human": "known_conservative_false_positive",
        "interface_v2_low_low_high": "retained_real_short_transient_violation",
    }
    snapshot = RUNTIME._build_fixed_snapshot()
    rows = []
    for trace_record in audit["traces"]:
        if trace_record["name"] not in required:
            continue
        trace = np.load(STAGE5_ROOT / trace_record["trace_path"])
        timestamp = float(trace_record["event"]["timestamp_s"])
        index = int(np.argmin(np.abs(trace["time_s"] - timestamp)))
        state = np.asarray(trace["estimated_state_rad_rad_s"][index], dtype=float)
        q_batch = np.broadcast_to(state, (32, 4)).copy()
        x = np.broadcast_to(
            trace["estimated_interface_translation_human_m"][index], (32, 3)
        ).copy()
        u = np.broadcast_to(
            trace["estimated_interface_velocity_human_m_s"][index], (32, 3)
        ).copy()
        theta = np.broadcast_to(
            trace["estimated_interface_rotation_human_rad"][index], (32, 3)
        ).copy()
        omega = np.broadcast_to(
            trace["estimated_interface_angular_velocity_human_rad_s"][index],
            (32, 3),
        ).copy()
        drive = np.broadcast_to(
            trace["prediction_base_drive_world_n"][index], (32, 3)
        ).copy()
        angular_drive = np.broadcast_to(
            trace["prediction_base_angular_drive_world_nm"][index], (32, 3)
        ).copy()
        reference_preview = RUNTIME.build_preview(
            snapshot, "v2_prefix", capture_prefix_substeps=True
        )
        native_preview = RUNTIME.build_preview(
            snapshot, "v2_prefix_native", capture_prefix_substeps=True
        )
        owner = snapshot["mpc"]
        for preview in (reference_preview, native_preview):
            preview._prefix_human_continuous_dynamics = (
                owner._batched_base_continuous_dynamics
            )
        jacobian, rotation = reference_preview._prefix_geometry_batch(
            q_batch[:, :2]
        )
        inputs = {
            "states": q_batch,
            "x": x,
            "u": u,
            "theta": theta,
            "omega": omega,
            "rotation": rotation,
            "jacobian": jacobian,
            "drive_world": drive,
            "angular_drive_world": angular_drive,
            "substeps": 20,
        }
        reference = reference_preview._propagate_prefix_segment_numpy(
            **{name: value.copy() if isinstance(value, np.ndarray) else value for name, value in inputs.items()},
            region_timing={
                "drive_frame_transforms": 0.0,
                "interface_state_and_wrench": 0.0,
                "human_forward_dynamics": 0.0,
                "geometry_and_frame_update": 0.0,
            },
            profile=False,
        )
        compiled = native_preview._propagate_prefix_segment_native(
            **{name: value.copy() if isinstance(value, np.ndarray) else value for name, value in inputs.items()}
        )
        field_names = (
            "state",
            "translation",
            "translation_velocity",
            "rotation",
            "angular_velocity",
            "frame",
            "jacobian",
            "substep_trace",
        )
        differences = {
            name: _max_abs(left, right)
            for name, left, right in zip(field_names, reference, compiled, strict=True)
        }
        rows.append(
            {
                "label": required[trace_record["name"]],
                "source_trace": trace_record["trace_path"],
                "timestamp_s": float(trace["time_s"][index]),
                "maximum_numeric_difference": max(differences.values()),
                "maximum_relative_difference": _max_relative(
                    reference[-1], compiled[-1]
                ),
                "fields": differences,
                "passed": max(differences.values()) <= ABSOLUTE_TOLERANCE,
                "truth_used_online": False,
            }
        )
    if {row["label"] for row in rows} != set(required.values()):
        raise RuntimeError("required saved-event traces are unavailable")
    return rows


def equivalence_audit() -> dict[str, Any]:
    nominal_snapshot = RUNTIME._build_fixed_snapshot()
    nominal = _compare_full_solve(
        nominal_snapshot, "nominal_and_near_acceleration_limit"
    )
    progressive_snapshot = RUNTIME._build_fixed_snapshot()
    progressive_snapshot["human_model"] = _model(
        progressive_snapshot["human_model"].geometry, PROGRESSIVE_THETA_5
    )
    progressive = _compare_full_solve(
        progressive_snapshot, "representative_progressive_theta_5"
    )
    event_rows = _saved_event_rows()

    repeat_snapshot = RUNTIME._build_fixed_snapshot()
    mpc_snapshot = deepcopy(repeat_snapshot["mpc_snapshot"])
    first = RUNTIME.one_solve(repeat_snapshot, mpc_snapshot, "v2_prefix_native")
    first_sequence = repeat_snapshot["mpc"].last_sequence.copy()
    second = RUNTIME.one_solve(repeat_snapshot, mpc_snapshot, "v2_prefix_native")
    second_sequence = repeat_snapshot["mpc"].last_sequence.copy()
    repeatability = {
        "selected_action_exact": bool(np.array_equal(first[0], second[0])),
        "selected_sequence_exact": bool(
            np.array_equal(first_sequence, second_sequence)
        ),
        "status_exact": first[1]["status"] == second[1]["status"],
    }
    result = {
        "schema": "stage5_native_prefix_equivalence_v1",
        "absolute_tolerance": ABSOLUTE_TOLERANCE,
        "full_solve_snapshots": [nominal, progressive],
        "saved_event_segment_snapshots": event_rows,
        "deterministic_repeatability": repeatability,
        "frozen_contract": {
            "prefix_times_s": [0.005, 0.010, 0.015, 0.020],
            "substep_s": 0.00025,
            "substeps_per_prefix": 20,
            "candidate_count": 32,
            "cem_iterations": 2,
            "native_calls_per_population": 4,
            "float_precision": "float64",
            "fast_math": False,
            "fp_contraction": "off",
        },
        "truth_used_online": False,
    }
    result["passed"] = bool(
        all(row["passed"] for row in result["full_solve_snapshots"])
        and all(row["passed"] for row in event_rows)
        and all(repeatability.values())
    )
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = equivalence_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "snapshots": [
                    {
                        "label": row["label"],
                        "maximum_numeric_difference": row[
                            "maximum_numeric_difference"
                        ],
                    }
                    for row in result["full_solve_snapshots"]
                    + result["saved_event_segment_snapshots"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
