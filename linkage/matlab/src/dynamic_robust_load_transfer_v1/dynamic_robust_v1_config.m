function config = dynamic_robust_v1_config()
%DYNAMIC_ROBUST_V1_CONFIG Fixed 200 N / 10 degree capability experiment.

config = bed_supported_v1_config(200, 10, "nominal");
config.case_name = "dynamic_robust_nominal_200N_10deg";
config.robust_entry_trigger_N = 20;
config.robust_entry_hysteresis_N = 1;
config.supervisor_period_s = 0.01;
config.entry_guard_duration_s = 0.10;
config.transfer_ready_duration_s = 0.50;
config.takeover_recovery_timeout_s = 2.0;
config.suspended_blend_duration_s = 0.50;
config.suspended_pause_timeout_s = 2.0;
config.recontact_timeout_s = 8.0;
config.recontact_search_period_s = 0.10;
config.max_time_s = 60.0;
config.posture_candidate_step_deg = 1.0;
config.dynamic_residual_tolerance_Nm = config.residual_tolerance_Nm;
config.soft_torque_tolerance_Nm = 1e-8;
config.force_rate_tolerance_N_s = max(config.du_max)+1e-8;
config.return_terminal_velocity_tolerance_rad_s = deg2rad(0.5);
config.event_position_tolerance_rad = deg2rad(0.5);
% R1 startup handover.  The capture band is tied to half of the existing
% 20 N robust-entry margin; it bounds the actuator mismatch admitted to the
% short slew-limited TAKEOVER phase without changing the nominal law.
config.safe_takeover_capture_band_N = config.robust_entry_trigger_N/2;
config.safe_takeover_tracking_error_N = config.force_jump_tolerance_N;
config.safe_takeover_tracking_clearance_rad = ...
    config.preposition_position_tolerance_rad;
config.safe_takeover_stable_duration_s = 0.02;
config.safe_takeover_timeout_s = config.preposition_timeout_s;
config.safe_takeover_prediction_tolerance_rad = 1e-12;
config.safe_takeover_velocity_tolerance_rad_s = 1e-12;
config.engineering_trigger_not_clinical = true;
end
