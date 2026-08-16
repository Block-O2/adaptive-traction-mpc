function progress = dynamic_robust_v1_advance_progress( ...
        progress, enabled, config)
%DYNAMIC_ROBUST_V1_ADVANCE_PROGRESS Jerk-limited run/pause governor.
%
% During a pause the rate and acceleration states ramp toward zero, but the
% task coordinate itself is held. Physical reference continuity is handled by
% the state's blend reference; residual governor speed must not move the tube
% center away from a fixed transfer target.

target_rate=double(enabled)*config.nominal_progress_rate;
desired_acceleration=min(max(4*(target_rate-progress.s_dot), ...
    -config.max_progress_acceleration),config.max_progress_acceleration);
jerk=min(max((desired_acceleration-progress.s_ddot)/config.dt, ...
    -config.max_progress_jerk),config.max_progress_jerk);
progress.s_ddot=min(max(progress.s_ddot+config.dt*jerk, ...
    -config.max_progress_acceleration),config.max_progress_acceleration);
progress.s_dot=max(0,min(config.max_progress_rate, ...
    progress.s_dot+config.dt*progress.s_ddot));
if enabled
    progress.s=min(1,progress.s+config.dt*progress.s_dot);
end
end
