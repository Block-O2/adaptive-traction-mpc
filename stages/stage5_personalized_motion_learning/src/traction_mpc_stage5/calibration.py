"""Auditable Stage-5 high-stiffness interface engineering calibration."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import (
    BED_SOLIMP,
    BED_SOLREF,
    SLEEVE_SOLIMP,
    SLEEVE_SOLREF,
    SUSPENDED_SEATED_LIKE_SCENARIO,
)
from traction_mpc_stage3.spring_damper_interface import InterfaceParameters

from .config import STAGE5_CONFIG, STAGE5_ROOT
from .human import STAGE5_HUMAN
from .mechanics import STAGE4_P1_INTERFACE, STAGE5_RIGID_INTERFACE
from .plant import Stage5SpringDamperPlant
from .validation import _reachability_and_clearance


CANDIDATE_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_rigid_interface_candidates.json"
)
AXIS_NAMES = ("axial_x", "tangential_y", "radial_z")


def load_candidate_config(path: Path = CANDIDATE_CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_rigid_interface_candidates_v1":
        raise ValueError("unexpected rigid-interface candidate schema")
    return payload


def _parameters(translation: dict[str, Any], rotation: dict[str, Any]) -> InterfaceParameters:
    stiffness = float(translation["stiffness_n_m"])
    return InterfaceParameters(
        translation_stiffness_n_m=(stiffness, stiffness, stiffness),
        translation_damping_ns_m=tuple(translation["damping_ns_m"]),
        rotation_stiffness_nm_rad=float(rotation["stiffness_nm_rad"]),
        rotation_damping_nms_rad=float(rotation["damping_nms_rad"]),
    )


def _full_mass_matrix(plant: Stage5SpringDamperPlant) -> np.ndarray:
    matrix = np.zeros((plant.model.nv, plant.model.nv))
    mujoco.mj_fullM(plant.model, plant.data, matrix)
    return matrix


def effective_mass_audit() -> dict[str, Any]:
    plant = Stage5SpringDamperPlant(engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO)
    rows = []
    for posture_deg in STAGE5_CONFIG["representative_postures_deg"]:
        plant.reset(np.radians(posture_deg))
        inverse_mass = np.linalg.inv(_full_mass_matrix(plant))
        relative_jacobian = (
            plant._site_pose_jacobian(plant.attachment_site_id)
            - plant._site_pose_jacobian(plant.sleeve_site_id)
        )
        cuff_rotation = plant.data.site_xmat[plant.sleeve_site_id].reshape(3, 3)
        translation_mass = []
        rotation_inertia = []
        for axis_index in range(3):
            axis_world = cuff_rotation[:, axis_index]
            translation_inverse_mass = float(
                axis_world
                @ relative_jacobian[:3]
                @ inverse_mass
                @ relative_jacobian[:3].T
                @ axis_world
            )
            rotation_inverse_inertia = float(
                axis_world
                @ relative_jacobian[3:]
                @ inverse_mass
                @ relative_jacobian[3:].T
                @ axis_world
            )
            translation_mass.append(1.0 / translation_inverse_mass)
            rotation_inertia.append(1.0 / rotation_inverse_inertia)
        rows.append(
            {
                "human_q_deg": list(posture_deg),
                "translation_effective_mass_kg": translation_mass,
                "rotation_effective_inertia_kg_m2": rotation_inertia,
            }
        )
    mass = np.asarray([row["translation_effective_mass_kg"] for row in rows])
    inertia = np.asarray([row["rotation_effective_inertia_kg_m2"] for row in rows])
    return {
        "method": "directional inverse apparent mass from J_rel M^-1 J_rel^T; J_rel=J_robot_site-J_human_site",
        "contact_constraints_excluded_from_formula": True,
        "samples": rows,
        "translation_axis_median_kg": np.median(mass, axis=0).tolist(),
        "translation_all_min_median_max_kg": [
            float(np.min(mass)),
            float(np.median(mass)),
            float(np.max(mass)),
        ],
        "rotation_axis_median_kg_m2": np.median(inertia, axis=0).tolist(),
        "rotation_all_min_median_max_kg_m2": [
            float(np.min(inertia)),
            float(np.median(inertia)),
            float(np.max(inertia)),
        ],
    }


def _analytical_tables(config: dict[str, Any]) -> dict[str, Any]:
    force_levels = (10.0, 25.0, 50.0, 100.0)
    displacement_mm = (0.5, 1.0, 2.0, 5.0)
    moment_levels = (1.0, 2.5, 5.0, 10.0)
    angle_deg = (0.25, 0.5, 1.0, 2.0)
    translations = []
    for candidate in config["translation_candidates"]:
        stiffness = float(candidate["stiffness_n_m"])
        translations.append(
            {
                **candidate,
                "force_n_at_displacement_mm": {
                    str(value): stiffness * value / 1000.0 for value in displacement_mm
                },
                "deformation_mm_at_force_n": {
                    str(value): 1000.0 * value / stiffness for value in force_levels
                },
                "deformation_mm_at_stage4_gate_force_n": 1000.0 * 200.0 / stiffness,
            }
        )
    rotations = []
    for candidate in config["rotation_candidates"]:
        stiffness = float(candidate["stiffness_nm_rad"])
        rotations.append(
            {
                **candidate,
                "moment_nm_at_angle_deg": {
                    str(value): stiffness * math.radians(value) for value in angle_deg
                },
                "angle_deg_at_moment_nm": {
                    str(value): math.degrees(value / stiffness) for value in moment_levels
                },
            }
        )
    return {"translation": translations, "rotation": rotations}


def _pose_error(
    plant: Stage5SpringDamperPlant,
    target_position: np.ndarray,
    target_rotation: np.ndarray,
) -> np.ndarray:
    current_position = plant.data.site_xpos[plant.attachment_site_id]
    current_rotation = plant.data.site_xmat[plant.attachment_site_id].reshape(3, 3)
    return np.r_[
        target_position - current_position,
        Rotation.from_matrix(target_rotation @ current_rotation.T).as_rotvec(),
    ]


def _realize_robot_site_pose(
    plant: Stage5SpringDamperPlant,
    target_position: np.ndarray,
    target_rotation: np.ndarray,
) -> float:
    for _ in range(40):
        error = _pose_error(plant, target_position, target_rotation)
        if np.linalg.norm(error) <= 1.0e-11:
            break
        jacobian = plant._site_pose_jacobian(plant.attachment_site_id)[
            :, plant.robot_dof_indices
        ]
        delta = np.linalg.pinv(jacobian, rcond=1.0e-10) @ error
        maximum = float(np.max(np.abs(delta)))
        if maximum > 0.08:
            delta *= 0.08 / maximum
        plant.data.qpos[plant.robot_qpos_indices] += delta
        mujoco.mj_forward(plant.model, plant.data)
    residual = float(np.linalg.norm(_pose_error(plant, target_position, target_rotation)))
    if residual > 2.0e-8:
        raise RuntimeError(f"perturbed cuff-site pose residual {residual:.6g}")
    plant.data.qvel[:] = 0.0
    mujoco.mj_forward(plant.model, plant.data)
    return residual


def _initialize_probe(
    plant: Stage5SpringDamperPlant,
    posture_deg: tuple[float, float] | list[float],
    *,
    kind: str,
    axis_index: int,
    magnitude: float,
) -> float:
    plant.reset(np.radians(posture_deg))
    human_position = plant.data.site_xpos[plant.sleeve_site_id].copy()
    human_rotation = plant.data.site_xmat[plant.sleeve_site_id].reshape(3, 3).copy()
    if kind == "translation":
        target_position = human_position + human_rotation[:, axis_index] * magnitude
        target_rotation = human_rotation
    elif kind == "rotation":
        target_position = human_position
        local_rotation = Rotation.from_rotvec(np.eye(3)[axis_index] * magnitude).as_matrix()
        target_rotation = human_rotation @ local_rotation
    else:
        raise ValueError("kind must be translation or rotation")
    return _realize_robot_site_pose(plant, target_position, target_rotation)


def _interface_sample(plant: Stage5SpringDamperPlant) -> dict[str, np.ndarray]:
    interface = plant._evaluate_current_interface()
    human_rotation = plant.data.site_xmat[plant.sleeve_site_id].reshape(3, 3)
    return {
        "translation": interface.displacement_human_m.copy(),
        "rotation": interface.rotation_error_human_rad.copy(),
        "force": human_rotation.T @ interface.human_wrench_world[:3],
        "moment": human_rotation.T @ interface.human_wrench_world[3:],
    }


def _balanced_free_decay_step(plant: Stage5SpringDamperPlant) -> None:
    """Advance an interface-only decay while retaining the full inertial model."""

    plant.data.eq_active[plant.weld_id] = 0
    mujoco.mj_step1(plant.model, plant.data)
    # Cancel gravity and MuJoCo passive joint mechanics only for this controlled
    # calibration fixture. The explicit interface remains the sole excitation.
    plant.data.qfrc_applied[:] = plant.data.qfrc_bias - plant.data.qfrc_passive
    plant._apply_interface()
    mujoco.mj_step2(plant.model, plant.data)
    mujoco.mj_fwdPosition(plant.model, plant.data)
    mujoco.mj_fwdVelocity(plant.model, plant.data)


def _settling_and_ringing(
    time_s: np.ndarray,
    signal: np.ndarray,
    *,
    absolute_tolerance: float,
) -> tuple[float | None, int]:
    initial = abs(float(signal[0]))
    threshold = max(0.02 * initial, absolute_tolerance)
    settling = None
    for index in range(len(signal)):
        if np.max(np.abs(signal[index:])) <= threshold:
            settling = float(time_s[index])
            break
    active = np.asarray(signal)[np.abs(signal) > absolute_tolerance]
    ringing = int(np.count_nonzero(active[1:] * active[:-1] < 0.0)) if len(active) > 1 else 0
    return settling, ringing


def _run_probe(
    plant: Stage5SpringDamperPlant,
    posture_deg: list[float],
    *,
    kind: str,
    axis_index: int,
    magnitude: float,
    duration_s: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    residual = _initialize_probe(
        plant,
        posture_deg,
        kind=kind,
        axis_index=axis_index,
        magnitude=magnitude,
    )
    samples = [_interface_sample(plant)]
    times = [0.0]
    steps = int(round(duration_s / plant.model.opt.timestep))
    finite = True
    for step in range(steps):
        _balanced_free_decay_step(plant)
        sample = _interface_sample(plant)
        samples.append(sample)
        times.append((step + 1) * plant.model.opt.timestep)
        finite_values = np.concatenate(
            [plant.data.qpos, plant.data.qvel, *sample.values()]
        )
        finite = finite and bool(np.all(np.isfinite(finite_values)))
        if not finite or plant.warning_counts():
            break
    time = np.asarray(times)
    trace = {
        "time_s": time,
        "translation_m": np.asarray([sample["translation"] for sample in samples]),
        "rotation_rad": np.asarray([sample["rotation"] for sample in samples]),
        "force_local_n": np.asarray([sample["force"] for sample in samples]),
        "moment_local_nm": np.asarray([sample["moment"] for sample in samples]),
    }
    signal = trace["translation_m"][:, axis_index] if kind == "translation" else trace["rotation_rad"][:, axis_index]
    tolerance = 1.0e-5 if kind == "translation" else math.radians(0.01)
    settling, ringing = _settling_and_ringing(time, signal, absolute_tolerance=tolerance)
    force_rate = np.zeros_like(trace["force_local_n"])
    if len(time) > 1:
        force_rate[1:] = np.diff(trace["force_local_n"], axis=0) / np.diff(time)[:, None]
    result = {
        "posture_deg": posture_deg,
        "kind": kind,
        "axis": AXIS_NAMES[axis_index],
        "signed_requested_translation_mm": 1000.0 * magnitude if kind == "translation" else None,
        "signed_requested_rotation_deg": math.degrees(magnitude) if kind == "rotation" else None,
        "pose_realization_residual": residual,
        "initial_translation_deformation_mm": (1000.0 * trace["translation_m"][0]).tolist(),
        "initial_rotation_deformation_deg": np.degrees(trace["rotation_rad"][0]).tolist(),
        "initial_force_local_n": trace["force_local_n"][0].tolist(),
        "initial_force_norm_n": float(np.linalg.norm(trace["force_local_n"][0])),
        "initial_moment_local_nm": trace["moment_local_nm"][0].tolist(),
        "initial_moment_norm_nm": float(np.linalg.norm(trace["moment_local_nm"][0])),
        "peak_force_norm_n": float(np.max(np.linalg.norm(trace["force_local_n"], axis=1))),
        "peak_moment_norm_nm": float(np.max(np.linalg.norm(trace["moment_local_nm"], axis=1))),
        "peak_translation_deformation_mm": float(1000.0 * np.max(np.linalg.norm(trace["translation_m"], axis=1))),
        "peak_rotation_deformation_deg": float(np.degrees(np.max(np.linalg.norm(trace["rotation_rad"], axis=1)))),
        "peak_force_slew_n_s": float(np.max(np.linalg.norm(force_rate, axis=1))),
        "settling_time_s": settling,
        "ringing_zero_crossings": ringing,
        "finite": finite,
        "warning_counts": plant.warning_counts(),
    }
    return result, trace


def _candidate_sweep(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    selected_rotation = next(
        item
        for item in config["rotation_candidates"]
        if item["name"] == config["selected_rotation_candidate"]
    )
    rows = []
    selected_trace: dict[str, np.ndarray] | None = None
    for translation in config["translation_candidates"]:
        plant = Stage5SpringDamperPlant(
            _parameters(translation, selected_rotation),
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        )
        probes = []
        for posture in config["probe"]["nominal_postures_deg"]:
            for axis_index in range(3):
                for displacement_mm in config["probe"]["translation_mm"]:
                    for sign in config["probe"]["signs"]:
                        result, trace = _run_probe(
                            plant,
                            posture,
                            kind="translation",
                            axis_index=axis_index,
                            magnitude=sign * displacement_mm / 1000.0,
                            duration_s=float(config["probe"]["free_decay_duration_s"]),
                        )
                        probes.append(result)
                        if (
                            translation["name"] == config["selected_translation_candidate"]
                            and posture == [5.0, 10.0]
                            and axis_index == 2
                            and displacement_mm == 2.0
                            and sign == 1.0
                        ):
                            selected_trace = trace
                for rotation_deg in config["probe"]["rotation_deg"]:
                    for sign in config["probe"]["signs"]:
                        result, _ = _run_probe(
                            plant,
                            posture,
                            kind="rotation",
                            axis_index=axis_index,
                            magnitude=sign * math.radians(rotation_deg),
                            duration_s=float(config["probe"]["free_decay_duration_s"]),
                        )
                        probes.append(result)
        rows.append(
            {
                "candidate": translation["name"],
                "translation_stiffness_n_m": translation["stiffness_n_m"],
                "translation_damping_ns_m": translation["damping_ns_m"],
                "rotation_candidate_used": selected_rotation,
                "probe_count": len(probes),
                "all_finite": all(item["finite"] for item in probes),
                "warning_probe_count": sum(bool(item["warning_counts"]) for item in probes),
                "unsettled_probe_count": sum(item["settling_time_s"] is None for item in probes),
                "maximum_ringing_zero_crossings": max(item["ringing_zero_crossings"] for item in probes),
                "maximum_peak_force_n": max(item["peak_force_norm_n"] for item in probes),
                "maximum_peak_moment_nm": max(item["peak_moment_norm_nm"] for item in probes),
                "maximum_force_slew_n_s": max(item["peak_force_slew_n_s"] for item in probes),
                "probes": probes,
            }
        )
    if selected_trace is None:
        raise RuntimeError("selected representative trace was not captured")
    return rows, selected_trace


def _rotation_candidate_sweep(config: dict[str, Any]) -> list[dict[str, Any]]:
    selected_translation = next(
        item
        for item in config["translation_candidates"]
        if item["name"] == config["selected_translation_candidate"]
    )
    rows = []
    for rotation in config["rotation_candidates"]:
        plant = Stage5SpringDamperPlant(
            _parameters(selected_translation, rotation),
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        )
        probes = []
        for posture in config["probe"]["nominal_postures_deg"]:
            for axis_index in range(3):
                for rotation_deg in config["probe"]["rotation_deg"]:
                    for sign in config["probe"]["signs"]:
                        result, _ = _run_probe(
                            plant,
                            posture,
                            kind="rotation",
                            axis_index=axis_index,
                            magnitude=sign * math.radians(rotation_deg),
                            duration_s=float(config["probe"]["free_decay_duration_s"]),
                        )
                        probes.append(result)
        rows.append(
            {
                "candidate": rotation["name"],
                "rotation_stiffness_nm_rad": rotation["stiffness_nm_rad"],
                "rotation_damping_nms_rad": rotation["damping_nms_rad"],
                "probe_count": len(probes),
                "all_finite": all(item["finite"] for item in probes),
                "warning_probe_count": sum(bool(item["warning_counts"]) for item in probes),
                "unsettled_probe_count": sum(item["settling_time_s"] is None for item in probes),
                "maximum_ringing_zero_crossings": max(item["ringing_zero_crossings"] for item in probes),
                "maximum_peak_moment_nm": max(item["peak_moment_norm_nm"] for item in probes),
                "maximum_peak_force_n": max(item["peak_force_norm_n"] for item in probes),
                "probes": probes,
            }
        )
    return rows


def _timestep_sweep(config: dict[str, Any]) -> list[dict[str, Any]]:
    rotation = next(
        item for item in config["rotation_candidates"]
        if item["name"] == config["selected_rotation_candidate"]
    )
    rows = []
    for candidate_name in config["timestep_shortlist"]:
        translation = next(
            item for item in config["translation_candidates"] if item["name"] == candidate_name
        )
        candidate_rows = []
        for dt_s in config["timestep_probe_s"]:
            plant = Stage5SpringDamperPlant(
                _parameters(translation, rotation),
                physics_dt_s=float(dt_s),
                engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
            )
            result, _ = _run_probe(
                plant,
                [20.0, 35.0],
                kind="translation",
                axis_index=2,
                magnitude=0.002,
                duration_s=0.30,
            )
            rotation_result, _ = _run_probe(
                plant,
                [20.0, 35.0],
                kind="rotation",
                axis_index=1,
                magnitude=math.radians(1.0),
                duration_s=0.30,
            )
            candidate_rows.append(
                {
                    "dt_s": dt_s,
                    "translation_probe": result,
                    "rotation_probe": rotation_result,
                }
            )
        baseline = candidate_rows[-1]
        for row in candidate_rows:
            for probe_name in ("translation_probe", "rotation_probe"):
                probe = row[probe_name]
                base = baseline[probe_name]
                probe["sensitivity_relative_to_0p25ms_percent"] = {
                    key: 100.0 * (probe[key] - base[key]) / max(abs(base[key]), 1.0e-12)
                    for key in (
                        "peak_force_norm_n",
                        "peak_moment_norm_nm",
                        "peak_translation_deformation_mm",
                        "peak_rotation_deformation_deg",
                        "peak_force_slew_n_s",
                    )
                }
        rows.append({"candidate": candidate_name, "samples": candidate_rows})
    return rows


def _rom_static_checks(config: dict[str, Any]) -> dict[str, Any]:
    reachability = _reachability_and_clearance()
    rotation = next(
        item for item in config["rotation_candidates"]
        if item["name"] == config["selected_rotation_candidate"]
    )
    candidates = []
    for candidate_name in config["timestep_shortlist"]:
        translation = next(
            item for item in config["translation_candidates"] if item["name"] == candidate_name
        )
        plant = Stage5SpringDamperPlant(_parameters(translation, rotation))
        samples = []
        for posture in STAGE5_CONFIG["representative_postures_deg"]:
            observation = plant.reset(np.radians(posture))
            interface = plant._evaluate_current_interface()
            samples.append(
                {
                    "human_q_deg": posture,
                    "cuff_position_consistency_error_mm": 1000.0 * observation.weld_position_error_m,
                    "cuff_rotation_consistency_error_deg": math.degrees(observation.weld_rotation_error_rad),
                    "interface_preload_translation_mm": (1000.0 * interface.displacement_human_m).tolist(),
                    "interface_preload_rotation_deg": np.degrees(interface.rotation_error_human_rad).tolist(),
                    "static_force_norm_n": float(np.linalg.norm(observation.cuff_force_vector_n)),
                    "static_moment_norm_nm": float(np.linalg.norm(observation.cuff_moment_vector_nm)),
                    "finite": bool(np.all(np.isfinite(np.r_[plant.data.qpos, plant.data.qvel]))),
                    "warning_counts": plant.warning_counts(),
                }
            )
        candidates.append(
            {
                "candidate": candidate_name,
                "samples": samples,
                "maximum_preload_force_n": max(item["static_force_norm_n"] for item in samples),
                "maximum_cuff_position_consistency_error_mm": max(item["cuff_position_consistency_error_mm"] for item in samples),
                "maximum_cuff_rotation_consistency_error_deg": max(item["cuff_rotation_consistency_error_deg"] for item in samples),
                "all_finite": all(item["finite"] for item in samples),
                "warning_sample_count": sum(bool(item["warning_counts"]) for item in samples),
            }
        )
    return {"geometry_reachability_and_clearance": reachability, "candidate_checks": candidates}


def _mechanics_audit() -> dict[str, Any]:
    return {
        "A_human_passive_joint_mechanics": {
            "stiffness_nm_rad": list(STAGE5_HUMAN.passive_stiffness_nm_rad),
            "damping_nms_rad": list(STAGE5_HUMAN.passive_damping_nms_rad),
            "status": "unchanged; not used as a proxy for metallic cuff/link rigidity",
        },
        "B_translation_interface": {
            "law": "objective linear Kelvin-Voigt bushing in moving Human cuff frame",
            "stiffness_diagonal": True,
            "selected_stiffness_isotropic": True,
            "selected_damping_axis_specific_from_effective_mass": True,
            "rest_translation_m": list(STAGE5_RIGID_INTERFACE.rest_translation_human_m),
            "preload_intended": False,
        },
        "C_rotation_interface": {
            "law": "isotropic SO(3) rotation-vector Kelvin-Voigt spring-damper",
            "rest_rotation_rotvec_rad": list(STAGE5_RIGID_INTERFACE.rest_rotation_rotvec_human_rad),
        },
        "D_mujoco_constraints_contacts": {
            "integrator": "implicitfast",
            "soft_interface_weld_active": False,
            "inactive_weld_solref": list(SLEEVE_SOLREF),
            "inactive_weld_solimp": list(SLEEVE_SOLIMP),
            "bed_contact_solref": list(BED_SOLREF),
            "bed_contact_solimp": list(BED_SOLIMP),
            "note": "weld compliance parameters are retained in XML for the donor rigid mode but the equality is disabled in Stage-5 soft-interface execution",
        },
        "E_retained_P1_mechanism": {
            "stage4_p1_reference_parameters": {
                "translation_stiffness_n_m": list(STAGE4_P1_INTERFACE.translation_stiffness_n_m),
                "translation_damping_ns_m": list(STAGE4_P1_INTERFACE.translation_damping_ns_m),
                "rotation_stiffness_nm_rad": STAGE4_P1_INTERFACE.rotation_stiffness_nm_rad,
                "rotation_damping_nms_rad": STAGE4_P1_INTERFACE.rotation_damping_nms_rad,
            },
            "checked_in_force_law_is_nonlinear": False,
            "audit_finding": "the inherited checked-in P1 objective bushing is linear Kelvin-Voigt; no progressive or other nonlinear spring term is present in evaluate_interface",
        },
    }


def _plots(
    output_dir: Path,
    analytical: dict[str, Any],
    timestep: list[dict[str, Any]],
    selected_trace: dict[str, np.ndarray],
) -> None:
    translation = analytical["translation"]
    stiffness = np.array([item["stiffness_n_m"] for item in translation]) / 1000.0
    deformation = np.array([item["deformation_mm_at_force_n"]["50.0"] for item in translation])
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(stiffness, deformation, "o-")
    ax.set(xlabel="Kt (kN/m)", ylabel="Static deformation at 50 N (mm)", title="Stage-5 candidate rigidity scale")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "A_kt_vs_deformation_50n.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    x = np.array([0.5, 1.0, 2.0, 5.0])
    for item in translation:
        y = [item["force_n_at_displacement_mm"][str(value)] for value in x]
        ax.plot(x, y, marker="o", label=item["name"])
    ax.set(xlabel="Imposed displacement (mm)", ylabel="Static force (N)", title="Linear interface force-deformation candidates")
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "B_displacement_vs_force.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for item in timestep:
        dt = [1000.0 * sample["dt_s"] for sample in item["samples"]]
        peak = [sample["translation_probe"]["peak_force_norm_n"] for sample in item["samples"]]
        ax.plot(dt, peak, marker="o", label=item["candidate"])
    ax.invert_xaxis()
    ax.set(xlabel="Physics timestep (ms)", ylabel="Peak force for 2 mm radial probe (N)", title="Shortlist timestep sensitivity")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "C_timestep_sensitivity.png", dpi=180)
    plt.close(fig)

    time = selected_trace["time_s"]
    force = np.linalg.norm(selected_trace["force_local_n"], axis=1)
    deformation = 1000.0 * np.linalg.norm(selected_trace["translation_m"], axis=1)
    fig, force_axis = plt.subplots(figsize=(7.0, 4.3))
    deformation_axis = force_axis.twinx()
    force_axis.plot(time, force, color="tab:red", label="force")
    deformation_axis.plot(time, deformation, color="tab:blue", label="deformation")
    force_axis.set(xlabel="Time (s)", ylabel="Force norm (N)", title="Selected Kt_25k: 2 mm radial free-decay probe")
    deformation_axis.set_ylabel("Interface deformation (mm)")
    force_axis.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "D_selected_force_deformation_trace.png", dpi=180)
    plt.close(fig)


def run_rigid_interface_calibration(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_candidate_config()
    analytical = _analytical_tables(config)
    sweep, selected_trace = _candidate_sweep(config)
    timestep = _timestep_sweep(config)
    rom = _rom_static_checks(config)
    report = {
        "schema": "stage5_rigid_interface_calibration_v1",
        "evidence_category": "smoke_engineering_calibration_only",
        "qualification_claim": False,
        "hardware_measured_values": False,
        "mechanics_audit": _mechanics_audit(),
        "effective_mass_audit": effective_mass_audit(),
        "analytical_force_deformation": analytical,
        "candidate_dynamic_sweep": sweep,
        "rotation_candidate_dynamic_sweep": _rotation_candidate_sweep(config),
        "timestep_sensitivity": timestep,
        "representative_rom_static_checks": rom,
        "selection": {
            "translation_candidate": config["selected_translation_candidate"],
            "rotation_candidate": config["selected_rotation_candidate"],
            "parameters": {
                "translation_stiffness_n_m": list(STAGE5_RIGID_INTERFACE.translation_stiffness_n_m),
                "translation_damping_ns_m": list(STAGE5_RIGID_INTERFACE.translation_damping_ns_m),
                "rotation_stiffness_nm_rad": STAGE5_RIGID_INTERFACE.rotation_stiffness_nm_rad,
                "rotation_damping_nms_rad": STAGE5_RIGID_INTERFACE.rotation_damping_nms_rad,
            },
            "force_deformation_interpretation": {
                str(force): 1000.0 * force / 25000.0 for force in (50.0, 100.0, 150.0, 200.0)
            },
            "stage4_200n_convention": "simulation engineering gate only; not clinical, hardware-certified, or tissue-measured",
            "plant_release": "Stage-5 Plant v1",
            "status": "frozen engineering configuration pending physical hardware calibration",
        },
        "scope": {
            "geometry_changed": False,
            "human_joint_mechanics_changed": False,
            "stage3_or_stage4_files_changed": False,
            "learning_or_rl_run": False,
        },
    }
    (output_dir / "calibration_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(output_dir / "selected_probe_trace.npz", **selected_trace)
    _plots(output_dir, analytical, timestep, selected_trace)
    return report
