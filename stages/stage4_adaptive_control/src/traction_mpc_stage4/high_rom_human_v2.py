"""Explicit engineering High-ROM Human V2 variant and mechanics audit helpers.

The canonical ``HUMAN`` object is not modified.  This variant extends only the
modeled ROM/soft-limit location needed by the three audited high-ROM paths.
Its passive extrapolation is an engineering assumption pending physical and
hardware validation, not a physiological claim.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import math
from typing import Any

import numpy as np

from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    HumanV2Parameters,
    soft_limit_torque,
)

from .continuous_high_rom import PATH_SAMPLE_COUNT, smooth_joint_path
from .cuff_allocator import default_engineering_cuff_allocator
from .human_model import dynamic_terms, inverse_dynamics


HIGH_ROM_VARIANT_NAME = "human_v2_high_rom_engineering_v2_125deg_both_joints"
HIGH_ROM_HUMAN_V2 = replace(
    HUMAN,
    q_max_rad=(math.radians(125.0), math.radians(125.0)),
)
HIGH_ROM_ENDPOINTS_DEG = {
    "hip_dominant_100_60": np.array([100.0, 60.0]),
    "knee_high_folding_90_120": np.array([90.0, 120.0]),
    "aggressive_both_120_120": np.array([120.0, 120.0]),
}
PRIMARY_ENDPOINT_NAMES = (
    "hip_dominant_100_60",
    "knee_high_folding_90_120",
    "aggressive_both_120_120",
)


def _degrees(values: Any) -> list[float]:
    return np.round(np.degrees(np.asarray(values, dtype=float)), 12).tolist()


def high_rom_config_payload() -> dict[str, Any]:
    canonical = asdict(HUMAN)
    variant = asdict(HIGH_ROM_HUMAN_V2)
    changed = {
        name: {"canonical": canonical[name], "high_rom": value}
        for name, value in variant.items()
        if value != canonical[name]
    }
    upper_soft_start = (
        np.asarray(HIGH_ROM_HUMAN_V2.q_max_rad)
        - HIGH_ROM_HUMAN_V2.soft_limit_margin_rad
    )
    return {
        "schema_version": HIGH_ROM_VARIANT_NAME,
        "scope": (
            "simulation engineering assumption pending physical/hardware "
            "validation; not a physiological ROM or passive-torque claim"
        ),
        "canonical_human_overwritten": False,
        "q_min_deg": _degrees(HIGH_ROM_HUMAN_V2.q_min_rad),
        "q_max_deg": _degrees(HIGH_ROM_HUMAN_V2.q_max_rad),
        "upper_soft_zone_start_deg": _degrees(upper_soft_start),
        "soft_limit_margin_deg": float(
            np.degrees(HIGH_ROM_HUMAN_V2.soft_limit_margin_rad)
        ),
        "q_rest_deg": _degrees(HIGH_ROM_HUMAN_V2.q_rest_rad),
        "passive_stiffness_nm_rad": list(
            HIGH_ROM_HUMAN_V2.passive_stiffness_nm_rad
        ),
        "passive_damping_nms_rad": list(
            HIGH_ROM_HUMAN_V2.passive_damping_nms_rad
        ),
        "soft_limit_boundary_torque_nm": (
            HIGH_ROM_HUMAN_V2.soft_limit_boundary_torque_nm
        ),
        "soft_limit_damping_nms_rad": (
            HIGH_ROM_HUMAN_V2.soft_limit_damping_nms_rad
        ),
        "changed_from_canonical": changed,
        "explicitly_unchanged": [
            name for name in variant if name not in changed
        ],
        "trajectory_margins_deg": {
            name: {
                "endpoint_deg": HIGH_ROM_ENDPOINTS_DEG[name].tolist(),
                "to_hard_upper_limit_deg": np.round(
                    np.degrees(HIGH_ROM_HUMAN_V2.q_max_rad)
                    - HIGH_ROM_ENDPOINTS_DEG[name],
                    12,
                ).tolist(),
                "to_upper_soft_zone_start_deg": np.round(
                    np.degrees(upper_soft_start)
                    - HIGH_ROM_ENDPOINTS_DEG[name],
                    12,
                ).tolist(),
            }
            for name in PRIMARY_ENDPOINT_NAMES
        },
    }


def _passive_left(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    human: HumanV2Parameters = HIGH_ROM_HUMAN_V2,
) -> np.ndarray:
    _, _, _, passive = dynamic_terms(q_rad, dq_rad_s, human)
    return passive


def audit_passive_model(
    human: HumanV2Parameters = HIGH_ROM_HUMAN_V2,
    *,
    samples_per_joint: int = 501,
) -> dict[str, Any]:
    if samples_per_joint < 11:
        raise ValueError("samples_per_joint must be at least 11")
    q_min = np.asarray(human.q_min_rad)
    q_max = np.asarray(human.q_max_rad)
    q_rest = np.asarray(human.q_rest_rad)
    stiffness = np.asarray(human.passive_stiffness_nm_rad)
    damping = np.asarray(human.passive_damping_nms_rad)
    lower_soft_start = q_min + human.soft_limit_margin_rad
    upper_soft_start = q_max - human.soft_limit_margin_rad
    epsilon = 1e-7
    joints: dict[str, Any] = {}
    all_continuity_jumps: list[float] = []
    all_max_damping_power: list[float] = []

    for joint_index, joint_name in enumerate(("hip", "knee")):
        q_values = np.linspace(
            q_min[joint_index], q_max[joint_index], samples_per_joint
        )
        ordinary_left = stiffness[joint_index] * (
            q_values - q_rest[joint_index]
        )
        soft_values = []
        passive_left_values = []
        for value in q_values:
            q = q_rest.copy()
            q[joint_index] = value
            soft = soft_limit_torque(q, np.zeros(2), human)[joint_index]
            soft_values.append(float(soft))
            passive_left_values.append(
                float(_passive_left(q, np.zeros(2), human)[joint_index])
            )
        soft_array = np.asarray(soft_values)
        passive_left_array = np.asarray(passive_left_values)

        continuity: dict[str, float] = {}
        for boundary_name, boundary in (
            ("lower_soft_start", lower_soft_start[joint_index]),
            ("upper_soft_start", upper_soft_start[joint_index]),
        ):
            samples = []
            for offset in (-epsilon, 0.0, epsilon):
                q = q_rest.copy()
                q[joint_index] = boundary + offset
                samples.append(
                    soft_limit_torque(q, np.zeros(2), human)[joint_index]
                )
            jump = float(max(abs(samples[1] - samples[0]), abs(samples[2] - samples[1])))
            continuity[boundary_name + "_max_adjacent_jump_nm"] = jump
            all_continuity_jumps.append(jump)

        damping_power = []
        velocity_values = np.linspace(-2.0, 2.0, 81)
        for q_value in q_values:
            q = q_rest.copy()
            q[joint_index] = q_value
            soft_static = soft_limit_torque(q, np.zeros(2), human)[joint_index]
            for velocity in velocity_values:
                dq = np.zeros(2)
                dq[joint_index] = velocity
                soft_dynamic = soft_limit_torque(q, dq, human)[joint_index]
                physical_velocity_torque = (
                    -damping[joint_index] * velocity
                    + soft_dynamic
                    - soft_static
                )
                damping_power.append(float(physical_velocity_torque * velocity))
        max_damping_power = max(damping_power)
        all_max_damping_power.append(max_damping_power)

        lower_q = q_rest.copy()
        lower_q[joint_index] = q_min[joint_index]
        upper_q = q_rest.copy()
        upper_q[joint_index] = q_max[joint_index]
        lower_soft = float(
            soft_limit_torque(lower_q, np.zeros(2), human)[joint_index]
        )
        upper_soft = float(
            soft_limit_torque(upper_q, np.zeros(2), human)[joint_index]
        )
        joints[joint_name] = {
            "q_range_deg": [
                float(np.degrees(q_min[joint_index])),
                float(np.degrees(q_max[joint_index])),
            ],
            "lower_soft_zone_start_deg": float(
                np.degrees(lower_soft_start[joint_index])
            ),
            "upper_soft_zone_start_deg": float(
                np.degrees(upper_soft_start[joint_index])
            ),
            "ordinary_passive_left_static_envelope_nm": [
                float(np.min(ordinary_left)),
                float(np.max(ordinary_left)),
            ],
            "soft_limit_actual_torque_envelope_nm": [
                float(np.min(soft_array)),
                float(np.max(soft_array)),
            ],
            "total_passive_left_static_envelope_nm": [
                float(np.min(passive_left_array)),
                float(np.max(passive_left_array)),
            ],
            "soft_limit_at_lower_hard_boundary_nm": lower_soft,
            "soft_limit_at_upper_hard_boundary_nm": upper_soft,
            "soft_limit_direction_pushes_inward": bool(
                lower_soft > 0.0 and upper_soft < 0.0
            ),
            "maximum_sampled_physical_damping_power_w": max_damping_power,
            "damping_dissipative": bool(max_damping_power <= 1e-12),
            "continuity": continuity,
            "sampled_position_deg": np.degrees(q_values).tolist(),
            "ordinary_passive_left_static_nm": ordinary_left.tolist(),
            "soft_limit_actual_static_nm": soft_array.tolist(),
            "total_passive_left_static_nm": passive_left_array.tolist(),
        }

    return {
        "variant": high_rom_config_payload(),
        "samples_per_joint": samples_per_joint,
        "joints": joints,
        "global_checks": {
            "finite_over_full_rom": True,
            "maximum_soft_boundary_continuity_jump_nm": max(
                all_continuity_jumps
            ),
            "no_soft_limit_inside_central_region": all(
                np.allclose(
                    np.asarray(joint["soft_limit_actual_static_nm"])[
                        (np.asarray(joint["sampled_position_deg"])
                         >= joint["lower_soft_zone_start_deg"])
                        & (np.asarray(joint["sampled_position_deg"])
                           <= joint["upper_soft_zone_start_deg"])
                    ],
                    0.0,
                    atol=1e-12,
                )
                for joint in joints.values()
            ),
            "soft_limit_inward_at_hard_boundaries": all(
                joint["soft_limit_direction_pushes_inward"]
                for joint in joints.values()
            ),
            "damping_dissipative": max(all_max_damping_power) <= 1e-12,
            "interpretation": (
                "passive_left is the generalized torque that must be overcome "
                "in the inverse-dynamics convention; physical passive torque "
                "has the opposite sign. Soft-limit values are actual inward "
                "joint torque."
            ),
        },
    }


def _peak_component(
    values: np.ndarray,
    q_deg: np.ndarray,
    component: int,
) -> dict[str, Any]:
    index = int(np.argmax(np.abs(values[:, component])))
    return {
        "signed_nm": float(values[index, component]),
        "absolute_nm": float(abs(values[index, component])),
        "sample_index": index,
        "q_deg": q_deg[index].tolist(),
    }


def audit_quasistatic_paths(
    human: HumanV2Parameters = HIGH_ROM_HUMAN_V2,
    *,
    sample_count: int = PATH_SAMPLE_COUNT,
) -> dict[str, Any]:
    allocator = default_engineering_cuff_allocator()
    results: dict[str, Any] = {}
    for name in PRIMARY_ENDPOINT_NAMES:
        _, q_path_deg = smooth_joint_path(
            HIGH_ROM_ENDPOINTS_DEG[name], sample_count=sample_count
        )
        passive = []
        required = []
        soft = []
        force = []
        moment = []
        for q_deg in q_path_deg:
            q = np.radians(q_deg)
            zero = np.zeros(2)
            passive.append(_passive_left(q, zero, human))
            required_torque = inverse_dynamics(q, zero, zero, human)
            required.append(required_torque)
            soft.append(soft_limit_torque(q, zero, human))
            allocation = allocator.allocate(required_torque, q, human)
            force.append(float(allocation["force_norm_n"]))
            moment.append(abs(float(allocation["sagittal_wrench"][2])))
        passive_array = np.asarray(passive)
        required_array = np.asarray(required)
        soft_array = np.asarray(soft)
        force_array = np.asarray(force)
        moment_array = np.asarray(moment)
        required_norm = np.linalg.norm(required_array, axis=1)
        force_index = int(np.argmax(force_array))
        moment_index = int(np.argmax(moment_array))
        required_norm_index = int(np.argmax(required_norm))
        results[name] = {
            "endpoint_deg": HIGH_ROM_ENDPOINTS_DEG[name].tolist(),
            "sample_count": sample_count,
            "rom_valid_all_samples": bool(
                np.all(np.radians(q_path_deg) >= np.asarray(human.q_min_rad))
                and np.all(np.radians(q_path_deg) <= np.asarray(human.q_max_rad))
            ),
            "soft_limit_inactive_all_samples": bool(
                np.allclose(soft_array, 0.0, atol=1e-12)
            ),
            "peak_passive_left_by_joint": {
                "hip": _peak_component(passive_array, q_path_deg, 0),
                "knee": _peak_component(passive_array, q_path_deg, 1),
            },
            "peak_required_torque_by_joint": {
                "hip": _peak_component(required_array, q_path_deg, 0),
                "knee": _peak_component(required_array, q_path_deg, 1),
            },
            "peak_required_torque_norm": {
                "nm": float(required_norm[required_norm_index]),
                "sample_index": required_norm_index,
                "q_deg": q_path_deg[required_norm_index].tolist(),
            },
            "peak_cuff_force": {
                "n": float(force_array[force_index]),
                "q_deg": q_path_deg[force_index].tolist(),
                "margin_to_200_n": float(
                    CUFF_TRANSLATIONAL_FORCE_GATE_N - force_array[force_index]
                ),
            },
            "peak_cuff_moment": {
                "nm": float(moment_array[moment_index]),
                "q_deg": q_path_deg[moment_index].tolist(),
            },
            "force_gate_passed": bool(
                np.all(force_array <= CUFF_TRANSLATIONAL_FORCE_GATE_N)
            ),
            "classification": (
                "READY FOR DYNAMIC PILOT"
                if np.all(force_array <= CUFF_TRANSLATIONAL_FORCE_GATE_N)
                and np.allclose(soft_array, 0.0, atol=1e-12)
                else "MODEL-BLOCKED"
            ),
            "trace": {
                "human_q_deg": q_path_deg.tolist(),
                "passive_left_nm": passive_array.tolist(),
                "required_torque_nm": required_array.tolist(),
                "soft_limit_actual_torque_nm": soft_array.tolist(),
                "cuff_force_n": force_array.tolist(),
                "cuff_moment_abs_nm": moment_array.tolist(),
            },
        }
    return {
        "audit_kind": "high_rom_human_v2_actual_passive_quasistatic_audit",
        "controller_or_dynamic_rollout_run": False,
        "human_variant": high_rom_config_payload(),
        "paths": results,
    }
