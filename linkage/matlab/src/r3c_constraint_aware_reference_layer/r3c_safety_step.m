function state=r3c_safety_step(state,signals,config)
%R3C_SAFETY_STEP NORMAL/SLOWDOWN/HOLD/RECOVERY_REFERENCE hierarchy.

mode_before=state.mode;state.mode_time_s=state.mode_time_s+config.dt;
warning=config.r3c_warning_buffer_rad;
hold=config.r3c_hold_buffer_rad;resume=config.r3c_resume_buffer_rad;
predicted=signals.predicted_min_soft_clearance_rad;
state.alpha=clearance_scale(predicted,hold,warning);

switch state.mode
    case "NORMAL"
        state.alpha=1;
        if predicted<=warning || ...
                (signals.force_infeasible && predicted<=resume)
            state=change_mode(state,"SLOWDOWN",signals,"PREDICTIVE_MARGIN");
        end
    case "SLOWDOWN"
        if predicted<=hold
            state=change_mode(state,"HOLD",signals,"HOLD_BUFFER");
            state.alpha=0;
        elseif predicted>=resume && ~signals.force_infeasible
            state=change_mode(state,"NORMAL",signals,"MARGIN_RESTORED");
            state.alpha=1;
        end
    case "HOLD"
        state.alpha=0;
        if signals.current_min_soft_clearance_rad< ...
                -config.soft_margin_tolerance_rad
            state.classification="RECOVERY_FAILED";
        elseif state.mode_time_s>=config.r3c_hold_before_recovery_s
            if signals.recovery_feasible
                state=change_mode(state,"RECOVERY_REFERENCE",signals, ...
                    "RECOVERY_AVAILABLE");
            else
                state.classification="TASK_INFEASIBLE";
                state.last_reason="NO_SAFE_RECOVERY_REFERENCE";
            end
        end
    case "RECOVERY_REFERENCE"
        state.alpha=0;
        if signals.current_min_soft_clearance_rad>=resume && ...
                predicted>=resume && ~signals.force_infeasible
            state.recovery_success_count=state.recovery_success_count+1;
            state=change_mode(state,"NORMAL",signals,"RECOVERY_COMPLETE");
            state.resume_blending=true;
            state.alpha=1;
        elseif state.mode_time_s>=config.r3c_recovery_timeout_s
            state.classification="RECOVERY_FAILED";
            state.last_reason="RECOVERY_TIMEOUT";
        elseif signals.current_min_soft_clearance_rad< ...
                -config.soft_margin_tolerance_rad
            state.classification="RECOVERY_FAILED";
            state.last_reason="SOFT_BOUNDARY_REACHED";
        end
    otherwise
        state.classification="ABORTED";
        state.last_reason="INVALID_SAFETY_MODE";
end

if state.mode=="SLOWDOWN",state.slowdown_time_s=state.slowdown_time_s+config.dt;end
if state.mode=="HOLD",state.hold_time_s=state.hold_time_s+config.dt;end
if state.mode=="RECOVERY_REFERENCE"
    state.recovery_time_s=state.recovery_time_s+config.dt;
end
if state.mode~="NORMAL"
    state.total_intervention_time_s=state.total_intervention_time_s+config.dt;
end
if state.mode~=mode_before,state.mode_time_s=0;end
end


function state=change_mode(state,mode,signals,reason)
state.mode=string(mode);state.mode_time_s=0;state.last_reason=string(reason);
if isnan(state.first_intervention_time_s) && mode~="NORMAL"
    state.first_intervention_time_s=signals.time_s;
    state.first_intervention_progress=signals.progress;
end
if mode=="SLOWDOWN",state.slowdown_count=state.slowdown_count+1;end
if mode=="HOLD",state.hold_count=state.hold_count+1;end
if mode=="RECOVERY_REFERENCE",state.recovery_count=state.recovery_count+1;end
end


function alpha=clearance_scale(clearance,hold,warning)
if clearance<=hold,alpha=0;return;end
if clearance>=warning,alpha=1;return;end
r=(clearance-hold)/(warning-hold);
alpha=10*r^3-15*r^4+6*r^5;
alpha=min(max(alpha,0),1);
end
