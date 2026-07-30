function mapping = shank_endpoint_force_map(q, dq, p)
%SHANK_ENDPOINT_FORCE_MAP Local cuff force to world force/generalized torque.

contact = shank_contact_kinematics(q, dq, p);
tangent = [cos(contact.phi); sin(contact.phi)];
rotation = [tangent, contact.normal];

mapping = struct();
mapping.contact = contact;
mapping.tangent = tangent;
mapping.normal = contact.normal;
mapping.rotation = rotation;
mapping.generalized_force_map = contact.J' * rotation;
end
