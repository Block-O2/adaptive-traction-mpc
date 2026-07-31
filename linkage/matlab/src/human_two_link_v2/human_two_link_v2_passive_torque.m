function [tau_passive_left, details] = ...
        human_two_link_v2_passive_torque(q, dq, p)
%HUMAN_TWO_LINK_V2_PASSIVE_TORQUE Passive resistance on dynamics left side.
%
% M*qdd+h+G+tau_passive_left=tau_joint. Positive-semidefinite damping is
% therefore +B*dq here. Physical passive torque on the right is its negative.

q = q(:);
dq = dq(:);
[tau_soft_rhs, soft_details] = ...
    human_two_link_v2_soft_limit_rhs_torque(q, dq, p);
spring_left = p.K_passive*(q-p.q_rest);
damping_left = p.B_passive*dq;
soft_left = -tau_soft_rhs;
tau_passive_left = spring_left+damping_left+soft_left;

details = struct();
details.spring_left = spring_left;
details.damping_left = damping_left;
details.soft_left = soft_left;
details.soft_rhs = tau_soft_rhs;
details.soft = soft_details;
details.damping_dissipation_W = dq'*p.B_passive*dq;
details.physical_rhs_torque = -tau_passive_left;
end
