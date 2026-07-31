function [u, details] = single_arm_v2_stable_force_solve(A, tau, tolerance)
%SINGLE_ARM_V2_STABLE_FORCE_SOLVE SVD solve without explicitly forming inv(A).

if nargin < 3
    tolerance = 1e-12;
end
tau = tau(:);
if ~isequal(size(A), [2, 2]) || numel(tau) ~= 2 || ...
        any(~isfinite([A(:); tau])) || ~isscalar(tolerance) || ...
        tolerance <= 0
    error('SingleArmV2:InvalidLinearSolve', ...
        'A, tau, and tolerance must be finite and dimensionally valid.');
end

[U, S, V] = svd(A, 'econ');
s = diag(S);
threshold = tolerance*max(1, s(1));
retained = s > threshold;
inverse_s = zeros(size(s));
inverse_s(retained) = 1./s(retained);
u = V*(inverse_s.*(U'*tau));

details = struct();
details.singular_values = s;
details.rank = sum(retained);
details.threshold = threshold;
details.residual = A*u-tau;
details.residual_norm = norm(details.residual);
if s(end) > 0
    details.condition_number = s(1)/s(end);
else
    details.condition_number = Inf;
end
details.sigma_min = s(end);
end
