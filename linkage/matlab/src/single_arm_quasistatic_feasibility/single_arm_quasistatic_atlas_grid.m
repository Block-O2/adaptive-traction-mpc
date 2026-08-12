function atlas = single_arm_quasistatic_atlas_grid( ...
        p, q1_deg, q2_deg, component_bounds_N, svd_relative_tolerance)
%SINGLE_ARM_QUASISTATIC_ATLAS_GRID Evaluate the static hold-force map.

if nargin < 2
    q1_deg = 0:1:80;
end
if nargin < 3
    q2_deg = 0:1:100;
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
if isempty(q1_deg) || isempty(q2_deg) || ...
        any(~isfinite([q1_deg, q2_deg]))
    error('SingleArmQuasistatic:InvalidGrid', ...
        'Joint grids must be nonempty and finite.');
end

nq1 = numel(q1_deg);
nq2 = numel(q2_deg);
nb = numel(component_bounds_N);
shape = [nq2, nq1];
F_parallel = NaN(shape);
F_perp = NaN(shape);
force_norm = NaN(shape);
torque_residual = NaN([shape, 2]);
torque_residual_norm = NaN(shape);
sigma_min = NaN(shape);
condition_number = NaN(shape);
det_A = NaN(shape);
gravity_torque = NaN([shape, 2]);
passive_torque = NaN([shape, 2]);
holding_torque = NaN([shape, 2]);
rank_deficient = false(shape);
feasible = false([shape, nb]);
bounded_force = NaN([shape, 2, nb]);
bounded_residual_norm = NaN([shape, nb]);

for q1_index = 1:nq1
    for q2_index = 1:nq2
        point = single_arm_quasistatic_hold_point( ...
            deg2rad([q1_deg(q1_index); q2_deg(q2_index)]), p, ...
            component_bounds_N, svd_relative_tolerance);
        F_parallel(q2_index, q1_index) = point.F_parallel;
        F_perp(q2_index, q1_index) = point.F_perp;
        force_norm(q2_index, q1_index) = point.force_norm;
        torque_residual(q2_index, q1_index, :) = point.torque_residual;
        torque_residual_norm(q2_index, q1_index) = ...
            point.torque_residual_norm;
        sigma_min(q2_index, q1_index) = point.sigma_min;
        condition_number(q2_index, q1_index) = point.condition_number;
        det_A(q2_index, q1_index) = point.det_A;
        gravity_torque(q2_index, q1_index, :) = point.gravity_torque;
        passive_torque(q2_index, q1_index, :) = ...
            point.passive_torque_left;
        holding_torque(q2_index, q1_index, :) = point.holding_torque;
        rank_deficient(q2_index, q1_index) = point.rank_deficient;
        for bound_index = 1:nb
            feasible(q2_index, q1_index, bound_index) = ...
                point.exact_feasible(bound_index);
            bounded_force(q2_index, q1_index, :, bound_index) = ...
                point.bounded_force(:, bound_index);
            bounded_residual_norm(q2_index, q1_index, bound_index) = ...
                point.bounded_residual_norm(bound_index);
        end
    end
end

minimum_feasible_q2_deg = NaN(nb, nq1);
for bound_index = 1:nb
    for q1_index = 1:nq1
        first = find(feasible(:, q1_index, bound_index), 1, 'first');
        if ~isempty(first)
            minimum_feasible_q2_deg(bound_index, q1_index) = q2_deg(first);
        end
    end
end

atlas = struct();
atlas.q1_deg = q1_deg;
atlas.q2_deg = q2_deg;
atlas.component_bounds_N = component_bounds_N;
atlas.F_parallel = F_parallel;
atlas.F_perp = F_perp;
atlas.force_norm = force_norm;
atlas.torque_residual = torque_residual;
atlas.torque_residual_norm = torque_residual_norm;
atlas.sigma_min = sigma_min;
atlas.condition_number = condition_number;
atlas.det_A = det_A;
atlas.gravity_torque = gravity_torque;
atlas.passive_torque_left = passive_torque;
atlas.holding_torque = holding_torque;
atlas.rank_deficient = rank_deficient;
atlas.feasible = feasible;
atlas.bounded_force = bounded_force;
atlas.bounded_residual_norm = bounded_residual_norm;
atlas.minimum_feasible_q2_deg = minimum_feasible_q2_deg;
atlas.svd_relative_tolerance = svd_relative_tolerance;
end
