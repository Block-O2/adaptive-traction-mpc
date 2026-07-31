function [xdot, details] = endpoint_force_dynamics(x, u, p)
%ENDPOINT_FORCE_DYNAMICS Human dynamics driven only by ideal endpoint force.

x = x(:);
u = u(:);
if numel(x) ~= 4 || numel(u) ~= 2 || ...
        any(~isfinite(x)) || any(~isfinite(u))
    error('IdealEndpointForce:InvalidDynamicsInput', ...
        'x and u must be finite 4- and 2-vectors.');
end

q = x(1:2);
dq = x(3:4);
mapping = shank_endpoint_force_map(q, dq, p);
world_force = mapping.rotation * u;
tau_contact = mapping.contact.J' * world_force;
[M, h, C, G] = dynamics_terms(q, dq, p);
ddq = M \ (tau_contact - h - G - p.B*dq);

xdot = [dq; ddq];
details = struct();
details.M = M;
details.h = h;
details.C = C;
details.G = G;
details.mapping = mapping;
details.world_force = world_force;
details.tau_contact = tau_contact;
details.ddq = ddq;
end
