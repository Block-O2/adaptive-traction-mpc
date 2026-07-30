function geometry = kinematics(q, p)
%KINEMATICS Planar lower-limb geometry for phi = q1 - q2.

q = q(:);
if numel(q) ~= 2 || any(~isfinite(q))
    error('HumanTwoLink:InvalidState', 'q must be a finite 2-vector.');
end

q1 = q(1);
q2 = q(2);
phi = q1 - q2;
e1 = [cos(q1); sin(q1)];
e2 = [cos(phi); sin(phi)];

geometry = struct();
geometry.phi = phi;
geometry.hip = zeros(2, 1);
geometry.knee = p.L1 * e1;
geometry.ankle = geometry.knee + p.L2 * e2;
geometry.com1 = p.lc1 * e1;
geometry.com2 = geometry.knee + p.lc2 * e2;
geometry.thigh_direction = e1;
geometry.shank_direction = e2;
geometry.shank_normal = [-sin(phi); cos(phi)];
end
