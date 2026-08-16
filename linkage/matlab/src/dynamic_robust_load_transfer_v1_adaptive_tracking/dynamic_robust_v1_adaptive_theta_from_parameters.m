function theta = dynamic_robust_v1_adaptive_theta_from_parameters( ...
        nominal, parameters)
%DYNAMIC_ROBUST_V1_ADAPTIVE_THETA_FROM_PARAMETERS Post-hoc diagnostic map.
%
% Runtime identifier code does not call this function. It is used by replay
% and formal reporting to compare an estimate with a known simulation case.

human_two_link_v2_validate_parameters(nominal);
human_two_link_v2_validate_parameters(parameters);
theta=[parameters.body_mass_kg/nominal.body_mass_kg; ...
    parameters.lc1/nominal.lc1;parameters.lc2/nominal.lc2; ...
    parameters.K_passive(1,1)/nominal.K_passive(1,1); ...
    parameters.q_rest(:)-nominal.q_rest(:);parameters.sc/nominal.sc];
end
