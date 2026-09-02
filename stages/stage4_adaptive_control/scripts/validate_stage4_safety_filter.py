#!/usr/bin/env python3
"""Short engineering validation/profile for the executable-force filter.

The historical failure-state NPZ files are unavailable.  This script reuses
the Phase-3 analytic failure-time references and force-matched unsafe actions;
it does not advance a High-ROM trajectory or make a scientific claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable

import numpy as np

from scripts.validate_stage4_brake_windows import (
    FIXTURES,
    _estimated_state,
    _initialize,
    _measurement,
    _model,
    _reconstructed_unsafe_action,
    _reference,
)
from traction_mpc_stage4.cuff_allocator import (
    default_engineering_cuff_allocator,
)
from traction_mpc_stage4.mpc import HumanSpaceMPC, SAFE_ACTION
from traction_mpc_stage4.safety_filter import (
    filter_executable_command,
    filter_executable_commands_batch,
    make_stage4_executable_force_filter,
    prepare_executable_force_filter_context,
)
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor


def _timing(
    operation: Callable[[], Any],
    *,
    warmup: int,
    samples: int,
    deadline_ms: float,
) -> dict[str, Any]:
    values = np.empty(samples)
    for index in range(warmup + samples):
        started = perf_counter_ns()
        operation()
        elapsed_ms = (perf_counter_ns() - started) / 1.0e6
        if index >= warmup:
            values[index - warmup] = elapsed_ms
    mean_ms = float(np.mean(values))
    return {
        "warmup": warmup,
        "samples": samples,
        "mean_ms": mean_ms,
        "median_ms": float(np.median(values)),
        "p95_ms": float(np.percentile(values, 95.0)),
        "max_ms": float(np.max(values)),
        "over_deadline_count": int(np.count_nonzero(values > deadline_ms)),
        "deadline_ms": deadline_ms,
        "effective_hz_from_mean": 1000.0 / mean_ms,
        "headroom_at_p95_ms": deadline_ms
        - float(np.percentile(values, 95.0)),
    }


def _representative_results() -> tuple[list[dict[str, Any]], tuple[Any, ...]]:
    runs: list[dict[str, Any]] = []
    benchmark_fixture: tuple[Any, ...] | None = None
    for fixture in FIXTURES:
        reference = _reference(fixture)
        plant = _initialize(reference)
        measurement = _measurement(plant.observe())
        model = _model()
        allocator = default_engineering_cuff_allocator()
        state = _estimated_state(model, measurement)
        action, reconstructed_force = _reconstructed_unsafe_action(
            fixture=fixture,
            plant=plant,
            measurement=measurement,
            state=state,
            model=model,
            reference=reference,
            allocator=allocator,
        )
        context = prepare_executable_force_filter_context(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        )
        result = filter_executable_command(context, action)
        supervisor = TrackBrakeSupervisor()
        decision = supervisor.command(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            track_reference=reference,
            proposed_action_nm=action,
            mpc_status=SAFE_ACTION,
            proposed_filter_result=result,
        )
        preview_execution_identical = False
        if decision.executable_preview is not None:
            plant.apply_executable_command(decision.executable_preview.command)
            preview_execution_identical = bool(
                np.array_equal(
                    plant.last_force,
                    decision.executable_preview.command.force_total_n,
                )
                and np.array_equal(
                    plant.last_moment,
                    decision.executable_preview.command.moment_total_nm,
                )
            )
        runs.append(
            {
                "fixture": fixture.name,
                "fixture_kind": (
                    "analytic_reference_state_and_force_matched_unsafe_action"
                ),
                "historical_force_n": fixture.rejected_executable_force_n,
                "reconstructed_nominal_force_n": reconstructed_force,
                "filter_status": result.status,
                "supervisor_mode": decision.mode,
                "supervisor_status": decision.status,
                "supervisor_trigger": decision.trigger,
                "nominal_wrench_world": result.nominal_preview.allocation[
                    "wrench_world"
                ].tolist(),
                "filtered_wrench_world": result.filtered_preview.allocation[
                    "wrench_world"
                ].tolist(),
                "nominal_executable_force_n": (
                    result.nominal_preview.command.translational_force_norm_n
                ),
                "filtered_executable_force_n": (
                    result.filtered_preview.command.translational_force_norm_n
                ),
                "filtered_force_margin_n": (
                    result.filtered_preview.command.margin_to_force_gate_n
                ),
                "lambda": result.lambda_value,
                "rho_wrench_coordinate_norm": (
                    result.intervention_coordinate_norm
                ),
                "force_intervention_norm_n": (
                    result.force_intervention_norm_n
                ),
                "moment_intervention_norm_nm": (
                    result.moment_intervention_norm_nm
                ),
                "torque_residual_nm": result.torque_residual_nm,
                "torque_exactly_preserved": result.torque_exactly_preserved,
                "preview_equals_execution": preview_execution_identical,
                "brake_fallback_used": decision.mode == "BRAKE",
            }
        )
        if benchmark_fixture is None:
            benchmark_fixture = (
                plant,
                measurement,
                model,
                state,
                reference,
                allocator,
                action,
                context,
            )
    assert benchmark_fixture is not None
    return runs, benchmark_fixture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--filter-samples", type=int, default=1000)
    parser.add_argument("--mpc-warmup", type=int, default=20)
    parser.add_argument("--mpc-samples", type=int, default=200)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    if min(
        args.warmup,
        args.filter_samples,
        args.mpc_warmup,
        args.mpc_samples,
    ) < 0 or min(args.filter_samples, args.mpc_samples) == 0:
        raise ValueError("warmups must be nonnegative and samples positive")

    representative, fixture = _representative_results()
    (
        plant,
        measurement,
        model,
        state,
        reference,
        allocator,
        action,
        prepared_context,
    ) = fixture
    base = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    actions = np.linspace(0.25, 4.0, 32)[:, np.newaxis] * base

    scalar = _timing(
        lambda: filter_executable_command(prepared_context, action),
        warmup=args.warmup,
        samples=args.filter_samples,
        deadline_ms=5.0,
    )
    batch = _timing(
        lambda: filter_executable_commands_batch(prepared_context, actions),
        warmup=args.warmup,
        samples=args.filter_samples,
        deadline_ms=5.0,
    )
    runtime = _timing(
        lambda: filter_executable_command(
            prepare_executable_force_filter_context(
                plant=plant,
                measurement=measurement,
                estimated_state=state,
                human_model=model,
                cuff_allocator=allocator,
                reference=reference,
            ),
            action,
        ),
        warmup=args.warmup,
        samples=args.filter_samples,
        deadline_ms=5.0,
    )

    controller = HumanSpaceMPC(cuff_allocator=allocator)
    dimensions = (
        controller.config.horizon_steps,
        controller.config.candidate_count,
        controller.config.elite_count,
        controller.config.cem_iterations,
    )
    if dimensions != (15, 32, 6, 2):
        raise RuntimeError(f"unexpected MPC dimensions: {dimensions}")

    def solve_once() -> None:
        safety_filter = make_stage4_executable_force_filter(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        )
        selected, diagnostics = controller.solve(
            state,
            FIXTURES[0].failure_time_s,
            lambda _: reference,
            model,
            first_action_batch_preview=safety_filter,
        )
        if selected is None or diagnostics["status"] != SAFE_ACTION:
            raise RuntimeError("fixed MPC profile fixture produced NO_SAFE_ACTION")
        safety_filter.selected_result(selected)

    mpc = _timing(
        solve_once,
        warmup=args.mpc_warmup,
        samples=args.mpc_samples,
        deadline_ms=20.0,
    )
    if mpc["p95_ms"] >= 20.0:
        verdict = "FAIL"
    elif mpc["over_deadline_count"]:
        verdict = "SOFT_PASS"
    else:
        verdict = "PASS"
    payload = {
        "evidence_category": (
            "short_engineering_safety_filter_validation_not_scientific"
        ),
        "fixture_limit": (
            "representative analytic failure-time states and force-matched "
            "unsafe actions; original historical full-state NPZ unavailable"
        ),
        "full_high_rom_rollout_run": False,
        "representative_states": representative,
        "configuration_unchanged": {
            "horizon_steps": dimensions[0],
            "candidate_count": dimensions[1],
            "elite_count": dimensions[2],
            "cem_iterations": dimensions[3],
            "force_gate_n": 200.0,
        },
        "latency": {
            "scalar_prepared_filter": scalar,
            "batch_32_prepared_filter": batch,
            "runtime_context_plus_scalar_filter": runtime,
            "complete_mpc_context_filter_and_solve": mpc,
        },
        "desktop_50_hz_verdict": verdict,
        "hardware_hard_realtime_claimed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
