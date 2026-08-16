function vector = dynamic_robust_v1_parameter_vector(parameters)
%DYNAMIC_ROBUST_V1_PARAMETER_VECTOR Ordered numeric model fingerprint.

human_two_link_v2_validate_parameters(parameters);
fields = {'height_m','body_mass_kg','L1','L2','m1','m2','lc1','lc2', ...
    'I1','I2','g','sc','q_rest','K_passive','B_passive','q_min', ...
    'q_max','soft_limit_margin','soft_limit_numerical_tolerance', ...
    'soft_limit_boundary_torque_Nm','soft_limit_damping_Nms_rad'};
vector = zeros(0,1);
for index = 1:numel(fields)
    value = parameters.(fields{index});
    vector = [vector; value(:)]; %#ok<AGROW>
end
end
