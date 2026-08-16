function parameters = dynamic_robust_v1_adaptive_apply_theta(nominal, theta)
%DYNAMIC_ROBUST_V1_ADAPTIVE_APPLY_THETA Build model from registered factors.

theta=theta(:);
if numel(theta)~=7 || any(~isfinite(theta))
    error('DynamicRobustV1:InvalidAdaptiveTheta', ...
        'Adaptive theta must contain seven finite values.');
end
override=struct('mass_scale',theta(1),'lc1_scale',theta(2), ...
    'lc2_scale',theta(3),'K_scale',theta(4), ...
    'q_rest_offset_rad',theta(5:6),'sc_scale',theta(7));
parameters=bed_supported_v1_parameter_override(nominal,override);
end
