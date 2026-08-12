function [state, reference, details] = hybrid_tube_v1_manager_step( ...
        state, plan, actual_q, actual_dq, p, config)
%HYBRID_TUBE_V1_MANAGER_STEP Jerk-limited monotone progress governor.

if state.status ~= "RUNNING"
    target_rate = 0;
else
    lookahead = min(1, state.s+max(state.s_dot, ...
        config.nominal_progress_rate)*0.10);
    ahead = hybrid_tube_v1_plan_sample(plan, lookahead);
    utilization = max(abs(ahead.force_local))/config.force_bound_N;
    force_factor = quintic_factor((config.force_utilization_stop- ...
        utilization)/(config.force_utilization_stop- ...
        config.force_utilization_slow));
    force_gradient = norm(ahead.force_local-state.previous_force)/ ...
        max(lookahead-state.s, 1e-6);
    slew_rate = min(config.max_progress_rate, ...
        min(config.du_max)/max(force_gradient, 1e-9));
    target_rate = min(config.nominal_progress_rate*force_factor, slew_rate);
    if ~ahead.hold_feasible
        target_rate = 0;
    end
end

desired_acceleration = min(max(4*(target_rate-state.s_dot), ...
    -config.max_progress_acceleration), config.max_progress_acceleration);
jerk = min(max((desired_acceleration-state.s_ddot)/config.dt, ...
    -config.max_progress_jerk), config.max_progress_jerk);
state.s_ddot = state.s_ddot+config.dt*jerk;
state.s_ddot = min(max(state.s_ddot, -config.max_progress_acceleration), ...
    config.max_progress_acceleration);
state.s_dot = max(0, min(config.max_progress_rate, ...
    state.s_dot+config.dt*state.s_ddot));
state.s = min(1, state.s+config.dt*state.s_dot);

sample = hybrid_tube_v1_plan_sample(plan, state.s);
reference = struct();
reference.q = sample.q;
reference.dq = sample.q_s*state.s_dot;
reference.ddq = sample.q_ss*state.s_dot^2+sample.q_s*state.s_ddot;
reference.sample = sample;

current = single_arm_quasistatic_hold_point(actual_q, p, ...
    config.force_bound_N, config.svd_relative_tolerance);
current_hold_feasible = ~current.rank_deficient && ...
    current.bounded_residual_norm(1) <= config.plan_residual_tolerance_Nm && ...
    all(abs(current.force_local) <= config.force_bound_N+ ...
    config.bound_tolerance_N);
if target_rate <= 1e-10 && state.s_dot <= 1e-6 && state.s < 1- ...
        config.progress_tolerance
    state.pause_time = state.pause_time+config.dt;
else
    state.pause_time = 0;
end
if state.pause_time >= config.pause_classification_s && ...
        state.status == "RUNNING"
    if current_hold_feasible
        state.status = "TRANSFER_REQUIRED";
    else
        state.status = "INFEASIBLE";
    end
end
terminal_error = actual_q-sample.q;
if state.s >= 1-config.progress_tolerance && ...
        all(abs(terminal_error) <= sample.tube_rad+ ...
        config.terminal_position_tolerance_rad) && current_hold_feasible
    state.status = "TASK_COMPLETE";
end
state.previous_force = sample.force_local;
details = struct('target_progress_rate', target_rate, ...
    'force_utilization', max(abs(sample.force_local))/ ...
    config.force_bound_N, 'current_hold_feasible', current_hold_feasible, ...
    'current_support_residual_Nm', current.bounded_residual_norm(1), ...
    'actual_velocity_norm', norm(actual_dq), 'jerk', jerk);
end


function y = quintic_factor(x)
x = min(max(x, 0), 1);
y = 10*x^3-15*x^4+6*x^5;
end
