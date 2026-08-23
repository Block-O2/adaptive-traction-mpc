"""Contact-consistent quasistatic feasibility audit for plant V2."""

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
import numpy as np
from scipy.optimize import LinearConstraint, brentq, minimize

from .config import HumanV2Parameters, PlantV2Config
from .environment import SleeveRobotEnvironment
from .kinematics import sleeve_jacobian
from .validation import run_bed_start


@dataclass(frozen=True)
class ContactAuditConfig:
    force_bound_n: float = 200.0
    interaction_force_gate_n: float = 200.0
    soft_limit_margin_deg: float = 5.0
    soft_limit_boundary_torque_nm: float = 25.0
    gap_tolerance_m: float = 1e-8
    normal_velocity_tolerance_m_per_rad: float = 1e-9
    equality_tolerance_nm: float = 1e-7
    rank_relative_tolerance: float = 1e-10
    fine_step_deg: float = 0.25
    coarse_step_deg: float = 0.5
    fine_end_deg: float = 10.0
    scan_end_deg: float = 25.0
    evidence_class: str = "offline_mechanics_diagnostic"


@dataclass(frozen=True)
class BedPoint:
    name: str
    link: str
    distance_m: float
    radius_m: float


def preparation_q1(q2_rad: float, human: HumanV2Parameters) -> float:
    """Candidate ankle-level geometry supplied in the experiment contract."""

    return math.atan2(
        human.shank_length_m * math.sin(q2_rad),
        human.thigh_length_m + human.shank_length_m * math.cos(q2_rad),
    )


def preparation_q1_derivative(q2_rad: float, human: HumanV2Parameters) -> float:
    epsilon = 1e-6
    return (
        preparation_q1(q2_rad + epsilon, human)
        - preparation_q1(q2_rad - epsilon, human)
    ) / (2.0 * epsilon)


def human_v2_quasistatic_load(
    q_rad: np.ndarray,
    human: HumanV2Parameters,
    audit: ContactAuditConfig,
) -> dict[str, np.ndarray]:
    """Return source-faithful G + passive-left load at dq=0.

    This ports the retained MATLAB Human V2 formulation, including the cubic
    lower/upper soft-limit torque that is not present in the V2 MJCF joints.
    """

    q = np.asarray(q_rad, dtype=float)
    q1, q2 = q
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
        q - np.asarray(human.q_rest_rad)
    )
    lower = np.asarray(human.q_min_rad) + math.radians(audit.soft_limit_margin_deg)
    upper = np.asarray(human.q_max_rad) - math.radians(audit.soft_limit_margin_deg)
    soft_rhs = np.zeros(2)
    margin = math.radians(audit.soft_limit_margin_deg)
    for index in range(2):
        if q[index] < lower[index] - 1e-9:
            depth = (lower[index] - 1e-9 - q[index]) / margin
            soft_rhs[index] = audit.soft_limit_boundary_torque_nm * depth**3
        elif q[index] > upper[index] + 1e-9:
            depth = (q[index] - upper[index] - 1e-9) / margin
            soft_rhs[index] = -audit.soft_limit_boundary_torque_nm * depth**3
    soft_left = -soft_rhs
    passive_left = spring_left + soft_left
    return {
        "gravity_nm": gravity,
        "spring_left_nm": spring_left,
        "soft_rhs_nm": soft_rhs,
        "soft_left_nm": soft_left,
        "passive_left_nm": passive_left,
        "tau_required_nm": gravity + passive_left,
    }


def _point_gap_jacobian(
    point: BedPoint,
    q_rad: np.ndarray,
    human: HumanV2Parameters,
    plant: PlantV2Config,
) -> tuple[float, np.ndarray]:
    q1, q2 = q_rad
    if point.link == "thigh":
        center_height = plant.hip_height_m + point.distance_m * math.sin(q1)
        jacobian = np.array([point.distance_m * math.cos(q1), 0.0])
    elif point.link == "shank":
        phi = q1 - q2
        center_height = (
            plant.hip_height_m
            + human.thigh_length_m * math.sin(q1)
            + point.distance_m * math.sin(phi)
        )
        jacobian = np.array(
            [
                human.thigh_length_m * math.cos(q1)
                + point.distance_m * math.cos(phi),
                -point.distance_m * math.cos(phi),
            ]
        )
    else:
        raise ValueError(f"unknown link {point.link}")
    gap = center_height - point.radius_m - plant.bed_height_m
    return float(gap), jacobian


def _contact_catalog(
    human: HumanV2Parameters,
    plant: PlantV2Config,
    distributed: bool,
) -> list[BedPoint]:
    fractions = (0.0, 0.25, 0.5, 0.75, 1.0) if distributed else (0.0, 1.0)
    points = []
    for link, length, radius in (
        ("thigh", human.thigh_length_m, plant.thigh_radius_m),
        ("shank", human.shank_length_m, plant.shank_radius_m),
    ):
        for fraction in fractions:
            points.append(
                BedPoint(
                    name=f"{link}_{fraction:.2f}",
                    link=link,
                    distance_m=fraction * length,
                    radius_m=radius,
                )
            )
    return points


def classify_contacts(
    q_rad: np.ndarray,
    tangent_dq_dq2: np.ndarray,
    human: HumanV2Parameters,
    plant: PlantV2Config,
    audit: ContactAuditConfig,
    distributed: bool = False,
    allow_existing_compliance: bool = False,
) -> dict[str, Any]:
    """Classify bed points using gap-rate positive = separating.

    MuJoCo contact-frame force component 0 is compressive in the local contact
    normal, but its geom ordering may flip the world direction.  The audit
    avoids that ambiguity by defining an explicit world-up gap
    g=z_center-radius-z_bed.  Thus gdot>0 is separating, gdot<0 is motion into
    the bed, and physical bed force is +world-z.
    """

    rows = []
    invalid = False
    for point in _contact_catalog(human, plant, distributed):
        gap, jacobian = _point_gap_jacobian(point, q_rad, human, plant)
        gap_rate = float(jacobian @ tangent_dq_dq2)
        if gap < -audit.gap_tolerance_m and not allow_existing_compliance:
            mode = "invalid_penetration"
            invalid = True
        elif gap > audit.gap_tolerance_m:
            mode = "geometrically_separated"
        elif gap_rate > audit.normal_velocity_tolerance_m_per_rad:
            mode = "separating_lambda_zero"
        elif gap_rate < -audit.normal_velocity_tolerance_m_per_rad:
            mode = "invalid_into_bed"
            invalid = True
        else:
            mode = "admissible_maintained"
        rows.append(
            {
                "name": point.name,
                "link": point.link,
                "gap_mm": 1e3 * gap,
                "gap_rate_m_per_rad": gap_rate,
                "normal_generalized_direction": jacobian.tolist(),
                "mode": mode,
            }
        )
    return {
        "rows": rows,
        "invalid": invalid,
        "admissible": [row for row in rows if row["mode"] == "admissible_maintained"],
        "separating": [row for row in rows if row["mode"] == "separating_lambda_zero"],
        "geometrically_separated": [
            row for row in rows if row["mode"] == "geometrically_separated"
        ],
    }


def _matrix_rank(matrix: np.ndarray, relative_tolerance: float) -> int:
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if not len(singular_values) or singular_values[0] == 0.0:
        return 0
    return int(np.sum(singular_values > relative_tolerance * singular_values[0]))


def solve_minimum_robot_force(
    robot_map: np.ndarray,
    bed_directions: np.ndarray,
    tau_required: np.ndarray,
    audit: ContactAuditConfig,
) -> dict[str, Any]:
    """Minimize robot-force norm subject to exact unilateral equilibrium."""

    bed = np.asarray(bed_directions, dtype=float)
    if bed.size == 0:
        bed = np.zeros((2, 0))
    system = np.column_stack([robot_map, bed])
    variable_count = system.shape[1]
    initial = np.zeros(variable_count)
    unconstrained = np.linalg.lstsq(system, tau_required, rcond=None)[0]
    initial[:2] = unconstrained[:2]
    if variable_count > 2:
        initial[2:] = np.maximum(0.0, unconstrained[2:])
    lower = np.concatenate([np.full(2, -np.inf), np.zeros(variable_count - 2)])
    upper = np.full(variable_count, np.inf)

    def objective(value: np.ndarray) -> float:
        return 0.5 * float(value[:2] @ value[:2])

    def gradient(value: np.ndarray) -> np.ndarray:
        result = np.zeros_like(value)
        result[:2] = value[:2]
        return result

    result = minimize(
        objective,
        initial,
        jac=gradient,
        method="SLSQP",
        bounds=list(zip(lower, upper, strict=True)),
        constraints=[LinearConstraint(system, tau_required, tau_required)],
        options={"ftol": 1e-12, "maxiter": 500},
    )
    value = result.x
    residual = float(np.linalg.norm(system @ value - tau_required))
    exact = residual <= audit.equality_tolerance_nm
    force = value[:2]
    force_norm = float(np.linalg.norm(force))
    within_force = bool(
        force_norm <= audit.interaction_force_gate_n + 1e-9
        and np.all(np.abs(force) <= audit.force_bound_n + 1e-9)
    )
    return {
        "optimizer_success": bool(result.success),
        "optimizer_message": result.message,
        "exact_equilibrium": exact,
        "equilibrium_residual_nm": residual,
        "robot_force_n": force.tolist(),
        "robot_force_norm_n": force_norm,
        "bed_reactions_n": value[2:].tolist(),
        "within_force_limits": within_force,
        "force_reserve_n": (
            audit.interaction_force_gate_n - force_norm if exact else None
        ),
    }


def _mujoco_load_crosscheck(
    q_rad: np.ndarray,
    env: SleeveRobotEnvironment,
    analytical: dict[str, np.ndarray],
) -> dict[str, Any]:
    for equality_index in range(env.model.neq):
        env.data.eq_active[equality_index] = 0
    env.data.joint("hip_joint").qpos[0] = q_rad[0]
    env.data.joint("knee_joint").qpos[0] = q_rad[1]
    env.data.qvel[:] = 0.0
    env.data.ctrl[:] = 0.0
    import mujoco

    mujoco.mj_forward(env.model, env.data)
    dofs = np.array(
        [env.model.joint(name).dofadr[0] for name in ("hip_joint", "knee_joint")]
    )
    mujoco_base_load = env.data.qfrc_bias[dofs] - env.data.qfrc_passive[dofs]
    analytical_base = analytical["gravity_nm"] + analytical["spring_left_nm"]
    return {
        "mujoco_gravity_plus_linear_passive_nm": mujoco_base_load.tolist(),
        "analytical_gravity_plus_linear_passive_nm": analytical_base.tolist(),
        "max_abs_error_nm": float(np.max(np.abs(mujoco_base_load - analytical_base))),
        "soft_limit_in_mjcf": False,
    }


def _scan_grid(rest_q2_deg: float, audit: ContactAuditConfig) -> np.ndarray:
    fine = np.arange(0.0, audit.fine_end_deg + 0.5 * audit.fine_step_deg, audit.fine_step_deg)
    coarse = np.arange(
        audit.fine_end_deg + audit.coarse_step_deg,
        audit.scan_end_deg + 0.5 * audit.coarse_step_deg,
        audit.coarse_step_deg,
    )
    return np.unique(np.concatenate([fine, coarse, [rest_q2_deg]]))


def _refined_force_feasible_intervals(
    rows: list[dict[str, Any]],
    human: HumanV2Parameters,
    plant: PlantV2Config,
    audit: ContactAuditConfig,
) -> list[list[float]]:
    """Refine 200 N crossings bracketed by the registered posture grid."""

    valid_rows = [row for row in rows if row["q2_deg"] > 1e-6]
    crossings = []
    for before, after in zip(valid_rows[:-1], valid_rows[1:], strict=True):
        before_margin = before["force_reserve_n"]
        after_margin = after["force_reserve_n"]
        if before_margin is None or after_margin is None:
            continue
        if before_margin == 0.0:
            crossings.append(before["q2_deg"])
        elif before_margin * after_margin < 0.0:
            root = brentq(
                lambda value: audit_posture(value, human, plant, audit)[
                    "force_reserve_n"
                ],
                before["q2_deg"],
                after["q2_deg"],
                xtol=1e-11,
            )
            crossings.append(float(root))
    boundaries = [valid_rows[0]["q2_deg"], *crossings, valid_rows[-1]["q2_deg"]]
    intervals = []
    for lower, upper in zip(boundaries[:-1], boundaries[1:], strict=True):
        midpoint = 0.5 * (lower + upper)
        row = audit_posture(midpoint, human, plant, audit)
        if row["classification"] in (
            "CONTACT_ASSISTED_FEASIBLE",
            "ROBOT_ONLY_FEASIBLE",
        ):
            intervals.append([lower, upper])
    return intervals


def audit_posture(
    q2_deg: float,
    human: HumanV2Parameters,
    plant: PlantV2Config,
    audit: ContactAuditConfig,
    distributed: bool = False,
) -> dict[str, Any]:
    q2 = math.radians(q2_deg)
    q1 = preparation_q1(q2, human)
    q = np.array([q1, q2])
    tangent = np.array([preparation_q1_derivative(q2, human), 1.0])
    contacts = classify_contacts(q, tangent, human, plant, audit, distributed)
    robot_map = sleeve_jacobian(q, human)[[0, 2], :].T
    admissible = contacts["admissible"]
    bed = (
        np.column_stack(
            [np.asarray(row["normal_generalized_direction"]) for row in admissible]
        )
        if admissible
        else np.zeros((2, 0))
    )
    load = human_v2_quasistatic_load(q, human, audit)
    robot_only = solve_minimum_robot_force(
        robot_map, np.zeros((2, 0)), load["tau_required_nm"], audit
    )
    assisted = solve_minimum_robot_force(robot_map, bed, load["tau_required_nm"], audit)
    augmented = np.column_stack([robot_map, bed])
    if contacts["invalid"]:
        classification = "PATH_CONTACT_INCOMPATIBLE"
    elif assisted["exact_equilibrium"] and assisted["within_force_limits"]:
        if any(value > 1e-6 for value in assisted["bed_reactions_n"]):
            classification = "CONTACT_ASSISTED_FEASIBLE"
        else:
            classification = "ROBOT_ONLY_FEASIBLE"
    elif not assisted["exact_equilibrium"]:
        classification = "RANK_OR_UNILATERAL_INCOMPATIBLE"
    else:
        classification = "FORCE_LIMIT_INFEASIBLE"
    reactions = {
        row["name"]: value
        for row, value in zip(admissible, assisted["bed_reactions_n"], strict=True)
    }
    return {
        "q2_deg": q2_deg,
        "q1_deg": math.degrees(q1),
        "path_tangent_dq1_dq2": tangent[0],
        "robot_only_rank": _matrix_rank(robot_map, audit.rank_relative_tolerance),
        "augmented_admissible_rank": _matrix_rank(
            augmented, audit.rank_relative_tolerance
        ),
        "admissible_contacts": [row["name"] for row in admissible],
        "separating_contacts": [row["name"] for row in contacts["separating"]],
        "geometrically_separated_contacts": [
            row["name"] for row in contacts["geometrically_separated"]
        ],
        "invalid_contacts": [
            row["name"]
            for row in contacts["rows"]
            if row["mode"].startswith("invalid")
        ],
        "contact_mode": "+".join(row["name"] for row in admissible) or "none",
        "tau_required_nm": load["tau_required_nm"].tolist(),
        "gravity_nm": load["gravity_nm"].tolist(),
        "passive_left_nm": load["passive_left_nm"].tolist(),
        "soft_rhs_nm": load["soft_rhs_nm"].tolist(),
        "robot_only_force_n": robot_only["robot_force_n"],
        "robot_only_force_norm_n": robot_only["robot_force_norm_n"],
        "robot_only_force_reserve_n": robot_only["force_reserve_n"],
        "robot_only_exact": robot_only["exact_equilibrium"],
        "minimum_robot_force_n": assisted["robot_force_n"],
        "minimum_robot_force_norm_n": assisted["robot_force_norm_n"],
        "force_reserve_n": assisted["force_reserve_n"],
        "bed_reactions_n": reactions,
        "equilibrium_residual_nm": assisted["equilibrium_residual_nm"],
        "classification": classification,
        "contact_details": contacts["rows"],
    }


def run_contact_feasibility_audit(
    audit_config: ContactAuditConfig | None = None,
) -> dict[str, Any]:
    audit = audit_config or ContactAuditConfig()
    human = HumanV2Parameters()
    plant = PlantV2Config()
    bed_start, _ = run_bed_start(plant)
    rest_q = np.radians(bed_start["resting_q_deg"])
    rest_q2_deg = float(bed_start["resting_q_deg"][1])
    rows = [
        audit_posture(value, human, plant, audit, distributed=False)
        for value in _scan_grid(rest_q2_deg, audit)
    ]
    sensitivity_rows = [
        audit_posture(value, human, plant, audit, distributed=True)
        for value in (0.0, rest_q2_deg, 5.0, 10.0, 20.0)
    ]
    force_feasible_intervals = _refined_force_feasible_intervals(
        rows, human, plant, audit
    )

    path_q1_at_rest = preparation_q1(rest_q[1], human)
    entry_tangent = np.array(
        [preparation_q1_derivative(rest_q[1], human), 1.0]
    )
    rest_contacts = classify_contacts(
        rest_q,
        entry_tangent,
        human,
        plant,
        audit,
        distributed=True,
        allow_existing_compliance=True,
    )
    intervals_after_rest = [
        interval for interval in force_feasible_intervals if interval[1] >= rest_q2_deg
    ]
    robot_only_entry = (
        max(rest_q2_deg, intervals_after_rest[0][0]) if intervals_after_rest else None
    )
    persistent_entry = (
        intervals_after_rest[-1][0]
        if intervals_after_rest
        and abs(intervals_after_rest[-1][1] - audit.scan_end_deg) <= 1e-8
        else None
    )
    assisted_from_rest = [
        row
        for row in rows
        if row["q2_deg"] >= rest_q2_deg
        and row["classification"] in (
            "CONTACT_ASSISTED_FEASIBLE",
            "ROBOT_ONLY_FEASIBLE",
        )
    ]
    first_assisted = (
        min(row["q2_deg"] for row in assisted_from_rest)
        if assisted_from_rest
        else None
    )
    continuous_from_rest = bool(
        first_assisted is not None
        and first_assisted <= rest_q2_deg + audit.fine_step_deg + 1e-9
    )
    sensitivity_equivalent = all(
        abs(
            row["minimum_robot_force_norm_n"]
            - next(
                nominal["minimum_robot_force_norm_n"]
                for nominal in rows
                if abs(nominal["q2_deg"] - row["q2_deg"]) < 1e-9
            )
        )
        <= 1e-6
        for row in sensitivity_rows
    )
    representative_q = np.array(
        [preparation_q1(math.radians(5.0), human), math.radians(5.0)]
    )
    representative_load = human_v2_quasistatic_load(representative_q, human, audit)
    env = SleeveRobotEnvironment(config=plant)
    env.reset(plant.q_terminal_deg)
    crosscheck = _mujoco_load_crosscheck(representative_q, env, representative_load)
    path_valid = not any(row["classification"] == "PATH_CONTACT_INCOMPATIBLE" for row in rows)
    if not path_valid:
        conclusion = "PATH_CONTACT_INCOMPATIBLE"
    elif continuous_from_rest and robot_only_entry is not None:
        conclusion = "CONTINUOUS_SUPPORT_BRIDGE_FOUND"
    else:
        conclusion = "SUPPORT_AUTHORITY_GAP"
    concise_rows = [
        {key: value for key, value in row.items() if key != "contact_details"}
        for row in rows
    ]
    return {
        "evidence_class": audit.evidence_class,
        "audit_config": asdict(audit),
        "bed_start": bed_start,
        "candidate_path": {
            "formula": "atan2(L2*sin(q2), L1+L2*cos(q2))",
            "path_q1_at_measured_rest_q2_deg": math.degrees(path_q1_at_rest),
            "measured_rest_to_path_q1_offset_deg": math.degrees(path_q1_at_rest - rest_q[0]),
            "contact_kinematically_valid": path_valid,
        },
        "measured_rest_entry_contacts": rest_contacts["rows"],
        "primary_rows": concise_rows,
        "distribution_sensitivity_rows": sensitivity_rows,
        "distribution_sensitivity_equivalent": sensitivity_equivalent,
        "contact_assisted_continuous_from_rest": continuous_from_rest,
        "contact_assisted_continuous_interval_deg": None,
        "contact_and_robot_force_feasible_intervals_within_scan_deg": (
            force_feasible_intervals
        ),
        "first_feasible_scanned_angle_deg": first_assisted,
        "robot_only_feasible_entry_deg": robot_only_entry,
        "robot_only_persistent_entry_deg": persistent_entry,
        "global_classification": conclusion,
        "mujoco_load_crosscheck_at_5deg": crosscheck,
        "normal_sign_convention": {
            "gap": "g=z_center-radius-z_bed",
            "positive_gap_rate": "separating; lambda=0",
            "negative_gap_rate": "motion into bed; path invalid",
            "physical_bed_force": "+world-z",
            "prompt_minus_form_equivalence": (
                "tau_req=Js^T F+Jpoint^T n_up lambda; equivalently use "
                "J_b=-Jpoint in the stated minus-sum equation"
            ),
        },
        "frozen_values": {
            "human_v2": True,
            "cr12_like_robot": True,
            "bilateral_point_sleeve": True,
            "unilateral_compliant_bed": True,
            "force_bound_n": audit.force_bound_n,
            "interaction_force_gate_n": audit.interaction_force_gate_n,
            "normal_controller_windowed_nls_r3c_recovery": False,
        },
        "scientific_variables_changed": [],
    }


def _plot_audit(output_dir: Path, summary: dict[str, Any]) -> None:
    rows = summary["primary_rows"]
    q2 = np.array([row["q2_deg"] for row in rows])
    robot = np.array(
        [
            row["robot_only_force_norm_n"] if row["robot_only_exact"] else np.nan
            for row in rows
        ]
    )
    assisted = np.array(
        [
            row["minimum_robot_force_norm_n"]
            if row["equilibrium_residual_nm"] <= summary["audit_config"]["equality_tolerance_nm"]
            else np.nan
            for row in rows
        ]
    )
    reactions = np.array(
        [sum(row["bed_reactions_n"].values()) for row in rows]
    )
    rank_robot = np.array([row["robot_only_rank"] for row in rows])
    rank_augmented = np.array([row["augmented_admissible_rank"] for row in rows])
    feasible = np.array(
        [
            row["classification"]
            in ("CONTACT_ASSISTED_FEASIBLE", "ROBOT_ONLY_FEASIBLE")
            for row in rows
        ],
        dtype=float,
    )
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, constrained_layout=True)
    axes[0].plot(q2, robot, label="robot-only required")
    axes[0].plot(q2, assisted, "--", label="contact-assisted minimum")
    axes[0].axhline(200.0, color="r", linestyle=":", label="200 N gate")
    axes[0].set_ylim(0.0, min(1000.0, 1.05 * np.nanmax(assisted[q2 >= 1.0])))
    axes[0].set_ylabel("robot force norm (N)")
    axes[0].legend()
    axes[1].plot(q2, reactions, label="total admissible bed reaction")
    axes[1].set_ylabel("bed reaction (N)")
    axes[1].legend()
    axes[2].step(q2, rank_robot, where="mid", label="robot-only rank")
    axes[2].step(q2, rank_augmented, "--", where="mid", label="augmented rank")
    axes[2].step(q2, feasible, ":", where="mid", label="force/contact feasible")
    axes[2].set_ylabel("rank / gate")
    axes[2].set_xlabel("q2 (deg)")
    axes[2].set_yticks([0, 1, 2])
    axes[2].legend()
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Contact-consistent quasistatic bridge audit")
    fig.savefig(output_dir / "force_rank_feasibility_timeline.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    axes[0].plot(q2, 200.0 - assisted, label="force reserve")
    axes[0].axhline(0.0, color="r", linestyle=":")
    axes[0].set_yscale("symlog", linthresh=50.0)
    axes[0].set_ylabel("reserve (N)")
    modes = sorted({row["contact_mode"] for row in rows})
    mode_index = np.array([modes.index(row["contact_mode"]) for row in rows])
    axes[1].step(q2, mode_index, where="mid")
    axes[1].set_yticks(range(len(modes)), modes)
    axes[1].set_ylabel("admissible contact mode")
    axes[1].set_xlabel("q2 (deg)")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Force margin and admissible bed-contact mode")
    fig.savefig(output_dir / "force_margin_contact_mode.png", dpi=170)
    plt.close(fig)


def write_contact_feasibility_artifacts(output_dir: Path, summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    fields = [
        "q2_deg",
        "q1_deg",
        "robot_only_rank",
        "augmented_admissible_rank",
        "contact_mode",
        "robot_only_force_n",
        "robot_only_force_norm_n",
        "minimum_robot_force_n",
        "minimum_robot_force_norm_n",
        "bed_reactions_n",
        "force_reserve_n",
        "classification",
    ]
    lines = [",".join(fields)]
    for row in summary["primary_rows"]:
        values = []
        for field in fields:
            value = row[field]
            if isinstance(value, (list, dict)):
                value = json.dumps(value, separators=(";", ":"))
            values.append(str(value))
        lines.append(",".join(values))
    (output_dir / "posture_feasibility.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    _plot_audit(output_dir, summary)
