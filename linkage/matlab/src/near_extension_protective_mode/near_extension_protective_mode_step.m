function [state, command, telemetry] = near_extension_protective_mode_step( ...
        state, input, config)
%NEAR_EXTENSION_PROTECTIVE_MODE_STEP Sanity state machine and command router.
%
% Kinematic modes generate q/dq/ddq without force inversion. NORMAL_REHAB
% delegates unchanged to bed_supported_v1_robot_controller. Measured force is
% used only by the hard veto and never changes the kinematic trajectory.

q = input.measured_q_rad(:); dq = input.measured_dq_rad_s(:);
force = input.measured_force_N(:);
force_veto = any(~isfinite(force)) || any(abs(force) > ...
    config.force_bound_N+config.force_veto_tolerance_N);
if force_veto
    state.protective_stop_latched = true;
    state.mode = "PROTECTIVE_STOP";
end
if state.protective_stop_latched
    command = kinematic_command(q, zeros(2, 1), zeros(2, 1), ...
        "PROTECTIVE_STOP");
    telemetry = details(false, force_veto, state, 0);
    return;
end

if state.direction == "landing"
    [state, command, normal_called, elapsed] = landing_step( ...
        state, input, config, q, dq);
else
    [state, command, normal_called, elapsed] = takeoff_step( ...
        state, input, config, q, dq);
end
telemetry = details(normal_called, false, state, elapsed);
end


function [state, command, normal_called, elapsed] = landing_step( ...
        state, input, config, q, dq)
normal_called = false; elapsed = 0;
if state.mode == "NORMAL_REHAB"
    if input.request_landing && q(2) <= ...
            config.q_switch_rad+config.switch_tolerance_rad
        state = start_patch(state, input.time_s, q, dq, ...
            near_extension_protective_mode_coordinated_posture( ...
            config.q_terminal_rad), zeros(2, 1), zeros(2, 1));
        state.mode = "BLEND_TO_LANDING";
        state.transition_count = state.transition_count+1;
    else
        [command, normal_called] = normal_command(input);
        return;
    end
end
elapsed = input.time_s-state.patch_start_time_s;
sample = patch_sample(state, elapsed, config);
if sample.complete
    state.mode = "TERMINAL";
elseif elapsed >= config.blend_duration_s
    state.mode = "KINEMATIC_LANDING";
else
    state.mode = "BLEND_TO_LANDING";
end
command = kinematic_command(sample.q, sample.dq, sample.ddq, state.mode);
end


function [state, command, normal_called, elapsed] = takeoff_step( ...
        state, input, config, q, dq)
normal_called = false; elapsed = 0;
if state.mode == "BED_START"
    if ~input.request_takeoff
        command = kinematic_command(q, zeros(2, 1), zeros(2, 1), ...
            "BED_START");
        return;
    end
    state = start_patch(state, input.time_s, q, dq, ...
        near_extension_protective_mode_coordinated_posture( ...
        config.q_switch_rad), input.normal_reference.dq, ...
        input.normal_reference.ddq);
    state.mode = "KINEMATIC_TAKEOFF";
    state.transition_count = state.transition_count+1;
end
if ismember(state.mode, ["KINEMATIC_TAKEOFF", "BLEND_TO_NORMAL"])
    elapsed = input.time_s-state.patch_start_time_s;
    sample = patch_sample(state, elapsed, config);
    blend_start = config.transition_duration_s-config.blend_duration_s;
    if sample.complete
        state.mode = "NORMAL_REHAB";
        [command, normal_called] = normal_command(input);
        return;
    elseif elapsed >= blend_start
        state.mode = "BLEND_TO_NORMAL";
    else
        state.mode = "KINEMATIC_TAKEOFF";
    end
    command = kinematic_command(sample.q, sample.dq, sample.ddq, state.mode);
else
    [command, normal_called] = normal_command(input);
end
end


function state = start_patch(state, time_s, q, dq, qf, dqf, ddqf)
state.patch_active = true;
state.patch_start_time_s = time_s;
state.patch_q0_rad = q;
state.patch_dq0_rad_s = dq;
state.patch_qf_rad = qf;
state.patch_dqf_rad_s = dqf(:);
state.patch_ddqf_rad_s2 = ddqf(:);
end


function sample = patch_sample(state, elapsed, config)
sample = near_extension_protective_mode_quintic(elapsed, ...
    config.transition_duration_s, state.patch_q0_rad, ...
    state.patch_dq0_rad_s, state.patch_qf_rad, ...
    state.patch_dqf_rad_s, zeros(2, 1), state.patch_ddqf_rad_s2);
end


function [command, called] = normal_command(input)
context = input.normal_context;
[u, controller] = bed_supported_v1_robot_controller( ...
    input.measured_q_rad, input.measured_dq_rad_s, ...
    input.normal_reference.q, input.normal_reference.dq, ...
    input.normal_reference.ddq, context.tau_bed_Nm, ...
    context.u_previous_N, context.parameters, context.config, ...
    context.robot_authority, context.bed_credit);
command = struct('actuation_mode', "FORCE_AWARE_NORMAL", ...
    'q_cmd_rad', input.normal_reference.q(:), ...
    'dq_cmd_rad_s', input.normal_reference.dq(:), ...
    'ddq_cmd_rad_s2', input.normal_reference.ddq(:), ...
    'force_command_N', u, 'normal_controller_details', controller);
called = true;
end


function command = kinematic_command(q, dq, ddq, label)
command = struct('actuation_mode', "KINEMATIC_POSITION_VELOCITY", ...
    'q_cmd_rad', q(:), 'dq_cmd_rad_s', dq(:), ...
    'ddq_cmd_rad_s2', ddq(:), 'force_command_N', nan(2, 1), ...
    'normal_controller_details', struct('bypassed_reason', label));
end


function telemetry = details(normal_called, force_veto, state, elapsed)
telemetry = struct('mode', state.mode, ...
    'normal_controller_called', normal_called, ...
    'force_inversion_called', normal_called, ...
    'force_veto_active', force_veto || state.protective_stop_latched, ...
    'patch_elapsed_s', elapsed, 'direction', state.direction);
end
