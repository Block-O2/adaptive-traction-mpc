function run_human_two_link_baseline()
%RUN_HUMAN_TWO_LINK_BASELINE Headless deterministic validation matrix.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'human_two_link_baseline');
runs_dir = fullfile(output_dir, 'runs');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
if ~isfolder(runs_dir)
    mkdir(runs_dir);
end

trajectories = [ ...
    "slow_coordinated", ...
    "faster_low_amplitude", ...
    "phase_shifted"];
profiles = ["nominal", "short_light", "tall_heavy"];
contact_modes = [false, true];

base_config = struct();
base_config.dt = 0.002;
base_config.t_final = 8.0;
base_config.Kp = diag([180, 140]);
base_config.Kd = diag([28, 22]);
base_config.initial_position_offset = deg2rad([2; -2]);
base_config.initial_velocity_offset = deg2rad([1; -1]);
base_config.dissipativity_tolerance = 1e-10;
base_config.limit_tolerance = 1e-10;

profile_parameters = cell(1, numel(profiles));
for profile_index = 1:numel(profiles)
    profile_parameters{profile_index} = default_parameters( ...
        profiles(profile_index));
end
validate_references(trajectories, base_config, profile_parameters{1});

command_file = fopen(fullfile(output_dir, 'commands.txt'), 'w');
assert(command_file >= 0, 'Could not create command record.');
fprintf(command_file, '%s\n', ...
    ['/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab ' ...
    '-logfile /Users/hankli/Desktop/coding/adaptive-traction-mpc/' ...
    'linkage/results/local/human_two_link_baseline/test_console.log ' ...
    '-batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_human_two_link_tests"']);
fprintf(command_file, '%s\n', ...
    ['/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab ' ...
    '-logfile /Users/hankli/Desktop/coding/adaptive-traction-mpc/' ...
    'linkage/results/local/human_two_link_baseline/' ...
    'baseline_console.log ' ...
    '-batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_human_two_link_baseline"']);
fclose(command_file);

version_file = fopen(fullfile(output_dir, 'matlab_version.txt'), 'w');
assert(version_file >= 0, 'Could not create MATLAB version record.');
fprintf(version_file, '%s\n', version);
fclose(version_file);

configuration = struct();
configuration.trajectories = trajectories;
configuration.profiles = profiles;
configuration.contact_modes = ["disabled", "damping"];
configuration.base = base_config;
configuration.profile_parameters = profile_parameters;
configuration.note = "Nominal engineering parameters and deterministic " + ...
    "synthetic stress profiles; not clinically validated patient populations.";
save(fullfile(output_dir, 'configuration_snapshot.mat'), 'configuration');
write_configuration_text(fullfile(output_dir, ...
    'configuration_snapshot.txt'), configuration);

record_count = numel(trajectories) * numel(profiles) * ...
    numel(contact_modes);
records = repmat(empty_record(), record_count, 1);
record_index = 0;

fprintf('HUMAN TWO-LINK BASELINE MATLAB: %s\n', version);
fprintf('HUMAN TWO-LINK OUTPUT: %s\n', output_dir);
fprintf('HUMAN TWO-LINK RUN COUNT: %d\n', record_count);

for trajectory_index = 1:numel(trajectories)
    for profile_index = 1:numel(profiles)
        p = profile_parameters{profile_index};
        for contact_index = 1:numel(contact_modes)
            record_index = record_index + 1;
            config = base_config;
            config.trajectory_name = trajectories(trajectory_index);
            config.contact_enabled = contact_modes(contact_index);
            if config.contact_enabled
                contact_name = "damping";
            else
                contact_name = "disabled";
            end

            run_id = sprintf('%s__%s__%s', ...
                char(config.trajectory_name), char(p.profile_name), ...
                char(contact_name));
            result = simulate_episode(config, p);
            save(fullfile(runs_dir, run_id + ".mat"), ...
                'result', '-v7');

            records(record_index) = make_record( ...
                run_id, config, p, contact_name, result.metrics);
            per_run_table = struct2table(records(record_index));
            writetable(per_run_table, ...
                fullfile(runs_dir, run_id + "_metrics.csv"));

            fprintf(['  %02d/%02d %-64s completed=%d ' ...
                'rmse=[%.4f, %.4f]deg Fmax=%.4fN\n'], ...
                record_index, record_count, run_id, ...
                result.metrics.completed, ...
                rad2deg(result.metrics.rmse_rad(1)), ...
                rad2deg(result.metrics.rmse_rad(2)), ...
                result.metrics.max_contact_force_N);
        end
    end
end

aggregate = struct2table(records);
writetable(aggregate, fullfile(output_dir, 'aggregate_metrics.csv'));
save(fullfile(output_dir, 'aggregate_metrics.mat'), ...
    'aggregate', 'configuration');
create_aggregate_figure(aggregate, fullfile(output_dir, ...
    'aggregate_comparison.png'));

visible_figures = findall(groot, 'Type', 'figure', 'Visible', 'on');
if ~isempty(visible_figures)
    error('HumanTwoLink:VisibleFigure', ...
        'The headless runner created a visible figure.');
end
if any(~aggregate.completed)
    error('HumanTwoLink:IncompleteBaseline', ...
        'At least one baseline case did not complete with finite values.');
end

fprintf(['HUMAN TWO-LINK BASELINE SUMMARY: completed=%d/%d ' ...
    'joint_limit_violations=%d velocity_limit_violations=%d ' ...
    'dissipativity_violations=%d nonfinite=%d\n'], ...
    sum(aggregate.completed), height(aggregate), ...
    sum(aggregate.joint_limit_violation_count), ...
    sum(aggregate.velocity_limit_violation_count), ...
    sum(aggregate.contact_dissipativity_violation_count), ...
    sum(aggregate.nonfinite_count));
end


function validate_references(trajectories, config, p)
t = 0:config.dt:config.t_final;
for trajectory = trajectories
    q = zeros(2, numel(t));
    dq = zeros(2, numel(t));
    ddq = zeros(2, numel(t));
    for index = 1:numel(t)
        [q(:, index), dq(:, index), ddq(:, index)] = ...
            reference_trajectory(t(index), trajectory);
    end
    if any(q < p.q_min | q > p.q_max, 'all')
        error('HumanTwoLink:ReferenceJointLimit', ...
            'Reference %s exceeds a configured joint range.', trajectory);
    end
    if any(abs(dq) > p.dq_max, 'all')
        error('HumanTwoLink:ReferenceVelocityLimit', ...
            'Reference %s exceeds a configured velocity range.', trajectory);
    end
    if any(abs(ddq) > p.reference_ddq_max, 'all')
        error('HumanTwoLink:ReferenceAccelerationLimit', ...
            'Reference %s exceeds a configured acceleration range.', trajectory);
    end
end
end


function record = empty_record()
record = struct( ...
    'run_id', "", ...
    'trajectory', "", ...
    'profile', "", ...
    'contact_mode', "", ...
    'length_scale', 0, ...
    'mass_scale', 0, ...
    'completed', false, ...
    'rmse_q1_deg', 0, ...
    'rmse_q2_deg', 0, ...
    'max_error_q1_deg', 0, ...
    'max_error_q2_deg', 0, ...
    'max_velocity_q1_deg_s', 0, ...
    'max_velocity_q2_deg_s', 0, ...
    'max_acceleration_q1_deg_s2', 0, ...
    'max_acceleration_q2_deg_s2', 0, ...
    'max_torque_q1_Nm', 0, ...
    'max_torque_q2_Nm', 0, ...
    'max_torque_norm_Nm', 0, ...
    'max_contact_force_N', 0, ...
    'contact_dissipativity_violation_count', 0, ...
    'joint_limit_violation_count', 0, ...
    'velocity_limit_violation_count', 0, ...
    'nonfinite_count', 0);
end


function record = make_record(run_id, config, p, contact_name, metrics)
record = empty_record();
record.run_id = string(run_id);
record.trajectory = string(config.trajectory_name);
record.profile = string(p.profile_name);
record.contact_mode = string(contact_name);
record.length_scale = p.length_scale;
record.mass_scale = p.mass_scale;
record.completed = metrics.completed;
record.rmse_q1_deg = rad2deg(metrics.rmse_rad(1));
record.rmse_q2_deg = rad2deg(metrics.rmse_rad(2));
record.max_error_q1_deg = rad2deg(metrics.max_abs_error_rad(1));
record.max_error_q2_deg = rad2deg(metrics.max_abs_error_rad(2));
record.max_velocity_q1_deg_s = ...
    rad2deg(metrics.max_abs_velocity_rad_s(1));
record.max_velocity_q2_deg_s = ...
    rad2deg(metrics.max_abs_velocity_rad_s(2));
record.max_acceleration_q1_deg_s2 = ...
    rad2deg(metrics.max_abs_acceleration_rad_s2(1));
record.max_acceleration_q2_deg_s2 = ...
    rad2deg(metrics.max_abs_acceleration_rad_s2(2));
record.max_torque_q1_Nm = metrics.max_abs_joint_torque_Nm(1);
record.max_torque_q2_Nm = metrics.max_abs_joint_torque_Nm(2);
record.max_torque_norm_Nm = metrics.max_joint_torque_norm_Nm;
record.max_contact_force_N = metrics.max_contact_force_N;
record.contact_dissipativity_violation_count = ...
    metrics.contact_dissipativity_violation_count;
record.joint_limit_violation_count = ...
    metrics.joint_limit_violation_count;
record.velocity_limit_violation_count = ...
    metrics.velocity_limit_violation_count;
record.nonfinite_count = metrics.nonfinite_count;
end


function create_aggregate_figure(aggregate, output_path)
figure_handle = figure('Visible', 'off', 'Position', [50, 50, 1500, 850]);
labels = aggregate.trajectory + " | " + aggregate.profile + ...
    " | " + aggregate.contact_mode;

subplot(2, 1, 1);
bar([aggregate.rmse_q1_deg, aggregate.rmse_q2_deg]);
grid on;
ylabel('Tracking RMSE (deg)');
title('Human two-link oracle validation tracking');
legend({'q1', 'q2'}, 'Location', 'northwest');
xticks(1:height(aggregate));
xticklabels(labels);
xtickangle(45);

subplot(2, 1, 2);
yyaxis left;
bar(aggregate.max_contact_force_N);
ylabel('Maximum contact force (N)');
yyaxis right;
plot(1:height(aggregate), aggregate.max_torque_norm_Nm, ...
    'ko-', 'LineWidth', 1);
ylabel('Maximum joint-torque norm (N m)');
grid on;
title('Contact and generalized torque');
xticks(1:height(aggregate));
xticklabels(labels);
xtickangle(45);

exportgraphics(figure_handle, output_path, 'Resolution', 160);
close(figure_handle);
end


function write_configuration_text(path, configuration)
output_file = fopen(path, 'w');
assert(output_file >= 0, 'Could not create configuration text snapshot.');
cleanup = onCleanup(@() fclose(output_file));

fprintf(output_file, 'MATLAB: %s\n', version);
fprintf(output_file, 'dt: %.17g s\n', configuration.base.dt);
fprintf(output_file, 't_final: %.17g s\n', configuration.base.t_final);
fprintf(output_file, 'Kp: %s\n', mat2str(configuration.base.Kp));
fprintf(output_file, 'Kd: %s\n', mat2str(configuration.base.Kd));
fprintf(output_file, 'initial position offset [deg]: %s\n', ...
    mat2str(rad2deg(configuration.base.initial_position_offset)'));
fprintf(output_file, 'initial velocity offset [deg/s]: %s\n', ...
    mat2str(rad2deg(configuration.base.initial_velocity_offset)'));
fprintf(output_file, 'trajectories: %s\n', ...
    strjoin(configuration.trajectories, ', '));
fprintf(output_file, 'contact modes: disabled, damping\n');
for index = 1:numel(configuration.profiles)
    p = configuration.profile_parameters{index};
    fprintf(output_file, ...
        ['profile=%s length_scale=%.4f mass_scale=%.4f ' ...
        'L1=%.6f L2=%.6f m1=%.6f m2=%.6f sc=%.6f cn=%.6f\n'], ...
        p.profile_name, p.length_scale, p.mass_scale, ...
        p.L1, p.L2, p.m1, p.m2, p.sc, p.cn);
end
fprintf(output_file, '%s\n', configuration.note);
end
