function [xdot, details] = single_arm_v2_endpoint_dynamics(x, u, p)
%SINGLE_ARM_V2_ENDPOINT_DYNAMICS V2 plant driven only by local cuff force.

x = x(:);
u = u(:);
if numel(x) ~= 4 || numel(u) ~= 2 || any(~isfinite([x; u]))
    error('SingleArmV2:InvalidEndpointDynamicsInput', ...
        'State and local endpoint force must be finite 4- and 2-vectors.');
end
q = x(1:2);
dq = x(3:4);
mapping = single_arm_v2_force_map(q, dq, p);
[M, h, C, G] = human_two_link_v2_dynamics_terms(q, dq, p);
[tau_passive, passive] = human_two_link_v2_passive_torque(q, dq, p);
world_force = mapping.rotation*u;
tau_contact = mapping.A*u;
ddq = M\(tau_contact-h-G-tau_passive);

xdot = [dq; ddq];
details = struct('M', M, 'h', h, 'C', C, 'G', G, ...
    'tau_passive_left', tau_passive, 'passive', passive, ...
    'mapping', mapping, 'force_local', u, ...
    'force_world', world_force, 'tau_contact', tau_contact, ...
    'ddq', ddq);
end
