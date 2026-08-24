function run_human_model_v2_baseline()
%RUN_HUMAN_MODEL_V2_BASELINE Headless nominal V2 plant/reference validation.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'human_model_v2');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

diary_path = fullfile(output_dir, 'baseline_console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
diary_cleanup = onCleanup(@() diary('off'));

p = human_two_link_v2_parameters(1.72, 75.0);
config = human_two_link_v2_baseline_config();
write_command_record(fullfile(output_dir, 'commands.txt'));
write_version_record(fullfile(output_dir, 'matlab_version.txt'));
write_parameter_text(fullfile(output_dir, 'parameter_snapshot.txt'), p, config);
save(fullfile(output_dir, 'parameter_snapshot.mat'), 'p', 'config');

fprintf('HUMAN MODEL V2 BASELINE MATLAB: %s\n', version);
fprintf('HUMAN MODEL V2 OUTPUT: %s\n', output_dir);
fprintf('HUMAN MODEL V2 PROFILE: H=%.3fm M=%.3fkg\n', ...
    p.height_m, p.body_mass_kg);
result = simulate_human_two_link_v2_oracle(config, p);
save(fullfile(output_dir, 'nominal_oracle_workspace.mat'), ...
    'result', '-v7');

record = metrics_record(result.metrics);
writetable(struct2table(record), fullfile(output_dir, 'metrics.csv'));
gif_path = fullfile(output_dir, ...
    'slow_passive_flexion_v2_nominal.gif');
create_validation_gif(result, gif_path, output_dir);

visible_figures = findall(groot, 'Type', 'figure', 'Visible', 'on');
if ~isempty(visible_figures)
    error('HumanTwoLinkV2:VisibleFigure', ...
        'The headless runner created a visible figure.');
end
gif_files = dir(fullfile(output_dir, '*.gif'));
if numel(gif_files) ~= 1
    error('HumanTwoLinkV2:GifCount', ...
        'Expected exactly one V2 GIF, found %d.', numel(gif_files));
end
if ~result.metrics.completed || result.metrics.nonfinite_count ~= 0
    error('HumanTwoLinkV2:NonfiniteBaseline', ...
        'The nominal V2 rollout contains nonfinite values.');
end
if any(rad2deg(result.metrics.rmse_rad) >= 1e-4)
    error('HumanTwoLinkV2:TrackingAcceptance', ...
        'Oracle tracking RMSE exceeds 1e-4 deg.');
end
if result.metrics.rom_violation_count ~= 0 || ...
        result.metrics.soft_limit_activation_count ~= 0
    error('HumanTwoLinkV2:ROMAcceptance', ...
        'Nominal rollout violated ROM or activated a soft limit.');
end
if max(result.metrics.reference_max_velocity_rad_s) > 0.40 || ...
        max(result.metrics.reference_max_acceleration_rad_s2) > 1.5
    error('HumanTwoLinkV2:ReferenceAcceptance', ...
        'Reference velocity or acceleration exceeds its engineering bound.');
end

fprintf(['HUMAN MODEL V2 SUMMARY: completed=%d rmse_deg=[%.9g %.9g] ' ...
    'ref_vmax=[%.6f %.6f]rad/s ref_amax=[%.6f %.6f]rad/s2 ' ...
    'ref_jmax=[%.6f %.6f]rad/s3 ROM=%d soft=%d nonfinite=%d gif=%s\n'], ...
    result.metrics.completed, rad2deg(result.metrics.rmse_rad(1)), ...
    rad2deg(result.metrics.rmse_rad(2)), ...
    result.metrics.reference_max_velocity_rad_s(1), ...
    result.metrics.reference_max_velocity_rad_s(2), ...
    result.metrics.reference_max_acceleration_rad_s2(1), ...
    result.metrics.reference_max_acceleration_rad_s2(2), ...
    result.metrics.reference_max_jerk_rad_s3(1), ...
    result.metrics.reference_max_jerk_rad_s3(2), ...
    result.metrics.rom_violation_count, ...
    result.metrics.soft_limit_activation_count, ...
    result.metrics.nonfinite_count, gif_path);
end


function record = metrics_record(metrics)
record = struct();
record.completed = metrics.completed;
record.nonfinite_count = metrics.nonfinite_count;
record.rmse_q1_deg = rad2deg(metrics.rmse_rad(1));
record.rmse_q2_deg = rad2deg(metrics.rmse_rad(2));
record.max_error_q1_deg = rad2deg(metrics.max_abs_error_rad(1));
record.max_error_q2_deg = rad2deg(metrics.max_abs_error_rad(2));
record.reference_max_velocity_q1_rad_s = ...
    metrics.reference_max_velocity_rad_s(1);
record.reference_max_velocity_q2_rad_s = ...
    metrics.reference_max_velocity_rad_s(2);
record.reference_max_acceleration_q1_rad_s2 = ...
    metrics.reference_max_acceleration_rad_s2(1);
record.reference_max_acceleration_q2_rad_s2 = ...
    metrics.reference_max_acceleration_rad_s2(2);
record.reference_max_jerk_q1_rad_s3 = ...
    metrics.reference_max_jerk_rad_s3(1);
record.reference_max_jerk_q2_rad_s3 = ...
    metrics.reference_max_jerk_rad_s3(2);
record.actual_max_velocity_q1_rad_s = ...
    metrics.actual_max_velocity_rad_s(1);
record.actual_max_velocity_q2_rad_s = ...
    metrics.actual_max_velocity_rad_s(2);
record.actual_max_acceleration_q1_rad_s2 = ...
    metrics.actual_max_acceleration_rad_s2(1);
record.actual_max_acceleration_q2_rad_s2 = ...
    metrics.actual_max_acceleration_rad_s2(2);
record.actual_max_jerk_q1_rad_s3 = metrics.actual_max_jerk_rad_s3(1);
record.actual_max_jerk_q2_rad_s3 = metrics.actual_max_jerk_rad_s3(2);
record.max_passive_hip_torque_Nm = metrics.max_abs_passive_torque_Nm(1);
record.max_passive_knee_torque_Nm = metrics.max_abs_passive_torque_Nm(2);
record.max_soft_hip_torque_Nm = metrics.max_abs_soft_rhs_torque_Nm(1);
record.max_soft_knee_torque_Nm = metrics.max_abs_soft_rhs_torque_Nm(2);
record.max_oracle_hip_torque_Nm = metrics.max_abs_oracle_torque_Nm(1);
record.max_oracle_knee_torque_Nm = metrics.max_abs_oracle_torque_Nm(2);
record.max_oracle_torque_norm_Nm = metrics.max_oracle_torque_norm_Nm;
record.minimum_hip_rom_margin_deg = ...
    rad2deg(metrics.minimum_rom_margin_rad(1));
record.minimum_knee_rom_margin_deg = ...
    rad2deg(metrics.minimum_rom_margin_rad(2));
record.rom_violation_count = metrics.rom_violation_count;
record.soft_limit_activation_count = metrics.soft_limit_activation_count;
end


function create_validation_gif(result, gif_path, output_dir)
figure_handle = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [20, 20, 1420, 880]);
layout = tiledlayout(figure_handle, 6, 2, ...
    'TileSpacing', 'compact', 'Padding', 'compact');
p = result.parameters;
t = result.t;

body_axis = nexttile(layout, 1, [6, 1]);
hold(body_axis, 'on');
axis(body_axis, 'equal');
grid(body_axis, 'on');
reach = p.L1+p.L2;
xlim(body_axis, [-0.25, reach+0.25]);
ylim(body_axis, [-0.30, reach+0.25]);
xlabel(body_axis, 'X (m)');
ylabel(body_axis, 'Y (m)');
body_line = plot(body_axis, nan, nan, 'o-', 'LineWidth', 5, ...
    'MarkerSize', 8, 'Color', [0.10, 0.35, 0.75]);
contact_marker = plot(body_axis, nan, nan, 's', 'MarkerSize', 10, ...
    'MarkerFaceColor', [0.85, 0.25, 0.15], 'MarkerEdgeColor', 'k');
text(body_axis, 0.02, 0.98, ...
    'Square: distal wide-cuff equivalent point (s_c=0.90L_2)', ...
    'Units', 'normalized', 'VerticalAlignment', 'top');

q_axis = nexttile(layout, 2);
hold(q_axis, 'on');
plot(q_axis, t, rad2deg(result.q_ref(1, :)), '--', ...
    'Color', [0.25, 0.45, 0.90]);
plot(q_axis, t, rad2deg(result.q_ref(2, :)), '--', ...
    'Color', [0.90, 0.45, 0.20]);
q1_line = plot(q_axis, nan, nan, '-', 'Color', [0.05, 0.20, 0.65]);
q2_line = plot(q_axis, nan, nan, '-', 'Color', [0.70, 0.15, 0.05]);
grid(q_axis, 'on');
xlim(q_axis, [0, t(end)]);
ylabel(q_axis, 'Angle (deg)');
title(q_axis, 'q_1/q_2 reference and actual');
legend(q_axis, {'q_1 ref', 'q_2 ref', 'q_1', 'q_2'}, ...
    'Location', 'eastoutside');

dq_axis = nexttile(layout, 4);
hold(dq_axis, 'on');
dq1_line = plot(dq_axis, nan, nan, 'LineWidth', 1.3);
dq2_line = plot(dq_axis, nan, nan, 'LineWidth', 1.3);
grid(dq_axis, 'on');
xlim(dq_axis, [0, t(end)]);
ylabel(dq_axis, 'Velocity (rad/s)');
title(dq_axis, 'Actual joint velocity');
legend(dq_axis, {'dq_1', 'dq_2'}, 'Location', 'eastoutside');

motion_axis = nexttile(layout, 6);
hold(motion_axis, 'on');
acceleration_line = plot(motion_axis, nan, nan, ...
    'Color', [0.10, 0.55, 0.20], 'LineWidth', 1.3);
jerk_line = plot(motion_axis, nan, nan, ...
    'Color', [0.55, 0.15, 0.65], 'LineWidth', 1.3);
grid(motion_axis, 'on');
xlim(motion_axis, [0, t(end)]);
ylabel(motion_axis, 'Norm');
title(motion_axis, 'Acceleration and jerk norms');
legend(motion_axis, {'||ddq|| (rad/s^2)', '||jerk|| (rad/s^3)'}, ...
    'Location', 'eastoutside');

passive_axis = nexttile(layout, 8);
hold(passive_axis, 'on');
passive_hip_line = plot(passive_axis, nan, nan, 'LineWidth', 1.3);
passive_knee_line = plot(passive_axis, nan, nan, 'LineWidth', 1.3);
grid(passive_axis, 'on');
xlim(passive_axis, [0, t(end)]);
ylabel(passive_axis, 'Left-side torque (N m)');
title(passive_axis, 'Passive resistance');
legend(passive_axis, {'hip', 'knee'}, 'Location', 'eastoutside');

oracle_axis = nexttile(layout, 10);
hold(oracle_axis, 'on');
oracle_hip_line = plot(oracle_axis, nan, nan, 'LineWidth', 1.3);
oracle_knee_line = plot(oracle_axis, nan, nan, 'LineWidth', 1.3);
grid(oracle_axis, 'on');
xlim(oracle_axis, [0, t(end)]);
ylabel(oracle_axis, 'Torque (N m)');
title(oracle_axis, 'Direct-joint-torque oracle');
legend(oracle_axis, {'hip', 'knee'}, 'Location', 'eastoutside');

error_axis = nexttile(layout, 12);
yyaxis(error_axis, 'left');
tracking_line = plot(error_axis, nan, nan, ...
    'Color', [0.10, 0.35, 0.75], 'LineWidth', 1.3);
ylabel(error_axis, 'Tracking error (deg)');
yyaxis(error_axis, 'right');
margin_line = plot(error_axis, nan, nan, ...
    'Color', [0.85, 0.25, 0.15], 'LineWidth', 1.3);
ylabel(error_axis, 'Minimum ROM margin (deg)');
grid(error_axis, 'on');
xlim(error_axis, [0, t(end)]);
xlabel(error_axis, 'Time (s)');
title(error_axis, 'Tracking error and ROM margin');

axes_with_markers = [q_axis, dq_axis, motion_axis, passive_axis, ...
    oracle_axis, error_axis];
time_markers = gobjects(size(axes_with_markers));
for marker_index = 1:numel(axes_with_markers)
    marker_axis = axes_with_markers(marker_index);
    hold(marker_axis, 'on');
    time_markers(marker_index) = plot(marker_axis, [0, 0], ...
        ylim(marker_axis), 'k:', 'LineWidth', 0.8, ...
        'HandleVisibility', 'off');
end

frame_indices = unique(round(linspace(1, numel(t), 65)));
frame_path = fullfile(output_dir, 'human_model_v2_frame.png');
delay_time = result.config.t_final/numel(frame_indices);
for frame_number = 1:numel(frame_indices)
    index = frame_indices(frame_number);
    active = 1:index;
    geometry = human_two_link_v2_kinematics( ...
        result.state(1:2, index), p);
    points = [geometry.hip, geometry.knee, geometry.ankle];
    set(body_line, 'XData', points(1, :), 'YData', points(2, :));
    set(contact_marker, 'XData', geometry.contact(1), ...
        'YData', geometry.contact(2));
    title(body_axis, sprintf( ...
        'Human Model V2 plant/reference validation: t=%.2f s', t(index)));

    set(q1_line, 'XData', t(active), ...
        'YData', rad2deg(result.state(1, active)));
    set(q2_line, 'XData', t(active), ...
        'YData', rad2deg(result.state(2, active)));
    set(dq1_line, 'XData', t(active), ...
        'YData', result.state(3, active));
    set(dq2_line, 'XData', t(active), ...
        'YData', result.state(4, active));
    set(acceleration_line, 'XData', t(active), ...
        'YData', vecnorm(result.acceleration(:, active), 2, 1));
    set(jerk_line, 'XData', t(active), ...
        'YData', vecnorm(result.jerk_actual(:, active), 2, 1));
    set(passive_hip_line, 'XData', t(active), ...
        'YData', result.tau_passive_left(1, active));
    set(passive_knee_line, 'XData', t(active), ...
        'YData', result.tau_passive_left(2, active));
    set(oracle_hip_line, 'XData', t(active), ...
        'YData', result.tau_joint(1, active));
    set(oracle_knee_line, 'XData', t(active), ...
        'YData', result.tau_joint(2, active));
    set(tracking_line, 'XData', t(active), ...
        'YData', rad2deg(vecnorm(result.tracking_error(:, active), 2, 1)));
    set(margin_line, 'XData', t(active), ...
        'YData', rad2deg(min(result.rom_margin(:, active), [], 1)));
    for marker_index = 1:numel(time_markers)
        set(time_markers(marker_index), 'XData', [t(index), t(index)]);
    end

    exportgraphics(figure_handle, frame_path, 'Resolution', 90);
    rgb_frame = imread(frame_path);
    [indexed_frame, color_map] = rgb2ind(rgb_frame, 256);
    if frame_number == 1
        imwrite(indexed_frame, color_map, gif_path, 'gif', ...
            'LoopCount', Inf, 'DelayTime', delay_time);
    else
        imwrite(indexed_frame, color_map, gif_path, 'gif', ...
            'WriteMode', 'append', 'DelayTime', delay_time);
    end
end
close(figure_handle);
if isfile(frame_path)
    delete(frame_path);
end
end


function write_command_record(path)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not create command record.');
cleanup = onCleanup(@() fclose(output_file));
fprintf(output_file, '%s\n', ...
    ['/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab ' ...
    '-batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_human_model_v2_tests"']);
fprintf(output_file, '%s\n', ...
    ['/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab ' ...
    '-batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_human_model_v2_baseline"']);
end


function write_version_record(path)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not create MATLAB version record.');
cleanup = onCleanup(@() fclose(output_file));
fprintf(output_file, '%s\n', version);
end


function write_parameter_text(path, p, config)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not create parameter snapshot.');
cleanup = onCleanup(@() fclose(output_file));
fprintf(output_file, 'model: %s\n', p.model_name);
fprintf(output_file, 'height_m: %.17g\n', p.height_m);
fprintf(output_file, 'body_mass_kg: %.17g\n', p.body_mass_kg);
fields = {'L1', 'L2', 'm1', 'm2', 'lc1', 'lc2', 'I1', 'I2', ...
    'g', 'sc', 'soft_limit_margin', ...
    'soft_limit_numerical_tolerance', ...
    'soft_limit_boundary_torque_Nm', ...
    'soft_limit_damping_Nms_rad'};
for field_index = 1:numel(fields)
    name = fields{field_index};
    fprintf(output_file, '%s: %.17g\n', name, p.(name));
end
fprintf(output_file, 'q_rest_rad: %s\n', mat2str(p.q_rest'));
fprintf(output_file, 'K_passive: %s\n', mat2str(p.K_passive));
fprintf(output_file, 'B_passive: %s\n', mat2str(p.B_passive));
fprintf(output_file, 'q_min_rad: %s\n', mat2str(p.q_min'));
fprintf(output_file, 'q_max_rad: %s\n', mat2str(p.q_max'));
fprintf(output_file, 'dt: %.17g\n', config.dt);
fprintf(output_file, 't_final: %.17g\n', config.t_final);
fprintf(output_file, 'oracle_Kp: %s\n', mat2str(config.Kp));
fprintf(output_file, 'oracle_Kd: %s\n', mat2str(config.Kd));
end
