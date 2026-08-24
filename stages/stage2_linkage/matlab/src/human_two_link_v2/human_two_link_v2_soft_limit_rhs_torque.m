function [tau_soft_rhs, details] = ...
        human_two_link_v2_soft_limit_rhs_torque(q, dq, p)
%HUMAN_TWO_LINK_V2_SOFT_LIMIT_RHS_TORQUE Smooth inward physical torque.
%
% This is a physical torque on the dynamics right-hand side. The passive
% resistance term on the left-hand side therefore subtracts this value.

q = q(:);
dq = dq(:);
if numel(q) ~= 2 || numel(dq) ~= 2 || ...
        any(~isfinite(q)) || any(~isfinite(dq))
    error('HumanTwoLinkV2:InvalidState', ...
        'q and dq must be finite 2-vectors.');
end

lower_start = p.q_min + p.soft_limit_margin;
upper_start = p.q_max - p.soft_limit_margin;
lower_activation = lower_start-p.soft_limit_numerical_tolerance;
upper_activation = upper_start+p.soft_limit_numerical_tolerance;
tau_soft_rhs = zeros(2, 1);
normalized_penetration = zeros(2, 1);
active_side = zeros(2, 1);

for joint_index = 1:2
    if q(joint_index) < lower_activation(joint_index)
        z = (lower_activation(joint_index)-q(joint_index)) / ...
            p.soft_limit_margin;
        position_torque = p.soft_limit_boundary_torque_Nm*z^3;
        damping_torque = p.soft_limit_damping_Nms_rad*z^2 * ...
            max(-dq(joint_index), 0);
        tau_soft_rhs(joint_index) = position_torque+damping_torque;
        normalized_penetration(joint_index) = z;
        active_side(joint_index) = -1;
    elseif q(joint_index) > upper_activation(joint_index)
        z = (q(joint_index)-upper_activation(joint_index)) / ...
            p.soft_limit_margin;
        position_torque = p.soft_limit_boundary_torque_Nm*z^3;
        damping_torque = p.soft_limit_damping_Nms_rad*z^2 * ...
            max(dq(joint_index), 0);
        tau_soft_rhs(joint_index) = -(position_torque+damping_torque);
        normalized_penetration(joint_index) = z;
        active_side(joint_index) = 1;
    end
end

details = struct();
details.lower_start = lower_start;
details.upper_start = upper_start;
details.lower_activation = lower_activation;
details.upper_activation = upper_activation;
details.normalized_penetration = normalized_penetration;
details.active_side = active_side;
details.active = active_side ~= 0;
end
