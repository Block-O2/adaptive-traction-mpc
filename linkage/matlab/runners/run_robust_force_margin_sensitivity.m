function run_robust_force_margin_sensitivity()
%RUN_ROBUST_FORCE_MARGIN_SENSITIVITY Headless quasistatic robustness study.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'bed_supported_load_transfer_v1', ...
    'robust_force_margin_sensitivity');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

nominal = human_two_link_v2_parameters(1.72, 75);
config = bed_supported_v1_force_margin_sensitivity_config();
study = bed_supported_v1_robust_force_margin_sensitivity(nominal, config);
sensitivity_cases = study.results_table;

save(fullfile(output_dir, 'robust_force_margin_sensitivity.mat'), ...
    'study', 'sensitivity_cases', '-v7.3');
writetable(sensitivity_cases, fullfile(output_dir, ...
    'sensitivity_cases.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), study);
save_one_at_a_time_margin(study, fullfile(output_dir, ...
    'one_at_a_time_margin.png'));
save_force_components(study, fullfile(output_dir, ...
    'force_components_sensitivity.png'));
save_combined_margin(study, fullfile(output_dir, ...
    'combined_uncertainty_margin.png'));
save_posture_comparison(study, fullfile(output_dir, ...
    'posture_comparison_5deg_vs_7deg.png'));

if ~isempty(findall(groot, 'Type', 'figure', 'Visible', 'on'))
    error('BedSupportedV1:VisibleSensitivityFigure', ...
        'Sensitivity runner created a visible figure.');
end
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
end


function write_summary(path, study)
file = fopen(path, 'w');
assert(file >= 0);
cleanup = onCleanup(@() fclose(file));
table_data = study.results_table;
config = study.config;
fprintf(file, 'Robust force-margin sensitivity\n');
fprintf(file, 'MATLAB %s\n', version);
fprintf(file, ['quasistatic robot-only hold; force bound=%.9g N; ' ...
    'guard=%.9g N\n'], config.force_bound_N, config.guard_N);
fprintf(file, ['Engineering sensitivity ranges only; not clinical ' ...
    'population bounds or a statistical distribution.\n']);

fprintf(file, '\nNominal\n');
for posture = config.posture_names
    row = table_data(table_data.layer == "one_at_a_time" & ...
        table_data.case_id == "nominal" & ...
        table_data.posture_name == posture, :);
    print_row(file, row);
end

fprintf(file, '\nWorst one-at-a-time\n');
for posture = config.posture_names
    rows = table_data(table_data.layer == "one_at_a_time" & ...
        table_data.case_id ~= "nominal" & ...
        table_data.posture_name == posture, :);
    [~, index] = min(rows.force_margin_N);
    print_row(file, rows(index, :));
end

fprintf(file, '\nLayer-1 selected adverse directions at current [7,20] deg\n');
for index = 1:numel(study.low_adverse_choices)
    low = study.low_adverse_choices(index);
    full = study.full_adverse_choices(index);
    fprintf(file, ['family=%s mild_direction=%s margin=%.9g N ' ...
        'full_direction=%s margin=%.9g N\n'], low.family, ...
        low.case_id, low.margin_at_primary_N, full.case_id, ...
        full.margin_at_primary_N);
end

fprintf(file, '\nCombined uncertainty\n');
for case_name = config.combined_case_names
    fprintf(file, 'case=%s sources=%s\n', case_name, ...
        study.combined_cases([study.combined_cases.case_id] == ...
        case_name).source_case_ids);
    for posture = config.posture_names
        row = table_data(table_data.layer == "combined" & ...
            table_data.case_id == case_name & ...
            table_data.posture_name == posture, :);
        print_row(file, row);
    end
end

fprintf(file, '\nGuard categories\n');
for posture = config.posture_names
    rows = table_data(table_data.case_id ~= "nominal" & ...
        table_data.posture_name == posture, :);
    fprintf(file, ['posture=%s ge10=%d ge5=%d positive_below5=%d ' ...
        'nonpositive=%d total=%d\n'], posture, ...
        sum(rows.margin_ge_10N), sum(rows.margin_ge_5N), ...
        sum(rows.margin_positive_below_5N), ...
        sum(rows.margin_nonpositive), height(rows));
    filtered = rows(rows.force_margin_N < config.guard_N, :);
    fprintf(file, '  filtered_by_5N_guard=%s\n', ...
        join_case_ids(filtered));
    positive = rows(rows.force_margin_N > 0, :);
    if isempty(positive)
        fprintf(file, '  smallest_positive_margin=none\n');
    else
        [smallest, index] = min(positive.force_margin_N);
        fprintf(file, '  smallest_positive_margin=%.9g N case=%s\n', ...
            smallest, positive.case_id(index));
    end
    first_5 = find(rows.force_margin_N < config.guard_N, 1);
    first_0 = find(rows.force_margin_N <= 0, 1);
    fprintf(file, '  first_below_5N=%s first_nonpositive=%s\n', ...
        row_case_or_none(rows, first_5), row_case_or_none(rows, first_0));
end

fprintf(file, '\nPosture comparison\n');
nominal_current = select_margin(table_data, "nominal", "current_7deg");
nominal_optimum = select_margin(table_data, "nominal", "max_margin_5deg");
fprintf(file, ['nominal [5,20]-[7,20] advantage=%.9g N; ' ...
    '[7,20] retains 2 deg soft-limit clearance while [5,20] is on the ' ...
    'activation boundary.\n'], nominal_optimum-nominal_current);
for case_name = config.combined_case_names
    current = select_margin(table_data, case_name, "current_7deg");
    optimum = select_margin(table_data, case_name, "max_margin_5deg");
    fprintf(file, 'case=%s [5,20]-[7,20] margin difference=%.9g N\n', ...
        case_name, optimum-current);
end

primary_oat = table_data(table_data.layer == "one_at_a_time" & ...
    table_data.case_id ~= "nominal" & ...
    table_data.posture_name == "current_7deg", :);
if any(primary_oat.force_margin_N <= 0)
    verdict = "clearly insufficient as a nominal-model uncertainty "+ ...
        "reserve under the registered engineering ranges";
elseif any(primary_oat.force_margin_N < config.guard_N)
    verdict = "roughly meaningful as an operational filter, but not a "+ ...
        "complete uncertainty reserve";
else
    verdict = "cannot yet be justified by the registered cases";
end
fprintf(file, '\n5 N guard engineering interpretation: %s.\n', verdict);
fprintf(file, ['This diagnostic does not establish that 200 N is clinically ' ...
    'safe or that 5 N is a clinical safety margin.\n']);
end


function print_row(file, row)
fprintf(file, ['posture=%s case=%s family=%s perturbation=%s ' ...
    'F=[%.9g %.9g] N norm2=%.9g N normInf=%.9g N margin=%.9g N ' ...
    'delta=%.9g N residual=%.9g Nm sigma_min=%.9g cond=%.9g ' ...
    'feasible=%d ge10=%d ge5=%d\n'], row.posture_name, row.case_id, ...
    row.family, row.perturbation, row.F_parallel_N, row.F_perp_N, ...
    row.force_norm_2_N, row.force_norm_inf_N, row.force_margin_N, ...
    row.delta_margin_N, row.torque_residual_norm_Nm, row.sigma_min, ...
    row.condition_number, row.feasible_200N, row.margin_ge_10N, ...
    row.margin_ge_5N);
end


function value = join_case_ids(rows)
if isempty(rows)
    value = "none";
else
    value = strjoin(rows.case_id, ",");
end
end


function value = row_case_or_none(rows, index)
if isempty(index)
    value = "none";
else
    value = rows.case_id(index);
end
end


function margin = select_margin(table_data, case_id, posture)
row = table_data(table_data.case_id == case_id & ...
    table_data.posture_name == posture, :);
margin = row.force_margin_N;
end


function save_one_at_a_time_margin(study, path)
table_data = study.results_table;
rows = table_data(table_data.layer == "one_at_a_time", :);
[case_ids, margins] = case_matrix(rows, study.config.posture_names, ...
    'force_margin_N');
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1250, 660]);
ax = axes(fig); hold(ax, 'on'); grid(ax, 'on');
curves = plot(ax, margins, '-o', 'LineWidth', 1.3, 'MarkerSize', 4);
yline(ax, study.config.guard_N, 'k--', '5 N guard', ...
    'HandleVisibility', 'off');
yline(ax, 0, 'r--', 'zero margin', 'HandleVisibility', 'off');
xticks(ax, 1:numel(case_ids)); xticklabels(ax, case_ids);
xtickangle(ax, 55);
ylabel(ax, '200 N component reserve (N)');
title(ax, 'One-at-a-time engineering force-margin sensitivity');
legend(ax, curves, study.config.posture_names, 'Location', 'southoutside', ...
    'Orientation', 'horizontal', 'Interpreter', 'none');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_force_components(study, path)
table_data = study.results_table;
rows = table_data(table_data.layer == "one_at_a_time", :);
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1250, 780]);
layout = tiledlayout(fig, 2, 1, 'TileSpacing', 'compact');
for posture_index = 1:numel(study.config.posture_names)
    posture = study.config.posture_names(posture_index);
    selected = rows(rows.posture_name == posture, :);
    ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    h_parallel = plot(ax, selected.F_parallel_N, '-o', 'LineWidth', 1.2, ...
        'MarkerSize', 3, 'DisplayName', 'F parallel');
    h_perp = plot(ax, selected.F_perp_N, '-s', 'LineWidth', 1.2, ...
        'MarkerSize', 3, 'DisplayName', 'F perp');
    yline(ax, -study.config.force_bound_N, 'r--', '-200 N', ...
        'HandleVisibility', 'off');
    yline(ax, study.config.force_bound_N, 'r--', '+200 N', ...
        'HandleVisibility', 'off');
    xticks(ax, 1:height(selected)); xticklabels(ax, selected.case_id);
    xtickangle(ax, 55); ylabel(ax, 'Force component (N)');
    title(ax, sprintf('%s at [%.0f,%.0f] deg', posture, ...
        selected.q1_deg(1), selected.q2_deg(1)), 'Interpreter', 'none');
    legend(ax, [h_parallel, h_perp], 'Location', 'best');
end
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_combined_margin(study, path)
rows = study.results_table(study.results_table.layer == "combined", :);
[case_ids, margins] = case_matrix(rows, study.config.posture_names, ...
    'force_margin_N');
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 850, 600]);
ax = axes(fig); bars = bar(ax, margins); grid(ax, 'on'); hold(ax, 'on');
yline(ax, study.config.guard_N, 'k--', '5 N guard', ...
    'HandleVisibility', 'off');
yline(ax, 0, 'r--', 'zero margin', 'HandleVisibility', 'off');
ylim(ax, [floor(min(margins, [], 'all')/5)*5-5, 12]);
xticks(ax, 1:numel(case_ids)); xticklabels(ax, case_ids);
ylabel(ax, '200 N component reserve (N)');
title(ax, 'Deterministic combined engineering stress cases');
legend(ax, bars, study.config.posture_names, 'Location', 'southoutside', ...
    'Orientation', 'horizontal', 'Interpreter', 'none');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_posture_comparison(study, path)
table_data = study.results_table;
case_ids = unique(table_data.case_id, 'stable');
difference = NaN(numel(case_ids), 1);
for index = 1:numel(case_ids)
    current = select_margin(table_data, case_ids(index), "current_7deg");
    optimum = select_margin(table_data, case_ids(index), "max_margin_5deg");
    difference(index) = optimum-current;
end
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1250, 650]);
ax = axes(fig); bar(ax, difference); grid(ax, 'on'); hold(ax, 'on');
yline(ax, 0, 'k--', 'HandleVisibility', 'off');
xticks(ax, 1:numel(case_ids)); xticklabels(ax, case_ids);
xtickangle(ax, 55);
ylabel(ax, 'margin([5,20]) - margin([7,20]) (N)');
title(ax, ['Force-reserve advantage of soft-limit-boundary posture; ' ...
    '[7,20] retains 2 deg clearance']);
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function [case_ids, values] = case_matrix(rows, posture_names, variable)
case_ids = unique(rows.case_id, 'stable');
values = NaN(numel(case_ids), numel(posture_names));
for case_index = 1:numel(case_ids)
    for posture_index = 1:numel(posture_names)
        match = rows.case_id == case_ids(case_index) & ...
            rows.posture_name == posture_names(posture_index);
        values(case_index, posture_index) = rows.(variable)(match);
    end
end
end
