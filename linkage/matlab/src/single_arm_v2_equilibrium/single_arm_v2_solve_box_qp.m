function [u, details] = single_arm_v2_solve_box_qp(H, f, lower, upper)
%SINGLE_ARM_V2_SOLVE_BOX_QP Deterministic active-set enumeration in 2-D.
%
% Solves min u'*H*u+2*f'*u with lower<=u<=upper.

f = f(:);
lower = lower(:);
upper = upper(:);
if ~isequal(size(H), [2, 2]) || numel(f) ~= 2 || ...
        numel(lower) ~= 2 || numel(upper) ~= 2 || ...
        any(~isfinite([H(:); f; lower; upper])) || any(lower > upper)
    error('SingleArmV2:InvalidQuadraticProgram', ...
        'Finite two-dimensional quadratic data and ordered bounds are required.');
end
H = (H+H')/2;
[~, flag] = chol(H);
if flag ~= 0
    error('SingleArmV2:NonconvexQuadraticProgram', ...
        'The quadratic Hessian must be positive definite.');
end

statuses = [0 0; -1 0; 1 0; 0 -1; 0 1; ...
    -1 -1; -1 1; 1 -1; 1 1];
tol = 1e-11;
best_value = Inf;
best_u = zeros(2, 1);
best_status = zeros(2, 1);
feasible_count = 0;
for index = 1:size(statuses, 1)
    status = statuses(index, :)';
    candidate = zeros(2, 1);
    fixed = status ~= 0;
    free = ~fixed;
    candidate(status == -1) = lower(status == -1);
    candidate(status == 1) = upper(status == 1);
    if any(free)
        candidate(free) = -(H(free, free)\( ...
            f(free)+H(free, fixed)*candidate(fixed)));
    end
    if any(candidate < lower-tol) || any(candidate > upper+tol)
        continue;
    end
    candidate = min(max(candidate, lower), upper);
    feasible_count = feasible_count+1;
    value = candidate'*H*candidate+2*f'*candidate;
    if value < best_value-tol
        best_value = value;
        best_u = candidate;
        best_status = status;
    end
end
if feasible_count == 0
    error('SingleArmV2:NoFeasibleQPCandidate', ...
        'The deterministic boundary enumeration found no feasible point.');
end

u = best_u;
details = struct('objective', best_value, ...
    'active_status', best_status, ...
    'feasible_candidate_count', feasible_count, ...
    'stationarity_residual', H*u+f);
end
