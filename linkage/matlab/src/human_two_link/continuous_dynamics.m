function [xdot, details] = continuous_dynamics( ...
        x, tau_joint, vr, p, contact_enabled)
%CONTINUOUS_DYNAMICS Human two-link state derivative.

if nargin < 5
    contact_enabled = true;
end
x = x(:);
tau_joint = tau_joint(:);
if numel(x) ~= 4 || numel(tau_joint) ~= 2 || ...
        any(~isfinite(x)) || any(~isfinite(tau_joint))
    error('HumanTwoLink:InvalidDynamicsInput', ...
        'x and tau_joint must be finite 4- and 2-vectors.');
end

q = x(1:2);
dq = x(3:4);
[M, h, C, G] = dynamics_terms(q, dq, p);
[Fc, tau_contact, contact] = damping_contact_force( ...
    q, dq, vr, p, contact_enabled);
ddq = M \ (tau_joint + tau_contact - h - G - p.B*dq);

xdot = [dq; ddq];
details = struct();
details.M = M;
details.h = h;
details.C = C;
details.G = G;
details.Fc = Fc;
details.tau_contact = tau_contact;
details.contact = contact;
details.ddq = ddq;
end
