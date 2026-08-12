function contact = bed_supported_v1_contact(q, dq, h_hip, p, config)
%BED_SUPPORTED_V1_CONTACT Unilateral vertical Kelvin-Voigt bed abstraction.

points = bed_supported_v1_contact_points(q, dq, h_hip, p, config);
n = size(points.position_world, 2);
gap = points.position_world(2, :)-config.bed_plane_y_m;
penetration = max(-gap, 0);
penetration_rate = max(-points.velocity_world(2, :), 0);
normal_force = zeros(1, n);
if config.bed_enabled
    active = penetration > 0;
    normal_force(active) = max(0, config.k_bed_N_m*penetration(active)+ ...
        config.c_bed_Ns_m*penetration_rate(active));
else
    active = false(1, n);
end
tau = zeros(2, 1);
for index = 1:n
    tau = tau+points.J(:, :, index)'*[0; normal_force(index)];
end
contact = struct('points', points, 'gap_m', gap, ...
    'penetration_m', penetration, 'penetration_rate_m_s', ...
    penetration_rate, 'active', active, 'normal_force_N', normal_force, ...
    'total_normal_force_N', sum(normal_force), ...
    'generalized_torque_Nm', tau);
end
