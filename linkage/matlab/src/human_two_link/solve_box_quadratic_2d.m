function [u, details] = solve_box_quadratic_2d(H, f, lower, upper)
%SOLVE_BOX_QUADRATIC_2D Deterministic enumeration for a convex 2-D box QP.
%
% Solve min_u u'*H*u + 2*f'*u subject to lower <= u <= upper.

f = f(:);
lower = lower(:);
upper = upper(:);
if ~isequal(size(H), [2, 2]) || numel(f) ~= 2 || ...
        numel(lower) ~= 2 || numel(upper) ~= 2 || ...
        any(~isfinite([H(:); f; lower; upper])) || ...
        any(lower > upper)
    error('IdealEndpointForce:InvalidQuadraticProgram', ...
        'H, f, and finite ordered 2-vector bounds are required.');
end

H = (H + H') / 2;
[~, chol_flag] = chol(H);
if chol_flag ~= 0
    error('IdealEndpointForce:NonconvexQuadraticProgram', ...
        'H must be symmetric positive definite.');
end

% -1: lower bound, 0: free, +1: upper bound.
statuses = [ ...
    0,  0; ...
   -1,  0; ...
    1,  0; ...
    0, -1; ...
    0,  1; ...
   -1, -1; ...
   -1,  1; ...
    1, -1; ...
    1,  1];
tolerance = 1e-12;
best_value = inf;
best_u = zeros(2, 1);
best_status = zeros(2, 1);
feasible_count = 0;

for candidate_index = 1:size(statuses, 1)
    status = statuses(candidate_index, :)';
    candidate = zeros(2, 1);
    fixed = status ~= 0;
    free = ~fixed;
    candidate(status == -1) = lower(status == -1);
    candidate(status == 1) = upper(status == 1);

    if any(free)
        candidate(free) = -(H(free, free) \ ( ...
            f(free) + H(free, fixed)*candidate(fixed)));
    end

    if any(candidate < lower - tolerance) || ...
            any(candidate > upper + tolerance)
        continue;
    end
    candidate = min(max(candidate, lower), upper);
    feasible_count = feasible_count + 1;
    value = candidate'*H*candidate + 2*f'*candidate;
    if value < best_value - tolerance
        best_value = value;
        best_u = candidate;
        best_status = status;
    end
end

if feasible_count == 0
    error('IdealEndpointForce:NoFeasibleCandidate', ...
        'Boundary enumeration found no feasible candidate.');
end

u = best_u;
details = struct();
details.objective = best_value;
details.active_status = best_status;
details.feasible_candidate_count = feasible_count;
details.stationarity_residual = H*u + f;
end
