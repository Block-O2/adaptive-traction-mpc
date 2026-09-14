"""Focused offline prediction/execution audit for Goal-MPC smoke attempt 02."""

from __future__ import annotations

from collections import Counter
import cProfile
import csv
import hashlib
import io
import json
from pathlib import Path
import pstats
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
    preview_stage4_executable_command,
)
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor

from .baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from .goal_mpc import GoalDirectedHumanSpaceMPC, local_command_reference
from .human import STAGE5_HUMAN
from .task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, start_episode
from .task_observation import task_observation_from_deployable_estimator_path


REQUIRED_PRIMARY_FIELDS = (
    "time_s",
    "estimated_state_rad_rad_s",
    "evaluation_human_q_rad",
    "evaluation_human_dq_rad_s",
    "physical_cuff_force_world_n",
    "physical_cuff_moment_world_nm",
    "executed_generalized_action_nm",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rotation_error_rad(target: np.ndarray, current: np.ndarray) -> float:
    return float(
        np.linalg.norm(Rotation.from_matrix(target @ current.T).as_rotvec())
    )


def _fixed_runtime() -> tuple[
    Stage5SensorBoundaryPlant,
    list[CausalMeasurementLayer],
    FixedStage5Estimator,
    Any,
    Any,
    TrackBrakeSupervisor,
]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad, dtype=float))
    ideal = MeasurementCase(
        name="stage5_goal_mpc_attempt02_consistency_audit",
        update_rate_hz=200.0,
        latency_s=0.0,
        preprocessing_enabled=False,
    )
    layers = [CausalMeasurementLayer(ideal, truth) for _ in range(3)]
    initial = layers[0].current
    estimator = FixedStage5Estimator(
        initial.attachment_position_m,
        initial.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad, dtype=float),
    )
    estimator.observe(
        time_s=initial.sample_time_s,
        position_world_m=initial.attachment_position_m,
        rotation_world_from_cuff=initial.attachment_rotation_matrix,
        linear_velocity_world_m_s=initial.attachment_velocity_m_s,
        angular_velocity_world_rad_s=initial.attachment_angular_velocity_rad_s,
        force_world_n=initial.cuff_force_vector_n,
        moment_world_nm=initial.cuff_moment_vector_nm,
        bed_contaminated=False,
    )
    plant.neutral_robot_q = initial.robot_q_rad.copy()
    return (
        plant,
        layers,
        estimator,
        estimator.model,
        default_engineering_cuff_allocator(),
        TrackBrakeSupervisor(),
    )


def _estimate_variants(plant: Stage5SensorBoundaryPlant, model: Any, truth: Any):
    robot = plant._attachment_state(plant.attachment_site_id)
    human = plant._attachment_state(plant.sleeve_site_id)
    geometry = model.geometry
    variants = {
        "raw_robot_side": geometry.estimate_state(
            robot.position_world_m,
            robot.rotation_world,
            robot.velocity_world_m_s,
            robot.angular_velocity_world_rad_s,
        ),
        "translation_corrected_only": geometry.estimate_state(
            human.position_world_m,
            robot.rotation_world,
            human.velocity_world_m_s,
            robot.angular_velocity_world_rad_s,
        ),
        "rotation_corrected_only": geometry.estimate_state(
            robot.position_world_m,
            human.rotation_world,
            robot.velocity_world_m_s,
            human.angular_velocity_world_rad_s,
        ),
        "full_human_side_offline": geometry.estimate_state(
            human.position_world_m,
            human.rotation_world,
            human.velocity_world_m_s,
            human.angular_velocity_world_rad_s,
        ),
    }
    target = np.concatenate(
        [np.asarray(truth.human_q_rad), np.asarray(truth.human_dq_rad_s)]
    )
    return variants, target, robot, human


def replay_saved_action_sequence(primary: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Replay only the saved actions; MuJoCo truth remains audit-only."""

    time_s = np.asarray(primary["time_s"], dtype=float)
    saved_actions = np.asarray(primary["executed_generalized_action_nm"], dtype=float)
    if len(time_s) < 2 or saved_actions.shape != (len(time_s), 2):
        raise ValueError("primary trace has an invalid time/action shape")
    if not np.allclose(np.diff(time_s), 0.005, rtol=0.0, atol=1.0e-12):
        raise ValueError("attempt-02 replay requires the saved 5 ms sample grid")

    plant, layers, estimator, model, allocator, supervisor = _fixed_runtime()
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    state_variants: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "raw_robot_side",
            "translation_corrected_only",
            "rotation_corrected_only",
            "full_human_side_offline",
        )
    }
    truth_state: list[np.ndarray] = []
    observation_age: list[float] = []
    interface_translation: list[np.ndarray] = []
    interface_velocity: list[np.ndarray] = []
    interface_rotation: list[np.ndarray] = []
    interface_angular_velocity: list[np.ndarray] = []
    spring_force: list[np.ndarray] = []
    damping_force: list[np.ndarray] = []
    rotation_spring_moment: list[np.ndarray] = []
    rotation_damping_moment: list[np.ndarray] = []
    transport_moment: list[np.ndarray] = []
    physical_force: list[np.ndarray] = []
    physical_moment: list[np.ndarray] = []
    truth_forward_position_residual: list[float] = []
    truth_forward_rotation_residual: list[float] = []

    command_time: list[float] = []
    requested_action: list[np.ndarray] = []
    allocator_wrench: list[np.ndarray] = []
    force_position: list[np.ndarray] = []
    force_velocity: list[np.ndarray] = []
    force_allocator: list[np.ndarray] = []
    force_total: list[np.ndarray] = []
    raw_force_position: list[np.ndarray] = []
    raw_force_velocity: list[np.ndarray] = []
    feedback_clip_delta: list[np.ndarray] = []
    moment_orientation: list[np.ndarray] = []
    moment_angular_velocity: list[np.ndarray] = []
    moment_allocator: list[np.ndarray] = []
    moment_total: list[np.ndarray] = []
    executed_action: list[np.ndarray] = []
    executable_force_margin: list[float] = []
    joint_torque_clip_norm: list[float] = []
    safety_status: list[str] = []
    safety_lambda: list[float] = []
    safety_intervention: list[float] = []
    old_velocity_equivalent_delta: list[np.ndarray] = []

    for index in range(len(time_s)):
        truth = plant.observe()
        estimator_measurement, mpc_measurement, low_level_measurement = (
            layer.update(truth) for layer in layers
        )
        if index % 4 == 0:
            estimator.observe(
                time_s=estimator_measurement.sample_time_s,
                position_world_m=estimator_measurement.attachment_position_m,
                rotation_world_from_cuff=(
                    estimator_measurement.attachment_rotation_matrix
                ),
                linear_velocity_world_m_s=(
                    estimator_measurement.attachment_velocity_m_s
                ),
                angular_velocity_world_rad_s=(
                    estimator_measurement.attachment_angular_velocity_rad_s
                ),
                force_world_n=estimator_measurement.cuff_force_vector_n,
                moment_world_nm=estimator_measurement.cuff_moment_vector_nm,
                bed_contaminated=False,
            )
            model = estimator.model
        observation = task_observation_from_deployable_estimator_path(
            mpc_measurement,
            model,
            human_model_version="stage5_fixed_registered_human_v1_audit_replay",
        )
        variants, target, robot, human = _estimate_variants(plant, model, truth)
        for name, state in variants.items():
            state_variants[name].append(np.asarray(state, dtype=float).copy())
        truth_state.append(target)
        observation_age.append(observation.age_s)

        interface = plant._evaluate_current_interface()
        rotation_world_from_human = human.rotation_world
        stiffness = np.asarray(plant.interface_parameters.translation_stiffness_n_m)
        damping = np.asarray(plant.interface_parameters.translation_damping_ns_m)
        spring = rotation_world_from_human @ (
            stiffness * interface.displacement_human_m
        )
        damp = rotation_world_from_human @ (
            damping * interface.velocity_human_m_s
        )
        rotational_spring = rotation_world_from_human @ (
            plant.interface_parameters.rotation_stiffness_nm_rad
            * interface.rotation_error_human_rad
        )
        rotational_damp = rotation_world_from_human @ (
            plant.interface_parameters.rotation_damping_nms_rad
            * interface.angular_velocity_human_rad_s
        )
        transport = np.cross(
            robot.position_world_m - human.position_world_m,
            spring + damp,
        )
        interface_translation.append(interface.displacement_human_m.copy())
        interface_velocity.append(interface.velocity_human_m_s.copy())
        interface_rotation.append(interface.rotation_error_human_rad.copy())
        interface_angular_velocity.append(
            interface.angular_velocity_human_rad_s.copy()
        )
        spring_force.append(spring)
        damping_force.append(damp)
        rotation_spring_moment.append(rotational_spring)
        rotation_damping_moment.append(rotational_damp)
        transport_moment.append(transport)
        physical_force.append(np.asarray(truth.cuff_force_vector_n).copy())
        physical_moment.append(np.asarray(truth.cuff_moment_vector_nm).copy())
        truth_pose = model.geometry.cuff_pose(truth.human_q_rad)
        truth_forward_position_residual.append(
            float(np.linalg.norm(truth_pose.translation - human.position_world_m))
        )
        truth_forward_rotation_residual.append(
            _rotation_error_rad(truth_pose.rotation, human.rotation_world)
        )

        if index == len(time_s) - 1:
            break
        # The action stored at sample i+1 is the action applied over [i, i+1].
        action = saved_actions[index + 1].copy()
        estimated_state = observation.as_array()
        reference = local_command_reference(estimated_state, action, model)
        status = SAFE_ACTION if index % 4 == 0 else None
        decision = supervisor.command(
            plant=plant,
            measurement=low_level_measurement,
            estimated_state=estimated_state,
            human_model=model,
            cuff_allocator=allocator,
            track_reference=reference,
            proposed_action_nm=action,
            mpc_status=status,
            proposed_filter_result=None,
        )
        if decision.executable_preview is None or decision.action_nm is None:
            raise RuntimeError("saved safe action did not replay through execution")
        preview = decision.executable_preview
        command = preview.command
        metadata = decision.safety_filter or {}
        control_velocity = plant.control_feedback_velocity_snapshot(
            low_level_measurement
        ).linear_velocity_world_m_s
        history_velocity = np.asarray(
            low_level_measurement.attachment_velocity_m_s, dtype=float
        )

        command_time.append(float(time_s[index]))
        requested_action.append(action)
        allocator_wrench.append(np.asarray(preview.allocation["wrench_world"]).copy())
        force_position.append(command.force_position_n.copy())
        force_velocity.append(command.force_velocity_n.copy())
        force_allocator.append(command.force_allocator_n.copy())
        force_total.append(command.force_total_n.copy())
        raw_force_position.append(command.raw_force_position_n.copy())
        raw_force_velocity.append(command.raw_force_velocity_n.copy())
        feedback_clip_delta.append(command.feedback_force_clipping_delta_n.copy())
        moment_orientation.append(command.moment_orientation_nm.copy())
        moment_angular_velocity.append(command.moment_angular_velocity_nm.copy())
        moment_allocator.append(command.moment_allocator_nm.copy())
        moment_total.append(command.moment_total_nm.copy())
        executed_action.append(decision.action_nm.copy())
        executable_force_margin.append(float(command.margin_to_force_gate_n))
        joint_torque_clip_norm.append(
            float(
                np.linalg.norm(
                    command.unclipped_joint_torque_nm
                    - command.joint_torque_command_nm
                )
            )
        )
        safety_status.append(str(metadata.get("status", "NONE")))
        safety_lambda.append(float(metadata.get("lambda", np.nan)))
        safety_intervention.append(
            float(metadata.get("intervention_coordinate_norm", np.nan))
        )
        old_velocity_equivalent_delta.append(
            DEFAULT_LOW_LEVEL_COMMAND_GAINS.velocity_ns_per_m
            * (control_velocity - history_velocity)
        )

        plant.apply_executable_command(command)
        for _ in range(20):
            truth = plant.step()

    trace = {
        "time_s": time_s,
        "truth_state_rad_rad_s": np.asarray(truth_state),
        "observation_age_s": np.asarray(observation_age),
        "interface_translation_human_m": np.asarray(interface_translation),
        "interface_velocity_human_m_s": np.asarray(interface_velocity),
        "interface_rotation_human_rad": np.asarray(interface_rotation),
        "interface_angular_velocity_human_rad_s": np.asarray(
            interface_angular_velocity
        ),
        "interface_spring_force_world_n": np.asarray(spring_force),
        "interface_damping_force_world_n": np.asarray(damping_force),
        "interface_rotation_spring_moment_world_nm": np.asarray(
            rotation_spring_moment
        ),
        "interface_rotation_damping_moment_world_nm": np.asarray(
            rotation_damping_moment
        ),
        "interface_transport_moment_world_nm": np.asarray(transport_moment),
        "replayed_physical_force_world_n": np.asarray(physical_force),
        "replayed_physical_moment_world_nm": np.asarray(physical_moment),
        "truth_forward_position_residual_m": np.asarray(
            truth_forward_position_residual
        ),
        "truth_forward_rotation_residual_rad": np.asarray(
            truth_forward_rotation_residual
        ),
        "command_time_s": np.asarray(command_time),
        "command_effect_time_s": time_s[1:].copy(),
        "requested_action_nm": np.asarray(requested_action),
        "allocator_wrench_world": np.asarray(allocator_wrench),
        "executable_force_position_world_n": np.asarray(force_position),
        "executable_force_velocity_world_n": np.asarray(force_velocity),
        "executable_force_allocator_world_n": np.asarray(force_allocator),
        "executable_force_total_world_n": np.asarray(force_total),
        "executable_raw_force_position_world_n": np.asarray(raw_force_position),
        "executable_raw_force_velocity_world_n": np.asarray(raw_force_velocity),
        "executable_feedback_clipping_delta_world_n": np.asarray(
            feedback_clip_delta
        ),
        "executable_moment_orientation_world_nm": np.asarray(moment_orientation),
        "executable_moment_angular_velocity_world_nm": np.asarray(
            moment_angular_velocity
        ),
        "executable_moment_allocator_world_nm": np.asarray(moment_allocator),
        "executable_moment_total_world_nm": np.asarray(moment_total),
        "executed_action_nm": np.asarray(executed_action),
        "executable_force_margin_n": np.asarray(executable_force_margin),
        "joint_torque_clipping_norm_nm": np.asarray(joint_torque_clip_norm),
        "safety_filter_status": np.asarray(safety_status, dtype=str),
        "safety_filter_lambda": np.asarray(safety_lambda),
        "safety_filter_intervention_coordinate_norm": np.asarray(
            safety_intervention
        ),
        "old_history_velocity_equivalent_force_delta_world_n": np.asarray(
            old_velocity_equivalent_delta
        ),
    }
    for name, values in state_variants.items():
        trace[f"state_{name}_rad_rad_s"] = np.asarray(values)
    return trace


def _state_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    truth = trace["truth_state_rad_rad_s"]
    result: dict[str, Any] = {}
    for label in (
        "raw_robot_side",
        "translation_corrected_only",
        "rotation_corrected_only",
        "full_human_side_offline",
    ):
        error = trace[f"state_{label}_rad_rad_s"] - truth
        result[label] = {
            "q_rmse_deg": np.degrees(
                np.sqrt(np.mean(error[:, :2] ** 2, axis=0))
            ).tolist(),
            "dq_rmse_deg_s": np.degrees(
                np.sqrt(np.mean(error[:, 2:] ** 2, axis=0))
            ).tolist(),
            "q_peak_abs_deg": np.degrees(
                np.max(np.abs(error[:, :2]), axis=0)
            ).tolist(),
            "dq_peak_abs_deg_s": np.degrees(
                np.max(np.abs(error[:, 2:]), axis=0)
            ).tolist(),
            "abort_error_q_dq_deg_deg_s": np.degrees(error[-1]).tolist(),
        }
    return result


def _profile_goal_mpc() -> tuple[dict[str, Any], str]:
    plant, layers, _, model, allocator, _ = _fixed_runtime()
    measurement = layers[1].current
    observation = task_observation_from_deployable_estimator_path(
        measurement,
        model,
        human_model_version="stage5_fixed_registered_human_v1_runtime_profile",
    )
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    task_state = start_episode(
        spec,
        observation.as_array()[:2],
        observation.as_array()[2:],
        np.zeros(2),
    )
    reference = local_command_reference(observation.as_array(), np.zeros(2), model)

    def scalar_preview(action_nm: np.ndarray):
        return preview_stage4_executable_command(
            plant=plant,
            measurement=measurement,
            action_nm=action_nm,
            estimated_state=observation.as_array(),
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        ).command

    batch_preview = make_stage4_first_action_batch_preview(
        plant=plant,
        measurement=measurement,
        estimated_state=observation.as_array(),
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    cases = (
        (
            "current_batched_population_scalar_screening",
            "batched",
            {"first_action_preview": scalar_preview},
        ),
        (
            "diagnostic_scalar_population_scalar_screening",
            "scalar",
            {"first_action_preview": scalar_preview},
        ),
        (
            "offline_hypothesis_batched_population_batch_screening",
            "batched",
            {"first_action_batch_preview": batch_preview},
        ),
    )
    profile: dict[str, Any] = {
        "configuration_unchanged": {
            "prediction_dt_s": 0.02,
            "horizon_steps": 15,
            "candidate_count": 32,
            "cem_iterations": 2,
            "elite_count": 6,
        },
        "timing_repetitions_after_one_warmup": 5,
        "cases": {},
        "simulated_action_hold_timing_uses_wall_clock": False,
    }
    for name, implementation, solve_kwargs in cases:
        controller = GoalDirectedHumanSpaceMPC(
            cuff_allocator=allocator,
            implementation=implementation,
            record_timing_breakdown=True,
        )
        elapsed_ms: list[float] = []
        breakdowns: list[dict[str, float]] = []
        for repetition in range(6):
            started = perf_counter()
            _, diagnostics = controller.solve_goal(
                observation,
                task_state,
                spec,
                model,
                **solve_kwargs,
            )
            elapsed = 1000.0 * (perf_counter() - started)
            if repetition:
                elapsed_ms.append(elapsed)
                breakdowns.append(diagnostics["implementation_timing_ms"])
        keys = sorted({key for item in breakdowns for key in item})
        profile["cases"][name] = {
            "wall_mean_ms": float(np.mean(elapsed_ms)),
            "wall_p95_ms": float(np.percentile(elapsed_ms, 95)),
            "wall_max_ms": float(np.max(elapsed_ms)),
            "implementation_timing_mean_ms": {
                key: float(np.mean([item.get(key, 0.0) for item in breakdowns]))
                for key in keys
            },
        }

    controller = GoalDirectedHumanSpaceMPC(
        cuff_allocator=allocator,
        implementation="batched",
        record_timing_breakdown=True,
    )
    profiler = cProfile.Profile()
    profiler.enable()
    controller.solve_goal(
        observation,
        task_state,
        spec,
        model,
        first_action_preview=scalar_preview,
    )
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
        "cumtime"
    ).print_stats(30)
    profile["cprofile_total_function_calls"] = int(
        sum(entry.callcount for entry in profiler.getstats())
    )
    return profile, stream.getvalue()


def _write_state_table(path: Path, trace: dict[str, np.ndarray]) -> None:
    times = trace["time_s"]
    indices = sorted(
        {
            int(np.argmin(np.abs(times - target)))
            for target in (0.0, 0.05, 0.10, 0.15, 0.20, times[-1])
        }
    )
    truth = trace["truth_state_rad_rad_s"]
    raw = trace["state_raw_robot_side_rad_rad_s"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "time_s",
                "q1_error_deg",
                "q2_error_deg",
                "dq1_error_deg_s",
                "dq2_error_deg_s",
                "translation_deformation_norm_mm",
                "rotation_deformation_norm_deg",
            ]
        )
        for index in indices:
            error = np.degrees(raw[index] - truth[index])
            writer.writerow(
                [
                    float(times[index]),
                    *map(float, error),
                    float(
                        1000.0
                        * np.linalg.norm(
                            trace["interface_translation_human_m"][index]
                        )
                    ),
                    float(
                        np.degrees(
                            np.linalg.norm(
                                trace["interface_rotation_human_rad"][index]
                            )
                        )
                    ),
                ]
            )


def _write_force_table(path: Path, trace: dict[str, np.ndarray]) -> None:
    effect_time = trace["command_effect_time_s"]
    selected = np.flatnonzero(effect_time >= effect_time[-1] - 0.035 - 1.0e-12)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "command_time_s",
                "effect_time_s",
                "action_q1_nm",
                "action_q2_nm",
                "allocator_force_norm_n",
                "position_feedback_norm_n",
                "velocity_feedback_norm_n",
                "executable_force_norm_n",
                "interface_spring_force_norm_n",
                "interface_damping_force_norm_n",
                "physical_force_norm_n",
                "safety_filter_status",
                "joint_torque_clip_norm_nm",
            ]
        )
        for index in selected:
            writer.writerow(
                [
                    float(trace["command_time_s"][index]),
                    float(effect_time[index]),
                    *map(float, trace["requested_action_nm"][index]),
                    float(
                        np.linalg.norm(
                            trace["executable_force_allocator_world_n"][index]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["executable_force_position_world_n"][index]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["executable_force_velocity_world_n"][index]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["executable_force_total_world_n"][index]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["interface_spring_force_world_n"][index + 1]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["interface_damping_force_world_n"][index + 1]
                        )
                    ),
                    float(
                        np.linalg.norm(
                            trace["replayed_physical_force_world_n"][index + 1]
                        )
                    ),
                    str(trace["safety_filter_status"][index]),
                    float(trace["joint_torque_clipping_norm_nm"][index]),
                ]
            )


def _write_plots(output_dir: Path, trace: dict[str, np.ndarray]) -> None:
    time_s = trace["time_s"]
    truth = trace["truth_state_rad_rad_s"]
    labels = (
        ("raw_robot_side", "robot-side estimate", "tab:red"),
        ("translation_corrected_only", "offline translation correction", "tab:blue"),
        ("rotation_corrected_only", "offline rotation correction", "tab:orange"),
        ("full_human_side_offline", "offline full human-side pose", "tab:green"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.2), sharex=True)
    names = ("q1 error [deg]", "q2 error [deg]", "dq1 error [deg/s]", "dq2 error [deg/s]")
    for component, axis in enumerate(axes.flat):
        for key, label, color in labels:
            error = np.degrees(trace[f"state_{key}_rad_rad_s"][:, component] - truth[:, component])
            axis.plot(time_s, error, label=label, color=color, linewidth=1.4)
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.axvline(time_s[-1], color="black", linestyle="--", linewidth=0.8)
        axis.set_ylabel(names[component])
        axis.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_xlabel("time [s]")
    axes[1, 1].set_xlabel("time [s]")
    fig.suptitle("Goal-MPC attempt 02: synchronized estimator-minus-Human state error")
    fig.tight_layout()
    fig.savefig(output_dir / "state_error_time.png", dpi=180)
    plt.close(fig)

    effect_time = trace["command_effect_time_s"]
    norm = lambda value: np.linalg.norm(value, axis=1)
    fig, axes = plt.subplots(2, 1, figsize=(11.0, 7.2), sharex=True)
    axes[0].plot(
        effect_time,
        norm(trace["executable_force_allocator_world_n"]),
        label="allocator request",
    )
    axes[0].plot(
        effect_time,
        norm(trace["executable_force_position_world_n"]),
        label="position feedback",
    )
    axes[0].plot(
        effect_time,
        norm(trace["executable_force_velocity_world_n"]),
        label="velocity feedback",
    )
    axes[0].plot(
        effect_time,
        norm(trace["executable_force_total_world_n"]),
        label="executable total",
        linewidth=2.0,
    )
    axes[0].axhline(200.0, color="black", linestyle="--", label="engineering gate")
    axes[0].set_ylabel("command component norm [N]")
    axes[0].legend(ncol=3, fontsize=8)
    axes[0].grid(alpha=0.25)
    axes[1].plot(
        effect_time,
        norm(trace["interface_spring_force_world_n"][1:]),
        label="interface Kx",
    )
    axes[1].plot(
        effect_time,
        norm(trace["interface_damping_force_world_n"][1:]),
        label="interface Dv",
    )
    axes[1].plot(
        effect_time,
        norm(trace["replayed_physical_force_world_n"][1:]),
        label="physical Kx+Dv",
        linewidth=2.0,
    )
    axes[1].axhline(200.0, color="black", linestyle="--")
    axes[1].set_ylabel("interface/physical norm [N]")
    axes[1].set_xlabel("effect time [s]")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)
    fig.suptitle("Saved-action replay: command-to-interface synchronized force chain")
    fig.tight_layout()
    fig.savefig(output_dir / "force_decomposition_time.png", dpi=180)
    plt.close(fig)


def _vector_record(value: np.ndarray) -> list[float]:
    return [float(item) for item in np.asarray(value, dtype=float)]


def run_goal_mpc_consistency_audit(
    primary_trace_path: Path,
    primary_summary_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    primary_trace_path = Path(primary_trace_path)
    primary_summary_path = Path(primary_summary_path)
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite audit output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    with np.load(primary_trace_path) as archive:
        missing = sorted(set(REQUIRED_PRIMARY_FIELDS) - set(archive.files))
        if missing:
            raise KeyError(f"primary trace is missing fields: {missing}")
        primary = {key: np.asarray(archive[key]).copy() for key in archive.files}
    primary_summary = json.loads(primary_summary_path.read_text(encoding="utf-8"))
    if primary_summary.get("abort_reason") != "PHYSICAL_CUFF_FORCE_GATE":
        raise ValueError("the focused audit requires attempt-02 force-gate evidence")

    replay = replay_saved_action_sequence(primary)
    state_metrics = _state_metrics(replay)
    primary_truth = np.column_stack(
        [primary["evaluation_human_q_rad"], primary["evaluation_human_dq_rad_s"]]
    )
    replay_force_delta = replay["replayed_physical_force_world_n"] - primary[
        "physical_cuff_force_world_n"
    ]
    replay_moment_delta = replay["replayed_physical_moment_world_nm"] - primary[
        "physical_cuff_moment_world_nm"
    ]
    replay_state_delta = replay["state_raw_robot_side_rad_rad_s"] - primary[
        "estimated_state_rad_rad_s"
    ]
    replay_truth_delta = replay["truth_state_rad_rad_s"] - primary_truth
    physical_force = replay["replayed_physical_force_world_n"]
    physical_moment = replay["replayed_physical_moment_world_nm"]
    force_identity = (
        replay["interface_spring_force_world_n"]
        + replay["interface_damping_force_world_n"]
    )
    moment_identity = (
        replay["interface_rotation_spring_moment_world_nm"]
        + replay["interface_rotation_damping_moment_world_nm"]
        + replay["interface_transport_moment_world_nm"]
    )
    abort_command = len(replay["command_time_s"]) - 1
    abort_sample = len(replay["time_s"]) - 1
    runtime_profile, cprofile_text = _profile_goal_mpc()

    summary = {
        "schema": "stage5_goal_mpc_prediction_execution_consistency_audit_v1",
        "evidence_category": "focused_engineering_audit",
        "primary_evidence": {
            "trace_path": str(primary_trace_path),
            "trace_sha256": _sha256(primary_trace_path),
            "summary_path": str(primary_summary_path),
            "summary_sha256": _sha256(primary_summary_path),
            "abort_time_s": float(primary["time_s"][-1]),
            "abort_reason": primary_summary["abort_reason"],
        },
        "targeted_replay": {
            "scope": "saved actions only, 0.215 s, unchanged Plant-v1 and execution chain",
            "controller_or_parameter_retuning": False,
            "truth_used_by_control": False,
            "maximum_primary_replay_force_vector_delta_n": float(
                np.max(np.abs(replay_force_delta))
            ),
            "maximum_primary_replay_moment_vector_delta_nm": float(
                np.max(np.abs(replay_moment_delta))
            ),
            "maximum_primary_replay_estimated_state_delta": float(
                np.max(np.abs(replay_state_delta))
            ),
            "maximum_primary_replay_truth_state_delta": float(
                np.max(np.abs(replay_truth_delta))
            ),
        },
        "state_discrepancy": {
            "synchronized_metrics": state_metrics,
            "peak_translation_deformation_mm": float(
                1000.0
                * np.max(
                    np.linalg.norm(
                        replay["interface_translation_human_m"], axis=1
                    )
                )
            ),
            "abort_translation_deformation_human_mm": _vector_record(
                1000.0 * replay["interface_translation_human_m"][abort_sample]
            ),
            "peak_rotation_deformation_deg": float(
                np.degrees(
                    np.max(
                        np.linalg.norm(
                            replay["interface_rotation_human_rad"], axis=1
                        )
                    )
                )
            ),
            "abort_rotation_deformation_human_deg": _vector_record(
                np.degrees(replay["interface_rotation_human_rad"][abort_sample])
            ),
            "maximum_observation_age_ms": float(
                1000.0 * np.max(replay["observation_age_s"])
            ),
            "measurement_preprocessing_enabled": False,
            "measurement_latency_s": 0.0,
            "maximum_truth_forward_position_residual_m": float(
                np.max(replay["truth_forward_position_residual_m"])
            ),
            "maximum_truth_forward_rotation_residual_rad": float(
                np.max(replay["truth_forward_rotation_residual_rad"])
            ),
            "interpretation": (
                "deterministic semantic mismatch: deployable estimator interprets the "
                "robot-side cuff pose/twist as the Human-side shank cuff state while "
                "Plant v1 permits finite relative translation and rotation"
            ),
        },
        "force_execution_discrepancy": {
            "abort_requested_action_nm": _vector_record(
                replay["requested_action_nm"][abort_command]
            ),
            "abort_allocator_wrench_world": _vector_record(
                replay["allocator_wrench_world"][abort_command]
            ),
            "abort_position_feedback_world_n": _vector_record(
                replay["executable_force_position_world_n"][abort_command]
            ),
            "abort_velocity_feedback_world_n": _vector_record(
                replay["executable_force_velocity_world_n"][abort_command]
            ),
            "abort_executable_total_force_world_n": _vector_record(
                replay["executable_force_total_world_n"][abort_command]
            ),
            "abort_executable_total_force_norm_n": float(
                np.linalg.norm(
                    replay["executable_force_total_world_n"][abort_command]
                )
            ),
            "abort_interface_spring_force_world_n": _vector_record(
                replay["interface_spring_force_world_n"][abort_sample]
            ),
            "abort_interface_damping_force_world_n": _vector_record(
                replay["interface_damping_force_world_n"][abort_sample]
            ),
            "abort_physical_force_world_n": _vector_record(
                physical_force[abort_sample]
            ),
            "abort_physical_force_norm_n": float(
                np.linalg.norm(physical_force[abort_sample])
            ),
            "abort_physical_moment_world_nm": _vector_record(
                physical_moment[abort_sample]
            ),
            "maximum_force_constitutive_identity_error_n": float(
                np.max(np.abs(physical_force - force_identity))
            ),
            "maximum_moment_constitutive_identity_error_nm": float(
                np.max(np.abs(physical_moment - moment_identity))
            ),
            "safety_filter_status_counts": dict(
                Counter(map(str, replay["safety_filter_status"]))
            ),
            "maximum_safety_filter_intervention_coordinate_norm": float(
                np.nanmax(
                    replay["safety_filter_intervention_coordinate_norm"]
                )
            ),
            "maximum_feedback_clipping_delta_n": float(
                np.max(
                    np.linalg.norm(
                        replay["executable_feedback_clipping_delta_world_n"],
                        axis=1,
                    )
                )
            ),
            "maximum_joint_torque_clipping_norm_nm": float(
                np.max(replay["joint_torque_clipping_norm_nm"])
            ),
            "maximum_old_history_velocity_equivalent_force_delta_n": float(
                np.max(
                    np.linalg.norm(
                        replay[
                            "old_history_velocity_equivalent_force_delta_world_n"
                        ],
                        axis=1,
                    )
                )
            ),
            "old_stage4_velocity_mismatch_reproduced": False,
            "interpretation": (
                "allocator-dominated executable request remains below 200 N, but the "
                "next Plant-v1 Kelvin-Voigt interface state produces a physical force "
                "above 200 N; instantaneous screening does not predict that transition"
            ),
        },
        "runtime_discrepancy": runtime_profile,
        "root_causes": [
            "robot-side cuff pose/twist is not the Human-side cuff state under Plant-v1 compliance",
            "Human-only MPC and instantaneous execution screening omit the cuff-interface state transition",
            "scalar first-action screening repeats allocation, geometry, robot kinematics, and command preparation for 65 previews per solve",
            "Goal-MPC post-solve diagnostics repeat selected-sequence rollout/allocation work",
        ],
        "not_supported_as_root_causes": [
            "measurement latency or pose-history filtering in attempt 02",
            "T_EC/registered planar geometry error within the simulated model",
            "the superseded Stage-4 history-derived translational velocity feedback mismatch",
            "Safety Filter intervention, feedback clipping, or robot torque clipping",
            "wall-clock solve overrun extending simulated action-hold time",
        ],
        "minimal_fixes_before_v1_1": [
            "define a controller-deployable Human-side state observation or explicit cuff-relative state estimate",
            "include the deterministic Plant-v1 interface transition in horizon/screening or validate a conservative next-step physical-force margin",
            "use the existing batch first-action preview for the candidate-invariant local target and remove duplicate hot-loop diagnostics",
            "retain the same horizon/candidates while revalidating completion, force, and sub-20-ms throughput",
        ],
        "plausible_future_learning_targets_after_deterministic_fixes": [
            "hardware-calibrated cuff/tissue stiffness and damping uncertainty",
            "remaining Human/interface model discrepancy demonstrated on causal hardware measurements",
        ],
        "learning_not_justified_by_this_audit": True,
    }

    np.savez_compressed(output_dir / "synchronized_audit_trace.npz", **replay)
    _write_state_table(output_dir / "state_error_samples.csv", replay)
    _write_force_table(output_dir / "force_near_abort.csv", replay)
    _write_plots(output_dir, replay)
    (output_dir / "runtime_cprofile.txt").write_text(cprofile_text, encoding="utf-8")
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


__all__ = ["replay_saved_action_sequence", "run_goal_mpc_consistency_audit"]
