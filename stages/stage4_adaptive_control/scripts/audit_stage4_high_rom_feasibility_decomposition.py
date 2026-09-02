#!/usr/bin/env python3
"""Failure-state feasibility decomposition for the frozen High-ROM controller.

This engineering diagnostic hydrates the exact controller history by deterministic
prefix replay, verifies the saved BRAKE-entry integration state, then observes the
existing BRAKE execution.  Shadow MPC, task-retention, and broader BRAKE searches
never alter the command executed by the source replay.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any, Callable, Mapping

import mujoco
import numpy as np
from scipy.optimize import minimize

from run_stage4_high_rom_time_scale_audit import (
    DEFAULT_MATRIX,
    DEFAULT_OUTPUT as TIME_SCALE_OUTPUT,
    FixedExternalTimeScale,
    HIGH_ROM_HUMAN,
    NOMINAL_PATH_DURATION_S,
    REPO_ROOT,
    SnapshotCapturePlant,
    TRAJECTORIES,
    _save_snapshot,
    _scaled_horizon_s,
)
from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    SUSPENDED_SEATED_LIKE_SCENARIO,
)
from traction_mpc_stage3.executable_command import (
    preview_executable_command_from_context,
)
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.mpc import (
    NO_SAFE_ACTION,
    SAFE_ACTION,
    HumanSpaceMPC,
    _step_model,
)
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
    write_strict_json,
)
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    make_stage4_executable_force_filter,
    prepare_executable_force_filter_context,
)
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.track_brake import (
    BRAKE,
    BRAKE_INFEASIBLE,
    TRACK,
    TrackBrakeSupervisor,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "high_rom_feasibility_decomposition_20260902"
)
DEFAULT_SPEC = DEFAULT_OUTPUT / "diagnostic_spec.json"
DEFAULT_SPEC_SHA256 = (
    "a99b6d9586b4075232a23c16ff1b40f96235b8ba2c9e3cd982fc05fa7b0d5a5f"
)
SOURCE_ALPHA = 0.125
FORCE_GATE_N = CUFF_TRANSLATIONAL_FORCE_GATE_N
STATE_SPEC = mujoco.mjtState.mjSTATE_INTEGRATION


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scaled_reference(
    base_reference: Callable[[float], CuffPoseReference],
    *,
    phase_at_anchor_s: float,
    anchor_time_s: float,
    alpha: float,
) -> Callable[[float], CuffPoseReference]:
    def reference(time_s: float) -> CuffPoseReference:
        phase = phase_at_anchor_s + float(alpha) * (float(time_s) - anchor_time_s)
        base = base_reference(phase)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=float(alpha) * base.dq_rad_s,
            ddq_rad_s2=float(alpha) ** 2 * base.ddq_rad_s2,
            world_from_cuff=base.world_from_cuff,
        )

    return reference


class FiveMillisecondReplay:
    """Reusable exact-state plant clone for non-mutating 5 ms command tests."""

    def __init__(self, source_plant: SnapshotCapturePlant) -> None:
        self.plant = SensorBoundaryStage4Plant(
            HIGH_ROM_HUMAN,
            attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        )
        self.plant.reset(source_plant.observe().human_q_rad)
        self.plant.neutral_robot_q = source_plant.neutral_robot_q.copy()

    @staticmethod
    def _warnings(plant: SensorBoundaryStage4Plant) -> dict[str, int]:
        return {str(key): int(value) for key, value in plant.warning_counts().items()}

    def evaluate(
        self,
        source_plant: SnapshotCapturePlant,
        command: Any,
    ) -> dict[str, Any]:
        state = source_plant._integration_state()
        mujoco.mj_setState(self.plant.model, self.plant.data, state, STATE_SPEC)
        mujoco.mj_forward(self.plant.model, self.plant.data)
        self.plant.neutral_robot_q = source_plant.neutral_robot_q.copy()
        warning_before = self._warnings(self.plant)
        observation = self.plant.observe()
        force_norms = [float(np.linalg.norm(observation.cuff_force_vector_n))]
        moment_norms = [float(np.linalg.norm(observation.cuff_moment_vector_nm))]
        human_rom = False
        robot_limit = False
        structural = bool(observation.unintended_contact_pairs)
        human_limits = np.column_stack(
            [HIGH_ROM_HUMAN.q_min_rad, HIGH_ROM_HUMAN.q_max_rad]
        )
        robot_ranges = self.plant.model.jnt_range[self.plant.robot_joint_ids]
        self.plant.apply_executable_command(command)
        for _ in range(CONTROL_SUBSTEPS):
            observation = self.plant.step()
            force_norms.append(float(np.linalg.norm(observation.cuff_force_vector_n)))
            moment_norms.append(float(np.linalg.norm(observation.cuff_moment_vector_nm)))
            human_rom = human_rom or bool(
                np.any(observation.human_q_rad < human_limits[:, 0] - 1e-9)
                or np.any(observation.human_q_rad > human_limits[:, 1] + 1e-9)
            )
            robot_limit = robot_limit or bool(
                np.any(observation.robot_q_rad < robot_ranges[:, 0] - 1e-9)
                or np.any(observation.robot_q_rad > robot_ranges[:, 1] + 1e-9)
            )
            structural = structural or bool(observation.unintended_contact_pairs)
        warning_after = self._warnings(self.plant)
        warning_delta = {
            key: warning_after.get(key, 0) - warning_before.get(key, 0)
            for key in set(warning_before) | set(warning_after)
            if warning_after.get(key, 0) - warning_before.get(key, 0) != 0
        }
        peak_force = max(force_norms)
        return {
            "duration_s": CONTROL_DT_S,
            "physical_force_initial_n": force_norms[0],
            "physical_force_peak_n": peak_force,
            "physical_force_final_n": force_norms[-1],
            "physical_moment_initial_nm": moment_norms[0],
            "physical_moment_peak_nm": max(moment_norms),
            "physical_moment_final_nm": moment_norms[-1],
            "human_rom_event": human_rom,
            "robot_joint_limit_event": robot_limit,
            "mujoco_warning_delta": warning_delta,
            "unintended_structural_contact": structural,
            "safe": bool(
                peak_force <= FORCE_GATE_N + 1e-9
                and not human_rom
                and not robot_limit
                and not warning_delta
                and not structural
            ),
        }


def _task_retention_audit(
    *,
    plant: SnapshotCapturePlant,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
    desired_action_nm: np.ndarray | None,
    replay: FiveMillisecondReplay,
) -> dict[str, Any]:
    if desired_action_nm is None:
        return {
            "available": False,
            "reason": "NO_SAFE_ACTION_has_no_selected_tau_des_to_scale",
        }
    action = np.asarray(desired_action_nm, dtype=float)
    context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        cuff_allocator=cuff_allocator,
        reference=reference,
    )
    nominal_world = np.asarray(
        cuff_allocator.allocate(action, estimated_state[:2], human_model)[
            "wrench_world"
        ],
        dtype=float,
    )
    nominal_sagittal = np.linalg.lstsq(
        context.world_mapping, nominal_world, rcond=None
    )[0]
    feedback = context.command_context.feedback_force_after_clipping_n
    nominal_force = nominal_world[:3]
    null_force = context.world_null_wrench[:3]
    null_squared = float(null_force @ null_force)

    def candidate(gamma: float) -> tuple[float, Any, np.ndarray, np.ndarray]:
        base_force = feedback + float(gamma) * nominal_force
        lam = (
            -float(base_force @ null_force) / null_squared
            if null_squared > 1e-15
            else 0.0
        )
        sagittal = float(gamma) * nominal_sagittal + lam * context.sagittal_null_vector
        world = context.world_mapping @ sagittal
        preview = preview_executable_command_from_context(
            context.command_context, world
        )
        return lam, preview, sagittal, world

    def feasible(gamma: float) -> bool:
        _, preview, _, world = candidate(gamma)
        return bool(
            preview.translational_force_norm_n <= FORCE_GATE_N + 1e-9
            and np.linalg.norm(world[:3]) <= FORCE_GATE_N + 1e-9
        )

    if feasible(1.0):
        gamma_star = 1.0
    elif not feasible(0.0):
        return {
            "available": True,
            "feasible_gamma_found": False,
            "reason": "even_gamma_zero_has_no_force_feasible_null_coordinate",
        }
    else:
        lower, upper = 0.0, 1.0
        for _ in range(60):
            midpoint = 0.5 * (lower + upper)
            if feasible(midpoint):
                lower = midpoint
            else:
                upper = midpoint
        gamma_star = lower
    lam, preview, sagittal, world = candidate(gamma_star)
    applied_tau = context.allocation_matrix @ sagittal
    target_tau = gamma_star * action
    residual = applied_tau - target_tau
    denominator = float(np.linalg.norm(applied_tau) * np.linalg.norm(action))
    direction_cosine = (
        float(applied_tau @ action) / denominator if denominator > 1e-15 else None
    )
    physical = replay.evaluate(plant, preview)
    return {
        "available": True,
        "feasible_gamma_found": True,
        "gamma_star": gamma_star,
        "lambda_star": lam,
        "task_reduction_percent": 100.0 * (1.0 - gamma_star),
        "tau_des_nm": action.tolist(),
        "applied_human_torque_nm": applied_tau.tolist(),
        "human_torque_direction_cosine": direction_cosine,
        "human_torque_equality_residual_nm": float(np.linalg.norm(residual)),
        "nominal_sagittal_wrench": nominal_sagittal.tolist(),
        "selected_sagittal_wrench": sagittal.tolist(),
        "selected_world_wrench": world.tolist(),
        "allocator_force_norm_n": float(np.linalg.norm(world[:3])),
        "command_force_n": preview.translational_force_norm_n,
        "command_force_margin_n": preview.margin_to_force_gate_n,
        "command_moment_norm_nm": float(np.linalg.norm(preview.moment_total_nm)),
        "unclipped_robot_torque_limit_fraction": float(
            np.max(
                np.abs(preview.unclipped_joint_torque_nm)
                / context.command_context.torque_limits_nm
            )
        ),
        "physical_5ms": physical,
    }


def _single_shadow_evaluation(
    *,
    shadow_mpc: HumanSpaceMPC,
    alpha: float,
    trajectory: Any,
    time_s: float,
    plant: SnapshotCapturePlant,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    replay: FiveMillisecondReplay,
) -> dict[str, Any]:
    phase = SOURCE_ALPHA * time_s
    reference_fn = _scaled_reference(
        trajectory.reference,
        phase_at_anchor_s=phase,
        anchor_time_s=time_s,
        alpha=alpha,
    )
    reference = reference_fn(time_s)
    safety_filter = make_stage4_executable_force_filter(
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        cuff_allocator=cuff_allocator,
        reference=reference,
    )
    started = perf_counter()
    action, diagnostics = shadow_mpc.solve(
        estimated_state,
        time_s,
        reference_fn,
        human_model,
        first_action_batch_preview=safety_filter,
    )
    elapsed_ms = 1000.0 * (perf_counter() - started)
    if action is None:
        return {
            "time_s": time_s,
            "alpha": alpha,
            "mpc_status": str(diagnostics.get("status", NO_SAFE_ACTION)),
            "safe": False,
            "reason": "NO_SAFE_ACTION",
            "runtime_ms": elapsed_ms,
        }
    filtered = safety_filter.selected_result(action)
    preview = filtered.filtered_preview
    command_safe = bool(
        filtered.feasible
        and preview.command.translational_force_norm_n <= FORCE_GATE_N + 1e-9
        and float(preview.allocation["force_norm_n"]) <= FORCE_GATE_N + 1e-9
    )
    physical = replay.evaluate(plant, preview.command) if command_safe else None
    safe = bool(command_safe and physical is not None and physical["safe"])
    return {
        "time_s": time_s,
        "alpha": alpha,
        "mpc_status": str(diagnostics.get("status", NO_SAFE_ACTION)),
        "safety_filter_status": filtered.status,
        "command_force_n": preview.command.translational_force_norm_n,
        "allocator_force_n": float(preview.allocation["force_norm_n"]),
        "command_margin_n": preview.command.margin_to_force_gate_n,
        "physical_5ms": physical,
        "safe": safe,
        "reason": "safe" if safe else "command_or_physical_replay_unsafe",
        "runtime_ms": elapsed_ms,
    }


def _candidate_brake_family(
    supervisor: TrackBrakeSupervisor,
    *,
    plant: SnapshotCapturePlant,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rate in supervisor.config.braking_rates_per_s:
        acceleration = supervisor._braking_acceleration(rate)
        reference = supervisor._candidate_reference(acceleration, human_model)
        action = np.asarray(
            human_model.inverse_dynamics(
                estimated_state[:2], estimated_state[2:], acceleration
            ),
            dtype=float,
        )
        context = prepare_executable_force_filter_context(
            plant=plant,
            measurement=measurement,
            estimated_state=estimated_state,
            human_model=human_model,
            cuff_allocator=cuff_allocator,
            reference=reference,
        )
        allocation = cuff_allocator.allocate(
            action, estimated_state[:2], human_model
        )
        world = np.asarray(allocation["wrench_world"], dtype=float)
        sagittal = np.linalg.lstsq(context.world_mapping, world, rcond=None)[0]
        command = preview_executable_command_from_context(
            context.command_context, world
        )
        predicted = _step_model(estimated_state, action, CONTROL_DT_S, human_model)
        speed_before = float(np.linalg.norm(estimated_state[2:]))
        speed_after = float(np.linalg.norm(predicted[2:]))
        power = float(estimated_state[2:] @ action)
        robot_ok = bool(
            np.all(
                np.abs(command.unclipped_joint_torque_nm)
                <= context.command_context.torque_limits_nm + 1e-9
            )
        )
        safe_dissipative = bool(
            np.linalg.norm(world[:3]) <= FORCE_GATE_N + 1e-9
            and command.translational_force_norm_n <= FORCE_GATE_N + 1e-9
            and robot_ok
            and power <= 1e-9
            and speed_after <= speed_before - 1e-9
        )
        candidates.append(
            {
                "rate_per_s": float(rate),
                "reference": reference,
                "context": context,
                "action_nm": action,
                "sagittal_wrench": sagittal,
                "command_force_n": command.translational_force_norm_n,
                "allocator_force_n": float(np.linalg.norm(world[:3])),
                "unclipped_robot_torque_limit_fraction": float(
                    np.max(
                        np.abs(command.unclipped_joint_torque_nm)
                        / context.command_context.torque_limits_nm
                    )
                ),
                "mechanical_power_w": power,
                "predicted_speed_before_rad_s": speed_before,
                "predicted_speed_after_5ms_rad_s": speed_after,
                "safe_dissipative": safe_dissipative,
            }
        )
    return candidates


def _derived_moment_bound(context: Any) -> float:
    command = context.command_context
    fixed_wrench = np.concatenate(
        [
            command.feedback_force_after_clipping_n,
            command.moment_orientation_nm + command.moment_angular_velocity_nm,
        ]
    )
    constant = command.joint_torque_base_nm + fixed_wrench @ command.robot_attachment_jacobian
    coefficient = context.world_mapping.T @ command.robot_attachment_jacobian
    bounds = []
    for joint in range(6):
        moment_coefficient = abs(float(coefficient[2, joint]))
        if moment_coefficient <= 1e-12:
            continue
        worst_force = FORCE_GATE_N * float(np.linalg.norm(coefficient[:2, joint]))
        bounds.append(
            (
                float(command.torque_limits_nm[joint])
                + abs(float(constant[joint]))
                + worst_force
            )
            / moment_coefficient
        )
    if not bounds or not np.isfinite(min(bounds)):
        raise RuntimeError("robot torque constraints did not derive a finite moment bound")
    return float(min(bounds))


def _broader_brake_audit(
    *,
    supervisor: TrackBrakeSupervisor,
    plant: SnapshotCapturePlant,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    replay: FiveMillisecondReplay,
) -> dict[str, Any]:
    family = _candidate_brake_family(
        supervisor,
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        cuff_allocator=cuff_allocator,
    )
    all_family_wrenches = [item["sagittal_wrench"] for item in family]
    speed_before = float(np.linalg.norm(estimated_state[2:]))
    feasible_solutions: list[dict[str, Any]] = []
    optimizer_attempts = 0
    for family_item in family:
        context = family_item["context"]
        reference = family_item["reference"]
        moment_bound = _derived_moment_bound(context)
        starts: list[np.ndarray] = [np.zeros(3)]
        starts.extend(np.asarray(item, dtype=float).copy() for item in all_family_wrenches)
        for force_x in np.linspace(-FORCE_GATE_N, FORCE_GATE_N, 5):
            for force_z in np.linspace(-FORCE_GATE_N, FORCE_GATE_N, 5):
                if math.hypot(force_x, force_z) > FORCE_GATE_N + 1e-9:
                    continue
                for moment in (-moment_bound, 0.0, moment_bound):
                    starts.append(np.array([force_x, force_z, moment], dtype=float))
        unique_starts: list[np.ndarray] = []
        seen: set[tuple[float, float, float]] = set()
        for start in starts:
            clipped = np.array(
                [
                    np.clip(start[0], -FORCE_GATE_N, FORCE_GATE_N),
                    np.clip(start[1], -FORCE_GATE_N, FORCE_GATE_N),
                    np.clip(start[2], -moment_bound, moment_bound),
                ]
            )
            key = tuple(np.round(clipped, 10))
            if key not in seen:
                unique_starts.append(clipped)
                seen.add(key)

        def evaluate(x: np.ndarray) -> dict[str, Any]:
            sagittal = np.asarray(x, dtype=float)
            world = context.world_mapping @ sagittal
            action = context.allocation_matrix @ sagittal
            command = preview_executable_command_from_context(
                context.command_context, world
            )
            predicted = _step_model(
                estimated_state, action, CONTROL_DT_S, human_model
            )
            return {
                "world": world,
                "action": action,
                "command": command,
                "predicted": predicted,
                "allocator_margin": FORCE_GATE_N - float(np.linalg.norm(world[:3])),
                "command_margin": command.margin_to_force_gate_n,
                "robot_margins": context.command_context.torque_limits_nm
                - np.abs(command.unclipped_joint_torque_nm),
                "power_margin": -float(estimated_state[2:] @ action),
                "speed_margin": speed_before
                - float(np.linalg.norm(predicted[2:]))
                - 1e-9,
            }

        def objective(x: np.ndarray) -> float:
            values = evaluate(x)
            return float(np.linalg.norm(values["predicted"][2:]))

        def constraints(x: np.ndarray) -> np.ndarray:
            values = evaluate(x)
            return np.concatenate(
                [
                    np.array(
                        [
                            values["allocator_margin"],
                            values["command_margin"],
                            values["power_margin"],
                            values["speed_margin"],
                        ]
                    ),
                    values["robot_margins"],
                ]
            )

        for start in unique_starts:
            optimizer_attempts += 1
            result = minimize(
                objective,
                start,
                method="SLSQP",
                bounds=[
                    (-FORCE_GATE_N, FORCE_GATE_N),
                    (-FORCE_GATE_N, FORCE_GATE_N),
                    (-moment_bound, moment_bound),
                ],
                constraints=[{"type": "ineq", "fun": constraints}],
                options={"maxiter": 1000, "ftol": 1e-12, "disp": False},
            )
            values = evaluate(result.x)
            minimum_margin = float(np.min(constraints(result.x)))
            if minimum_margin < -1e-7:
                continue
            predicted_q = np.asarray(values["predicted"][:2], dtype=float)
            q_min = np.asarray(human_model.rom_human.q_min_rad, dtype=float)
            q_max = np.asarray(human_model.rom_human.q_max_rad, dtype=float)
            if np.any(predicted_q < q_min - 1e-9) or np.any(predicted_q > q_max + 1e-9):
                continue
            feasible_solutions.append(
                {
                    "reference_rate_per_s": family_item["rate_per_s"],
                    "reference": reference,
                    "context": context,
                    "sagittal_wrench": np.asarray(result.x, dtype=float).copy(),
                    "world_wrench": values["world"].copy(),
                    "action_nm": values["action"].copy(),
                    "command": values["command"],
                    "predicted": values["predicted"].copy(),
                    "minimum_constraint_margin": minimum_margin,
                    "optimizer_success": bool(result.success),
                    "optimizer_message": str(result.message),
                    "moment_search_bound_nm": moment_bound,
                }
            )
    selected = (
        min(
            feasible_solutions,
            key=lambda item: (
                float(np.linalg.norm(item["predicted"][2:])),
                item["command"].translational_force_norm_n,
            ),
        )
        if feasible_solutions
        else None
    )
    family_public = [
        {key: _jsonable(value) for key, value in item.items() if key not in {"reference", "context", "sagittal_wrench", "action_nm"}}
        | {
            "action_nm": item["action_nm"].tolist(),
            "sagittal_wrench": item["sagittal_wrench"].tolist(),
        }
        for item in family
    ]
    output: dict[str, Any] = {
        "current_family": {
            "candidate_count": len(family),
            "safe_dissipative_count": sum(
                bool(item["safe_dissipative"]) for item in family
            ),
            "candidates": family_public,
        },
        "broader_set": {
            "optimizer_attempts": optimizer_attempts,
            "postchecked_feasible_solution_count": len(feasible_solutions),
            "safe_dissipative_action_found": selected is not None,
            "human_action_hard_bounds_present_in_frozen_mpc": False,
            "bounded_domain": "200N_sagittal_force_ball_plus_current_unclipped_robot_torque_limits",
        },
    }
    if selected is not None:
        command = selected["command"]
        physical = replay.evaluate(plant, command)
        current_family_vectors = np.vstack(all_family_wrenches)
        distance = float(
            np.min(
                np.linalg.norm(
                    current_family_vectors - selected["sagittal_wrench"], axis=1
                )
            )
        )
        output["broader_set"]["selected"] = {
            "reference_rate_per_s": selected["reference_rate_per_s"],
            "sagittal_wrench": selected["sagittal_wrench"].tolist(),
            "world_wrench": selected["world_wrench"].tolist(),
            "human_action_nm": selected["action_nm"].tolist(),
            "mechanical_power_w": float(
                estimated_state[2:] @ selected["action_nm"]
            ),
            "predicted_speed_before_rad_s": speed_before,
            "predicted_speed_after_5ms_rad_s": float(
                np.linalg.norm(selected["predicted"][2:])
            ),
            "allocator_force_n": float(
                np.linalg.norm(selected["world_wrench"][:3])
            ),
            "command_force_n": command.translational_force_norm_n,
            "command_margin_n": command.margin_to_force_gate_n,
            "command_moment_norm_nm": float(np.linalg.norm(command.moment_total_nm)),
            "unclipped_robot_torque_limit_fraction": float(
                np.max(
                    np.abs(command.unclipped_joint_torque_nm)
                    / selected["context"].command_context.torque_limits_nm
                )
            ),
            "minimum_constraint_margin": selected["minimum_constraint_margin"],
            "minimum_distance_to_current_family_sagittal_wrench": distance,
            "outside_current_six_candidate_family": distance > 1e-7,
            "moment_search_bound_nm": selected["moment_search_bound_nm"],
            "physical_5ms": physical,
        }
    return output


class DecompositionSupervisor(TrackBrakeSupervisor):
    def __init__(
        self,
        *,
        trajectory: Any,
        source_snapshot: Path,
        actual_mpc_getter: Callable[[], HumanSpaceMPC],
        output_dir: Path,
    ) -> None:
        super().__init__()
        self.trajectory = trajectory
        self.source_snapshot = source_snapshot
        self.actual_mpc_getter = actual_mpc_getter
        self.output_dir = output_dir
        self.entry_time_s: float | None = None
        self.entry_state_error: float | None = None
        self.entry_state_verified = False
        self.shadow_mpcs: dict[float, HumanSpaceMPC] = {}
        self.shadow_records: dict[float, list[dict[str, Any]]] = {
            alpha: [] for alpha in (0.0, 0.125, 0.25)
        }
        self.task_retention: dict[str, Any] | None = None
        self.broader_brake: dict[str, Any] | None = None
        self.replay: FiveMillisecondReplay | None = None
        self.brake_cycle_since_entry = 0
        self.terminal_snapshot_written = False
        self.last_progress_report_s = -math.inf

    def _verify_entry(self, plant: SnapshotCapturePlant) -> None:
        with np.load(self.source_snapshot, allow_pickle=False) as saved:
            expected = np.asarray(saved["mujoco_integration_state"], dtype=float)
        actual = plant._integration_state()
        if actual.shape != expected.shape:
            raise RuntimeError("saved and hydrated integration states differ in shape")
        self.entry_state_error = float(np.max(np.abs(actual - expected)))
        if self.entry_state_error > 1e-10:
            raise RuntimeError(
                f"hydrated BRAKE-entry state mismatch: {self.entry_state_error:.3e}"
            )
        self.entry_state_verified = True

    def _write_terminal_snapshot(
        self,
        *,
        plant: SnapshotCapturePlant,
        measurement: Any,
        estimated_state: np.ndarray,
        decision: Any,
    ) -> None:
        snapshot_dir = self.output_dir / self.trajectory.name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        observation = plant.observe()
        context = plant._context(observation, "controller_termination:BRAKE_INFEASIBLE")
        context.update(
            {
                "estimated_state": np.asarray(estimated_state, dtype=float).tolist(),
                "measurement_arrival_time_s": float(measurement.arrival_time_s),
                "supervisor_status": decision.status,
                "brake_trigger": decision.trigger,
            }
        )
        path = snapshot_dir / "brake_infeasible_snapshot.npz"
        _save_snapshot(
            path,
            plant._integration_state(),
            context,
            alpha=SOURCE_ALPHA,
            trajectory_name=self.trajectory.name,
            kind="missing_exact_BRAKE_INFEASIBLE_terminal_state",
            termination_reason=BRAKE_INFEASIBLE,
        )
        self.terminal_snapshot_written = True

    def command(self, **kwargs: Any) -> Any:
        mode_before = self.mode
        decision = super().command(**kwargs)
        plant = kwargs["plant"]
        measurement = kwargs["measurement"]
        estimated_state = np.asarray(kwargs["estimated_state"], dtype=float)
        human_model = kwargs["human_model"]
        cuff_allocator = kwargs["cuff_allocator"]
        time_s = float(measurement.arrival_time_s)
        entered = mode_before == TRACK and decision.mode == BRAKE
        if entered:
            self.entry_time_s = time_s
            self._verify_entry(plant)
            self.replay = FiveMillisecondReplay(plant)
            actual_mpc = self.actual_mpc_getter()
            self.shadow_mpcs = {
                alpha: copy.deepcopy(actual_mpc)
                for alpha in (0.0, 0.125, 0.25)
            }
            desired = kwargs.get("proposed_action_nm")
            self.task_retention = _task_retention_audit(
                plant=plant,
                measurement=measurement,
                estimated_state=estimated_state,
                human_model=human_model,
                cuff_allocator=cuff_allocator,
                reference=kwargs["track_reference"],
                desired_action_nm=desired,
                replay=self.replay,
            )
            print(
                json.dumps(
                    {
                        "trajectory": self.trajectory.name,
                        "event": "matched_BRAKE_entry",
                        "time_s": time_s,
                        "state_max_abs_error": self.entry_state_error,
                        "gamma_star": self.task_retention.get("gamma_star"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        if self.entry_time_s is not None:
            if self.brake_cycle_since_entry % 4 == 0:
                assert self.replay is not None
                for alpha, shadow_mpc in self.shadow_mpcs.items():
                    record = _single_shadow_evaluation(
                        shadow_mpc=shadow_mpc,
                        alpha=alpha,
                        trajectory=self.trajectory,
                        time_s=time_s,
                        plant=plant,
                        measurement=measurement,
                        estimated_state=estimated_state,
                        human_model=human_model,
                        cuff_allocator=cuff_allocator,
                        replay=self.replay,
                    )
                    self.shadow_records[alpha].append(record)
            self.brake_cycle_since_entry += 1
            if time_s - self.last_progress_report_s >= 20.0:
                self.last_progress_report_s = time_s
                print(
                    json.dumps(
                        {
                            "trajectory": self.trajectory.name,
                            "event": "BRAKE_shadow_progress",
                            "time_s": time_s,
                            "shadow_cycles_per_alpha": len(
                                self.shadow_records[0.0]
                            ),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        if decision.status == BRAKE_INFEASIBLE:
            if self.trajectory.name == "aggressive_both_120_120":
                assert self.replay is not None
                self.broader_brake = _broader_brake_audit(
                    supervisor=self,
                    plant=plant,
                    measurement=measurement,
                    estimated_state=estimated_state,
                    human_model=human_model,
                    cuff_allocator=cuff_allocator,
                    replay=self.replay,
                )
                self._write_terminal_snapshot(
                    plant=plant,
                    measurement=measurement,
                    estimated_state=estimated_state,
                    decision=decision,
                )
        return decision

    def _shadow_summary(self, alpha: float, replay_end_s: float) -> dict[str, Any]:
        records = self.shadow_records[alpha]
        safe = np.asarray([bool(item["safe"]) for item in records], dtype=bool)
        times = np.asarray([float(item["time_s"]) for item in records], dtype=float)
        intervals: list[dict[str, Any]] = []
        index = 0
        while index < len(records):
            if not safe[index]:
                index += 1
                continue
            start = index
            while index + 1 < len(records) and safe[index + 1]:
                index += 1
            end = index
            duration = min(replay_end_s, times[end] + 0.02) - times[start]
            intervals.append(
                {
                    "start_time_s": float(times[start]),
                    "end_time_s": float(times[end]),
                    "duration_s": float(max(0.0, duration)),
                    "cycle_count": int(end - start + 1),
                }
            )
            index += 1
        qualifying = [item for item in intervals if item["cycle_count"] >= 5]
        runtime = np.asarray(
            [float(item["runtime_ms"]) for item in records], dtype=float
        )
        command = np.asarray(
            [
                float(item["command_force_n"])
                for item in records
                if item.get("command_force_n") is not None
            ],
            dtype=float,
        )
        return {
            "alpha": alpha,
            "evaluation_count": len(records),
            "single_safe_cycle_count": int(np.count_nonzero(safe)),
            "safe_track_reappears": bool(qualifying),
            "earliest_warning_time_s": (
                float(times[np.flatnonzero(safe)[0]]) if np.any(safe) else None
            ),
            "earliest_warning_after_brake_entry_s": (
                float(times[np.flatnonzero(safe)[0]] - self.entry_time_s)
                if np.any(safe) and self.entry_time_s is not None
                else None
            ),
            "reentry_opportunity_time_s": (
                float(qualifying[0]["start_time_s"] + 4 * 0.02)
                if qualifying
                else None
            ),
            "maximum_safe_persistence_s": (
                max(float(item["duration_s"]) for item in intervals)
                if intervals
                else 0.0
            ),
            "qualifying_intervals": qualifying,
            "all_safe_intervals": intervals,
            "runtime_ms": {
                "mean": float(np.mean(runtime)) if len(runtime) else None,
                "p95": float(np.percentile(runtime, 95.0)) if len(runtime) else None,
                "max": float(np.max(runtime)) if len(runtime) else None,
            },
            "command_force_n_over_available_actions": {
                "minimum": float(np.min(command)) if len(command) else None,
                "maximum": float(np.max(command)) if len(command) else None,
            },
        }

    def result(self, replay_end_s: float, termination: str) -> dict[str, Any]:
        if self.entry_time_s is None:
            raise RuntimeError("source replay never entered BRAKE")
        shadow = {
            str(alpha): self._shadow_summary(alpha, replay_end_s)
            for alpha in (0.0, 0.125, 0.25)
        }
        any_reentry = any(item["safe_track_reappears"] for item in shadow.values())
        gamma = self.task_retention or {"available": False}
        gamma_classifiable = bool(
            gamma.get("feasible_gamma_found")
            and float(gamma.get("gamma_star", 0.0)) >= 0.5
            and gamma.get("physical_5ms", {}).get("safe", False)
        )
        broad_selected = (
            (self.broader_brake or {})
            .get("broader_set", {})
            .get("selected", {})
        )
        broad_family_limited = bool(
            self.broader_brake
            and self.broader_brake["current_family"]["safe_dissipative_count"] == 0
            and self.broader_brake["broader_set"]["safe_dissipative_action_found"]
            and broad_selected.get("outside_current_six_candidate_family", False)
            and broad_selected.get("physical_5ms", {}).get("safe", False)
        )
        if any_reentry:
            classification = "A_RECOVERY_LOGIC_LIMITED"
        elif gamma_classifiable:
            classification = "B_TASK_PRESERVATION_LIMITED"
        elif broad_family_limited:
            classification = "C_BRAKE_FAMILY_LIMITED"
        else:
            classification = "D_LOCALLY_CONTROL_INFEASIBLE"
        return {
            "trajectory": self.trajectory.name,
            "source_alpha": SOURCE_ALPHA,
            "source_snapshot": str(self.source_snapshot.relative_to(REPO_ROOT)),
            "entry_time_s": self.entry_time_s,
            "replay_end_time_s": replay_end_s,
            "post_entry_replay_duration_s": replay_end_s - self.entry_time_s,
            "source_termination": termination,
            "snapshot_match": {
                "verified": self.entry_state_verified,
                "integration_state_max_abs_error": self.entry_state_error,
            },
            "shadow_reentry": shadow,
            "task_retention": gamma,
            "broader_brake": self.broader_brake,
            "classification": classification,
            "terminal_snapshot_written": self.terminal_snapshot_written,
        }


def _run_trajectory(
    *,
    trajectory: Any,
    case: Any,
    output_dir: Path,
) -> dict[str, Any]:
    allocator = default_engineering_cuff_allocator()
    clock = FixedExternalTimeScale(trajectory.reference, SOURCE_ALPHA)
    plants: list[SnapshotCapturePlant] = []
    mpcs: list[HumanSpaceMPC] = []
    source_snapshot = (
        TIME_SCALE_OUTPUT
        / trajectory.name
        / "alpha_0p125"
        / "first_failure_snapshot.npz"
    )
    if not source_snapshot.is_file():
        raise FileNotFoundError(source_snapshot)

    def plant_factory(human: Any) -> SnapshotCapturePlant:
        plant = SnapshotCapturePlant(human)
        plants.append(plant)
        return plant

    def mpc_factory() -> HumanSpaceMPC:
        mpc = HumanSpaceMPC(cuff_allocator=allocator)
        mpcs.append(mpc)
        return mpc

    def mpc_getter() -> HumanSpaceMPC:
        if len(mpcs) != 1:
            raise RuntimeError("expected exactly one source MPC")
        return mpcs[0]

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN,
        )

    supervisor = DecompositionSupervisor(
        trajectory=trajectory,
        source_snapshot=source_snapshot,
        actual_mpc_getter=mpc_getter,
        output_dir=output_dir,
    )
    summary, trace = run_sensor_realism_case(
        case,
        duration_s=_scaled_horizon_s(SOURCE_ALPHA),
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__alpha_0.125__decomposition",
        true_human_override=HIGH_ROM_HUMAN,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_0_125deg",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        plant_factory=plant_factory,
        reference_execution=clock,
        reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
        capture_system_pilot_diagnostics=True,
        track_brake_supervisor=supervisor,
        mpc_factory=mpc_factory,
        cuff_allocator=allocator,
        estimator_factory=estimator_factory,
    )
    if len(plants) != 1:
        raise RuntimeError("expected exactly one source plant")
    replay_end_s = float(np.asarray(trace["time_s"])[-1])
    termination = str(summary["termination_reason"])
    result = supervisor.result(replay_end_s, termination)
    del trace
    return result


def _smallest_change(results: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {item["classification"] for item in results}
    if classes == {"A_RECOVERY_LOGIC_LIMITED"}:
        return {
            "recommendation": "BRAKE_to_TRACK_reentry",
            "reason": "all_paths_show_a_persistent_five_cycle_safe_TRACK_window",
        }
    if "B_TASK_PRESERVATION_LIMITED" in classes:
        return {
            "recommendation": "hierarchical_gamma_task_relaxation",
            "reason": "at_least_one_path_requires_positive_task_scaling_and_not_all_are_reentry_only",
        }
    if "C_BRAKE_FAMILY_LIMITED" in classes:
        return {
            "recommendation": "broader_BRAKE_projection",
            "reason": "terminal_120_120_has_a_safe_dissipative_action_outside_the_six_rate_family",
        }
    return {
        "recommendation": "stop_and_investigate_interaction_or_mechanical_limits",
        "reason": "the_audited_local_track_task_scaled_and_braking_sets_did_not_restore_feasibility",
    }


def _write_table(path: Path, results: list[dict[str, Any]]) -> None:
    fields = [
        "trajectory",
        "entry_time_s",
        "reentry_alpha_0",
        "reentry_alpha_0p125",
        "reentry_alpha_0p25",
        "earliest_reentry_time_s",
        "gamma_star",
        "task_reduction_percent",
        "broader_brake_safe_action",
        "classification",
    ]
    rows = []
    for item in results:
        shadow = item["shadow_reentry"]
        reentry_times = [
            value["reentry_opportunity_time_s"]
            for value in shadow.values()
            if value["reentry_opportunity_time_s"] is not None
        ]
        gamma = item["task_retention"]
        broad = item.get("broader_brake") or {}
        rows.append(
            {
                "trajectory": item["trajectory"],
                "entry_time_s": item["entry_time_s"],
                "reentry_alpha_0": shadow["0.0"]["safe_track_reappears"],
                "reentry_alpha_0p125": shadow["0.125"]["safe_track_reappears"],
                "reentry_alpha_0p25": shadow["0.25"]["safe_track_reappears"],
                "earliest_reentry_time_s": min(reentry_times) if reentry_times else "",
                "gamma_star": gamma.get("gamma_star", ""),
                "task_reduction_percent": gamma.get("task_reduction_percent", ""),
                "broader_brake_safe_action": broad.get("broader_set", {}).get(
                    "safe_dissipative_action_found", ""
                ),
                "classification": item["classification"],
            }
        )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_path = args.spec.resolve()
    spec_hash = _sha256(spec_path)
    if spec_hash != DEFAULT_SPEC_SHA256:
        raise RuntimeError(
            f"diagnostic spec hash drifted: {spec_hash} != {DEFAULT_SPEC_SHA256}"
        )
    spec = json.loads(spec_path.read_text())
    output_dir = args.output_dir.resolve()
    if args.validate_only:
        print(
            json.dumps(
                {
                    "spec": str(spec_path),
                    "sha256": spec_hash,
                    "trajectory_count": len(spec["trajectories"]),
                    "no_diagnostics_started": True,
                },
                sort_keys=True,
            )
        )
        return 0
    result_path = output_dir / "feasibility_decomposition.json"
    if result_path.exists():
        raise FileExistsError(f"refusing to overwrite {result_path}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not commit.startswith(str(spec["checkpoint_commit"])):
        raise RuntimeError("diagnostic is not running from the checkpoint commit")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix, measurement_seed=44104)
    if case.seed != 44104:
        raise RuntimeError("measurement seed drifted")
    trajectories = {item.name: item for item in TRAJECTORIES}
    results = []
    wall_start = perf_counter()
    for name in spec["trajectories"]:
        result = _run_trajectory(
            trajectory=trajectories[name],
            case=case,
            output_dir=output_dir,
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "trajectory": name,
                    "classification": result["classification"],
                    "event": "trajectory_diagnostic_complete",
                },
                sort_keys=True,
            ),
            flush=True,
        )
    payload = {
        "schema_version": "high_rom_feasibility_decomposition_result_v1",
        "evidence_category": "engineering_failure_state_audit_not_formal_or_authoritative",
        "checkpoint_commit": commit,
        "diagnostic_spec": str(spec_path.relative_to(REPO_ROOT)),
        "diagnostic_spec_sha256": spec_hash,
        "controller_or_parameter_modified": False,
        "full_trajectory_campaign_run": False,
        "deterministic_prefix_hydration_run": True,
        "executed_post_boundary_controller": "unchanged_existing_BRAKE",
        "execution_command": (
            "env PYTHONPATH=stages/stage3_full3d/src:"
            "stages/stage4_adaptive_control/src conda run -n mpc_learn python "
            "stages/stage4_adaptive_control/scripts/"
            "audit_stage4_high_rom_feasibility_decomposition.py"
        ),
        "results": results,
        "local_infeasibility_scope": (
            "any_D_result_is_only_local_to_the_audited_state_and_bounded_action_set"
        ),
        "smallest_justified_next_implementation": _smallest_change(results),
        "runtime_wall_s": perf_counter() - wall_start,
    }
    write_strict_json(result_path, payload)
    _write_table(output_dir / "summary_table.csv", results)
    print(json.dumps({"result": str(result_path)}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
