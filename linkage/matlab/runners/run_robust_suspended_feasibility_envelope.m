function run_robust_suspended_feasibility_envelope()
%RUN_ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE Headless quasistatic envelope.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'bed_supported_load_transfer_v1', ...
    'robust_suspended_feasibility_envelope');
if ~isfolder(output_dir), mkdir(output_dir); end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path), delete(diary_path); end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

nominal = human_two_link_v2_parameters(1.72, 75);
config = bed_supported_v1_robust_envelope_config();
study = bed_supported_v1_robust_suspended_envelope(nominal, config);
envelope_samples = study.envelope_samples;
boundary_summary = study.boundary_summary;
boundary_details = study.boundary_details;
save(fullfile(output_dir, ...
    'robust_suspended_feasibility_envelope.mat'), 'study', ...
    'envelope_samples', 'boundary_summary', 'boundary_details', '-v7.3');
writetable(envelope_samples, fullfile(output_dir, 'envelope_samples.csv'));
writetable(boundary_summary, fullfile(output_dir, 'boundary_summary.csv'));
writetable(boundary_details, fullfile(output_dir, 'boundary_details.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), study);
save_robust_margin_along_path(study, fullfile(output_dir, ...
    'robust_margin_along_path.png'));
save_nominal_vs_robust_200(study, fullfile(output_dir, ...
    'nominal_vs_robust_margin_200N.png'));
save_liftoff_boundaries(study, fullfile(output_dir, ...
    'liftoff_boundary_vs_force_bound.png'));
save_bed_and_margin(study, fullfile(output_dir, ...
    'bed_support_and_robot_margin.png'));
save_transfer_window(study, fullfile(output_dir, ...
    'quasistatic_transfer_window.png'));
save_q_plane(study, fullfile(output_dir, ...
    'q1_q2_robust_liftoff_envelope.png'));

if ~isempty(findall(groot, 'Type', 'figure', 'Visible', 'on'))
    error('BedSupportedV1:VisibleEnvelopeFigure', ...
        'Envelope runner created a visible figure.');
end
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
end


function write_summary(path, study)
file = fopen(path, 'w');
assert(file >= 0);
cleanup = onCleanup(@() fclose(file));
c = study.config;
fprintf(file, 'Robust suspended feasibility / liftoff envelope\n');
fprintf(file, 'MATLAB %s\n', version);
fprintf(file, ['Scope: current Human V2 + current single-contact geometry + ' ...
    'registered deterministic engineering uncertainty set.\n']);
fprintf(file, ['Quasistatic qdot=qddot=0 only; not dynamic liftoff, recontact, ' ...
    'clinical safety, or a mattress validation.\n']);
fprintf(file, ['force bounds N=%s; tube caps deg=%s; diagnostic robust ' ...
    'thresholds N=%s\n'], mat2str(c.force_bounds_N), ...
    mat2str(c.tube_caps_deg), mat2str(c.robust_thresholds_N));
fprintf(file, ['coarse progress step=%.9g candidate step=%.9g deg; ' ...
    'refined progress step=%.9g candidate step=%.9g deg; ' ...
    'window=%.9g progress\n'], c.progress_step, c.candidate_step_deg, ...
    c.refined_progress_step, c.refined_candidate_step_deg, ...
    c.boundary_window_s);
fprintf(file, ['mechanical convergence tolerances: q2 <= %.9g deg, ' ...
    'entry margin <= %.9g N\n'], c.convergence_q2_tolerance_deg, ...
    c.convergence_margin_tolerance_N);
fprintf(file, ['bed h_hip=%.9g m; availability uses retained %.9g N ' ...
    'contact-force threshold\n'], study.calibration.h_hip_m, ...
    study.bed_config.contact_force_threshold_N);
fprintf(file, 'registered uncertainty cases=%d\n', ...
    numel(study.uncertainty.case_ids));

fprintf(file, '\nBoundary summary\n');
for row_index = 1:height(study.boundary_summary)
    row = study.boundary_summary(row_index, :);
    fprintf(file, ['B=%g N tube=%g deg nominal0=%s robust0=%s ' ...
        'robust5=%s robust10=%s robust20=%s bed_end=%s ' ...
        'overlap=[%s,%s] duration=%.9g segments=%d gap=%d class=%s\n'], ...
        row.force_bound_N, row.tube_cap_deg, ...
        value_or_not_reached(row.nominal_0N_entry_s), ...
        value_or_not_reached(row.robust_0N_entry_s), ...
        value_or_not_reached(row.robust_5N_entry_s), ...
        value_or_not_reached(row.robust_10N_entry_s), ...
        value_or_not_reached(row.robust_20N_entry_s), ...
        value_or_not_reached(row.bed_support_end_s), ...
        value_or_not_reached(row.overlap_start_s), ...
        value_or_not_reached(row.overlap_end_s), ...
        row.overlap_duration_s, row.overlap_segment_count, ...
        row.support_gap_flag, row.classification);
end

fprintf(file, '\nRefined boundary details\n');
for row_index = 1:height(study.boundary_details)
    row = study.boundary_details(row_index, :);
    if ~row.reached, continue; end
    fprintf(file, ['B=%g tube=%g type=%s threshold=%g s=%.9g ' ...
        'q_path=[%.9g %.9g] q_star=[%.9g %.9g] F=[%.9g %.9g] ' ...
        'norm2=%.9g normInf=%.9g margin=%.9g worst=%s ' ...
        'sigma_min=%.9g cond=%.9g residual=%.9g ' ...
        'soft_clearance=%.9g bed=%.9g contacts=%d ' ...
        'coarse_to_fine_dq2=%.9g dmargin=%.9g mechanically_converged=%d\n'], ...
        row.force_bound_N, row.tube_cap_deg, row.boundary_type, ...
        row.threshold_N, row.refined_entry_s, row.q_path1_deg, ...
        row.q_path2_deg, row.q_star1_deg, row.q_star2_deg, ...
        row.F_parallel_N, row.F_perp_N, row.force_norm_2_N, ...
        row.force_norm_inf_N, row.margin_N, row.worst_case_id, ...
        row.sigma_min, row.condition_number, ...
        row.torque_residual_norm_Nm, row.soft_limit_clearance_deg, ...
        row.bed_total_force_N, row.bed_active_count, ...
        row.convergence_q2_delta_deg, row.convergence_margin_delta_N, ...
        row.mechanical_convergence);
end

converged = study.boundary_details.reached & ...
    study.boundary_details.mechanical_convergence;
reached = study.boundary_details.reached;
fprintf(file, '\nmechanical boundary convergence=%d/%d reached entries\n', ...
    sum(converged), sum(reached));
fprintf(file, ['Return-path interpretation: the same envelope is traversed ' ...
    'in reverse geometrically; dynamic recontact remains untested.\n']);
end


function value = value_or_not_reached(x)
if isfinite(x), value = sprintf('%.9g', x); else, value = 'NOT_REACHED'; end
end


function save_robust_margin_along_path(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1100, 900]);
layout = tiledlayout(fig, numel(study.config.force_bounds_N), 1, ...
    'TileSpacing', 'compact');
colors = lines(numel(study.tubes));
for bound_index = 1:numel(study.config.force_bounds_N)
    bound_N = study.config.force_bounds_N(bound_index);
    ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    for tube_index = 1:numel(study.tubes)
        tube = study.tubes(tube_index);
        plot(ax, tube.s, bound_N-tube.robust_required_force_N, ...
            'LineWidth', 1.6, 'Color', colors(tube_index,:), ...
            'DisplayName', sprintf('%g deg tube', tube.cap_deg));
    end
    yline(ax, 0, 'k--', 'HandleVisibility', 'off');
    ylabel(ax, sprintf('%g N margin', bound_N));
    legend(ax, 'Location', 'best');
end
xlabel(layout, 'Outbound geometric path progress s');
title(layout, 'Registered-worst robot-only component-force margin');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_nominal_vs_robust_200(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1050, 780]);
layout = tiledlayout(fig, numel(study.tubes), 1, ...
    'TileSpacing', 'compact');
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    plot(ax, tube.s, 200-tube.nominal_required_force_N, ...
        'LineWidth', 1.5, 'DisplayName', 'nominal');
    plot(ax, tube.s, 200-tube.robust_required_force_N, ...
        'LineWidth', 1.5, 'DisplayName', 'registered worst');
    yline(ax, 0, 'k--', 'HandleVisibility', 'off');
    ylabel(ax, sprintf('%g deg (N)', tube.cap_deg));
    legend(ax, 'Location', 'best');
end
xlabel(layout, 'Outbound geometric path progress s');
title(layout, '200 N nominal versus registered-worst reserve');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_liftoff_boundaries(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 900, 620]);
ax = axes(fig); hold(ax, 'on'); grid(ax, 'on');
colors = lines(numel(study.tubes));
for tube_index = 1:numel(study.tubes)
    cap = study.tubes(tube_index).cap_deg;
    rows = study.boundary_summary(study.boundary_summary.tube_cap_deg == ...
        cap, :);
    plot(ax, rows.force_bound_N, rows.robust_0N_entry_s, '-o', ...
        'LineWidth', 1.7, 'Color', colors(tube_index,:), ...
        'DisplayName', sprintf('robust %g deg', cap));
    plot(ax, rows.force_bound_N, rows.nominal_0N_entry_s, '--s', ...
        'LineWidth', 1.2, 'Color', colors(tube_index,:), ...
        'HandleVisibility', 'off');
end
xlabel(ax, 'Component force bound (N)'); ylabel(ax, 'Earliest progress s');
title(ax, 'Liftoff entry: robust solid, nominal dashed');
legend(ax, 'Location', 'best'); ylim(ax, [0, 1]);
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_bed_and_margin(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1080, 850]);
layout = tiledlayout(fig, numel(study.tubes), 1, ...
    'TileSpacing', 'compact');
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    yyaxis(ax, 'left');
    plot(ax, tube.s, tube.path_bed_total_force_N, 'LineWidth', 1.4, ...
        'DisplayName', 'bed force on nominal path');
    ylabel(ax, 'Bed normal force (N)');
    yyaxis(ax, 'right');
    plot(ax, tube.s, 200-tube.robust_required_force_N, 'LineWidth', 1.5, ...
        'DisplayName', '200 N robust margin');
    yline(ax, 0, 'k--', 'HandleVisibility', 'off');
    ylabel(ax, 'Robot robust margin (N)');
    title(ax, sprintf('%g degree tube', tube.cap_deg));
end
xlabel(layout, 'Outbound geometric path progress s');
title(layout, 'Bed support and robot-only robust reserve');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_transfer_window(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 1100, 650]);
layout = tiledlayout(fig, numel(study.tubes), 1, ...
    'TileSpacing', 'compact');
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    ax = nexttile(layout); hold(ax, 'on');
    bed = double(tube.bed_available_any);
    robot = double(200-tube.robust_required_force_N > 0);
    overlap = double(200-tube.supported_robust_required_force_N > 0);
    imagesc(ax, tube.s, 1:3, [bed; overlap; robot]);
    yticks(ax, 1:3); yticklabels(ax, ...
        {'bed support available','same-posture overlap','robot robust feasible'});
    colormap(ax, [0.92 0.92 0.92; 0.12 0.55 0.30]);
    clim(ax, [0, 1]); title(ax, sprintf('200 N, %g degree tube', ...
        tube.cap_deg));
end
xlabel(layout, 'Outbound geometric path progress s');
title(layout, 'Quasistatic support / transfer / suspension regions');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end


function save_q_plane(study, path)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [30, 30, 900, 680]);
ax = axes(fig); hold(ax, 'on'); grid(ax, 'on');
plot(ax, rad2deg(study.path.q(1,:)), rad2deg(study.path.q(2,:)), ...
    'k-', 'LineWidth', 2, 'DisplayName', 'nominal path');
colors = lines(numel(study.tubes));
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    q1 = arrayfun(@(x) x.robust.q_deg(1), tube.samples);
    q2 = arrayfun(@(x) x.robust.q_deg(2), tube.samples);
    feasible = 200-tube.robust_required_force_N > 0;
    plot(ax, q1(feasible), q2(feasible), '.', ...
        'Color', colors(tube_index,:), 'MarkerSize', 11, ...
        'DisplayName', sprintf('%g deg robust best', tube.cap_deg));
end
xlabel(ax, 'q1 (deg)'); ylabel(ax, 'q2 (deg)');
title(ax, '200 N registered-robust selected postures');
legend(ax, 'Location', 'best');
exportgraphics(fig, path, 'Resolution', 180); close(fig);
end
