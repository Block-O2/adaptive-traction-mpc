function point = bed_supported_v1_force_margin_point( ...
        q, p, component_bounds_N, svd_relative_tolerance)
%BED_SUPPORTED_V1_FORCE_MARGIN_POINT Robot-only quasistatic hold reserve.

% This diagnostic does not use bed support or a controller. It evaluates
% A(q)*F_hold=G(q)+tau_passive_left(q,0), with force ordered as
% [F_parallel; F_perp].

if nargin < 4
    svd_relative_tolerance = 1e-12;
end
q = q(:);
component_bounds_N = component_bounds_N(:)';
if numel(q) ~= 2 || any(~isfinite(q)) || ...
        any(q < p.q_min) || any(q > p.q_max) || ...
        any(~isfinite(component_bounds_N)) || ...
        any(component_bounds_N <= 0)
    error('BedSupportedV1:InvalidForceMarginPoint', ...
        'Posture and component-force bounds must be finite and valid.');
end

dq = zeros(2, 1);
[~, ~, ~, gravity_torque] = ...
    human_two_link_v2_dynamics_terms(q, dq, p);
[passive_torque, passive_details] = ...
    human_two_link_v2_passive_torque(q, dq, p);
holding_torque = gravity_torque+passive_torque;
mapping = single_arm_v2_force_map(q, dq, p);
[force, solve] = single_arm_v2_stable_force_solve( ...
    mapping.A, holding_torque, svd_relative_tolerance);

rank_deficient = solve.rank < 2;
if rank_deficient
    force(:) = NaN;
    force_norm_2 = NaN;
    force_norm_inf = NaN;
    force_margin_N = NaN(size(component_bounds_N));
else
    force_norm_2 = norm(force, 2);
    force_norm_inf = norm(force, Inf);
    force_margin_N = component_bounds_N-force_norm_inf;
end

lower_start = p.q_min+p.soft_limit_margin;
upper_start = p.q_max-p.soft_limit_margin;
soft_limit_margin_rad = min(q-lower_start, upper_start-q);

point = struct();
point.q = q;
point.force_local_N = force;
point.F_parallel_N = force(1);
point.F_perp_N = force(2);
point.force_norm_2_N = force_norm_2;
point.force_norm_inf_N = force_norm_inf;
point.component_bounds_N = component_bounds_N;
point.force_margin_N = force_margin_N;
point.exact_feasible = force_margin_N >= -1e-10;
point.gravity_torque_Nm = gravity_torque;
point.passive_torque_left_Nm = passive_torque;
point.holding_torque_Nm = holding_torque;
point.sigma_min = mapping.sigma_min;
point.condition_number = mapping.condition_number;
point.rank_deficient = rank_deficient;
point.exact_torque_residual_Nm = solve.residual;
point.exact_torque_residual_norm_Nm = solve.residual_norm;
point.soft_limit_active = any(passive_details.soft.active);
point.soft_limit_active_by_joint = passive_details.soft.active;
point.soft_limit_margin_rad = soft_limit_margin_rad;
point.minimum_soft_limit_margin_rad = min(soft_limit_margin_rad);
end
