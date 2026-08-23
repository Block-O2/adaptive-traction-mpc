function config = near_extension_protective_mode_config()
%NEAR_EXTENSION_PROTECTIVE_MODE_CONFIG MATLAB sanity-only interface settings.

normal = dynamic_robust_v1_config();
config.q_switch_rad = deg2rad(30);
config.q_terminal_rad = deg2rad(2);
config.q_switch_deg = 30;
config.q_terminal_deg = 2;
config.transition_duration_s = 4.0;
config.blend_duration_s = 0.75;
config.dt = normal.dt;
config.force_bound_N = normal.force_bound_N;
config.force_veto_tolerance_N = normal.bound_tolerance_N;
config.switch_tolerance_rad = deg2rad(0.05);
config.terminal_tolerance_rad = deg2rad(0.05);
config.normal_config = normal;
config.engineering_switch_not_clinical = true;
config.validation_scope = "COMMAND_INTERFACE_SANITY_ONLY";
end
