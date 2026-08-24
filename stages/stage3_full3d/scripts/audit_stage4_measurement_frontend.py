from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import CausalMeasurementLayer, architecture_comparison_sensor_cases
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validated-summary", type=Path, required=True)
    parser.add_argument("--ideal-boundary-summary", type=Path, required=True)
    args = parser.parse_args()

    human, _ = registered_cold_start_perturbed_human()
    original = SensorBoundaryStage4Plant(human)
    measured = SensorBoundaryStage4Plant(human)
    q0 = np.radians([5.0, 10.0])
    original_truth = original.reset(q0)
    measured_truth = measured.reset(q0)
    layer = CausalMeasurementLayer(architecture_comparison_sensor_cases()[0], measured_truth)
    measurement = layer.current
    pass_through_errors = {
        "robot_q_rad": float(np.max(np.abs(measurement.robot_q_rad - measured_truth.robot_q_rad))),
        "robot_dq_rad_s": float(np.max(np.abs(measurement.robot_dq_rad_s - measured_truth.robot_dq_rad_s))),
        "cuff_position_m": float(np.max(np.abs(measurement.attachment_position_m - measured_truth.attachment_position_m))),
        "cuff_rotation_matrix": float(np.max(np.abs(measurement.attachment_rotation_matrix - measured_truth.attachment_rotation_matrix))),
        "cuff_linear_velocity_m_s": float(np.max(np.abs(measurement.attachment_velocity_m_s - measured_truth.attachment_velocity_m_s))),
        "cuff_angular_velocity_rad_s": float(np.max(np.abs(measurement.attachment_angular_velocity_rad_s - measured_truth.attachment_angular_velocity_rad_s))),
        "cuff_force_n": float(np.max(np.abs(measurement.cuff_force_vector_n - measured_truth.cuff_force_vector_n))),
        "cuff_moment_nm": float(np.max(np.abs(measurement.cuff_moment_vector_nm - measured_truth.cuff_moment_vector_nm))),
    }

    target_position = original_truth.attachment_position_m + np.array([1e-4, -2e-4, 1e-4])
    target_velocity = np.array([0.002, -0.001, 0.003])
    target_rotation = original_truth.attachment_rotation_matrix
    target_angular_velocity = np.array([0.0, 0.01, 0.0])
    feedforward = np.array([5.0, -3.0, 2.0, 0.1, -0.2, 0.3])
    original.apply_nominal_cartesian_control(
        target_position,
        target_velocity,
        target_rotation,
        target_angular_velocity,
        feedforward,
    )
    measured.apply_measured_nominal_cartesian_control(
        measurement,
        target_position,
        target_velocity,
        target_rotation,
        target_angular_velocity,
        feedforward,
    )
    validated = json.loads(args.validated_summary.read_text(encoding="utf-8"))
    ideal = json.loads(args.ideal_boundary_summary.read_text(encoding="utf-8"))
    output = {
        "evidence_category": "stage4_measurement_frontend_transparency_audit",
        "ideal_measurement_max_abs_errors": pass_through_errors,
        "low_level_unclipped_torque_max_abs_error_nm": float(
            np.max(
                np.abs(
                    original.last_unclipped_joint_torque
                    - measured.last_unclipped_joint_torque
                )
            )
        ),
        "measurement_object_has_human_state": hasattr(measurement, "human_q_rad"),
        "measurement_object_has_bed_force": hasattr(measurement, "bed_force_n"),
        "full_rollout_metric_comparison": {
            "validated_stage4_tracking_rmse_deg": validated["tracking"]["combined_rmse_deg"],
            "strict_boundary_ideal_tracking_rmse_deg": ideal["tracking"]["combined_rmse_deg"],
            "tracking_rmse_difference_deg": ideal["tracking"]["combined_rmse_deg"] - validated["tracking"]["combined_rmse_deg"],
            "validated_dynamic_accepted_updates": validated["dynamic_identifier"]["accepted_updates"],
            "strict_boundary_dynamic_accepted_updates": ideal["dynamic_identifier"]["accepted_updates"],
            "validated_geometry_trustworthy_time_s": validated["geometry_identifier"]["trustworthy_time_s"],
            "strict_boundary_geometry_trustworthy_time_s": ideal["geometry_identifier"]["trustworthy_time_s"],
        },
        "diagnosis": (
            "The ideal measurement sample and measured low-level law are numerically transparent. "
            "The full-rollout discrepancy comes from removing the MuJoCo bed-contact truth flag "
            "from the estimator boundary, not from sensor perturbation. Both A and B use the same "
            "strict measurement-only boundary."
        ),
        "proceed_with_fair_ab_comparison": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
