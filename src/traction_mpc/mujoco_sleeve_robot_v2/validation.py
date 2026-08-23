"""Reproducible engineering diagnostics for the MuJoCo sleeve/robot plant V2.

These routines are intentionally gate-driven.  They do not tune the plant and
they do not run the complete protective-mode motion unless every local posture
has first demonstrated a releasable equilibrium and bidirectional authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
from scipy.optimize import least_squares

from .config import HumanV2Parameters, PlantV2Config, RobotV2Parameters
from .environment import PlantObservation, SleeveRobotEnvironment
from .kinematics import (
    coordinated_posture,
    coordinated_sleeve_direction,
    quintic_progress,
    sleeve_jacobian,
)


POSTURES_DEG = (2.0, 10.0, 20.0, 30.0)
RIGID_CUFF_POSTURES_DEG = (0.0, 2.0, 3.0, 5.0, 10.0, 20.0)


def _human_v2_mass_matrix(q_rad: np.ndarray, human: HumanV2Parameters) -> np.ndarray:
    q2 = float(q_rad[1])
    b = human.shank_inertia_kg_m2 + human.shank_mass_kg * human.shank_com_m**2
    d = human.shank_mass_kg * human.thigh_length_m * human.shank_com_m
    a = (
        human.thigh_inertia_kg_m2
        + human.thigh_mass_kg * human.thigh_com_m**2
        + b
        + human.shank_mass_kg * human.thigh_length_m**2
    )
    return np.array(
        [
            [a + 2.0 * d * math.cos(q2), -(b + d * math.cos(q2))],
            [-(b + d * math.cos(q2)), b],
        ]
    )


def _human_v2_static_hold_torque(
    q_rad: np.ndarray, human: HumanV2Parameters
) -> np.ndarray:
    q1, q2 = q_rad
    phi = q1 - q2
    gravity = np.array(
        [
            human.gravity_m_s2
            * (
                (human.thigh_mass_kg * human.thigh_com_m
                 + human.shank_mass_kg * human.thigh_length_m)
                * math.cos(q1)
                + human.shank_mass_kg * human.shank_com_m * math.cos(phi)
            ),
            -human.shank_mass_kg
            * human.gravity_m_s2
            * human.shank_com_m
            * math.cos(phi),
        ]
    )
    spring_left = np.asarray(human.passive_stiffness_nm_rad) * (
        q_rad - np.asarray(human.q_rest_rad)
    )
    lower_activation = (
        np.asarray(human.q_min_rad)
        + human.soft_limit_margin_rad
        - human.soft_limit_numerical_tolerance_rad
    )
    upper_activation = (
        np.asarray(human.q_max_rad)
        - human.soft_limit_margin_rad
        + human.soft_limit_numerical_tolerance_rad
    )
    soft_rhs = np.zeros(2)
    for index in range(2):
        if q_rad[index] < lower_activation[index]:
            z = (lower_activation[index] - q_rad[index]) / human.soft_limit_margin_rad
            soft_rhs[index] = human.soft_limit_boundary_torque_nm * z**3
        elif q_rad[index] > upper_activation[index]:
            z = (q_rad[index] - upper_activation[index]) / human.soft_limit_margin_rad
            soft_rhs[index] = -human.soft_limit_boundary_torque_nm * z**3
    return gravity + spring_left - soft_rhs


def _minimum_translation_cuff_wrench(
    force_map: np.ndarray, hold_torque: np.ndarray
) -> np.ndarray:
    """Minimize translational force with an unbounded sagittal cuff moment.

    No force/moment weighting or moment limit is introduced.  Projecting the
    two equilibrium equations onto the complement of the moment column leaves
    one scalar constraint whose minimum-norm force has a closed-form solution.
    """

    moment_map = np.array([-1.0, 1.0])
    moment_orthogonal = np.array([1.0, 1.0]) / math.sqrt(2.0)
    projected_force_map = force_map.T @ moment_orthogonal
    projected_torque = float(moment_orthogonal @ hold_torque)
    denominator = float(projected_force_map @ projected_force_map)
    if denominator <= 1e-18:
        raise RuntimeError("cuff force map cannot satisfy moment-compatible equilibrium")
    force = projected_force_map * projected_torque / denominator
    moment = float(
        moment_map @ (hold_torque - force_map @ force)
        / (moment_map @ moment_map)
    )
    return np.array([force[0], force[1], moment])


def run_rigid_cuff_posture_validation(
    postures_deg: tuple[float, ...] = RIGID_CUFF_POSTURES_DEG,
) -> list[dict[str, Any]]:
    """Validate the revised plant statically before any protective trajectory.

    Bed contact is disabled only inside this suspended-equilibrium check so the
    cuff load can be compared directly with the former point-force assumption.
    The built plant and its normal runtime bed contact are not changed.
    """

    rows: list[dict[str, Any]] = []
    for q2_deg in postures_deg:
        env = SleeveRobotEnvironment()
        reset_observation = env.reset(q2_deg)
        env.model.geom("bed").contype = 0
        env.model.geom("bed").conaffinity = 0
        mujoco.mj_forward(env.model, env.data)

        q = coordinated_posture(math.radians(q2_deg))
        full_mass = np.zeros((env.model.nv, env.model.nv))
        mujoco.mj_fullM(env.model, env.data, full_mass)
        human_dofs = np.array(
            [env.model.joint(name).dofadr[0] for name in ("hip_joint", "knee_joint")]
        )
        mujoco_mass = full_mass[np.ix_(human_dofs, human_dofs)]
        analytical_mass = _human_v2_mass_matrix(q, env.human)
        mass_error = float(np.max(np.abs(mujoco_mass - analytical_mass)))

        hold_torque = _human_v2_static_hold_torque(q, env.human)
        position_jacobian = sleeve_jacobian(q, env.human)[[0, 2], :].T
        cuff_map = np.column_stack([position_jacobian, np.array([-1.0, 1.0])])
        planar_wrench = _minimum_translation_cuff_wrench(
            position_jacobian, hold_torque
        )
        expected_wrench_world = np.array(
            [planar_wrench[0], 0.0, planar_wrench[1], 0.0, planar_wrench[2], 0.0]
        )

        point_rank = int(np.linalg.matrix_rank(position_jacobian, tol=1e-10))
        if point_rank == 2:
            point_force = np.linalg.solve(position_jacobian, hold_torque)
            point_force_norm = float(np.linalg.norm(point_force))
        else:
            point_force_norm = None

        robot_jacobian = env._site_pose_jacobian(env._ee_site_id)[
            :, env._robot_dof_indices
        ]
        robot_torque = env.data.qfrc_bias[env._robot_dof_indices].copy()
        robot_torque += robot_jacobian.T @ expected_wrench_world
        env.data.ctrl[:] = robot_torque
        env.last_joint_torque_command_nm = robot_torque.copy()
        env._apply_human_soft_limit()
        mujoco.mj_forward(env.model, env.data)
        observation = env.observe()

        torque_limits = np.asarray(env.robot.joint_torque_limits_nm)
        analytical_force_norm = float(np.linalg.norm(planar_wrench[:2]))
        force_reduction = None
        if q2_deg == 3.0:
            force_reduction = 100.0 * (1.0 - analytical_force_norm / 348.0)
        rows.append(
            {
                "q2_deg": q2_deg,
                "q1_deg": float(math.degrees(q[0])),
                "mass_matrix_max_abs_error": mass_error,
                "relative_position_error_mm": 1e3 * observation.sleeve_deformation_m,
                "relative_rotation_error_deg": math.degrees(
                    observation.sleeve_relative_rotation_rad
                ),
                "cuff_force_n": analytical_force_norm,
                "cuff_force_vector_n": expected_wrench_world[:3].tolist(),
                "cuff_my_nm": float(planar_wrench[2]),
                "static_wrench_equation_residual_nm": float(
                    np.linalg.norm(cuff_map @ planar_wrench - hold_torque)
                ),
                "translational_force_gate_passed": bool(
                    analytical_force_norm <= env.config.force_veto_bound_n + 1e-9
                ),
                "point_force_requirement_n": point_force_norm,
                "robot_peak_torque_nm": float(np.max(np.abs(robot_torque))),
                "robot_peak_torque_limit_fraction": float(
                    np.max(np.abs(robot_torque) / torque_limits)
                ),
                "robot_torque_limits_respected": bool(
                    np.all(np.abs(robot_torque) <= torque_limits + 1e-9)
                ),
                "wrench_reconstruction_residual_nm": (
                    observation.sleeve_wrench_reconstruction_residual_nm
                ),
                "solver_probe_force_n": observation.sleeve_force_n,
                "solver_probe_my_nm": observation.sleeve_moment_my_nm,
                "force_reduction_vs_previous_348n_percent": force_reduction,
                "reset_position_error_mm": 1e3
                * float(
                    np.linalg.norm(
                        reset_observation.ee_position_m
                        - reset_observation.sleeve_position_m
                    )
                ),
                "reset_rotation_error_deg": math.degrees(
                    reset_observation.sleeve_relative_rotation_rad
                ),
            }
        )
    return rows


def write_rigid_cuff_posture_artifacts(
    output_dir: Path, rows: list[dict[str, Any]]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "evidence_category": "engineering_validation_smoke",
        "protective_trajectory_run": False,
        "static_wrench_definition": (
            "minimum translational force satisfying suspended Human V2 static "
            "equilibrium with unconstrained sagittal cuff moment"
        ),
        "bed_contact_in_static_check": False,
        "solver_probe_is_static_equilibrium": False,
        "solver_probe_purpose": (
            "validate equality generalized-force to physical site-wrench reconstruction"
        ),
        "postures_deg": [row["q2_deg"] for row in rows],
        "force_gate_n": PlantV2Config().force_veto_bound_n,
        "moment_limit_nm": None,
        "rows": rows,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    fieldnames = [
        "q2_deg",
        "q1_deg",
        "mass_matrix_max_abs_error",
        "relative_position_error_mm",
        "relative_rotation_error_deg",
        "cuff_force_n",
        "cuff_my_nm",
        "point_force_requirement_n",
        "robot_peak_torque_nm",
        "robot_peak_torque_limit_fraction",
        "robot_torque_limits_respected",
        "translational_force_gate_passed",
        "static_wrench_equation_residual_nm",
        "wrench_reconstruction_residual_nm",
        "force_reduction_vs_previous_348n_percent",
    ]
    with (output_dir / "posture_validation.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {name: row[name] for name in fieldnames}
            for row in rows
        )


@dataclass(frozen=True)
class SegmentTrace:
    time_s: np.ndarray
    q_deg: np.ndarray
    dq_deg_s: np.ndarray
    ee_position_m: np.ndarray
    sleeve_position_m: np.ndarray
    sleeve_force_vector_n: np.ndarray
    sleeve_force_n: np.ndarray
    sleeve_deformation_mm: np.ndarray
    bed_force_n: np.ndarray
    bed_penetration_mm: np.ndarray
    bed_contact_count: np.ndarray
    human_dynamics_residual_nm: np.ndarray
    peak_sleeve_force_n: float
    peak_bed_force_n: float
    peak_bed_penetration_mm: float
    bed_active_transitions: int
    bed_contact_count_transitions: int


def _trace_from_records(
    observations: list[PlantObservation],
    peaks: list[tuple[float, float, float, int, int]],
) -> SegmentTrace:
    return SegmentTrace(
        time_s=np.array([obs.time_s for obs in observations]),
        q_deg=np.degrees(np.array([obs.human_q_rad for obs in observations])),
        dq_deg_s=np.degrees(np.array([obs.human_dq_rad_s for obs in observations])),
        ee_position_m=np.array([obs.ee_position_m for obs in observations]),
        sleeve_position_m=np.array([obs.sleeve_position_m for obs in observations]),
        sleeve_force_vector_n=np.array(
            [obs.sleeve_force_vector_n for obs in observations]
        ),
        sleeve_force_n=np.array([obs.sleeve_force_n for obs in observations]),
        sleeve_deformation_mm=1e3
        * np.array([obs.sleeve_deformation_m for obs in observations]),
        bed_force_n=np.array([obs.bed_force_n for obs in observations]),
        bed_penetration_mm=1e3
        * np.array([obs.bed_penetration_m for obs in observations]),
        bed_contact_count=np.array(
            [obs.bed_contact_count for obs in observations], dtype=int
        ),
        human_dynamics_residual_nm=np.array(
            [obs.human_dynamics_residual_nm for obs in observations]
        ),
        peak_sleeve_force_n=max((item[0] for item in peaks), default=0.0),
        peak_bed_force_n=max((item[1] for item in peaks), default=0.0),
        peak_bed_penetration_mm=1e3
        * max((item[2] for item in peaks), default=0.0),
        bed_active_transitions=sum(item[3] for item in peaks),
        bed_contact_count_transitions=sum(item[4] for item in peaks),
    )


def _run_target(
    env: SleeveRobotEnvironment,
    duration_s: float,
    target: Callable[[float], tuple[np.ndarray, np.ndarray]],
) -> SegmentTrace:
    observations = [env.observe()]
    peaks: list[tuple[float, float, float, int, int]] = []
    start = env.data.time
    steps = int(round(duration_s / env.config.control_dt_s))
    for step_index in range(steps):
        elapsed = step_index * env.config.control_dt_s
        position, velocity = target(elapsed)
        result = env.step_cartesian(position, velocity)
        observations.append(result.observation)
        peaks.append(
            (
                result.peak_sleeve_force_n,
                result.peak_bed_force_n,
                result.peak_bed_penetration_m,
                result.bed_active_transitions,
                result.bed_contact_count_transitions,
            )
        )
    trace = _trace_from_records(observations, peaks)
    return SegmentTrace(**{**asdict(trace), "time_s": trace.time_s - start})


def _hold(
    env: SleeveRobotEnvironment, target_position_m: np.ndarray, duration_s: float
) -> SegmentTrace:
    target = np.asarray(target_position_m).copy()
    return _run_target(env, duration_s, lambda _: (target, np.zeros(3)))


def _settle_until_stable(
    env: SleeveRobotEnvironment, target_position_m: np.ndarray
) -> tuple[SegmentTrace, bool]:
    """Hold until the registered tail gate passes or the max time is reached."""

    target = np.asarray(target_position_m).copy()
    observations = [env.observe()]
    peaks: list[tuple[float, float, float, int, int]] = []
    stable = False
    max_steps = int(round(env.config.settle_max_time_s / env.config.control_dt_s))
    window_steps = int(round(env.config.settle_window_s / env.config.control_dt_s))
    min_steps = int(round(env.config.settle_min_time_s / env.config.control_dt_s))
    for step_index in range(max_steps):
        result = env.step_cartesian(target, np.zeros(3))
        observations.append(result.observation)
        peaks.append(
            (
                result.peak_sleeve_force_n,
                result.peak_bed_force_n,
                result.peak_bed_penetration_m,
                result.bed_active_transitions,
                result.bed_contact_count_transitions,
            )
        )
        if step_index + 1 < min_steps or len(observations) <= window_steps:
            continue
        tail = observations[-window_steps:]
        max_joint_speed = max(
            float(np.max(np.abs(np.degrees(obs.human_dq_rad_s)))) for obs in tail
        )
        max_ee_speed = 1e3 * max(
            float(np.linalg.norm(obs.ee_velocity_m_s)) for obs in tail
        )
        bed_force_range = max(obs.bed_force_n for obs in tail) - min(
            obs.bed_force_n for obs in tail
        )
        stable = (
            max_joint_speed <= env.config.stable_joint_speed_deg_s
            and max_ee_speed <= env.config.stable_ee_speed_mm_s
            and bed_force_range <= env.config.stable_force_range_n
        )
        if stable:
            break
    return _trace_from_records(observations, peaks), stable


def _minimum_jerk_move(
    env: SleeveRobotEnvironment,
    start_position_m: np.ndarray,
    displacement_m: np.ndarray,
    duration_s: float,
) -> SegmentTrace:
    start = np.asarray(start_position_m).copy()
    displacement = np.asarray(displacement_m).copy()

    def target(elapsed: float) -> tuple[np.ndarray, np.ndarray]:
        progress, dprogress, _ = quintic_progress(elapsed / duration_s)
        return (
            start + displacement * progress,
            displacement * dprogress / duration_s,
        )

    return _run_target(env, duration_s, target)


def _tail_metrics(trace: SegmentTrace, window_s: float) -> dict[str, float]:
    mask = trace.time_s >= max(0.0, trace.time_s[-1] - window_s)
    return {
        "max_abs_joint_speed_deg_s": float(np.max(np.abs(trace.dq_deg_s[mask]))),
        "max_ee_speed_mm_s": float(
            1e3
            * np.max(
                np.linalg.norm(
                    np.gradient(trace.ee_position_m[mask], trace.time_s[mask], axis=0),
                    axis=1,
                )
            )
        ),
        "bed_force_range_n": float(np.ptp(trace.bed_force_n[mask])),
        "max_dynamics_residual_nm": float(
            np.max(np.abs(trace.human_dynamics_residual_nm[mask]))
        ),
    }


def run_bed_start(config: PlantV2Config | None = None) -> tuple[dict[str, Any], SegmentTrace]:
    """Settle from the frozen 2 degree initialization without a fixture."""

    env = SleeveRobotEnvironment(config=config)
    initial = env.reset(env.config.q_terminal_deg)
    trace, stable = _settle_until_stable(env, initial.ee_position_m)
    tail = _tail_metrics(trace, env.config.settle_window_s)
    summary = {
        "initialized_q2_deg": env.config.q_terminal_deg,
        "robot_command_during_settle": "hold initial EE position with zero offset",
        "resting_q_deg": trace.q_deg[-1].tolist(),
        "resting_dq_deg_s": trace.dq_deg_s[-1].tolist(),
        "stable_by_registered_tail_gate": bool(stable),
        "settle_time_s": float(trace.time_s[-1]),
        "tail_metrics": tail,
        "peak_bed_force_n": trace.peak_bed_force_n,
        "final_bed_force_n": float(trace.bed_force_n[-1]),
        "max_bed_penetration_mm": trace.peak_bed_penetration_mm,
        "bed_active_transitions": trace.bed_active_transitions,
        "bed_contact_count_transitions": trace.bed_contact_count_transitions,
        "peak_sleeve_force_n": trace.peak_sleeve_force_n,
        "final_sleeve_force_n": float(trace.sleeve_force_n[-1]),
        "final_sleeve_deformation_mm": float(trace.sleeve_deformation_mm[-1]),
        "terminal_2deg_held_without_preload": bool(
            abs(trace.q_deg[-1, 1] - env.config.q_terminal_deg)
            <= env.config.terminal_position_tolerance_deg
        ),
    }
    return summary, trace


def run_fixture_probe(
    q2_deg: float, sign: int, config: PlantV2Config | None = None
) -> tuple[dict[str, Any], SegmentTrace]:
    """Check topology and force direction with human joints mechanically fixed."""

    env = SleeveRobotEnvironment(fixture_q2_deg=q2_deg, config=config)
    initial = env.reset(q2_deg)
    nominal = initial.ee_position_m.copy()
    _hold(env, nominal, 1.0)
    start = env.observe()
    direction = coordinated_sleeve_direction(q2_deg, env.human, env.config) * sign
    displacement = direction * env.config.fixture_probe_displacement_m
    trace = _minimum_jerk_move(
        env, start.ee_position_m, displacement, env.config.fixture_probe_duration_s
    )
    final = env.observe()
    force_delta = final.sleeve_force_vector_n - start.sleeve_force_vector_n
    force_norm = float(np.linalg.norm(force_delta))
    force_direction_cosine = (
        float(np.dot(force_delta, direction) / force_norm) if force_norm > 1e-12 else 0.0
    )
    actual_motion = final.ee_position_m - start.ee_position_m
    actual_motion_projection_mm = 1e3 * float(np.dot(actual_motion, direction))
    deformation_ratio = float(
        final.sleeve_deformation_m / env.config.fixture_probe_displacement_m
    )
    attachment_error_mm = 1e3 * float(
        np.linalg.norm(final.sleeve_position_m - final.ee_position_m)
    )
    passed = (
        force_direction_cosine > 0.95
        and deformation_ratio < 0.10
        and np.max(np.abs(trace.sleeve_force_vector_n))
        <= env.config.actuator_cartesian_force_bound_n + 1e-6
    )
    summary = {
        "q2_deg": q2_deg,
        "direction": "flexion" if sign > 0 else "extension",
        "command_displacement_mm": sign * env.config.fixture_probe_displacement_m * 1e3,
        "actual_ee_projection_mm": sign * actual_motion_projection_mm,
        "force_delta_projection_n": float(np.dot(force_delta, direction)),
        "force_direction_cosine": force_direction_cosine,
        "attachment_error_mm": attachment_error_mm,
        "sleeve_deformation_mm": float(final.sleeve_deformation_m * 1e3),
        "sleeve_deformation_over_command": deformation_ratio,
        "peak_interaction_force_n": trace.peak_sleeve_force_n,
        "max_abs_force_component_n": float(
            np.max(np.abs(trace.sleeve_force_vector_n))
        ),
        "fixture_reaction_start_nm": start.fixture_reaction_nm.tolist(),
        "fixture_reaction_final_nm": final.fixture_reaction_nm.tolist(),
        "passed": bool(passed),
    }
    return summary, trace


def _evaluate_preload(
    q2_deg: float,
    offset_xz_m: np.ndarray,
    config: PlantV2Config,
    duration_s: float,
) -> tuple[SleeveRobotEnvironment, np.ndarray, SegmentTrace]:
    env = SleeveRobotEnvironment(fixture_q2_deg=q2_deg, config=config)
    initial = env.reset(q2_deg)
    target = initial.ee_position_m + np.array([offset_xz_m[0], 0.0, offset_xz_m[1]])
    trace = _hold(env, target, duration_s)
    return env, target, trace


def prepare_dynamic_equilibrium(
    q2_deg: float, config: PlantV2Config | None = None
) -> tuple[dict[str, Any], SegmentTrace]:
    """Bounded deterministic preload search followed by a two-second release."""

    cfg = config or PlantV2Config()

    def residual(offset_xz_m: np.ndarray) -> np.ndarray:
        env, _, _ = _evaluate_preload(
            q2_deg, offset_xz_m, cfg, cfg.preload_settle_s
        )
        return env.observe().fixture_reaction_nm / 20.0

    solution = least_squares(
        residual,
        np.zeros(2),
        bounds=(-0.07 * np.ones(2), 0.07 * np.ones(2)),
        max_nfev=cfg.preload_max_function_evaluations,
        xtol=1e-8,
        ftol=1e-8,
        gtol=1e-8,
    )
    env, target, preload_trace = _evaluate_preload(
        q2_deg, solution.x, cfg, max(0.8, cfg.preload_settle_s)
    )
    fixture_observation = env.observe()
    fixture_reaction_norm = float(np.linalg.norm(fixture_observation.fixture_reaction_nm))
    force_component_peak = float(
        np.max(np.abs(fixture_observation.cartesian_force_command_n))
    )
    interaction_force_norm = float(fixture_observation.sleeve_force_n)
    joint_torque_fraction = float(
        np.max(
            np.abs(fixture_observation.joint_torque_command_nm)
            / np.asarray(env.robot.joint_torque_limits_nm)
        )
    )
    env.release_fixture()
    release_start_q = env.observe().human_q_rad.copy()
    release_trace = _hold(env, target, cfg.release_observation_s)
    tail = _tail_metrics(release_trace, cfg.settle_window_s)
    drift_deg = np.degrees(release_trace.q_deg[-1] * math.pi / 180.0 - release_start_q)
    reaction_gate = fixture_reaction_norm <= cfg.fixture_reaction_tolerance_nm
    force_gate = force_component_peak <= cfg.actuator_cartesian_force_bound_n + 1e-6
    force_veto_gate = interaction_force_norm <= cfg.force_veto_bound_n + 1e-6
    release_gate = (
        abs(drift_deg[1]) <= cfg.terminal_position_tolerance_deg
        and tail["max_abs_joint_speed_deg_s"] <= cfg.stable_joint_speed_deg_s
    )
    deformation_gate = (
        float(fixture_observation.sleeve_deformation_m)
        <= 0.10 * max(float(np.linalg.norm(solution.x)), 1e-9)
    )
    passed = (
        reaction_gate
        and force_gate
        and force_veto_gate
        and release_gate
        and deformation_gate
    )
    summary = {
        "q2_deg": q2_deg,
        "preload_search_scope": "Cartesian x/z offsets bounded to +/-70 mm",
        "preload_offset_mm": (1e3 * solution.x).tolist(),
        "optimizer_nfev": int(solution.nfev),
        "optimizer_success": bool(solution.success),
        "fixture_reaction_nm": fixture_observation.fixture_reaction_nm.tolist(),
        "fixture_reaction_norm_nm": fixture_reaction_norm,
        "sleeve_force_vector_n": fixture_observation.sleeve_force_vector_n.tolist(),
        "interaction_force_norm_n": interaction_force_norm,
        "max_abs_cartesian_command_component_n": force_component_peak,
        "max_joint_torque_limit_fraction": joint_torque_fraction,
        "sleeve_deformation_mm": float(
            fixture_observation.sleeve_deformation_m * 1e3
        ),
        "bed_force_before_release_n": fixture_observation.bed_force_n,
        "release_q_drift_deg": drift_deg.tolist(),
        "release_final_dq_deg_s": release_trace.dq_deg_s[-1].tolist(),
        "release_tail_metrics": tail,
        "reaction_gate": bool(reaction_gate),
        "force_gate": bool(force_gate),
        "force_veto_gate": bool(force_veto_gate),
        "release_stability_gate": bool(release_gate),
        "deformation_gate": bool(deformation_gate),
        "passed": bool(passed),
    }
    return summary, release_trace


def run_dynamic_probe(
    q2_deg: float,
    sign: int,
    equilibrium_summary: dict[str, Any],
    config: PlantV2Config | None = None,
) -> tuple[dict[str, Any], SegmentTrace]:
    """Paired hold-versus-command probe from a released local equilibrium."""

    if not equilibrium_summary["passed"]:
        raise ValueError("dynamic probe requires a passed equilibrium gate")
    cfg = config or PlantV2Config()
    offset = 1e-3 * np.asarray(equilibrium_summary["preload_offset_mm"])
    env, target, _ = _evaluate_preload(q2_deg, offset, cfg, 0.8)
    env.release_fixture()
    _hold(env, target, cfg.release_observation_s)
    snapshot = env.snapshot()

    hold_trace = _hold(env, target, cfg.dynamic_probe_duration_s)
    hold_final = env.observe()
    env.restore(snapshot)
    start = env.observe()
    direction = coordinated_sleeve_direction(q2_deg, env.human, env.config)
    displacement = sign * direction * cfg.dynamic_probe_displacement_m
    probe_trace = _minimum_jerk_move(
        env, target, displacement, cfg.dynamic_probe_duration_s
    )
    probe_final = env.observe()

    delta_q2_deg = math.degrees(
        probe_final.human_q_rad[1] - hold_final.human_q_rad[1]
    )
    delta_ee = probe_final.ee_position_m - hold_final.ee_position_m
    signed_delta_ee_mm = 1e3 * float(np.dot(delta_ee, direction))
    gain = delta_q2_deg / signed_delta_ee_mm
    delta_deformation_mm = 1e3 * (
        probe_final.sleeve_deformation_m - hold_final.sleeve_deformation_m
    )
    deformation_ratio = abs(delta_deformation_mm) / max(abs(signed_delta_ee_mm), 1e-12)
    force_veto_gate = probe_trace.peak_sleeve_force_n <= cfg.force_veto_bound_n + 1e-6
    passed = (
        gain > 0.0
        and deformation_ratio < 0.10
        and np.max(np.abs(probe_trace.sleeve_force_vector_n))
        <= cfg.actuator_cartesian_force_bound_n + 1e-6
        and force_veto_gate
    )
    summary = {
        "q2_deg": q2_deg,
        "direction": "flexion" if sign > 0 else "extension",
        "command_displacement_mm": sign * cfg.dynamic_probe_displacement_m * 1e3,
        "paired_delta_q2_deg": delta_q2_deg,
        "paired_delta_ee_mm": signed_delta_ee_mm,
        "effective_delta_q2_deg_per_mm": gain,
        "paired_sleeve_deformation_delta_mm": delta_deformation_mm,
        "sleeve_deformation_over_actual_ee_motion": deformation_ratio,
        "peak_interaction_force_n": probe_trace.peak_sleeve_force_n,
        "max_abs_force_component_n": float(
            np.max(np.abs(probe_trace.sleeve_force_vector_n))
        ),
        "peak_bed_force_n": probe_trace.peak_bed_force_n,
        "force_veto_gate": bool(force_veto_gate),
        "passed": bool(passed),
    }
    return summary, probe_trace


def run_validation() -> tuple[dict[str, Any], dict[str, SegmentTrace]]:
    """Run the registered V2 plant-validation sequence and apply its gates."""

    cfg = PlantV2Config()
    traces: dict[str, SegmentTrace] = {}
    bed_summary, traces["bed_start"] = run_bed_start(cfg)

    fixture_summaries: list[dict[str, Any]] = []
    for q2_deg in POSTURES_DEG:
        for sign in (-1, 1):
            summary, trace = run_fixture_probe(q2_deg, sign, cfg)
            fixture_summaries.append(summary)
            traces[f"fixture_{q2_deg:g}_{sign:+d}"] = trace
    fixture_gate = all(item["passed"] for item in fixture_summaries)

    equilibrium_summaries: list[dict[str, Any]] = []
    dynamic_summaries: list[dict[str, Any]] = []
    if fixture_gate:
        for q2_deg in POSTURES_DEG:
            summary, trace = prepare_dynamic_equilibrium(q2_deg, cfg)
            equilibrium_summaries.append(summary)
            traces[f"release_{q2_deg:g}"] = trace
            if summary["passed"]:
                for sign in (-1, 1):
                    dynamic_summary, dynamic_trace = run_dynamic_probe(
                        q2_deg, sign, summary, cfg
                    )
                    dynamic_summaries.append(dynamic_summary)
                    traces[f"dynamic_{q2_deg:g}_{sign:+d}"] = dynamic_trace

    dynamic_gate = bool(equilibrium_summaries) and all(
        item["passed"] for item in equilibrium_summaries
    ) and len(dynamic_summaries) == 2 * len(POSTURES_DEG) and all(
        item["passed"] for item in dynamic_summaries
    )
    full_motion_status = (
        "eligible_but_not_run" if fixture_gate and dynamic_gate else "skipped_by_authority_gate"
    )
    robot = RobotV2Parameters()
    summary = {
        "evidence_class": "engineering_validation_smoke",
        "robot_model": {
            "label": robot.model_label,
            "old_asset_found": True,
            "old_asset": robot.provenance_asset,
            "old_asset_reused_for_plant": robot.provenance_reusable_for_kinematics,
            "reason": (
                "visual assembly has one root link, zero joints, zero inertials, "
                "and zero transmissions"
            ),
        },
        "frozen_task_values": {
            "force_component_bound_n": cfg.actuator_cartesian_force_bound_n,
            "q_switch_deg": cfg.q_switch_deg,
            "terminal_q2_deg": cfg.q_terminal_deg,
            "normal_trajectory_changed": False,
        },
        "bed_start": bed_summary,
        "fixture_probes": fixture_summaries,
        "fixture_gate_passed": fixture_gate,
        "dynamic_equilibria": equilibrium_summaries,
        "dynamic_probes": dynamic_summaries,
        "dynamic_authority_gate_passed": dynamic_gate,
        "complete_protective_motion": full_motion_status,
        "q_switch_sweep": "not_run_by_scope",
    }
    return summary, traces


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    lines = [",".join(fields)]
    for row in rows:
        values = []
        for field in fields:
            value = row[field]
            if isinstance(value, bool):
                values.append(str(value).lower())
            else:
                values.append(str(value))
        lines.append(",".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_topology(path: Path) -> None:
    env = SleeveRobotEnvironment()
    env.reset(20.0)
    body_names = [f"robot_link_{index}" for index in range(1, 7)]
    robot_points = np.array([env.data.body(name).xpos for name in body_names])
    robot_points = np.vstack([robot_points, env.data.site("robot_ee_site").xpos])
    hip = env.data.body("hip").xpos.copy()
    knee = env.data.body("shank").xpos.copy()
    sleeve = env.data.site("sleeve_attach_site").xpos.copy()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for axis, first, second, labels in (
        (axes[0], 0, 2, ("x (m)", "z (m)")),
        (axes[1], 0, 1, ("x (m)", "y (m)")),
    ):
        axis.plot(robot_points[:, first], robot_points[:, second], "o-", label="CR12-like arm")
        human_points = np.vstack([hip, knee, sleeve])
        axis.plot(human_points[:, first], human_points[:, second], "o-", label="Human V2 / sleeve")
        axis.scatter(
            [sleeve[first]],
            [sleeve[second]],
            s=100,
            color="#9c36c7",
            label="bilateral sleeve link",
        )
        axis.set_xlabel(labels[0])
        axis.set_ylabel(labels[1])
        axis.grid(alpha=0.25)
        axis.axis("equal")
    axes[0].axhline(env.config.bed_height_m, color="#4e7fa3", linewidth=4, label="unilateral bed")
    axes[0].set_title("Side view")
    axes[1].set_title("Top view")
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("MuJoCo plant V2 topology (engineering assumptions, not CR12 CAD)")
    fig.savefig(path, dpi=170)
    plt.close(fig)


def write_artifacts(
    output_dir: Path, summary: dict[str, Any], traces: dict[str, SegmentTrace]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_csv(
        output_dir / "fixture_authority.csv",
        summary["fixture_probes"],
        [
            "q2_deg",
            "direction",
            "command_displacement_mm",
            "actual_ee_projection_mm",
            "force_delta_projection_n",
            "force_direction_cosine",
            "sleeve_deformation_mm",
            "sleeve_deformation_over_command",
            "peak_interaction_force_n",
            "passed",
        ],
    )
    _write_csv(
        output_dir / "dynamic_equilibrium.csv",
        summary["dynamic_equilibria"],
        [
            "q2_deg",
            "fixture_reaction_norm_nm",
            "interaction_force_norm_n",
            "max_abs_cartesian_command_component_n",
            "max_joint_torque_limit_fraction",
            "sleeve_deformation_mm",
            "bed_force_before_release_n",
            "release_stability_gate",
            "passed",
        ],
    )
    if summary["dynamic_probes"]:
        _write_csv(
            output_dir / "dynamic_authority.csv",
            summary["dynamic_probes"],
            [
                "q2_deg",
                "direction",
                "command_displacement_mm",
                "paired_delta_q2_deg",
                "paired_delta_ee_mm",
                "effective_delta_q2_deg_per_mm",
                "paired_sleeve_deformation_delta_mm",
                "sleeve_deformation_over_actual_ee_motion",
                "peak_interaction_force_n",
                "peak_bed_force_n",
                "passed",
            ],
        )

    bed = traces["bed_start"]
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, constrained_layout=True)
    axes[0].plot(bed.time_s, bed.q_deg[:, 1], label="q2")
    axes[0].axhline(2.0, color="k", linestyle="--", label="initialized q2")
    axes[0].set_ylabel("q2 (deg)")
    axes[0].legend()
    axes[1].plot(bed.time_s, bed.bed_force_n, label="bed force")
    axes[1].set_ylabel("Force (N)")
    axes[1].legend()
    axes[2].plot(bed.time_s, bed.bed_penetration_mm, label="penetration")
    axes[2].step(
        bed.time_s,
        bed.bed_contact_count,
        where="post",
        label="contact count",
    )
    axes[2].set_ylabel("mm / count")
    axes[2].set_xlabel("Time (s)")
    axes[2].legend()
    fig.suptitle("BED_START: initialized 2 deg versus natural resting equilibrium")
    fig.savefig(output_dir / "bed_start_equilibrium.png", dpi=170)
    plt.close(fig)

    fixture = summary["fixture_probes"]
    labels = [f"{int(row['q2_deg'])}/{row['direction'][0]}" for row in fixture]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].bar(labels, [row["force_delta_projection_n"] for row in fixture])
    axes[0].axhline(0.0, color="k", linewidth=0.8)
    axes[0].set_ylabel("Directed force increment (N)")
    axes[0].set_title("Fixture topology probe: correct bilateral force sign")
    axes[1].bar(
        labels, [100 * row["sleeve_deformation_over_command"] for row in fixture]
    )
    axes[1].set_ylabel("Sleeve deformation / 2 mm command (%)")
    axes[1].set_xlabel("q2 deg / e=extension, f=flexion")
    fig.savefig(output_dir / "fixture_authority_comparison.png", dpi=170)
    plt.close(fig)

    equilibria = summary["dynamic_equilibria"]
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), constrained_layout=True)
    q_values = [row["q2_deg"] for row in equilibria]
    axes[0].bar(q_values, [row["fixture_reaction_norm_nm"] for row in equilibria], width=3.0)
    axes[0].axhline(1.0, color="r", linestyle="--", label="release gate")
    axes[0].set_ylabel("Fixture reaction norm (Nm)")
    axes[0].legend()
    for q2_deg in q_values:
        trace = traces[f"release_{q2_deg:g}"]
        axes[1].plot(trace.time_s, trace.q_deg[:, 1] - q2_deg, label=f"{q2_deg:g} deg")
    axes[1].axhline(1.0, color="r", linestyle="--")
    axes[1].axhline(-1.0, color="r", linestyle="--")
    axes[1].set_ylabel("q2 drift after release (deg)")
    axes[1].set_xlabel("Time after release (s)")
    axes[1].legend(ncol=2)
    fig.suptitle("Dynamic equilibrium gate before authority probing")
    fig.savefig(output_dir / "dynamic_equilibrium_gate.png", dpi=170)
    plt.close(fig)

    dynamic = summary["dynamic_probes"]
    if dynamic:
        labels = [f"{int(row['q2_deg'])}/{row['direction'][0]}" for row in dynamic]
        fig, axes = plt.subplots(2, 1, figsize=(9, 7), constrained_layout=True)
        axes[0].bar(
            labels,
            [row["effective_delta_q2_deg_per_mm"] for row in dynamic],
        )
        axes[0].set_ylabel("paired delta q2 / delta EE (deg/mm)")
        axes[0].set_title("Dynamic authority only at released equilibria")
        axes[1].bar(
            labels,
            [
                100 * row["sleeve_deformation_over_actual_ee_motion"]
                for row in dynamic
            ],
        )
        axes[1].set_ylabel("Sleeve deformation / EE motion (%)")
        axes[1].set_xlabel("q2 deg / e=extension, f=flexion")
        fig.savefig(output_dir / "dynamic_authority_comparison.png", dpi=170)
        plt.close(fig)
    _plot_topology(output_dir / "robot_sleeve_topology.png")

    np.savez_compressed(
        output_dir / "diagnostic_traces.npz",
        **{
            f"{name}__{field}": value
            for name, trace in traces.items()
            for field, value in asdict(trace).items()
            if isinstance(value, np.ndarray)
        },
    )
