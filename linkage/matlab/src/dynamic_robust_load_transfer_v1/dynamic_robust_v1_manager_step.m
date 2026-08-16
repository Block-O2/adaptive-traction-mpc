function [state, action] = dynamic_robust_v1_manager_step( ...
        state, signals, config)
%DYNAMIC_ROBUST_V1_MANAGER_STEP Hybrid safety supervisor state transition.

state.mode_time_s = state.mode_time_s+config.dt;
mode_before = state.mode;
state.entry_guard_time_s = stable_timer(state.entry_guard_time_s, ...
    signals.entry_ready, config.dt);
state.contact_stable_time_s = stable_timer(state.contact_stable_time_s, ...
    signals.bed_supported, config.dt);
if isfield(signals,'recontact_stable')
    recontact_stable=signals.recontact_stable;
else
    recontact_stable=signals.bed_supported;
end
state.recontact_stable_time_s=stable_timer( ...
    state.recontact_stable_time_s,recontact_stable,config.dt);
state.absent_stable_time_s = stable_timer(state.absent_stable_time_s, ...
    signals.bed_absent, config.dt);
action = default_action(state.mode);

if signals.force_bound_violation
    state = fail(state, "FORCE_BOUND_VIOLATION");
elseif signals.rom_violation
    state = fail(state, "ABORTED");
elseif signals.soft_limit_violation
    state = fail(state, "SOFT_LIMIT_VIOLATION");
end
if state.classification ~= "RUNNING"
    action = default_action(state.mode);
    action.progress_enabled = false;
    action.bed_credit = state.bed_credit;
    return;
end

switch state.mode
    case "BED_SUPPORTED_MOTION"
        action.progress_enabled = true;
        action.bed_credit = 1;
        if state.entry_guard_time_s >= config.entry_guard_duration_s
            state = change_mode(state, "TRANSFER_READY");
        elseif signals.return_phase_reached
            state = fail(state, "TRANSFER_REGION_NOT_REACHED");
        end
    case "TRANSFER_READY"
        action.use_transfer_target = true;
        if ~signals.bed_supported
            state = fail(state, "LOAD_TAKEOVER_FAILED");
        elseif signals.takeover_feasible && ...
                state.mode_time_s >= config.transfer_ready_duration_s
            state = change_mode(state, "LOAD_TAKEOVER");
        elseif state.mode_time_s >= config.transfer_ready_duration_s+ ...
                config.takeover_recovery_timeout_s
            state = fail(state, "LOAD_TAKEOVER_FAILED");
        elseif signals.robust_static_margin_N < ...
                config.robust_entry_trigger_N- ...
                config.robust_entry_hysteresis_N
            state = change_mode(state, "BED_SUPPORTED_MOTION");
        end
    case "LOAD_TAKEOVER"
        action.use_transfer_target = true;
        action.progress_enabled = true;
        erosion = ~signals.takeover_feasible;
        if erosion && signals.bed_supported
            state.takeover_paused = true;
            state.recovery_time_s = state.recovery_time_s+config.dt;
            action.pause_unloading = true;
            action.progress_enabled = false;
            action.bed_credit = state.bed_credit;
            if state.recovery_time_s >= config.takeover_recovery_timeout_s
                state = fail(state, "LOAD_TAKEOVER_FAILED");
            end
        elseif erosion
            state = fail(state, "DYNAMIC_MARGIN_VIOLATION");
        else
            state.takeover_paused = false;
            state.recovery_time_s = 0;
            state.takeover_time_s=state.takeover_time_s+config.dt;
            fraction = smooth01(state.takeover_time_s/ ...
                config.load_takeover_duration_s);
            state.bed_credit = min(state.bed_credit, 1-fraction);
            action.bed_credit = state.bed_credit;
            if fraction >= 1
                state = change_mode(state, "LIFTOFF");
                state.bed_credit = 0;
            end
        end
    case "LIFTOFF"
        action.use_transfer_target = true;
        action.bed_credit = 0;
        if signals.liftoff_ready && state.absent_stable_time_s >= ...
                config.contact_stable_duration_s
            state = change_mode(state, "SUSPENDED_MOTION");
        elseif ~signals.takeover_feasible && ~signals.bed_supported
            state = fail(state, "LIFTOFF_INFEASIBLE");
        elseif state.mode_time_s >= config.liftoff_timeout_s
            state = fail(state, "LIFTOFF_INFEASIBLE");
        end
    case "SUSPENDED_MOTION"
        action.bed_credit = 0;
        action.use_governed_plan = true;
        action.progress_enabled = state.mode_time_s >= ...
            config.suspended_blend_duration_s && signals.suspended_feasible;
        if signals.prepare_recontact
            action.progress_enabled = false;
            action.use_return_target = true;
        end
        if ~signals.suspended_feasible
            state.recovery_time_s = state.recovery_time_s+config.dt;
            if state.recovery_time_s >= config.suspended_pause_timeout_s
                state = fail(state, "SUSPENDED_INFEASIBLE");
            end
        else
            state.recovery_time_s = 0;
        end
        if signals.returning && state.contact_stable_time_s >= ...
                config.contact_stable_duration_s
            state = change_mode(state, "RECONTACT");
        elseif signals.task_at_end
            state = fail(state, "RECONTACT_FAILED");
        end
    case "RECONTACT"
        action.use_return_target = true;
        action.bed_credit = 0;
        if isfield(signals,'recontact_unsafe') && signals.recontact_unsafe
            state = fail(state, "RECONTACT_FAILED");
        elseif recontact_timer(state,config) >= ...
                config.contact_stable_duration_s
            state = change_mode(state, "LOAD_RETURN");
        elseif state.mode_time_s >= config.recontact_timeout_s
            state = fail(state, "RECONTACT_FAILED");
        end
    case "LOAD_RETURN"
        action.use_return_target = true;
        fraction = smooth01(state.mode_time_s/config.load_return_duration_s);
        state.bed_credit = max(state.bed_credit, fraction);
        action.bed_credit = state.bed_credit;
        if ~signals.bed_supported && ...
                signals.robust_static_margin_N <= ...
                config.robust_entry_hysteresis_N
            state = fail(state, "LOAD_RETURN_FAILED");
        elseif fraction >= 1 && recontact_timer(state,config) >= ...
                config.contact_stable_duration_s
            state = change_mode(state, "BED_SUPPORTED_RETURN");
            state.bed_credit = 1;
        end
    case "BED_SUPPORTED_RETURN"
        action.progress_enabled = true;
        action.bed_credit = 1;
        if signals.task_complete
            state = change_mode(state, "TASK_COMPLETE");
            state.classification = "TASK_COMPLETE";
        elseif ~signals.bed_supported && ...
                signals.robust_static_margin_N <= 0
            state = fail(state, "LOAD_RETURN_FAILED");
        end
    case "TASK_COMPLETE"
        state.classification = "TASK_COMPLETE";
    otherwise
        state = fail(state, "ABORTED");
end
if state.mode ~= mode_before
    action = default_action(state.mode);
end
action.bed_credit = state.bed_credit;
end


function value = stable_timer(previous, condition, dt)
if condition, value = previous+dt; else, value = 0; end
end


function state = change_mode(state, mode)
state.mode = string(mode); state.mode_time_s = 0;
state.recovery_time_s = 0;
if mode == "LOAD_TAKEOVER"
    state.bed_credit = 1; state.takeover_time_s = 0;
    state.takeover_paused = false;
end
if mode == "RECONTACT"
    state.contact_stable_time_s = 0;
    state.recontact_stable_time_s = 0;
end
end


function value=recontact_timer(state,config)
enabled=isfield(config,'r3b_recontact_enabled') && ...
    config.r3b_recontact_enabled;
if enabled,value=state.recontact_stable_time_s;
else,value=state.contact_stable_time_s;end
end


function state = fail(state, classification)
state.classification = string(classification);
end


function action = default_action(mode)
action = struct('progress_enabled', false, 'use_transfer_target', false, ...
    'use_governed_plan', false, 'use_return_target', false, ...
    'pause_unloading', false, 'bed_credit', 1);
switch mode
    case {"BED_SUPPORTED_MOTION","BED_SUPPORTED_RETURN"}
        action.progress_enabled = true;
    case {"TRANSFER_READY","LOAD_TAKEOVER","LIFTOFF"}
        action.use_transfer_target = true;
        if mode=="LOAD_TAKEOVER",action.progress_enabled=true;end
    case "SUSPENDED_MOTION"
        action.use_governed_plan = true; action.bed_credit = 0;
    case {"RECONTACT","LOAD_RETURN"}
        action.use_return_target = true;
end
end


function value = smooth01(r)
r = min(max(r,0),1); value = 10*r^3-15*r^4+6*r^5;
end
