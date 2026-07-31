function run_single_arm_trajectory_feasibility_study()
%RUN_SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY Open-loop trajectory preflight.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'single_arm_trajectory_feasibility_study');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

fprintf('SINGLE-ARM TRAJECTORY FEASIBILITY MATLAB: %s\n', version);
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
p = human_two_link_v2_parameters(1.72, 75.0);
base = single_arm_v2_equilibrium_base_config();
analysis_dt = 0.002;

trajectory_a = current_v2_trajectory(analysis_dt);
trajectory_b = translated_professor_trajectory(analysis_dt);
[candidate_definition, search_table] = search_force_aware_candidate(p, base);
trajectory_c = force_aware_trajectory(analysis_dt, candidate_definition);

analysis_a = analyze_trajectory(trajectory_a, p, base);
analysis_b = analyze_trajectory(trajectory_b, p, base);
analysis_c = analyze_trajectory(trajectory_c, p, base);
analyses = {analysis_a, analysis_b, analysis_c};

comparison = comparison_table(analyses);
writetable(comparison, fullfile(output_dir, 'comparison_metrics.csv'));
writetable(search_table, fullfile(output_dir, 'candidate_search.csv'));
timeseries = timeseries_table(analyses);
writetable(timeseries, fullfile(output_dir, 'trajectory_timeseries.csv'));
save(fullfile(output_dir, 'study_workspace.mat'), 'p', 'base', ...
    'trajectory_a', 'trajectory_b', 'trajectory_c', ...
    'analysis_a', 'analysis_b', 'analysis_c', ...
    'candidate_definition', 'search_table', 'comparison', '-v7');

write_audit(fullfile(output_dir, 'trajectory_source_audit.txt'));
write_summary(fullfile(output_dir, 'study_summary.txt'), analyses, ...
    candidate_definition);
write_command(fullfile(output_dir, 'command.txt'));
write_version(fullfile(output_dir, 'matlab_version.txt'));

plot_joint_paths(analyses, fullfile(output_dir, ...
    '01_joint_space_paths.png'));
plot_force_histories(analyses, fullfile(output_dir, ...
    '02_force_components_vs_time.png'));
plot_mapping_diagnostics(analyses, fullfile(output_dir, ...
    '03_mapping_conditioning.png'));
plot_static_dynamic_torque(analyses, fullfile(output_dir, ...
    '04_static_dynamic_torque.png'));
plot_peak_decomposition(analyses, fullfile(output_dir, ...
    '05_peak_force_torque_decomposition.png'));
plot_force_vs_knee(analyses, fullfile(output_dir, ...
    '06_peak_force_vs_q2.png'));

visible_figures = findall(groot, 'Type', 'figure', 'Visible', 'on');
assert(isempty(visible_figures), 'TrajectoryStudy:VisibleFigure', ...
    'The headless study created a visible figure.');
gif_files = dir(fullfile(output_dir, '*.gif'));
assert(isempty(gif_files), 'TrajectoryStudy:UnexpectedGif', ...
    'Open-loop preflight must not generate a GIF.');

disp(comparison);
fprintf(['SELECTED FORCE-AWARE: hip waypoint=%.3fdeg ' ...
    'knee waypoint=%.3fdeg first stage=%.3fs objective=%.9g\n'], ...
    candidate_definition.q_waypoint_deg(1), ...
    candidate_definition.q_waypoint_deg(2), ...
    candidate_definition.first_stage_duration_s, ...
    candidate_definition.objective);
fprintf('STUDY COMPLETE: closed_loop=0 gif=0 figures=6\n');
end


function trajectory = current_v2_trajectory(dt)
t = 0:dt:16.0;
n = numel(t);
q = zeros(2, n); dq = zeros(2, n); ddq = zeros(2, n);
jerk = zeros(2, n); phase = strings(1, n);
for index = 1:n
    [q(:, index), dq(:, index), ddq(:, index), phase(index), ~, ...
        jerk(:, index)] = human_two_link_v2_reference( ...
        t(index), "slow_passive_flexion_v2");
end
trajectory = make_trajectory("Current V2", ...
    "current_v2_joint_space_validation", t, q, dq, ddq, jerk, phase, ...
    deg2rad([45; 84]));
end


function trajectory = translated_professor_trajectory(dt)
% Diagnostic translation only: the source explicitly uses shank=q1-q2.
t = 0:dt:12.0;
frequency_hz = 0.2;
omega = 2*pi*frequency_hz;
phase_angle = omega*t;
hip_amplitude = deg2rad(65)/2;
knee_amplitude = deg2rad(70)/2;
q = [hip_amplitude*(1-cos(phase_angle)); ...
     knee_amplitude*(1-cos(phase_angle))];
dq = [hip_amplitude*omega*sin(phase_angle); ...
      knee_amplitude*omega*sin(phase_angle)];
ddq = [hip_amplitude*omega^2*cos(phase_angle); ...
       knee_amplitude*omega^2*cos(phase_angle)];
jerk = [-hip_amplitude*omega^3*sin(phase_angle); ...
        -knee_amplitude*omega^3*sin(phase_angle)];
phase = repmat("professor_periodic", 1, numel(t));
trajectory = make_trajectory("Professor translated", ...
    "translated_professor_trajectory_diagnostic", ...
    t, q, dq, ddq, jerk, phase, deg2rad([65; 70]));
end


function [selected, search_table] = search_force_aware_candidate(p, base)
search_dt = 0.01;
hip_waypoints_deg = [5, 8, 12];
knee_waypoints_deg = [35, 45, 55];
first_stage_durations = [2.8, 3.2, 3.6];
record_count = numel(hip_waypoints_deg)*numel(knee_waypoints_deg)* ...
    numel(first_stage_durations);
records(record_count, 1) = struct();
record_index = 0;
best_objective = Inf;
selected = struct();

for hip_deg = hip_waypoints_deg
    for knee_deg = knee_waypoints_deg
        for first_duration = first_stage_durations
            definition = struct();
            definition.q_start_deg = [5; 10];
            definition.q_waypoint_deg = [hip_deg; knee_deg];
            definition.q_peak_deg = [45; 84];
            definition.first_stage_duration_s = first_duration;
            definition.second_stage_duration_s = 7.5-first_duration;
            definition.peak_hold_duration_s = 1.0;
            trajectory = force_aware_trajectory(search_dt, definition);
            analysis = analyze_trajectory(trajectory, p, base);
            m = analysis.metrics;
            target_error_deg = norm(rad2deg( ...
                max(trajectory.q, [], 2)-trajectory.target_peak));
            conditioning_penalty = mean(1./max(analysis.sigma_min, 1e-4));
            objective = ...
                m.peak_abs_F_parallel_N/320 + ...
                m.peak_force_norm_N/320 + ...
                0.75*m.force_rms_N/320 + ...
                0.05*conditioning_penalty/30 + ...
                0.10*m.max_abs_dq_rad_s/0.40 + ...
                0.05*m.max_abs_ddq_rad_s2/1.5 + ...
                0.02*m.max_abs_jerk_rad_s3/1.5 + ...
                100*target_error_deg;
            feasible = m.rom_violation_count == 0 && ...
                m.max_abs_dq_rad_s <= 0.40+1e-12 && ...
                m.max_abs_ddq_rad_s2 <= 1.5+1e-12 && ...
                target_error_deg <= 1e-10;
            record_index = record_index+1;
            records(record_index).hip_waypoint_deg = hip_deg;
            records(record_index).knee_waypoint_deg = knee_deg;
            records(record_index).first_stage_duration_s = first_duration;
            records(record_index).second_stage_duration_s = ...
                definition.second_stage_duration_s;
            records(record_index).objective = objective;
            records(record_index).feasible = feasible;
            records(record_index).peak_abs_F_parallel_N = ...
                m.peak_abs_F_parallel_N;
            records(record_index).peak_force_norm_N = m.peak_force_norm_N;
            records(record_index).force_rms_N = m.force_rms_N;
            records(record_index).min_sigma_min_A = m.min_sigma_min_A;
            records(record_index).max_abs_dq_rad_s = m.max_abs_dq_rad_s;
            records(record_index).max_abs_ddq_rad_s2 = ...
                m.max_abs_ddq_rad_s2;
            records(record_index).max_abs_jerk_rad_s3 = ...
                m.max_abs_jerk_rad_s3;
            records(record_index).target_error_deg = target_error_deg;
            if feasible && objective < best_objective
                best_objective = objective;
                selected = definition;
                selected.objective = objective;
            end
        end
    end
end
assert(isfinite(best_objective), 'TrajectoryStudy:NoFeasibleCandidate', ...
    'The fixed candidate grid contains no feasible slow trajectory.');
search_table = struct2table(records);
end


function trajectory = force_aware_trajectory(dt, definition)
t = 0:dt:16.0;
n = numel(t);
q = zeros(2, n); dq = zeros(2, n); ddq = zeros(2, n);
jerk = zeros(2, n); phase = strings(1, n);
q_start = deg2rad(definition.q_start_deg(:));
q_waypoint = deg2rad(definition.q_waypoint_deg(:));
q_peak = deg2rad(definition.q_peak_deg(:));
d1 = definition.first_stage_duration_s;
d2 = definition.second_stage_duration_s;
t_peak = d1+d2;
t_return_start = t_peak+definition.peak_hold_duration_s;
t_waypoint_return = t_return_start+d2;

for index = 1:n
    time = t(index);
    if time < d1
        [q(:, index), dq(:, index), ddq(:, index), jerk(:, index)] = ...
            quintic_segment(time, 0, d1, q_start, q_waypoint);
        phase(index) = "knee_flexion_first";
    elseif time < t_peak
        [q(:, index), dq(:, index), ddq(:, index), jerk(:, index)] = ...
            quintic_segment(time, d1, t_peak, q_waypoint, q_peak);
        phase(index) = "coordinated_to_peak";
    elseif time < t_return_start
        q(:, index) = q_peak;
        phase(index) = "peak_hold";
    elseif time < t_waypoint_return
        [q(:, index), dq(:, index), ddq(:, index), jerk(:, index)] = ...
            quintic_segment(time, t_return_start, ...
            t_waypoint_return, q_peak, q_waypoint);
        phase(index) = "coordinated_return";
    else
        [q(:, index), dq(:, index), ddq(:, index), jerk(:, index)] = ...
            quintic_segment(time, t_waypoint_return, 16.0, ...
            q_waypoint, q_start);
        phase(index) = "knee_extension_last";
    end
end
trajectory = make_trajectory("Force-aware candidate", ...
    "fixed_grid_force_aware_waypoint_diagnostic", ...
    t, q, dq, ddq, jerk, phase, q_peak);
trajectory.definition = definition;
end


function [q, dq, ddq, jerk] = quintic_segment(t, t0, tf, q0, qf)
duration = tf-t0;
r = min(max((t-t0)/duration, 0), 1);
s = 10*r^3-15*r^4+6*r^5;
ds = (30*r^2-60*r^3+30*r^4)/duration;
dds = (60*r-180*r^2+120*r^3)/duration^2;
ddds = (60-360*r+360*r^2)/duration^3;
delta = qf-q0;
q = q0+delta*s;
dq = delta*ds;
ddq = delta*dds;
jerk = delta*ddds;
end


function trajectory = make_trajectory(name, source, t, q, dq, ddq, ...
        jerk, phase, target_peak)
trajectory = struct();
trajectory.name = string(name);
trajectory.source = string(source);
trajectory.t = t;
trajectory.q = q;
trajectory.dq = dq;
trajectory.ddq = ddq;
trajectory.jerk = jerk;
trajectory.phase = phase;
trajectory.target_peak = target_peak;
end


function analysis = analyze_trajectory(trajectory, p, base)
n = numel(trajectory.t);
tau_required = zeros(2, n); tau_static = zeros(2, n);
tau_dynamic = zeros(2, n); tau_gravity = zeros(2, n);
tau_passive = zeros(2, n); tau_inertial_coriolis = zeros(2, n);
force_local = zeros(2, n); force_static = zeros(2, n);
force_dynamic = zeros(2, n); force_world = zeros(2, n);
contact_parallel_torque = zeros(2, n);
contact_perpendicular_torque = zeros(2, n);
sigma_min = zeros(1, n); condition_number = zeros(1, n);
det_A = zeros(1, n); solve_residual = zeros(1, n);
solve_rank = zeros(1, n); rom_violation = false(1, n);

for index = 1:n
    q = trajectory.q(:, index);
    dq = trajectory.dq(:, index);
    ddq = trajectory.ddq(:, index);
    [M, h, ~, G] = human_two_link_v2_dynamics_terms(q, dq, p);
    passive = human_two_link_v2_passive_torque(q, dq, p);
    passive_at_zero_velocity = ...
        human_two_link_v2_passive_torque(q, zeros(2, 1), p);
    inertial_coriolis = M*ddq+h;
    required = inertial_coriolis+G+passive;
    static = G+passive_at_zero_velocity;
    dynamic = required-static;
    mapping = single_arm_v2_force_map(q, dq, p);
    [u, solve_details] = single_arm_v2_stable_force_solve( ...
        mapping.A, required, base.svd_relative_tolerance);
    u_static = single_arm_v2_stable_force_solve( ...
        mapping.A, static, base.svd_relative_tolerance);
    u_dynamic = single_arm_v2_stable_force_solve( ...
        mapping.A, dynamic, base.svd_relative_tolerance);

    tau_required(:, index) = required;
    tau_static(:, index) = static;
    tau_dynamic(:, index) = dynamic;
    tau_gravity(:, index) = G;
    tau_passive(:, index) = passive;
    tau_inertial_coriolis(:, index) = inertial_coriolis;
    force_local(:, index) = u;
    force_static(:, index) = u_static;
    force_dynamic(:, index) = u_dynamic;
    force_world(:, index) = mapping.rotation*u;
    contact_parallel_torque(:, index) = mapping.A(:, 1)*u(1);
    contact_perpendicular_torque(:, index) = mapping.A(:, 2)*u(2);
    sigma_min(index) = mapping.sigma_min;
    condition_number(index) = mapping.condition_number;
    det_A(index) = mapping.det_A;
    solve_residual(index) = solve_details.residual_norm;
    solve_rank(index) = solve_details.rank;
    rom_violation(index) = any(q < p.q_min-1e-12 | q > p.q_max+1e-12);
end

force_norm = vecnorm(force_local, 2, 1);
[peak_force, peak_index] = max(force_norm);
target_error = norm(max(trajectory.q, [], 2)-trajectory.target_peak);
metrics = struct();
metrics.peak_force_norm_N = peak_force;
metrics.peak_abs_F_parallel_N = max(abs(force_local(1, :)));
metrics.peak_abs_F_perp_N = max(abs(force_local(2, :)));
metrics.force_rms_N = sqrt(mean(force_norm.^2));
metrics.peak_abs_world_vertical_N = max(abs(force_world(2, :)));
metrics.peak_abs_world_horizontal_N = max(abs(force_world(1, :)));
metrics.min_sigma_min_A = min(sigma_min);
metrics.max_cond_A = max(condition_number);
metrics.peak_abs_hip_torque_Nm = max(abs(tau_required(1, :)));
metrics.peak_abs_knee_torque_Nm = max(abs(tau_required(2, :)));
metrics.peak_static_torque_norm_Nm = max(vecnorm(tau_static, 2, 1));
metrics.peak_dynamic_torque_norm_Nm = max(vecnorm(tau_dynamic, 2, 1));
metrics.max_abs_dq_rad_s = max(abs(trajectory.dq), [], 'all');
metrics.max_abs_ddq_rad_s2 = max(abs(trajectory.ddq), [], 'all');
metrics.max_abs_jerk_rad_s3 = max(abs(trajectory.jerk), [], 'all');
metrics.rom_reached = target_error <= 1e-10;
metrics.rom_violation_count = sum(rom_violation);
metrics.exact_rank_deficient_samples = sum(solve_rank < 2);
metrics.near_singular_samples = sum(sigma_min < 1e-4);
metrics.max_solve_residual_Nm = max(solve_residual);
metrics.peak_time_s = trajectory.t(peak_index);
metrics.peak_phase = trajectory.phase(peak_index);
metrics.peak_q1_deg = rad2deg(trajectory.q(1, peak_index));
metrics.peak_q2_deg = rad2deg(trajectory.q(2, peak_index));
metrics.peak_F_parallel_N = force_local(1, peak_index);
metrics.peak_F_perp_N = force_local(2, peak_index);
metrics.peak_static_F_parallel_N = force_static(1, peak_index);
metrics.peak_dynamic_F_parallel_N = force_dynamic(1, peak_index);
metrics.peak_static_force_norm_N = norm(force_static(:, peak_index));
metrics.peak_dynamic_force_norm_N = norm(force_dynamic(:, peak_index));

analysis = struct();
analysis.trajectory = trajectory;
analysis.metrics = metrics;
analysis.tau_required = tau_required;
analysis.tau_static = tau_static;
analysis.tau_dynamic = tau_dynamic;
analysis.tau_gravity = tau_gravity;
analysis.tau_passive = tau_passive;
analysis.tau_inertial_coriolis = tau_inertial_coriolis;
analysis.force_local = force_local;
analysis.force_static = force_static;
analysis.force_dynamic = force_dynamic;
analysis.force_world = force_world;
analysis.force_norm = force_norm;
analysis.contact_parallel_torque = contact_parallel_torque;
analysis.contact_perpendicular_torque = contact_perpendicular_torque;
analysis.sigma_min = sigma_min;
analysis.condition_number = condition_number;
analysis.det_A = det_A;
analysis.solve_residual = solve_residual;
analysis.solve_rank = solve_rank;
analysis.peak_index = peak_index;
end


function table_out = comparison_table(analyses)
rows(numel(analyses), 1) = struct();
for index = 1:numel(analyses)
    a = analyses{index};
    m = a.metrics;
    rows(index).trajectory = a.trajectory.name;
    rows(index).peak_force_norm_N = m.peak_force_norm_N;
    rows(index).peak_abs_F_parallel_N = m.peak_abs_F_parallel_N;
    rows(index).peak_abs_F_perp_N = m.peak_abs_F_perp_N;
    rows(index).force_rms_N = m.force_rms_N;
    rows(index).peak_abs_world_vertical_N = ...
        m.peak_abs_world_vertical_N;
    rows(index).peak_abs_world_horizontal_N = ...
        m.peak_abs_world_horizontal_N;
    rows(index).min_sigma_min_A = m.min_sigma_min_A;
    rows(index).max_cond_A = m.max_cond_A;
    rows(index).peak_abs_hip_torque_Nm = m.peak_abs_hip_torque_Nm;
    rows(index).peak_abs_knee_torque_Nm = m.peak_abs_knee_torque_Nm;
    rows(index).peak_static_torque_norm_Nm = ...
        m.peak_static_torque_norm_Nm;
    rows(index).peak_dynamic_torque_norm_Nm = ...
        m.peak_dynamic_torque_norm_Nm;
    rows(index).max_abs_dq_rad_s = m.max_abs_dq_rad_s;
    rows(index).max_abs_ddq_rad_s2 = m.max_abs_ddq_rad_s2;
    rows(index).max_abs_jerk_rad_s3 = m.max_abs_jerk_rad_s3;
    rows(index).rom_reached = m.rom_reached;
    rows(index).rom_violation_count = m.rom_violation_count;
    rows(index).rank_deficient_samples = m.exact_rank_deficient_samples;
    rows(index).near_singular_samples = m.near_singular_samples;
    rows(index).max_solve_residual_Nm = m.max_solve_residual_Nm;
    rows(index).peak_time_s = m.peak_time_s;
    rows(index).peak_q2_deg = m.peak_q2_deg;
end
table_out = struct2table(rows);
end


function table_out = timeseries_table(analyses)
tables = cell(size(analyses));
for index = 1:numel(analyses)
    a = analyses{index};
    n = numel(a.trajectory.t);
    tables{index} = table(repmat(a.trajectory.name, n, 1), ...
        a.trajectory.t', a.trajectory.phase', ...
        a.trajectory.q(1, :)', a.trajectory.q(2, :)', ...
        a.trajectory.dq(1, :)', a.trajectory.dq(2, :)', ...
        a.trajectory.ddq(1, :)', a.trajectory.ddq(2, :)', ...
        a.tau_required(1, :)', a.tau_required(2, :)', ...
        a.tau_static(1, :)', a.tau_static(2, :)', ...
        a.tau_dynamic(1, :)', a.tau_dynamic(2, :)', ...
        a.force_local(1, :)', a.force_local(2, :)', ...
        a.force_norm', a.force_world(1, :)', a.force_world(2, :)', ...
        a.sigma_min', a.condition_number', a.det_A', ...
        'VariableNames', {'trajectory', 'time_s', 'phase', ...
        'q1_rad', 'q2_rad', 'dq1_rad_s', 'dq2_rad_s', ...
        'ddq1_rad_s2', 'ddq2_rad_s2', 'tau_required_hip_Nm', ...
        'tau_required_knee_Nm', 'tau_static_hip_Nm', ...
        'tau_static_knee_Nm', 'tau_dynamic_hip_Nm', ...
        'tau_dynamic_knee_Nm', 'F_parallel_N', 'F_perp_N', ...
        'force_norm_N', 'world_Fx_N', 'world_Fy_N', ...
        'sigma_min_A', 'cond_A', 'det_A'});
end
table_out = vertcat(tables{:});
end


function plot_joint_paths(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 900, 650]);
axis_handle = axes(fig); hold(axis_handle, 'on'); grid(axis_handle, 'on');
for index = 1:numel(analyses)
    a = analyses{index};
    plot(axis_handle, rad2deg(a.trajectory.q(1, :)), ...
        rad2deg(a.trajectory.q(2, :)), 'LineWidth', 2);
end
xlabel(axis_handle, 'q1 hip angle (deg)');
ylabel(axis_handle, 'q2 knee flexion (deg)');
title(axis_handle, 'Joint-space path comparison');
legend(axis_handle, trajectory_names(analyses), 'Location', 'best');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function plot_force_histories(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 1100, 850]);
layout = tiledlayout(fig, 3, 1, 'TileSpacing', 'compact');
for index = 1:numel(analyses)
    a = analyses{index}; ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    semilogy(ax, a.trajectory.t, max(abs(a.force_local(1, :)), 1e-3), ...
        'LineWidth', 1.3);
    semilogy(ax, a.trajectory.t, max(abs(a.force_local(2, :)), 1e-3), ...
        'LineWidth', 1.3);
    semilogy(ax, a.trajectory.t, max(a.force_norm, 1e-3), ...
        'k-', 'LineWidth', 1.5);
    set(ax, 'YScale', 'log');
    ylabel(ax, 'Force magnitude (N)'); title(ax, a.trajectory.name);
    legend(ax, {'|F parallel|','|F perp|','|F|'}, 'Location', 'eastoutside');
end
xlabel(nexttile_reference(layout, 3), 'Time (s)');
title(layout, 'Single-contact force histories (log magnitude)');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function plot_mapping_diagnostics(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 1100, 850]);
layout = tiledlayout(fig, 3, 1, 'TileSpacing', 'compact');
for index = 1:numel(analyses)
    a = analyses{index}; ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    yyaxis(ax, 'left');
    semilogy(ax, a.trajectory.t, max(a.sigma_min, 1e-12), 'LineWidth', 1.4);
    set(ax, 'YScale', 'log');
    ylabel(ax, 'sigma min(A)');
    yyaxis(ax, 'right');
    semilogy(ax, a.trajectory.t, min(a.condition_number, 1e12), ...
        'LineWidth', 1.4);
    set(ax, 'YScale', 'log');
    ylabel(ax, 'cond(A), capped at 1e12'); title(ax, a.trajectory.name);
end
xlabel(nexttile_reference(layout, 3), 'Time (s)');
title(layout, 'Contact-map conditioning');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function plot_static_dynamic_torque(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 1100, 850]);
layout = tiledlayout(fig, 3, 1, 'TileSpacing', 'compact');
for index = 1:numel(analyses)
    a = analyses{index}; ax = nexttile(layout); hold(ax, 'on'); grid(ax, 'on');
    plot(ax, a.trajectory.t, vecnorm(a.tau_static, 2, 1), 'LineWidth', 1.4);
    plot(ax, a.trajectory.t, vecnorm(a.tau_dynamic, 2, 1), 'LineWidth', 1.4);
    ylabel(ax, 'Torque norm (N m)'); title(ax, a.trajectory.name);
    legend(ax, {'static','dynamic'}, 'Location', 'eastoutside');
end
xlabel(nexttile_reference(layout, 3), 'Time (s)');
title(layout, 'Static versus dynamic generalized-torque demand');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function plot_peak_decomposition(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 1200, 900]);
layout = tiledlayout(fig, 3, 2, 'TileSpacing', 'compact');
for index = 1:numel(analyses)
    a = analyses{index}; peak = a.peak_index;
    ax_demand = nexttile(layout); grid(ax_demand, 'on');
    demand = [a.tau_gravity(:, peak), a.tau_passive(:, peak), ...
        a.tau_inertial_coriolis(:, peak)];
    bar(ax_demand, demand);
    xticklabels(ax_demand, {'hip','knee'}); ylabel(ax_demand, 'N m');
    title(ax_demand, sprintf('%s: required torque', a.trajectory.name));
    legend(ax_demand, {'gravity','passive','inertial+Coriolis'}, ...
        'Location', 'best');

    ax_contact = nexttile(layout); grid(ax_contact, 'on');
    contact = [a.contact_parallel_torque(:, peak), ...
        a.contact_perpendicular_torque(:, peak)];
    bar(ax_contact, contact);
    xticklabels(ax_contact, {'hip','knee'}); ylabel(ax_contact, 'N m');
    title(ax_contact, sprintf('contact map at peak |F|, t=%.4g s', ...
        a.metrics.peak_time_s));
    legend(ax_contact, {'F parallel contribution','F perp contribution'}, ...
        'Location', 'best');
end
title(layout, 'Peak-force generalized-torque decomposition');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function plot_force_vs_knee(analyses, path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 900, 650]);
ax = axes(fig); hold(ax, 'on'); grid(ax, 'on');
for index = 1:numel(analyses)
    a = analyses{index};
    semilogy(ax, rad2deg(a.trajectory.q(2, :)), ...
        max(a.force_norm, 1e-3), '.', 'MarkerSize', 5);
    plot(ax, a.metrics.peak_q2_deg, a.metrics.peak_force_norm_N, ...
        'o', 'MarkerSize', 8, 'LineWidth', 1.5, 'HandleVisibility', 'off');
end
set(ax, 'YScale', 'log');
xlabel(ax, 'q2 knee flexion (deg)'); ylabel(ax, '|F| (N, log scale)');
title(ax, 'Force magnitude versus knee flexion');
legend(ax, trajectory_names(analyses), 'Location', 'best');
exportgraphics(fig, path, 'Resolution', 160); close(fig);
end


function names = trajectory_names(analyses)
names = strings(1, numel(analyses));
for index = 1:numel(analyses)
    names(index) = analyses{index}.trajectory.name;
end
end


function ax = nexttile_reference(layout, tile_number)
ax = nexttile(layout, tile_number);
end


function write_audit(path)
file = fopen(path, 'w'); assert(file >= 0); cleanup = onCleanup(@() fclose(file));
fprintf(file, 'CURRENT V2 TRAJECTORY\n');
fprintf(file, 'q_start_deg=[5 10]\nq_peak_deg=[45 84]\n');
fprintf(file, ['shared_progress=yes; fixed joint-space ratio; ' ...
    'minimum-jerk/quintic\n']);
fprintf(file, ['purpose=Human Model V2 plant/oracle validation; ' ...
    'not contact-force or conditioning aware\n\n']);
fprintf(file, 'PROFESSOR SOURCE (READ ONLY)\n');
fprintf(file, ['sha256=b8c95ab1df3507efd610a3a72057e31a33724626d37341' ...
    'bd5d5a4abaa833c19f\n']);
fprintf(file, 'q1=32.5deg*(1-cos(2*pi*0.2*t))\n');
fprintf(file, 'q2=35deg*(1-cos(2*pi*0.2*t))\n');
fprintf(file, 'start_deg=[0 0]; maxima_deg=[65 70]; period_s=5; frequency_Hz=0.2\n');
fprintf(file, ['t_total_s=12; endpoint_at_12s_is_not_a_cycle_boundary; ' ...
    'endpoint_deg_approx=[58.79 63.31]\n']);
fprintf(file, ['coordinate_translation=unambiguous for reference: source ' ...
    'uses hip absolute q1, positive knee flexion q2, shank=q1-q2\n']);
fprintf(file, ['original_actuation=direct computed joint torque plus two ' ...
    'normal contact forces at 0.55*thigh and 0.50*shank, plus safety torque\n']);
fprintf(file, ['gravity=the coded gravity term is included in tau_ctrl and ' ...
    'subtracted in forward dynamics, producing coded cancellation\n']);
fprintf(file, ['translation_label=translated professor trajectory diagnostic; ' ...
    'not professor experiment reproduction\n']);
end


function write_summary(path, analyses, selected)
file = fopen(path, 'w'); assert(file >= 0); cleanup = onCleanup(@() fclose(file));
fprintf(file, 'study_type=open-loop inverse-dynamics/contact-force preflight\n');
fprintf(file, 'closed_loop_tracking=0\ngif_generated=0\n');
fprintf(file, 'force_names=F_parallel along shank axis; F_perp normal to shank axis\n');
for index = 1:numel(analyses)
    a = analyses{index}; m = a.metrics;
    fprintf(file, '\n[%s]\n', a.trajectory.name);
    fprintf(file, 'source=%s\n', a.trajectory.source);
    fprintf(file, 'peak_force_norm_N=%.12g\n', m.peak_force_norm_N);
    fprintf(file, 'peak_abs_F_parallel_N=%.12g\n', m.peak_abs_F_parallel_N);
    fprintf(file, 'force_rms_N=%.12g\n', m.force_rms_N);
    fprintf(file, 'peak_time_s=%.12g\npeak_q2_deg=%.12g\n', ...
        m.peak_time_s, m.peak_q2_deg);
    fprintf(file, 'min_sigma_min_A=%.12g\nmax_cond_A=%.12g\n', ...
        m.min_sigma_min_A, m.max_cond_A);
    fprintf(file, 'rank_deficient_samples=%d\nnear_singular_samples=%d\n', ...
        m.exact_rank_deficient_samples, m.near_singular_samples);
    fprintf(file, 'peak_static_F_parallel_N=%.12g\n', ...
        m.peak_static_F_parallel_N);
    fprintf(file, 'peak_dynamic_F_parallel_N=%.12g\n', ...
        m.peak_dynamic_F_parallel_N);
end
fprintf(file, '\n[force_aware_definition]\n');
fprintf(file, 'q_start_deg=%s\n', mat2str(selected.q_start_deg'));
fprintf(file, 'q_waypoint_deg=%s\n', mat2str(selected.q_waypoint_deg'));
fprintf(file, 'q_peak_deg=%s\n', mat2str(selected.q_peak_deg'));
fprintf(file, 'first_stage_duration_s=%.12g\n', ...
    selected.first_stage_duration_s);
fprintf(file, 'second_stage_duration_s=%.12g\n', ...
    selected.second_stage_duration_s);
fprintf(file, 'objective=%.12g\n', selected.objective);
end


function write_command(path)
file = fopen(path, 'w'); assert(file >= 0); cleanup = onCleanup(@() fclose(file));
fprintf(file, ['/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch ' ...
    '"addpath(genpath(''linkage/matlab'')); ' ...
    'run_single_arm_trajectory_feasibility_study"\n']);
end


function write_version(path)
file = fopen(path, 'w'); assert(file >= 0); cleanup = onCleanup(@() fclose(file));
fprintf(file, '%s\n', version);
end
