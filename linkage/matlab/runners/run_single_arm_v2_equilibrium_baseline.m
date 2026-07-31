function run_single_arm_v2_equilibrium_baseline()
%RUN_SINGLE_ARM_V2_EQUILIBRIUM_BASELINE Headless preflight and two cases.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'single_arm_v2_equilibrium_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
old_gifs = dir(fullfile(output_dir, '*.gif'));
for index = 1:numel(old_gifs)
    delete(fullfile(old_gifs(index).folder, old_gifs(index).name));
end
diary_path = fullfile(output_dir, 'baseline_console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

fprintf('SINGLE ARM V2 EQUILIBRIUM MATLAB: %s\n', version);
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
p = human_two_link_v2_parameters(1.72, 75.0);
base = single_arm_v2_equilibrium_base_config();
preflight = single_arm_v2_reference_preflight(p, base);
ideal_config = single_arm_v2_case_config( ...
    base, preflight, "ideal_authority");
engineering_config = single_arm_v2_case_config( ...
    base, preflight, "engineering_bound");

save(fullfile(output_dir, 'preflight.mat'), 'preflight', 'p', 'base');
write_preflight_csv(fullfile(output_dir, 'preflight.csv'), preflight);
write_command_record(fullfile(output_dir, 'commands.txt'));
write_version_record(fullfile(output_dir, 'matlab_version.txt'));
write_config_record(fullfile(output_dir, 'config.txt'), p, base, ...
    ideal_config, engineering_config);
save(fullfile(output_dir, 'config.mat'), 'p', 'base', ...
    'ideal_config', 'engineering_config');

fprintf(['PREFLIGHT: max|Ft|=%.9gN max|Fn|=%.9gN max||F||=%.9gN ' ...
    'max||dF/dt||=%.9gN/s min_sigma=%.9g max_cond=%.9g ' ...
    '80N_feasible=%.6f residual_rms=%.9gNm\n'], ...
    preflight.metrics.max_abs_Ft_N, preflight.metrics.max_abs_Fn_N, ...
    preflight.metrics.max_force_norm_N, ...
    preflight.metrics.max_force_rate_norm_N_s, ...
    preflight.metrics.min_sigma, preflight.metrics.max_condition, ...
    preflight.metrics.engineering_feasible_fraction, ...
    preflight.metrics.engineering_residual_rms_Nm);
fprintf(['IDEAL AUTO BOUNDS: |u|<=[%.9g %.9g]N ' ...
    '|du/dt|<=[%.9g %.9g]N/s\n'], ideal_config.force_limit(1), ...
    ideal_config.force_limit(2), ideal_config.du_max(1), ...
    ideal_config.du_max(2));

ideal = simulate_single_arm_v2_equilibrium(ideal_config, p);
save(fullfile(output_dir, 'ideal_authority_workspace.mat'), ...
    'ideal', '-v7');
engineering = simulate_single_arm_v2_equilibrium(engineering_config, p);
save(fullfile(output_dir, 'engineering_bound_workspace.mat'), ...
    'engineering', '-v7');
oracle_config = human_two_link_v2_baseline_config();
oracle = simulate_human_two_link_v2_oracle(oracle_config, p);
save(fullfile(output_dir, 'oracle_comparison_metrics.mat'), ...
    'oracle_config', 'oracle');

records = [case_record(ideal); case_record(engineering)];
writetable(struct2table(records), fullfile(output_dir, 'case_metrics.csv'));
oracle_record = struct();
oracle_record.rmse_q1_deg = rad2deg(oracle.metrics.rmse_rad(1));
oracle_record.rmse_q2_deg = rad2deg(oracle.metrics.rmse_rad(2));
oracle_record.max_error_q1_deg = ...
    rad2deg(oracle.metrics.max_abs_error_rad(1));
oracle_record.max_error_q2_deg = ...
    rad2deg(oracle.metrics.max_abs_error_rad(2));
oracle_record.rom_violation_count = oracle.metrics.rom_violation_count;
oracle_record.soft_limit_activation_count = ...
    oracle.metrics.soft_limit_activation_count;
writetable(struct2table(oracle_record), ...
    fullfile(output_dir, 'oracle_comparison_metrics.csv'));

gif_path = fullfile(output_dir, ...
    'single_arm_v2_ideal_authority.gif');
create_equilibrium_gif(ideal, gif_path, output_dir);

visible_figures = findall(groot, 'Type', 'figure', 'Visible', 'on');
if ~isempty(visible_figures)
    error('SingleArmV2:VisibleFigure', ...
        'The headless runner created a visible figure.');
end
gif_files = dir(fullfile(output_dir, '*.gif'));
if numel(gif_files) ~= 1
    error('SingleArmV2:GifCount', ...
        'Expected exactly one GIF, found %d.', numel(gif_files));
end
if ~ideal.metrics.completed || ~engineering.metrics.completed
    error('SingleArmV2:IncompleteRollout', ...
        'Both 16 s rollouts must complete with finite recorded signals.');
end

ideal_success = evaluate_ideal_acceptance(ideal);
engineering_success = evaluate_engineering_acceptance(engineering);
if ~ideal_success
    classification = "ideal_not_accepted_do_not_enter_nmpc";
elseif ~engineering_success
    classification = ...
        "mathematical_authority_only_engineering_force_infeasible";
else
    classification = "eligible_for_fixed_model_nmpc";
end
write_classification(fullfile(output_dir, 'classification.txt'), ...
    classification, ideal_success, engineering_success);

print_case_summary(ideal);
print_case_summary(engineering);
fprintf('ORACLE: rmse_deg=[%.9g %.9g] ROM=%d soft=%d\n', ...
    oracle_record.rmse_q1_deg, oracle_record.rmse_q2_deg, ...
    oracle_record.rom_violation_count, ...
    oracle_record.soft_limit_activation_count);
fprintf('CLASSIFICATION: %s\n', classification);
fprintf('GIF: %s\n', gif_path);
end


function record = case_record(result)
m = result.metrics;
record = struct();
record.case_name = result.config.case_name;
record.completed = m.completed;
record.rmse_q1_deg = rad2deg(m.rmse_rad(1));
record.rmse_q2_deg = rad2deg(m.rmse_rad(2));
record.max_error_q1_deg = rad2deg(m.max_abs_error_rad(1));
record.max_error_q2_deg = rad2deg(m.max_abs_error_rad(2));
record.max_abs_Ft_N = m.max_force_component_N(1);
record.max_abs_Fn_N = m.max_force_component_N(2);
record.max_force_norm_N = m.max_force_norm_N;
record.max_force_rate_norm_N_s = m.max_force_rate_norm_N_s;
record.force_feasible_fraction = m.force_feasible_fraction;
record.full_constraint_feasible_fraction = ...
    m.full_constraint_feasible_fraction;
record.force_saturation_fraction = m.force_saturation_fraction;
record.slew_saturation_fraction = m.slew_saturation_fraction;
record.torque_residual_rms_Nm = m.torque_residual_rms_Nm;
record.torque_residual_max_Nm = m.torque_residual_max_Nm;
record.rom_violation_count = m.rom_violation_count;
record.soft_limit_activation_count = m.soft_limit_activation_count;
record.min_sigma = m.min_sigma;
record.max_condition = m.max_condition;
record.max_acceleration_q1_rad_s2 = m.max_abs_acceleration_rad_s2(1);
record.max_acceleration_q2_rad_s2 = m.max_abs_acceleration_rad_s2(2);
record.max_jerk_q1_rad_s3 = m.max_abs_jerk_rad_s3(1);
record.max_jerk_q2_rad_s3 = m.max_abs_jerk_rad_s3(2);
record.first_failure_time_s = m.first_failure_time_s;
record.first_failure_phase = m.first_failure_phase;
record.force_bound_limited_fraction = m.force_bound_limited_fraction;
record.slew_bound_limited_fraction = m.slew_bound_limited_fraction;
record.conditioning_limited_fraction = m.conditioning_limited_fraction;
record.numerical_limited_fraction = m.numerical_limited_fraction;
end


function print_case_summary(result)
m = result.metrics;
fprintf(['CASE %s: completed=%d rmse_deg=[%.9g %.9g] ' ...
    'max_error_deg=[%.9g %.9g] force_max=%.9gN rate_max=%.9gN/s ' ...
    'feasible=%.6f force_sat=%.6f slew_sat=%.6f ' ...
    'residual_rms=%.9gNm residual_max=%.9gNm ROM=%d soft=%d ' ...
    'min_sigma=%.9g max_cond=%.9g first=%.6gs/%s\n'], ...
    result.config.case_name, m.completed, rad2deg(m.rmse_rad(1)), ...
    rad2deg(m.rmse_rad(2)), rad2deg(m.max_abs_error_rad(1)), ...
    rad2deg(m.max_abs_error_rad(2)), m.max_force_norm_N, ...
    m.max_force_rate_norm_N_s, m.force_feasible_fraction, ...
    m.force_saturation_fraction, m.slew_saturation_fraction, ...
    m.torque_residual_rms_Nm, m.torque_residual_max_Nm, ...
    m.rom_violation_count, m.soft_limit_activation_count, ...
    m.min_sigma, m.max_condition, m.first_failure_time_s, ...
    m.first_failure_phase);
end


function success = evaluate_ideal_acceptance(result)
m = result.metrics;
success = m.completed && max(rad2deg(m.rmse_rad)) < 0.1 && ...
    m.rom_violation_count == 0 && ...
    m.soft_limit_activation_count == 0 && m.nonfinite_count == 0 && ...
    m.force_saturation_fraction == 0 && ...
    m.torque_residual_rms_Nm < 1e-8 && ...
    m.max_condition < result.config.conditioning_threshold;
end


function success = evaluate_engineering_acceptance(result)
m = result.metrics;
success = m.completed && max(rad2deg(m.rmse_rad)) < 0.1 && ...
    m.rom_violation_count == 0 && ...
    m.soft_limit_activation_count == 0 && m.nonfinite_count == 0 && ...
    m.force_saturation_fraction == 0;
end


function write_preflight_csv(path, preflight)
T = table(preflight.t', preflight.phase', ...
    preflight.q_ref(1, :)', preflight.q_ref(2, :)', ...
    preflight.tau_static(1, :)', preflight.tau_static(2, :)', ...
    preflight.tau_dynamic_increment(1, :)', ...
    preflight.tau_dynamic_increment(2, :)', ...
    preflight.u_static(1, :)', preflight.u_static(2, :)', ...
    preflight.u_ff(1, :)', preflight.u_ff(2, :)', ...
    preflight.force_norm', preflight.force_rate_norm', ...
    preflight.sigma_min', preflight.condition_number', ...
    preflight.det_A', preflight.engineering_bounded_residual_Nm', ...
    preflight.engineering_feasible', ...
    'VariableNames', {'time_s', 'phase', 'q1_rad', 'q2_rad', ...
    'tau_static_q1_Nm', 'tau_static_q2_Nm', ...
    'tau_dynamic_q1_Nm', 'tau_dynamic_q2_Nm', ...
    'u_static_Ft_N', 'u_static_Fn_N', 'u_ff_Ft_N', 'u_ff_Fn_N', ...
    'force_norm_N', 'force_rate_norm_N_s', 'sigma_min', ...
    'condition_number', 'det_A', 'bounded_residual_Nm', ...
    'engineering_feasible'});
writetable(T, path);
end


function write_command_record(path)
file = fopen(path, 'w');
assert(file >= 0, 'Could not create command record.');
cleanup = onCleanup(@() fclose(file));
fprintf(file, '%s\n', ['/Users/hankli/Desktop/MATLAB_R2025b.app/' ...
    'bin/matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_single_arm_v2_equilibrium_tests"']);
fprintf(file, '%s\n', ['/Users/hankli/Desktop/MATLAB_R2025b.app/' ...
    'bin/matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_single_arm_v2_equilibrium_baseline"']);
end


function write_version_record(path)
file = fopen(path, 'w');
assert(file >= 0, 'Could not create version record.');
cleanup = onCleanup(@() fclose(file));
fprintf(file, '%s\n', version);
end


function write_config_record(path, p, base, ideal, engineering)
file = fopen(path, 'w');
assert(file >= 0, 'Could not create config record.');
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'model=%s\n', p.model_name);
fprintf(file, 'height_m=%.17g\nbody_mass_kg=%.17g\n', ...
    p.height_m, p.body_mass_kg);
fprintf(file, 'contact_sc_m=%.17g\n', p.sc);
fprintf(file, 'dt_s=%.17g\nt_final_s=%.17g\n', base.dt, base.t_final);
fprintf(file, 'Kp=%s\nKd=%s\n', mat2str(base.Kp), mat2str(base.Kd));
fprintf(file, 'legacy_attempt_Kp=diag([36 49])\n');
fprintf(file, 'legacy_attempt_Kd=diag([12 14])\n');
fprintf(file, ['gain_revision_reason=legacy gains caused 0.0077 deg ' ...
    'return undershoot into the V2 soft-limit zone\n']);
fprintf(file, 'ideal_force_limit_N=%s\n', mat2str(ideal.force_limit'));
fprintf(file, 'engineering_force_limit_N=%s\n', ...
    mat2str(engineering.force_limit'));
fprintf(file, 'shared_du_max_N_s=%s\n', mat2str(ideal.du_max'));
fprintf(file, 'lambda_ref=%.17g\nlambda_du=%.17g\n', ...
    base.lambda_ref, base.lambda_du);
end


function write_classification(path, classification, ideal_success, ...
        engineering_success)
file = fopen(path, 'w');
assert(file >= 0, 'Could not create classification record.');
cleanup = onCleanup(@() fclose(file));
fprintf(file, 'classification=%s\n', classification);
fprintf(file, 'ideal_acceptance=%d\n', ideal_success);
fprintf(file, 'engineering_acceptance=%d\n', engineering_success);
end


function create_equilibrium_gif(result, gif_path, output_dir)
fig = figure('Visible', 'off', 'Color', 'w', ...
    'Position', [20, 20, 1420, 880]);
layout = tiledlayout(fig, 6, 2, ...
    'TileSpacing', 'compact', 'Padding', 'compact');
p = result.parameters;
t = result.t;

body_axis = nexttile(layout, 1, [6, 1]);
hold(body_axis, 'on'); axis(body_axis, 'equal'); grid(body_axis, 'on');
reach = p.L1+p.L2;
xlim(body_axis, [-0.35, reach+0.45]);
ylim(body_axis, [-0.35, reach+0.35]);
xlabel(body_axis, 'X (m)'); ylabel(body_axis, 'Y (m)');
body_line = plot(body_axis, nan, nan, 'o-', 'LineWidth', 5, ...
    'MarkerSize', 8, 'Color', [0.10, 0.35, 0.75]);
contact_marker = plot(body_axis, nan, nan, 's', 'MarkerSize', 10, ...
    'MarkerFaceColor', [0.85, 0.25, 0.15], 'MarkerEdgeColor', 'k');
force_arrow = quiver(body_axis, nan, nan, nan, nan, 0, ...
    'LineWidth', 2.2, 'Color', [0.80, 0.10, 0.10], ...
    'MaxHeadSize', 0.8);
text(body_axis, 0.02, 0.98, ...
    'Red arrow: actual world force (1 m = 800 N)', ...
    'Units', 'normalized', 'VerticalAlignment', 'top');

q_axis = nexttile(layout, 2); hold(q_axis, 'on'); grid(q_axis, 'on');
plot(q_axis, t, rad2deg(result.q_ref(1, :)), '--');
plot(q_axis, t, rad2deg(result.q_ref(2, :)), '--');
q1_line = plot(q_axis, nan, nan, '-'); q2_line = plot(q_axis, nan, nan, '-');
xlim(q_axis, [0, t(end)]); ylabel(q_axis, 'Angle (deg)');
title(q_axis, 'q reference and actual');
legend(q_axis, {'q1 ref','q2 ref','q1','q2'}, 'Location', 'eastoutside');

force_axis = nexttile(layout, 4); hold(force_axis, 'on'); grid(force_axis, 'on');
Ft_line = plot(force_axis, nan, nan, '-');
Fn_line = plot(force_axis, nan, nan, '-');
Fnorm_line = plot(force_axis, nan, nan, 'k-', 'LineWidth', 1.3);
xlim(force_axis, [0, t(end)]); ylabel(force_axis, 'Force (N)');
title(force_axis, 'Local cuff force');
legend(force_axis, {'Ft','Fn','||F||'}, 'Location', 'eastoutside');

torque_axis = nexttile(layout, 6); hold(torque_axis, 'on'); grid(torque_axis, 'on');
static_line = plot(torque_axis, nan, nan, '-');
dynamic_line = plot(torque_axis, nan, nan, '-');
feedback_line = plot(torque_axis, nan, nan, '-');
xlim(torque_axis, [0, t(end)]); ylabel(torque_axis, 'Torque norm (N m)');
title(torque_axis, 'Static, dynamic, feedback demand');
legend(torque_axis, {'static','dynamic','feedback'}, 'Location', 'eastoutside');

residual_axis = nexttile(layout, 8); hold(residual_axis, 'on'); grid(residual_axis, 'on');
residual_line = plot(residual_axis, nan, nan, 'LineWidth', 1.3);
xlim(residual_axis, [0, t(end)]); ylabel(residual_axis, 'Residual (N m)');
title(residual_axis, 'Generalized torque residual');

motion_axis = nexttile(layout, 10); hold(motion_axis, 'on'); grid(motion_axis, 'on');
accel_line = plot(motion_axis, nan, nan, '-');
jerk_line = plot(motion_axis, nan, nan, '-');
xlim(motion_axis, [0, t(end)]); ylabel(motion_axis, 'Norm');
title(motion_axis, 'Acceleration and jerk');
legend(motion_axis, {'||ddq||','||jerk||'}, 'Location', 'eastoutside');

diagnostic_axis = nexttile(layout, 12); hold(diagnostic_axis, 'on');
yyaxis(diagnostic_axis, 'left');
sigma_line = plot(diagnostic_axis, nan, nan, '-');
condition_line = plot(diagnostic_axis, nan, nan, '-');
ylabel(diagnostic_axis, 'sigma min / condition');
yyaxis(diagnostic_axis, 'right');
saturation_line = plot(diagnostic_axis, nan, nan, 'k:');
margin_line = plot(diagnostic_axis, nan, nan, '-');
ylabel(diagnostic_axis, 'Saturation flag / ROM margin (deg)');
grid(diagnostic_axis, 'on'); xlim(diagnostic_axis, [0, t(end)]);
xlabel(diagnostic_axis, 'Time (s)');
title(diagnostic_axis, 'Mapping, saturation, and ROM margin');
legend(diagnostic_axis, {'sigma min','cond(A)','saturation','ROM margin'}, ...
    'Location', 'eastoutside');

axes_list = [q_axis, force_axis, torque_axis, residual_axis, ...
    motion_axis, diagnostic_axis];
markers = gobjects(size(axes_list));
for index = 1:numel(axes_list)
    hold(axes_list(index), 'on');
    markers(index) = plot(axes_list(index), [0 0], ylim(axes_list(index)), ...
        'k:', 'HandleVisibility', 'off');
end

frame_indices = unique(round(linspace(1, numel(t), 65)));
frame_path = fullfile(output_dir, 'single_arm_v2_frame.png');
delay = result.config.t_final/numel(frame_indices);
for frame_number = 1:numel(frame_indices)
    index = frame_indices(frame_number);
    active = 1:index;
    geometry = human_two_link_v2_kinematics(result.state(1:2, index), p);
    points = [geometry.hip, geometry.knee, geometry.ankle];
    set(body_line, 'XData', points(1, :), 'YData', points(2, :));
    set(contact_marker, 'XData', geometry.contact(1), ...
        'YData', geometry.contact(2));
    force_scale = 800;
    set(force_arrow, 'XData', geometry.contact(1), ...
        'YData', geometry.contact(2), ...
        'UData', result.force_world(1, index)/force_scale, ...
        'VData', result.force_world(2, index)/force_scale);
    title(body_axis, sprintf('Single-arm V2 ideal authority: t=%.2f s', t(index)));
    set(q1_line, 'XData', t(active), ...
        'YData', rad2deg(result.state(1, active)));
    set(q2_line, 'XData', t(active), ...
        'YData', rad2deg(result.state(2, active)));
    set(Ft_line, 'XData', t(active), 'YData', result.force_local(1, active));
    set(Fn_line, 'XData', t(active), 'YData', result.force_local(2, active));
    set(Fnorm_line, 'XData', t(active), ...
        'YData', vecnorm(result.force_local(:, active), 2, 1));
    set(static_line, 'XData', t(active), ...
        'YData', vecnorm(result.tau_static(:, active), 2, 1));
    set(dynamic_line, 'XData', t(active), ...
        'YData', vecnorm(result.tau_dynamic(:, active), 2, 1));
    set(feedback_line, 'XData', t(active), ...
        'YData', vecnorm(result.tau_feedback(:, active), 2, 1));
    set(residual_line, 'XData', t(active), ...
        'YData', vecnorm(result.torque_residual(:, active), 2, 1));
    set(accel_line, 'XData', t(active), ...
        'YData', vecnorm(result.acceleration(:, active), 2, 1));
    set(jerk_line, 'XData', t(active), ...
        'YData', vecnorm(result.jerk(:, active), 2, 1));
    set(sigma_line, 'XData', t(active), 'YData', result.sigma_min(active));
    set(condition_line, 'XData', t(active), ...
        'YData', result.condition_number(active));
    set(saturation_line, 'XData', t(active), ...
        'YData', double(result.force_saturated(active) | ...
        result.slew_saturated(active)));
    set(margin_line, 'XData', t(active), ...
        'YData', rad2deg(min(result.rom_margin(:, active), [], 1)));
    for marker_index = 1:numel(markers)
        set(markers(marker_index), 'XData', [t(index), t(index)]);
    end
    exportgraphics(fig, frame_path, 'Resolution', 90);
    rgb = imread(frame_path);
    [indexed, color_map] = rgb2ind(rgb, 256);
    if frame_number == 1
        imwrite(indexed, color_map, gif_path, 'gif', ...
            'LoopCount', Inf, 'DelayTime', delay);
    else
        imwrite(indexed, color_map, gif_path, 'gif', ...
            'WriteMode', 'append', 'DelayTime', delay);
    end
end
close(fig);
if isfile(frame_path)
    delete(frame_path);
end
end
