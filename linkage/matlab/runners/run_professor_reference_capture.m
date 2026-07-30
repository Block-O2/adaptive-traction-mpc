function run_professor_reference_capture()
% External, non-invasive runner for the preserved professor reference.

runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
source_path = fullfile(repo_root, 'linkage', 'matlab', 'reference', ...
    'professor_original', 'singleArmDual.m');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'professor_reference_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

fprintf('CAPTURE MATLAB VERSION: %s\n', version);
fprintf('CAPTURE SOURCE: %s\n', source_path);
fprintf('CAPTURE OUTPUT: %s\n', output_dir);
fprintf('CAPTURE START UTC: %s\n', ...
    char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX')));

execution_completed = false;
runtime_error_report = '';

try
    run(source_path);
    execution_completed = true;
catch caught_error
    execution_completed = false;
    runtime_error_report = getReport(caught_error, 'extended', 'hyperlinks', 'off');
    fprintf(2, 'CAPTURE RUNTIME ERROR:\n%s\n', runtime_error_report);
end

% The reference begins with clear, so reconstruct runner paths after it returns.
if ~exist('execution_completed', 'var')
    execution_completed = false;
end
if ~exist('runtime_error_report', 'var')
    runtime_error_report = '';
end
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
source_path = fullfile(repo_root, 'linkage', 'matlab', 'reference', ...
    'professor_original', 'singleArmDual.m');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'professor_reference_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
workspace_path = fullfile(output_dir, 'workspace_numeric.mat');
runtime_error_path = fullfile(output_dir, 'runtime_error.txt');

error_file = fopen(runtime_error_path, 'w');
if error_file >= 0
    if execution_completed
        fprintf(error_file, 'NONE\n');
    else
        fprintf(error_file, '%s\n', runtime_error_report);
    end
    fclose(error_file);
end

% Save all workspace values that are data rather than live graphics handles.
capture_execution_completed = execution_completed;
capture_runtime_error_report = runtime_error_report;
workspace_items = whos;
workspace_names = {};
runner_internal_names = {'runner_dir', 'repo_root', 'source_path', ...
    'runner_internal_names'};
for item_index = 1:numel(workspace_items)
    item_name = workspace_items(item_index).name;
    if ismember(item_name, runner_internal_names)
        continue;
    end
    item_value = eval(item_name);
    if isnumeric(item_value) || islogical(item_value) || ischar(item_value) || ...
            isstring(item_value) || isstruct(item_value) || iscell(item_value) || ...
            isdatetime(item_value)
        workspace_names{end + 1} = item_name; %#ok<AGROW>
    end
end
save(workspace_path, workspace_names{:}, '-v7.3');
fprintf('CAPTURE WORKSPACE SAVED: %s (%d variables)\n', ...
    workspace_path, numel(workspace_names));

% Save every figure that exists, including partially initialized figures.
figure_handles = findall(groot, 'Type', 'figure');
if ~isempty(figure_handles)
    [~, figure_order] = sort(arrayfun(@(h) h.Number, figure_handles));
    figure_handles = figure_handles(figure_order);
end

manifest_path = fullfile(output_dir, 'figure_manifest.tsv');
manifest_file = fopen(manifest_path, 'w');
if manifest_file >= 0
    fprintf(manifest_file, 'index\tnumber\tname\tfig_saved\tpng_saved\n');
end

figure_save_failures = {};
for figure_index = 1:numel(figure_handles)
    figure_handle = figure_handles(figure_index);
    figure_number = figure_handle.Number;
    figure_name = string(figure_handle.Name);
    fig_path = fullfile(output_dir, sprintf('figure_%02d.fig', figure_index));
    png_path = fullfile(output_dir, sprintf('figure_%02d.png', figure_index));
    fig_saved = false;
    png_saved = false;

    try
        savefig(figure_handle, fig_path);
        fig_saved = true;
    catch figure_error
        figure_save_failures{end + 1} = sprintf( ... %#ok<AGROW>
            'FIG %d savefig: %s', figure_index, figure_error.message);
    end

    try
        exportgraphics(figure_handle, png_path, 'Resolution', 160);
        png_saved = true;
    catch figure_error
        figure_save_failures{end + 1} = sprintf( ... %#ok<AGROW>
            'FIG %d exportgraphics: %s', figure_index, figure_error.message);
    end

    if manifest_file >= 0
        fprintf(manifest_file, '%d\t%d\t%s\t%d\t%d\n', figure_index, ...
            figure_number, char(figure_name), fig_saved, png_saved);
    end
end
if manifest_file >= 0
    fclose(manifest_file);
end

fprintf('CAPTURE FIGURE COUNT: %d\n', numel(figure_handles));
for failure_index = 1:numel(figure_save_failures)
    fprintf(2, 'CAPTURE FIGURE SAVE WARNING: %s\n', ...
        figure_save_failures{failure_index});
end

% Compute diagnostics only from the workspace produced by the preserved script.
diagnostics_available = false;
diagnostics_error_report = '';
try
    workspace_data = load(workspace_path);
    diagnostics = compute_reference_diagnostics(workspace_data);
    diagnostics_available = true;
    save(fullfile(output_dir, 'numerical_diagnostics.mat'), ...
        'diagnostics', '-v7.3');
    write_diagnostics_text(fullfile(output_dir, 'numerical_diagnostics.txt'), ...
        diagnostics);
    print_diagnostics(diagnostics);
catch diagnostics_error
    diagnostics_error_report = getReport(diagnostics_error, ...
        'extended', 'hyperlinks', 'off');
    fprintf(2, 'CAPTURE DIAGNOSTICS ERROR:\n%s\n', diagnostics_error_report);
end

capture_status = struct();
capture_status.matlab_version = version;
capture_status.execution_completed = execution_completed;
capture_status.runtime_error_report = runtime_error_report;
capture_status.figure_count = numel(figure_handles);
capture_status.figure_save_failures = figure_save_failures;
capture_status.workspace_path = workspace_path;
capture_status.diagnostics_available = diagnostics_available;
capture_status.diagnostics_error_report = diagnostics_error_report;
capture_status.finished_utc = char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX'));
save(fullfile(output_dir, 'capture_status.mat'), 'capture_status');

fprintf('CAPTURE EXECUTION COMPLETED: %d\n', execution_completed);
fprintf('CAPTURE DIAGNOSTICS AVAILABLE: %d\n', diagnostics_available);
fprintf('CAPTURE FINISH UTC: %s\n', capture_status.finished_utc);

if ~execution_completed
    error('ProfessorReference:ExecutionFailed', ...
        'The preserved reference raised a runtime error. See runtime_error.txt.');
end
if ~diagnostics_available
    error('ProfessorReference:DiagnosticsFailed', ...
        'The reference ran, but diagnostics failed. See console output.');
end
end


function diagnostics = compute_reference_diagnostics(s)
required = {'state', 't', 'dt', 'N', 'L1', 'L2', 'm1', 'm2', ...
    'lc1', 'lc2', 'I1', 'I2', 'g', 's_attach1', 's_attach2', ...
    'arm1_offset', 'arm2_offset', 'arm1_stiffness', 'arm2_stiffness', ...
    'arm1_damping', 'arm2_damping', 'max_hip_velocity', ...
    'max_knee_velocity', 'max_hip_flexion', 'max_hip_extension', ...
    'max_knee_flexion', 'max_knee_hyperextension', 'safety_margin', ...
    'max_knee_hip_ratio', 'min_knee_at_max_hip', 'K_safety', ...
    'Kp', 'Kd', 'hip_ref', 'knee_ref', 'dhip_ref', 'dknee_ref', ...
    'ddhip_ref', 'ddknee_ref', 'hip_torque', 'knee_torque', ...
    'arm1_force_log', 'arm2_force_log', 'constraint_violation_log', ...
    'hip_angle', 'knee_angle'};
for required_index = 1:numel(required)
    assert(isfield(s, required{required_index}), ...
        'Missing required workspace variable: %s', required{required_index});
end

n_steps = size(s.state, 2) - 1;
assert(n_steps == s.N - 1, 'Unexpected state length.');

spring_error_1 = zeros(1, n_steps);
spring_error_2 = zeros(1, n_steps);
stiffness_scalar_1 = zeros(1, n_steps);
stiffness_scalar_2 = zeros(1, n_steps);
damping_scalar_1 = zeros(1, n_steps);
damping_scalar_2 = zeros(1, n_steps);
stiffness_cartesian_1 = zeros(2, n_steps);
stiffness_cartesian_2 = zeros(2, n_steps);
damping_cartesian_1 = zeros(2, n_steps);
damping_cartesian_2 = zeros(2, n_steps);
mass_min_eigenvalue = zeros(1, n_steps);
mass_condition_number = zeros(1, n_steps);
gravity_norm = zeros(1, n_steps);
gravity_cancellation_residual = zeros(2, n_steps);
logged_torque_reconstruction_residual = zeros(2, n_steps);
safety_torque = zeros(2, n_steps);
velocity_clip_hip = false(1, n_steps);
velocity_clip_knee = false(1, n_steps);
angle_clip_hip = false(1, n_steps);
angle_clip_knee = false(1, n_steps);
force_reconstruction_residual_1 = zeros(1, n_steps);
force_reconstruction_residual_2 = zeros(1, n_steps);

for step_index = 1:n_steps
    th1 = s.state(1, step_index);
    th2 = s.state(2, step_index);
    dth1 = s.state(3, step_index);
    dth2 = s.state(4, step_index);
    dq = [dth1; dth2];
    ankle_angle = th1 - th2;

    thigh_dir = [cos(th1); sin(th1)];
    thigh_normal = [-sin(th1); cos(th1)];
    if thigh_normal(2) < 0
        thigh_normal = -thigh_normal;
    end
    attach1_pos = s.s_attach1 * thigh_dir;
    arm1_end_pos = attach1_pos + s.arm1_offset * thigh_normal;
    current_offset1 = dot(arm1_end_pos - attach1_pos, thigh_normal);
    spring_error_1(step_index) = s.arm1_offset - current_offset1;

    shank_dir = [cos(ankle_angle); sin(ankle_angle)];
    shank_normal = [-sin(ankle_angle); cos(ankle_angle)];
    if shank_normal(2) < 0
        shank_normal = -shank_normal;
    end
    knee_pos = s.L1 * thigh_dir;
    attach2_pos = knee_pos + s.s_attach2 * shank_dir;
    arm2_end_pos = attach2_pos + s.arm2_offset * shank_normal;
    current_offset2 = dot(arm2_end_pos - attach2_pos, shank_normal);
    spring_error_2(step_index) = s.arm2_offset - current_offset2;

    j1 = [-s.s_attach1 * sin(th1), 0; ...
           s.s_attach1 * cos(th1), 0];
    j2 = [-s.L1*sin(th1) - s.s_attach2*sin(ankle_angle), ...
           s.s_attach2*sin(ankle_angle); ...
           s.L1*cos(th1) + s.s_attach2*cos(ankle_angle), ...
          -s.s_attach2*cos(ankle_angle)];

    vel_normal1 = dot(j1 * dq, thigh_normal);
    vel_normal2 = dot(j2 * dq, shank_normal);
    stiffness_scalar_1(step_index) = ...
        s.arm1_stiffness * spring_error_1(step_index);
    stiffness_scalar_2(step_index) = ...
        s.arm2_stiffness * spring_error_2(step_index);
    damping_scalar_1(step_index) = -s.arm1_damping * vel_normal1;
    damping_scalar_2(step_index) = -s.arm2_damping * vel_normal2;
    stiffness_cartesian_1(:, step_index) = ...
        stiffness_scalar_1(step_index) * thigh_normal;
    stiffness_cartesian_2(:, step_index) = ...
        stiffness_scalar_2(step_index) * shank_normal;
    damping_cartesian_1(:, step_index) = ...
        damping_scalar_1(step_index) * thigh_normal;
    damping_cartesian_2(:, step_index) = ...
        damping_scalar_2(step_index) * shank_normal;

    force_scalar1 = max(min(stiffness_scalar_1(step_index) + ...
        damping_scalar_1(step_index), 500), -500);
    force_scalar2 = max(min(stiffness_scalar_2(step_index) + ...
        damping_scalar_2(step_index), 400), -400);
    force_reconstruction_residual_1(step_index) = norm( ...
        force_scalar1 * thigh_normal - s.arm1_force_log(:, step_index + 1));
    force_reconstruction_residual_2(step_index) = norm( ...
        force_scalar2 * shank_normal - s.arm2_force_log(:, step_index + 1));

    mass_matrix = diagnostic_inertia(th2, s);
    coriolis_matrix = diagnostic_coriolis(th2, dth1, dth2, s);
    eigenvalues = eig((mass_matrix + mass_matrix') / 2);
    mass_min_eigenvalue(step_index) = min(eigenvalues);
    mass_condition_number(step_index) = cond(mass_matrix);

    tau_gravity = [ ...
        -s.m1*s.g*s.lc1*sin(th1) - s.m2*s.g * ...
            (s.L1*sin(th1) + s.lc2*sin(ankle_angle)); ...
        -s.m2*s.g*s.lc2*sin(ankle_angle)];
    gravity_norm(step_index) = norm(tau_gravity);

    tau_safety = diagnostic_safety_torque(th1, th2, s);
    safety_torque(:, step_index) = tau_safety;

    q_ref = [s.hip_ref(step_index); s.knee_ref(step_index)];
    dq_ref = [s.dhip_ref(step_index); s.dknee_ref(step_index)];
    ddq_ref = [s.ddhip_ref(step_index); s.ddknee_ref(step_index)];
    q = [th1; th2];
    tau_ff = mass_matrix * ddq_ref + coriolis_matrix * dq_ref;
    tau_fb = -s.Kp * (q - q_ref) - s.Kd * (dq - dq_ref);
    tau_arm1 = j1' * s.arm1_force_log(:, step_index + 1);
    tau_arm2 = j2' * s.arm2_force_log(:, step_index + 1);

    rhs_as_coded = tau_gravity + tau_ff + tau_fb + tau_arm1 + ...
        tau_arm2 + tau_safety - coriolis_matrix*dq - tau_gravity;
    rhs_after_cancellation = tau_ff + tau_fb + tau_arm1 + ...
        tau_arm2 + tau_safety - coriolis_matrix*dq;
    gravity_cancellation_residual(:, step_index) = ...
        rhs_as_coded - rhs_after_cancellation;

    reconstructed_total_torque = tau_gravity + tau_ff + tau_fb + ...
        tau_arm1 + tau_arm2 + tau_safety;
    logged_total_torque = [s.hip_torque(step_index + 1); ...
        s.knee_torque(step_index + 1)];
    logged_torque_reconstruction_residual(:, step_index) = ...
        reconstructed_total_torque - logged_total_torque;

    acceleration = mass_matrix \ (logged_total_torque - ...
        coriolis_matrix*dq - tau_gravity);
    raw_velocity = dq + acceleration * s.dt;
    velocity_clip_hip(step_index) = raw_velocity(1) > s.max_hip_velocity || ...
        raw_velocity(1) < -s.max_hip_velocity;
    velocity_clip_knee(step_index) = raw_velocity(2) > s.max_knee_velocity || ...
        raw_velocity(2) < -s.max_knee_velocity;
    clipped_velocity = [ ...
        max(min(raw_velocity(1), s.max_hip_velocity), -s.max_hip_velocity); ...
        max(min(raw_velocity(2), s.max_knee_velocity), -s.max_knee_velocity)];
    raw_angle = q + clipped_velocity * s.dt;
    angle_clip_hip(step_index) = raw_angle(1) > s.max_hip_flexion || ...
        raw_angle(1) < s.max_hip_extension;
    angle_clip_knee(step_index) = raw_angle(2) > s.max_knee_flexion || ...
        raw_angle(2) < s.max_knee_hyperextension;
end

diagnostics = struct();
diagnostics.sample_count = s.N;
diagnostics.transition_count = n_steps;
diagnostics.spring_error_arm1_range_m = range_pair(spring_error_1);
diagnostics.spring_error_arm2_range_m = range_pair(spring_error_2);
diagnostics.stiffness_normal_arm1_range_N = range_pair(stiffness_scalar_1);
diagnostics.stiffness_normal_arm2_range_N = range_pair(stiffness_scalar_2);
diagnostics.damping_normal_arm1_range_N = range_pair(damping_scalar_1);
diagnostics.damping_normal_arm2_range_N = range_pair(damping_scalar_2);
diagnostics.stiffness_cartesian_arm1_range_N = row_ranges(stiffness_cartesian_1);
diagnostics.stiffness_cartesian_arm2_range_N = row_ranges(stiffness_cartesian_2);
diagnostics.damping_cartesian_arm1_range_N = row_ranges(damping_cartesian_1);
diagnostics.damping_cartesian_arm2_range_N = row_ranges(damping_cartesian_2);
diagnostics.max_force_reconstruction_residual_arm1_N = ...
    max(force_reconstruction_residual_1);
diagnostics.max_force_reconstruction_residual_arm2_N = ...
    max(force_reconstruction_residual_2);
diagnostics.coded_gravity_norm_range_Nm = range_pair(gravity_norm);
diagnostics.max_gravity_cancellation_residual_Nm = ...
    max(abs(gravity_cancellation_residual), [], 'all');
diagnostics.max_logged_torque_reconstruction_residual_Nm = ...
    max(abs(logged_torque_reconstruction_residual), [], 'all');
diagnostics.mass_matrix_min_eigenvalue = min(mass_min_eigenvalue);
diagnostics.mass_matrix_max_condition_number = max(mass_condition_number);
diagnostics.mass_matrix_min_condition_number = min(mass_condition_number);
diagnostics.velocity_clip_hip_count = sum(velocity_clip_hip);
diagnostics.velocity_clip_knee_count = sum(velocity_clip_knee);
diagnostics.velocity_clip_any_transition_count = ...
    sum(velocity_clip_hip | velocity_clip_knee);
diagnostics.velocity_clip_any_transition_fraction = ...
    diagnostics.velocity_clip_any_transition_count / n_steps;
diagnostics.angle_clip_hip_count = sum(angle_clip_hip);
diagnostics.angle_clip_knee_count = sum(angle_clip_knee);
diagnostics.angle_clip_any_transition_count = ...
    sum(angle_clip_hip | angle_clip_knee);
diagnostics.angle_clip_any_transition_fraction = ...
    diagnostics.angle_clip_any_transition_count / n_steps;
diagnostics.safety_torque_any_transition_count = ...
    sum(any(abs(safety_torque) > 0, 1));
diagnostics.safety_torque_hip_transition_count = ...
    sum(abs(safety_torque(1, :)) > 0);
diagnostics.safety_torque_knee_transition_count = ...
    sum(abs(safety_torque(2, :)) > 0);
diagnostics.safety_log_activation_count = ...
    sum(s.constraint_violation_log > 0);
diagnostics.hip_angle_range_deg = range_pair(s.hip_angle * 180/pi);
diagnostics.knee_angle_range_deg = range_pair(s.knee_angle * 180/pi);
force1_magnitude = vecnorm(s.arm1_force_log, 2, 1);
force2_magnitude = vecnorm(s.arm2_force_log, 2, 1);
diagnostics.arm1_max_force_N = max(force1_magnitude);
diagnostics.arm2_max_force_N = max(force2_magnitude);
diagnostics.hip_max_tracking_error_deg = ...
    max(abs(s.hip_angle - s.hip_ref)) * 180/pi;
diagnostics.knee_max_tracking_error_deg = ...
    max(abs(s.knee_angle - s.knee_ref)) * 180/pi;

diagnostics.timeseries = struct();
diagnostics.timeseries.transition_time_s = s.t(1:n_steps);
diagnostics.timeseries.spring_error_arm1_m = spring_error_1;
diagnostics.timeseries.spring_error_arm2_m = spring_error_2;
diagnostics.timeseries.stiffness_normal_arm1_N = stiffness_scalar_1;
diagnostics.timeseries.stiffness_normal_arm2_N = stiffness_scalar_2;
diagnostics.timeseries.damping_normal_arm1_N = damping_scalar_1;
diagnostics.timeseries.damping_normal_arm2_N = damping_scalar_2;
diagnostics.timeseries.mass_min_eigenvalue = mass_min_eigenvalue;
diagnostics.timeseries.mass_condition_number = mass_condition_number;
diagnostics.timeseries.gravity_norm_Nm = gravity_norm;
diagnostics.timeseries.gravity_cancellation_residual_Nm = ...
    gravity_cancellation_residual;
diagnostics.timeseries.velocity_clip_hip = velocity_clip_hip;
diagnostics.timeseries.velocity_clip_knee = velocity_clip_knee;
diagnostics.timeseries.angle_clip_hip = angle_clip_hip;
diagnostics.timeseries.angle_clip_knee = angle_clip_knee;
diagnostics.timeseries.safety_torque_Nm = safety_torque;
end


function mass_matrix = diagnostic_inertia(th2, s)
mass_matrix_11 = s.I1 + s.I2 + s.m1*s.lc1^2 + ...
    s.m2*(s.L1^2 + s.lc2^2 + 2*s.L1*s.lc2*cos(th2));
mass_matrix_12 = s.I2 + s.m2*(s.lc2^2 + s.L1*s.lc2*cos(th2));
mass_matrix_22 = s.I2 + s.m2*s.lc2^2;
mass_matrix = [mass_matrix_11, mass_matrix_12; ...
    mass_matrix_12, mass_matrix_22];
end


function coriolis_matrix = diagnostic_coriolis(th2, dth1, dth2, s)
h = -s.m2 * s.L1 * s.lc2 * sin(th2);
coriolis_matrix = [h*dth2, h*(dth1+dth2); -h*dth1, 0];
end


function tau_safety = diagnostic_safety_torque(th1, th2, s)
tau_safety = [0; 0];
if th1 > s.max_hip_flexion - s.safety_margin
    penetration = th1 - (s.max_hip_flexion - s.safety_margin);
    tau_safety(1) = tau_safety(1) - s.K_safety(1,1) * penetration;
elseif th1 < s.max_hip_extension + s.safety_margin
    penetration = th1 - (s.max_hip_extension + s.safety_margin);
    tau_safety(1) = tau_safety(1) - s.K_safety(1,1) * penetration;
end
if th2 > s.max_knee_flexion - s.safety_margin
    penetration = th2 - (s.max_knee_flexion - s.safety_margin);
    tau_safety(2) = tau_safety(2) - s.K_safety(2,2) * penetration;
elseif th2 < s.max_knee_hyperextension + s.safety_margin
    penetration = th2 - (s.max_knee_hyperextension + s.safety_margin);
    tau_safety(2) = tau_safety(2) - s.K_safety(2,2) * penetration;
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


function output = range_pair(values)
output = [min(values, [], 'all'), max(values, [], 'all')];
end


function output = row_ranges(values)
output = [min(values, [], 2), max(values, [], 2)];
end


function write_diagnostics_text(path, d)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not open diagnostics text output.');
cleanup = onCleanup(@() fclose(output_file));
fprintf(output_file, 'Samples: %d\n', d.sample_count);
fprintf(output_file, 'Transitions: %d\n', d.transition_count);
fprintf(output_file, 'Spring error arm 1 range [m]: [%.17g, %.17g]\n', ...
    d.spring_error_arm1_range_m);
fprintf(output_file, 'Spring error arm 2 range [m]: [%.17g, %.17g]\n', ...
    d.spring_error_arm2_range_m);
fprintf(output_file, 'Stiffness normal arm 1 range [N]: [%.17g, %.17g]\n', ...
    d.stiffness_normal_arm1_range_N);
fprintf(output_file, 'Stiffness normal arm 2 range [N]: [%.17g, %.17g]\n', ...
    d.stiffness_normal_arm2_range_N);
fprintf(output_file, 'Damping normal arm 1 range [N]: [%.17g, %.17g]\n', ...
    d.damping_normal_arm1_range_N);
fprintf(output_file, 'Damping normal arm 2 range [N]: [%.17g, %.17g]\n', ...
    d.damping_normal_arm2_range_N);
fprintf(output_file, 'Coded gravity norm range [N m]: [%.17g, %.17g]\n', ...
    d.coded_gravity_norm_range_Nm);
fprintf(output_file, 'Max gravity cancellation residual [N m]: %.17g\n', ...
    d.max_gravity_cancellation_residual_Nm);
fprintf(output_file, 'Mass matrix minimum eigenvalue: %.17g\n', ...
    d.mass_matrix_min_eigenvalue);
fprintf(output_file, 'Mass matrix condition number range: [%.17g, %.17g]\n', ...
    d.mass_matrix_min_condition_number, d.mass_matrix_max_condition_number);
fprintf(output_file, 'Velocity clips hip/knee/any: %d / %d / %d (%.9f%%)\n', ...
    d.velocity_clip_hip_count, d.velocity_clip_knee_count, ...
    d.velocity_clip_any_transition_count, ...
    100*d.velocity_clip_any_transition_fraction);
fprintf(output_file, 'Angle clips hip/knee/any: %d / %d / %d (%.9f%%)\n', ...
    d.angle_clip_hip_count, d.angle_clip_knee_count, ...
    d.angle_clip_any_transition_count, ...
    100*d.angle_clip_any_transition_fraction);
fprintf(output_file, 'Safety torque activations any/hip/knee: %d / %d / %d\n', ...
    d.safety_torque_any_transition_count, ...
    d.safety_torque_hip_transition_count, ...
    d.safety_torque_knee_transition_count);
fprintf(output_file, 'Safety log activation count: %d\n', ...
    d.safety_log_activation_count);
fprintf(output_file, 'Hip angle range [deg]: [%.9f, %.9f]\n', ...
    d.hip_angle_range_deg);
fprintf(output_file, 'Knee angle range [deg]: [%.9f, %.9f]\n', ...
    d.knee_angle_range_deg);
fprintf(output_file, 'Maximum arm forces [N]: %.9f / %.9f\n', ...
    d.arm1_max_force_N, d.arm2_max_force_N);
fprintf(output_file, 'Maximum tracking errors [deg]: %.9f / %.9f\n', ...
    d.hip_max_tracking_error_deg, d.knee_max_tracking_error_deg);
end


function print_diagnostics(d)
fprintf('CAPTURE DIAGNOSTICS BEGIN\n');
fprintf('  spring errors [m]: arm1=[%.17g, %.17g] arm2=[%.17g, %.17g]\n', ...
    d.spring_error_arm1_range_m, d.spring_error_arm2_range_m);
fprintf('  stiffness normal [N]: arm1=[%.17g, %.17g] arm2=[%.17g, %.17g]\n', ...
    d.stiffness_normal_arm1_range_N, d.stiffness_normal_arm2_range_N);
fprintf('  damping normal [N]: arm1=[%.17g, %.17g] arm2=[%.17g, %.17g]\n', ...
    d.damping_normal_arm1_range_N, d.damping_normal_arm2_range_N);
fprintf('  gravity norm [N m]=[%.17g, %.17g], cancellation residual=%.17g\n', ...
    d.coded_gravity_norm_range_Nm, ...
    d.max_gravity_cancellation_residual_Nm);
fprintf('  M min eigenvalue=%.17g, cond range=[%.17g, %.17g]\n', ...
    d.mass_matrix_min_eigenvalue, d.mass_matrix_min_condition_number, ...
    d.mass_matrix_max_condition_number);
fprintf('  velocity clips hip/knee/any=%d/%d/%d\n', ...
    d.velocity_clip_hip_count, d.velocity_clip_knee_count, ...
    d.velocity_clip_any_transition_count);
fprintf('  angle clips hip/knee/any=%d/%d/%d\n', ...
    d.angle_clip_hip_count, d.angle_clip_knee_count, ...
    d.angle_clip_any_transition_count);
fprintf('  safety torque activations any/hip/knee=%d/%d/%d; source log=%d\n', ...
    d.safety_torque_any_transition_count, ...
    d.safety_torque_hip_transition_count, ...
    d.safety_torque_knee_transition_count, ...
    d.safety_log_activation_count);
fprintf('CAPTURE DIAGNOSTICS END\n');
end
