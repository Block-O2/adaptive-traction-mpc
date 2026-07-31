function config = single_arm_v2_case_config(base, preflight, case_name)
%SINGLE_ARM_V2_CASE_CONFIG Apply only the specified actuator limits.

case_name = string(case_name);
ideal_force_limit = base.preflight_margin*max(abs(preflight.u_ff), [], 2);
ideal_rate_limit = base.preflight_margin* ...
    max(abs(preflight.force_rate), [], 2);
% Avoid zero-width bounds without changing any observed nonzero requirement.
ideal_force_limit = max(ideal_force_limit, 1e-6);
ideal_rate_limit = max(ideal_rate_limit, 1e-6);

config = base;
config.case_name = case_name;
config.du_max = ideal_rate_limit;
if case_name == "ideal_authority"
    config.force_limit = ideal_force_limit;
elseif case_name == "engineering_bound"
    config.force_limit = base.engineering_force_limit_N(:);
else
    error('SingleArmV2:UnknownCase', 'Unknown case: %s', case_name);
end
config.u_min = -config.force_limit;
config.u_max = config.force_limit;
config.ideal_force_limit = ideal_force_limit;
config.ideal_rate_limit = ideal_rate_limit;
end
