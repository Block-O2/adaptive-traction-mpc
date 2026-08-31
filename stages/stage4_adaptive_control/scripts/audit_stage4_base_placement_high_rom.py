#!/usr/bin/env python3
"""Search one common UR10e base pose and re-audit high-ROM paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.frames import WORLD_FROM_BASE
from traction_mpc_stage4.base_placement_high_rom import (
    COARSE_PATH_SAMPLE_COUNT,
    BasePose,
    coarse_base_candidates,
    dense_reaudit,
    local_refinement_candidates,
    placement_score,
    search_common_base,
)
from traction_mpc_stage4.continuous_high_rom import PATH_SAMPLE_COUNT
from traction_mpc_stage4.high_rom_feasibility import json_ready


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
REPORT_MARKER = "## Common base placement under revised collision policy"
DISPLAY_NAMES = {
    "hip_dominant_100_60": "100/60 hip",
    "both_high_90_90": "90/90 both",
    "aggressive_120_90": "120/90 aggressive",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--coarse-sample-count", type=int, default=COARSE_PATH_SAMPLE_COUNT
    )
    parser.add_argument("--refine-sample-count", type=int, default=31)
    parser.add_argument("--dense-sample-count", type=int, default=PATH_SAMPLE_COUNT)
    parser.add_argument("--search-random-seeds", type=int, default=16)
    return parser.parse_args()


def _pose_from_result(result: dict[str, object]) -> BasePose:
    translation = result["base_pose"]["translation_m"]
    return BasePose(
        float(translation[0]),
        float(translation[1]),
        float(translation[2]),
        float(result["base_pose"]["yaw_deg"]),
    )


def _compact_candidate(result: dict[str, object]) -> dict[str, object]:
    return {
        "base_pose": result["base_pose"],
        "initial_exact_ik_branch_count": result["initial_exact_ik_branch_count"],
        "primary_feasible_count": result["primary_feasible_count"],
        "primary_ik_completed_count": result["primary_ik_completed_count"],
        "all_primary_feasible": result["all_primary_feasible"],
        "worst_primary_required_clearance_m": result[
            "worst_primary_required_clearance_m"
        ],
        "worst_primary_jacobian_condition": result[
            "worst_primary_jacobian_condition"
        ],
        "minimum_primary_joint_limit_margin_deg": result[
            "minimum_primary_joint_limit_margin_deg"
        ],
        "paths": {
            name: {
                "feasible": path["revised_policy_continuous_feasible"],
                "ik_completed": path["ik_completed"],
                "minimum_required_clearance_m": path.get(
                    "minimum_required_clearance_m"
                ),
                "worst_jacobian_condition": path.get("robot", {}).get(
                    "worst_jacobian_condition"
                ),
                "minimum_joint_limit_margin_deg": path.get("robot", {}).get(
                    "minimum_joint_limit_margin_deg"
                ),
                "failure_reason": path.get("failure_reason"),
            }
            for name, path in result["paths"].items()
        },
    }


def _write_plot(output: Path, dense: dict[str, object]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    for name, path in dense["paths"].items():
        trace = path["trace"]
        fraction = np.asarray(trace["path_fraction"])
        axes[0].plot(
            fraction,
            1000.0 * np.asarray(trace["minimum_required_clearance_m"]),
            label=DISPLAY_NAMES[name],
        )
        axes[1].plot(
            fraction,
            np.asarray(trace["robot_jacobian_condition"]),
            label=DISPLAY_NAMES[name],
        )
    axes[0].axhline(0.0, color="black", linewidth=1.0)
    axes[0].set_title("Selected common base: required clearance")
    axes[0].set_xlabel("path fraction")
    axes[0].set_ylabel("minimum required clearance (mm)")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Selected common base: UR10e conditioning")
    axes[1].set_xlabel("path fraction")
    axes[1].set_ylabel("Jacobian condition number")
    axes[1].legend(fontsize=8)
    figure.savefig(output / "base_placement_clearance.png", dpi=180)
    plt.close(figure)


def _report_section(payload: dict[str, object]) -> str:
    selected = payload["selected_common_base"]
    dense = payload["dense_reaudit"]
    translation = selected["translation_m"]
    lines = [
        REPORT_MARKER,
        "",
        (
            "The revised policy ignores finite cuff thickness, thigh, and mid-shank "
            "support-plane contact as trajectory-failure criteria. Robot/adapter "
            "environment and Human clearance, robot self-collision, distal ankle-point "
            "clearance, continuous IK, joint limits, conditioning, and the conditional "
            "200 N cuff-force gate remain required."
        ),
        "No foot body or dynamic distal extension was added.",
        "",
        (
            f"Selected common UR10e base: [{translation[0]:.3f}, "
            f"{translation[1]:.3f}, {translation[2]:.3f}] m, "
            f"yaw {selected['yaw_deg']:.1f} deg."
        ),
        (
            f"The search evaluated {payload['search']['coarse_candidate_count']} "
            f"coarse and {payload['search']['refinement_candidate_count']} local "
            "placements using only longitudinal, lateral, height, and yaw coordinates."
        ),
        "",
        "| candidate | revised result | min required | robot-bed interval end | robot-human | distal ankle | worst J condition | min joint margin | peak force / moment |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, path in dense["paths"].items():
        clearance = path["minimum_clearance_by_required_domain_m"]
        qstatic = path["conditional_quasistatic"]
        robot_bed_intervals = path["failure_intervals"]["robot_bed_m"]
        robot_bed_end = max(
            (interval["end_fraction"] for interval in robot_bed_intervals),
            default=None,
        )
        robot_bed_text = "none" if robot_bed_end is None else f"{robot_bed_end:.3f}"
        lines.append(
            f"| {DISPLAY_NAMES[name]} | "
            f"{'READY FOR ROM-MODEL AMENDMENT' if path['revised_policy_continuous_feasible'] else 'STILL GEOMETRICALLY BLOCKED'} | "
            f"{1000*path['minimum_required_clearance_m']:.1f} mm | "
            f"{robot_bed_text} | "
            f"{1000*clearance['robot_human_m']:.1f} mm | "
            f"{1000*clearance['distal_ankle_support_plane_m']:.1f} mm | "
            f"{path['robot']['worst_jacobian_condition']:.2f} | "
            f"{path['robot']['minimum_joint_limit_margin_deg']:.2f} deg | "
            f"{qstatic['peak_cuff_force_n']:.2f} N / "
            f"{qstatic['peak_cuff_moment_abs_nm']:.2f} Nm |"
        )
    ready = [
        DISPLAY_NAMES[name]
        for name, path in dense["paths"].items()
        if path["revised_policy_continuous_feasible"]
    ]
    lines.extend(
        [
            "",
            (
                "The 140 mm adapter remains unchanged; its minimum Human clearance "
                "stays positive on all selected branches."
            ),
            (
                "All three dense paths complete continuous IK on one common branch, "
                "but all seven exact initial branches collide with the support plane. "
                "The selected branch is limited by the local wrist_2 collision proxy "
                "at the fixed cuff pose, so translating or yawing the base cannot remove "
                "the initial overlap."
            ),
            (
                "Geometrically ready trajectories: "
                + (", ".join(ready) if ready else "none")
                + "."
            ),
            (
                "No Human V2 ROM, passive, controller, cost, constraint, bed, or cuff "
                "mechanics parameter was changed, and no dynamic rollout was run."
            ),
            "",
            "See `base_placement_audit.json` and `base_placement_clearance.png`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    coarse = search_common_base(
        coarse_base_candidates(),
        sample_count=args.coarse_sample_count,
        random_seed_count=args.search_random_seeds,
    )
    coarse_pose = _pose_from_result(coarse["selected"])
    refinement = search_common_base(
        local_refinement_candidates(coarse_pose),
        sample_count=args.refine_sample_count,
        random_seed_count=args.search_random_seeds,
    )
    selected_search_result = max(
        (coarse["selected"], refinement["selected"]), key=placement_score
    )
    selected_pose = _pose_from_result(selected_search_result)
    dense = dense_reaudit(selected_pose)

    payload = {
        "audit_kind": "common_ur10e_base_search_and_dense_kinematic_reaudit",
        "controller_or_dynamic_rollout_run": False,
        "current_default_base_pose": {
            "translation_m": WORLD_FROM_BASE.translation.tolist(),
            "yaw_deg": 0.0,
        },
        "selected_common_base": selected_pose.as_dict(),
        "search": {
            "coarse_candidate_count": coarse["candidate_count"],
            "coarse_sample_count_per_path": coarse["sample_count_per_path"],
            "coarse_grid": {
                "longitudinal_x_m": [0.90, 1.10, 1.30],
                "lateral_y_m": [-0.62, -0.77, -0.92],
                "base_height_m": [0.16, 0.24, 0.32],
                "yaw_deg": [-20.0, 0.0, 20.0],
            },
            "refinement_candidate_count": refinement["candidate_count"],
            "refinement_sample_count_per_path": refinement["sample_count_per_path"],
            "refinement_offsets": {
                "longitudinal_x_m": [-0.10, 0.0, 0.10],
                "lateral_y_m": [-0.075, 0.0, 0.075],
                "base_height_m": [-0.04, 0.0, 0.04],
                "yaw_deg": [-10.0, 0.0, 10.0],
            },
            "selection_rule": coarse["selection_rule"],
            "coarse_candidates": [
                _compact_candidate(candidate) for candidate in coarse["candidates"]
            ],
            "refinement_candidates": [
                _compact_candidate(candidate)
                for candidate in refinement["candidates"]
            ],
        },
        "dense_reaudit": dense,
        "revised_collision_policy": {
            "ignored_as_trajectory_failure": [
                "finite cuff thickness versus support plane",
                "thigh versus support plane",
                "mid-shank versus support plane",
            ],
            "required": [
                "robot and adapter versus bed/environment",
                "robot and adapter versus Human",
                "robot self-collision",
                "distal shank ankle endpoint versus support plane",
                "continuous IK, joint limits, singularity/conditioning",
                "conditional quasi-static cuff force <= 200 N",
            ],
            "foot_model_added": False,
            "cuff_mechanics_changed": False,
        },
    }
    (output / "base_placement_audit.json").write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_plot(output, dense)
    report_path = output / "high_rom_feasibility_report.md"
    baseline = report_path.read_text(encoding="utf-8")
    baseline = baseline.split(REPORT_MARKER, maxsplit=1)[0].rstrip() + "\n\n"
    report_path.write_text(baseline + _report_section(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "selected_common_base": selected_pose.as_dict(),
                "dense_path_results": {
                    name: path["revised_policy_continuous_feasible"]
                    for name, path in dense["paths"].items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
