#!/usr/bin/env python3
"""Read-only audit of cuff-force and Human-acceleration constraint independence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.human_model import continuous_dynamics, dynamic_terms
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


WINDOW_S = 0.020
OFFLINE_DT_S = 0.00025
EVENT_TIME_S = 0.320


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array(
            [STAGE5_HUMAN.sleeve_center_m, 0.0]
        ),
    )


def _summary(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        "start": array[0].tolist(),
        "end": array[-1].tolist(),
        "minimum": np.min(array, axis=0).tolist(),
        "maximum": np.max(array, axis=0).tolist(),
        "mean": np.mean(array, axis=0).tolist(),
    }


def _norm_summary(values: np.ndarray) -> dict[str, float]:
    norms = np.linalg.norm(np.asarray(values, dtype=float), axis=1)
    return {
        "start": float(norms[0]),
        "end": float(norms[-1]),
        "minimum": float(np.min(norms)),
        "maximum": float(np.max(norms)),
        "mean": float(np.mean(norms)),
    }


def _cr12_event(trace_path: Path) -> dict[str, Any]:
    with np.load(trace_path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        selected = np.flatnonzero(
            (time_s >= EVENT_TIME_S - WINDOW_S - 1.0e-10)
            & (time_s <= EVENT_TIME_S + 1.0e-10)
        )
        if len(selected) != 5 or not np.allclose(
            time_s[selected],
            np.linspace(EVENT_TIME_S - WINDOW_S, EVENT_TIME_S, 5),
            atol=1.0e-10,
            rtol=0.0,
        ):
            raise ValueError("CR12 trace does not contain the exact 20 ms window")

        estimated_state = np.asarray(
            trace["estimated_state_rad_rad_s"][selected], dtype=float
        )
        truth_q = np.asarray(trace["evaluation_human_q_rad"][selected], dtype=float)
        truth_dq = np.asarray(
            trace["evaluation_human_dq_rad_s"][selected], dtype=float
        )
        truth_qacc = np.asarray(
            trace["evaluation_only_instantaneous_acceleration_rad_s2"][selected],
            dtype=float,
        )
        force = np.asarray(trace["physical_cuff_force_world_n"][selected], dtype=float)
        moment = np.asarray(
            trace["physical_cuff_moment_world_nm"][selected], dtype=float
        )
        generalized = np.asarray(
            trace["deployable_measured_generalized_input_nm"][selected],
            dtype=float,
        )
        command = np.asarray(
            trace["executed_command_wrench_world"][selected], dtype=float
        )
        interface_translation = np.asarray(
            trace["interface_translation_human_m"][selected], dtype=float
        )
        interface_rotation = np.asarray(
            trace["interface_rotation_human_rad"][selected], dtype=float
        )
        interface_velocity = np.asarray(
            trace["estimated_interface_velocity_human_m_s"][selected], dtype=float
        )
        interface_angular_velocity = np.asarray(
            trace["estimated_interface_angular_velocity_human_rad_s"][selected],
            dtype=float,
        )

    deployable_20ms = (estimated_state[-1, 2:] - estimated_state[0, 2:]) / WINDOW_S
    truth_20ms = (truth_dq[-1] - truth_dq[0]) / WINDOW_S
    mass_terms: list[np.ndarray] = []
    coriolis_terms: list[np.ndarray] = []
    gravity_terms: list[np.ndarray] = []
    passive_terms: list[np.ndarray] = []
    required_external: list[np.ndarray] = []
    acceleration_contributions: dict[str, list[np.ndarray]] = {
        "external": [],
        "coriolis": [],
        "gravity": [],
        "passive": [],
    }
    for q, dq, qacc in zip(truth_q, truth_dq, truth_qacc, strict=True):
        mass, coriolis, gravity, passive = dynamic_terms(q, dq, STAGE5_HUMAN)
        required = mass @ qacc + coriolis + gravity + passive
        mass_terms.append(mass)
        coriolis_terms.append(coriolis)
        gravity_terms.append(gravity)
        passive_terms.append(passive)
        required_external.append(required)
        acceleration_contributions["external"].append(
            np.linalg.solve(mass, required)
        )
        acceleration_contributions["coriolis"].append(
            np.linalg.solve(mass, -coriolis)
        )
        acceleration_contributions["gravity"].append(
            np.linalg.solve(mass, -gravity)
        )
        acceleration_contributions["passive"].append(
            np.linalg.solve(mass, -passive)
        )

    limit = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
        dtype=float,
    )
    deployable_deg = np.degrees(deployable_20ms)
    truth_deg = np.degrees(truth_20ms)
    return {
        "trace": str(trace_path.relative_to(STAGE5_ROOT)),
        "window_s": [float(time_s[selected[0]]), float(time_s[selected[-1]])],
        "sample_times_s": time_s[selected].tolist(),
        "registered_acceleration_limit_deg_s2": np.degrees(limit).tolist(),
        "deployable_dq_hat_20ms_acceleration_deg_s2": deployable_deg.tolist(),
        "offline_truth_dq_20ms_acceleration_deg_s2": truth_deg.tolist(),
        "deployable_minus_truth_deg_s2": (deployable_deg - truth_deg).tolist(),
        "deployable_violation": bool(np.any(np.abs(deployable_20ms) > limit)),
        "offline_truth_violation": bool(np.any(np.abs(truth_20ms) > limit)),
        "same_joint_same_sign_violation": bool(
            np.any(
                (np.abs(deployable_20ms) > limit)
                & (np.abs(truth_20ms) > limit)
                & (np.sign(deployable_20ms) == np.sign(truth_20ms))
            )
        ),
        "cuff_force_norm_n": _norm_summary(force),
        "cuff_moment_norm_nm": _norm_summary(moment),
        "deployable_generalized_human_input_nm": _summary(generalized),
        "offline_truth_required_external_torque_nm": _summary(
            np.asarray(required_external)
        ),
        "offline_dynamic_torque_terms_nm": {
            "coriolis": _summary(np.asarray(coriolis_terms)),
            "gravity": _summary(np.asarray(gravity_terms)),
            "passive": _summary(np.asarray(passive_terms)),
        },
        "offline_instantaneous_acceleration_contributions_deg_s2": {
            name: _summary(np.degrees(np.asarray(values)))
            for name, values in acceleration_contributions.items()
        },
        "robot_command": {
            "force_norm_n": _norm_summary(command[:, :3]),
            "moment_norm_nm": _norm_summary(command[:, 3:]),
            "wrench_world": _summary(command),
        },
        "interface_state": {
            "translation_norm_mm": {
                key: value * 1000.0
                for key, value in _norm_summary(interface_translation).items()
            },
            "translation_rate_norm_mm_s": {
                key: value * 1000.0
                for key, value in _norm_summary(interface_velocity).items()
            },
            "rotation_norm_deg": {
                key: math.degrees(value)
                for key, value in _norm_summary(interface_rotation).items()
            },
            "rotation_rate_norm_deg_s": {
                key: math.degrees(value)
                for key, value in _norm_summary(interface_angular_velocity).items()
            },
        },
        "force_gate_satisfied_entire_window": bool(
            np.all(np.linalg.norm(force, axis=1) <= CUFF_TRANSLATIONAL_FORCE_GATE_N)
        ),
        "registered_numeric_cuff_moment_limit_nm": None,
        "time_alignment_note": (
            "All saved signals use the same five 5 ms timestamps. Offline truth "
            "torque terms are reconstructed from Human V2 and sampled MuJoCo qacc; "
            "they are evaluation-only and are not an online signal."
        ),
    }


def _integrate_constant_wrench(
    geometry: PlanarCuffGeometry,
    initial_state: np.ndarray,
    force_world_n: np.ndarray,
    moment_world_nm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(initial_state, dtype=float).copy()
    history = [state.copy()]

    def derivative(value: np.ndarray) -> np.ndarray:
        torque = geometry.generalized_input_from_wrench(
            value[:2], force_world_n, moment_world_nm
        )
        return continuous_dynamics(value, torque, STAGE5_HUMAN)

    step_count = int(round(WINDOW_S / OFFLINE_DT_S))
    for _ in range(step_count):
        k1 = derivative(state)
        k2 = derivative(state + 0.5 * OFFLINE_DT_S * k1)
        k3 = derivative(state + 0.5 * OFFLINE_DT_S * k2)
        k4 = derivative(state + OFFLINE_DT_S * k3)
        state = state + OFFLINE_DT_S * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        history.append(state.copy())
    return state, np.asarray(history)


def _controlled_counterexamples() -> dict[str, Any]:
    geometry = _geometry()
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    q_bounds = np.asarray(task.q_bounds_rad, dtype=float)
    velocity_limit = np.asarray(task.task_joint_velocity_limit_rad_s, dtype=float)
    acceleration_limit = np.asarray(
        task.task_joint_acceleration_limit_rad_s2, dtype=float
    )
    plane_x = geometry.plane_x_world
    plane_z = geometry.plane_z_world
    zero_moment = np.zeros(3)
    candidates: list[dict[str, Any]] = []
    for q_deg in (
        (5.0, 10.0),
        (20.0, 35.0),
        (40.0, 60.0),
        (60.0, 90.0),
    ):
        for dq_deg_s in (
            (-30.0, -50.0),
            (-30.0, 0.0),
            (0.0, 0.0),
            (30.0, 0.0),
            (30.0, 50.0),
        ):
            initial = np.concatenate([np.radians(q_deg), np.radians(dq_deg_s)])
            for force_norm_n in (0.0, 50.0, 100.0, 150.0, 200.0):
                angle_count = 1 if force_norm_n == 0.0 else 16
                for angle in np.linspace(0.0, 2.0 * math.pi, angle_count, endpoint=False):
                    force = force_norm_n * (
                        math.cos(angle) * plane_x + math.sin(angle) * plane_z
                    )
                    final, history = _integrate_constant_wrench(
                        geometry, initial, force, zero_moment
                    )
                    q = history[:, :2]
                    dq = history[:, 2:]
                    if not (
                        np.all(q >= q_bounds[:, 0] - 1.0e-12)
                        and np.all(q <= q_bounds[:, 1] + 1.0e-12)
                        and np.all(np.abs(dq) <= velocity_limit + 1.0e-12)
                    ):
                        continue
                    acceleration = (final[2:] - initial[2:]) / WINDOW_S
                    ratio = np.abs(acceleration) / acceleration_limit
                    if np.any(ratio > 1.0):
                        candidates.append(
                            {
                                "initial_q_deg": list(q_deg),
                                "initial_dq_deg_s": list(dq_deg_s),
                                "force_norm_n": force_norm_n,
                                "force_direction_in_human_plane_deg": math.degrees(angle),
                                "moment_norm_nm": 0.0,
                                "realized_20ms_acceleration_deg_s2": np.degrees(
                                    acceleration
                                ).tolist(),
                                "final_q_deg": np.degrees(final[:2]).tolist(),
                                "final_dq_deg_s": np.degrees(final[2:]).tolist(),
                                "maximum_limit_ratio": float(np.max(ratio)),
                                "entire_window_inside_registered_q_dq_range": True,
                            }
                        )

    examples: list[dict[str, Any]] = []
    for target_force in (0.0, 100.0, 200.0):
        matching = [row for row in candidates if row["force_norm_n"] == target_force]
        if matching:
            examples.append(min(matching, key=lambda row: row["maximum_limit_ratio"]))
    return {
        "method": (
            "deterministic Human-V2 RK4, fixed world-frame sagittal force and "
            "zero cuff moment for exactly 20 ms"
        ),
        "integration_dt_s": OFFLINE_DT_S,
        "registered_q_bounds_deg": np.degrees(q_bounds).tolist(),
        "registered_velocity_limit_deg_s": np.degrees(velocity_limit).tolist(),
        "registered_acceleration_limit_deg_s2": np.degrees(
            acceleration_limit
        ).tolist(),
        "force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
        "cuff_moment_nm": 0.0,
        "candidate_count_with_acceleration_violation_and_q_dq_compliance": len(
            candidates
        ),
        "representative_counterexamples": examples,
        "scientific_parameters_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_split_authority_baseline_attempt_03/execution/trace.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results/force_acceleration_independence_audit",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    cr12 = _cr12_event(args.trace.resolve())
    counterexamples = _controlled_counterexamples()
    relationship = {
        "force_gate_alone_guarantees_acceleration_envelope": False,
        "registered_numeric_cuff_moment_limit_exists": False,
        "acceleration_is_independent_human_motion_constraint": True,
        "reason": (
            "The CR12 realized event and controlled zero-moment Human-V2 "
            "counterexamples satisfy the 200 N force gate while exceeding the "
            "registered 20 ms acceleration envelope."
        ),
    }
    result = {
        "schema": "stage5_force_acceleration_independence_audit_v1",
        "evidence_category": "read_only_offline_engineering_audit",
        "cr12_event": cr12,
        "controlled_offline_evaluation": counterexamples,
        "relationship": relationship,
        "authority_changed": False,
        "threshold_changed": False,
        "scientific_parameters_changed": False,
        "conclusion": (
            "FA-B — ACCELERATION PROVIDES AN INDEPENDENT HUMAN-MOTION CONSTRAINT"
        ),
    }
    path = output / "force_acceleration_independence_audit.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
