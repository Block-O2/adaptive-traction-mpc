function mapping = single_arm_v2_force_map(q, dq, p)
%SINGLE_ARM_V2_FORCE_MAP Local distal-cuff force to generalized torque.

contact = human_two_link_v2_contact_kinematics(q, dq, p);
R = [contact.tangent, contact.normal];
A = contact.J'*R;
analytic_A = [ ...
    -p.L1*sin(q(2)), p.L1*cos(q(2))+p.sc; ...
     0,               -p.sc];
singular_values = svd(A);

mapping = struct();
mapping.contact = contact;
mapping.rotation = R;
mapping.A = A;
mapping.analytic_A = analytic_A;
mapping.analytic_residual = A-analytic_A;
mapping.det_A = det(A);
mapping.det_A_analytic = p.L1*p.sc*sin(q(2));
mapping.sigma_max = singular_values(1);
mapping.sigma_min = singular_values(end);
if mapping.sigma_min > 0
    mapping.condition_number = mapping.sigma_max/mapping.sigma_min;
else
    mapping.condition_number = Inf;
end
end
