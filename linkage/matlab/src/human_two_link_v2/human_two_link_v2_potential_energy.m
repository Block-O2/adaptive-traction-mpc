function potential = human_two_link_v2_potential_energy(q, p)
%HUMAN_TWO_LINK_V2_POTENTIAL_ENERGY Gravitational potential with Y upward.

q = q(:);
if numel(q) ~= 2 || any(~isfinite(q))
    error('HumanTwoLinkV2:InvalidState', 'q must be a finite 2-vector.');
end
phi = q(1)-q(2);
potential = p.g*((p.m1*p.lc1+p.m2*p.L1)*sin(q(1)) + ...
    p.m2*p.lc2*sin(phi));
end
