"""Staged MuJoCo study of kinematic-to-original-controller handoff angle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np

from .config import PlantV2Config
from .environment import PlantObservation, SleeveRobotEnvironment
from .kinematics import (
    coordinated_posture,
    human_reference,
    quintic_boundary_sample,
    quintic_progress,
    sleeve_jacobian,
    sleeve_position,
)
from .normal_controller import (
    NormalControllerConfig,
    local_force_rotation,
    original_normal_controller,
    taught_reference_time_for_q2,
)


@dataclass(frozen=True)
class HandoffStudyConfig:
    candidates_deg: tuple[float, ...] = (5.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0)
    kinematic_duration_s: float = 4.0
    blend_duration_s: float = 0.75
    normal_horizon_s: float = 2.0
    required_progress_fraction: float = 0.05
    maximum_progress_reversal_fraction: float = 0.01
    handoff_position_tolerance_deg: float = 0.75
    handoff_speed_tolerance_deg_s: float = 1.0
    force_bound_n: float = 200.0
    blend_force_spike_tolerance_n: float = 30.0
    sleeve_deformation_limit_mm: float = 1.0
    rom_tolerance_deg: float = 0.05
    soft_limit_start_deg: float = 5.0
    bed_active_force_threshold_n: float = 2.0
    maximum_bed_active_transitions: int = 2
    bed_impact_margin_n: float = 50.0
    bed_impact_factor: float = 1.75
    normal_controller_dt_s: float = 0.002
    evidence_class: str = "engineering_validation_smoke"


@dataclass(frozen=True)
class HandoffTrace:
    time_s: np.ndarray
    mode: np.ndarray
    q_deg: np.ndarray
    dq_deg_s: np.ndarray
    q_reference_deg: np.ndarray
    task_progress: np.ndarray
    interaction_force_n: np.ndarray
    interaction_force_vector_n: np.ndarray
    bed_force_n: np.ndarray
    bed_contact_count: np.ndarray
    sleeve_deformation_mm: np.ndarray
    cartesian_command_n: np.ndarray
    soft_limit_active: np.ndarray
    robot_chain_position_m: np.ndarray
    ee_position_m: np.ndarray
    sleeve_position_m: np.ndarray


def _task_progress(q_rad: np.ndarray) -> float:
    start = np.radians([5.0, 10.0])
    delta = np.radians([40.0, 74.0])
    return float(np.dot(q_rad - start, delta) / np.dot(delta, delta))


def _robot_chain(env: SleeveRobotEnvironment) -> np.ndarray:
    names = [f"robot_link_{index}" for index in range(1, 7)]
    points = np.array([env.data.body(name).xpos.copy() for name in names])
    return np.vstack([points, env.data.site("robot_ee_site").xpos.copy()])


def _record(
    records: list[dict[str, Any]],
    env: SleeveRobotEnvironment,
    observation: PlantObservation,
    mode: str,
    reference_q: np.ndarray | None,
    soft_active: np.ndarray | None = None,
) -> None:
    records.append(
        {
            "time_s": observation.time_s,
            "mode": mode,
            "q_deg": np.degrees(observation.human_q_rad),
            "dq_deg_s": np.degrees(observation.human_dq_rad_s),
            "q_reference_deg": (
                np.full(2, np.nan) if reference_q is None else np.degrees(reference_q)
            ),
            "task_progress": _task_progress(observation.human_q_rad),
            "interaction_force_n": observation.sleeve_force_n,
            "interaction_force_vector_n": observation.sleeve_force_vector_n,
            "bed_force_n": observation.bed_force_n,
            "bed_contact_count": observation.bed_contact_count,
            "sleeve_deformation_mm": 1e3 * observation.sleeve_deformation_m,
            "cartesian_command_n": observation.cartesian_force_command_n,
            "soft_limit_active": (
                np.zeros(2, dtype=bool) if soft_active is None else soft_active
            ),
            "robot_chain_position_m": _robot_chain(env),
            "ee_position_m": observation.ee_position_m,
            "sleeve_position_m": observation.sleeve_position_m,
        }
    )


def _as_trace(records: list[dict[str, Any]]) -> HandoffTrace:
    return HandoffTrace(
        time_s=np.array([item["time_s"] for item in records]),
        mode=np.array([item["mode"] for item in records]),
        q_deg=np.array([item["q_deg"] for item in records]),
        dq_deg_s=np.array([item["dq_deg_s"] for item in records]),
        q_reference_deg=np.array([item["q_reference_deg"] for item in records]),
        task_progress=np.array([item["task_progress"] for item in records]),
        interaction_force_n=np.array(
            [item["interaction_force_n"] for item in records]
        ),
        interaction_force_vector_n=np.array(
            [item["interaction_force_vector_n"] for item in records]
        ),
        bed_force_n=np.array([item["bed_force_n"] for item in records]),
        bed_contact_count=np.array(
            [item["bed_contact_count"] for item in records], dtype=int
        ),
        sleeve_deformation_mm=np.array(
            [item["sleeve_deformation_mm"] for item in records]
        ),
        cartesian_command_n=np.array(
            [item["cartesian_command_n"] for item in records]
        ),
        soft_limit_active=np.array(
            [item["soft_limit_active"] for item in records], dtype=bool
        ),
        robot_chain_position_m=np.array(
            [item["robot_chain_position_m"] for item in records]
        ),
        ee_position_m=np.array([item["ee_position_m"] for item in records]),
        sleeve_position_m=np.array(
            [item["sleeve_position_m"] for item in records]
        ),
    )


def _settle_from_bed_rest(
    env: SleeveRobotEnvironment,
    records: list[dict[str, Any]],
) -> dict[str, float | bool]:
    initial = env.reset(env.config.q_terminal_deg)
    target = initial.ee_position_m.copy()
    _record(records, env, initial, "BED_REST_SETTLE", None)
    cfg = env.config
    stable = False
    window: list[PlantObservation] = []
    active_transitions = 0
    peak_force = initial.sleeve_force_n
    peak_bed = initial.bed_force_n
    max_steps = int(round(cfg.settle_max_time_s / cfg.control_dt_s))
    minimum_steps = int(round(cfg.settle_min_time_s / cfg.control_dt_s))
    window_steps = int(round(cfg.settle_window_s / cfg.control_dt_s))
    for index in range(max_steps):
        step = env.step_cartesian(target, np.zeros(3))
        observation = step.observation
        _record(records, env, observation, "BED_REST_SETTLE", None)
        window.append(observation)
        window = window[-window_steps:]
        active_transitions += step.bed_active_transitions
        peak_force = max(peak_force, step.peak_sleeve_force_n)
        peak_bed = max(peak_bed, step.peak_bed_force_n)
        if index + 1 < minimum_steps or len(window) < window_steps:
            continue
        speed = max(
            float(np.max(np.abs(np.degrees(item.human_dq_rad_s)))) for item in window
        )
        ee_speed = 1e3 * max(
            float(np.linalg.norm(item.ee_velocity_m_s)) for item in window
        )
        force_range = max(item.bed_force_n for item in window) - min(
            item.bed_force_n for item in window
        )
        stable = (
            speed <= cfg.stable_joint_speed_deg_s
            and ee_speed <= cfg.stable_ee_speed_mm_s
            and force_range <= cfg.stable_force_range_n
        )
        if stable:
            break
    final = env.observe()
    return {
        "stable": stable,
        "settle_time_s": final.time_s,
        "rest_q1_deg": math.degrees(final.human_q_rad[0]),
        "rest_q2_deg": math.degrees(final.human_q_rad[1]),
        "rest_bed_force_n": final.bed_force_n,
        "peak_settle_bed_force_n": peak_bed,
        "peak_settle_interaction_force_n": peak_force,
        "bed_active_transitions": active_transitions,
    }


def _kinematic_target(
    sample_q: np.ndarray,
    sample_dq: np.ndarray,
    env: SleeveRobotEnvironment,
) -> tuple[np.ndarray, np.ndarray]:
    position = sleeve_position(sample_q, env.human, env.config)
    planar_velocity = sleeve_jacobian(sample_q, env.human) @ sample_dq
    velocity = np.array([planar_velocity[0], 0.0, planar_velocity[1]])
    return position, velocity


def _soft_active_from_q(q_rad: np.ndarray, config: HandoffStudyConfig) -> np.ndarray:
    q_deg = np.degrees(q_rad)
    lower = np.full(2, config.soft_limit_start_deg)
    upper = np.array([80.0, 100.0]) - config.soft_limit_start_deg
    return (q_deg < lower) | (q_deg > upper)


def run_handoff_candidate(
    q_handoff_deg: float,
    study_config: HandoffStudyConfig | None = None,
) -> tuple[dict[str, Any], HandoffTrace]:
    """Run one candidate from an independently settled BED REST state."""

    study = study_config or HandoffStudyConfig()
    plant_config = PlantV2Config()
    normal_config = NormalControllerConfig(dt_s=study.normal_controller_dt_s)
    env = SleeveRobotEnvironment(config=plant_config)
    records: list[dict[str, Any]] = []
    settle = _settle_from_bed_rest(env, records)
    takeoff_start = env.observe()
    q0 = takeoff_start.human_q_rad.copy()
    dq0 = takeoff_start.human_dq_rad_s.copy()
    q_target = coordinated_posture(math.radians(q_handoff_deg))
    kinematic_peak_force = takeoff_start.sleeve_force_n
    kinematic_peak_bed = takeoff_start.bed_force_n
    kinematic_bed_active_transitions = 0
    kinematic_max_deformation_mm = 1e3 * takeoff_start.sleeve_deformation_m
    protective_stop = False
    protective_reason = ""
    rom_violation = False
    soft_violation = False
    bed_active_transitions = 0
    peak_bed_after_handoff = 0.0
    peak_force_after_handoff = 0.0
    max_deformation_after_handoff_mm = 0.0
    actuator_component_saturation = False
    steps = int(round(study.kinematic_duration_s / plant_config.control_dt_s))
    for index in range(steps):
        elapsed = (index + 1) * plant_config.control_dt_s
        sample = quintic_boundary_sample(
            elapsed,
            study.kinematic_duration_s,
            q0,
            dq0,
            q_target,
        )
        target_position, target_velocity = _kinematic_target(sample.q, sample.dq, env)
        step = env.step_cartesian(target_position, target_velocity)
        observation = step.observation
        _record(records, env, observation, "KINEMATIC_TAKEOFF", sample.q)
        kinematic_peak_force = max(kinematic_peak_force, step.peak_sleeve_force_n)
        kinematic_peak_bed = max(kinematic_peak_bed, step.peak_bed_force_n)
        kinematic_bed_active_transitions += step.bed_active_transitions
        kinematic_max_deformation_mm = max(
            kinematic_max_deformation_mm,
            1e3 * observation.sleeve_deformation_m,
        )
        q_deg = np.degrees(observation.human_q_rad)
        kinematic_rom_violation = bool(
            np.any(q_deg < -study.rom_tolerance_deg)
            or q_deg[0] > 80.0 + study.rom_tolerance_deg
            or q_deg[1] > 100.0 + study.rom_tolerance_deg
        )
        if step.peak_sleeve_force_n > study.force_bound_n + 1e-6:
            protective_stop = True
            protective_reason = "kinematic_interaction_force_veto"
            break
        if kinematic_rom_violation:
            rom_violation = True
            protective_stop = True
            protective_reason = "kinematic_wrong_motion_reached_rom_boundary"
            break

    handoff_observation = env.observe()
    handoff_q2_error = abs(
        math.degrees(handoff_observation.human_q_rad[1]) - q_handoff_deg
    )
    handoff_speed = float(
        np.max(np.abs(np.degrees(handoff_observation.human_dq_rad_s)))
    )
    handoff_reached = (
        not protective_stop
        and handoff_q2_error <= study.handoff_position_tolerance_deg
        and handoff_speed <= study.handoff_speed_tolerance_deg_s
    )
    final_target_position = sleeve_position(q_target, env.human, env.config)
    final_ee_position_error_mm = 1e3 * float(
        np.linalg.norm(final_target_position - handoff_observation.ee_position_m)
    )

    handoff_command = handoff_observation.cartesian_force_command_n.copy()
    rotation = local_force_rotation(handoff_observation.human_q_rad)
    previous_local_force = rotation.T @ handoff_command
    capture_local_force = previous_local_force.copy()
    first_blend_command_jump_n = math.nan
    maximum_command_step_n = 0.0
    normal_controller_calls = 0
    normal_start_time = math.nan
    reference_start_time = taught_reference_time_for_q2(q_handoff_deg)
    total_force_steps = int(
        round(
            (study.blend_duration_s + study.normal_horizon_s)
            / study.normal_controller_dt_s
        )
    )
    normal_substeps = int(
        round(study.normal_controller_dt_s / plant_config.simulation_dt_s)
    )
    if handoff_reached:
        for index in range(total_force_steps):
            elapsed = (index + 1) * study.normal_controller_dt_s
            reference = human_reference(reference_start_time + elapsed)
            current = env.observe()
            controller = original_normal_controller(
                current.human_q_rad,
                current.human_dq_rad_s,
                reference,
                current.bed_generalized_torque_nm,
                previous_local_force,
                env.human,
                normal_config,
            )
            normal_controller_calls += 1
            if elapsed <= study.blend_duration_s:
                alpha, _, _ = quintic_progress(elapsed / study.blend_duration_s)
                applied_local_force = (
                    (1.0 - alpha) * capture_local_force
                    + alpha * controller.local_force_n
                )
                mode = "BLEND_TO_NORMAL"
            else:
                applied_local_force = controller.local_force_n
                mode = "NORMAL_REHAB"
                if not math.isfinite(normal_start_time):
                    normal_start_time = current.time_s
            world_force = local_force_rotation(current.human_q_rad) @ applied_local_force
            clipped_world_force = np.clip(
                world_force,
                -plant_config.actuator_cartesian_force_bound_n,
                plant_config.actuator_cartesian_force_bound_n,
            )
            if not np.allclose(world_force, clipped_world_force, atol=1e-9, rtol=0.0):
                actuator_component_saturation = True
            command_step = float(
                np.linalg.norm(clipped_world_force - current.cartesian_force_command_n)
            )
            maximum_command_step_n = max(maximum_command_step_n, command_step)
            if index == 0:
                first_blend_command_jump_n = command_step
            step = env.step_cartesian_force(
                clipped_world_force, substeps=normal_substeps
            )
            observation = step.observation
            soft_active = _soft_active_from_q(observation.human_q_rad, study)
            _record(records, env, observation, mode, reference.q, soft_active)
            previous_local_force = (
                local_force_rotation(observation.human_q_rad).T @ clipped_world_force
            )
            bed_active_transitions += step.bed_active_transitions
            peak_bed_after_handoff = max(
                peak_bed_after_handoff, step.peak_bed_force_n
            )
            peak_force_after_handoff = max(
                peak_force_after_handoff, step.peak_sleeve_force_n
            )
            max_deformation_after_handoff_mm = max(
                max_deformation_after_handoff_mm,
                1e3 * observation.sleeve_deformation_m,
            )
            soft_violation = soft_violation or bool(np.any(soft_active))
            q_deg = np.degrees(observation.human_q_rad)
            rom_violation = rom_violation or bool(
                np.any(q_deg < -study.rom_tolerance_deg)
                or q_deg[0] > 80.0 + study.rom_tolerance_deg
                or q_deg[1] > 100.0 + study.rom_tolerance_deg
            )
            if step.peak_sleeve_force_n > study.force_bound_n + 1e-6:
                protective_stop = True
                protective_reason = "normal_interaction_force_veto"
                break
            if rom_violation:
                protective_stop = True
                protective_reason = "rom_violation"
                break

    trace = _as_trace(records)
    handoff_index = int(np.flatnonzero(trace.mode == "KINEMATIC_TAKEOFF")[-1])
    takeoff_indices = np.flatnonzero(trace.mode == "KINEMATIC_TAKEOFF")
    normal_indices = np.flatnonzero(trace.mode == "NORMAL_REHAB")
    blend_indices = np.flatnonzero(trace.mode == "BLEND_TO_NORMAL")
    completed_horizon = (
        len(normal_indices)
        >= int(round(study.normal_horizon_s / study.normal_controller_dt_s)) - 1
    )
    if len(normal_indices):
        progress = trace.task_progress[normal_indices]
        progress_gain = float(progress[-1] - progress[0])
        cumulative_max = np.maximum.accumulate(progress)
        maximum_reversal = float(np.max(cumulative_max - progress))
    else:
        progress_gain = 0.0
        maximum_reversal = math.inf
    progress_gate = (
        progress_gain >= study.required_progress_fraction
        and maximum_reversal <= study.maximum_progress_reversal_fraction
    )
    if len(blend_indices):
        blend_peak_force = float(np.max(trace.interaction_force_n[blend_indices]))
    else:
        blend_peak_force = 0.0
    handoff_force = float(trace.interaction_force_n[handoff_index])
    blend_force_spike = max(0.0, blend_peak_force - handoff_force)
    force_spike_gate = blend_force_spike <= study.blend_force_spike_tolerance_n
    command_continuity_gate = first_blend_command_jump_n <= 1.0
    bed_impact_limit = max(
        float(settle["rest_bed_force_n"]) + study.bed_impact_margin_n,
        float(settle["rest_bed_force_n"]) * study.bed_impact_factor,
    )
    bed_transfer_gate = (
        bed_active_transitions <= study.maximum_bed_active_transitions
        and peak_bed_after_handoff <= bed_impact_limit
    )
    force_gate = (
        max(kinematic_peak_force, peak_force_after_handoff)
        <= study.force_bound_n + 1e-6
    )
    sleeve_gate = (
        max(kinematic_max_deformation_mm, max_deformation_after_handoff_mm)
        <= study.sleeve_deformation_limit_mm
    )
    passed = all(
        [
            bool(settle["stable"]),
            handoff_reached,
            completed_horizon,
            command_continuity_gate,
            force_spike_gate,
            progress_gate,
            force_gate,
            not soft_violation,
            not rom_violation,
            not protective_stop,
            not actuator_component_saturation,
            bed_transfer_gate,
            sleeve_gate,
        ]
    )
    if not settle["stable"]:
        mechanism = "bed_rest_not_stable"
    elif protective_reason == "kinematic_interaction_force_veto":
        mechanism = protective_reason
    elif protective_reason == "kinematic_wrong_motion_reached_rom_boundary":
        mechanism = protective_reason
    elif not handoff_reached:
        if handoff_observation.human_q_rad[1] <= q0[1]:
            mechanism = "kinematic_takeoff_wrong_generalized_motion_q2_extension"
        else:
            mechanism = "kinematic_takeoff_insufficient_position_authority"
    elif soft_violation:
        mechanism = "normal_handoff_inside_human_v2_soft_limit_zone"
    elif protective_reason:
        mechanism = protective_reason
    elif actuator_component_saturation:
        mechanism = "normal_force_command_exceeded_actuator_component_bound"
    elif not completed_horizon:
        mechanism = "normal_horizon_not_completed"
    elif not progress_gate:
        mechanism = (
            "normal_task_progress_reversal"
            if maximum_reversal > study.maximum_progress_reversal_fraction
            else "normal_task_progress_stall"
        )
    elif not force_spike_gate or not command_continuity_gate:
        mechanism = "handoff_dynamic_force_or_command_jump"
    elif not bed_transfer_gate:
        mechanism = "bed_robot_load_transfer_instability"
    elif not sleeve_gate:
        mechanism = "sleeve_deformation_limit"
    else:
        mechanism = "none"

    summary = {
        "q_handoff_deg": q_handoff_deg,
        "status": "PASS" if passed else "FAIL",
        "direct_mechanism": mechanism,
        "settle": settle,
        "measured_handoff_q_deg": np.degrees(
            handoff_observation.human_q_rad
        ).tolist(),
        "measured_handoff_dq_deg_s": np.degrees(
            handoff_observation.human_dq_rad_s
        ).tolist(),
        "handoff_q2_error_deg": handoff_q2_error,
        "final_ee_position_error_mm": final_ee_position_error_mm,
        "handoff_reached": handoff_reached,
        "taught_reference_start_time_s": reference_start_time,
        "normal_controller_source": normal_config.source_function,
        "normal_controller_calls": normal_controller_calls,
        "completed_normal_horizon": completed_horizon,
        "normal_horizon_s": study.normal_horizon_s,
        "task_progress_gain": progress_gain,
        "maximum_task_progress_reversal": (
            maximum_reversal if math.isfinite(maximum_reversal) else None
        ),
        "first_blend_command_jump_n": (
            first_blend_command_jump_n
            if math.isfinite(first_blend_command_jump_n)
            else None
        ),
        "maximum_command_step_n": maximum_command_step_n,
        "blend_force_spike_n": blend_force_spike,
        "peak_interaction_force_n": max(
            kinematic_peak_force, peak_force_after_handoff
        ),
        "takeoff_task_progress_gain": float(
            trace.task_progress[takeoff_indices[-1]]
            - trace.task_progress[takeoff_indices[0]]
        ),
        "takeoff_peak_bed_force_n": kinematic_peak_bed,
        "takeoff_final_bed_force_n": handoff_observation.bed_force_n,
        "takeoff_bed_active_transitions": kinematic_bed_active_transitions,
        "takeoff_maximum_sleeve_deformation_mm": kinematic_max_deformation_mm,
        "takeoff_final_cartesian_command_norm_n": float(
            np.linalg.norm(handoff_observation.cartesian_force_command_n)
        ),
        "peak_bed_force_after_handoff_n": peak_bed_after_handoff,
        "bed_impact_limit_n": bed_impact_limit,
        "bed_active_transitions_after_handoff": bed_active_transitions,
        "maximum_sleeve_deformation_after_handoff_mm": (
            max_deformation_after_handoff_mm
        ),
        "maximum_sleeve_deformation_overall_mm": max(
            kinematic_max_deformation_mm, max_deformation_after_handoff_mm
        ),
        "soft_limit_violation": soft_violation,
        "rom_violation": rom_violation,
        "protective_stop": protective_stop,
        "actuator_component_saturation": actuator_component_saturation,
        "gates": {
            "settled_bed_rest": bool(settle["stable"]),
            "handoff_reached": handoff_reached,
            "completed_normal_horizon": completed_horizon,
            "command_continuity": command_continuity_gate,
            "blend_force_spike": force_spike_gate,
            "task_progress": progress_gate,
            "interaction_force": force_gate,
            "no_soft_or_rom_violation": not soft_violation and not rom_violation,
            "no_protective_stop": not protective_stop,
            "no_actuator_component_saturation": not actuator_component_saturation,
            "stable_bed_load_transfer": bed_transfer_gate,
            "small_sleeve_deformation": sleeve_gate,
        },
    }
    return summary, trace


def run_staged_handoff_search(
    study_config: HandoffStudyConfig | None = None,
) -> tuple[dict[str, Any], dict[float, HandoffTrace]]:
    """Search upward, then retain one neighbor and the 30 degree reference."""

    cfg = study_config or HandoffStudyConfig()
    traces: dict[float, HandoffTrace] = {}
    results: dict[float, dict[str, Any]] = {}
    first_pass: float | None = None
    candidates = list(cfg.candidates_deg)
    for index, candidate in enumerate(candidates):
        if candidate == 30.0:
            continue
        result, trace = run_handoff_candidate(candidate, cfg)
        results[candidate] = result
        traces[candidate] = trace
        if result["status"] == "PASS":
            first_pass = candidate
            if index + 1 < len(candidates) and candidates[index + 1] != 30.0:
                neighbor = candidates[index + 1]
                neighbor_result, neighbor_trace = run_handoff_candidate(neighbor, cfg)
                results[neighbor] = neighbor_result
                traces[neighbor] = neighbor_trace
            break
    if 30.0 not in results:
        result, trace = run_handoff_candidate(30.0, cfg)
        results[30.0] = result
        traces[30.0] = trace
        if first_pass is None and result["status"] == "PASS":
            first_pass = 30.0

    rows = []
    for candidate in candidates:
        if candidate in results:
            rows.append(results[candidate])
        else:
            rows.append(
                {
                    "q_handoff_deg": candidate,
                    "status": "NOT_RUN_STAGED",
                    "direct_mechanism": "outside_required_boundary_neighborhood",
                }
            )
    tested_passes = [
        candidate
        for candidate, result in results.items()
        if result["status"] == "PASS"
    ]
    minimum_feasible = min(tested_passes) if tested_passes else None
    tested_failures_below = sorted(
        candidate
        for candidate, result in results.items()
        if result["status"] == "FAIL"
        and (minimum_feasible is None or candidate < minimum_feasible)
    )
    boundary_case = minimum_feasible if minimum_feasible is not None else max(results)
    summary = {
        "evidence_class": cfg.evidence_class,
        "study_config": asdict(cfg),
        "staged_policy": (
            "ascending until first PASS, then one upper neighbor and 30 deg reference"
        ),
        "candidate_rows": rows,
        "tested_candidates_deg": sorted(results),
        "minimum_tested_feasible_handoff_deg": minimum_feasible,
        "largest_tested_failure_below_feasible_deg": (
            max(tested_failures_below) if tested_failures_below else None
        ),
        "representative_boundary_case_deg": boundary_case,
        "architecture_small_angle_supported": bool(
            minimum_feasible is not None and minimum_feasible <= 10.0
        ),
        "q_switch_30_role": "positive_reference_only",
        "scientific_variables_changed": [],
        "frozen_values": {
            "human_v2": True,
            "bed_contact": True,
            "robot_sleeve_plant_v2": True,
            "force_bound_n": cfg.force_bound_n,
            "normal_controller": "source-faithful retained law",
            "taught_trajectory": "slow_passive_flexion_v2",
            "windowed_nls_r3c_r4": False,
        },
    }
    return summary, traces


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "q_handoff_deg",
        "status",
        "direct_mechanism",
        "handoff_q2_error_deg",
        "final_ee_position_error_mm",
        "takeoff_task_progress_gain",
        "task_progress_gain",
        "maximum_task_progress_reversal",
        "first_blend_command_jump_n",
        "blend_force_spike_n",
        "peak_interaction_force_n",
        "takeoff_final_bed_force_n",
        "takeoff_bed_active_transitions",
        "peak_bed_force_after_handoff_n",
        "bed_active_transitions_after_handoff",
        "maximum_sleeve_deformation_overall_mm",
        "soft_limit_violation",
        "rom_violation",
        "protective_stop",
    ]
    lines = [",".join(fields)]
    for row in rows:
        values = [row.get(field, "") for field in fields]
        lines.append(",".join("" if value is None else str(value) for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_boundary(
    output_dir: Path,
    summary: dict[str, Any],
    traces: dict[float, HandoffTrace],
) -> None:
    case = float(summary["representative_boundary_case_deg"])
    trace = traces[case]
    modes = ["BED_REST_SETTLE", "KINEMATIC_TAKEOFF", "BLEND_TO_NORMAL", "NORMAL_REHAB"]
    mode_values = np.array([modes.index(mode) for mode in trace.mode])
    fig, axes = plt.subplots(5, 1, figsize=(10, 12), sharex=True, constrained_layout=True)
    axes[0].plot(trace.time_s, trace.q_deg[:, 1], label="q2 measured")
    axes[0].plot(
        trace.time_s,
        trace.q_reference_deg[:, 1],
        "--",
        label="active q2 command/reference",
    )
    axes[0].set_ylabel("q2 (deg)")
    axes[0].legend()
    axes[1].plot(trace.time_s, trace.task_progress)
    axes[1].set_ylabel("task progress")
    axes[2].plot(trace.time_s, trace.interaction_force_n, label="interaction")
    axes[2].axhline(200.0, color="r", linestyle="--", label="veto")
    axes[2].set_ylabel("force (N)")
    axes[2].legend()
    axes[3].plot(trace.time_s, trace.bed_force_n, label="bed")
    axes[3].set_ylabel("bed force (N)")
    axes[4].step(trace.time_s, mode_values, where="post")
    axes[4].set_yticks(range(len(modes)), modes)
    axes[4].set_ylabel("mode")
    axes[4].set_xlabel("time (s)")
    fig.suptitle(f"Representative handoff boundary case: {case:g} deg")
    fig.savefig(output_dir / "representative_handoff_timeseries.png", dpi=170)
    plt.close(fig)

    tested = [row for row in summary["candidate_rows"] if row["status"] != "NOT_RUN_STAGED"]
    labels = [f"{row['q_handoff_deg']:g}" for row in tested]
    colors = ["#2a9d5b" if row["status"] == "PASS" else "#c94b45" for row in tested]
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), constrained_layout=True)
    x = np.arange(len(tested))
    axes[0].bar(
        x - 0.18,
        [row["q_handoff_deg"] for row in tested],
        width=0.36,
        color="#7aa6c2",
        label="candidate",
    )
    axes[0].bar(
        x + 0.18,
        [row["measured_handoff_q_deg"][1] for row in tested],
        width=0.36,
        color=colors,
        label="measured after 4 s patch",
    )
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("q2 (deg)")
    axes[0].legend()
    axes[1].bar(labels, [row["peak_interaction_force_n"] for row in tested], color=colors)
    axes[1].axhline(200.0, color="r", linestyle="--", label="force gate")
    axes[1].set_ylabel("peak interaction (N)")
    axes[1].legend()
    axes[2].bar(
        labels,
        [row["maximum_sleeve_deformation_overall_mm"] for row in tested],
        color=colors,
    )
    axes[2].axhline(1.0, color="k", linestyle="--", label="deformation gate")
    axes[2].set_ylabel("sleeve deformation (mm)")
    axes[2].set_xlabel("handoff candidate (deg)")
    axes[2].legend()
    fig.suptitle("Staged small-angle handoff comparison")
    fig.savefig(output_dir / "handoff_angle_comparison.png", dpi=170)
    plt.close(fig)


def _write_gif(path: Path, case: float, trace: HandoffTrace) -> None:
    duration = trace.time_s[-1] - trace.time_s[0]
    frame_count = max(2, int(math.ceil(duration * 12.0)))
    frame_indices = np.unique(
        np.linspace(0, len(trace.time_s) - 1, frame_count).astype(int)
    )
    fig = plt.figure(figsize=(10, 6.4), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    ax_scene = fig.add_subplot(grid[:, 0])
    ax_q = fig.add_subplot(grid[0, 1])
    ax_force = fig.add_subplot(grid[1, 1])

    def draw(frame: int) -> None:
        index = int(frame_indices[frame])
        ax_scene.clear()
        ax_q.clear()
        ax_force.clear()
        robot = trace.robot_chain_position_m[index]
        q1, q2 = np.radians(trace.q_deg[index])
        l1, l2 = 0.43688, 0.40076
        hip = np.array([0.0, 0.062])
        knee = hip + l1 * np.array([math.cos(q1), math.sin(q1)])
        ankle = knee + l2 * np.array([math.cos(q1 - q2), math.sin(q1 - q2)])
        ax_scene.axhline(0.012, color="#5f8faa", linewidth=7)
        ax_scene.plot(robot[:, 0], robot[:, 2], "o-", color="#28558c", label="robot")
        ax_scene.plot(
            [hip[0], knee[0], ankle[0]],
            [hip[1], knee[1], ankle[1]],
            "o-",
            color="#df7c25",
            linewidth=4,
            label="Human V2",
        )
        sleeve = trace.sleeve_position_m[index]
        ax_scene.scatter(sleeve[0], sleeve[2], s=100, color="#9c36c7", label="sleeve")
        ax_scene.set_xlim(-0.1, 1.25)
        ax_scene.set_ylim(-0.04, 0.9)
        ax_scene.set_aspect("equal")
        ax_scene.grid(alpha=0.2)
        ax_scene.legend(fontsize=8)
        ax_scene.set_title(f"{trace.mode[index]}  t={trace.time_s[index]:.2f}s")
        ax_q.plot(trace.time_s[: index + 1], trace.q_deg[: index + 1, 1], label="q2")
        ax_q.plot(
            trace.time_s[: index + 1],
            trace.q_reference_deg[: index + 1, 1],
            "--",
            label="active q2 command/reference",
        )
        ax_q.set_xlim(trace.time_s[0], trace.time_s[-1])
        ax_q.set_ylim(-2.0, max(32.0, case + 2.0))
        ax_q.set_ylabel("q2 (deg)")
        ax_q.grid(alpha=0.2)
        ax_q.legend(fontsize=8)
        ax_force.plot(
            trace.time_s[: index + 1],
            trace.interaction_force_n[: index + 1],
            label="interaction",
        )
        ax_force.plot(
            trace.time_s[: index + 1], trace.bed_force_n[: index + 1], label="bed"
        )
        ax_force.axhline(200.0, color="r", linestyle="--")
        ax_force.set_xlim(trace.time_s[0], trace.time_s[-1])
        ax_force.set_ylim(0.0, max(210.0, 1.1 * np.max(trace.bed_force_n)))
        ax_force.set_xlabel("time (s)")
        ax_force.set_ylabel("force (N)")
        ax_force.grid(alpha=0.2)
        ax_force.legend(fontsize=8)

    animation = FuncAnimation(fig, draw, frames=len(frame_indices), interval=1000 / 12)
    animation.save(path, writer=PillowWriter(fps=12))
    plt.close(fig)


def write_study_artifacts(
    output_dir: Path,
    summary: dict[str, Any],
    traces: dict[float, HandoffTrace],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_csv(output_dir / "handoff_angle_table.csv", summary["candidate_rows"])
    _plot_boundary(output_dir, summary, traces)
    case = float(summary["representative_boundary_case_deg"])
    _write_gif(output_dir / "representative_boundary_handoff.gif", case, traces[case])
    np.savez_compressed(
        output_dir / "handoff_traces.npz",
        **{
            f"q{candidate:g}__{field}": value
            for candidate, trace in traces.items()
            for field, value in asdict(trace).items()
            if isinstance(value, np.ndarray)
        },
    )
