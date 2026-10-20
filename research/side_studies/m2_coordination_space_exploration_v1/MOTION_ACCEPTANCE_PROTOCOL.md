# Prospective motion acceptance

{
  "registered_unix": 1791479768.952254,
  "clinical_thresholds": false,
  "reference": "new same-seed cold B full TASK; prospective thresholds frozen before any new physical output",
  "primary": {
    "burden_ratio": 1.1,
    "velocity": [
      "max_abs",
      "p95_abs",
      "rms"
    ],
    "acceleration": [
      "max_abs",
      "p95_abs",
      "rms"
    ],
    "jerk": [
      "p95_abs",
      "rms"
    ],
    "excursion_abs_delta_deg": 0.5,
    "cumulative_ratio_upper": 1.05,
    "cumulative_ratio_lower": 0.95,
    "endpoint_and_phase_boundary_abs_delta_deg": 0.5,
    "total_duration_abs_delta_s": 0.1,
    "each_phase_duration_abs_delta_s": 0.1,
    "moment_integral_ratio": 1.25,
    "tracking_RMS_add_deg": 0.5,
    "force_peak_ratio": 1.05,
    "moment_peak_ratio": 1.05,
    "phase_shape_diagnostic_only": true
  },
  "sensitivity_burden_ratios": [
    1.0,
    1.05,
    1.1,
    1.25
  ],
  "phase_shape_reference_degrees": [
    0.5,
    1.0,
    2.0
  ],
  "jerk_method": "dense true dq gradient twice, raw mandatory; SG5/21 order3 sensitivity; no endpoint deletion",
  "basis": "10% research noninferiority retains historical moderate tier; .5 degree endpoint/excursion and 5% dose retain historical moderate limits. Add raw acceleration peak and jerk p95/RMS as prospective burden gates. 5% peak compensation and 25% moment integral bounded within unchanged native absolute limits. No evidence supports clinical thresholds; strict/5%/25% reported without reselection.",
  "therapy_trajectory": "phase-shape reported separately because broad progress-shape envelope lacks clinical justification; phase goals/boundaries, timing, original tracking and physical hard gates remain mandatory. Full historical PASS/FAIL unchanged."
}
