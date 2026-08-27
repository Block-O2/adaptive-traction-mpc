from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    FiniteSurfaceConfig,
    FiniteSurfaceLoadModel,
    surface_load_metrics,
)


REGISTERED_LENGTHS_M = (0.060, 0.080, 0.100, 0.120)


def _trace_invariance(
    baseline_path: Path,
    candidate: dict[str, np.ndarray],
) -> dict[str, Any]:
    baseline_archive = np.load(baseline_path)
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
            float(np.max(np.abs(current.astype(float) - baseline.astype(float))))
            if same_shape and baseline.size
            else float("inf")
        )
        overall = max(overall, maximum)
        per_array[name] = {
            "same_shape": same_shape,
            "exactly_equal": exact,
            "maximum_absolute_difference": maximum,
        }
    baseline_archive.close()
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


def _length_row(
    length_m: float,
    wrench: np.ndarray,
    rigid_summary: dict[str, Any],
) -> dict[str, Any]:
    config = FiniteSurfaceConfig(length_m)
    model = FiniteSurfaceLoadModel(config)
    decomposition = model.decompose(wrench)
    return {
        "cuff_length_mm": 1000.0 * length_m,
        "patch_offsets_mm": (1000.0 * config.patch_offsets_m).tolist(),
        "completed": rigid_summary["mechanically_completed_requested_duration"],
        "duration_s": rigid_summary["completed_duration_s"],
        "termination": rigid_summary["termination_reason"],
        "surface_loads": surface_load_metrics(decomposition),
        "tracking": rigid_summary["tracking"],
        "robot": rigid_summary["robot"],
        "geometry_identifier": rigid_summary["geometry_identifier"],
        "dynamic_identifier": rigid_summary["dynamic_identifier"],
        "events": rigid_summary["events"],
    }


def _write_summary(output_dir: Path, comparison: dict[str, Any]) -> None:
    rows = comparison["length_sweep"]
    table = [
        "| Lc (mm) | complete | max local (N) | patch peak norms (N) | patch RMS norms (N) | concentration max/mean | axial Mx residual peak (N m) |",
        "|---:|:---:|---:|---|---|---:|---:|",
    ]
    for row in rows:
        metrics = row["surface_loads"]
        peaks = "/".join(f"{value:.2f}" for value in metrics["peak_force_norm_n_per_patch"])
        rms = "/".join(f"{value:.2f}" for value in metrics["rms_force_norm_n_per_patch"])
        table.append(
            f"| {row['cuff_length_mm']:.0f} | {row['completed']} | "
            f"{metrics['maximum_local_force_n']:.2f} | {peaks} | {rms} | "
            f"{metrics['peak_load_concentration_max_over_mean']:.3f} | "
            f"{metrics['peak_unachievable_axial_moment_residual_nm']:.3f} |"
        )
    invariant = comparison["rigid_plant_invariance"]
    resultant = comparison["resultant_rigid_cuff_wrench"]
    text = (
        "# Stage 4 rigid finite-surface cuff load audit\n\n"
        "Engineering post-processing only: the validated rigid weld, Architecture A, "
        "controller, estimator, continuous 23 s trajectory, and safety settings are unchanged.\n\n"
        f"Rigid rerun completed: `{comparison['rigid_run']['completed']}`; trace arrays exactly "
        f"match the registered baseline: `{invariant['all_arrays_bitwise_equal']}`; maximum "
        f"absolute trace difference: `{invariant['overall_maximum_absolute_trace_difference']:.3g}`.\n\n"
        f"Common resultant for every length: peak |F| `{resultant['peak_force_norm_n']:.3f} N`, "
        f"peak |My| `{resultant['peak_abs_sagittal_moment_my_nm']:.3f} N m`, peak off-axis "
        f"moment norm `{resultant['peak_off_axis_moment_mx_mz_norm_nm']:.3f} N m`.\n\n"
        + "\n".join(table)
        + "\n\nThe four collinear translational patches span only "
        "[Fx,Fy,Fz,My,Mz]. Mx is reported as an unachievable residual; no patch moment is invented.\n"
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
        result_case_name="rigid_surface_invariance_run",
        reference_fn=continuous_teaching_reference,
        trajectory_label="stage4_continuous_c2_high_flexion_23s",
        trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
    )
    save_sensor_case(args.output_dir, summary, trace)

    force = trace["cuff_force_local_n_god_view"]
    moment = trace["cuff_moment_local_nm_god_view"]
    wrench = np.concatenate((force, moment), axis=1)
    rows = [_length_row(length, wrench, summary) for length in REGISTERED_LENGTHS_M]
    comparison = {
        "evidence_category": "stage4_rigid_finite_surface_load_engineering",
        "active_plant": "validated_single_six_constraint_rigid_weld",
        "surface_model_role": "god_view_evaluation_postprocessing_only",
        "controller_estimator_surface_load_access": False,
        "single_variable_in_sweep": "postprocessed finite surface patch lever arms",
        "same_rigid_run_reused_for_all_lengths": True,
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
            "representative_config": FiniteSurfaceConfig(0.080).as_dict(),
            "rank_analysis": FiniteSurfaceLoadModel(
                FiniteSurfaceConfig(0.080)
            ).diagnostics(),
            "interpretation_limit": (
                "equivalent translational surface loads only; not pressure, strap tension, friction, soft tissue, or slip"
            ),
        },
        "length_sweep": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "README.md").write_text(
        "# Registered command\n\n"
        "```bash\n"
        "PYTHONPATH=src conda run -n mpc_learn python "
        "scripts/run_stage4_rigid_surface_loads.py \\\n"
        "  --output-dir results/stage4_rigid_surface_loads_engineering \\\n"
        "  --baseline-trace results/stage4_continuous_trajectory_engineering/"
        "continuous_perturbed_human_one_shot_trace.npz\n"
        "```\n\n"
        "This command reruns one unchanged rigid-weld trajectory, verifies it against "
        "the registered trace, then evaluates four cuff lengths without feeding local "
        "loads back to simulation, the estimator, or the controller.\n",
        encoding="utf-8",
    )
    _write_summary(args.output_dir, comparison)


if __name__ == "__main__":
    main()
