function geometry = human_two_link_v2_kinematics(q, p)
%HUMAN_TWO_LINK_V2_KINEMATICS Planar geometry for phi=q1-q2.

q = q(:);
if numel(q) ~= 2 || any(~isfinite(q))
    error('HumanTwoLinkV2:InvalidState', 'q must be a finite 2-vector.');
end
phi = q(1)-q(2);
e1 = [cos(q(1)); sin(q(1))];
e2 = [cos(phi); sin(phi)];

geometry = struct();
geometry.phi = phi;
geometry.hip = zeros(2, 1);
geometry.knee = p.L1*e1;
geometry.ankle = geometry.knee+p.L2*e2;
geometry.com1 = p.lc1*e1;
geometry.com2 = geometry.knee+p.lc2*e2;
geometry.contact = geometry.knee+p.sc*e2;
geometry.shank_normal = [-sin(phi); cos(phi)];
end
