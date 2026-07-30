function [M, h, C, G] = dynamics_terms(q, dq, p)
%DYNAMICS_TERMS Physically consistent terms for phi = q1 - q2.

q = q(:);
dq = dq(:);
if numel(q) ~= 2 || numel(dq) ~= 2 || ...
        any(~isfinite(q)) || any(~isfinite(dq))
    error('HumanTwoLink:InvalidState', ...
        'q and dq must be finite 2-vectors.');
end

q1 = q(1);
q2 = q(2);
dq1 = dq(1);
dq2 = dq(2);
phi = q1 - q2;

b = p.I2 + p.m2*p.lc2^2;
d = p.m2*p.L1*p.lc2;
a = p.I1 + p.m1*p.lc1^2 + b + p.m2*p.L1^2;

M11 = a + 2*d*cos(q2);
M12 = -(b + d*cos(q2));
M = [M11, M12; M12, b];

h = [ ...
    d*sin(q2)*(-2*dq1*dq2 + dq2^2); ...
    d*sin(q2)*dq1^2];

C = [ ...
    -d*sin(q2)*dq2, d*sin(q2)*(dq2-dq1); ...
     d*sin(q2)*dq1, 0];

G = [ ...
    p.g*((p.m1*p.lc1 + p.m2*p.L1)*cos(q1) + ...
        p.m2*p.lc2*cos(phi)); ...
    -p.m2*p.g*p.lc2*cos(phi)];
end
