function contact = shank_contact_kinematics(q, dq, p)
%SHANK_CONTACT_KINEMATICS Shank contact point, Jacobian, and velocity.

q = q(:);
dq = dq(:);
if numel(q) ~= 2 || numel(dq) ~= 2 || ...
        any(~isfinite(q)) || any(~isfinite(dq))
    error('HumanTwoLink:InvalidState', ...
        'q and dq must be finite 2-vectors.');
end

q1 = q(1);
q2 = q(2);
phi = q1 - q2;
e1 = [cos(q1); sin(q1)];
e2 = [cos(phi); sin(phi)];

contact = struct();
contact.phi = phi;
contact.position = p.L1*e1 + p.sc*e2;
contact.normal = [-sin(phi); cos(phi)];
contact.J = [ ...
    -p.L1*sin(q1) - p.sc*sin(phi),  p.sc*sin(phi); ...
     p.L1*cos(q1) + p.sc*cos(phi), -p.sc*cos(phi)];
contact.velocity = contact.J * dq;
end
