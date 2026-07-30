function V = potential_energy(q, p)
%POTENTIAL_ENERGY Gravitational potential with horizontal angle zero.

q = q(:);
if numel(q) ~= 2 || any(~isfinite(q))
    error('HumanTwoLink:InvalidState', 'q must be a finite 2-vector.');
end

q1 = q(1);
q2 = q(2);
V = p.g * ((p.m1*p.lc1 + p.m2*p.L1)*sin(q1) + ...
    p.m2*p.lc2*sin(q1-q2));
end
