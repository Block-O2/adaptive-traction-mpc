"""Aggregate existing formal full-3D startup traces as development diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _first(t: np.ndarray, mask: np.ndarray) -> float | None:
    found = np.flatnonzero(mask)
    return None if len(found) == 0 else float(t[int(found[0])])


def _median(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return None if not values else float(np.median(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    for path in sorted(args.formal_root.glob("*/continual_adaptive")):
        if not (path / "summary.json").exists():
            rows.append({"case_key": path.parent.name,
                         "status": "PRESERVED_PRESTEP_RUNNER_EXCEPTION"})
            continue
        summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
        config = json.loads((path / "config_snapshot.json").read_text(encoding="utf-8"))
        with np.load(path / "trace.npz", allow_pickle=False) as trace:
            comm = trace["stage"] == "COMMISSIONING"
            task = trace["stage"] == "TASK"
            t = trace["time_s"][comm]
            qref = np.rad2deg(trace["reference_q_rad"][comm])
            true = np.rad2deg(trace["evaluation_only_human_state_rad_rad_s"][comm])
            estimated = np.rad2deg(trace["estimated_human_state_rad_rad_s"][comm])
            contact = trace["shank_bed_contact_evaluation_only"][comm]
            fitted_estimated = np.rad2deg(trace["estimated_human_state_rad_rad_s"][task][0])
            fitted_true = np.rad2deg(trace["evaluation_only_human_state_rad_rad_s"][task][0])
        q_tol = np.asarray(config["completion_angle_tolerance_deg"], dtype=float)
        q_error = np.abs(true[:, :2] - qref)
        prior_half_second_index = int(np.argmin(np.abs(t - (float(t[-1]) - 0.5))))
        endpoint_error_half_second_before = float(np.max(q_error[prior_half_second_index]))
        endpoint_error_at_handoff = float(np.max(q_error[-1]))
        contact_time = _first(t, contact)
        divergence_time = _first(t, np.any(q_error > q_tol, axis=1))
        if contact_time is None or divergence_time is None:
            ordering = "missing_contact_or_divergence"
        elif divergence_time + 1e-10 < contact_time:
            ordering = "tracking_divergence_before_contact"
        elif contact_time + 1e-10 < divergence_time:
            ordering = "contact_before_tracking_divergence"
        else:
            ordering = "same_5ms_boundary"
        sample_times = [float(item["time_s"]) for item in
                        summary["commissioning"]["aligned_update_history"]]
        overlapping_samples = sum(bool(np.any(contact[(t >= sample_time - 0.020 - 1e-10)
                                                     & (t <= sample_time + 1e-10)]))
                                  for sample_time in sample_times)
        row = {
            "case_key": path.parent.name,
            "status": summary["status"],
            "abort_reason": summary["abort_reason"],
            "initial_5ms_contact": bool(contact[0]),
            "first_contact_5ms_s": contact_time,
            "first_true_tracking_error_over_existing_1deg_s": divergence_time,
            "event_order": ordering,
            "commissioning_contact_boundary_count": int(contact.sum()),
            "commissioning_20ms_update_count": len(sample_times),
            "commissioning_20ms_update_intervals_overlapping_5ms_contact": overlapping_samples,
            "initial_estimate_minus_true_max_abs_deg": float(np.max(np.abs(estimated[0, :2]-true[0, :2]))),
            "prefit_true_minus_reference_max_abs_deg": float(np.max(np.abs(true[-1, :2]-qref[-1]))),
            "reference_error_half_second_before_handoff_deg": endpoint_error_half_second_before,
            "reference_error_at_handoff_deg": endpoint_error_at_handoff,
            "reference_error_change_last_half_second_deg": (
                endpoint_error_at_handoff - endpoint_error_half_second_before),
            "true_velocity_at_handoff_max_abs_deg_s": float(np.max(np.abs(true[-1, 2:]))),
            "prefit_estimate_minus_true_max_abs_deg": float(np.max(np.abs(estimated[-1, :2]-true[-1, :2]))),
            "fitted_estimate_minus_prefit_max_abs_deg": float(np.max(np.abs(fitted_estimated[:2]-estimated[-1, :2]))),
            "fitted_estimate_minus_true_max_abs_deg": float(np.max(np.abs(fitted_estimated[:2]-fitted_true[:2]))),
            "postfit_estimated_start_inside_angle_tolerance": bool(np.all(
                np.abs(fitted_estimated[:2]-qref[-1]) <= q_tol)),
            "physical_true_start_inside_angle_tolerance": bool(np.all(
                np.abs(fitted_true[:2]-qref[-1]) <= q_tol)),
            "geometry_fit_condition_number_regularized":
                summary["commissioning"]["geometry_fit"]["condition_number"],
            "geometry_fit_accepted": summary["commissioning"]["geometry_fit"]["accepted"],
        }
        rows.append(row)
    physical = [row for row in rows if row["status"] != "PRESERVED_PRESTEP_RUNNER_EXCEPTION"]
    handoff = [row for row in physical if str(row["abort_reason"]).startswith(
        "COMMISSIONING_HANDOFF_NOT_SETTLED")]
    aggregate = {
        "schema": "full3d_startup_dgn_v1_existing_formal_as_development_diagnostics",
        "case_count": len(rows), "physical_case_count": len(physical),
        "prestep_exception_case_count": len(rows) - len(physical),
        "handoff_failure_count": len(handoff),
        "physical_initial_contact_count": sum(row["initial_5ms_contact"] for row in physical),
        "physical_any_commissioning_contact_count": sum(
            row["commissioning_contact_boundary_count"] > 0 for row in physical),
        "event_order_counts": {key: sum(row["event_order"] == key for row in physical)
                               for key in sorted({row["event_order"] for row in physical})},
        "handoff_median_prefit_true_reference_max_abs_deg": _median(
            handoff, "prefit_true_minus_reference_max_abs_deg"),
        "handoff_median_prefit_estimate_true_max_abs_deg": _median(
            handoff, "prefit_estimate_minus_true_max_abs_deg"),
        "handoff_median_model_switch_estimate_jump_deg": _median(
            handoff, "fitted_estimate_minus_prefit_max_abs_deg"),
        "handoff_physical_start_inside_angle_tolerance_count": sum(
            row["physical_true_start_inside_angle_tolerance"] for row in handoff),
        "handoff_postfit_estimated_start_inside_angle_tolerance_count": sum(
            row["postfit_estimated_start_inside_angle_tolerance"] for row in handoff),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in aggregate.items() if key != "rows"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
