function run_robot_only_preposition_force_margin_map()
%RUN_ROBOT_ONLY_PREPOSITION_FORCE_MARGIN_MAP Quasistatic tube diagnostic.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'bed_supported_load_transfer_v1', ...
    'robot_only_preposition_force_margin_map');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

p = human_two_link_v2_parameters(1.72, 75);
tube_caps_deg = [5, 10];
component_bounds_N = [80, 120, 200];
grid_resolution_deg = 0.1;
svd_relative_tolerance = 1e-12;
study = bed_supported_v1_force_margin_map(p, tube_caps_deg, ...
    component_bounds_N, grid_resolution_deg, svd_relative_tolerance);
current_q_deg = [7; 20];
current = bed_supported_v1_force_margin_point(deg2rad(current_q_deg), ...
    p, component_bounds_N, svd_relative_tolerance);
study.current_preposition_q_deg = current_q_deg;
study.current_preposition = current;

samples = samples_table(study);
summary_table = results_table(study, current);
save(fullfile(output_dir, 'robot_only_preposition_force_margin_map.mat'), ...
    'study', 'samples', 'summary_table', '-v7.3');
writetable(samples, fullfile(output_dir, ...
    'robot_only_preposition_force_margin_samples.csv'));
writetable(summary_table, fullfile(output_dir, ...
    'robot_only_preposition_force_margin_summary.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), study, current);

tube_10 = study.tubes([study.tubes.cap_deg] == 10);
for bound_index = 1:numel(component_bounds_N)
    bound_N = component_bounds_N(bound_index);
    path = fullfile(output_dir, sprintf( ...
        'force_margin_%gN_10deg_tube.png', bound_N));
    save_margin_map(tube_10, bound_index, study.q0_deg, ...
        current_q_deg, path);
end
save_best_margin_plot(study, fullfile(output_dir, ...
    'best_margin_vs_force_bound.png'));

if ~isempty(findall(groot, 'Type', 'figure', 'Visible', 'on'))
    error('BedSupportedV1:VisibleForceMarginFigure', ...
        'Force-margin runner created a visible figure.');
end
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
end


function table_out = samples_table(study)
rows = cell(1, numel(study.tubes));
bounds = study.component_bounds_N;
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    count = numel(tube.q1_grid_deg);
    table_out = table( ...
        repmat(tube.cap_deg, count, 1), tube.q1_grid_deg(:), ...
        tube.q2_grid_deg(:), tube.F_parallel_N(:), tube.F_perp_N(:), ...
        tube.force_norm_2_N(:), tube.force_norm_inf_N(:), ...
        tube.sigma_min(:), tube.condition_number(:), ...
        tube.soft_limit_active(:), tube.soft_limit_margin_deg(:), ...
        tube.exact_torque_residual_norm_Nm(:), ...
        'VariableNames', {'tube_cap_deg', 'q1_deg', 'q2_deg', ...
        'F_parallel_N', 'F_perp_N', 'force_norm_2_N', ...
        'force_norm_inf_N', 'sigma_min', 'condition_number', ...
        'soft_limit_active', 'soft_limit_margin_deg', ...
        'exact_torque_residual_norm_Nm'});
    for bound_index = 1:numel(bounds)
        suffix = sprintf('%gN', bounds(bound_index));
        table_out.(['force_margin_' suffix]) = ...
            reshape(tube.force_margin_N(:, :, bound_index), [], 1);
        table_out.(['feasible_' suffix]) = ...
            reshape(tube.feasible(:, :, bound_index), [], 1);
        table_out.(['robust_feasible_' suffix]) = ...
            reshape(tube.robust_feasible(:, :, bound_index), [], 1);
    end
    rows{tube_index} = table_out;
end
table_out = vertcat(rows{:});
end


function table_out = results_table(study, current)
row_count = numel(study.tubes)*numel(study.component_bounds_N);
tube_cap_deg = zeros(row_count, 1);
component_bound_N = zeros(row_count, 1);
maximum_margin_N = zeros(row_count, 1);
optimal_q1_deg = zeros(row_count, 1);
optimal_q2_deg = zeros(row_count, 1);
F_parallel_N = zeros(row_count, 1);
F_perp_N = zeros(row_count, 1);
force_norm_2_N = zeros(row_count, 1);
force_norm_inf_N = zeros(row_count, 1);
sigma_min = zeros(row_count, 1);
condition_number = zeros(row_count, 1);
soft_limit_margin_deg = zeros(row_count, 1);
feasible_fraction = zeros(row_count, 1);
robust_feasible_fraction = zeros(row_count, 1);
current_margin_N = NaN(row_count, 1);
current_margin_loss_N = NaN(row_count, 1);
raw_maximum_margin_N = zeros(row_count, 1);
raw_optimal_q1_deg = zeros(row_count, 1);
raw_optimal_q2_deg = zeros(row_count, 1);
raw_optimum_soft_limit_active = false(row_count, 1);
row = 0;
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    for bound_index = 1:numel(study.component_bounds_N)
        row = row+1;
        best = tube.best(bound_index);
        raw_best = tube.raw_best(bound_index);
        tube_cap_deg(row) = tube.cap_deg;
        component_bound_N(row) = best.component_bound_N;
        maximum_margin_N(row) = best.maximum_margin_N;
        optimal_q1_deg(row) = best.q_deg(1);
        optimal_q2_deg(row) = best.q_deg(2);
        F_parallel_N(row) = best.F_parallel_N;
        F_perp_N(row) = best.F_perp_N;
        force_norm_2_N(row) = best.force_norm_2_N;
        force_norm_inf_N(row) = best.force_norm_inf_N;
        sigma_min(row) = best.sigma_min;
        condition_number(row) = best.condition_number;
        soft_limit_margin_deg(row) = best.soft_limit_margin_deg;
        feasible_fraction(row) = best.feasible_fraction;
        robust_feasible_fraction(row) = best.robust_feasible_fraction;
        raw_maximum_margin_N(row) = raw_best.maximum_margin_N;
        raw_optimal_q1_deg(row) = raw_best.q_deg(1);
        raw_optimal_q2_deg(row) = raw_best.q_deg(2);
        raw_optimum_soft_limit_active(row) = raw_best.soft_limit_active;
        if tube.cap_deg == 10
            current_margin_N(row) = current.force_margin_N(bound_index);
            current_margin_loss_N(row) = best.maximum_margin_N- ...
                current.force_margin_N(bound_index);
        end
    end
end
table_out = table(tube_cap_deg, component_bound_N, maximum_margin_N, ...
    optimal_q1_deg, optimal_q2_deg, F_parallel_N, F_perp_N, ...
    force_norm_2_N, force_norm_inf_N, sigma_min, condition_number, ...
    soft_limit_margin_deg, feasible_fraction, robust_feasible_fraction, ...
    current_margin_N, current_margin_loss_N, raw_maximum_margin_N, ...
    raw_optimal_q1_deg, raw_optimal_q2_deg, ...
    raw_optimum_soft_limit_active);
end


function write_summary(path, study, current)
file = fopen(path, 'w');
assert(file >= 0);
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'Robot-only preposition force-margin map\n');
fprintf(file, 'MATLAB %s\n', version);
fprintf(file, 'q0=[5 10] deg; grid=%.3g deg; dq=ddq=0\n', ...
    study.grid_resolution_deg);
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    for bound_index = 1:numel(study.component_bounds_N)
        best = tube.best(bound_index);
        raw_best = tube.raw_best(bound_index);
        fprintf(file, ['tube=%g deg bound=%g N max_margin=%.9g N ' ...
            'q=[%.3f %.3f] deg F=[%.9g %.9g] N norm2=%.9g N ' ...
            'sigma_min=%.9g cond=%.9g soft_margin=%.3f deg ' ...
            'feasible_fraction=%.9g robust_feasible_fraction=%.9g ' ...
            'residual=%.9g Nm\n'], tube.cap_deg, ...
            best.component_bound_N, best.maximum_margin_N, ...
            best.q_deg(1), best.q_deg(2), best.F_parallel_N, ...
            best.F_perp_N, best.force_norm_2_N, best.sigma_min, ...
            best.condition_number, best.soft_limit_margin_deg, ...
            best.feasible_fraction, best.robust_feasible_fraction, ...
            best.exact_torque_residual_norm_Nm);
        fprintf(file, ['  raw maximum including soft-limit-active: ' ...
            'margin=%.9g N q=[%.3f %.3f] deg active=%d\n'], ...
            raw_best.maximum_margin_N, raw_best.q_deg(1), ...
            raw_best.q_deg(2), raw_best.soft_limit_active);
    end
end
fprintf(file, ['current q=[7 20] deg F=[%.9g %.9g] N norm2=%.9g N ' ...
    'norm_inf=%.9g N sigma_min=%.9g cond=%.9g ' ...
    'soft_margin=%.3f deg residual=%.9g Nm\n'], ...
    current.F_parallel_N, current.F_perp_N, current.force_norm_2_N, ...
    current.force_norm_inf_N, current.sigma_min, ...
    current.condition_number, ...
    rad2deg(current.minimum_soft_limit_margin_rad), ...
    current.exact_torque_residual_norm_Nm);
for bound_index = 1:numel(study.component_bounds_N)
    tube_10 = study.tubes([study.tubes.cap_deg] == 10);
    best = tube_10.best(bound_index);
    fprintf(file, ['current bound=%g N margin=%.9g N ' ...
        'loss_to_10deg_optimum=%.9g N\n'], ...
        study.component_bounds_N(bound_index), ...
        current.force_margin_N(bound_index), ...
        best.maximum_margin_N-current.force_margin_N(bound_index));
end
end


function save_margin_map(tube, bound_index, nominal_q_deg, ...
        current_q_deg, path)
best = tube.best(bound_index);
raw_best = tube.raw_best(bound_index);
margin = tube.force_margin_N(:, :, bound_index);
display_margin = max(margin, -best.component_bound_N);
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [40, 40, 980, 760]);
ax = axes(fig);
imagesc(ax, tube.q1_deg, tube.q2_deg, display_margin);
set(ax, 'YDir', 'normal');
axis(ax, 'tight');
hold(ax, 'on');
colormap(ax, turbo);
colorbar(ax);
active = tube.soft_limit_active;
scatter(ax, tube.q1_grid_deg(active), tube.q2_grid_deg(active), ...
    7, [0.35, 0.35, 0.35], 'filled', 'MarkerFaceAlpha', 0.22, ...
    'HandleVisibility', 'off');
h_nominal = plot(ax, nominal_q_deg(1), nominal_q_deg(2), 'wo', ...
    'MarkerFaceColor', 'k', 'MarkerSize', 8, 'LineWidth', 1.2);
h_current = plot(ax, current_q_deg(1), current_q_deg(2), 'ws', ...
    'MarkerFaceColor', [0.95, 0.55, 0.05], 'MarkerSize', 8, ...
    'LineWidth', 1.2);
h_best = plot(ax, best.q_deg(1), best.q_deg(2), 'wp', ...
    'MarkerFaceColor', [0.1, 0.7, 0.2], 'MarkerSize', 12, ...
    'LineWidth', 1.2);
h_raw = plot(ax, raw_best.q_deg(1), raw_best.q_deg(2), 'x', ...
    'Color', [0.25, 0.25, 0.25], 'MarkerSize', 10, 'LineWidth', 2);
xlabel(ax, 'q_1 (deg)');
ylabel(ax, 'q_2 (deg)');
title(ax, sprintf(['Robot-only hold force margin, B=%g N, 10 deg tube' ...
    '\nvalues below -%g N visually clipped; gray samples soft-limit active'], ...
    best.component_bound_N, best.component_bound_N));
legend(ax, [h_nominal, h_current, h_raw, h_best], ...
    {'nominal [5,10]', 'current [7,20]', ...
    sprintf('raw max, active [%.1f,%.1f]', raw_best.q_deg), ...
    sprintf('recommended non-active max [%.1f,%.1f]', best.q_deg)}, ...
    'Location', 'southoutside', 'Orientation', 'horizontal');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_best_margin_plot(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [40, 40, 850, 600]);
ax = axes(fig);
hold(ax, 'on');
grid(ax, 'on');
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    plot(ax, study.component_bounds_N, ...
        [tube.best.maximum_margin_N], '-o', 'LineWidth', 1.8, ...
        'DisplayName', sprintf('%g deg tube', tube.cap_deg));
end
yline(ax, 0, 'k--', 'zero reserve');
xlabel(ax, 'component force bound B (N)');
ylabel(ax, 'maximum nominal force margin (N)');
title(ax, 'Best robot-only hold reserve within initial tubes');
legend(ax, 'Location', 'northwest');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end
