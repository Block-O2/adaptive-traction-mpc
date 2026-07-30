function [Fc, tau_contact, details] = damping_contact_force( ...
        q, dq, vr, p, contact_enabled)
%DAMPING_CONTACT_FORCE Continuous damping-only shank interaction.

if nargin < 5
    contact_enabled = true;
end
vr = vr(:);
if numel(vr) ~= 2 || any(~isfinite(vr))
    error('HumanTwoLink:InvalidRobotVelocity', ...
        'vr must be a finite 2-vector.');
end

contact = shank_contact_kinematics(q, dq, p);
v_rel = contact.velocity - vr;
vn_rel = contact.normal' * v_rel;

if contact_enabled
    Fc = -p.cn * vn_rel * contact.normal;
    tau_contact = contact.J' * Fc;
else
    Fc = zeros(2, 1);
    tau_contact = zeros(2, 1);
end

details = contact;
details.robot_velocity = vr;
details.relative_velocity = v_rel;
details.relative_normal_velocity = vn_rel;
details.relative_power = v_rel' * Fc;
details.enabled = logical(contact_enabled);
end
