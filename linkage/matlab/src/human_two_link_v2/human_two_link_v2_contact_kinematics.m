function contact = human_two_link_v2_contact_kinematics(q, dq, p)
%HUMAN_TWO_LINK_V2_CONTACT_KINEMATICS Distal wide-cuff equivalent point.

q = q(:);
dq = dq(:);
if numel(q) ~= 2 || numel(dq) ~= 2 || ...
        any(~isfinite(q)) || any(~isfinite(dq))
    error('HumanTwoLinkV2:InvalidState', ...
        'q and dq must be finite 2-vectors.');
end
phi = q(1)-q(2);
contact = struct();
contact.phi = phi;
contact.position = [ ...
    p.L1*cos(q(1))+p.sc*cos(phi); ...
    p.L1*sin(q(1))+p.sc*sin(phi)];
contact.J = [ ...
    -p.L1*sin(q(1))-p.sc*sin(phi),  p.sc*sin(phi); ...
     p.L1*cos(q(1))+p.sc*cos(phi), -p.sc*cos(phi)];
contact.velocity = contact.J*dq;
contact.tangent = [cos(phi); sin(phi)];
contact.normal = [-sin(phi); cos(phi)];
end
