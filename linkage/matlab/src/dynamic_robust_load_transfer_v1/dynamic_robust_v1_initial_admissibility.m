function report = dynamic_robust_v1_initial_admissibility( ...
        nominal, plant, calibration, config, controller_model)
%DYNAMIC_ROBUST_V1_INITIAL_ADMISSIBILITY Consistent case-start contract.
%
% The physical posture, velocity, hip height, bed, limits, and nominal
% task/supervisor baseline are shared by every case. Only the actuator force
% already present at t=0 is equilibrated against the selected true plant.
% CONTROLLER_MODEL defaults to NOMINAL; R2A may explicitly supply its fixed
% oracle model for the controller-only diagnostic path.

if nargin < 5 || isempty(controller_model), controller_model = nominal; end
human_two_link_v2_validate_parameters(controller_model);

q = calibration.q_initial_rad(:);
dq = zeros(2, 1);
x = [q; dq];
h_hip = calibration.h_hip_m;

bed = bed_supported_v1_contact(q, dq, h_hip, plant, config);
[~, true_passive] = human_two_link_v2_passive_torque(q, dq, plant);
[~, model_passive] = human_two_link_v2_passive_torque( ...
    q, dq, controller_model);
[~, ~, ~, true_gravity] = human_two_link_v2_dynamics_terms(q, dq, plant);
[model_mass, model_coriolis, ~, model_gravity] = ...
    human_two_link_v2_dynamics_terms(q, dq, controller_model);
true_mapping = single_arm_v2_force_map(q, dq, plant);
model_mapping = single_arm_v2_force_map(q, dq, controller_model);

true_hold_torque = true_gravity+ ...
    human_two_link_v2_passive_torque(q, dq, plant)- ...
    bed.generalized_torque_Nm;
[true_equilibrium_force, true_solve] = single_arm_v2_stable_force_solve( ...
    true_mapping.A, true_hold_torque, config.svd_relative_tolerance);
model_hold_torque = model_gravity+ ...
    human_two_link_v2_passive_torque(q, dq, controller_model)- ...
    bed.generalized_torque_Nm;
[model_equilibrium_force, model_solve] = single_arm_v2_stable_force_solve( ...
    model_mapping.A, model_hold_torque, config.svd_relative_tolerance);

fixed_reference = struct('q', q, 'dq', dq, 'ddq', zeros(2, 1));
[first_command, first_controller] = bed_supported_v1_robot_controller( ...
    q, dq, fixed_reference.q, fixed_reference.dq, fixed_reference.ddq, ...
    bed.generalized_torque_Nm, true_equilibrium_force, controller_model, ...
    config, 1, 1);
[legacy_command, ~] = bed_supported_v1_robot_controller( ...
    q, dq, fixed_reference.q, fixed_reference.dq, fixed_reference.ddq, ...
    bed.generalized_torque_Nm, calibration.robot_force_N, controller_model, ...
    config, 1, 1);

[true_equilibrium_xdot, true_equilibrium_dynamics] = ...
    bed_supported_v1_dynamics(x, true_equilibrium_force, h_hip, plant, config);
[true_first_xdot, ~] = bed_supported_v1_dynamics( ...
    x, first_command, h_hip, plant, config);
[legacy_true_xdot, ~] = bed_supported_v1_dynamics( ...
    x, legacy_command, h_hip, plant, config);
model_first_alpha = model_mass\(model_mapping.A*first_command+ ...
    bed.generalized_torque_Nm-model_coriolis-model_gravity- ...
    human_two_link_v2_passive_torque(q, dq, controller_model));

true_soft_lower = plant.q_min+plant.soft_limit_margin;
true_soft_upper = plant.q_max-plant.soft_limit_margin;
model_soft_lower = controller_model.q_min+controller_model.soft_limit_margin;
model_soft_upper = controller_model.q_max-controller_model.soft_limit_margin;
true_force_margin = min([true_equilibrium_force-config.u_min; ...
    config.u_max-true_equilibrium_force]);
first_force_margin = min([first_command-config.u_min; ...
    config.u_max-first_command]);
true_soft_violation = any(true_passive.soft.active) && ...
    norm(true_passive.soft_rhs, Inf)>config.soft_torque_tolerance_Nm;
model_soft_violation = any(model_passive.soft.active) && ...
    norm(model_passive.soft_rhs, Inf)>config.soft_torque_tolerance_Nm;
rom_violation = any(q<plant.q_min-config.rom_tolerance_rad | ...
    q>plant.q_max+config.rom_tolerance_rad);
bed_supported = bed.total_normal_force_N>=config.contact_force_threshold_N;
equilibrium_residual_ok = true_solve.rank==2 && ...
    true_solve.residual_norm<=config.plan_residual_tolerance_Nm && ...
    norm(true_equilibrium_dynamics.balance_residual_Nm, Inf)<= ...
    config.plan_residual_tolerance_Nm;
force_ok = true_force_margin>=-config.bound_tolerance_N && ...
    first_force_margin>=-config.bound_tolerance_N;

report = struct();
report.pass = all(isfinite([q; dq; true_equilibrium_force; first_command])) && ...
    ~rom_violation && ~true_soft_violation && bed_supported && ...
    equilibrium_residual_ok && force_ok;
report.q_rad = q;
report.q_deg = rad2deg(q);
report.dq_rad_s = dq;
report.dq_deg_s = rad2deg(dq);
report.true_rom_lower_margin_deg = rad2deg(q-plant.q_min);
report.true_rom_upper_margin_deg = rad2deg(plant.q_max-q);
report.true_soft_lower_start_deg = rad2deg(true_soft_lower);
report.true_soft_upper_start_deg = rad2deg(true_soft_upper);
report.true_soft_clearance_deg = rad2deg(min( ...
    q-true_soft_lower, true_soft_upper-q));
report.model_soft_clearance_deg = rad2deg(min( ...
    q-model_soft_lower, model_soft_upper-q));
report.true_soft_torque_Nm = true_passive.soft_rhs;
report.model_soft_torque_Nm = model_passive.soft_rhs;
report.soft_torque_tolerance_Nm = config.soft_torque_tolerance_Nm;
report.true_soft_violation = true_soft_violation;
report.model_soft_violation = model_soft_violation;
report.rom_violation = rom_violation;
report.bed_force_N = bed.total_normal_force_N;
report.bed_force_threshold_N = config.contact_force_threshold_N;
report.bed_supported = bed_supported;
report.true_equilibrium_force_N = true_equilibrium_force;
report.model_equilibrium_force_N = model_equilibrium_force;
report.legacy_nominal_calibration_force_N = calibration.robot_force_N;
report.first_command_force_N = first_command;
report.force_bound_N = config.force_bound_N;
report.true_equilibrium_force_margin_N = true_force_margin;
report.first_command_force_margin_N = first_force_margin;
report.true_equilibrium_residual_Nm = true_solve.residual;
report.model_equilibrium_residual_Nm = model_solve.residual;
report.true_equilibrium_alpha_deg_s2 = rad2deg(true_equilibrium_xdot(3:4));
report.true_first_command_alpha_deg_s2 = rad2deg(true_first_xdot(3:4));
report.model_first_command_alpha_deg_s2 = rad2deg(model_first_alpha);
report.legacy_true_first_alpha_deg_s2 = rad2deg(legacy_true_xdot(3:4));
report.first_command_force_rate_N_s = first_controller.force_rate_N_s;
report.initialization_uses_true_plant_only = true;
report.controller_model_parameters = controller_model;
end
