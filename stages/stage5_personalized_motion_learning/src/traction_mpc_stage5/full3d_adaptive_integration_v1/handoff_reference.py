"""Causal fitted-coordinate handoff and actual Cartesian tool-path checks."""
from __future__ import annotations

from typing import Any
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SLEEVE_OUTER_RADIUS_M
from ..geometry import STAGE5_GEOMETRY


def stationary_emitted_boundary(trace: list[dict[str, Any]], emitted: list[dict[str, Any]],
                                settling_duration_s: float) -> dict[str, Any]:
    """Verify old emitted references, not measured settling velocities."""
    rows = [r for r in trace if r["stage"] == "COMMISSIONING"]
    end = float(rows[-1]["time_s"])
    suffix = [r for r in rows if r["time_s"] > end-settling_duration_s+1e-10]
    if not suffix or len(emitted) < 2:
        raise ValueError("HANDOFF_EMITTED_BOUNDARY_HISTORY_UNAVAILABLE")
    q = np.asarray([r["q_ref_rad"] for r in suffix])
    dq = np.asarray([r["dq_ref_rad_s"] for r in suffix])
    ddq = np.asarray([r["ddq_ref_rad_s2"] for r in suffix])
    last = emitted[-1]
    position_delta = max(float(np.linalg.norm(r["pose"].translation-last["pose"].translation)) for r in emitted)
    rotation_delta = max(float(np.linalg.norm(Rotation.from_matrix(
        r["pose"].rotation.T @ last["pose"].rotation).as_rotvec())) for r in emitted)
    twist_max = max(float(np.max(np.abs(r["twist"]))) for r in emitted)
    record = {"checked_commissioning_duration_s": settling_duration_s,
              "checked_trace_samples": len(suffix), "emitted_pose_samples": len(emitted),
              "q_reference_variation_rad": float(np.max(np.abs(q-q[-1]))),
              "dq_reference_max_rad_s": float(np.max(np.abs(dq))),
              "ddq_reference_max_rad_s2": float(np.max(np.abs(ddq))),
              "emitted_position_variation_m": position_delta,
              "emitted_rotation_variation_rad": rotation_delta,
              "emitted_twist_max": twist_max,
              "all_recent_commands_track": all(r["mode"] == "TRACK" for r in emitted)}
    record["stationary_verified"] = bool(record["all_recent_commands_track"] and max(
        record["q_reference_variation_rad"], record["dq_reference_max_rad_s"],
        record["ddq_reference_max_rad_s2"], position_delta, rotation_delta, twist_max) <= 1e-10)
    record["acceleration_boundary_basis"] = "constant emitted pose and analytic zero q/dq/ddq over fixed-model terminal hold"
    return record


def cartesian_tool_margins(positions: np.ndarray, rotations: np.ndarray) -> dict[str, np.ndarray]:
    """Registered robot bar/adapter cylinders at actual overridden cuff poses.

    Human sleeve is a different body and is checked on the fitted q path by
    the existing envelope. No collision mask or collider dimension is changed.
    """
    p = np.asarray(positions, dtype=float)
    r = np.asarray(rotations, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or r.shape != (len(p), 3, 3) or not np.all(np.isfinite(p)) or not np.all(np.isfinite(r)):
        raise ValueError("Cartesian tool poses must be finite Nx3/Nx3x3")
    geom = STAGE5_GEOMETRY
    axis = r @ geom.cuff_bar_axis_in_cuff
    bar = p[:, 2] - 0.5*geom.cuff_bar_length_m*np.abs(axis[:, 2]) \
        - geom.cuff_bar_radius_m*np.sqrt(np.maximum(0., 1.-axis[:, 2]**2)) - BED_HEIGHT_M
    relative = geom.end_effector_from_cuff
    offset_c = relative.rotation.T @ relative.translation
    offset_w = r @ offset_c
    length = float(np.linalg.norm(relative.translation))
    connector = max(0., length-SLEEVE_OUTER_RADIUS_M)
    flange_z = p[:, 2]-offset_w[:, 2]
    end_z = flange_z + connector/length * offset_w[:, 2] if length else flange_z
    adapter_axis_z = offset_w[:, 2]/length if length else np.zeros(len(p))
    adapter = np.minimum(flange_z, end_z) - .018*np.sqrt(np.maximum(0., 1.-adapter_axis_z**2)) - BED_HEIGHT_M
    return {"robot_cuff_bar_m": bar, "robot_cuff_adapter_m": adapter}


def screen_cartesian_bridge(bridge: Any, schedule: Any, envelope: Any) -> dict[str, Any]:
    """Continuous conservative tool and Human sleeve/q-path screening."""
    count = envelope.sample_count
    s = np.linspace(0., 1., count)
    u = 10*s**3-15*s**4+6*s**5
    old, new = bridge.old_world_from_cuff, bridge.new_world_from_cuff
    rotvec = Rotation.from_matrix(old.rotation.T @ new.rotation).as_rotvec()
    rotations = old.rotation @ Rotation.from_rotvec(u[:, None]*rotvec).as_matrix()
    positions = old.translation + u[:, None]*(new.translation-old.translation)
    sampled = {k: float(np.min(v)) for k, v in cartesian_tool_margins(positions, rotations).items()}
    # Rigid support-point displacement is Lipschitz in translation and angle;
    # quintic progress derivative <=1.875. No unsafe point is excused by spacing.
    geom = STAGE5_GEOMETRY
    radii = {"robot_cuff_bar_m": geom.cuff_bar_length_m/2+geom.cuff_bar_radius_m,
             "robot_cuff_adapter_m": np.linalg.norm(geom.end_effector_from_cuff.translation)+.018}
    bounds = {k: 1.875/(2*(count-1))*(abs(new.translation[2]-old.translation[2])
                                        + radius*np.linalg.norm(rotvec)) for k, radius in radii.items()}
    lower = {k: value-bounds[k] for k, value in sampled.items()}
    human = envelope.check_quintic(schedule.coefficients, schedule.duration_s)
    return {"feasible": bool(human["feasible"] and min(lower.values()) >= 0.),
            "robot_tool_minimum_sampled_m": sampled,
            "robot_tool_continuous_lower_m": lower,
            "robot_tool_lipschitz_bound_m": bounds, "sample_count": count,
            "human_sleeve_and_limb_path": human,
            "scope": "actual Cartesian robot tool bridge plus fitted Human sleeve/limb reference; not future physical tracking proof"}
