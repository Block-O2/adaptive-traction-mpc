"""Dynamic fixed-primitive feasibility experiment from a 3 degree floor."""

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
from .contact_feasibility import preparation_q1, preparation_q1_derivative
from .environment import PlantObservation, SleeveRobotEnvironment
from .kinematics import quintic_progress, sleeve_jacobian, sleeve_position


@dataclass(frozen=True)
class DynamicTransitionConfig:
    initial_q2_deg: float = 3.0
    target_candidates_deg: tuple[float, ...] = (10.0, 15.0, 20.0, 25.0, 30.0)
    peak_reference_speed_deg_s: float = 5.0
    target_hold_s: float = 0.5
    target_position_tolerance_deg: float = 0.75
    target_speed_tolerance_deg_s: float = 2.0
    required_target_dwell_s: float = 0.20
    force_gate_n: float = 200.0
    rom_tolerance_deg: float = 0.05
    engineering_floor_tolerance_deg: float = 0.05
    maximum_ee_reference_step_mm: float = 0.20
    include_retained_soft_limit_torque: bool = True
    evidence_class: str = "dynamic_feasibility_diagnostic"


@dataclass(frozen=True)
class DynamicTransitionTrace:
    time_s: np.ndarray
    mode: np.ndarray
    q_deg: np.ndarray
    dq_deg_s: np.ndarray
    qdd_deg_s2: np.ndarray
    q_reference_deg: np.ndarray
    ee_reference_m: np.ndarray
    ee_position_m: np.ndarray
    ee_tracking_error_mm: np.ndarray
    sleeve_force_n: np.ndarray
    sleeve_force_vector_n: np.ndarray
    sleeve_deformation_mm: np.ndarray
    cartesian_command_n: np.ndarray
    joint_torque_command_nm: np.ndarray
    retained_soft_limit_torque_nm: np.ndarray
    bed_force_n: np.ndarray
    bed_contact_count: np.ndarray
    bed_penetration_mm: np.ndarray
    robot_chain_position_m: np.ndarray


def primitive_duration_s(
    start_q2_deg: float,
    target_q2_deg: float,
    config: DynamicTransitionConfig,
) -> float:
    """Duration giving the registered peak q2 speed for quintic progress."""

    delta = abs(target_q2_deg - start_q2_deg)
    if delta <= 0.0:
        raise ValueError("primitive endpoints must differ")
    return 1.875 * delta / config.peak_reference_speed_deg_s


def fixed_primitive_sample(
    elapsed_s: float,
    duration_s: float,
    start_q2_deg: float,
    target_q2_deg: float,
    env: SleeveRobotEnvironment,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return candidate-path q/dq and corresponding Cartesian reference."""

    ratio = float(np.clip(elapsed_s / duration_s, 0.0, 1.0))
    progress, dprogress, _ = quintic_progress(ratio)
    delta_q2 = math.radians(target_q2_deg - start_q2_deg)
    q2 = math.radians(start_q2_deg) + delta_q2 * progress
    dq2 = delta_q2 * dprogress / duration_s
    q1 = preparation_q1(q2, env.human)
    dq1 = preparation_q1_derivative(q2, env.human) * dq2
    q = np.array([q1, q2])
    dq = np.array([dq1, dq2])
    position = sleeve_position(q, env.human, env.config)
    planar_velocity = sleeve_jacobian(q, env.human) @ dq
    velocity = np.array([planar_velocity[0], 0.0, planar_velocity[1]])
    return q, dq, position, velocity


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
    q_reference: np.ndarray,
    ee_reference: np.ndarray,
) -> None:
    records.append(
        {
            "time_s": observation.time_s,
            "mode": mode,
            "q_deg": np.degrees(observation.human_q_rad),
            "dq_deg_s": np.degrees(observation.human_dq_rad_s),
            "qdd_deg_s2": np.degrees(observation.human_qacc_rad_s2),
            "q_reference_deg": np.degrees(q_reference),
            "ee_reference_m": ee_reference,
            "ee_position_m": observation.ee_position_m,
            "ee_tracking_error_mm": 1e3
            * float(np.linalg.norm(ee_reference - observation.ee_position_m)),
            "sleeve_force_n": observation.sleeve_force_n,
            "sleeve_force_vector_n": observation.sleeve_force_vector_n,
            "sleeve_deformation_mm": 1e3 * observation.sleeve_deformation_m,
            "cartesian_command_n": observation.cartesian_force_command_n,
            "joint_torque_command_nm": observation.joint_torque_command_nm,
            "retained_soft_limit_torque_nm": (
                observation.retained_soft_limit_torque_nm
            ),
            "bed_force_n": observation.bed_force_n,
            "bed_contact_count": observation.bed_contact_count,
            "bed_penetration_mm": 1e3 * observation.bed_penetration_m,
            "robot_chain_position_m": _robot_chain(env),
        }
    )


def _as_trace(records: list[dict[str, Any]]) -> DynamicTransitionTrace:
    values = {
        field: np.array([record[field] for record in records])
        for field in DynamicTransitionTrace.__dataclass_fields__
    }
    return DynamicTransitionTrace(**values)


def _soft_active(q_rad: np.ndarray, env: SleeveRobotEnvironment) -> np.ndarray:
    lower = np.asarray(env.human.q_min_rad) + env.human.soft_limit_margin_rad
    upper = np.asarray(env.human.q_max_rad) - env.human.soft_limit_margin_rad
    return (q_rad < lower) | (q_rad > upper)


def run_transition(
    start_q2_deg: float,
    target_q2_deg: float,
    direction: str,
    experiment_config: DynamicTransitionConfig | None = None,
) -> tuple[dict[str, Any], DynamicTransitionTrace]:
    config = experiment_config or DynamicTransitionConfig()
    plant = PlantV2Config()
    env = SleeveRobotEnvironment(
        config=plant,
        include_retained_soft_limit_torque=config.include_retained_soft_limit_torque,
    )
    start_q2 = math.radians(start_q2_deg)
    q_initial = np.array([preparation_q1(start_q2, env.human), start_q2])
    initial = env.reset_posture(q_initial)
    initial_reference = sleeve_position(q_initial, env.human, plant)
    records: list[dict[str, Any]] = []
    _record(records, env, initial, "ENGINEERING_INITIALIZATION", q_initial, initial_reference)

    duration = primitive_duration_s(start_q2_deg, target_q2_deg, config)
    total_steps = int(round((duration + config.target_hold_s) / plant.control_dt_s))
    trajectory_steps = int(round(duration / plant.control_dt_s))
    dwell_steps_required = int(round(config.required_target_dwell_s / plant.control_dt_s))
    target_dwell_steps = 0
    reached_target_region = False
    protective_stop = False
    failure_reason = ""
    peak_force = initial.sleeve_force_n
    peak_bed_force = initial.bed_force_n
    max_bed_penetration = initial.bed_penetration_m
    max_ee_error_mm = 0.0
    max_sleeve_deformation_mm = 1e3 * initial.sleeve_deformation_m
    max_reference_step_mm = 0.0
    bed_active_transitions = 0
    bed_contact_count_transitions = 0
    actuator_component_saturation = False
    rom_violation = False
    floor_violation = False
    previous_reference = initial_reference.copy()

    for index in range(total_steps):
        if index < trajectory_steps:
            elapsed = min((index + 1) * plant.control_dt_s, duration)
            mode = "FORWARD_PROTECTIVE" if direction == "forward" else "REVERSE_PROTECTIVE"
        else:
            elapsed = duration
            mode = "TARGET_HOLD" if direction == "forward" else "FLOOR_HOLD"
        q_reference, _, ee_reference, ee_velocity = fixed_primitive_sample(
            elapsed, duration, start_q2_deg, target_q2_deg, env
        )
        max_reference_step_mm = max(
            max_reference_step_mm,
            1e3 * float(np.linalg.norm(ee_reference - previous_reference)),
        )
        step = env.step_cartesian(ee_reference, ee_velocity)
        observation = step.observation
        _record(records, env, observation, mode, q_reference, ee_reference)
        previous_reference = ee_reference
        peak_force = max(peak_force, step.peak_sleeve_force_n)
        peak_bed_force = max(peak_bed_force, step.peak_bed_force_n)
        max_bed_penetration = max(max_bed_penetration, step.peak_bed_penetration_m)
        max_ee_error_mm = max(
            max_ee_error_mm,
            1e3 * float(np.linalg.norm(ee_reference - observation.ee_position_m)),
        )
        max_sleeve_deformation_mm = max(
            max_sleeve_deformation_mm, 1e3 * observation.sleeve_deformation_m
        )
        bed_active_transitions += step.bed_active_transitions
        bed_contact_count_transitions += step.bed_contact_count_transitions
        actuator_component_saturation = actuator_component_saturation or bool(
            np.any(
                np.abs(observation.cartesian_force_command_n)
                >= plant.actuator_cartesian_force_bound_n - 1e-6
            )
        )
        q_deg = np.degrees(observation.human_q_rad)
        rom_violation = bool(
            np.any(q_deg < -config.rom_tolerance_deg)
            or q_deg[0] > 80.0 + config.rom_tolerance_deg
            or q_deg[1] > 100.0 + config.rom_tolerance_deg
        )
        floor_violation = bool(
            q_deg[1]
            < config.initial_q2_deg - config.engineering_floor_tolerance_deg
        )
        target_error = abs(q_deg[1] - target_q2_deg)
        speed = float(np.max(np.abs(np.degrees(observation.human_dq_rad_s))))
        if (
            target_error <= config.target_position_tolerance_deg
            and speed <= config.target_speed_tolerance_deg_s
        ):
            target_dwell_steps += 1
            reached_target_region = target_dwell_steps >= dwell_steps_required
        else:
            target_dwell_steps = 0
        if step.peak_sleeve_force_n > config.force_gate_n + 1e-6:
            protective_stop = True
            failure_reason = "interaction_force_gate"
        elif rom_violation:
            protective_stop = True
            failure_reason = "rom_violation"
        elif floor_violation:
            protective_stop = True
            failure_reason = "engineering_floor_violation"
        if protective_stop:
            break

    trace = _as_trace(records)
    final = env.observe()
    final_q_deg = np.degrees(final.human_q_rad)
    final_dq_deg_s = np.degrees(final.human_dq_rad_s)
    completed = len(records) - 1 == total_steps
    final_target_error = abs(final_q_deg[1] - target_q2_deg)
    final_speed = float(np.max(np.abs(final_dq_deg_s)))
    command_continuity = max_reference_step_mm <= config.maximum_ee_reference_step_mm
    passed = all(
        [
            completed,
            reached_target_region,
            final_target_error <= config.target_position_tolerance_deg,
            final_speed <= config.target_speed_tolerance_deg_s,
            peak_force <= config.force_gate_n + 1e-6,
            not rom_violation,
            not floor_violation,
            command_continuity,
            not protective_stop,
        ]
    )
    if passed:
        reason = "none"
    elif failure_reason:
        reason = failure_reason
    elif not reached_target_region:
        reason = "target_region_not_reached_with_required_dwell"
    elif final_target_error > config.target_position_tolerance_deg:
        reason = "final_position_error"
    elif final_speed > config.target_speed_tolerance_deg_s:
        reason = "final_speed_not_settled"
    elif not command_continuity:
        reason = "ee_reference_step_limit"
    else:
        reason = "incomplete_transition"
    soft_active_samples = np.array(
        [_soft_active(np.radians(q), env) for q in trace.q_deg]
    )
    return {
        "direction": direction,
        "start_q2_deg": start_q2_deg,
        "target_q2_deg": target_q2_deg,
        "status": "PASS" if passed else "FAIL",
        "failure_reason": reason,
        "primitive_duration_s": duration,
        "target_hold_s": config.target_hold_s,
        "initialized_q_deg": np.degrees(q_initial).tolist(),
        "initial_ee_error_mm": 1e3
        * float(np.linalg.norm(initial_reference - initial.ee_position_m)),
        "initial_bed_force_n": initial.bed_force_n,
        "initial_bed_contact_count": initial.bed_contact_count,
        "initial_soft_limit_torque_nm": initial.retained_soft_limit_torque_nm.tolist(),
        "initial_qacc_deg_s2": np.degrees(initial.human_qacc_rad_s2).tolist(),
        "peak_sleeve_force_n": peak_force,
        "peak_bed_force_n": peak_bed_force,
        "max_bed_penetration_mm": 1e3 * max_bed_penetration,
        "bed_active_transitions": bed_active_transitions,
        "bed_contact_count_transitions": bed_contact_count_transitions,
        "max_ee_tracking_error_mm": max_ee_error_mm,
        "max_sleeve_deformation_mm": max_sleeve_deformation_mm,
        "max_ee_reference_step_mm": max_reference_step_mm,
        "actuator_component_saturation": actuator_component_saturation,
        "retained_soft_limit_active_fraction": float(np.mean(np.any(soft_active_samples, axis=1))),
        "max_abs_retained_soft_limit_torque_nm": np.max(
            np.abs(trace.retained_soft_limit_torque_nm), axis=0
        ).tolist(),
        "reached_target_region": reached_target_region,
        "completed_planned_horizon": completed,
        "protective_stop": protective_stop,
        "rom_violation": rom_violation,
        "engineering_floor_violation": floor_violation,
        "final_q_deg": final_q_deg.tolist(),
        "final_dq_deg_s": final_dq_deg_s.tolist(),
        "final_target_error_deg": final_target_error,
        "final_speed_deg_s": final_speed,
        "gates": {
            "target_region_dwell": reached_target_region,
            "final_position": final_target_error <= config.target_position_tolerance_deg,
            "final_speed": final_speed <= config.target_speed_tolerance_deg_s,
            "interaction_force": peak_force <= config.force_gate_n + 1e-6,
            "rom": not rom_violation,
            "engineering_floor": not floor_violation,
            "command_continuity": command_continuity,
            "no_protective_stop": not protective_stop,
        },
    }, trace


def run_dynamic_transition_matrix(
    experiment_config: DynamicTransitionConfig | None = None,
) -> tuple[dict[str, Any], dict[str, DynamicTransitionTrace]]:
    config = experiment_config or DynamicTransitionConfig()
    traces: dict[str, DynamicTransitionTrace] = {}
    rows = []
    reverse_rows = []
    for target in config.target_candidates_deg:
        result, trace = run_transition(
            config.initial_q2_deg, target, "forward", config
        )
        rows.append(result)
        traces[f"forward_{target:g}"] = trace
        if result["status"] == "PASS":
            reverse, reverse_trace = run_transition(
                target, config.initial_q2_deg, "reverse", config
            )
            reverse_rows.append(reverse)
            traces[f"reverse_{target:g}"] = reverse_trace
    successful_targets = [row["target_q2_deg"] for row in rows if row["status"] == "PASS"]
    reverse_successes = [row["start_q2_deg"] for row in reverse_rows if row["status"] == "PASS"]
    earliest = min(successful_targets) if successful_targets else None
    if successful_targets:
        representative_forward = f"forward_{earliest:g}"
    else:
        informative = max(
            rows,
            key=lambda row: (
                config.initial_q2_deg - row["final_q_deg"][1],
                row["peak_bed_force_n"],
            ),
        )
        representative_forward = f"forward_{informative['target_q2_deg']:g}"
    representative_reverse = (
        f"reverse_{min(row['start_q2_deg'] for row in reverse_rows):g}"
        if reverse_rows
        else None
    )
    return {
        "evidence_class": config.evidence_class,
        "experiment_config": asdict(config),
        "primitive": {
            "joint_path": "q1(q2)=atan2(L2 sin(q2), L1+L2 cos(q2))",
            "progress": "minimum-jerk quintic",
            "peak_reference_q2_speed_deg_s": config.peak_reference_speed_deg_s,
            "cartesian_mapping": "Human V2 sleeve FK and analytic velocity Jacobian",
            "command_interface": "existing finite-impedance Cartesian EE position/velocity",
        },
        "initialization_boundary": {
            "q2_deg": config.initial_q2_deg,
            "meaning": "engineering diagnostic floor; not natural rest or clinical threshold",
            "natural_rest_to_floor_out_of_scope": True,
            "static_equilibrium_required": False,
            "geometric_and_robot_ik_consistency_required": True,
        },
        "model_boundary": {
            "retained_human_v2_soft_limit_included": config.include_retained_soft_limit_torque,
            "implementation": "state-dependent qfrc_applied physical RHS torque",
            "registered_values_unchanged": {
                "margin_deg": 5.0,
                "boundary_torque_nm": 25.0,
                "damping_nms_rad": 2.0,
            },
            "pr22_mjcf_originally_omitted_this_term": True,
        },
        "forward_rows": rows,
        "reverse_rows": reverse_rows,
        "successful_forward_targets_deg": successful_targets,
        "successful_reverse_starts_deg": reverse_successes,
        "continuous_safe_dynamic_bridge_exists": bool(successful_targets),
        "earliest_supported_candidate_region_deg": earliest,
        "representative_forward_trace": representative_forward,
        "representative_reverse_trace": representative_reverse,
        "frozen_values": {
            "human_v2_parameters": True,
            "plant_geometry_mass_inertia": True,
            "bilateral_point_sleeve": True,
            "bed_contact": True,
            "force_gate_n": config.force_gate_n,
            "normal_controller_mpc_learning": False,
        },
        "scientific_variables_changed": [
            "apply retained Human V2 cubic soft-limit RHS torque omitted by PR22 MJCF"
        ],
    }, traces


def _plot_representative(
    path: Path,
    title: str,
    trace: DynamicTransitionTrace,
) -> None:
    fig, axes = plt.subplots(6, 1, figsize=(11, 14), sharex=True, constrained_layout=True)
    axes[0].plot(trace.time_s, trace.q_deg[:, 0], label="q1")
    axes[0].plot(trace.time_s, trace.q_deg[:, 1], label="q2")
    axes[0].plot(trace.time_s, trace.q_reference_deg[:, 1], "--", label="q2 ref")
    axes[0].set_ylabel("angle (deg)")
    axes[0].legend(ncol=3)
    axes[1].plot(trace.time_s, trace.dq_deg_s[:, 0], label="dq1")
    axes[1].plot(trace.time_s, trace.dq_deg_s[:, 1], label="dq2")
    axes[1].set_ylabel("velocity (deg/s)")
    axes[1].legend()
    axes[2].plot(trace.time_s, trace.ee_tracking_error_mm)
    axes[2].set_ylabel("EE error (mm)")
    axes[3].plot(trace.time_s, trace.sleeve_force_n, label="norm")
    axes[3].plot(trace.time_s, trace.sleeve_force_vector_n[:, 0], label="Fx")
    axes[3].plot(trace.time_s, trace.sleeve_force_vector_n[:, 1], label="Fy")
    axes[3].plot(trace.time_s, trace.sleeve_force_vector_n[:, 2], label="Fz")
    axes[3].axhline(200.0, color="r", linestyle=":", label="gate")
    axes[3].set_ylabel("sleeve force (N)")
    axes[3].legend(ncol=5)
    axes[4].plot(trace.time_s, trace.bed_force_n, label="bed force")
    axes[4].step(
        trace.time_s,
        trace.bed_contact_count,
        where="post",
        label="contact count",
    )
    axes[4].set_ylabel("bed evidence")
    axes[4].legend()
    modes = list(dict.fromkeys(trace.mode.tolist()))
    values = np.array([modes.index(mode) for mode in trace.mode])
    axes[5].step(trace.time_s, values, where="post")
    axes[5].set_yticks(range(len(modes)), modes)
    axes[5].set_ylabel("mode")
    axes[5].set_xlabel("time (s)")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle(title)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _write_gif(path: Path, title: str, trace: DynamicTransitionTrace) -> None:
    duration = trace.time_s[-1] - trace.time_s[0]
    if duration < 1.0:
        indices = np.arange(len(trace.time_s))
        frames_per_second = 4
    else:
        frame_count = max(2, int(math.ceil(duration * 12.0)))
        indices = np.unique(
            np.linspace(0, len(trace.time_s) - 1, frame_count).astype(int)
        )
        frames_per_second = 12
    fig = plt.figure(figsize=(10, 6.4), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    scene = fig.add_subplot(grid[:, 0])
    joints = fig.add_subplot(grid[0, 1])
    forces = fig.add_subplot(grid[1, 1])

    def draw(frame: int) -> None:
        index = int(indices[frame])
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
        sleeve = trace.ee_position_m[index]
        scene.scatter(sleeve[0], sleeve[2], s=100, color="#9c36c7", label="sleeve")
        scene.set_xlim(-0.1, 1.25)
        scene.set_ylim(-0.04, 0.9)
        scene.set_aspect("equal")
        scene.grid(alpha=0.2)
        scene.legend(fontsize=8)
        scene.set_title(f"{title}\n{trace.mode[index]} t={trace.time_s[index]:.2f}s")
        joints.plot(trace.time_s[: index + 1], trace.q_deg[: index + 1, 1], label="q2")
        joints.plot(
            trace.time_s[: index + 1],
            trace.q_reference_deg[: index + 1, 1],
            "--",
            label="q2 ref",
        )
        joints.set_xlim(trace.time_s[0], trace.time_s[-1])
        joints.set_ylabel("q2 (deg)")
        joints.grid(alpha=0.2)
        joints.legend(fontsize=8)
        forces.plot(
            trace.time_s[: index + 1], trace.sleeve_force_n[: index + 1], label="sleeve"
        )
        forces.plot(
            trace.time_s[: index + 1], trace.bed_force_n[: index + 1], label="bed"
        )
        forces.axhline(200.0, color="r", linestyle=":")
        forces.set_xlim(trace.time_s[0], trace.time_s[-1])
        forces.set_ylim(0.0, max(210.0, 1.1 * np.max(trace.bed_force_n)))
        forces.set_xlabel("time (s)")
        forces.set_ylabel("force (N)")
        forces.grid(alpha=0.2)
        forces.legend(fontsize=8)

    animation = FuncAnimation(
        fig, draw, frames=len(indices), interval=1000 / frames_per_second
    )
    animation.save(path, writer=PillowWriter(fps=frames_per_second))
    plt.close(fig)


def write_dynamic_transition_artifacts(
    output_dir: Path,
    summary: dict[str, Any],
    traces: dict[str, DynamicTransitionTrace],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else value,
        ),
        encoding="utf-8",
    )
    fields = [
        "direction",
        "start_q2_deg",
        "target_q2_deg",
        "status",
        "failure_reason",
        "peak_sleeve_force_n",
        "reached_target_region",
        "final_q_deg",
        "final_dq_deg_s",
        "max_ee_tracking_error_mm",
        "bed_active_transitions",
        "rom_violation",
        "engineering_floor_violation",
    ]
    lines = [",".join(fields)]
    for row in [*summary["forward_rows"], *summary["reverse_rows"]]:
        values = []
        for field in fields:
            value = row[field]
            if isinstance(value, list):
                value = json.dumps(value, separators=(";", ":"))
            values.append(str(value))
        lines.append(",".join(values))
    (output_dir / "transition_results.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    forward_key = summary["representative_forward_trace"]
    forward_trace = traces[forward_key]
    _plot_representative(
        output_dir / "representative_forward_timeseries.png",
        forward_key,
        forward_trace,
    )
    _write_gif(
        output_dir / "representative_forward.gif", forward_key, forward_trace
    )
    reverse_key = summary["representative_reverse_trace"]
    if reverse_key is not None:
        reverse_trace = traces[reverse_key]
        _plot_representative(
            output_dir / "representative_reverse_timeseries.png",
            reverse_key,
            reverse_trace,
        )
        _write_gif(
            output_dir / "representative_reverse.gif", reverse_key, reverse_trace
        )

    labels = [f"{row['target_q2_deg']:g}" for row in summary["forward_rows"]]
    colors = [
        "#2a9d5b" if row["status"] == "PASS" else "#c94b45"
        for row in summary["forward_rows"]
    ]
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), constrained_layout=True)
    axes[0].bar(
        labels,
        [row["peak_sleeve_force_n"] for row in summary["forward_rows"]],
        color=colors,
    )
    axes[0].axhline(200.0, color="r", linestyle=":")
    axes[0].set_ylabel("peak sleeve force (N)")
    axes[1].bar(labels, [row["final_q_deg"][1] for row in summary["forward_rows"]], color=colors)
    axes[1].plot(
        labels,
        [row["target_q2_deg"] for row in summary["forward_rows"]],
        "k--",
        label="target",
    )
    axes[1].set_ylabel("final q2 (deg)")
    axes[1].legend()
    axes[2].bar(
        labels,
        [row["max_ee_tracking_error_mm"] for row in summary["forward_rows"]],
        color=colors,
    )
    axes[2].set_ylabel("max EE error (mm)")
    axes[2].set_xlabel("forward target q2 (deg)")
    fig.suptitle("Fixed protective primitive candidate comparison")
    fig.savefig(output_dir / "candidate_comparison.png", dpi=170)
    plt.close(fig)

    np.savez_compressed(
        output_dir / "transition_traces.npz",
        **{
            f"{key}__{field}": value
            for key, trace in traces.items()
            for field, value in asdict(trace).items()
            if isinstance(value, np.ndarray)
        },
    )
