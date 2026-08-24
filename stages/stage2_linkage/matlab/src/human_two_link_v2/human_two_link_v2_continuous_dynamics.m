function [xdot, details] = ...
        human_two_link_v2_continuous_dynamics(x, tau_joint, p)
%HUMAN_TWO_LINK_V2_CONTINUOUS_DYNAMICS V2 left-side passive dynamics.

x = x(:);
tau_joint = tau_joint(:);
if numel(x) ~= 4 || numel(tau_joint) ~= 2 || ...
        any(~isfinite(x)) || any(~isfinite(tau_joint))
    error('HumanTwoLinkV2:InvalidDynamicsInput', ...
        'x and tau_joint must be finite 4- and 2-vectors.');
end
q = x(1:2);
dq = x(3:4);
[M, h, C, G] = human_two_link_v2_dynamics_terms(q, dq, p);
[tau_passive, passive_details] = ...
    human_two_link_v2_passive_torque(q, dq, p);
ddq = M\(tau_joint-h-G-tau_passive);

xdot = [dq; ddq];
details = struct();
details.M = M;
details.h = h;
details.C = C;
details.G = G;
details.tau_passive_left = tau_passive;
details.passive = passive_details;
details.ddq = ddq;
end
