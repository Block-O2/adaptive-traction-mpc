# 0.46 m structural prior audit

{
  "role": "Fixed structural conservative full knee-to-ankle shank length upper bound used to construct a worst-case distal cylinder endpoint; not cuff lever, fitted L2, measured registered individual bound or fit optimizer limit.",
  "value_m": 0.46,
  "additional_margin_m": 0.001,
  "shank_radius_m": 0.045,
  "bed_height_m": 0.012,
  "source": "SessionClearanceContract runtime.py:151-209 plus RigidTableReferenceEnvelopeV1 rigid_table_reference.py:46-47; development_v1_1.json registered same value.",
  "estimator_bounds": {
    "hip_x_m": [
      -0.35,
      0.35
    ],
    "hip_z_m": [
      -0.05,
      0.3
    ],
    "thigh_length_m": [
      0.3,
      0.56
    ],
    "knee_to_cuff_m": [
      0.14,
      0.48
    ]
  },
  "fit_identifies": "hip world X/Z, thigh length, effective cuff lever only; explicitly does not split cuff lever=fraction*full_shank.",
  "expression": "min(knee_z, knee_z + .46*sin(q1-q2)) - .045 - .012 - .001",
  "B_handoff_distal_m": -0.00182709542797332,
  "true_geometry_same_state_distal_m": -0.0018368384996284527,
  "critical_full_shank_upper_at_B_m": 0.4419582955880755,
  "actual_full_shank_m_evaluation_only": 0.40076,
  "excess_length_m": 0.05924,
  "predicted_extra_downward_endpoint_displacement_m": 0.005999274274862906,
  "truth_bound_diagnostic_m": 0.004172178846889582,
  "same_prior_both_recovery_paths": true,
  "same_zero_tool_reference_offset_both_recovery_paths": true,
  "different_model_gauge_equivalent_in_world_hip": true,
  "different_handoff_physical_state": true,
  "why_conservative": "A shorter cuff lever does not certify a shorter full shank. A .46m shank with the same identified lever remains in the admissible unmeasured geometry set. At this negative shank pitch its distal cylinder violates the certificate although the simulated .40076m shank does not.",
  "commissioning_escape_note": "The frozen commissioning path explicitly permits a narrow nonworsening distal-shank escape, guarded by monotonic geometric proof; its source explicitly forbids this exception in TASK/RECOVERY. No such bypass is enabled here."
}
