function result = simulate_near_extension_protective_mode_sanity(config)
%SIMULATE_NEAR_EXTENSION_PROTECTIVE_MODE_SANITY Ideal command-interface check.
%
% Measured state is set equal to the issued kinematic command. This is
% intentionally not a contact or actuator simulation.

if nargin < 1, config = near_extension_protective_mode_config(); end
p = human_two_link_v2_parameters(1.72, 75);
[flexion_switch, return_switch] = switch_references(config.q_switch_rad);
takeoff = run_takeoff(config, p, flexion_switch);
landing = run_landing(config, p, return_switch);
gap = config.dt;
landing.t = landing.t+takeoff.t(end)+gap;
result = concatenate(takeoff, landing);
result.config = config; result.parameters = p;
result.evidence = near_extension_protective_mode_q_switch_evidence();
result.metrics = metrics(result, takeoff, landing, config, p, flexion_switch);
end


function run = run_takeoff(config, p, switch_ref)
state = near_extension_protective_mode_initial_state("takeoff");
q = near_extension_protective_mode_coordinated_posture(config.q_terminal_rad);
dq = zeros(2, 1); u_previous = zeros(2, 1); t = 0;
records = repmat(empty_record(), 1, 1);
for index = 1:ceil((config.transition_duration_s+0.8)/config.dt)+3
    request = index > 1;
    input = make_input(t, q, dq, [40; 10], false, request, ...
        switch_ref, p, config.normal_config, u_previous);
    [state, command, telemetry] = ...
        near_extension_protective_mode_step(state, input, config);
    records(index) = record(t, q, dq, [40; 10], command, telemetry);
    if all(isfinite(command.force_command_N)),u_previous=command.force_command_N;end
    if command.actuation_mode == "KINEMATIC_POSITION_VELOCITY"
        q = command.q_cmd_rad; dq = command.dq_cmd_rad_s;
    else
        q = switch_ref.q; dq = switch_ref.dq;
    end
    if state.mode == "NORMAL_REHAB" && index > 3, break; end
    t = t+config.dt;
end
run = records_to_run(records, "takeoff");
end


function run = run_landing(config, p, switch_ref)
state = near_extension_protective_mode_initial_state("landing");
q = switch_ref.q; dq = switch_ref.dq; u_previous = zeros(2, 1); t = 0;
records = repmat(empty_record(), 1, 1);
for index = 1:ceil((config.transition_duration_s+0.2)/config.dt)+3
    input = make_input(t, q, dq, [40; 10], index > 1, false, ...
        switch_ref, p, config.normal_config, u_previous);
    [state, command, telemetry] = ...
        near_extension_protective_mode_step(state, input, config);
    records(index) = record(t, q, dq, [40; 10], command, telemetry);
    if all(isfinite(command.force_command_N)),u_previous=command.force_command_N;end
    if command.actuation_mode == "KINEMATIC_POSITION_VELOCITY"
        q = command.q_cmd_rad; dq = command.dq_cmd_rad_s;
    end
    if state.mode == "TERMINAL", break; end
    t = t+config.dt;
end
run = records_to_run(records, "landing");
end


function input = make_input(t, q, dq, force, landing, takeoff, ...
        reference, p, normal_config, u_previous)
context = struct('tau_bed_Nm', zeros(2, 1), ...
    'u_previous_N', u_previous, 'parameters', p, ...
    'config', normal_config, 'robot_authority', 1, 'bed_credit', 0);
input = struct('time_s', t, 'measured_q_rad', q, ...
    'measured_dq_rad_s', dq, 'measured_force_N', force, ...
    'request_landing', landing, 'request_takeoff', takeoff, ...
    'normal_reference', reference, 'normal_context', context);
end


function [flexion, returning] = switch_references(q_switch)
f = @(time) reference_q2(time)-q_switch;
t_flexion = fzero(f, [1, 7.5]);
t_return = fzero(f, [8.5, 15]);
[flexion.q, flexion.dq, flexion.ddq] = ...
    human_two_link_v2_reference(t_flexion, "slow_passive_flexion_v2");
[returning.q, returning.dq, returning.ddq] = ...
    human_two_link_v2_reference(t_return, "slow_passive_flexion_v2");
end


function q2 = reference_q2(time)
[q, ~, ~] = human_two_link_v2_reference(time, ...
    "slow_passive_flexion_v2");
q2 = q(2);
end


function item = empty_record()
item = struct('t', 0, 'q', zeros(2, 1), 'dq', zeros(2, 1), ...
    'force', zeros(2, 1), 'q_cmd', zeros(2, 1), ...
    'dq_cmd', zeros(2, 1), 'ddq_cmd', zeros(2, 1), ...
    'force_command', nan(2, 1), 'mode', "", 'actuation_mode', "", ...
    'normal_called', false, 'force_inversion_called', false, ...
    'force_veto', false);
end


function item = record(t, q, dq, force, command, telemetry)
item = struct('t', t, 'q', q, 'dq', dq, 'force', force, ...
    'q_cmd', command.q_cmd_rad, 'dq_cmd', command.dq_cmd_rad_s, ...
    'ddq_cmd', command.ddq_cmd_rad_s2, ...
    'force_command', command.force_command_N, 'mode', telemetry.mode, ...
    'actuation_mode', command.actuation_mode, ...
    'normal_called', telemetry.normal_controller_called, ...
    'force_inversion_called', telemetry.force_inversion_called, ...
    'force_veto', telemetry.force_veto_active);
end


function run = records_to_run(records, direction)
run = struct('t', [records.t], 'q', [records.q], 'dq', [records.dq], ...
    'measured_force_N', [records.force], 'q_cmd', [records.q_cmd], ...
    'dq_cmd', [records.dq_cmd], 'ddq_cmd', [records.ddq_cmd], ...
    'force_command_N', [records.force_command], 'mode', [records.mode], ...
    'actuation_mode', [records.actuation_mode], ...
    'normal_controller_called', [records.normal_called], ...
    'force_inversion_called', [records.force_inversion_called], ...
    'force_veto', [records.force_veto], 'direction', direction);
end


function result = concatenate(a, b)
fields = {'t','q','dq','measured_force_N','q_cmd','dq_cmd','ddq_cmd', ...
    'force_command_N','mode','actuation_mode','normal_controller_called', ...
    'force_inversion_called','force_veto'};
for index = 1:numel(fields)
    name = fields{index}; result.(name) = [a.(name), b.(name)];
end
result.segment = [repmat("takeoff", 1, numel(a.t)), ...
    repmat("landing", 1, numel(b.t))];
end


function value = metrics(result, takeoff, landing, config, p, switch_ref)
landing_sequence = strjoin(cellstr(unique(landing.mode, 'stable')), '>');
takeoff_sequence = strjoin(cellstr(unique(takeoff.mode, 'stable')), '>');
terminal = landing.q_cmd(:, end);
near = result.q(2, :) < config.q_switch_rad-config.switch_tolerance_rad;
first_landing = find(landing.mode == "BLEND_TO_LANDING", 1, 'first');
landing_capture = norm(landing.q_cmd(:, first_landing)- ...
    landing.q(:, first_landing), Inf);
last_takeoff = find(takeoff.mode == "BLEND_TO_NORMAL", 1, 'last');
normal_takeoff = find(takeoff.mode == "NORMAL_REHAB", 1, 'first');
handoff_q_jump = norm(takeoff.q_cmd(:, last_takeoff)- ...
    takeoff.q_cmd(:, normal_takeoff), Inf);
handoff_dq_jump = norm(takeoff.dq_cmd(:, last_takeoff)- ...
    takeoff.dq_cmd(:, normal_takeoff), Inf);
veto = veto_check(config, p, switch_ref);
regression = normal_regression(config, p, switch_ref);
value = struct('landing_sequence', string(landing_sequence), ...
    'takeoff_sequence', string(takeoff_sequence), ...
    'terminal_q2_deg', rad2deg(terminal(2)), ...
    'terminal_error_deg', abs(rad2deg(terminal(2))-config.q_terminal_deg), ...
    'landing_capture_jump_rad', landing_capture, ...
    'takeoff_handoff_q_jump_rad', handoff_q_jump, ...
    'takeoff_handoff_dq_jump_rad_s', handoff_dq_jump, ...
    'near_extension_force_inversion_calls', ...
    sum(result.force_inversion_called & near), ...
    'force_veto_latched', veto.latched, ...
    'force_veto_mode', veto.mode, ...
    'normal_force_command_delta_N', regression.force_delta_N, ...
    'normal_controller_exact_reuse', regression.exact_reuse);
end


function outcome = veto_check(config, p, reference)
state = near_extension_protective_mode_initial_state("takeoff");
q = near_extension_protective_mode_coordinated_posture(config.q_terminal_rad);
input = make_input(0, q, zeros(2, 1), ...
    [config.force_bound_N+1; 0], false, true, reference, p, ...
    config.normal_config, zeros(2, 1));
[state, ~, telemetry] = near_extension_protective_mode_step(state, input, config);
outcome = struct('latched', state.protective_stop_latched, ...
    'mode', telemetry.mode);
end


function outcome = normal_regression(config, p, reference)
q = reference.q; dq = reference.dq; previous = [20; -5];
input = make_input(0, q, dq, [40; 10], false, false, reference, p, ...
    config.normal_config, previous);
state = near_extension_protective_mode_initial_state("landing");
[~, command] = near_extension_protective_mode_step(state, input, config);
[expected, ~] = bed_supported_v1_robot_controller(q, dq, reference.q, ...
    reference.dq, reference.ddq, zeros(2, 1), previous, p, ...
    config.normal_config, 1, 0);
delta = norm(command.force_command_N-expected, Inf);
outcome = struct('force_delta_N', delta, 'exact_reuse', delta == 0);
end
