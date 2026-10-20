#!/usr/bin/env python3
"""Audit synchronous/separated trust semantics on one fixed canonical trace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
    preview_stage4_executable_command,
)
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import ControllerMeasurement, sensor_realism_cases
from traction_mpc_stage4.mpc import HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.reference import continuous_teaching_reference
from traction_mpc_stage4.separated_runtime import SeparatedEstimatorTrustRuntime
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant


def _canonical_measurements(
    trace: dict[str, np.ndarray],
) -> list[ControllerMeasurement]:
    trace_time = np.asarray(trace["time_s"], dtype=float)
    control_time = np.asarray(trace["control_time_s"], dtype=float)
    estimator_age = np.asarray(trace["estimator_measurement_age_s"], dtype=float)
    measured_force = np.asarray(trace["measured_cuff_force_world_n"], dtype=float)
    measured_moment = np.asarray(trace["measured_cuff_moment_world_nm"], dtype=float)
    new_sample = np.asarray(trace["measurement_new_sample"], dtype=bool)
    robot_q = np.asarray(trace["robot_q_rad"], dtype=float)
    robot_dq = np.asarray(trace["robot_dq_rad_s"], dtype=float)
    robot = UR10eTorqueRobot()
    measurements: list[ControllerMeasurement] = []
    for control_index in range(0, len(control_time), 4):
        arrival_time = float(control_time[control_index])
        sample_time = arrival_time - float(estimator_age[control_index])
        trace_index = min(
            int(np.searchsorted(trace_time, sample_time + 0.5e-3)),
            len(trace_time) - 1,
        )
        q = robot_q[trace_index]
        dq = robot_dq[trace_index]
        robot.set_configuration(q, dq)
        pose = robot.attachment_pose()
        twist = robot.attachment_jacobian() @ dq
        measurements.append(
            ControllerMeasurement(
                arrival_time_s=arrival_time,
                sample_time_s=sample_time,
                robot_q_rad=q.copy(),
                robot_dq_rad_s=dq.copy(),
                attachment_position_m=pose.translation.copy(),
                attachment_rotation_matrix=pose.rotation.copy(),
                attachment_velocity_m_s=twist[:3].copy(),
                attachment_angular_velocity_rad_s=twist[3:].copy(),
                cuff_force_vector_n=measured_force[control_index].copy(),
                cuff_moment_vector_nm=measured_moment[control_index].copy(),
                new_sample=bool(new_sample[control_index]),
            )
        )
    return measurements


def _make_estimator(initial: ControllerMeasurement):
    return OnlineSingleChallengerTrustEstimator(
        initial,
        continuous_teaching_reference(0.0).q_rad,
        measurement_case=sensor_realism_cases()[2],
        apply_qualified_model=True,
    )


def _run_synchronous(measurements: list[ControllerMeasurement]):
    estimator = _make_estimator(measurements[0])
    execution = ReferenceExecutionLayer(
        continuous_teaching_reference, confidence_aware=True
    )
    for measurement in measurements:
        _, diagnostics = estimator.observe_measurement(measurement)
        execution.update_from_estimator(
            measurement.arrival_time_s,
            estimator,
            diagnostics["geometry"],
            diagnostics["dynamics"],
        )
    return estimator, execution


def _run_separated(measurements: list[ControllerMeasurement]):
    estimator = _make_estimator(measurements[0])
    execution = ReferenceExecutionLayer(
        continuous_teaching_reference, confidence_aware=True
    )
    runtime = SeparatedEstimatorTrustRuntime(
        estimator, reference_execution=execution
    )
    true_human, _ = registered_cold_start_perturbed_human()
    plant = SensorBoundaryStage4Plant(true_human)
    plant.reset(continuous_teaching_reference(0.0).q_rad)
    plant.neutral_robot_q = measurements[0].robot_q_rad.copy()
    allocator = default_engineering_cuff_allocator()
    controller = HumanSpaceMPC(cuff_allocator=allocator)
    fast_path_s: list[float] = []
    no_safe_action_count = 0
    for cycle_index, measurement in enumerate(measurements):
        started = perf_counter()
        snapshot = runtime.activate_latest(
            control_cycle_index=cycle_index,
            control_time_s=measurement.arrival_time_s,
        )
        runtime.submit(measurement)
        state = snapshot.model.geometry.estimate_state(
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            measurement.attachment_velocity_m_s,
            measurement.attachment_angular_velocity_rad_s,
        )
        if snapshot.reference_execution is None:
            raise RuntimeError("missing published reference execution")
        active_reference = snapshot.reference_execution.reference
        reference = active_reference(measurement.arrival_time_s)
        action, _ = controller.solve(
            state,
            measurement.arrival_time_s,
            active_reference,
            snapshot.model,
            first_action_batch_preview=make_stage4_first_action_batch_preview(
                plant=plant,
                measurement=measurement,
                estimated_state=state,
                human_model=snapshot.model,
                cuff_allocator=allocator,
                reference=reference,
            ),
        )
        if action is None:
            no_safe_action_count += 1
        else:
            preview_stage4_executable_command(
                plant=plant,
                measurement=measurement,
                action_nm=action,
                estimated_state=state,
                human_model=snapshot.model,
                cuff_allocator=allocator,
                reference=reference,
            )
        fast_path_s.append(perf_counter() - started)
    runtime.drain()
    runtime.activate_latest(
        control_cycle_index=len(measurements),
        control_time_s=measurements[-1].arrival_time_s + 0.020,
    )
    runtime.close()
    return estimator, execution, runtime, fast_path_s, no_safe_action_count


def _assert_history_equal(sync: Any, separated: Any) -> None:
    if len(sync.raw_history) != len(separated.raw_history):
        raise AssertionError("raw estimator history length changed")
    for expected_index, (left, right) in enumerate(
        zip(sync.raw_history, separated.raw_history, strict=True)
    ):
        if left.keys() != right.keys():
            raise AssertionError("raw estimator history schema changed")
        for key in left:
            if isinstance(left[key], np.ndarray):
                np.testing.assert_array_equal(left[key], right[key])
            elif left[key] != right[key]:
                raise AssertionError(
                    f"history mismatch at {expected_index}:{key}"
                )


def _normalize(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    with np.load(args.trace) as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    measurements = _canonical_measurements(trace)
    synchronous, synchronous_execution = _run_synchronous(measurements)
    (
        separated,
        separated_execution,
        runtime,
        fast_path_s,
        no_safe_action_count,
    ) = _run_separated(measurements)

    _assert_history_equal(synchronous, separated)
    np.testing.assert_array_equal(
        synchronous.geometry_identifier.last_valid,
        separated.geometry_identifier.last_valid,
    )
    np.testing.assert_array_equal(
        synchronous.dynamic_identifier.last_valid,
        separated.dynamic_identifier.last_valid,
    )
    np.testing.assert_array_equal(
        synchronous.incumbent_beta,
        separated.incumbent_beta,
    )
    for name in ("challengers", "qualifications", "control_promotions"):
        if _normalize(getattr(synchronous, name)) != _normalize(
            getattr(separated, name)
        ):
            raise AssertionError(f"scientific lifecycle changed: {name}")
    final_time = measurements[-1].arrival_time_s
    if _normalize(synchronous_execution.summary(final_time)) != _normalize(
        separated_execution.summary(final_time)
    ):
        raise AssertionError("confidence pacing lifecycle changed")

    worker_indices = [record.input_index for record in runtime.slow_records]
    if worker_indices != list(range(len(measurements))):
        raise AssertionError("slow worker dropped or reordered estimator inputs")
    promotion_activation_delay_ms = []
    for epoch, promotion in enumerate(separated.control_promotions, start=1):
        activation = next(
            (
                record
                for record in runtime.activation_records
                if record.incumbent_epoch >= epoch
            ),
            None,
        )
        if activation is None:
            raise AssertionError("trusted incumbent was never activated")
        promotion_activation_delay_ms.append(
            1000.0
            * max(
                0.0,
                activation.control_time_s - float(promotion["promotion_time_s"]),
            )
        )
    fast_ms = 1000.0 * np.asarray(fast_path_s)
    print(
        json.dumps(
            {
                "evidence_category": "engineering_replay_audit_not_scientific",
                "scientific_equivalent": True,
                "measurement_count": len(measurements),
                "raw_valid_history_count": len(synchronous.raw_history),
                "challenger_count": len(synchronous.challengers),
                "qualification_count": len(synchronous.qualifications),
                "promotion_count": len(synchronous.control_promotions),
                "rejection_count": sum(
                    item["status"] == "rejected_no_statistical_support"
                    for item in synchronous.challengers
                ),
                "worker_input_indices_exact": True,
                "incumbent_beta_exact": True,
                "challengers_exact": True,
                "trust_verdicts_exact": True,
                "validation_blocks_exact": True,
                "promotion_sequence_exact": True,
                "confidence_pacing_state_exact": True,
                "promotion_activation_delay_ms": promotion_activation_delay_ms,
                "no_safe_action_count": no_safe_action_count,
                "fast_path_without_measurement_preprocessing": {
                    "count": len(fast_ms),
                    "mean_ms": float(np.mean(fast_ms)),
                    "median_ms": float(np.median(fast_ms)),
                    "p95_ms": float(np.percentile(fast_ms, 95.0)),
                    "max_ms": float(np.max(fast_ms)),
                    "over_20_ms_count": int(np.count_nonzero(fast_ms > 20.0)),
                },
                "slow_worker": runtime.timing_summary(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
