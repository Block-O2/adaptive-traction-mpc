function run_near_extension_force_mode_feasibility()
%RUN_NEAR_EXTENSION_FORCE_MODE_FEASIBILITY Offline quasistatic mechanics study.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'near_extension_force_mode_feasibility');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
command = ['matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_near_extension_force_mode_feasibility"'];
fprintf('NEAR-EXTENSION FORCE-MODE FEASIBILITY STUDY\n');
fprintf('MATLAB: %s\nCOMMAND: %s\nOUTPUT: %s\n', ...
    version, command, output_dir);

p = human_two_link_v2_parameters(1.72, 75.0);
bounds = [80, 120, 200];
tol = 1e-12;
study = single_arm_near_extension_force_mode_scan( ...
    p, 0:1:80, 1:1:30, bounds, tol);
return_branch = evaluate_return_branch(p, bounds, tol);
thresholds = threshold_crossings(return_branch, bounds);
summary = summarize_study(study, return_branch, thresholds, p, bounds, tol);

write_scan_csv(study, fullfile(output_dir, 'near_extension_scan.csv'));
write_curve_csv(study, fullfile(output_dir, 'force_mode_curves.csv'));
write_return_csv(return_branch, fullfile(output_dir, 'v2_return_branch.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), summary, bounds, command);
save(fullfile(output_dir, 'near_extension_force_mode_workspace.mat'), ...
    'study', 'return_branch', 'thresholds', 'summary', 'p', 'command');
create_plots(study, return_branch, output_dir);

for q2 = [30, 20, 15, 10, 5, 2, 1]
    record = summary.key_postures(summary.key_q2_deg == q2);
    fprintf(['q2=%2.0f deg representative(q1=%.6f): Fpar=%.6f N ' ...
        '|F|=%.6f N; minimum-|Fpar|(q1=%.0f): Fpar=%.6f N ' ...
        '|F|=%.6f N sigma=%.6g cond=%.6g\n'], ...
        q2, record.representative_q1_deg, ...
        record.representative_F_parallel_N, ...
        record.representative_force_norm_N, record.optimal_q1_deg, ...
        record.optimal_F_parallel_N, record.optimal_force_norm_N, ...
        record.optimal_sigma_min, record.optimal_cond_A);
end
fprintf(['CURRENT [5,10]: |F|=%.6f N; q2=10 minimum-|Fpar| ' ...
    'q1=%.0f deg, Fpar=%.6f N, |F|=%.6f N\n'], ...
    summary.current_start_force_norm_N, summary.q2_10_optimal_q1_deg, ...
    summary.q2_10_optimal_F_parallel_N, ...
    summary.q2_10_optimal_force_norm_N);
for index = 1:numel(bounds)
    fprintf(['BOUND +/-%.0f N: return residual begins below q2=%.6f deg ' ...
        '(dominant=%s); optimum curve residual q2 range=%s\n'], ...
        bounds(index), summary.return_support_onset_q2_deg(index), ...
        summary.return_support_dominant(index), ...
        summary.optimum_support_q2_description(index));
end
fprintf('NEAR-EXTENSION FORCE-MODE STUDY COMPLETE\n');
end


function return_branch = evaluate_return_branch(p, bounds, tol)
t = 8.5:0.002:15.0;
q = zeros(2, numel(t));
for index = 1:numel(t)
    q(:, index) = human_two_link_v2_reference( ...
        t(index), "slow_passive_flexion_v2");
end
return_branch = single_arm_quasistatic_path_support(q, t, p, bounds, tol);
return_branch.q_deg = rad2deg(q);
end


function crossings = threshold_crossings(path, bounds)
crossings = struct();
crossings.parallel = repmat(empty_crossing(), 1, numel(bounds));
crossings.norm = repmat(empty_crossing(), 1, numel(bounds));
for index = 1:numel(bounds)
    crossings.parallel(index) = first_crossing( ...
        abs(path.F_parallel), bounds(index), path);
    crossings.norm(index) = first_crossing( ...
        path.force_norm, bounds(index), path);
end
end


function crossing = empty_crossing()
crossing = struct('found', false, 'index', NaN, 'time_s', NaN, ...
    'q1_deg', NaN, 'q2_deg', NaN, 'value_N', NaN);
end


function crossing = first_crossing(values, threshold, path)
crossing = empty_crossing();
index = find(values > threshold, 1, 'first');
if isempty(index)
    return;
end
crossing.found = true;
crossing.index = index;
crossing.time_s = path.time_s(index);
crossing.q1_deg = path.q_deg(1, index);
crossing.q2_deg = path.q_deg(2, index);
crossing.value_N = values(index);
end


function summary = summarize_study(study, path, crossings, p, bounds, tol)
summary = struct();
key_q2 = [30, 20, 15, 10, 5, 2, 1];
records = repmat(key_record(), 1, numel(key_q2));
for index = 1:numel(key_q2)
    row = find(study.q2_deg == key_q2(index), 1);
    records(index) = build_key_record(study, row);
end
summary.key_q2_deg = key_q2;
summary.key_postures = records;
start = single_arm_quasistatic_hold_point( ...
    deg2rad([5; 10]), p, bounds, tol);
summary.current_start_force_norm_N = start.force_norm;
q2_10 = find(study.q2_deg == 10, 1);
summary.q2_10_optimal_q1_deg = study.parallel_optimum.q1_deg(q2_10);
summary.q2_10_optimal_F_parallel_N = ...
    study.parallel_optimum.F_parallel(q2_10);
summary.q2_10_optimal_force_norm_N = ...
    study.parallel_optimum.force_norm(q2_10);
summary.q2_10_parallel_reduction_fraction = 1-abs( ...
    summary.q2_10_optimal_F_parallel_N/start.F_parallel);
summary.q2_1_min_abs_F_parallel_N = abs( ...
    study.parallel_optimum.F_parallel(1));
summary.q2_2_min_abs_F_parallel_N = abs( ...
    study.parallel_optimum.F_parallel(2));
summary.q2_5_min_abs_F_parallel_N = abs( ...
    study.parallel_optimum.F_parallel(5));
summary.q2_10_min_abs_F_parallel_N = abs( ...
    study.parallel_optimum.F_parallel(10));
summary.q2_zero_rank_deficient = all(study.atlas.rank_deficient(1, :));
summary.parallel_threshold_crossings = crossings.parallel;
summary.norm_threshold_crossings = crossings.norm;

nb = numel(bounds);
summary.return_support_onset_q2_deg = NaN(1, nb);
summary.return_support_onset_time_s = NaN(1, nb);
summary.return_support_onset_norm_Nm = NaN(1, nb);
summary.return_support_dominant = strings(1, nb);
summary.return_support_peak_norm_Nm = NaN(1, nb);
summary.return_support_peak_hip_Nm = NaN(1, nb);
summary.return_support_peak_knee_Nm = NaN(1, nb);
summary.optimum_support_nonzero_q2_min_deg = NaN(1, nb);
summary.optimum_support_nonzero_q2_max_deg = NaN(1, nb);
summary.optimum_support_peak_norm_Nm = NaN(1, nb);
summary.optimum_support_dominant = strings(1, nb);
summary.optimum_support_q2_description = strings(1, nb);
support_tol = 1e-9;
for bound_index = 1:nb
    residual = path.support_norm(:, bound_index)';
    onset = find(residual > support_tol, 1, 'first');
    if ~isempty(onset)
        summary.return_support_onset_q2_deg(bound_index) = ...
            path.q_deg(2, onset);
        summary.return_support_onset_time_s(bound_index) = path.time_s(onset);
        summary.return_support_onset_norm_Nm(bound_index) = residual(onset);
    end
    [peak, peak_index] = max(residual);
    support = path.support_torque(:, peak_index, bound_index);
    summary.return_support_peak_norm_Nm(bound_index) = peak;
    summary.return_support_peak_hip_Nm(bound_index) = support(1);
    summary.return_support_peak_knee_Nm(bound_index) = support(2);
    summary.return_support_dominant(bound_index) = dominant_component(support);

    optimum_residual = study.parallel_optimum.support_norm(:, bound_index);
    nonzero = optimum_residual > support_tol;
    if any(nonzero)
        q2_nonzero = study.q2_deg(nonzero);
        summary.optimum_support_nonzero_q2_min_deg(bound_index) = ...
            min(q2_nonzero);
        summary.optimum_support_nonzero_q2_max_deg(bound_index) = ...
            max(q2_nonzero);
        summary.optimum_support_q2_description(bound_index) = sprintf( ...
            '%.0f..%.0f deg', min(q2_nonzero), max(q2_nonzero));
    else
        summary.optimum_support_q2_description(bound_index) = "none";
    end
    [optimum_peak, optimum_peak_index] = max(optimum_residual);
    optimum_support = study.parallel_optimum.support_torque( ...
        :, optimum_peak_index, bound_index);
    summary.optimum_support_peak_norm_Nm(bound_index) = optimum_peak;
    summary.optimum_support_dominant(bound_index) = ...
        dominant_component(optimum_support);
end
end


function label = dominant_component(torque)
if abs(torque(1)) >= abs(torque(2))
    label = "hip";
else
    label = "knee";
end
end


function record = key_record()
record = struct('q2_deg', NaN, 'representative_q1_deg', NaN, ...
    'representative_F_parallel_N', NaN, 'representative_F_perp_N', NaN, ...
    'representative_force_norm_N', NaN, ...
    'representative_sigma_min', NaN, 'representative_cond_A', NaN, ...
    'optimal_q1_deg', NaN, 'optimal_F_parallel_N', NaN, ...
    'optimal_F_perp_N', NaN, 'optimal_force_norm_N', NaN, ...
    'optimal_sigma_min', NaN, 'optimal_cond_A', NaN, ...
    'q1_deviation_deg', NaN);
end


function record = build_key_record(study, row)
record = key_record();
record.q2_deg = study.q2_deg(row);
record.representative_q1_deg = study.representative.q1_deg(row);
record.representative_F_parallel_N = study.representative.F_parallel(row);
record.representative_F_perp_N = study.representative.F_perp(row);
record.representative_force_norm_N = study.representative.force_norm(row);
record.representative_sigma_min = study.representative.sigma_min(row);
record.representative_cond_A = study.representative.condition_number(row);
record.optimal_q1_deg = study.parallel_optimum.q1_deg(row);
record.optimal_F_parallel_N = study.parallel_optimum.F_parallel(row);
record.optimal_F_perp_N = study.parallel_optimum.F_perp(row);
record.optimal_force_norm_N = study.parallel_optimum.force_norm(row);
record.optimal_sigma_min = study.parallel_optimum.sigma_min(row);
record.optimal_cond_A = study.parallel_optimum.condition_number(row);
record.q1_deviation_deg = record.optimal_q1_deg-record.representative_q1_deg;
end


function write_scan_csv(study, path)
[Q1, Q2] = meshgrid(study.q1_deg, study.q2_deg);
rows = 2:size(study.atlas.F_parallel, 1);
table_data = table(Q1(:), Q2(:), ...
    reshape(study.atlas.F_parallel(rows, :), [], 1), ...
    reshape(study.atlas.F_perp(rows, :), [], 1), ...
    reshape(study.atlas.force_norm(rows, :), [], 1), ...
    reshape(study.atlas.sigma_min(rows, :), [], 1), ...
    reshape(study.atlas.condition_number(rows, :), [], 1), ...
    'VariableNames', {'q1_deg', 'q2_deg', 'F_parallel_N', 'F_perp_N', ...
    'force_norm_N', 'sigma_min_A', 'cond_A'});
writetable(table_data, path);
end


function write_curve_csv(study, path)
p = study.parallel_optimum;
n = study.norm_optimum;
r = study.representative;
table_data = table(study.q2_deg(:), r.q1_deg(:), r.F_parallel(:), ...
    r.F_perp(:), r.force_norm(:), p.q1_deg(:), p.F_parallel(:), ...
    p.F_perp(:), p.force_norm(:), p.sigma_min(:), ...
    p.condition_number(:), n.q1_deg(:), n.F_parallel(:), ...
    n.F_perp(:), n.force_norm(:), ...
    'VariableNames', {'q2_deg', 'representative_q1_deg', ...
    'representative_F_parallel_N', 'representative_F_perp_N', ...
    'representative_force_norm_N', 'min_parallel_q1_deg', ...
    'min_parallel_F_parallel_N', 'min_parallel_F_perp_N', ...
    'min_parallel_force_norm_N', 'min_parallel_sigma_min_A', ...
    'min_parallel_cond_A', 'min_norm_q1_deg', ...
    'min_norm_F_parallel_N', 'min_norm_F_perp_N', ...
    'minimum_force_norm_N'});
writetable(table_data, path);
end


function write_return_csv(path_data, path)
table_data = table(path_data.time_s(:), path_data.q_deg(1, :)', ...
    path_data.q_deg(2, :)', path_data.F_parallel(:), ...
    path_data.F_perp(:), path_data.force_norm(:), ...
    path_data.sigma_min(:), path_data.condition_number(:), ...
    path_data.support_norm(:, 1), path_data.support_norm(:, 2), ...
    path_data.support_norm(:, 3), ...
    'VariableNames', {'time_s', 'q1_deg', 'q2_deg', 'F_parallel_N', ...
    'F_perp_N', 'force_norm_N', 'sigma_min_A', 'cond_A', ...
    'support_residual_80N_Nm', 'support_residual_120N_Nm', ...
    'support_residual_200N_Nm'});
writetable(table_data, path);
end


function create_plots(study, path, output_dir)
save_parallel_map(study, fullfile(output_dir, ...
    'force_parallel_near_extension_map.png'));
save_minimum_parallel(study, fullfile(output_dir, ...
    'minimum_parallel_force_vs_knee_flexion.png'));
save_optimal_hip(study, fullfile(output_dir, ...
    'optimal_hip_angle_vs_knee_flexion.png'));
save_minimum_norm(study, fullfile(output_dir, ...
    'minimum_force_norm_vs_knee_flexion.png'));
save_return_comparison(study, path, fullfile(output_dir, ...
    'v2_return_vs_force_mode_optimum.png'));
for bound_index = 1:numel(study.component_bounds_N)
    save_support_plot(study, path, bound_index, fullfile(output_dir, ...
        sprintf('support_residual_%dN.png', ...
        study.component_bounds_N(bound_index))));
end
end


function [fig, ax] = base_figure()
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [100, 100, 900, 650]);
ax = axes(fig);
end


function save_parallel_map(study, path)
[fig, ax] = base_figure();
data = study.atlas.F_parallel(2:end, :);
limit = 400;
imagesc(ax, study.q1_deg, study.q2_deg, min(max(data, -limit), limit));
set(ax, 'YDir', 'normal');
clim(ax, [-limit, limit]);
color_axis = colorbar(ax);
color_axis.Label.String = 'F_{parallel} (N), saturated at +/-400 N';
xlabel(ax, 'Hip angle q_1 (deg)');
ylabel(ax, 'Knee flexion q_2 (deg)');
title(ax, 'Near-extension axial force map');
hold(ax, 'on');
plot(ax, study.parallel_optimum.q1_deg, study.q2_deg, 'w-', ...
    'LineWidth', 2.2);
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_minimum_parallel(study, path)
[fig, ax] = base_figure();
semilogy(ax, study.q2_deg, max(abs(study.parallel_optimum.F_parallel), 1e-6), ...
    'LineWidth', 1.8);
xlabel(ax, 'Knee flexion q_2 (deg)');
ylabel(ax, 'Minimum |F_{parallel}| (N), log scale');
title(ax, 'Minimum axial force over scanned hip posture');
grid(ax, 'on');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_optimal_hip(study, path)
[fig, ax] = base_figure();
plot(ax, study.q2_deg, study.parallel_optimum.q1_deg, 'LineWidth', 1.8, ...
    'DisplayName', 'minimum |F_{parallel}|');
hold(ax, 'on');
plot(ax, study.q2_deg, study.norm_optimum.q1_deg, '--', 'LineWidth', 1.8, ...
    'DisplayName', 'minimum |F|');
plot(ax, study.q2_deg, study.representative.q1_deg, ':', 'LineWidth', 1.8, ...
    'DisplayName', 'V2 coordination / extrapolation');
xlabel(ax, 'Knee flexion q_2 (deg)');
ylabel(ax, 'Selected hip angle q_1 (deg)');
title(ax, 'Posture selected by separate force objectives');
grid(ax, 'on');
legend(ax, 'Location', 'best');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_minimum_norm(study, path)
[fig, ax] = base_figure();
semilogy(ax, study.q2_deg, study.norm_optimum.force_norm, 'LineWidth', 1.8);
xlabel(ax, 'Knee flexion q_2 (deg)');
ylabel(ax, 'Minimum force norm (N), log scale');
title(ax, 'Minimum total force over scanned hip posture');
grid(ax, 'on');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_return_comparison(study, path_data, output_path)
[fig, ax] = base_figure();
plot(ax, path_data.q_deg(2, :), abs(path_data.F_parallel), ...
    'LineWidth', 1.8, 'DisplayName', 'V2 return |F_{parallel}|');
hold(ax, 'on');
plot(ax, study.q2_deg, abs(study.parallel_optimum.F_parallel), ...
    'LineWidth', 1.8, 'DisplayName', 'posture-optimum |F_{parallel}|');
plot(ax, study.q2_deg, abs(study.parallel_optimum.q1_deg- ...
    study.representative.q1_deg), '--', 'LineWidth', 1.5, ...
    'DisplayName', '|q_1 deviation| (deg)');
xlabel(ax, 'Knee flexion q_2 (deg)');
ylabel(ax, 'Force (N) or hip deviation (deg)');
title(ax, 'Current V2 return versus force-mode posture optimum');
grid(ax, 'on');
legend(ax, 'Location', 'best');
set(ax, 'XDir', 'reverse');
exportgraphics(fig, output_path, 'Resolution', 180);
close(fig);
end


function save_support_plot(study, path_data, bound_index, output_path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [100, 100, 1000, 700]);
layout = tiledlayout(fig, 2, 1, 'TileSpacing', 'compact');
ax1 = nexttile(layout, 1);
plot_support_components(ax1, path_data.q_deg(2, :), ...
    path_data.support_torque(:, :, bound_index), ...
    path_data.support_norm(:, bound_index), 'Current V2 return');
set(ax1, 'XDir', 'reverse');
ax2 = nexttile(layout, 2);
plot_support_components(ax2, study.q2_deg, ...
    study.parallel_optimum.support_torque(:, :, bound_index), ...
    study.parallel_optimum.support_norm(:, bound_index), ...
    'Minimum-|F_{parallel}| posture curve');
xlabel(ax2, 'Knee flexion q_2 (deg)');
title(layout, sprintf(['Abstract external-support generalized-torque ' ...
    'residual, robot bound +/-%.0f N'], ...
    study.component_bounds_N(bound_index)));
exportgraphics(fig, output_path, 'Resolution', 180);
close(fig);
end


function plot_support_components(ax, q2, torque, residual_norm, label)
plot(ax, q2, residual_norm, 'k-', 'LineWidth', 1.8, ...
    'DisplayName', '||\tau_{support}||');
hold(ax, 'on');
plot(ax, q2, squeeze(torque(1, :)), 'LineWidth', 1.5, ...
    'DisplayName', 'hip component');
plot(ax, q2, squeeze(torque(2, :)), 'LineWidth', 1.5, ...
    'DisplayName', 'knee component');
yline(ax, 0, 'k:', 'HandleVisibility', 'off');
ylabel(ax, 'Generalized torque (N m)');
title(ax, label);
grid(ax, 'on');
legend(ax, 'Location', 'best');
end


function write_summary(path, summary, bounds, command)
file = fopen(path, 'w');
if file < 0
    error('NearExtensionForceMode:SummaryOpenFailed', ...
        'Could not open summary output.');
end
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'near_extension_force_mode_feasibility\n');
fprintf(file, 'generated_utc=%s\nmatlab_version=%s\ncommand=%s\n', ...
    char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX')), version, command);
fprintf(file, 'definition=dq=[0;0], ddq=[0;0]\n');
fprintf(file, 'current_start_force_norm_N=%.12g\n', ...
    summary.current_start_force_norm_N);
fprintf(file, 'q2_10_optimal_q1_deg=%.12g\n', ...
    summary.q2_10_optimal_q1_deg);
fprintf(file, 'q2_10_optimal_F_parallel_N=%.12g\n', ...
    summary.q2_10_optimal_F_parallel_N);
fprintf(file, 'q2_10_optimal_force_norm_N=%.12g\n', ...
    summary.q2_10_optimal_force_norm_N);
fprintf(file, 'q2_10_parallel_reduction_fraction=%.12g\n', ...
    summary.q2_10_parallel_reduction_fraction);
fprintf(file, 'q2_zero_rank_deficient=%d\n', ...
    summary.q2_zero_rank_deficient);
for record = summary.key_postures
    fprintf(file, ['key_q2_%.0f=representative_q1 %.12g, Fparallel %.12g, ' ...
        'Fperp %.12g, norm %.12g, sigma %.12g, cond %.12g; ' ...
        'optimal_q1 %.12g, Fparallel %.12g, Fperp %.12g, norm %.12g, ' ...
        'sigma %.12g, cond %.12g, q1_deviation %.12g\n'], ...
        record.q2_deg, record.representative_q1_deg, ...
        record.representative_F_parallel_N, record.representative_F_perp_N, ...
        record.representative_force_norm_N, ...
        record.representative_sigma_min, record.representative_cond_A, ...
        record.optimal_q1_deg, record.optimal_F_parallel_N, ...
        record.optimal_F_perp_N, record.optimal_force_norm_N, ...
        record.optimal_sigma_min, record.optimal_cond_A, ...
        record.q1_deviation_deg);
end
for index = 1:numel(bounds)
    fprintf(file, 'bound_%.0fN_return_support_onset_q2_deg=%.12g\n', ...
        bounds(index), summary.return_support_onset_q2_deg(index));
    fprintf(file, 'bound_%.0fN_return_support_peak_norm_Nm=%.12g\n', ...
        bounds(index), summary.return_support_peak_norm_Nm(index));
    fprintf(file, 'bound_%.0fN_return_support_peak_hip_Nm=%.12g\n', ...
        bounds(index), summary.return_support_peak_hip_Nm(index));
    fprintf(file, 'bound_%.0fN_return_support_peak_knee_Nm=%.12g\n', ...
        bounds(index), summary.return_support_peak_knee_Nm(index));
    fprintf(file, 'bound_%.0fN_return_support_dominant=%s\n', ...
        bounds(index), summary.return_support_dominant(index));
    fprintf(file, 'bound_%.0fN_optimum_support_q2_range=%s\n', ...
        bounds(index), summary.optimum_support_q2_description(index));
    fprintf(file, 'bound_%.0fN_optimum_support_peak_norm_Nm=%.12g\n', ...
        bounds(index), summary.optimum_support_peak_norm_Nm(index));
    fprintf(file, 'bound_%.0fN_optimum_support_dominant=%s\n', ...
        bounds(index), summary.optimum_support_dominant(index));
    write_crossing(file, sprintf('parallel_%.0fN', bounds(index)), ...
        summary.parallel_threshold_crossings(index));
    write_crossing(file, sprintf('norm_%.0fN', bounds(index)), ...
        summary.norm_threshold_crossings(index));
end
fprintf(file, ['scope=offline quasistatic mechanics feasibility only; ' ...
    'support residual is not a bed/contact model\n']);
end


function write_crossing(file, name, crossing)
fprintf(file, '%s_found=%d\n', name, crossing.found);
fprintf(file, '%s_q1_deg=%.12g\n%s_q2_deg=%.12g\n', ...
    name, crossing.q1_deg, name, crossing.q2_deg);
fprintf(file, '%s_time_s=%.12g\n%s_value_N=%.12g\n', ...
    name, crossing.time_s, name, crossing.value_N);
end
