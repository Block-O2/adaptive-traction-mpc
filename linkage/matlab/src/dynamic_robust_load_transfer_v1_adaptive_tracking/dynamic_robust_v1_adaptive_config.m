function adaptive = dynamic_robust_v1_adaptive_config(config)
%DYNAMIC_ROBUST_V1_ADAPTIVE_CONFIG Fixed R2B identifier configuration.

if nargin < 1 || isempty(config), config = dynamic_robust_v1_config(); end
adaptive = struct();
adaptive.enabled = true;
adaptive.parameter_names = ["mass_scale","lc1_scale","lc2_scale", ...
    "K_scale","qrest1_offset_rad","qrest2_offset_rad","sc_scale"];
adaptive.theta_nominal = [1;1;1;1;0;0;1];
adaptive.theta_min = [.90;.90;.90;.80;deg2rad(-2);deg2rad(-2);.95];
adaptive.theta_max = [1.10;1.10;1.10;1.20;deg2rad(2);deg2rad(2);1.05];
adaptive.theta_range = adaptive.theta_max-adaptive.theta_min;
% The mechanical task is slow relative to the 2 ms control step. A 0.2 s
% window preserves recent dynamics. The exact-RK4 seven-parameter solve cost
% measured by the pre-closed-loop replay requires a 1 Hz solve cadence rather
% than a solve at the 500 Hz control rate.
adaptive.window_size = round(0.20/config.dt);
adaptive.minimum_window_size = adaptive.window_size;
adaptive.update_interval = round(1.00/config.dt);
adaptive.maximum_iterations = 6;
adaptive.finite_difference_step = 1e-4;
adaptive.line_search_scales = [1,.5,.25,.125];
adaptive.lm_damping = 1e-8;
adaptive.maximum_condition_number = 1/sqrt(eps);
% At most 20% of each registered parameter range is admitted per accepted
% 1 Hz update. This preserves the originally selected maximum continuous
% adaptation rate of 20% of the registered range per simulated second.
adaptive.maximum_update_step = .20*adaptive.theta_range;
adaptive.fit_improvement_tolerance = 100*eps;
adaptive.parameter_bound_tolerance = 100*eps;
adaptive.engineering_bounds_not_case_specific = true;
adaptive.no_deliberate_excitation = true;
end
