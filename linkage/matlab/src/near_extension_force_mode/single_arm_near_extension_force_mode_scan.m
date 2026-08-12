function study = single_arm_near_extension_force_mode_scan( ...
        p, q1_deg, q2_deg, component_bounds_N, svd_relative_tolerance)
%SINGLE_ARM_NEAR_EXTENSION_FORCE_MODE_SCAN Quasistatic posture objectives.
%
% For each positive knee-flexion sample, retain separate grid postures that
% minimize abs(F_parallel) and total force norm. q2=0 is evaluated only as a
% rank-deficient diagnostic row and is excluded from both searches.

if nargin < 2
    q1_deg = 0:1:80;
end
if nargin < 3
    q2_deg = 1:1:30;
end
if nargin < 4
    component_bounds_N = [80, 120, 200];
end
if nargin < 5
    svd_relative_tolerance = 1e-12;
end
q1_deg = q1_deg(:)';
q2_deg = q2_deg(:)';
component_bounds_N = component_bounds_N(:)';
if isempty(q1_deg) || isempty(q2_deg) || any(q2_deg <= 0) || ...
        any(~isfinite([q1_deg, q2_deg, component_bounds_N]))
    error('NearExtensionForceMode:InvalidGrid', ...
        'Finite q1 and strictly positive q2 grids are required.');
end

atlas = single_arm_quasistatic_atlas_grid(p, q1_deg, ...
    [0, q2_deg], component_bounds_N, svd_relative_tolerance);
if ~all(atlas.rank_deficient(1, :)) || ...
        ~all(isnan(atlas.force_norm(1, :)))
    error('NearExtensionForceMode:SingularRowInvalid', ...
        'q2=0 must remain rank deficient with NaN exact force.');
end

nq2 = numel(q2_deg);
parallel_optimum = initialize_curve(nq2, numel(component_bounds_N));
norm_optimum = initialize_curve(nq2, numel(component_bounds_N));
representative = initialize_curve(nq2, numel(component_bounds_N));
for q2_index = 1:nq2
    atlas_row = q2_index+1;
    [~, parallel_index] = min(abs(atlas.F_parallel(atlas_row, :)));
    [~, norm_index] = min(atlas.force_norm(atlas_row, :));
    parallel_optimum = assign_point(parallel_optimum, q2_index, ...
        q1_deg(parallel_index), q2_deg(q2_index), p, ...
        component_bounds_N, svd_relative_tolerance);
    norm_optimum = assign_point(norm_optimum, q2_index, ...
        q1_deg(norm_index), q2_deg(q2_index), p, ...
        component_bounds_N, svd_relative_tolerance);

    % Current V2 uses q1=5+(40/74)*(q2-10) on its actual q2=10..84
    % range. The same line is clipped to the scanned hip ROM below 10 deg
    % solely as a representative near-extension diagnostic extrapolation.
    representative_q1 = min(max( ...
        5+(40/74)*(q2_deg(q2_index)-10), q1_deg(1)), q1_deg(end));
    representative = assign_point(representative, q2_index, ...
        representative_q1, q2_deg(q2_index), p, ...
        component_bounds_N, svd_relative_tolerance);
end

study = struct();
study.q1_deg = q1_deg;
study.q2_deg = q2_deg;
study.component_bounds_N = component_bounds_N;
study.svd_relative_tolerance = svd_relative_tolerance;
study.atlas = atlas;
study.parallel_optimum = parallel_optimum;
study.norm_optimum = norm_optimum;
study.representative = representative;
study.representative_definition = [ ...
    "current V2 q1-q2 coordination line on q2=10..30 deg; " ...
    "clipped diagnostic extrapolation on q2=1..9 deg"];
end


function curve = initialize_curve(n, bound_count)
curve = struct();
curve.q1_deg = NaN(1, n);
curve.q2_deg = NaN(1, n);
curve.F_parallel = NaN(1, n);
curve.F_perp = NaN(1, n);
curve.force_norm = NaN(1, n);
curve.sigma_min = NaN(1, n);
curve.condition_number = NaN(1, n);
curve.holding_torque = NaN(2, n);
curve.robot_force = NaN(2, n, bound_count);
curve.support_torque = NaN(2, n, bound_count);
curve.support_norm = NaN(n, bound_count);
end


function curve = assign_point(curve, index, q1_deg, q2_deg, p, bounds, tol)
point = single_arm_quasistatic_hold_point( ...
    deg2rad([q1_deg; q2_deg]), p, bounds, tol);
curve.q1_deg(index) = q1_deg;
curve.q2_deg(index) = q2_deg;
curve.F_parallel(index) = point.F_parallel;
curve.F_perp(index) = point.F_perp;
curve.force_norm(index) = point.force_norm;
curve.sigma_min(index) = point.sigma_min;
curve.condition_number(index) = point.condition_number;
curve.holding_torque(:, index) = point.holding_torque;
for bound_index = 1:numel(bounds)
    robot_force = point.bounded_force(:, bound_index);
    support = point.holding_torque-point.mapping.A*robot_force;
    curve.robot_force(:, index, bound_index) = robot_force;
    curve.support_torque(:, index, bound_index) = support;
    curve.support_norm(index, bound_index) = norm(support);
end
end
