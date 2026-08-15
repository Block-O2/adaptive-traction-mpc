function [xdot, details] = bed_supported_v1_dynamics(x, u_robot, h_hip, p, config)
%BED_SUPPORTED_V1_DYNAMICS V2 plant with separate robot and bed torques.

x = x(:); q = x(1:2); dq = x(3:4); u_robot = u_robot(:);
mapping = single_arm_v2_force_map(q, dq, p);
[M, h, C, G] = human_two_link_v2_dynamics_terms(q, dq, p);
[tau_passive, passive] = human_two_link_v2_passive_torque(q, dq, p);
bed = bed_supported_v1_contact(q, dq, h_hip, p, config);
tau_robot = mapping.A*u_robot;
rhs_total = tau_robot+bed.generalized_torque_Nm;
ddq = M\(rhs_total-h-G-tau_passive);
balance_residual = M*ddq+h+G+tau_passive-rhs_total;
xdot = [dq; ddq];
details = struct('M', M, 'h', h, 'C', C, 'G', G, ...
    'tau_passive_left', tau_passive, 'passive', passive, ...
    'mapping', mapping, 'robot_force_local_N', u_robot, ...
    'robot_force_world_N', mapping.rotation*u_robot, ...
    'tau_robot_Nm', tau_robot, 'bed', bed, ...
    'tau_bed_Nm', bed.generalized_torque_Nm, 'ddq', ddq, ...
    'balance_residual_Nm', balance_residual);
end
