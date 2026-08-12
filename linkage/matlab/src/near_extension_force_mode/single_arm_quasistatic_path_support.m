function path = single_arm_quasistatic_path_support( ...
        q, time_s, p, component_bounds_N, svd_relative_tolerance)
%SINGLE_ARM_QUASISTATIC_PATH_SUPPORT Evaluate force and abstract support.
%
% tau_support_required=tau_hold-A*F_robot. It is a generalized-torque
% residual only and does not assume any external contact geometry.

if nargin < 4
    component_bounds_N = [80, 120, 200];
end
if nargin < 5
    svd_relative_tolerance = 1e-12;
end
if size(q, 1) ~= 2 || any(~isfinite(q(:)))
    error('NearExtensionForceMode:InvalidPath', ...
        'q must be a finite 2-by-N array.');
end
time_s = time_s(:)';
if numel(time_s) ~= size(q, 2) || any(~isfinite(time_s))
    error('NearExtensionForceMode:InvalidPathTime', ...
        'time_s must match the posture sample count.');
end
component_bounds_N = component_bounds_N(:)';
n = size(q, 2);
nb = numel(component_bounds_N);
path = struct();
path.time_s = time_s;
path.q = q;
path.F_parallel = NaN(1, n);
path.F_perp = NaN(1, n);
path.force_norm = NaN(1, n);
path.sigma_min = NaN(1, n);
path.condition_number = NaN(1, n);
path.rank_deficient = false(1, n);
path.holding_torque = NaN(2, n);
path.robot_force = NaN(2, n, nb);
path.support_torque = NaN(2, n, nb);
path.support_norm = NaN(n, nb);
path.component_bounds_N = component_bounds_N;
for index = 1:n
    point = single_arm_quasistatic_hold_point( ...
        q(:, index), p, component_bounds_N, svd_relative_tolerance);
    path.F_parallel(index) = point.F_parallel;
    path.F_perp(index) = point.F_perp;
    path.force_norm(index) = point.force_norm;
    path.sigma_min(index) = point.sigma_min;
    path.condition_number(index) = point.condition_number;
    path.rank_deficient(index) = point.rank_deficient;
    path.holding_torque(:, index) = point.holding_torque;
    for bound_index = 1:nb
        robot_force = point.bounded_force(:, bound_index);
        support = point.holding_torque-point.mapping.A*robot_force;
        path.robot_force(:, index, bound_index) = robot_force;
        path.support_torque(:, index, bound_index) = support;
        path.support_norm(index, bound_index) = norm(support);
    end
end
end
