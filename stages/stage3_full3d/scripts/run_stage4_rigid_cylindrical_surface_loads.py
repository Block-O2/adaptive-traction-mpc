from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import SHANK_RADIUS_M, SLEEVE_OUTER_RADIUS_M
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
    cylindrical_surface_load_metrics,
)


REGISTERED_LENGTHS_M = (0.060, 0.080, 0.100, 0.120)


def _trace_invariance(
    baseline_path: Path,
    candidate: dict[str, np.ndarray],
) -> dict[str, Any]:
    with np.load(baseline_path) as baseline_archive:
        baseline_keys = set(baseline_archive.files)
        candidate_keys = set(candidate)
        common = sorted(baseline_keys & candidate_keys)
        per_array: dict[str, dict[str, Any]] = {}
        overall = 0.0
        all_exact = baseline_keys == candidate_keys
        for name in common:
            baseline = baseline_archive[name]
            current = np.asarray(candidate[name])
            same_shape = baseline.shape == current.shape
            exact = same_shape and np.array_equal(baseline, current)
            all_exact = all_exact and exact
            maximum = (
                float(
                    np.max(
                        np.abs(current.astype(float) - baseline.astype(float))
                    )
                )
                if same_shape and baseline.size
                else float("inf")
            )
            overall = max(overall, maximum)
            per_array[name] = {
                "same_shape": same_shape,
                "exactly_equal": exact,
                "maximum_absolute_difference": maximum,
            }
    return {
        "baseline_trace": str(baseline_path),
        "same_key_set": baseline_keys == candidate_keys,
        "all_arrays_bitwise_equal": all_exact,
        "overall_maximum_absolute_trace_difference": overall,
        "per_array": per_array,
    }


def _resultant_metrics(force: np.ndarray, moment: np.ndarray) -> dict[str, Any]:
    force_norm = np.linalg.norm(force, axis=1)
    moment_norm = np.linalg.norm(moment, axis=1)
    return {
        "peak_force_norm_n": float(np.max(force_norm)),
        "rms_force_norm_n": float(np.sqrt(np.mean(force_norm**2))),
        "peak_abs_force_component_n": np.max(np.abs(force), axis=0).tolist(),
        "peak_moment_norm_nm": float(np.max(moment_norm)),
        "rms_moment_norm_nm": float(np.sqrt(np.mean(moment_norm**2))),
        "peak_abs_moment_component_nm": np.max(np.abs(moment), axis=0).tolist(),
        "peak_abs_sagittal_moment_my_nm": float(np.max(np.abs(moment[:, 1]))),
        "peak_off_axis_moment_mx_mz_norm_nm": float(
            np.max(np.linalg.norm(moment[:, [0, 2]], axis=1))
        ),
    }


def _length_row(length_m: float, wrench: np.ndarray) -> dict[str, Any]:
    config = CylindricalSurfaceConfig(length_m, radius_m=SHANK_RADIUS_M)
    model = CylindricalSurfaceLoadModel(config)
    decomposition = model.decompose(wrench)
    return {
        "cuff_length_mm": 1000.0 * length_m,
        "contact_surface_radius_mm": 1000.0 * config.radius_m,
        "axial_offsets_mm": (1000.0 * config.axial_offsets_m).tolist(),
        "circumferential_angles_deg": np.degrees(
            config.circumferential_angles_rad
        ).tolist(),
        "rank": model.rank,
        "nullity": model.nullity,
        "surface_loads": cylindrical_surface_load_metrics(
            decomposition, config
        ),
    }


def _add_scaling(rows: list[dict[str, Any]]) -> None:
    baseline = rows[0]["surface_loads"]["maximum_local_force_n"]
    for row in rows:
        maximum = row["surface_loads"]["maximum_local_force_n"]
        row["maximum_local_force_relative_to_60mm"] = maximum / baseline
        row["maximum_local_force_reduction_vs_60mm_percent"] = (
            100.0 * (baseline - maximum) / baseline
        )


def _format_four(values: list[float]) -> str:
    return "/".join(f"{value:.2f}" for value in values)


def _write_summary(output_dir: Path, comparison: dict[str, Any]) -> None:
    rows = comparison["length_sweep"]
    table = [
        "| Lc (mm) | max local (N) | patch peak range (N) | patch RMS range (N) | prox/dist row sum peak (N) | circumferential sector sum peaks (N) | concentration at max load | reduction vs 60 mm |",
        "|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for row in rows:
        metrics = row["surface_loads"]
        peaks = np.asarray(
            metrics["peak_force_norm_n_per_patch_axial_by_circumferential"]
        )
        rms = np.asarray(
            metrics["rms_force_norm_n_per_patch_axial_by_circumferential"]
        )
        table.append(
            f"| {row['cuff_length_mm']:.0f} | "
            f"{metrics['maximum_local_force_n']:.2f} | "
            f"{np.min(peaks):.2f}-{np.max(peaks):.2f} | "
            f"{np.min(rms):.2f}-{np.max(rms):.2f} | "
            f"{metrics['peak_proximal_row_sum_local_norm_n']:.2f}/"
            f"{metrics['peak_distal_row_sum_local_norm_n']:.2f} | "
            f"{_format_four(metrics['peak_circumferential_sector_sum_local_norm_n'])} | "
            f"{metrics['load_concentration_at_maximum_local_force']:.3f} | "
            f"{row['maximum_local_force_reduction_vs_60mm_percent']:.1f}% |"
        )
    invariant = comparison["rigid_plant_invariance"]
    resultant = comparison["resultant_rigid_cuff_wrench"]
    rank = comparison["surface_model"]["rank_analysis"]
    text = (
        "# Stage 4 rigid cylindrical-surface cuff load audit\n\n"
        "Engineering post-processing only. The validated rigid weld, Architecture A, "
        "controller, estimator, continuous 23 s trajectory, and safety settings are unchanged.\n\n"
        f"Rigid rerun completed: `{comparison['rigid_run']['completed']}`; all trace arrays "
        f"bitwise equal to baseline: `{invariant['all_arrays_bitwise_equal']}`; maximum "
        f"absolute difference: `{invariant['overall_maximum_absolute_trace_difference']:.3g}`.\n\n"
        f"Wrench map rank/nullity: `{rank['wrench_map_rank']}/{rank['wrench_map_nullity']}`. "
        "All six resultant components are reproduced by 16 translational-force patches; "
        "no direct patch moment is used.\n\n"
        f"Common resultant: peak/RMS |F| `{resultant['peak_force_norm_n']:.3f}/"
        f"{resultant['rms_force_norm_n']:.3f} N`; peak/RMS |M| "
        f"`{resultant['peak_moment_norm_nm']:.3f}/"
        f"{resultant['rms_moment_norm_nm']:.3f} N m`; peak |My| "
        f"`{resultant['peak_abs_sagittal_moment_my_nm']:.3f} N m`.\n\n"
        + "\n".join(table)
        + "\n\nPatch peak/RMS 4x4 matrices and full axial/circumferential distributions "
        "are in `comparison_summary.json`. These are equivalent surface forces, not pressure "
        "or clinical metrics.\n"
    )
    (output_dir / "summary.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-trace", type=Path, required=True)
    args = parser.parse_args()

    case = architecture_comparison_sensor_cases()[1]
    summary, trace = run_sensor_realism_case(
        case,
        duration_s=CONTINUOUS_TEACHING_DURATION_S,
        estimator_architecture="integral_minimal",
        result_case_name="rigid_cylindrical_surface_invariance_run",
        reference_fn=continuous_teaching_reference,
        trajectory_label="stage4_continuous_c2_high_flexion_23s",
        trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
    )
    save_sensor_case(args.output_dir, summary, trace)

    force = trace["cuff_force_local_n_god_view"]
    moment = trace["cuff_moment_local_nm_god_view"]
    wrench = np.concatenate((force, moment), axis=1)
    rows = [_length_row(length, wrench) for length in REGISTERED_LENGTHS_M]
    _add_scaling(rows)
    true_human, _ = registered_cold_start_perturbed_human()
    representative = CylindricalSurfaceConfig(0.080, radius_m=SHANK_RADIUS_M)
    representative_model = CylindricalSurfaceLoadModel(representative)
    comparison = {
        "evidence_category": "stage4_rigid_cylindrical_surface_load_engineering",
        "active_plant": "validated_single_six_constraint_rigid_weld",
        "cuff_body_or_new_dof_added": False,
        "surface_model_role": "god_view_evaluation_postprocessing_only",
        "controller_estimator_local_patch_load_access": False,
        "same_rigid_run_reused_for_all_lengths": True,
        "single_variable_in_sweep": "postprocessed axial cuff length",
        "fixed_cuff_center_sc_m_god_view": true_human.sleeve_center_m,
        "fixed_contact_surface_radius_m": SHANK_RADIUS_M,
        "visual_outer_radius_m": SLEEVE_OUTER_RADIUS_M,
        "human_case": summary["true_human_case"],
        "measurement_case": summary["measurement_model"]["name"],
        "trajectory": summary["trajectory"],
        "rigid_run": {
            "completed": summary["mechanically_completed_requested_duration"],
            "duration_s": summary["completed_duration_s"],
            "termination": summary["termination_reason"],
            "tracking": summary["tracking"],
            "robot": summary["robot"],
            "geometry_identifier": summary["geometry_identifier"],
            "dynamic_identifier": summary["dynamic_identifier"],
            "events": summary["events"],
        },
        "rigid_plant_invariance": _trace_invariance(args.baseline_trace, trace),
        "resultant_rigid_cuff_wrench": _resultant_metrics(force, moment),
        "surface_model": {
            "representative_config": representative.as_dict(),
            "rank_analysis": representative_model.diagnostics(),
            "interpretation_limit": (
                "equivalent translational surface loads only; not pressure, comfort, friction, slip, soft tissue, or clinical safety"
            ),
            "provenance_only_models": [
                "collinear_four_point_line_load",
                "rejected_zero_preload_explicit_penalty_spring",
            ],
        },
        "length_sweep": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "README.md").write_text(
        "# Registered engineering command\n\n"
        "```bash\n"
        "PYTHONPATH=src conda run -n mpc_learn python "
        "scripts/run_stage4_rigid_cylindrical_surface_loads.py \\\n"
        "  --output-dir results/stage4_rigid_cylindrical_surface_loads_engineering \\\n"
        "  --baseline-trace results/stage4_continuous_trajectory_engineering/"
        "continuous_perturbed_human_one_shot_trace.npz\n"
        "```\n\n"
        "One unchanged rigid-weld rollout is compared with the registered trace. "
        "The four lengths are evaluation-only decompositions of that same resultant wrench.\n",
        encoding="utf-8",
    )
    _write_summary(args.output_dir, comparison)


if __name__ == "__main__":
    main()
