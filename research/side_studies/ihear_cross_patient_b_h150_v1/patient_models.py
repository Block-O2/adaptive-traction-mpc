"""Plant-only patient generation and NON-STEPPING model audit.

Run only after the campaign source copy has been added to sys.path, or use CLI
--source. This module never calls mj_step, a physics owner, or a controller.
The returned qualification_case is the public experiment input. Its physical
dictionary reaches only existing hidden_plant/plant construction. Do not place
these hidden values in controller models, observations, or planner arguments.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ALLOWED_OVERRIDES = {
    "body_mass_kg", "height_m", "thigh_length_scale", "shank_length_scale",
    "thigh_mass_scale", "shank_mass_scale", "thigh_com_fraction",
    "shank_com_fraction", "thigh_inertia_radius_fraction",
    "shank_inertia_radius_fraction", "passive_stiffness_nm_rad",
    "passive_damping_nms_rad",
}

def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def patient_case(reference_case, patient_id, overrides):
    """Only change whitelisted physical coefficients; preserve task and setup."""
    illegal = set(overrides) - ALLOWED_OVERRIDES
    if illegal:
        raise ValueError(f"unregistered physical overrides: {sorted(illegal)}")
    case = deepcopy(reference_case)
    case["case_key"] = patient_id
    case["physical"].update(deepcopy(overrides))
    assert case["task"] == reference_case["task"]
    assert case.get("research_model") == reference_case.get("research_model")
    assert case["physical"]["hip_translation_xz_m"] == reference_case["physical"]["hip_translation_xz_m"]
    assert case["physical"]["cuff_fraction_of_shank"] == reference_case["physical"]["cuff_fraction_of_shank"]
    return case


def _cold_static_assembly(case, human, geometry, spec, verify_robot):
    """Use only a cold plant.reset(start); never assign later Human qpos/qvel."""
    import numpy as np
    from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant, solve_cr12_stage5_ik
    from traction_mpc_stage5.rigid_table_assembly_v1.assembly import (
        assess_assembly, _initial_geometry, _forbidden_initial_overlap,
    )
    # verify_robot=False branch uses analytic geometry only, with no MjData.
    result = assess_assembly(case, verify_robot=False)
    result["noninitial_human_state_writes"] = 0
    if not result["valid"] or not verify_robot:
        return result
    try:
        plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        plant.reset(np.asarray(spec.start_return_target_rad))
        assert float(plant.data.time) == 0.0
        result["initial"] = _initial_geometry(plant)
        bad = _forbidden_initial_overlap(result["initial"])
        if bad is not None:
            result.update(valid=False, category="INVALID_COLD_ASSEMBLY", reason=f"cold assembly overlap: {bad}")
            return result
        previous = plant.data.qpos[plant.robot_qpos_indices].copy()
        targets = []
        for q in (spec.outbound_goal_target_rad, spec.start_return_target_rad):
            previous = solve_cr12_stage5_ik(plant._ik_robot,
                geometry.base_from_end_effector_target(np.asarray(q), human), previous_q_rad=previous)
            limits = plant._ik_robot.joint_limits_rad
            targets.append({"human_target_rad": list(q), "robot_q_rad": previous.tolist(),
                "joint_limit_margin_rad": float(np.min(np.minimum(previous-limits[:, 0], limits[:, 1]-previous)))})
        assert float(plant.data.time) == 0.0
        result.update(valid=True, category="COLD_ASSEMBLY_AND_ENDPOINT_IK_VALID",
            reason="analytic task limb screen, cold compiled geometry and endpoint IK passed; no physics",
            endpoint_ik=targets,
            endpoint_full_robot_mesh_clearance="NOT_EVALUATED_WITH_HUMAN_STATE_TELEPORTATION; require execution monitors",
            native_steps=0)
    except (ValueError, RuntimeError) as error:
        result.update(valid=False, category="INITIALIZATION_OR_IK_SEARCH_FAILED", reason=f"{type(error).__name__}: {error}")
    return result


def model_static_audit(case, output_dir=None, verify_robot=True, patient_id=None):
    """Compile, inspect geometry/inertia, and static reset/IK; zero mj_step.

    Only the existing cold plant.reset(start) writes Human state. Endpoint IK
    uses the separate robot-only kinematic model. No endpoint Human qpos writes.
    No diagnostic objects are returned as executable initial state.
    Campaign execution must cold-initialize and commission afresh per patient.
    """
    import mujoco
    import numpy as np
    from traction_mpc_stage3.human import mass_matrix
    from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
    from traction_mpc_stage5.cr12_plant import build_stage5_cr12_model_xml
    from traction_mpc_stage5.mechanics import NOMINAL_PHYSICS_DT_S

    human, geometry, spec, commissioning = hidden_plant(case)
    xml = build_stage5_cr12_model_xml(human, geometry=geometry)
    model = mujoco.MjModel.from_xml_string(xml)
    model.opt.timestep = NOMINAL_PHYSICS_DT_S
    root = ET.fromstring(xml)
    properties = {name: float(getattr(human, name)) for name in (
        "thigh_length_m", "shank_length_m", "thigh_mass_kg", "shank_mass_kg",
        "thigh_com_m", "shank_com_m", "thigh_inertia_kg_m2", "shank_inertia_kg_m2", "sleeve_center_m")}
    if not all(np.isfinite(v) and v > 0.0 for v in properties.values()):
        raise ValueError("non-positive/non-finite patient physical property")
    checks = {}
    for name, prefix in (("hip", "thigh"), ("shank", "shank")):
        body = model.body(name)
        inertia = np.asarray(body.inertia, dtype=float)
        checks[f"{prefix}_positive_inertia"] = bool(np.all(inertia > 0.0))
        checks[f"{prefix}_triangle_inequality"] = bool(2.0 * np.max(inertia) <= np.sum(inertia) + 1e-12)
        checks[f"{prefix}_mass_exact"] = bool(np.isclose(body.mass[0], properties[f"{prefix}_mass_kg"], atol=1e-11, rtol=1e-11))
        checks[f"{prefix}_com_internal"] = bool(0.0 < properties[f"{prefix}_com_m"] < properties[f"{prefix}_length_m"])
    checks["sleeve_inside_shank"] = bool(.040 < human.sleeve_center_m < human.shank_length_m-.040)
    checks["frozen_shank_length_bound_046_m"] = bool(human.shank_length_m <= .46)
    mass_eigen_min = min(float(np.linalg.eigvalsh(mass_matrix(np.array([0., q2]), human)).min())
                         for q2 in np.linspace(human.q_min_rad[1], human.q_max_rad[1], 101))
    checks["planar_mass_matrix_positive_sampled"] = bool(mass_eigen_min > 0.0)
    checks["nonnegative_joint_stiffness_damping"] = bool(
        np.all(np.asarray(human.passive_stiffness_nm_rad) >= 0.0)
        and np.all(np.asarray(human.passive_damping_nms_rad) >= 0.0))
    base = root.find("./worldbody/body[@name='xMateCR12_base']")
    immutable_sections = {tag: ET.tostring(root.find(tag), encoding="unicode") for tag in ("actuator", "contact", "equality")}
    immutable_sections["robot_subtree"] = ET.tostring(base, encoding="unicode")
    immutable_sections["bed"] = ET.tostring(root.find("./worldbody/geom[@name='bed']"), encoding="unicode")
    result = {
        "patient_id": patient_id or case["case_key"], "scope": "NON_STEPPING_MODEL_AND_STATIC_ASSEMBLY_AUDIT_ONLY",
        "physics_starts": 0, "native_steps": 0, "controller_executed": False,
        "case_sha256": digest(case), "physical_sha256": digest(case["physical"]),
        "human_dataclass": asdict(human), "resolved_properties": properties,
        "xml_sha256": hashlib.sha256(xml.encode()).hexdigest(),
        "invariant_robot_contact_interface_sections_sha256": digest(immutable_sections),
        "physics_dt_s": float(model.opt.timestep), "model_nq": model.nq, "model_nv": model.nv,
        "compiled_human_joint_ranges_rad": model.jnt_range[[model.joint(n).id for n in ("hip_joint", "knee_joint")]].tolist(),
        "compiled_human_joint_stiffness_nm_rad": model.jnt_stiffness[[model.joint(n).id for n in ("hip_joint", "knee_joint")]].tolist(),
        "compiled_human_damping_nms_rad": model.dof_damping[[model.jnt_dofadr[model.joint(n).id] for n in ("hip_joint", "knee_joint")]].tolist(),
        "checks": checks, "minimum_sampled_planar_mass_eigenvalue_kg_m2": mass_eigen_min,
        "admissibility_incomplete_until_physical_commissioning": True,
    }
    result["static_assembly"] = _cold_static_assembly(case, human, geometry, spec, verify_robot)
    result["model_static_valid"] = bool(all(checks.values()) and result["static_assembly"]["valid"])
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=False)
        (out / "model.xml").write_text(xml, encoding="utf-8")
        (out / "qualification_case.json").write_text(json.dumps(case, indent=2)+"\n", encoding="utf-8")
        (out / "MODEL_STATIC_AUDIT.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--patient-id")
    parser.add_argument("--geometry-only", action="store_true")
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    for stage in ("stage3_full3d", "stage4_adaptive_control", "stage5_personalized_motion_learning"):
        sys.path.insert(0, str(args.source / "stages" / stage / "src"))
    case = json.loads(args.case.read_text())
    record = model_static_audit(case, args.output, not args.geometry_only, args.patient_id)
    print(json.dumps({"patient_id": record["patient_id"], "model_static_valid": record["model_static_valid"],
          "assembly_category": record["static_assembly"]["category"]}), flush=True)


if __name__ == "__main__":
    main()
