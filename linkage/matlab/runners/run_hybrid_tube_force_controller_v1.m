function run_hybrid_tube_force_controller_v1()
%RUN_HYBRID_TUBE_FORCE_CONTROLLER_V1 Formal 12-case dynamic comparison.
%
% This runner is the reproducible formal command. Repository policy reserves
% execution of the full scientific matrix for the user.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'hybrid_tube_force_controller_v1');
if ~isfolder(output_dir), mkdir(output_dir); end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path), delete(diary_path); end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

fprintf('HYBRID TUBE FORCE CONTROLLER V1 MATLAB: %s\n', version);
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
fprintf(['FORMAL COMMAND: matlab -batch "addpath(genpath(''' ...
    'linkage/matlab'')); run_hybrid_tube_force_controller_v1"\n']);
p = human_two_link_v2_parameters(1.72, 75);
bounds = [80, 120, 200];
caps = [0, 5, 10];
records = repmat(empty_record(), 12, 1);
results = cell(12, 1);
record_index = 0;

for bound = bounds
    strict_config = strict_config_for_bound(bound);
    strict = simulate_single_arm_v2_equilibrium(strict_config, p);
    record_index = record_index+1;
    results{record_index} = strict;
    records(record_index) = strict_record(strict, bound);
    fprintf('CASE strict_%gN: terminal=%s peak=%.6gN residual=%.6gNm\n', ...
        bound, records(record_index).terminal_state, ...
        records(record_index).peak_force_norm_N, ...
        records(record_index).torque_residual_rms_Nm);
    for cap = caps
        config = hybrid_tube_v1_config(bound, cap);
        plan = hybrid_tube_v1_build_plan(p, config);
        governed = simulate_hybrid_tube_force_controller_v1(config, p, plan);
        record_index = record_index+1;
        results{record_index} = governed;
        records(record_index) = governed_record(governed, bound, cap);
        fprintf(['CASE tube_%gdeg_%gN: terminal=%s progress=%.6f ' ...
            'peak=%.6gN residual=%.6gNm\n'], cap, bound, ...
            governed.metrics.terminal_state, governed.metrics.final_progress, ...
            governed.metrics.peak_force_norm_N, ...
            governed.metrics.torque_residual_rms_Nm);
    end
end

save(fullfile(output_dir, 'formal_results.mat'), 'results', 'records', ...
    'p', 'bounds', 'caps', '-v7.3');
writetable(struct2table(records), fullfile(output_dir, 'case_metrics.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), records);
create_summary_figures(records, output_dir);
create_detailed_figures(results, records, output_dir);
for bound_index = 1:numel(bounds)
    result_index = (bound_index-1)*4+4; % 10-degree tube case.
    gif_path = fullfile(output_dir, sprintf( ...
        'tube_10deg_%gN_representative.gif', bounds(bound_index)));
    create_hybrid_gif(results{result_index}, gif_path);
end
if numel(dir(fullfile(output_dir, '*.gif'))) < 3
    error('HybridTubeV1:MissingGif', ...
        'Expected at least three representative formal GIF files.');
end
if ~isempty(findall(groot, 'Type', 'figure', 'Visible', 'on'))
    error('HybridTubeV1:VisibleFigure', ...
        'Formal runner created a visible figure.');
end
end


function config = strict_config_for_bound(bound)
config = single_arm_v2_equilibrium_base_config();
config.case_name = sprintf('strict_current_v2_%gN', bound);
config.force_bound_N = bound;
config.u_min = -bound*ones(2, 1);
config.u_max = bound*ones(2, 1);
config.du_max = 250*ones(2, 1);
end


function record = empty_record()
record = struct('case_name', "", 'comparison_type', "", ...
    'force_bound_N', NaN, 'tube_cap_deg', NaN, ...
    'terminal_state', "", 'completion_time_s', NaN, ...
    'final_progress', NaN, 'terminal_deviation_q1_deg', NaN, ...
    'terminal_deviation_q2_deg', NaN, ...
    'rmse_q1_deg', NaN, 'rmse_q2_deg', NaN, ...
    'max_task_deviation_q1_deg', NaN, ...
    'max_task_deviation_q2_deg', NaN, 'time_outside_tube_s', NaN, ...
    'peak_parallel_N', NaN, 'peak_perp_N', NaN, ...
    'peak_force_norm_N', NaN, 'peak_force_rate_N_s', NaN, ...
    'force_rms_N', NaN, ...
    'torque_residual_rms_Nm', NaN, 'force_saturation_fraction', NaN, ...
    'slew_saturation_fraction', NaN, 'min_sigma', NaN, ...
    'max_condition', NaN, 'max_velocity_rad_s', NaN, ...
    'max_acceleration_rad_s2', NaN, 'max_jerk_rad_s3', NaN, ...
    'minimum_rom_margin_deg', NaN, 'progress_slowdown_s', NaN, ...
    'pause_duration_s', NaN, 'force_aware_deviation_duration_s', NaN, ...
    'controller_feasible_fraction', NaN, ...
    'soft_limit_count', NaN, 'rom_violation_count', NaN);
end


function record = strict_record(result, bound)
m = result.metrics;
record = empty_record();
record.case_name = string(result.config.case_name);
record.comparison_type = "strict_current_v2";
record.force_bound_N = bound;
record.tube_cap_deg = 0;
if m.nonfinite_count > 0 || m.rom_violation_count > 0
    record.terminal_state = "INFEASIBLE";
elseif m.torque_residual_rms_Nm > result.config.residual_tolerance_Nm
    record.terminal_state = "INFEASIBLE";
else
    record.terminal_state = "TASK_COMPLETE";
end
record.completion_time_s = result.t(end);
record.final_progress = 1;
record.rmse_q1_deg = rad2deg(m.rmse_rad(1));
record.rmse_q2_deg = rad2deg(m.rmse_rad(2));
record.terminal_deviation_q1_deg = rad2deg(result.tracking_error(1, end));
record.terminal_deviation_q2_deg = rad2deg(result.tracking_error(2, end));
record.time_outside_tube_s = result.config.dt*sum(any(abs( ...
    result.tracking_error) > deg2rad(1e-6), 1));
record.peak_parallel_N = m.max_force_component_N(1);
record.peak_perp_N = m.max_force_component_N(2);
record.peak_force_norm_N = m.max_force_norm_N;
record.force_rms_N = sqrt(mean(vecnorm(result.force_local, 2, 1).^2));
record.peak_force_rate_N_s = m.max_force_rate_norm_N_s;
record.torque_residual_rms_Nm = m.torque_residual_rms_Nm;
record.force_saturation_fraction = m.force_saturation_fraction;
record.slew_saturation_fraction = m.slew_saturation_fraction;
record.min_sigma = m.min_sigma;
record.max_condition = m.max_condition;
record.max_velocity_rad_s = max(abs(result.state(3:4, :)), [], 'all');
record.max_acceleration_rad_s2 = max(m.max_abs_acceleration_rad_s2);
record.max_jerk_rad_s3 = max(m.max_abs_jerk_rad_s3);
record.minimum_rom_margin_deg = rad2deg(min(result.rom_margin, [], 'all'));
record.progress_slowdown_s = 0;
record.pause_duration_s = 0;
record.force_aware_deviation_duration_s = 0;
record.controller_feasible_fraction = m.full_constraint_feasible_fraction;
record.soft_limit_count = m.soft_limit_activation_count;
record.rom_violation_count = m.rom_violation_count;
end


function record = governed_record(result, bound, cap)
m = result.metrics;
record = empty_record();
record.case_name = string(result.config.case_name);
record.comparison_type = "tube_reference_manager";
record.force_bound_N = bound;
record.tube_cap_deg = cap;
record.terminal_state = m.terminal_state;
record.completion_time_s = m.completion_time_s;
record.final_progress = m.final_progress;
record.rmse_q1_deg = m.rmse_tracking_deg(1);
record.rmse_q2_deg = m.rmse_tracking_deg(2);
record.terminal_deviation_q1_deg = m.terminal_deviation_deg(1);
record.terminal_deviation_q2_deg = m.terminal_deviation_deg(2);
record.max_task_deviation_q1_deg = m.max_task_deviation_deg(1);
record.max_task_deviation_q2_deg = m.max_task_deviation_deg(2);
record.time_outside_tube_s = m.time_outside_tube_s;
record.peak_parallel_N = m.peak_force_component_N(1);
record.peak_perp_N = m.peak_force_component_N(2);
record.peak_force_norm_N = m.peak_force_norm_N;
record.force_rms_N = m.force_rms_N;
record.peak_force_rate_N_s = max(vecnorm(result.force_rate, 2, 1));
record.torque_residual_rms_Nm = m.torque_residual_rms_Nm;
record.force_saturation_fraction = m.force_saturation_fraction;
record.slew_saturation_fraction = m.slew_saturation_fraction;
record.min_sigma = m.min_sigma;
record.max_condition = m.max_condition;
record.max_velocity_rad_s = max(m.max_velocity_rad_s);
record.max_acceleration_rad_s2 = max(m.max_acceleration_rad_s2);
record.max_jerk_rad_s3 = max(m.max_jerk_rad_s3);
record.minimum_rom_margin_deg = rad2deg(min(m.min_rom_margin_rad));
record.progress_slowdown_s = m.progress_slowdown_duration_s;
record.pause_duration_s = m.pause_duration_s;
record.force_aware_deviation_duration_s = ...
    m.force_aware_deviation_duration_s;
record.controller_feasible_fraction = m.controller_feasible_fraction;
record.soft_limit_count = m.soft_limit_activation_count;
record.rom_violation_count = m.rom_violation_count;
end


function write_summary(path, records)
file = fopen(path, 'w'); assert(file >= 0);
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'Hybrid tube force controller V1 formal comparison\n');
fprintf(file, 'MATLAB %s\n', version);
for index = 1:numel(records)
    r = records(index);
    fprintf(file, ['%s: terminal=%s, progress=%.9g, peak_force=%.9g N, ' ...
        'residual_rms=%.9g Nm, deviation=[%.9g %.9g] deg\n'], ...
        r.case_name, r.terminal_state, r.final_progress, ...
        r.peak_force_norm_N, r.torque_residual_rms_Nm, ...
        r.max_task_deviation_q1_deg, r.max_task_deviation_q2_deg);
end
end


function create_summary_figures(records, output_dir)
T = struct2table(records);
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [30 30 1200 700]);
tiledlayout(fig, 2, 2, 'TileSpacing', 'compact');
nexttile; bar(T.peak_force_norm_N); ylabel('Peak force norm (N)'); grid on;
nexttile; bar(T.torque_residual_rms_Nm); ylabel('Torque residual RMS (Nm)'); grid on;
nexttile; bar(T.final_progress); ylabel('Final progress'); ylim([0 1.05]); grid on;
nexttile; bar(T.max_condition); ylabel('Maximum cond(A)'); grid on;
sgtitle('Strict-path and tube-governed comparison');
exportgraphics(fig, fullfile(output_dir, 'comparison_summary.png'), ...
    'Resolution', 180); close(fig);
end


function create_detailed_figures(results, records, output_dir)
representative = results{end};

fig = figure('Visible', 'off', 'Color', 'w'); hold on; grid on;
plot(rad2deg(representative.q_nominal(1,:)), ...
    rad2deg(representative.q_nominal(2,:)), 'k--', 'LineWidth', 1.3);
plot(rad2deg(representative.q_reference(1,:)), ...
    rad2deg(representative.q_reference(2,:)), 'b-', 'LineWidth', 1.5);
plot(rad2deg(representative.x(1,:)), rad2deg(representative.x(2,:)), ...
    'r-', 'LineWidth', 1.2);
xlabel('q1 (deg)'); ylabel('q2 (deg)');
legend('nominal path','governed reference','actual','Location','best');
title('q1-q2 path, governed reference, and closed-loop state');
exportgraphics(fig, fullfile(output_dir, 'q1_q2_path_tube_actual.png'), ...
    'Resolution', 180); close(fig);

T = struct2table(records);
fig = figure('Visible', 'off', 'Color', 'w');
bar(T.peak_force_norm_N); grid on; ylabel('Peak force norm (N)');
xlabel('comparison case index'); title('Force comparison across 12 cases');
exportgraphics(fig, fullfile(output_dir, 'force_comparison.png'), ...
    'Resolution', 180); close(fig);

fig = figure('Visible', 'off', 'Color', 'w');
plot(representative.t, representative.progress, 'LineWidth', 1.5); grid on;
xlabel('time (s)'); ylabel('task progress s'); ylim([0 1.05]);
title('Force-aware progress management');
exportgraphics(fig, fullfile(output_dir, 'progress_vs_time.png'), ...
    'Resolution', 180); close(fig);

fig = figure('Visible', 'off', 'Color', 'w'); hold on; grid on;
plot(representative.t, rad2deg(representative.task_error));
xlabel('time (s)'); ylabel('actual minus nominal (deg)');
legend('q1','q2','Location','best'); title('Task-path deviation');
exportgraphics(fig, fullfile(output_dir, 'deviation_vs_time.png'), ...
    'Resolution', 180); close(fig);

fig = figure('Visible', 'off', 'Color', 'w'); hold on; grid on;
deviation = max([T.max_task_deviation_q1_deg, ...
    T.max_task_deviation_q2_deg], [], 2);
scatter(deviation, T.peak_force_norm_N, 70, T.force_bound_N, 'filled');
xlabel('maximum path deviation (deg)'); ylabel('peak force norm (N)');
title('Force/deviation tradeoff across tube caps'); colorbar;
exportgraphics(fig, fullfile(output_dir, ...
    'force_deviation_tradeoff.png'), 'Resolution', 180); close(fig);
end


function create_hybrid_gif(result, path)
p = result.parameters; t = result.t;
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20 20 1400 760]);
layout = tiledlayout(fig, 4, 2, 'TileSpacing', 'compact');
body = nexttile(layout, 1, [4 1]); hold(body, 'on'); axis(body, 'equal'); grid(body, 'on');
reach = p.L1+p.L2; xlim(body, [-reach reach]); ylim(body, [-0.15 reach+0.15]);
leg = plot(body, nan, nan, 'o-', 'LineWidth', 5, 'MarkerSize', 8);
force_arrow = quiver(body, nan, nan, nan, nan, 0, 'r', 'LineWidth', 2);
info = text(body, 0.02, 0.98, '', 'Units', 'normalized', ...
    'VerticalAlignment', 'top');
qax = nexttile(layout, 2); hold(qax, 'on'); grid(qax, 'on');
plot(qax, t, rad2deg(result.q_nominal), '--');
q1 = plot(qax, nan, nan); q2 = plot(qax, nan, nan); ylabel(qax, 'q (deg)');
fax = nexttile(layout, 4); hold(fax, 'on'); grid(fax, 'on');
fp = plot(fax, nan, nan); fn = plot(fax, nan, nan); ylabel(fax, 'Force (N)');
pax = nexttile(layout, 6); hold(pax, 'on'); grid(pax, 'on');
pr = plot(pax, nan, nan); ylabel(pax, 'progress'); ylim(pax, [0 1.05]);
dax = nexttile(layout, 8); hold(dax, 'on'); grid(dax, 'on');
dev1 = plot(dax, nan, nan); dev2 = plot(dax, nan, nan); ylabel(dax, 'deviation (deg)'); xlabel(dax, 'time (s)');
axes_list = [qax fax pax dax];
for ax = axes_list, xlim(ax, [0 max(t(end), eps)]); end
frames = unique(round(linspace(1, numel(t), min(240, numel(t)))));
for frame_index = 1:numel(frames)
    k = frames(frame_index); q = result.x(1:2, k);
    phi = q(1)-q(2); hip = [0;0]; knee = p.L1*[sin(q(1)); cos(q(1))];
    ankle = knee+p.L2*[sin(phi); cos(phi)];
    contact = knee+p.sc*[sin(phi); cos(phi)];
    set(leg, 'XData', [hip(1) knee(1) ankle(1)], 'YData', [hip(2) knee(2) ankle(2)]);
    mapping = single_arm_v2_force_map(q, result.x(3:4,k), p);
    fw = mapping.rotation*result.force_local(:,k)/800;
    set(force_arrow, 'XData', contact(1), 'YData', contact(2), 'UData', fw(1), 'VData', fw(2));
    set(info, 'String', sprintf(['t=%.2f s  s=%.3f  %s\n' ...
        'F_parallel=%.1f N  F_perp=%.1f N'], t(k), result.progress(k), ...
        result.status(k), result.force_local(1,k), result.force_local(2,k)));
    set(q1, 'XData', t(1:k), 'YData', rad2deg(result.x(1,1:k)));
    set(q2, 'XData', t(1:k), 'YData', rad2deg(result.x(2,1:k)));
    set(fp, 'XData', t(1:k), 'YData', result.force_local(1,1:k));
    set(fn, 'XData', t(1:k), 'YData', result.force_local(2,1:k));
    set(pr, 'XData', t(1:k), 'YData', result.progress(1:k));
    set(dev1, 'XData', t(1:k), 'YData', rad2deg(result.task_error(1,1:k)));
    set(dev2, 'XData', t(1:k), 'YData', rad2deg(result.task_error(2,1:k)));
    frame = getframe(fig); image = frame2im(frame); [indexed, map] = rgb2ind(image, 256);
    if frame_index == 1
        imwrite(indexed, map, path, 'gif', 'LoopCount', Inf, 'DelayTime', 0.08);
    else
        imwrite(indexed, map, path, 'gif', 'WriteMode', 'append', 'DelayTime', 0.08);
    end
end
close(fig);
end
