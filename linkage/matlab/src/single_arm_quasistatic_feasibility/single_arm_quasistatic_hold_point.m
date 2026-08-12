function point = single_arm_quasistatic_hold_point( ...
        q, p, component_bounds_N, svd_relative_tolerance)
%SINGLE_ARM_QUASISTATIC_HOLD_POINT Static distal-contact force diagnostic.
%
% Uses dq=0 and ddq=0 without changing the retained Human Model V2 or
% single-arm force-map implementations. Local force components are ordered
% [F_parallel; F_perp], matching the retained tangent/normal basis.

if nargin < 3
    component_bounds_N = [80, 120, 200];
end
if nargin < 4
    svd_relative_tolerance = 1e-12;
end
q = q(:);
component_bounds_N = component_bounds_N(:)';
if numel(q) ~= 2 || any(~isfinite(q)) || ...
        any(~isfinite(component_bounds_N)) || ...
        any(component_bounds_N <= 0) || ...
        ~isscalar(svd_relative_tolerance) || ...
        ~isfinite(svd_relative_tolerance) || svd_relative_tolerance <= 0
    error('SingleArmQuasistatic:InvalidInput', ...
        'q, component bounds, and SVD tolerance must be finite and valid.');
end

dq = zeros(2, 1);
[~, ~, ~, gravity_torque] = ...
    human_two_link_v2_dynamics_terms(q, dq, p);
[passive_torque, passive_details] = ...
    human_two_link_v2_passive_torque(q, dq, p);
holding_torque = gravity_torque+passive_torque;
mapping = single_arm_v2_force_map(q, dq, p);
[svd_force, svd_details] = single_arm_v2_stable_force_solve( ...
    mapping.A, holding_torque, svd_relative_tolerance);

rank_deficient = svd_details.rank < 2;
if rank_deficient
    exact_force = [NaN; NaN];
    force_norm = NaN;
    diagnostic_sigma_min = 0;
    diagnostic_condition_number = Inf;
    diagnostic_det_A = 0;
else
    exact_force = svd_force;
    force_norm = norm(exact_force);
    diagnostic_sigma_min = mapping.sigma_min;
    diagnostic_condition_number = mapping.condition_number;
    diagnostic_det_A = mapping.det_A_analytic;
end

bound_count = numel(component_bounds_N);
exact_feasible = false(1, bound_count);
bounded_force = NaN(2, bound_count);
bounded_residual = NaN(2, bound_count);
bounded_residual_norm = NaN(1, bound_count);
bounded_tie_break = zeros(1, bound_count);
for bound_index = 1:bound_count
    limit = component_bounds_N(bound_index);
    exact_feasible(bound_index) = ~rank_deficient && ...
        all(abs(exact_force) <= limit+1e-10);
    if exact_feasible(bound_index)
        candidate = exact_force;
    else
        H = mapping.A'*mapping.A;
        if rank_deficient
            % The existing box solver requires positive-definite H. This
            % negligible tie-break selects a deterministic minimum-norm point
            % from the rank-deficient least-residual solution set.
            bounded_tie_break(bound_index) = ...
                1e-12*max(1, norm(mapping.A, 'fro')^2);
            H = H+bounded_tie_break(bound_index)*eye(2);
        end
        f = -mapping.A'*holding_torque;
        candidate = single_arm_v2_solve_box_qp( ...
            H, f, -limit*ones(2, 1), limit*ones(2, 1));
    end
    residual = mapping.A*candidate-holding_torque;
    bounded_force(:, bound_index) = candidate;
    bounded_residual(:, bound_index) = residual;
    bounded_residual_norm(bound_index) = norm(residual);
end

point = struct();
point.q = q;
point.gravity_torque = gravity_torque;
point.passive_torque_left = passive_torque;
point.passive_details = passive_details;
point.holding_torque = holding_torque;
point.mapping = mapping;
point.rank_deficient = rank_deficient;
point.sigma_min = diagnostic_sigma_min;
point.condition_number = diagnostic_condition_number;
point.det_A = diagnostic_det_A;
point.force_local = exact_force;
point.F_parallel = exact_force(1);
point.F_perp = exact_force(2);
point.force_norm = force_norm;
point.svd_pseudoinverse_force = svd_force;
point.torque_residual = svd_details.residual;
point.torque_residual_norm = svd_details.residual_norm;
point.svd_details = svd_details;
point.component_bounds_N = component_bounds_N;
point.exact_feasible = exact_feasible;
point.bounded_force = bounded_force;
point.bounded_residual = bounded_residual;
point.bounded_residual_norm = bounded_residual_norm;
point.bounded_tie_break = bounded_tie_break;
end
