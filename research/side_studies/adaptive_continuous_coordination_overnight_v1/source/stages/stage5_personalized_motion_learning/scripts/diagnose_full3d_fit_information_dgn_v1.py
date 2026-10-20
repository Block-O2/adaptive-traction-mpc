"""Development-only replay: inspect data-only geometry information at handoff.

The temporary wrapper copies deployable commissioning observations before the
unchanged fit/replay executes.  Hidden plant parameters are never fit inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--contact-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)

    captured: dict[str, object] = {}
    original = runtime._fit_and_replay_commissioning

    def inspect(samples: list[dict[str, object]]):
        captured["samples"] = [
            {
                "time_s": float(s["time_s"]),
                "position_xz_m": np.asarray(s["human_position_world_m"])[[0, 2]].copy(),
                "phi_rad": float(s["phi_rad"]),
            }
            for s in samples
        ]
        result = original(samples)
        captured["fit"] = result[0]
        captured["updates"] = result[2]
        return result

    runtime._fit_and_replay_commissioning = inspect
    try:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        summary = runtime.run_executed_case(
            args.output / "episode", qualification_case=case,
            qualification_arm="continual_adaptive", simulate_planning_latency=True,
            formal_qualification=False,
        )
    finally:
        runtime._fit_and_replay_commissioning = original

    samples = captured["samples"]
    fit = captured["fit"]
    times = np.array([s["time_s"] for s in samples])
    position = np.array([s["position_xz_m"] for s in samples])
    phi = np.array([s["phi_rad"] for s in samples])
    direction = np.column_stack([np.cos(phi), np.sin(phi)])
    knee_minus_hip = position - fit.knee_to_cuff_m * direction - fit.hip_xz_m
    unit = knee_minus_hip / np.linalg.norm(knee_minus_hip, axis=1)[:, None]
    data_jac = np.column_stack([-unit[:, 0], -unit[:, 1],
                                -np.ones(len(unit)), -np.sum(unit * direction, axis=1)])
    data_singular = np.linalg.svd(data_jac, compute_uv=False)
    _, _, right = np.linalg.svd(data_jac, full_matrices=False)
    weight = 1e-3 if fit.angular_span_rad < np.deg2rad(20.0) else 1e-5
    regularization = np.diag(weight / np.array([0.25, 0.20, 0.12, 0.14]))
    augmented = np.vstack([data_jac, regularization])
    augmented_singular = np.linalg.svd(augmented, compute_uv=False)

    with np.load(args.contact_replay, allow_pickle=False) as contact:
        physical_time = contact["time_s"]
        physical_contact = contact["contact_count"] > 0
    update_intervals_with_contact = 0
    for start, end in zip(times[:-1], times[1:]):
        if np.any(physical_contact[(physical_time > start) & (physical_time <= end)]):
            update_intervals_with_contact += 1

    with np.load(args.output / "episode" / "trace.npz", allow_pickle=False) as current, \
            np.load(args.baseline / "trace.npz", allow_pickle=False) as baseline:
        c = current["stage"] == "COMMISSIONING"
        b = baseline["stage"] == "COMMISSIONING"
        differences = {}
        for name in ("time_s", "reference_q_rad", "estimated_human_state_rad_rad_s",
                     "evaluation_only_human_state_rad_rad_s", "cr12_q_rad",
                     "cr12_actuator_command_nm", "physical_cuff_force_world_n"):
            a, old = current[name][c], baseline[name][b]
            differences[name] = None if a.shape != old.shape else float(np.max(np.abs(a - old)))

    output = {
        "schema": "full3d_startup_dgn_v1_fit_information",
        "case_key": case["case_key"],
        "evidence_category": "development_replay_of_existing_formal_case",
        "fit_inputs": "deployable cuff position xz and measured shank angle only",
        "fit_accepted": bool(fit.accepted),
        "fit_reported_regularized_condition": float(fit.condition_number),
        "data_only_jacobian_singular_values": data_singular.tolist(),
        "data_only_jacobian_condition": float(data_singular[0] / data_singular[-1]),
        "data_only_weakest_parameter_direction_hx_hz_L1_sc": right[-1].tolist(),
        "regularized_jacobian_singular_values": augmented_singular.tolist(),
        "analytic_regularized_condition": float(augmented_singular[0] / augmented_singular[-1]),
        "sample_count": len(samples),
        "angular_span_rad": float(fit.angular_span_rad),
        "retrospective_dynamic_update_count": len(captured["updates"]),
        "retrospective_update_intervals_overlapping_physical_bed_contact": update_intervals_with_contact,
        "matched_commissioning_max_abs_differences": differences,
        "replay_status": summary["status"],
        "replay_abort_reason": summary["abort_reason"],
        "source_or_scientific_parameters_changed": False,
        "instrumentation_changes_planner_wall_clock_comparability": True,
    }
    (args.output / "fit_information.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
