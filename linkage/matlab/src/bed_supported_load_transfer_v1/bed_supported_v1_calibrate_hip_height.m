function calibration = bed_supported_v1_calibrate_hip_height(p, config)
%BED_SUPPORTED_V1_CALIBRATE_HIP_HEIGHT Deterministic initial support calibration.

q = deg2rad([5; 10]); dq = zeros(2, 1);
% Geometry is calibrated once against the nominal engineering bed. Softer and
% stiffer sensitivities retain the same hip height so stiffness is the only
% changed bed variable.
calibration_config = config;
calibration_config.k_bed_N_m = 3000;
calibration_config.c_bed_Ns_m = 55;
[~, ~, ~, G] = human_two_link_v2_dynamics_terms(q, dq, p);
passive = human_two_link_v2_passive_torque(q, dq, p);
tau_hold = G+passive;
mapping = single_arm_v2_force_map(q, dq, p);
h_values = linspace(config.calibration_h_range_m(1), ...
    config.calibration_h_range_m(2), config.calibration_samples);
scores = Inf(size(h_values));
robot_force = NaN(2, numel(h_values));
bed_total = NaN(size(h_values));
max_penetration = NaN(size(h_values));
leg_weight = (p.m1+p.m2)*p.g;
for index = 1:numel(h_values)
    bed = bed_supported_v1_contact(q, dq, h_values(index), p, ...
        calibration_config);
    max_penetration(index) = max(bed.penetration_m);
    if max_penetration(index) > config.calibration_max_penetration_m || ...
            bed.total_normal_force_N <= 0
        continue;
    end
    [u, solve] = single_arm_v2_stable_force_solve(mapping.A, ...
        tau_hold-bed.generalized_torque_Nm, config.svd_relative_tolerance);
    if solve.rank < 2 || any(~isfinite(u)), continue; end
    robot_force(:, index) = u;
    bed_total(index) = bed.total_normal_force_N;
    scores(index) = (norm(u)/100)^2+ ...
        ((bed_total(index)-leg_weight)/leg_weight)^2+ ...
        0.05*(max_penetration(index)/ ...
        config.calibration_max_penetration_m)^2;
end
[best_score, best_index] = min(scores);
if ~isfinite(best_score)
    error('BedSupportedV1:CalibrationFailed', ...
        'No hip height satisfies the fixed calibration constraints.');
end
h_hip = h_values(best_index);
bed = bed_supported_v1_contact(q, dq, h_hip, p, config);
[u, solve] = single_arm_v2_stable_force_solve(mapping.A, ...
    tau_hold-bed.generalized_torque_Nm, config.svd_relative_tolerance);
if solve.rank < 2
    error('BedSupportedV1:CalibrationRankLoss', ...
        'The initial robot force map lost rank during calibration.');
end
balance_residual = mapping.A*u+bed.generalized_torque_Nm-tau_hold;
calibration = struct('h_hip_m', h_hip, 'score', best_score, ...
    'q_initial_rad', q, 'bed', bed, 'robot_force_N', u, ...
    'robot_force_norm_N', norm(u), 'leg_weight_N', leg_weight, ...
    'tau_hold_Nm', tau_hold, ...
    'bed_generalized_torque_Nm', bed.generalized_torque_Nm, ...
    'balance_residual_Nm', balance_residual, ...
    'search_h_m', h_values, 'search_score', scores);
end
