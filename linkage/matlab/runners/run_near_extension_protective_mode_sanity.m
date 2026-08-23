function output_dir = run_near_extension_protective_mode_sanity()
%RUN_NEAR_EXTENSION_PROTECTIVE_MODE_SANITY Authorized MATLAB sanity experiment.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
stamp = char(datetime('now', 'Format', 'yyyyMMdd_HHmmss'));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'near_extension_protective_mode_sanity', stamp);
if ~isfolder(output_dir), mkdir(output_dir); end
diary_path = fullfile(output_dir, 'console.log');
diary(diary_path); cleanup = onCleanup(@()diary('off'));
config = near_extension_protective_mode_config();
result = simulate_near_extension_protective_mode_sanity(config);
metrics = struct2table(result.metrics);
writetable(metrics, fullfile(output_dir, 'sanity_metrics.csv'));
writetable(result.evidence.snapshot, ...
    fullfile(output_dir, 'q_switch_evidence.csv'));
save(fullfile(output_dir, 'sanity_result.mat'), 'result', 'config', '-v7.3');
gif_path = fullfile(output_dir, 'near_extension_protective_mode.gif');
near_extension_protective_mode_create_gif(result, gif_path);
write_summary(fullfile(output_dir, 'summary.txt'), result.metrics, config);
fprintf('NEAR-EXTENSION SANITY OUTPUT: %s\n', output_dir);
fprintf('TAKEOFF SEQUENCE: %s\n', result.metrics.takeoff_sequence);
fprintf('LANDING SEQUENCE: %s\n', result.metrics.landing_sequence);
fprintf(['terminal_q2=%.9g deg capture_jump=%.3g rad ' ...
    'handoff_q_jump=%.3g rad handoff_dq_jump=%.3g rad/s\n'], ...
    result.metrics.terminal_q2_deg, result.metrics.landing_capture_jump_rad, ...
    result.metrics.takeoff_handoff_q_jump_rad, ...
    result.metrics.takeoff_handoff_dq_jump_rad_s);
fprintf(['near_extension_force_inversion_calls=%d force_veto=%d ' ...
    'normal_exact_reuse=%d\n'], ...
    result.metrics.near_extension_force_inversion_calls, ...
    result.metrics.force_veto_latched, ...
    result.metrics.normal_controller_exact_reuse);
end


function write_summary(path, metrics, config)
file = fopen(path, 'w'); assert(file >= 0); cleanup = onCleanup(@()fclose(file));
fprintf(file, 'Near-extension protective mode MATLAB sanity\n');
fprintf(file, 'Scope: %s; not contact/actuator validation\n', config.validation_scope);
fprintf(file, 'q_switch=%.6g deg (engineering, not clinical); q_terminal=%.6g deg\n', ...
    config.q_switch_deg, config.q_terminal_deg);
names = fieldnames(metrics);
for index = 1:numel(names)
    value = metrics.(names{index});
    if isstring(value), text = char(value); else, text = mat2str(value, 12); end
    fprintf(file, '%s=%s\n', names{index}, text);
end
end
