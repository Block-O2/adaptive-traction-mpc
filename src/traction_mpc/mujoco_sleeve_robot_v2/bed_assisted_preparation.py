"""Bed-assisted low-angle preparation experiment for plant V2.

This module intentionally contains no normal controller or handoff logic.  It
settles the frozen Human V2/bed/robot/sleeve plant, constructs a small C2 path
from the measured state, and asks the Cartesian robot interface to follow the
corresponding sleeve trajectory.
"""

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
from scipy.optimize import brentq

from .config import HumanV2Parameters, PlantV2Config
from .environment import PlantObservation, SleeveRobotEnvironment
from .kinematics import quintic_boundary_sample, sleeve_jacobian, sleeve_position


@dataclass(frozen=True)
class PreparationStudyConfig:
    target_candidates_deg: tuple[float, ...] = (5.0, 8.0, 10.0)
    trajectory_duration_s: float = 4.0
    force_bound_n: float = 200.0
    target_tolerance_deg: float = 0.75
    final_speed_tolerance_deg_s: float = 1.0
    maximum_q2_reversal_deg: float = 0.15
    sleeve_deformation_limit_mm: float = 1.0
    rom_tolerance_deg: float = 0.05
    soft_limit_start_deg: float = 5.0
    bed_active_force_threshold_n: float = 2.0
    maximum_bed_active_transitions: int = 2
    command_step_limit_mm: float = 0.20
    force_command_step_limit_n: float = 5.0
    evidence_class: str = "engineering_validation_smoke"


@dataclass(frozen=True)
class PreparationTrace:
    time_s: np.ndarray
    mode: np.ndarray
    q_deg: np.ndarray
    dq_deg_s: np.ndarray
    q_reference_deg: np.ndarray
    ee_reference_m: np.ndarray
    ee_position_m: np.ndarray
    sleeve_position_m: np.ndarray
    interaction_force_n: np.ndarray
    interaction_force_vector_n: np.ndarray
    bed_force_n: np.ndarray
    bed_contact_count: np.ndarray
    bed_penetration_mm: np.ndarray
    sleeve_deformation_mm: np.ndarray
    cartesian_command_n: np.ndarray
    robot_chain_position_m: np.ndarray


def minimum_bed_clearance_q1(
    q2_rad: float,
    human: HumanV2Parameters,
    plant: PlantV2Config,
) -> float:
    """Smallest q1 that keeps the distal shank capsule tangent to the bed."""

    target_center_height = plant.bed_height_m + plant.shank_radius_m

    def residual(q1: float) -> float:
        return (
            plant.hip_height_m
            + human.thigh_length_m * math.sin(q1)
            + human.shank_length_m * math.sin(q1 - q2_rad)
            - target_center_height
        )

    return float(brentq(residual, math.radians(-10.0), math.radians(30.0)))


def preparation_target_posture(
    q2_target_deg: float,
    human: HumanV2Parameters,
    plant: PlantV2Config,
    study: PreparationStudyConfig,
) -> tuple[np.ndarray, dict[str, float]]:
    """Derive the least-flexed q1 satisfying bed clearance and soft-zone exit.

    The lower Human V2 soft boundary is not invented by this experiment.  The
    target q1 is the maximum of that registered boundary and the geometric
    bed-clearance solution, so it is the smallest admissible choice under the
    two explicit constraints.
    """

    q2_rad = math.radians(q2_target_deg)
    clearance_q1 = minimum_bed_clearance_q1(q2_rad, human, plant)
    q1_target = max(clearance_q1, math.radians(study.soft_limit_start_deg))
    return np.array([q1_target, q2_rad]), {
        "bed_clearance_minimum_q1_deg": math.degrees(clearance_q1),
        "soft_boundary_minimum_q1_deg": study.soft_limit_start_deg,
        "selected_q1_deg": math.degrees(q1_target),
    }


def _robot_chain(env: SleeveRobotEnvironment) -> np.ndarray:
    points = np.array(
        [env.data.body(f"robot_link_{index}").xpos.copy() for index in range(1, 7)]
    )
    return np.vstack([points, env.data.site("robot_ee_site").xpos.copy()])


def _record(
    records: list[dict[str, Any]],
    env: SleeveRobotEnvironment,
    observation: PlantObservation,
    mode: str,
    q_reference: np.ndarray | None,
    ee_reference: np.ndarray | None,
) -> None:
    records.append(
        {
            "time_s": observation.time_s,
            "mode": mode,
            "q_deg": np.degrees(observation.human_q_rad),
            "dq_deg_s": np.degrees(observation.human_dq_rad_s),
            "q_reference_deg": np.full(2, np.nan)
            if q_reference is None
            else np.degrees(q_reference),
            "ee_reference_m": np.full(3, np.nan)
            if ee_reference is None
            else ee_reference,
            "ee_position_m": observation.ee_position_m,
            "sleeve_position_m": observation.sleeve_position_m,
            "interaction_force_n": observation.sleeve_force_n,
            "interaction_force_vector_n": observation.sleeve_force_vector_n,
            "bed_force_n": observation.bed_force_n,
            "bed_contact_count": observation.bed_contact_count,
            "bed_penetration_mm": 1e3 * observation.bed_penetration_m,
            "sleeve_deformation_mm": 1e3 * observation.sleeve_deformation_m,
            "cartesian_command_n": observation.cartesian_force_command_n,
            "robot_chain_position_m": _robot_chain(env),
        }
    )


def _as_trace(records: list[dict[str, Any]]) -> PreparationTrace:
    fields = PreparationTrace.__dataclass_fields__
    values = {field: np.array([item[field] for item in records]) for field in fields}
    return PreparationTrace(**values)


def _settle(
    env: SleeveRobotEnvironment,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    initial = env.reset(env.config.q_terminal_deg)
    hold_target = initial.ee_position_m.copy()
    _record(records, env, initial, "BED_REST_SETTLE", None, hold_target)
    cfg = env.config
    stable = False
    window: list[PlantObservation] = []
    active_transitions = 0
    max_steps = int(round(cfg.settle_max_time_s / cfg.control_dt_s))
    minimum_steps = int(round(cfg.settle_min_time_s / cfg.control_dt_s))
    window_steps = int(round(cfg.settle_window_s / cfg.control_dt_s))
    peak_bed = initial.bed_force_n
    peak_interaction = initial.sleeve_force_n
    for index in range(max_steps):
        step = env.step_cartesian(hold_target, np.zeros(3))
        observation = step.observation
        _record(records, env, observation, "BED_REST_SETTLE", None, hold_target)
        window.append(observation)
        window = window[-window_steps:]
        active_transitions += step.bed_active_transitions
        peak_bed = max(peak_bed, step.peak_bed_force_n)
        peak_interaction = max(peak_interaction, step.peak_sleeve_force_n)
        if index + 1 < minimum_steps or len(window) < window_steps:
            continue
        joint_speed = max(
            float(np.max(np.abs(np.degrees(item.human_dq_rad_s)))) for item in window
        )
        ee_speed = 1e3 * max(
            float(np.linalg.norm(item.ee_velocity_m_s)) for item in window
        )
        bed_range = max(item.bed_force_n for item in window) - min(
            item.bed_force_n for item in window
        )
        stable = (
            joint_speed <= cfg.stable_joint_speed_deg_s
            and ee_speed <= cfg.stable_ee_speed_mm_s
            and bed_range <= cfg.stable_force_range_n
        )
        if stable:
            break
    final = env.observe()
    return {
        "stable": stable,
        "settle_time_s": final.time_s,
        "measured_rest_q_deg": np.degrees(final.human_q_rad).tolist(),
        "measured_rest_dq_deg_s": np.degrees(final.human_dq_rad_s).tolist(),
        "rest_bed_force_n": final.bed_force_n,
        "rest_interaction_force_n": final.sleeve_force_n,
        "peak_settle_bed_force_n": peak_bed,
        "peak_settle_interaction_force_n": peak_interaction,
        "bed_active_transitions": active_transitions,
    }


def _minimum_link_clearance_m(
    q_rad: np.ndarray,
    human: HumanV2Parameters,
    plant: PlantV2Config,
) -> float:
    q1, q2 = q_rad
    knee_z = plant.hip_height_m + human.thigh_length_m * math.sin(q1)
    ankle_z = knee_z + human.shank_length_m * math.sin(q1 - q2)
    thigh_clearance = min(plant.hip_height_m, knee_z) - (
        plant.bed_height_m + plant.thigh_radius_m
    )
    shank_clearance = min(knee_z, ankle_z) - (
        plant.bed_height_m + plant.shank_radius_m
    )
    return min(thigh_clearance, shank_clearance)


def _mapping_error(human: HumanV2Parameters, plant: PlantV2Config) -> float:
    q = np.radians([4.0, 5.0])
    epsilon = 1e-7
    finite_difference = np.column_stack(
        [
            (
                sleeve_position(q + epsilon * np.eye(2)[index], human, plant)
                - sleeve_position(q - epsilon * np.eye(2)[index], human, plant)
            )[[0, 2]]
            / (2.0 * epsilon)
            for index in range(2)
        ]
    )
    return float(
        np.max(np.abs(finite_difference - sleeve_jacobian(q, human)[[0, 2], :]))
    )


def run_preparation_candidate(
    q2_target_deg: float,
    study_config: PreparationStudyConfig | None = None,
) -> tuple[dict[str, Any], PreparationTrace]:
    study = study_config or PreparationStudyConfig()
    plant = PlantV2Config()
    env = SleeveRobotEnvironment(config=plant)
    records: list[dict[str, Any]] = []
    settle = _settle(env, records)
    start = env.observe()
    q0 = start.human_q_rad.copy()
    dq0 = start.human_dq_rad_s.copy()
    q_target, path_basis = preparation_target_posture(
        q2_target_deg, env.human, plant, study
    )
    final_reference = sleeve_position(q_target, env.human, plant)

    protective_stop = False
    protective_reason = ""
    rom_violation = False
    peak_force = start.sleeve_force_n
    peak_bed = start.bed_force_n
    max_deformation_mm = 1e3 * start.sleeve_deformation_m
    max_bed_penetration_mm = 1e3 * start.bed_penetration_m
    bed_active_transitions = 0
    max_command_step_mm = 0.0
    max_force_command_step_n = 0.0
    previous_reference = sleeve_position(q0, env.human, plant)
    previous_force_command = start.cartesian_force_command_n.copy()
    minimum_reference_clearance_m = math.inf
    steps = int(round(study.trajectory_duration_s / plant.control_dt_s))
    for index in range(steps):
        elapsed = (index + 1) * plant.control_dt_s
        sample = quintic_boundary_sample(
            elapsed, study.trajectory_duration_s, q0, dq0, q_target
        )
        target_position = sleeve_position(sample.q, env.human, plant)
        planar_velocity = sleeve_jacobian(sample.q, env.human) @ sample.dq
        target_velocity = np.array([planar_velocity[0], 0.0, planar_velocity[1]])
        minimum_reference_clearance_m = min(
            minimum_reference_clearance_m,
            _minimum_link_clearance_m(sample.q, env.human, plant),
        )
        max_command_step_mm = max(
            max_command_step_mm, 1e3 * float(np.linalg.norm(target_position - previous_reference))
        )
        step = env.step_cartesian(target_position, target_velocity)
        observation = step.observation
        _record(
            records,
            env,
            observation,
            "BED_ASSISTED_PREPARATION",
            sample.q,
            target_position,
        )
        max_force_command_step_n = max(
            max_force_command_step_n,
            float(np.linalg.norm(observation.cartesian_force_command_n - previous_force_command)),
        )
        previous_reference = target_position
        previous_force_command = observation.cartesian_force_command_n.copy()
        peak_force = max(peak_force, step.peak_sleeve_force_n)
        peak_bed = max(peak_bed, step.peak_bed_force_n)
        max_deformation_mm = max(
            max_deformation_mm, 1e3 * observation.sleeve_deformation_m
        )
        max_bed_penetration_mm = max(
            max_bed_penetration_mm, 1e3 * step.peak_bed_penetration_m
        )
        bed_active_transitions += step.bed_active_transitions
        q_deg = np.degrees(observation.human_q_rad)
        rom_violation = bool(
            np.any(q_deg < -study.rom_tolerance_deg)
            or q_deg[0] > 80.0 + study.rom_tolerance_deg
            or q_deg[1] > 100.0 + study.rom_tolerance_deg
        )
        if step.peak_sleeve_force_n > study.force_bound_n + 1e-6:
            protective_stop = True
            protective_reason = "interaction_force_veto"
            break
        if rom_violation:
            protective_stop = True
            protective_reason = "rom_violation"
            break

    trace = _as_trace(records)
    prep_indices = np.flatnonzero(trace.mode == "BED_ASSISTED_PREPARATION")
    final = env.observe()
    q2_values = trace.q_deg[prep_indices, 1]
    cumulative_max = np.maximum.accumulate(q2_values)
    maximum_reversal = float(np.max(cumulative_max - q2_values))
    q2_gain = float(q2_values[-1] - q2_values[0])
    q2_error = abs(float(np.degrees(final.human_q_rad[1])) - q2_target_deg)
    final_speed = float(np.max(np.abs(np.degrees(final.human_dq_rad_s))))
    target_gate = (
        q2_error <= study.target_tolerance_deg
        and q2_gain > 0.0
        and maximum_reversal <= study.maximum_q2_reversal_deg
        and final_speed <= study.final_speed_tolerance_deg_s
    )
    force_gate = peak_force <= study.force_bound_n + 1e-6
    sleeve_gate = max_deformation_mm <= study.sleeve_deformation_limit_mm
    bed_gate = bed_active_transitions <= study.maximum_bed_active_transitions
    command_gate = (
        max_command_step_mm <= study.command_step_limit_mm
        and max_force_command_step_n <= study.force_command_step_limit_n
    )
    final_q_deg = np.degrees(final.human_q_rad)
    # Natural rest is already below the registered 5 degree soft boundary.
    # The experiment therefore gates against any deeper excursion and requires
    # both coordinates to reach the boundary, instead of pretending rest was
    # initially outside the soft zone.
    soft_depth = np.maximum(0.0, study.soft_limit_start_deg - trace.q_deg[prep_indices])
    initial_soft_depth = soft_depth[0]
    no_soft_worsening = bool(
        np.all(np.max(soft_depth, axis=0) <= initial_soft_depth + 0.05)
    )
    exits_lower_soft_zone = bool(np.all(final_q_deg >= study.soft_limit_start_deg - 0.05))
    soft_gate = no_soft_worsening and exits_lower_soft_zone
    passed = all(
        [
            bool(settle["stable"]),
            target_gate,
            force_gate,
            sleeve_gate,
            bed_gate,
            command_gate,
            soft_gate,
            not rom_violation,
            not protective_stop,
        ]
    )

    achieved_delta_q = final.human_q_rad - q0
    requested_delta_q = q_target - q0
    requested_ee_delta = final_reference - sleeve_position(q0, env.human, plant)
    requested_ee_direction = requested_ee_delta / max(
        float(np.linalg.norm(requested_ee_delta)), 1e-12
    )
    rest_generalized_torque_per_n = (
        sleeve_jacobian(q0, env.human).T @ requested_ee_direction
    )
    achieved_path_fraction = float(
        np.dot(achieved_delta_q, requested_delta_q)
        / max(np.dot(requested_delta_q, requested_delta_q), 1e-12)
    )
    if not settle["stable"]:
        mechanism = "bed_rest_not_stable"
    elif protective_reason == "rom_violation" and final.human_q_rad[1] <= q0[1]:
        mechanism = "bed_constrained_cartesian_load_path_drives_knee_extension_rom_stop"
    elif protective_reason:
        mechanism = protective_reason
    elif not command_gate:
        mechanism = "cartesian_command_discontinuity"
    elif not bed_gate:
        mechanism = "bed_contact_chatter_or_loss"
    elif not sleeve_gate:
        mechanism = "sleeve_deformation_dominates_motion"
    elif not target_gate:
        if final.human_q_rad[1] <= q0[1]:
            mechanism = "bed_load_path_maps_ee_motion_to_knee_extension"
        elif np.linalg.norm(final_reference - final.ee_position_m) > 0.002:
            mechanism = "robot_cartesian_authority_insufficient_under_bed_load"
        else:
            mechanism = "joint_path_to_ee_mapping_does_not_produce_requested_knee_motion"
    elif not soft_gate:
        mechanism = "human_v2_lower_soft_zone_not_cleared"
    else:
        mechanism = "none"

    summary = {
        "target_q2_deg": q2_target_deg,
        "status": "PASS" if passed else "FAIL",
        "direct_mechanism": mechanism,
        "settle": settle,
        "path_basis": path_basis,
        "target_q_deg": np.degrees(q_target).tolist(),
        "measured_final_q_deg": final_q_deg.tolist(),
        "measured_final_dq_deg_s": np.degrees(final.human_dq_rad_s).tolist(),
        "q2_gain_deg": q2_gain,
        "q2_target_error_deg": q2_error,
        "maximum_q2_reversal_deg": maximum_reversal,
        "achieved_joint_path_fraction": achieved_path_fraction,
        "requested_ee_delta_mm": (1e3 * requested_ee_delta).tolist(),
        "rest_generalized_torque_per_unit_path_force_nm_per_n": (
            rest_generalized_torque_per_n.tolist()
        ),
        "final_ee_error_mm": 1e3 * float(np.linalg.norm(final_reference - final.ee_position_m)),
        "peak_interaction_force_n": peak_force,
        "rest_bed_force_n": settle["rest_bed_force_n"],
        "peak_bed_force_n": peak_bed,
        "final_bed_force_n": final.bed_force_n,
        "bed_active_transitions": bed_active_transitions,
        "max_bed_penetration_mm": max_bed_penetration_mm,
        "maximum_sleeve_deformation_mm": max_deformation_mm,
        "maximum_ee_reference_step_mm": max_command_step_mm,
        "maximum_cartesian_force_command_step_n": max_force_command_step_n,
        "minimum_reference_link_clearance_mm": 1e3 * minimum_reference_clearance_m,
        "protective_stop": protective_stop,
        "rom_violation": rom_violation,
        "inherited_soft_zone_at_start": bool(np.any(initial_soft_depth > 0.0)),
        "no_soft_zone_worsening": no_soft_worsening,
        "exits_lower_soft_zone": exits_lower_soft_zone,
        "mapping_jacobian_max_error": _mapping_error(env.human, plant),
        "gates": {
            "settled_rest": bool(settle["stable"]),
            "stable_monotonic_target_reach": target_gate,
            "interaction_force": force_gate,
            "small_sleeve_deformation": sleeve_gate,
            "stable_bed_contact": bed_gate,
            "command_continuity": command_gate,
            "no_new_soft_or_rom_violation": soft_gate and not rom_violation,
            "no_protective_stop": not protective_stop,
        },
    }
    return summary, trace


def run_staged_preparation(
    study_config: PreparationStudyConfig | None = None,
) -> tuple[dict[str, Any], dict[float, PreparationTrace]]:
    """Run 5 degrees first; run 8/10 only if 5 degrees passes."""

    study = study_config or PreparationStudyConfig()
    results: list[dict[str, Any]] = []
    traces: dict[float, PreparationTrace] = {}
    first, trace = run_preparation_candidate(5.0, study)
    results.append(first)
    traces[5.0] = trace
    if first["status"] == "PASS":
        for candidate in study.target_candidates_deg[1:]:
            result, candidate_trace = run_preparation_candidate(candidate, study)
            results.append(result)
            traces[candidate] = candidate_trace
    summary = {
        "evidence_class": study.evidence_class,
        "study_config": asdict(study),
        "staged_policy": "5 deg first; 8/10 deg only after a 5 deg PASS",
        "candidate_rows": results,
        "tested_candidates_deg": [row["target_q2_deg"] for row in results],
        "five_degree_pass": first["status"] == "PASS",
        "small_angle_preparation_supported": first["status"] == "PASS",
        "scientific_variables_changed": [],
        "frozen_values": {
            "human_v2": True,
            "bed_contact_parameters": True,
            "bilateral_sleeve": True,
            "cr12_like_robot": True,
            "force_bound_n": study.force_bound_n,
            "normal_controller_used": False,
            "windowed_nls_r3c_r4_used": False,
        },
    }
    return summary, traces


def _plot_trace(path: Path, summary: dict[str, Any], trace: PreparationTrace) -> None:
    prep = np.flatnonzero(trace.mode == "BED_ASSISTED_PREPARATION")
    modes = ["BED_REST_SETTLE", "BED_ASSISTED_PREPARATION"]
    mode_values = np.array([modes.index(item) for item in trace.mode])
    fig, axes = plt.subplots(6, 1, figsize=(11, 14), sharex=True, constrained_layout=True)
    axes[0].plot(trace.time_s, trace.q_deg[:, 0], label="q1 measured")
    axes[0].plot(trace.time_s, trace.q_reference_deg[:, 0], "--", label="q1 path")
    axes[0].plot(trace.time_s, trace.q_deg[:, 1], label="q2 measured")
    axes[0].plot(trace.time_s, trace.q_reference_deg[:, 1], "--", label="q2 path")
    axes[0].set_ylabel("joint angle (deg)")
    axes[0].legend(ncol=2)
    axes[1].plot(trace.time_s, trace.ee_position_m[:, 0], label="EE x actual")
    axes[1].plot(trace.time_s, trace.ee_reference_m[:, 0], "--", label="EE x cmd")
    axes[1].plot(trace.time_s, trace.ee_position_m[:, 2], label="EE z actual")
    axes[1].plot(trace.time_s, trace.ee_reference_m[:, 2], "--", label="EE z cmd")
    axes[1].set_ylabel("EE position (m)")
    axes[1].legend(ncol=2)
    ee_error = 1e3 * np.linalg.norm(trace.ee_reference_m - trace.ee_position_m, axis=1)
    axes[2].plot(trace.time_s[prep], ee_error[prep])
    axes[2].set_ylabel("EE error (mm)")
    axes[3].plot(trace.time_s, trace.interaction_force_n)
    axes[3].axhline(200.0, color="r", linestyle="--", label="veto")
    axes[3].set_ylabel("interaction (N)")
    axes[3].legend()
    axes[4].plot(trace.time_s, trace.bed_force_n, label="bed force")
    axes[4].step(
        trace.time_s,
        (trace.bed_force_n >= 2.0).astype(float) * np.nanmax(trace.bed_force_n),
        where="post",
        alpha=0.25,
        label="bed active",
    )
    axes[4].set_ylabel("bed force (N)")
    axes[4].legend()
    axes[5].step(trace.time_s, mode_values, where="post")
    axes[5].set_yticks(range(len(modes)), modes)
    axes[5].set_ylabel("mode")
    axes[5].set_xlabel("time (s)")
    for axis in axes:
        axis.grid(alpha=0.2)
    fig.suptitle(
        f"Bed-assisted preparation to 5 deg: {summary['candidate_rows'][0]['status']}"
    )
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _write_gif(path: Path, trace: PreparationTrace) -> None:
    frame_count = max(2, int(math.ceil((trace.time_s[-1] - trace.time_s[0]) * 12)))
    frame_indices = np.unique(np.linspace(0, len(trace.time_s) - 1, frame_count).astype(int))
    fig = plt.figure(figsize=(10, 6.4), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    scene = fig.add_subplot(grid[:, 0])
    joints = fig.add_subplot(grid[0, 1])
    forces = fig.add_subplot(grid[1, 1])

    def draw(frame: int) -> None:
        index = int(frame_indices[frame])
        scene.clear()
        joints.clear()
        forces.clear()
        robot = trace.robot_chain_position_m[index]
        q1, q2 = np.radians(trace.q_deg[index])
        hip = np.array([0.0, 0.062])
        knee = hip + 0.43688 * np.array([math.cos(q1), math.sin(q1)])
        ankle = knee + 0.40076 * np.array([math.cos(q1 - q2), math.sin(q1 - q2)])
        scene.axhline(0.012, color="#5f8faa", linewidth=7)
        scene.plot(robot[:, 0], robot[:, 2], "o-", color="#28558c", label="robot")
        scene.plot(
            [hip[0], knee[0], ankle[0]],
            [hip[1], knee[1], ankle[1]],
            "o-",
            color="#df7c25",
            linewidth=4,
            label="Human V2",
        )
        sleeve = trace.sleeve_position_m[index]
        scene.scatter(sleeve[0], sleeve[2], s=100, color="#9c36c7", label="sleeve")
        scene.set_xlim(-0.1, 1.25)
        scene.set_ylim(-0.04, 0.9)
        scene.set_aspect("equal")
        scene.grid(alpha=0.2)
        scene.legend(fontsize=8)
        scene.set_title(f"{trace.mode[index]}  t={trace.time_s[index]:.2f}s")
        joints.plot(trace.time_s[: index + 1], trace.q_deg[: index + 1, 0], label="q1")
        joints.plot(trace.time_s[: index + 1], trace.q_deg[: index + 1, 1], label="q2")
        joints.plot(
            trace.time_s[: index + 1],
            trace.q_reference_deg[: index + 1, 1],
            "--",
            label="q2 path",
        )
        joints.set_xlim(trace.time_s[0], trace.time_s[-1])
        joints.set_ylim(-1.0, 7.0)
        joints.set_ylabel("angle (deg)")
        joints.grid(alpha=0.2)
        joints.legend(fontsize=8)
        forces.plot(
            trace.time_s[: index + 1],
            trace.interaction_force_n[: index + 1],
            label="interaction",
        )
        forces.plot(trace.time_s[: index + 1], trace.bed_force_n[: index + 1], label="bed")
        forces.axhline(200.0, color="r", linestyle="--")
        forces.set_xlim(trace.time_s[0], trace.time_s[-1])
        forces.set_ylim(0.0, max(210.0, 1.1 * np.max(trace.bed_force_n)))
        forces.set_xlabel("time (s)")
        forces.set_ylabel("force (N)")
        forces.grid(alpha=0.2)
        forces.legend(fontsize=8)

    animation = FuncAnimation(fig, draw, frames=len(frame_indices), interval=1000 / 12)
    animation.save(path, writer=PillowWriter(fps=12))
    plt.close(fig)


def write_preparation_artifacts(
    output_dir: Path,
    summary: dict[str, Any],
    traces: dict[float, PreparationTrace],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    fields = [
        "target_q2_deg",
        "status",
        "direct_mechanism",
        "q2_gain_deg",
        "q2_target_error_deg",
        "peak_interaction_force_n",
        "rest_bed_force_n",
        "final_bed_force_n",
        "maximum_sleeve_deformation_mm",
        "final_ee_error_mm",
        "protective_stop",
    ]
    lines = [",".join(fields)]
    for row in summary["candidate_rows"]:
        lines.append(",".join(str(row[field]) for field in fields))
    (output_dir / "preparation_results.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    trace = traces[5.0]
    _plot_trace(output_dir / "resting_to_5deg_timeseries.png", summary, trace)
    _write_gif(output_dir / "resting_to_5deg_synchronized.gif", trace)
    np.savez_compressed(
        output_dir / "preparation_traces.npz",
        **{
            f"q{candidate:g}__{field}": value
            for candidate, candidate_trace in traces.items()
            for field, value in asdict(candidate_trace).items()
            if isinstance(value, np.ndarray)
        },
    )
