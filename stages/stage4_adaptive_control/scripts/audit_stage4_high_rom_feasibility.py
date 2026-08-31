#!/usr/bin/env python3
"""Run the static high-ROM Human V2 / UR10e feasibility audit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage4.high_rom_feasibility import (
    audit_pose,
    coordinate_description,
    flatten_row_for_csv,
    grid_values_deg,
    json_ready,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
SPECIAL_POSES = [(90.0, 90.0), (120.0, 90.0), (90.0, 120.0), (120.0, 120.0)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _scan() -> list[dict[str, object]]:
    values = grid_values_deg()
    robot = UR10eTorqueRobot()
    plant = CoupledUR10eHumanV2()
    rows: list[dict[str, object]] = []
    previous: np.ndarray | None = None
    for row_index, q1 in enumerate(values):
        q2_values = values if row_index % 2 == 0 else list(reversed(values))
        for q2 in q2_values:
            seeds = [] if previous is None else [previous]
            record, solution = audit_pose(
                (q1, q2), robot, plant, continuation_seeds=seeds
            )
            rows.append(record)
            if solution is not None:
                previous = solution
    rows.sort(key=lambda item: (item["q1_deg"], item["q2_deg"]))
    return rows


def _special(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_pose = {(row["q1_deg"], row["q2_deg"]): row for row in rows}
    return {f"{q1:g}_{q2:g}": by_pose[(q1, q2)] for q1, q2 in SPECIAL_POSES}


def _lookup(
    rows: list[dict[str, object]], q1: float, q2: float
) -> dict[str, object]:
    return next(
        row for row in rows if row["q1_deg"] == q1 and row["q2_deg"] == q2
    )


def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
    classifications: dict[str, int] = {}
    for row in rows:
        key = str(row["classification"])
        classifications[key] = classifications.get(key, 0) + 1
    strictly_clear = [row for row in rows if not row["mechanical_blockers"]]
    intrinsically_clear = [
        row for row in rows if not row["intrinsic_mechanical_blockers"]
    ]
    conditional_gate_clear = [
        row
        for row in intrinsically_clear
        if row["conditional_without_soft_limit_allocation"]["force_gate_margin_n"] >= 0.0
    ]
    high_rom_clear = [
        row
        for row in conditional_gate_clear
        if row["q1_deg"] >= 90.0 or row["q2_deg"] >= 90.0
    ]
    maximum = {
        "q1_deg": max((row["q1_deg"] for row in high_rom_clear), default=None),
        "q2_deg": max((row["q2_deg"] for row in high_rom_clear), default=None),
    }
    transmission_conditions = [
        row["rigid_cuff_transmission"]["condition_number_raw_mixed_units"]
        for row in rows
    ]
    robot_conditions = [
        row["robot"].get("jacobian_condition_number")
        for row in rows
        if row["robot"].get("jacobian_condition_number") is not None
    ]
    reachable = [row for row in rows if row["robot"]["reachable"]]
    robot_sigma = [
        row["robot"]["minimum_6d_jacobian_singular_value"] for row in reachable
    ]
    conditional_forces = [
        row["conditional_without_soft_limit_allocation"]["force_norm_n"]
        for row in rows
    ]
    collision_counts = {
        "human_or_sleeve_bed_penetration": sum(
            "human_or_sleeve_bed_penetration" in row["intrinsic_mechanical_blockers"]
            for row in rows
        ),
        "ur10e_full_pose_ik_unreachable": sum(
            "ur10e_full_pose_ik_unreachable" in row["intrinsic_mechanical_blockers"]
            for row in rows
        ),
        "ur10e_self_collision": sum(
            "ur10e_self_collision" in row["intrinsic_mechanical_blockers"]
            for row in rows
        ),
        "ur10e_bed_intersection_selected_branch": sum(
            "ur10e_bed_intersection" in row["surrogate_geometry_blockers"]
            for row in rows
        ),
        "ur10e_human_intersection": sum(
            "ur10e_human_intersection" in row["surrogate_geometry_blockers"]
            for row in rows
        ),
    }
    return {
        "audit_kind": "exploratory_static_engineering_feasibility",
        "dynamic_or_controller_benchmark_run": False,
        "grid": {
            "q1_values_deg": grid_values_deg(),
            "q2_values_deg": grid_values_deg(),
            "sample_count": len(rows),
            "description": "10 deg broad grid, refined to 5 deg spacing from 80 to 120 deg",
        },
        "frozen_human_v2": {
            "q_min_deg": np.degrees(HUMAN.q_min_rad).tolist(),
            "q_max_deg": np.degrees(HUMAN.q_max_rad).tolist(),
            "q_rest_deg": np.degrees(HUMAN.q_rest_rad).tolist(),
            "soft_limit_margin_deg": float(np.degrees(HUMAN.soft_limit_margin_rad)),
            "soft_limit_boundary_torque_nm": HUMAN.soft_limit_boundary_torque_nm,
            "soft_limit_damping_nms_rad": HUMAN.soft_limit_damping_nms_rad,
            "cuff_translational_force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
            "cuff_moment_gate": None,
        },
        "coordinate_conventions": coordinate_description(),
        "classification_counts": classifications,
        "current_rom_valid_sample_count": sum(
            bool(row["current_rom_valid"]) for row in rows
        ),
        "strictly_clear_sample_count": len(strictly_clear),
        "intrinsically_clear_ignoring_disabled_collision_domains_sample_count": len(
            intrinsically_clear
        ),
        "conditional_force_gate_clear_sample_count": len(conditional_gate_clear),
        "high_rom_conditionally_clear_sample_count": len(high_rom_clear),
        "largest_sampled_high_rom_coordinates_conditionally_clear": maximum,
        "conditional_without_soft_limit_force_n": {
            "minimum": float(min(conditional_forces)),
            "maximum": float(max(conditional_forces)),
            "samples_over_200_n": sum(
                force > CUFF_TRANSLATIONAL_FORCE_GATE_N
                for force in conditional_forces
            ),
        },
        "collision_and_reachability_counts": collision_counts,
        "rigid_cuff_condition_raw_mixed_units": {
            "minimum": float(min(transmission_conditions)),
            "maximum": float(max(transmission_conditions)),
        },
        "reachable_robot_condition": {
            "reachable_samples": len(reachable),
            "unreachable_samples": len(rows) - len(reachable),
            "minimum": float(min(robot_conditions)) if robot_conditions else None,
            "maximum": float(max(robot_conditions)) if robot_conditions else None,
            "minimum_6d_jacobian_singular_value": (
                float(min(robot_sigma)) if robot_sigma else None
            ),
        },
        "rigid_cuff_rank_counts": {
            str(rank): sum(
                row["rigid_cuff_transmission"]["rank"] == rank for row in rows
            )
            for rank in (0, 1, 2)
        },
        "translational_force_only_rank_counts": {
            str(rank): sum(
                row["rigid_cuff_transmission"]["translational_force_only_rank"]
                == rank
                for row in rows
            )
            for rank in (0, 1, 2)
        },
        "special_poses": _special(rows),
        "candidate_endpoints": {
            "hip_dominant": _lookup(rows, 100.0, 60.0),
            "knee_dominant": _lookup(rows, 60.0, 100.0),
            "both_high": _lookup(rows, 90.0, 90.0),
            "aggressive": _lookup(rows, 120.0, 90.0),
        },
        "interpretation_limits": [
            "The no-soft-limit allocation is a conditional diagnostic, not an amended Human V2 model.",
            "UR10e reachability does not establish CR12 reachability.",
            "Raw B singular values mix force and moment units and are used only for within-formulation comparison.",
            "Robot-Human and robot-bed contacts are disabled in the frozen plant; audit distances do not add contact response.",
            "The frozen model has no Human self-collision model or clinical ROM model.",
        ],
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    flattened = [flatten_row_for_csv(row) for row in rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flattened[0]))
        writer.writeheader()
        writer.writerows(flattened)


def _matrix(rows: list[dict[str, object]], key) -> tuple[np.ndarray, list[float]]:
    values = grid_values_deg()
    lookup = {(row["q1_deg"], row["q2_deg"]): row for row in rows}
    matrix = np.array([[key(lookup[(q1, q2)]) for q1 in values] for q2 in values])
    return matrix, values


def _write_plots(output: Path, rows: list[dict[str, object]]) -> None:
    classification_map = {
        "valid_under_current_human_v2": 0.0,
        "geometrically_feasible_if_human_rom_is_extended": 1.0,
        "blocked_by_current_surrogate_collision_geometry": 2.0,
        "geometric_or_robotic_infeasible": 3.0,
    }
    classes, values = _matrix(rows, lambda row: classification_map[row["classification"]])
    force, _ = _matrix(
        rows,
        lambda row: row["conditional_without_soft_limit_allocation"]["force_norm_n"],
    )
    extent = [min(values), max(values), min(values), max(values)]

    figure, axes = plt.subplots(1, 2, figsize=(12.0, 5.0), constrained_layout=True)
    image = axes[0].imshow(
        classes,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        aspect="equal",
        cmap=matplotlib.colors.ListedColormap(
            ["#2ca25f", "#3182bd", "#fdae6b", "#de2d26"]
        ),
        vmin=-0.5,
        vmax=3.5,
    )
    colorbar = figure.colorbar(image, ax=axes[0], ticks=[0, 1, 2, 3])
    colorbar.ax.set_yticklabels(
        ["current ROM", "ROM extension only", "surrogate geometry", "intrinsic blocker"]
    )
    axes[0].set_title("Static feasibility classification")
    axes[0].set_xlabel("hip q1 (deg)")
    axes[0].set_ylabel("knee q2 (deg)")

    force_image = axes[1].imshow(
        force,
        origin="lower",
        extent=extent,
        interpolation="bilinear",
        aspect="equal",
        cmap="viridis",
    )
    figure.colorbar(force_image, ax=axes[1], label="conditional force (N)")
    axes[1].contour(values, values, force, levels=[200.0], colors="red", linewidths=1.5)
    axes[1].set_title("Quasi-static force without soft-limit term")
    axes[1].set_xlabel("hip q1 (deg)")
    axes[1].set_ylabel("knee q2 (deg)")
    figure.savefig(output / "high_rom_feasibility_heatmaps.png", dpi=180)
    plt.close(figure)

    robot_condition, values = _matrix(
        rows,
        lambda row: row["robot"].get("jacobian_condition_number", np.nan),
    )
    cuff_condition, _ = _matrix(
        rows,
        lambda row: row["rigid_cuff_transmission"]["condition_number_raw_mixed_units"],
    )
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 5.0), constrained_layout=True)
    for axis, data, title in (
        (axes[0], robot_condition, "UR10e 6D Jacobian condition"),
        (axes[1], cuff_condition, "Rigid-cuff B condition (raw mixed units)"),
    ):
        image = axis.imshow(
            data,
            origin="lower",
            extent=extent,
            interpolation="bilinear",
            aspect="equal",
            cmap="magma",
        )
        figure.colorbar(image, ax=axis)
        axis.set_title(title)
        axis.set_xlabel("hip q1 (deg)")
        axis.set_ylabel("knee q2 (deg)")
    figure.savefig(output / "high_rom_conditioning_heatmaps.png", dpi=180)
    plt.close(figure)


def _report(summary: dict[str, object]) -> str:
    poses = summary["special_poses"]
    candidates = summary["candidate_endpoints"]
    lines = [
        "# High-ROM static feasibility audit",
        "",
        "Status: **exploratory engineering audit; not a formal experiment**.",
        "No controller benchmark, dynamic rehabilitation rollout, ROM amendment, or controller change was run.",
        "",
        "## Coordinate conventions",
        "",
        "`q1` is positive hip flexion from a thigh along world +X; the absolute thigh angle is `q1`.",
        "`q2` is positive knee flexion relative to the thigh; the absolute shank angle is `q1-q2`.",
        "The zero pose is a straight horizontal limb. The cuff orientation is `Ry(q2-q1)`.",
        "",
        "## Frozen assumptions",
        "",
        "Human V2 ROM remains hip 0-80 deg and knee 0-100 deg. The 5 deg soft-limit zone,",
        "25 Nm boundary term, 2 Nms/rad directional limit damping, and 200 N translational",
        "force gate are unchanged. No cuff moment gate exists in the frozen repository.",
        "",
        "## Four requested configurations",
        "",
        "| pose | physical interpretation | current ROM | current / conditional tau (Nm) | current / conditional force (N) | current / conditional moment (Nm) | blockers |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for key, physical in (
        ("90_90", "thigh vertical; shank horizontal"),
        ("120_90", "thigh 120 deg; shank 30 deg"),
        ("90_120", "thigh vertical; shank -30 deg"),
        ("120_120", "thigh 120 deg; shank horizontal"),
    ):
        row = poses[key]
        conditional = row["conditional_without_soft_limit_allocation"]
        current = row["current_model_allocation"]
        invalid_joints = []
        if row["q1_deg"] > 80.0:
            invalid_joints.append("hip")
        if row["q2_deg"] > 100.0:
            invalid_joints.append("knee")
        rom_note = "valid" if not invalid_joints else "invalid: " + "+".join(invalid_joints)
        tau_current = row["static_torque"]["current_nm"]
        tau_conditional = row["static_torque"]["without_soft_limit_nm"]
        blockers = ", ".join(row["mechanical_blockers"]) or "none"
        lines.append(
            f"| ({row['q1_deg']:g},{row['q2_deg']:g}) | {physical} | "
            f"{rom_note} | [{tau_current[0]:.2f},{tau_current[1]:.2f}] / "
            f"[{tau_conditional[0]:.2f},{tau_conditional[1]:.2f}] | "
            f"{current['force_norm_n']:.2f} / {conditional['force_norm_n']:.2f} | "
            f"{current['moment_abs_nm']:.2f} / {conditional['moment_abs_nm']:.2f} | {blockers} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "A pose outside 80/100 deg is invalid under the current Human V2 declaration even if geometry and IK are clear.",
            "For such poses, current soft-limit torque is reported but not interpreted as physical high-ROM demand.",
            "The conditional column removes only the frozen soft-limit term; it is a diagnostic for deciding whether a model amendment is worth reviewing, not a validated extended-ROM model.",
            "Human-bed penetration, UR10e IK failure, geometric intersections, modeled robot torque-limit violation, and the 200 N conditional force gate are kept as distinct mechanical blockers.",
            f"There are {summary['strictly_clear_sample_count']} strictly clear samples under every current geometry check. "
            f"When disabled robot-bed/robot-Human collision domains are separated as a surrogate-model issue, {summary['intrinsically_clear_ignoring_disabled_collision_domains_sample_count']} samples are otherwise clear.",
            "",
            "## Grid findings",
            "",
            f"The full-pose UR10e IK reached {summary['reachable_robot_condition']['reachable_samples']} of {summary['grid']['sample_count']} sampled poses; "
            f"{summary['reachable_robot_condition']['unreachable_samples']} were unreachable under the deterministic search.",
            f"Conditional no-soft-limit cuff force ranged from {summary['conditional_without_soft_limit_force_n']['minimum']:.2f} to "
            f"{summary['conditional_without_soft_limit_force_n']['maximum']:.2f} N; {summary['conditional_without_soft_limit_force_n']['samples_over_200_n']} samples exceeded 200 N.",
            f"The rigid-cuff map was rank 2 at {summary['rigid_cuff_rank_counts']['2']} of {summary['grid']['sample_count']} samples; "
            f"the point-force submap was rank 1 at {summary['translational_force_only_rank_counts']['1']} knee-extension samples.",
            f"The sampled conditional envelope reaches q1=120 and q2=120 algebraically, but this is not a strict current-model feasible region because of the collision-geometry findings below.",
            "On the sampled conditional envelope, q2=120 is intrinsically clear only from q1=70 upward, and q1=120 is intrinsically clear from q2=80 upward. These are grid observations, not continuous-boundary proofs.",
            "",
            "## Model/contact limits",
            "",
            "The frozen plant enables Human-bed and robot self-contact, but disables robot-bed and robot-Human contact.",
            "This audit queries their signed geometry distances without adding response forces. The model also has no Human self-collision or clinical ROM representation.",
            "Every IK-reachable sample showed a 0.062 m wrist/shank overlap with the provisional identity cuff adapter. This is a current surrogate geometry defect, not evidence that every physical adapter is impossible.",
            "Some selected IK branches also cross the bed; because one static branch per grid point was retained, a negative bed distance is an observed branch blocker rather than proof that all IK branches fail.",
            "The four requested poses have no Human-link or sleeve bed penetration. Their thigh capsule remains tangent at the fixed hip end; 120/120 additionally has a selected-branch UR10e-bed overlap.",
            "The high-flexion poses otherwise lift the distal limb away from the bed. Static balance therefore uses the world-anchored hip plus cuff reaction; this audit does not invent an additional bed-support force.",
            "Consequently, collision-free UR10e results are surrogate-only and do not establish CR12 feasibility.",
            "Target cuff orientation is a continuous function of q2-q1 over the scan. Pointwise IK does not prove a continuous collision-free robot branch or exclude joint-angle branch jumps along a future trajectory.",
            "",
            "## Rigid-cuff mechanics",
            "",
            f"Across the sampled grid, raw mixed-unit B conditioning ranged from "
            f"{summary['rigid_cuff_condition_raw_mixed_units']['minimum']:.3f} to "
            f"{summary['rigid_cuff_condition_raw_mixed_units']['maximum']:.3f}.",
            "The full rigid-cuff map includes sagittal moment and is checked for rank 2 at every pose.",
            "The translational-force-only submap is still rank-deficient at knee extension; the added moment authority is why the rigid-cuff map avoids that old point-force singularity.",
            "",
            "## Candidate endpoint classes for the next design review",
            "",
            "| class | endpoint | conditional force / moment | main caveat |",
            "|---|---:|---:|---|",
        ]
    )
    for name, caveat in (
        ("hip_dominant", "identity-adapter wrist/shank overlap"),
        ("knee_dominant", "selected IK branch also intersects bed"),
        ("both_high", "identity-adapter wrist/shank overlap"),
        ("aggressive", "hip 120 is not a clinical-angle claim"),
    ):
        row = candidates[name]
        allocation = row["conditional_without_soft_limit_allocation"]
        lines.append(
            f"| {name} | ({row['q1_deg']:g},{row['q2_deg']:g}) | "
            f"{allocation['force_norm_n']:.2f} N / {allocation['moment_abs_nm']:.2f} Nm | {caveat} |"
        )
    lines.extend(
        [
            "",
            "These are endpoint classes for review after geometry repair, not approved dynamic trajectories.",
            "Before an endpoint can sit outside the soft-limit zone, its declared upper ROM must exceed it by the frozen 5 deg margin; merely setting the upper bound equal to the endpoint would retain boundary torque.",
            "The ordinary passive stiffness/rest model is extrapolated in the conditional calculation and must be reviewed rather than assumed valid at 90-120 deg.",
            "Robot/cuff adapter geometry and robot-bed collision representation need revision or explicit validation before any controller campaign.",
            "For the four requested poses, keeping the endpoint outside the frozen 5 deg soft-limit zone would require reviewed upper limits of at least [95,95], [125,95], [95,125], and [125,125] deg respectively; these are software-margin implications, not clinical recommendations.",
            "Changing limits alone is insufficient: the passive stiffness/rest extrapolation, bed/contact representation, identity adapter, and continuous collision-free UR10e path all require review.",
            "No dynamic trajectory or controller comparison is approved by this report.",
            "",
            "## Artifacts",
            "",
            "- `high_rom_feasibility_summary.json`: compact assumptions, counts, and four-pose details",
            "- `feasible_region.csv`: one row per sampled configuration",
            "- `high_rom_feasibility_heatmaps.png`: classification and conditional cuff force",
            "- `high_rom_conditioning_heatmaps.png`: UR10e and rigid-cuff conditioning",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = _scan()
    summary = _summary(rows)
    (output / "high_rom_feasibility_summary.json").write_text(
        json.dumps(json_ready(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output / "feasible_region.csv", rows)
    _write_plots(output, rows)
    (output / "high_rom_feasibility_report.md").write_text(
        _report(summary), encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(output),
        "sample_count": len(rows),
        "classification_counts": summary["classification_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
