#!/usr/bin/env python3
"""Strict equivalence audit for the Stage-5 prefix-screen NumPy refactor."""

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
SPEC = importlib.util.spec_from_file_location("stage5_runtime_for_prefix_v1", RUNTIME_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
TOLERANCE = 1.0e-11
PROGRESSIVE_THETA_5 = (
    0.999984460611625,
    1.000264489157326,
    1.087992468652811,
)


def _maximum_difference(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def _solve_with_audit(
    snapshot: dict[str, Any], mode: str
) -> tuple[np.ndarray, dict[str, Any], Any, np.ndarray, list[dict[str, Any]]]:
    state = deepcopy(snapshot["mpc_snapshot"])
    state["_runtime_equivalence_population_audit"] = True
    action, diagnostics, _, _, preview = RUNTIME.one_solve(
        snapshot, state, mode, capture_prefix_diagnostics=True
    )
    sequence = snapshot["mpc"].last_sequence.copy()
    population_records = deepcopy(
        snapshot["mpc"]._runtime_equivalence_population_records
    )
    return action, diagnostics, preview, sequence, population_records


def _population_predictions(preview: Any, candidate_count: int) -> list[Any]:
    return [
        prediction
        for actions, prediction in preview._screen_cache
        if len(actions) == candidate_count
    ]


def _compare_full_solve(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    reference = _solve_with_audit(snapshot, "v2_prefix_reference")
    optimized = _solve_with_audit(snapshot, "v2_prefix")
    ref_action, ref_diag, ref_preview, ref_sequence, ref_records = reference
    opt_action, opt_diag, opt_preview, opt_sequence, opt_records = optimized
    candidate_count = snapshot["mpc"].config.candidate_count
    ref_populations = _population_predictions(ref_preview, candidate_count)
    opt_populations = _population_predictions(opt_preview, candidate_count)
    if len(ref_populations) != len(opt_populations):
        raise RuntimeError("reference and optimized CEM population counts differ")

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
    population_rows = []
    for ref, opt in zip(ref_populations, opt_populations, strict=True):
        row = {
            "feasibility_mask_exact": bool(np.array_equal(ref.feasible, opt.feasible)),
            "prefix_feasibility_exact": bool(
                np.array_equal(
                    ref.prefix_acceleration_feasible,
                    opt.prefix_acceleration_feasible,
                )
            ),
            "executable_force_max_abs_difference": _maximum_difference(
                ref.executable_batch.force_total_n, opt.executable_batch.force_total_n
            ),
            "executable_moment_max_abs_difference": _maximum_difference(
                ref.executable_batch.moment_total_nm,
                opt.executable_batch.moment_total_nm,
            ),
            "prefix_times_exact": bool(
                np.array_equal(ref.prefix_times_s, opt.prefix_times_s)
                and np.array_equal(
                    opt.prefix_times_s, np.asarray([0.005, 0.010, 0.015, 0.020])
                )
            ),
        }
        row.update(
            {
                f"{name}_max_abs_difference": _maximum_difference(
                    getattr(ref, name), getattr(opt, name)
                )
                for name in prefix_fields
            }
        )
        population_rows.append(row)

    if len(ref_records) != len(opt_records):
        raise RuntimeError("reference and optimized population records differ")
    candidate_cost_difference = max(
        _maximum_difference(a["cost"], b["cost"])
        for a, b in zip(ref_records, opt_records, strict=True)
    )
    candidate_margin_difference = max(
        _maximum_difference(a["margin"], b["margin"])
        for a, b in zip(ref_records, opt_records, strict=True)
    )
    predicted_state_difference = max(
        _maximum_difference(a["predicted_states"], b["predicted_states"])
        for a, b in zip(ref_records, opt_records, strict=True)
    )
    elite_indices_exact = all(
        np.array_equal(
            np.argsort(a["cost"])[
                : min(snapshot["mpc"].config.elite_count, len(a["cost"]))
            ],
            np.argsort(b["cost"])[
                : min(snapshot["mpc"].config.elite_count, len(b["cost"]))
            ],
        )
        for a, b in zip(ref_records, opt_records, strict=True)
    )
    selected_diag_fields = (
        "status",
        "first_action_feasible_candidates_per_iteration",
        "first_action_filter_statuses_per_iteration",
        "selected_executable_command",
        "selected_safety_filter",
    )
    selected_diagnostics_exact = {
        name: ref_diag[name] == opt_diag[name] for name in selected_diag_fields
    }
    numerical_maxima = [
        _maximum_difference(ref_action, opt_action),
        _maximum_difference(ref_sequence, opt_sequence),
        candidate_cost_difference,
        candidate_margin_difference,
        predicted_state_difference,
        *[
            float(value)
            for row in population_rows
            for name, value in row.items()
            if name.endswith("_max_abs_difference")
        ],
    ]
    passed = bool(
        max(numerical_maxima) <= TOLERANCE
        and elite_indices_exact
        and all(selected_diagnostics_exact.values())
        and all(
            row["feasibility_mask_exact"]
            and row["prefix_feasibility_exact"]
            and row["prefix_times_exact"]
            for row in population_rows
        )
    )
    return {
        "label": label,
        "passed": passed,
        "selected_action_max_abs_difference": numerical_maxima[0],
        "selected_sequence_max_abs_difference": numerical_maxima[1],
        "population_predicted_states_max_abs_difference": predicted_state_difference,
        "candidate_cost_max_abs_difference": candidate_cost_difference,
        "candidate_constraint_margin_max_abs_difference": (
            candidate_margin_difference
        ),
        "elite_indices_exact": elite_indices_exact,
        "selected_diagnostics_exact": selected_diagnostics_exact,
        "populations": population_rows,
    }


def _saved_trace_dynamics_checks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    audit_path = (
        STAGE5_ROOT
        / "results"
        / "acceleration_pacing_signal_audit_v1_attempt_02"
        / "acceleration_signal_audit.json"
    )
    audit = json.loads(audit_path.read_text())
    names = {
        "mass_plus_8pct_human": "known_conservative_false_positive",
        "interface_v2_low_low_high": "retained_real_short_transient_violation",
    }
    preview = RUNTIME.build_preview(snapshot, "v2_prefix")
    owner = snapshot["mpc"]
    preview._prefix_human_continuous_dynamics = (
        owner._batched_base_continuous_dynamics
    )
    rows = []
    for trace in audit["traces"]:
        if trace["name"] not in names:
            continue
        data = np.load(STAGE5_ROOT / trace["trace_path"])
        index = int(
            np.argmin(np.abs(data["time_s"] - float(trace["event"]["timestamp_s"])))
        )
        state = np.asarray(data["estimated_state_rad_rad_s"][index], dtype=float)[
            None, :
        ]
        action = np.asarray(
            data["deployable_measured_generalized_input_nm"][index], dtype=float
        )[None, :]
        reference = owner._batched_base_continuous_dynamics(
            state, action, snapshot["human_model"]
        )
        optimized = preview._prefix_continuous_dynamics_numpy(state, action)
        difference = _maximum_difference(reference, optimized)
        rows.append(
            {
                "label": names[trace["name"]],
                "source_trace": trace["trace_path"],
                "timestamp_s": float(data["time_s"][index]),
                "max_abs_difference": difference,
                "passed": difference <= TOLERANCE,
            }
        )
    if set(names.values()) != {row["label"] for row in rows}:
        raise RuntimeError("required saved acceleration traces are unavailable")
    return rows


def equivalence_audit() -> dict[str, Any]:
    snapshot = RUNTIME._build_fixed_snapshot()
    nominal = _compare_full_solve(snapshot, "nominal_and_near_acceleration_limit")
    progressive = RUNTIME._build_fixed_snapshot()
    progressive["human_model"] = _model(
        progressive["human_model"].geometry, PROGRESSIVE_THETA_5
    )
    progressive_result = _compare_full_solve(
        progressive, "representative_progressive_theta_5"
    )
    trace_rows = _saved_trace_dynamics_checks(snapshot)
    repeat_snapshot = RUNTIME._build_fixed_snapshot()
    repeat_state = deepcopy(repeat_snapshot["mpc_snapshot"])
    repeat_a = RUNTIME.one_solve(repeat_snapshot, repeat_state, "v2_prefix")
    sequence_a = repeat_snapshot["mpc"].last_sequence.copy()
    repeat_b = RUNTIME.one_solve(repeat_snapshot, repeat_state, "v2_prefix")
    sequence_b = repeat_snapshot["mpc"].last_sequence.copy()
    repeatability = {
        "selected_action_exact": bool(np.array_equal(repeat_a[0], repeat_b[0])),
        "selected_sequence_exact": bool(np.array_equal(sequence_a, sequence_b)),
        "status_exact": repeat_a[1]["status"] == repeat_b[1]["status"],
    }
    passed = bool(
        nominal["passed"]
        and progressive_result["passed"]
        and all(row["passed"] for row in trace_rows)
        and all(repeatability.values())
    )
    return {
        "schema": "stage5_prefix_optimization_equivalence_v1",
        "absolute_tolerance": TOLERANCE,
        "passed": passed,
        "full_solve_snapshots": [nominal, progressive_result],
        "saved_trace_dynamics_snapshots": trace_rows,
        "deterministic_repeatability": repeatability,
        "frozen_contract": {
            "prefix_times_s": [0.005, 0.010, 0.015, 0.020],
            "physical_substep_s": 0.00025,
            "horizon_candidates_iterations": [
                snapshot["mpc"].config.horizon_steps,
                snapshot["mpc"].config.candidate_count,
                snapshot["mpc"].config.cem_iterations,
            ],
            "task_acceleration_limits_rad_s2": list(
                snapshot["spec"].task_joint_acceleration_limit_rad_s2
            ),
            "acceleration_semantics_version": "v2_cumulative_prefix_5_10_15_20ms",
        },
        "truth_used_by_control": False,
        "production_parameters_changed": False,
    }


def main() -> None:
    result = equivalence_audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
