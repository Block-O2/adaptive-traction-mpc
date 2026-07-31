function config = single_arm_v2_equilibrium_base_config()
%SINGLE_ARM_V2_EQUILIBRIUM_BASE_CONFIG Fixed controller/scientific settings.

config = struct();
config.trajectory_name = "slow_passive_flexion_v2";
config.dt = 0.002;
config.t_final = 16.0;
% One global documented revision from the older endpoint gains
% diag([36,49])/diag([12,14]): those gains produced a 0.0077 deg return
% undershoot into the V2 soft-limit zone. Reuse the already validated V2
% oracle gains for both cases; no case-specific tuning is permitted.
config.Kp = diag([180, 140]);
config.Kd = diag([28, 22]);
config.W_tau = eye(2);
config.tau_scale_Nm = 50.0;
config.F_scale_N = 400.0;
config.du_scale_N_s = 500.0;
config.lambda_ref = 1e-6;
% Zero preserves the exact equilibrium command whenever it is feasible;
% the explicit slew constraint still enforces the rate limit.
config.lambda_du = 0.0;
config.svd_relative_tolerance = 1e-12;
config.conditioning_threshold = 1e3;
config.sigma_min_threshold = 1e-6;
config.residual_tolerance_Nm = 1e-8;
config.bound_tolerance_N = 1e-8;
config.rom_tolerance_rad = 1e-9;
config.preflight_margin = 1.20;
config.engineering_force_limit_N = [80; 80];
end
