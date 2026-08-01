function run_dynamics_consistency_checks()
% Deterministic consistency checks for the captured professor reference.
% The derived model below starts from the recorded kinematics and energies.

audit_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(audit_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'professor_reference_baseline');
workspace_path = fullfile(output_dir, 'workspace_numeric.mat');
s = load(workspace_path);

trajectory_q = s.state(1:2, :);
trajectory_dq = s.state(3:4, :);
trajectory = evaluate_state_set(trajectory_q, trajectory_dq, s);

q1_values = deg2rad([-5, 0, 15, 30, 45, 60, 75, 85]);
q2_values = deg2rad([-5, 0, 15, 30, 45, 60, 75, 90, 105, 120]);
dq1_values = deg2rad([-60, -30, 0, 30, 60]);
dq2_values = deg2rad([-80, -40, 0, 40, 80]);
[q1_grid, q2_grid, dq1_grid, dq2_grid] = ndgrid( ...
    q1_values, q2_values, dq1_values, dq2_values);
grid_q = [q1_grid(:)'; q2_grid(:)'];
grid_dq = [dq1_grid(:)'; dq2_grid(:)'];
fixed_grid = evaluate_state_set(grid_q, grid_dq, s);

torque = baseline_torque_decomposition(s);

audit = struct();
audit.matlab_version = version;
audit.generated_utc = char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX'));
audit.trajectory = trajectory;
audit.fixed_grid = fixed_grid;
audit.fixed_grid_definition = struct( ...
    'q1_deg', rad2deg(q1_values), ...
    'q2_deg', rad2deg(q2_values), ...
    'dq1_deg_s', rad2deg(dq1_values), ...
    'dq2_deg_s', rad2deg(dq2_values));
audit.torque = torque;

save(fullfile(output_dir, 'dynamics_consistency_results.mat'), ...
    'audit', '-v7.3');
write_report(fullfile(output_dir, 'dynamics_consistency_results.txt'), audit);
print_report(audit);
end


function result = evaluate_state_set(q_values, dq_values, s)
state_count = size(q_values, 2);
transform = diag([1, -1]);

derived_symmetry = zeros(1, state_count);
source_symmetry = zeros(1, state_count);
derived_min_eigenvalue = zeros(1, state_count);
source_min_eigenvalue = zeros(1, state_count);
derived_condition = zeros(1, state_count);
source_condition = zeros(1, state_count);
derived_skew_residual = zeros(1, state_count);
source_skew_residual = zeros(1, state_count);
potential_gradient_residual = zeros(1, state_count);
source_derived_mass_residual = zeros(1, state_count);
coordinate_equivalent_mass_residual = zeros(1, state_count);
source_derived_h_residual = zeros(1, state_count);
coordinate_equivalent_h_residual = zeros(1, state_count);
source_derived_gravity_residual = zeros(1, state_count);
source_negative_derived_gravity_residual = zeros(1, state_count);
attachment_display_velocity_arm1 = zeros(1, state_count);
attachment_display_velocity_arm2 = zeros(1, state_count);
attachment_display_normal_velocity_arm1 = zeros(1, state_count);
attachment_display_normal_velocity_arm2 = zeros(1, state_count);
normal_switch_state = false(1, state_count);

gradient_step = 1e-6;

for state_index = 1:state_count
    q = q_values(:, state_index);
    dq = dq_values(:, state_index);

    mass_derived = derived_mass(q, s);
    coriolis_derived = derived_coriolis(q, dq, s);
    h_derived = coriolis_derived * dq;
    gravity_derived = derived_gravity(q, s);
    mass_dot_derived = derived_mass_dot(q, dq, s);

    mass_source = source_mass(q, s);
    coriolis_source = source_coriolis(q, dq, s);
    h_source = coriolis_source * dq;
    gravity_source = source_gravity(q, s);
    mass_dot_source = source_mass_dot(q, dq, s);

    derived_symmetry(state_index) = max(abs( ...
        mass_derived - mass_derived'), [], 'all');
    source_symmetry(state_index) = max(abs( ...
        mass_source - mass_source'), [], 'all');
    derived_min_eigenvalue(state_index) = min(eig( ...
        (mass_derived + mass_derived') / 2));
    source_min_eigenvalue(state_index) = min(eig( ...
        (mass_source + mass_source') / 2));
    derived_condition(state_index) = cond(mass_derived);
    source_condition(state_index) = cond(mass_source);

    skew_derived = mass_dot_derived - 2*coriolis_derived;
    skew_source = mass_dot_source - 2*coriolis_source;
    derived_skew_residual(state_index) = max(abs( ...
        skew_derived + skew_derived'), [], 'all');
    source_skew_residual(state_index) = max(abs( ...
        skew_source + skew_source'), [], 'all');

    numerical_gradient = zeros(2, 1);
    for coordinate_index = 1:2
        perturbation = zeros(2, 1);
        perturbation(coordinate_index) = gradient_step;
        numerical_gradient(coordinate_index) = ( ...
            derived_potential(q + perturbation, s) - ...
            derived_potential(q - perturbation, s)) / (2*gradient_step);
    end
    potential_gradient_residual(state_index) = max(abs( ...
        numerical_gradient - gravity_derived));

    source_derived_mass_residual(state_index) = max(abs( ...
        mass_source - mass_derived), [], 'all');
    source_derived_h_residual(state_index) = max(abs( ...
        h_source - h_derived));
    source_derived_gravity_residual(state_index) = max(abs( ...
        gravity_source - gravity_derived));
    source_negative_derived_gravity_residual(state_index) = max(abs( ...
        gravity_source + gravity_derived));

    q_plus = transform * q;
    dq_plus = transform * dq;
    transformed_mass = transform' * source_mass(q_plus, s) * transform;
    transformed_coriolis = transform' * ...
        source_coriolis(q_plus, dq_plus, s) * transform;
    coordinate_equivalent_mass_residual(state_index) = max(abs( ...
        transformed_mass - mass_derived), [], 'all');
    coordinate_equivalent_h_residual(state_index) = max(abs( ...
        transformed_coriolis*dq - h_derived));

    [attach_j1, attach_j2, display_j1, display_j2, ...
        normal1, normal2, near_switch] = point_jacobians(q, s);
    attach_velocity1 = attach_j1 * dq;
    attach_velocity2 = attach_j2 * dq;
    display_velocity1 = display_j1 * dq;
    display_velocity2 = display_j2 * dq;
    velocity_difference1 = display_velocity1 - attach_velocity1;
    velocity_difference2 = display_velocity2 - attach_velocity2;
    attachment_display_velocity_arm1(state_index) = norm(velocity_difference1);
    attachment_display_velocity_arm2(state_index) = norm(velocity_difference2);
    attachment_display_normal_velocity_arm1(state_index) = ...
        abs(dot(velocity_difference1, normal1));
    attachment_display_normal_velocity_arm2(state_index) = ...
        abs(dot(velocity_difference2, normal2));
    normal_switch_state(state_index) = near_switch;
end

result = struct();
result.state_count = state_count;
result.max_derived_mass_symmetry_residual = max(derived_symmetry);
result.max_source_mass_symmetry_residual = max(source_symmetry);
result.min_derived_mass_eigenvalue = min(derived_min_eigenvalue);
result.min_source_mass_eigenvalue = min(source_min_eigenvalue);
result.derived_mass_condition_range = [ ...
    min(derived_condition), max(derived_condition)];
result.source_mass_condition_range = [ ...
    min(source_condition), max(source_condition)];
result.max_derived_skew_symmetry_residual = max(derived_skew_residual);
result.max_source_skew_symmetry_residual = max(source_skew_residual);
result.max_potential_gradient_residual_Nm = max(potential_gradient_residual);
result.max_source_derived_mass_residual = max(source_derived_mass_residual);
result.max_q2_transform_mass_residual = ...
    max(coordinate_equivalent_mass_residual);
result.max_source_derived_h_residual_Nm = max(source_derived_h_residual);
result.max_q2_transform_h_residual_Nm = ...
    max(coordinate_equivalent_h_residual);
result.max_source_derived_gravity_residual_Nm = ...
    max(source_derived_gravity_residual);
result.max_source_negative_derived_gravity_residual_Nm = ...
    max(source_negative_derived_gravity_residual);
result.max_attachment_display_velocity_difference_arm1_m_s = ...
    max(attachment_display_velocity_arm1);
result.max_attachment_display_velocity_difference_arm2_m_s = ...
    max(attachment_display_velocity_arm2);
result.max_attachment_display_normal_velocity_difference_arm1_m_s = ...
    max(attachment_display_normal_velocity_arm1);
result.max_attachment_display_normal_velocity_difference_arm2_m_s = ...
    max(attachment_display_normal_velocity_arm2);
result.normal_orientation_switch_state_count = sum(normal_switch_state);
end


function mass = derived_mass(q, s)
q2 = q(2);
b = s.I2 + s.m2*s.lc2^2;
d = s.m2*s.L1*s.lc2;
a11 = s.I1 + s.m1*s.lc1^2 + b + s.m2*s.L1^2;
mass = [a11 + 2*d*cos(q2), -(b + d*cos(q2)); ...
        -(b + d*cos(q2)), b];
end


function coriolis = derived_coriolis(q, dq, s)
q2 = q(2);
d = s.m2*s.L1*s.lc2;
sin_term = d*sin(q2);
coriolis = [ ...
    -sin_term*dq(2), sin_term*(dq(2) - dq(1)); ...
     sin_term*dq(1), 0];
end


function mass_dot = derived_mass_dot(q, dq, s)
q2 = q(2);
d = s.m2*s.L1*s.lc2;
sin_velocity = d*sin(q2)*dq(2);
mass_dot = [-2*sin_velocity, sin_velocity; sin_velocity, 0];
end


function potential = derived_potential(q, s)
q1 = q(1);
q2 = q(2);
potential = s.g * ((s.m1*s.lc1 + s.m2*s.L1)*sin(q1) + ...
    s.m2*s.lc2*sin(q1 - q2));
end


function gravity = derived_gravity(q, s)
q1 = q(1);
q2 = q(2);
gravity = [ ...
    s.g*((s.m1*s.lc1 + s.m2*s.L1)*cos(q1) + ...
        s.m2*s.lc2*cos(q1 - q2)); ...
    -s.m2*s.g*s.lc2*cos(q1 - q2)];
end


function mass = source_mass(q, s)
q2 = q(2);
b = s.I2 + s.m2*s.lc2^2;
d = s.m2*s.L1*s.lc2;
a11 = s.I1 + s.m1*s.lc1^2 + b + s.m2*s.L1^2;
mass = [a11 + 2*d*cos(q2), b + d*cos(q2); ...
        b + d*cos(q2), b];
end


function coriolis = source_coriolis(q, dq, s)
q2 = q(2);
h_scalar = -s.m2*s.L1*s.lc2*sin(q2);
coriolis = [ ...
    h_scalar*dq(2), h_scalar*(dq(1) + dq(2)); ...
    -h_scalar*dq(1), 0];
end


function mass_dot = source_mass_dot(q, dq, s)
q2 = q(2);
d = s.m2*s.L1*s.lc2;
sin_velocity = d*sin(q2)*dq(2);
mass_dot = [-2*sin_velocity, -sin_velocity; -sin_velocity, 0];
end


function gravity = source_gravity(q, s)
q1 = q(1);
q2 = q(2);
gravity = [ ...
    -s.m1*s.g*s.lc1*sin(q1) - s.m2*s.g * ...
        (s.L1*sin(q1) + s.lc2*sin(q1 - q2)); ...
    -s.m2*s.g*s.lc2*sin(q1 - q2)];
end


function [attach_j1, attach_j2, display_j1, display_j2, ...
        normal1, normal2, near_switch] = point_jacobians(q, s)
q1 = q(1);
q2 = q(2);
theta2 = q1 - q2;
e1 = [cos(q1); sin(q1)];
n1_unflipped = [-sin(q1); cos(q1)];
e2 = [cos(theta2); sin(theta2)];
n2_unflipped = [-sin(theta2); cos(theta2)];

sign1 = 1;
if n1_unflipped(2) < 0
    sign1 = -1;
end
sign2 = 1;
if n2_unflipped(2) < 0
    sign2 = -1;
end
normal1 = sign1*n1_unflipped;
normal2 = sign2*n2_unflipped;

attach_j1 = [ ...
    -s.s_attach1*sin(q1), 0; ...
     s.s_attach1*cos(q1), 0];
attach_j2 = [ ...
    -s.L1*sin(q1) - s.s_attach2*sin(theta2), ...
     s.s_attach2*sin(theta2); ...
     s.L1*cos(q1) + s.s_attach2*cos(theta2), ...
    -s.s_attach2*cos(theta2)];

display_j1 = attach_j1;
display_j1(:, 1) = display_j1(:, 1) - ...
    sign1*s.arm1_offset*e1;
display_j2 = attach_j2;
display_j2(:, 1) = display_j2(:, 1) - ...
    sign2*s.arm2_offset*e2;
display_j2(:, 2) = display_j2(:, 2) + ...
    sign2*s.arm2_offset*e2;

near_switch = abs(n1_unflipped(2)) < 1e-12 || ...
    abs(n2_unflipped(2)) < 1e-12;
end


function decomposition = baseline_torque_decomposition(s)
n_steps = size(s.state, 2) - 1;
gravity_compensation = zeros(2, n_steps);
computed_torque_feedforward = zeros(2, n_steps);
pd_feedback = zeros(2, n_steps);
arm1_generalized = zeros(2, n_steps);
arm2_generalized = zeros(2, n_steps);
safety = zeros(2, n_steps);
net_acceleration_driving = zeros(2, n_steps);
total_reconstruction_residual = zeros(2, n_steps);

for step_index = 1:n_steps
    q = s.state(1:2, step_index);
    dq = s.state(3:4, step_index);
    mass = source_mass(q, s);
    coriolis = source_coriolis(q, dq, s);
    q_ref = [s.hip_ref(step_index); s.knee_ref(step_index)];
    dq_ref = [s.dhip_ref(step_index); s.dknee_ref(step_index)];
    ddq_ref = [s.ddhip_ref(step_index); s.ddknee_ref(step_index)];

    gravity_compensation(:, step_index) = source_gravity(q, s);
    computed_torque_feedforward(:, step_index) = ...
        mass*ddq_ref + coriolis*dq_ref;
    pd_feedback(:, step_index) = ...
        -s.Kp*(q - q_ref) - s.Kd*(dq - dq_ref);

    [attach_j1, attach_j2] = point_jacobians(q, s);
    arm1_generalized(:, step_index) = ...
        attach_j1' * s.arm1_force_log(:, step_index + 1);
    arm2_generalized(:, step_index) = ...
        attach_j2' * s.arm2_force_log(:, step_index + 1);
    safety(:, step_index) = source_safety_torque(q, s);

    reconstructed_total = gravity_compensation(:, step_index) + ...
        computed_torque_feedforward(:, step_index) + ...
        pd_feedback(:, step_index) + arm1_generalized(:, step_index) + ...
        arm2_generalized(:, step_index) + safety(:, step_index);
    logged_total = [s.hip_torque(step_index + 1); ...
        s.knee_torque(step_index + 1)];
    total_reconstruction_residual(:, step_index) = ...
        reconstructed_total - logged_total;
    net_acceleration_driving(:, step_index) = ...
        logged_total - coriolis*dq - ...
        gravity_compensation(:, step_index);
end

decomposition = struct();
decomposition.transition_count = n_steps;
decomposition.gravity_compensation = torque_statistics(gravity_compensation);
decomposition.computed_torque_feedforward = ...
    torque_statistics(computed_torque_feedforward);
decomposition.pd_feedback = torque_statistics(pd_feedback);
decomposition.arm1_generalized = torque_statistics(arm1_generalized);
decomposition.arm2_generalized = torque_statistics(arm2_generalized);
decomposition.safety = torque_statistics(safety);
decomposition.net_acceleration_driving = ...
    torque_statistics(net_acceleration_driving);
decomposition.max_total_reconstruction_residual_Nm = ...
    max(abs(total_reconstruction_residual), [], 'all');
end


function tau_safety = source_safety_torque(q, s)
th1 = q(1);
th2 = q(2);
tau_safety = [0; 0];
if th1 > s.max_hip_flexion - s.safety_margin
    penetration = th1 - (s.max_hip_flexion - s.safety_margin);
    tau_safety(1) = tau_safety(1) - s.K_safety(1,1)*penetration;
elseif th1 < s.max_hip_extension + s.safety_margin
    penetration = th1 - (s.max_hip_extension + s.safety_margin);
    tau_safety(1) = tau_safety(1) - s.K_safety(1,1)*penetration;
end
if th2 > s.max_knee_flexion - s.safety_margin
    penetration = th2 - (s.max_knee_flexion - s.safety_margin);
    tau_safety(2) = tau_safety(2) - s.K_safety(2,2)*penetration;
elseif th2 < s.max_knee_hyperextension + s.safety_margin
    penetration = th2 - (s.max_knee_hyperextension + s.safety_margin);
    tau_safety(2) = tau_safety(2) - s.K_safety(2,2)*penetration;
end
if th1 < 20*pi/180
    max_allowed_knee = th1*s.max_knee_hip_ratio + 5*pi/180;
    if th2 > max_allowed_knee
        penetration = th2 - max_allowed_knee;
        tau_safety(2) = tau_safety(2) - ...
            s.K_safety(2,2)*1.5*penetration;
    end
end
if th1 > 40*pi/180 && th2 < s.min_knee_at_max_hip
    penetration = s.min_knee_at_max_hip - th2;
    tau_safety(2) = tau_safety(2) + ...
        s.K_safety(2,2)*0.8*penetration;
end
end


function statistics = torque_statistics(values)
statistics = struct();
statistics.hip_range_Nm = [min(values(1, :)), max(values(1, :))];
statistics.knee_range_Nm = [min(values(2, :)), max(values(2, :))];
statistics.hip_rms_Nm = sqrt(mean(values(1, :).^2));
statistics.knee_rms_Nm = sqrt(mean(values(2, :).^2));
statistics.max_vector_norm_Nm = max(vecnorm(values, 2, 1));
end


function write_report(path, audit)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not open dynamics report output.');
cleanup = onCleanup(@() fclose(output_file));
fprintf(output_file, 'MATLAB: %s\n', audit.matlab_version);
fprintf(output_file, 'Generated UTC: %s\n\n', audit.generated_utc);
write_state_set(output_file, 'CAPTURED BASELINE TRAJECTORY', audit.trajectory);
write_state_set(output_file, 'FIXED VALID-STATE GRID', audit.fixed_grid);
fprintf(output_file, 'GRID q1 [deg]: %s\n', ...
    mat2str(audit.fixed_grid_definition.q1_deg));
fprintf(output_file, 'GRID q2 [deg]: %s\n', ...
    mat2str(audit.fixed_grid_definition.q2_deg));
fprintf(output_file, 'GRID dq1 [deg/s]: %s\n', ...
    mat2str(audit.fixed_grid_definition.dq1_deg_s));
fprintf(output_file, 'GRID dq2 [deg/s]: %s\n\n', ...
    mat2str(audit.fixed_grid_definition.dq2_deg_s));
write_torque(output_file, audit.torque);
end


function write_state_set(output_file, label, r)
fprintf(output_file, '%s\n', label);
fprintf(output_file, 'states: %d\n', r.state_count);
fprintf(output_file, 'derived/source M symmetry residual: %.17g / %.17g\n', ...
    r.max_derived_mass_symmetry_residual, r.max_source_mass_symmetry_residual);
fprintf(output_file, 'derived/source min eigenvalue: %.17g / %.17g\n', ...
    r.min_derived_mass_eigenvalue, r.min_source_mass_eigenvalue);
fprintf(output_file, 'derived M condition range: [%.17g, %.17g]\n', ...
    r.derived_mass_condition_range);
fprintf(output_file, 'source M condition range: [%.17g, %.17g]\n', ...
    r.source_mass_condition_range);
fprintf(output_file, 'derived/source skew residual: %.17g / %.17g\n', ...
    r.max_derived_skew_symmetry_residual, ...
    r.max_source_skew_symmetry_residual);
fprintf(output_file, 'potential gradient residual [N m]: %.17g\n', ...
    r.max_potential_gradient_residual_Nm);
fprintf(output_file, 'source-derived M residual: %.17g\n', ...
    r.max_source_derived_mass_residual);
fprintf(output_file, 'q2-transform M residual: %.17g\n', ...
    r.max_q2_transform_mass_residual);
fprintf(output_file, 'source-derived C*dq residual [N m]: %.17g\n', ...
    r.max_source_derived_h_residual_Nm);
fprintf(output_file, 'q2-transform C*dq residual [N m]: %.17g\n', ...
    r.max_q2_transform_h_residual_Nm);
fprintf(output_file, 'source-derived gravity residual [N m]: %.17g\n', ...
    r.max_source_derived_gravity_residual_Nm);
fprintf(output_file, 'source+derived gravity residual [N m]: %.17g\n', ...
    r.max_source_negative_derived_gravity_residual_Nm);
fprintf(output_file, 'attachment-display velocity difference arm1/arm2 [m/s]: %.17g / %.17g\n', ...
    r.max_attachment_display_velocity_difference_arm1_m_s, ...
    r.max_attachment_display_velocity_difference_arm2_m_s);
fprintf(output_file, 'attachment-display normal velocity difference arm1/arm2 [m/s]: %.17g / %.17g\n', ...
    r.max_attachment_display_normal_velocity_difference_arm1_m_s, ...
    r.max_attachment_display_normal_velocity_difference_arm2_m_s);
fprintf(output_file, 'normal switch states: %d\n\n', ...
    r.normal_orientation_switch_state_count);
end


function write_torque(output_file, torque)
fprintf(output_file, 'BASELINE TORQUE DECOMPOSITION\n');
fprintf(output_file, 'transitions: %d\n', torque.transition_count);
names = {'gravity_compensation', 'computed_torque_feedforward', ...
    'pd_feedback', 'arm1_generalized', 'arm2_generalized', 'safety', ...
    'net_acceleration_driving'};
for name_index = 1:numel(names)
    name = names{name_index};
    stats = torque.(name);
    fprintf(output_file, '%s: hip=[%.17g, %.17g], knee=[%.17g, %.17g], rms=[%.17g, %.17g], max_norm=%.17g N m\n', ...
        name, stats.hip_range_Nm, stats.knee_range_Nm, ...
        stats.hip_rms_Nm, stats.knee_rms_Nm, stats.max_vector_norm_Nm);
end
fprintf(output_file, 'max total reconstruction residual [N m]: %.17g\n', ...
    torque.max_total_reconstruction_residual_Nm);
end


function print_report(audit)
fprintf('DYNAMICS CONSISTENCY CHECKS BEGIN\n');
write_state_set(1, 'CAPTURED BASELINE TRAJECTORY', audit.trajectory);
write_state_set(1, 'FIXED VALID-STATE GRID', audit.fixed_grid);
write_torque(1, audit.torque);
fprintf('DYNAMICS CONSISTENCY CHECKS END\n');
end
