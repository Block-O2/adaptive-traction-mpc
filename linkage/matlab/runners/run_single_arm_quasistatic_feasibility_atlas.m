function run_single_arm_quasistatic_feasibility_atlas()
%RUN_SINGLE_ARM_QUASISTATIC_FEASIBILITY_ATLAS Headless static force atlas.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'single_arm_quasistatic_feasibility_atlas');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

command = ['matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_single_arm_quasistatic_feasibility_atlas"'];
fprintf('SINGLE-ARM QUASISTATIC FEASIBILITY ATLAS\n');
fprintf('MATLAB: %s\n', version);
fprintf('COMMAND: %s\n', command);
fprintf('OUTPUT: %s\n', output_dir);

p = human_two_link_v2_parameters(1.72, 75.0);
q1_deg = 0:1:80;
q2_deg = 0:1:100;
component_bounds_N = [80, 120, 200];
svd_relative_tolerance = 1e-12;
atlas = single_arm_quasistatic_atlas_grid( ...
    p, q1_deg, q2_deg, component_bounds_N, svd_relative_tolerance);

validate_atlas(atlas);
summary = summarize_atlas(atlas, p);
reference = evaluate_current_reference(p, svd_relative_tolerance);
summary.reference_min_force_N = min(reference.force_norm);
summary.reference_max_force_N = max(reference.force_norm);
[~, reference_min_index] = min(reference.force_norm);
[~, reference_max_index] = max(reference.force_norm);
summary.reference_min_time_s = reference.t(reference_min_index);
summary.reference_max_time_s = reference.t(reference_max_index);
summary.reference_min_q_deg = rad2deg(reference.q(:, reference_min_index));
summary.reference_max_q_deg = rad2deg(reference.q(:, reference_max_index));

write_grid_csv(atlas, fullfile(output_dir, 'atlas_grid.csv'));
write_minimum_knee_csv(atlas, fullfile(output_dir, ...
    'minimum_feasible_knee_flexion.csv'));
save(fullfile(output_dir, 'atlas_workspace.mat'), ...
    'atlas', 'reference', 'summary', 'p', 'command');
write_summary(fullfile(output_dir, 'summary.txt'), ...
    atlas, reference, summary, p, command);
create_plots(atlas, reference, output_dir);

fprintf(['ATLAS SUMMARY: minimum=%.6f N at [%.0f, %.0f] deg; ' ...
    'maximum nonsingular=%.6f N at [%.0f, %.0f] deg\n'], ...
    summary.minimum_force_N, summary.minimum_force_q_deg, ...
    summary.maximum_force_N, summary.maximum_force_q_deg);
fprintf(['START [5,10] deg: F_parallel=%.6f N F_perp=%.6f N ' ...
    '|F|=%.6f N cond(A)=%.6f\n'], ...
    summary.start.F_parallel_N, summary.start.F_perp_N, ...
    summary.start.force_norm_N, summary.start.condition_number);
fprintf(['PEAK [45,84] deg: F_parallel=%.6f N F_perp=%.6f N ' ...
    '|F|=%.6f N cond(A)=%.6f\n'], ...
    summary.peak.F_parallel_N, summary.peak.F_perp_N, ...
    summary.peak.force_norm_N, summary.peak.condition_number);
for bound_index = 1:numel(component_bounds_N)
    fprintf(['BOUND +/-%.0f N: feasible=%d/%d (%.6f%% all grid), ' ...
        'start=%d peak=%d\n'], component_bounds_N(bound_index), ...
        summary.feasible_count(bound_index), summary.grid_count, ...
        100*summary.feasible_fraction_all(bound_index), ...
        summary.start.feasible(bound_index), ...
        summary.peak.feasible(bound_index));
end
fprintf('REFERENCE STATIC FORCE RANGE: %.6f to %.6f N\n', ...
    summary.reference_min_force_N, summary.reference_max_force_N);
fprintf('ATLAS COMPLETE\n');
end


function validate_atlas(atlas)
zero_knee = atlas.q2_deg == 0;
if ~all(atlas.rank_deficient(zero_knee, :), 'all') || ...
        ~all(isnan(atlas.force_norm(zero_knee, :)), 'all')
    error('SingleArmQuasistatic:SingularRowInvalid', ...
        'The q2=0 row must be rank deficient with NaN exact force.');
end
valid = ~atlas.rank_deficient;
signals = [atlas.F_parallel(valid); atlas.F_perp(valid); ...
    atlas.force_norm(valid); atlas.torque_residual_norm(valid); ...
    atlas.sigma_min(valid); atlas.condition_number(valid); atlas.det_A(valid)];
if any(~isfinite(signals))
    error('SingleArmQuasistatic:NonfiniteAtlas', ...
        'All nonsingular atlas results must be finite.');
end
if max(atlas.torque_residual_norm(valid)) > 1e-9
    error('SingleArmQuasistatic:ResidualTooLarge', ...
        'A nonsingular exact-force residual exceeded tolerance.');
end
for bound_index = 1:numel(atlas.component_bounds_N)
    limit = atlas.component_bounds_N(bound_index);
    expected = valid & abs(atlas.F_parallel) <= limit+1e-10 & ...
        abs(atlas.F_perp) <= limit+1e-10;
    if ~isequal(atlas.feasible(:, :, bound_index), expected)
        error('SingleArmQuasistatic:FeasibilityMaskMismatch', ...
            'A feasibility mask disagrees with its component bound.');
    end
end
end


function summary = summarize_atlas(atlas, p)
valid_indices = find(~atlas.rank_deficient & isfinite(atlas.force_norm));
[minimum_force, minimum_local_index] = ...
    min(atlas.force_norm(valid_indices));
[maximum_force, maximum_local_index] = ...
    max(atlas.force_norm(valid_indices));
minimum_index = valid_indices(minimum_local_index);
maximum_index = valid_indices(maximum_local_index);
[minimum_q2_index, minimum_q1_index] = ...
    ind2sub(size(atlas.force_norm), minimum_index);
[maximum_q2_index, maximum_q1_index] = ...
    ind2sub(size(atlas.force_norm), maximum_index);

summary = struct();
summary.grid_count = numel(atlas.force_norm);
summary.nonsingular_count = numel(valid_indices);
summary.singular_count = sum(atlas.rank_deficient, 'all');
summary.minimum_force_N = minimum_force;
summary.minimum_force_q_deg = [atlas.q1_deg(minimum_q1_index); ...
    atlas.q2_deg(minimum_q2_index)];
summary.maximum_force_N = maximum_force;
summary.maximum_force_q_deg = [atlas.q1_deg(maximum_q1_index); ...
    atlas.q2_deg(maximum_q2_index)];
summary.maximum_exact_torque_residual_Nm = ...
    max(atlas.torque_residual_norm(valid_indices));
summary.feasible_count = squeeze(sum(atlas.feasible, [1, 2]))';
summary.feasible_fraction_all = summary.feasible_count/summary.grid_count;
summary.feasible_fraction_nonsingular = ...
    summary.feasible_count/summary.nonsingular_count;
summary.start = point_summary(deg2rad([5; 10]), p, ...
    atlas.component_bounds_N, atlas.svd_relative_tolerance);
summary.peak = point_summary(deg2rad([45; 84]), p, ...
    atlas.component_bounds_N, atlas.svd_relative_tolerance);

[Q1, Q2] = meshgrid(atlas.q1_deg, atlas.q2_deg);
high_force = isfinite(atlas.force_norm) & atlas.force_norm >= 300;
ill_conditioned = isfinite(atlas.condition_number) & ...
    atlas.condition_number >= 100;
summary.force_at_least_300_count = sum(high_force, 'all');
summary.force_at_least_300_q2_range_deg = mask_q2_range(Q2, high_force);
summary.cond_at_least_100_count = sum(ill_conditioned, 'all');
summary.cond_at_least_100_q2_range_deg = ...
    mask_q2_range(Q2, ill_conditioned);
summary.q1_mesh_deg = Q1;
summary.q2_mesh_deg = Q2;
end


function record = point_summary(q, p, bounds, tolerance)
point = single_arm_quasistatic_hold_point(q, p, bounds, tolerance);
record = struct('q_deg', rad2deg(q), ...
    'F_parallel_N', point.F_parallel, ...
    'F_perp_N', point.F_perp, ...
    'force_norm_N', point.force_norm, ...
    'condition_number', point.condition_number, ...
    'sigma_min', point.sigma_min, ...
    'gravity_torque_Nm', point.gravity_torque, ...
    'passive_torque_Nm', point.passive_torque_left, ...
    'holding_torque_Nm', point.holding_torque, ...
    'component_bounds_N', point.component_bounds_N, ...
    'feasible', point.exact_feasible, ...
    'bounded_residual_Nm', point.bounded_residual_norm);
end


function range = mask_q2_range(Q2, mask)
values = Q2(mask);
if isempty(values)
    range = [NaN; NaN];
else
    range = [min(values); max(values)];
end
end


function reference = evaluate_current_reference(p, tolerance)
t = 0:0.002:16.0;
n = numel(t);
q = zeros(2, n);
force = zeros(2, n);
force_norm = zeros(1, n);
condition_number = zeros(1, n);
sigma_min = zeros(1, n);
for index = 1:n
    q(:, index) = human_two_link_v2_reference( ...
        t(index), "slow_passive_flexion_v2");
    point = single_arm_quasistatic_hold_point( ...
        q(:, index), p, [], tolerance);
    force(:, index) = point.force_local;
    force_norm(index) = point.force_norm;
    condition_number(index) = point.mapping.condition_number;
    sigma_min(index) = point.mapping.sigma_min;
end
reference = struct('t', t, 'q', q, 'force_local', force, ...
    'force_norm', force_norm, 'condition_number', condition_number, ...
    'sigma_min', sigma_min, ...
    'trajectory_name', "slow_passive_flexion_v2");
end


function write_grid_csv(atlas, path)
[Q1, Q2] = meshgrid(atlas.q1_deg, atlas.q2_deg);
table_data = table(Q1(:), Q2(:), atlas.rank_deficient(:), ...
    atlas.F_parallel(:), atlas.F_perp(:), atlas.force_norm(:), ...
    component(atlas.torque_residual, 1), ...
    component(atlas.torque_residual, 2), atlas.torque_residual_norm(:), ...
    atlas.sigma_min(:), atlas.condition_number(:), atlas.det_A(:), ...
    component(atlas.gravity_torque, 1), ...
    component(atlas.gravity_torque, 2), ...
    component(atlas.passive_torque_left, 1), ...
    component(atlas.passive_torque_left, 2), ...
    component(atlas.holding_torque, 1), ...
    component(atlas.holding_torque, 2), ...
    logical_slice(atlas.feasible, 1), ...
    logical_slice(atlas.feasible, 2), ...
    logical_slice(atlas.feasible, 3), ...
    numeric_slice(atlas.bounded_residual_norm, 1), ...
    numeric_slice(atlas.bounded_residual_norm, 2), ...
    numeric_slice(atlas.bounded_residual_norm, 3), ...
    'VariableNames', {'q1_deg', 'q2_deg', 'rank_deficient', ...
    'F_parallel_N', 'F_perp_N', 'force_norm_N', ...
    'torque_residual_hip_Nm', 'torque_residual_knee_Nm', ...
    'torque_residual_norm_Nm', 'sigma_min_A', 'cond_A', 'det_A', ...
    'gravity_hip_Nm', 'gravity_knee_Nm', ...
    'passive_hip_Nm', 'passive_knee_Nm', ...
    'holding_hip_Nm', 'holding_knee_Nm', ...
    'feasible_80N', 'feasible_120N', 'feasible_200N', ...
    'bounded_residual_80N_Nm', 'bounded_residual_120N_Nm', ...
    'bounded_residual_200N_Nm'});
writetable(table_data, path);
end


function values = component(array, index)
slice = array(:, :, index);
values = slice(:);
end


function values = logical_slice(array, index)
slice = array(:, :, index);
values = slice(:);
end


function values = numeric_slice(array, index)
slice = array(:, :, index);
values = slice(:);
end


function write_minimum_knee_csv(atlas, path)
minimums = atlas.minimum_feasible_q2_deg;
table_data = table(atlas.q1_deg(:), minimums(1, :)', ...
    minimums(2, :)', minimums(3, :)', ...
    'VariableNames', {'q1_deg', 'q2_min_80N_deg', ...
    'q2_min_120N_deg', 'q2_min_200N_deg'});
writetable(table_data, path);
end


function create_plots(atlas, reference, output_dir)
save_log_map(atlas, atlas.force_norm, 'log_{10}(|F| / N)', ...
    'Quasistatic holding-force norm (q_2=0 singular)', ...
    fullfile(output_dir, 'force_norm_map.png'));
save_signed_map(atlas, atlas.F_parallel, 'F_{parallel} (N)', ...
    'Force along the shank axis', ...
    fullfile(output_dir, 'force_parallel_map.png'));
save_signed_map(atlas, atlas.F_perp, 'F_{perp} (N)', ...
    'Force perpendicular to the shank axis', ...
    fullfile(output_dir, 'force_perp_map.png'));
save_log_map(atlas, atlas.condition_number, 'log_{10}(cond(A))', ...
    'Force-map conditioning (q_2=0 singular)', ...
    fullfile(output_dir, 'conditioning_map.png'));
save_linear_map(atlas, atlas.sigma_min, '\sigma_{min}(A)', ...
    'Minimum singular value of force map', ...
    fullfile(output_dir, 'sigma_min_map.png'));
for bound_index = 1:numel(atlas.component_bounds_N)
    limit = atlas.component_bounds_N(bound_index);
    save_feasibility_map(atlas, atlas.feasible(:, :, bound_index), ...
        limit, fullfile(output_dir, sprintf('feasibility_%dN.png', limit)));
end
save_minimum_knee_plot(atlas, fullfile(output_dir, ...
    'minimum_feasible_knee_flexion.png'));
save_reference_overlay(atlas, reference, fullfile(output_dir, ...
    'force_norm_map_with_v2_reference.png'));
end


function [fig, ax] = base_figure()
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [100, 100, 900, 650]);
ax = axes(fig);
end


function decorate_map(ax, atlas, label_text, title_text)
set(ax, 'YDir', 'normal', 'FontSize', 11);
xlabel(ax, 'Hip angle q_1 (deg)');
ylabel(ax, 'Knee flexion q_2 (deg)');
title(ax, title_text);
cb = colorbar(ax);
cb.Label.String = label_text;
xlim(ax, [atlas.q1_deg(1), atlas.q1_deg(end)]);
ylim(ax, [atlas.q2_deg(1), atlas.q2_deg(end)]);
end


function save_log_map(atlas, data, label_text, title_text, path)
[fig, ax] = base_figure();
display_data = log10(data);
display_data(~isfinite(display_data)) = NaN;
imagesc(ax, atlas.q1_deg, atlas.q2_deg, display_data);
decorate_map(ax, atlas, label_text, title_text);
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_linear_map(atlas, data, label_text, title_text, path)
[fig, ax] = base_figure();
display_data = data;
display_data(~isfinite(display_data)) = NaN;
imagesc(ax, atlas.q1_deg, atlas.q2_deg, display_data);
decorate_map(ax, atlas, label_text, title_text);
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_signed_map(atlas, data, label_text, title_text, path)
[fig, ax] = base_figure();
imagesc(ax, atlas.q1_deg, atlas.q2_deg, data);
finite_absolute = sort(abs(data(isfinite(data))));
display_limit = finite_absolute(max(1, ceil(0.99*numel(finite_absolute))));
display_limit = max(display_limit, 1);
clim(ax, [-display_limit, display_limit]);
decorate_map(ax, atlas, label_text, ...
    sprintf('%s (display clipped at +/-%.1f N)', title_text, display_limit));
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_feasibility_map(atlas, mask, limit, path)
[fig, ax] = base_figure();
imagesc(ax, atlas.q1_deg, atlas.q2_deg, double(mask));
colormap(ax, [0.75, 0.20, 0.20; 0.15, 0.65, 0.30]);
clim(ax, [0, 1]);
decorate_map(ax, atlas, '0 infeasible, 1 feasible', ...
    sprintf('Exact quasistatic feasibility under +/-%.0f N components', limit));
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_minimum_knee_plot(atlas, path)
[fig, ax] = base_figure();
hold(ax, 'on');
colors = lines(numel(atlas.component_bounds_N));
for index = 1:numel(atlas.component_bounds_N)
    plot(ax, atlas.q1_deg, atlas.minimum_feasible_q2_deg(index, :), ...
        'LineWidth', 1.8, 'Color', colors(index, :), ...
        'DisplayName', sprintf('+/-%.0f N', atlas.component_bounds_N(index)));
end
xlabel(ax, 'Hip angle q_1 (deg)');
ylabel(ax, 'Minimum feasible knee flexion q_{2,min} (deg)');
title(ax, 'Minimum exact-feasible knee flexion by hip angle');
grid(ax, 'on');
legend(ax, 'Location', 'best');
xlim(ax, [atlas.q1_deg(1), atlas.q1_deg(end)]);
ylim(ax, [atlas.q2_deg(1), atlas.q2_deg(end)]);
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function save_reference_overlay(atlas, reference, path)
[fig, ax] = base_figure();
display_data = log10(atlas.force_norm);
display_data(~isfinite(display_data)) = NaN;
imagesc(ax, atlas.q1_deg, atlas.q2_deg, display_data);
hold(ax, 'on');
plot(ax, rad2deg(reference.q(1, :)), rad2deg(reference.q(2, :)), ...
    'w-', 'LineWidth', 2.5);
plot(ax, rad2deg(reference.q(1, 1)), rad2deg(reference.q(2, 1)), ...
    'wo', 'MarkerFaceColor', 'k', 'MarkerSize', 7);
plot(ax, rad2deg(reference.q(1, 3751)), rad2deg(reference.q(2, 3751)), ...
    'ws', 'MarkerFaceColor', 'k', 'MarkerSize', 7);
decorate_map(ax, atlas, 'log_{10}(|F| / N)', ...
    'Current V2 reference over quasistatic force map');
legend(ax, {'V2 reference path', 'start', 'peak'}, ...
    'Location', 'southoutside', 'Orientation', 'horizontal');
exportgraphics(fig, path, 'Resolution', 180);
close(fig);
end


function write_summary(path, atlas, reference, summary, p, command)
file = fopen(path, 'w');
if file < 0
    error('SingleArmQuasistatic:SummaryOpenFailed', ...
        'Could not open summary output.');
end
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'single_arm_quasistatic_feasibility_atlas\n');
fprintf(file, 'generated_utc=%s\n', char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX')));
fprintf(file, 'matlab_version=%s\n', version);
fprintf(file, 'command=%s\n', command);
fprintf(file, 'definition=dq=[0;0], ddq=[0;0]\n');
fprintf(file, 'height_m=%.12g\nbody_mass_kg=%.12g\nsc_m=%.12g\n', ...
    p.height_m, p.body_mass_kg, p.sc);
fprintf(file, 'grid_q1_deg=0:1:80\ngrid_q2_deg=0:1:100\n');
fprintf(file, 'grid_count=%d\nnonsingular_count=%d\nsingular_count=%d\n', ...
    summary.grid_count, summary.nonsingular_count, summary.singular_count);
fprintf(file, 'minimum_force_N=%.12g\nminimum_force_q1_deg=%.12g\n', ...
    summary.minimum_force_N, summary.minimum_force_q_deg(1));
fprintf(file, 'minimum_force_q2_deg=%.12g\n', ...
    summary.minimum_force_q_deg(2));
fprintf(file, 'maximum_nonsingular_force_N=%.12g\n', ...
    summary.maximum_force_N);
fprintf(file, 'maximum_force_q1_deg=%.12g\nmaximum_force_q2_deg=%.12g\n', ...
    summary.maximum_force_q_deg(1), summary.maximum_force_q_deg(2));
fprintf(file, 'maximum_exact_torque_residual_Nm=%.12g\n', ...
    summary.maximum_exact_torque_residual_Nm);
write_point(file, 'start', summary.start);
write_point(file, 'peak', summary.peak);
fprintf(file, 'reference_min_static_force_N=%.12g\n', ...
    summary.reference_min_force_N);
fprintf(file, 'reference_max_static_force_N=%.12g\n', ...
    summary.reference_max_force_N);
fprintf(file, 'reference_min_time_s=%.12g\nreference_max_time_s=%.12g\n', ...
    summary.reference_min_time_s, summary.reference_max_time_s);
for bound_index = 1:numel(atlas.component_bounds_N)
    label = sprintf('%dN', atlas.component_bounds_N(bound_index));
    fprintf(file, 'feasible_count_%s=%d\n', label, ...
        summary.feasible_count(bound_index));
    fprintf(file, 'feasible_fraction_all_%s=%.12g\n', label, ...
        summary.feasible_fraction_all(bound_index));
    fprintf(file, 'feasible_fraction_nonsingular_%s=%.12g\n', label, ...
        summary.feasible_fraction_nonsingular(bound_index));
end
fprintf(file, 'force_at_least_300_count=%d\n', ...
    summary.force_at_least_300_count);
fprintf(file, 'force_at_least_300_q2_range_deg=[%.12g,%.12g]\n', ...
    summary.force_at_least_300_q2_range_deg);
fprintf(file, 'cond_at_least_100_count=%d\n', ...
    summary.cond_at_least_100_count);
fprintf(file, 'cond_at_least_100_q2_range_deg=[%.12g,%.12g]\n', ...
    summary.cond_at_least_100_q2_range_deg);
fprintf(file, 'reference_samples=%d\n', numel(reference.t));
fprintf(file, ['scope=quasistatic mechanical diagnostic only; no closed-loop ' ...
    'controllability, comfort, clinical safety, or architecture claim\n']);
end


function write_point(file, prefix, point)
fprintf(file, '%s_q1_deg=%.12g\n%s_q2_deg=%.12g\n', ...
    prefix, point.q_deg(1), prefix, point.q_deg(2));
fprintf(file, '%s_F_parallel_N=%.12g\n%s_F_perp_N=%.12g\n', ...
    prefix, point.F_parallel_N, prefix, point.F_perp_N);
fprintf(file, '%s_force_norm_N=%.12g\n%s_cond_A=%.12g\n', ...
    prefix, point.force_norm_N, prefix, point.condition_number);
fprintf(file, '%s_sigma_min_A=%.12g\n', prefix, point.sigma_min);
for index = 1:numel(point.feasible)
    fprintf(file, '%s_feasible_%dN=%d\n', prefix, ...
        point.component_bounds_N(index), ...
        point.feasible(index));
end
end
