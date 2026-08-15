function config = bed_supported_v1_robust_envelope_config()
%BED_SUPPORTED_V1_ROBUST_ENVELOPE_CONFIG Quasistatic envelope numerics.

config = struct();
config.analysis_name = "robust_suspended_feasibility_envelope";
config.force_bounds_N = [80, 120, 200];
config.tube_caps_deg = [0, 5, 10];
config.robust_thresholds_N = [0, 5, 10, 20];
config.progress_step = 0.01;
config.candidate_step_deg = 1.0;
config.refined_progress_step = 0.002;
config.refined_candidate_step_deg = 0.5;
config.boundary_window_s = 0.02;
config.svd_relative_tolerance = 1e-12;
config.torque_residual_tolerance_Nm = 1e-10;
config.force_tie_tolerance_N = 1e-10;
config.convergence_q2_tolerance_deg = 0.75;
config.convergence_margin_tolerance_N = 2.0;
config.run_boundary_refinement = true;
end
