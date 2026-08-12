function config = hybrid_tube_v1_config(force_bound_N, tube_cap_deg)
%HYBRID_TUBE_V1_CONFIG Fixed V1 task/reference-manager settings.

if ~isscalar(force_bound_N) || ~ismember(force_bound_N, [80, 120, 200]) || ...
        ~isscalar(tube_cap_deg) || ~ismember(tube_cap_deg, [0, 5, 10])
    error('HybridTubeV1:InvalidSensitivityCase', ...
        'Force bound must be 80/120/200 N and tube cap 0/5/10 deg.');
end
base = single_arm_v2_equilibrium_base_config();
config = base;
config.case_name = sprintf('tube_%gdeg_%gN', tube_cap_deg, force_bound_N);
config.force_bound_N = force_bound_N;
config.tube_cap_deg = tube_cap_deg;
config.u_min = -force_bound_N*ones(2, 1);
config.u_max = force_bound_N*ones(2, 1);
config.du_max = 250*ones(2, 1);
config.task_nominal_duration_s = 16.0;
config.max_time_s = 40.0;
config.nominal_progress_rate = 1/config.task_nominal_duration_s;
config.max_progress_rate = config.nominal_progress_rate;
config.max_progress_acceleration = 0.04;
config.max_progress_jerk = 0.20;
config.pause_classification_s = 1.0;
config.progress_tolerance = 1e-6;
config.terminal_position_tolerance_rad = deg2rad(0.5);
config.plan_node_count = 501;
config.candidate_step_deg = 1.0;
config.soft_margin_tolerance_rad = deg2rad(0.05);
config.plan_residual_tolerance_Nm = 1e-8;
config.force_utilization_slow = 0.65;
config.force_utilization_stop = 0.98;
config.plan_weights = struct( ...
    'path', 1.0, 'parallel_force', 5.0, 'force_norm', 2.0, ...
    'force_change', 0.5, 'posture_change', 0.5, 'rom_margin', 2.0);
end
