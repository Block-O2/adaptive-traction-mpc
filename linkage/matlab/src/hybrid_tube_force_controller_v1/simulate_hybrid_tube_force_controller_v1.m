function result = simulate_hybrid_tube_force_controller_v1(config, p, plan)
%SIMULATE_HYBRID_TUBE_FORCE_CONTROLLER_V1 Closed-loop task-set rollout.

if nargin < 3 || isempty(plan)
    plan = hybrid_tube_v1_build_plan(p, config);
end
max_samples = floor(config.max_time_s/config.dt)+1;
t = (0:max_samples-1)*config.dt;
x = zeros(4, max_samples);

initial = hybrid_tube_v1_plan_sample(plan, 0);
% A wider tube must not silently pre-position the patient into a lower-force
% posture before the modeled rollout begins.
x(:, 1) = [initial.nominal_q; zeros(2, 1)];
initial_hold = single_arm_quasistatic_hold_point(initial.nominal_q, p, ...
    config.force_bound_N, config.svd_relative_tolerance);
u_previous = initial_hold.bounded_force(:, 1);
initial_hold_feasible = ~initial_hold.rank_deficient && ...
    initial_hold.exact_feasible(1) && ...
    initial_hold.bounded_residual_norm(1) <= ...
    config.plan_residual_tolerance_Nm;
if initial_hold_feasible
    initial_status = "RUNNING";
else
    initial_status = "INITIAL_SUPPORT_REQUIRED";
end
manager = struct('s', 0, 's_dot', 0, 's_ddot', 0, ...
    'pause_time', 0, 'status', initial_status, ...
    'previous_force', initial.force_local);

q_reference = zeros(2, max_samples);
dq_reference = zeros(2, max_samples);
ddq_reference = zeros(2, max_samples);
q_nominal = zeros(2, max_samples);
tube = zeros(2, max_samples);
progress = zeros(1, max_samples);
progress_rate = zeros(1, max_samples);
progress_acceleration = zeros(1, max_samples);
progress_jerk = zeros(1, max_samples);
force_local = zeros(2, max_samples);
force_rate = zeros(2, max_samples);
torque_residual = zeros(2, max_samples);
acceleration = zeros(2, max_samples);
sigma_min = zeros(1, max_samples);
condition_number = zeros(1, max_samples);
force_saturated = false(1, max_samples);
slew_saturated = false(1, max_samples);
soft_limit_active = false(1, max_samples);
rom_violation = false(1, max_samples);
current_hold_feasible = false(1, max_samples);
controller_feasible = false(1, max_samples);
support_residual = zeros(1, max_samples);
phase = strings(1, max_samples);
status = strings(1, max_samples);

last_index = max_samples;
for index = 1:max_samples
    q = x(1:2, index);
    dq = x(3:4, index);
    [manager, reference, manager_details] = ...
        hybrid_tube_v1_manager_step(manager, plan, q, dq, p, config);
    [u, controller] = single_arm_v2_equilibrium_controller( ...
        q, dq, reference.q, reference.dq, reference.ddq, ...
        u_previous, p, config);
    [~, dynamics] = single_arm_v2_endpoint_dynamics(x(:, index), u, p);

    q_reference(:, index) = reference.q;
    dq_reference(:, index) = reference.dq;
    ddq_reference(:, index) = reference.ddq;
    q_nominal(:, index) = reference.sample.nominal_q;
    tube(:, index) = reference.sample.tube_rad;
    progress(index) = manager.s;
    progress_rate(index) = manager.s_dot;
    progress_acceleration(index) = manager.s_ddot;
    progress_jerk(index) = manager_details.jerk;
    force_local(:, index) = u;
    force_rate(:, index) = controller.force_rate;
    torque_residual(:, index) = controller.torque_residual;
    acceleration(:, index) = dynamics.ddq;
    sigma_min(index) = controller.mapping.sigma_min;
    condition_number(index) = controller.mapping.condition_number;
    force_saturated(index) = controller.force_saturated;
    slew_saturated(index) = controller.slew_saturated;
    soft_limit_active(index) = any(dynamics.passive.soft.active);
    rom_violation(index) = any(q < p.q_min-config.rom_tolerance_rad | ...
        q > p.q_max+config.rom_tolerance_rad);
    current_hold_feasible(index) = manager_details.current_hold_feasible;
    controller_feasible(index) = controller.full_constraint_feasible && ...
        norm(controller.torque_residual) <= config.residual_tolerance_Nm;
    support_residual(index) = manager_details.current_support_residual_Nm;
    phase(index) = reference.sample.phase;
    status(index) = manager.status;

    if manager.status ~= "RUNNING"
        last_index = index;
        break;
    end
    if index < max_samples
        held_force = u;
        rhs = @(~, state) single_arm_v2_endpoint_dynamics( ...
            state, held_force, p);
        x(:, index+1) = human_two_link_v2_rk4_step( ...
            rhs, t(index), x(:, index), config.dt);
        u_previous = u;
    end
end

if manager.status == "RUNNING"
    if current_hold_feasible(last_index)
        manager.status = "TRANSFER_REQUIRED";
    else
        manager.status = "INFEASIBLE";
    end
    status(last_index) = manager.status;
end

result.t = t(1:last_index);
result.x = x(:, 1:last_index);
result.q_reference = q_reference(:, 1:last_index);
result.dq_reference = dq_reference(:, 1:last_index);
result.ddq_reference = ddq_reference(:, 1:last_index);
result.q_nominal = q_nominal(:, 1:last_index);
result.tube = tube(:, 1:last_index);
result.progress = progress(1:last_index);
result.progress_rate = progress_rate(1:last_index);
result.progress_acceleration = progress_acceleration(1:last_index);
result.progress_jerk = progress_jerk(1:last_index);
result.force_local = force_local(:, 1:last_index);
result.force_rate = force_rate(:, 1:last_index);
result.torque_residual = torque_residual(:, 1:last_index);
result.acceleration = acceleration(:, 1:last_index);
result.sigma_min = sigma_min(1:last_index);
result.condition_number = condition_number(1:last_index);
result.force_saturated = force_saturated(1:last_index);
result.slew_saturated = slew_saturated(1:last_index);
result.soft_limit_active = soft_limit_active(1:last_index);
result.rom_violation = rom_violation(1:last_index);
result.current_hold_feasible = current_hold_feasible(1:last_index);
result.controller_feasible = controller_feasible(1:last_index);
result.support_residual = support_residual(1:last_index);
result.phase = phase(1:last_index);
result.status = status(1:last_index);

tracking_error = result.x(1:2, :)-result.q_reference;
task_error = result.x(1:2, :)-result.q_nominal;
tube_excess = max(abs(task_error)-result.tube, 0);
force_norm = vecnorm(result.force_local, 2, 1);
residual_norm = vecnorm(result.torque_residual, 2, 1);
jerk = zeros(size(result.acceleration));
if last_index > 1
    jerk(:, 2:end) = diff(result.acceleration, 1, 2)/config.dt;
end
metrics = struct();
metrics.terminal_state = manager.status;
metrics.completion_time_s = result.t(end);
metrics.final_progress = result.progress(end);
metrics.rmse_tracking_deg = rad2deg(sqrt(mean(tracking_error.^2, 2)));
metrics.max_task_deviation_deg = rad2deg(max(abs(task_error), [], 2));
metrics.max_tube_excess_deg = rad2deg(max(tube_excess, [], 2));
metrics.time_outside_tube_s = config.dt*sum(any(tube_excess > ...
    deg2rad(1e-6), 1));
metrics.peak_force_component_N = max(abs(result.force_local), [], 2);
metrics.peak_force_norm_N = max(force_norm);
metrics.force_rms_N = sqrt(mean(force_norm.^2));
metrics.peak_force_rate_component_N_s = max(abs(result.force_rate), [], 2);
metrics.torque_residual_rms_Nm = sqrt(mean(residual_norm.^2));
metrics.torque_residual_max_Nm = max(residual_norm);
metrics.force_saturation_fraction = mean(result.force_saturated);
metrics.slew_saturation_fraction = mean(result.slew_saturated);
metrics.min_sigma = min(result.sigma_min);
metrics.max_condition = max(result.condition_number);
metrics.min_rom_margin_rad = min(min(result.x(1:2, :)-p.q_min, ...
    p.q_max-result.x(1:2, :)), [], 2);
metrics.max_velocity_rad_s = max(abs(result.x(3:4, :)), [], 2);
metrics.max_acceleration_rad_s2 = max(abs(result.acceleration), [], 2);
metrics.max_jerk_rad_s3 = max(abs(jerk), [], 2);
metrics.soft_limit_activation_count = sum(result.soft_limit_active);
metrics.rom_violation_count = sum(result.rom_violation);
metrics.nonfinite_count = sum(~isfinite([result.x(:); ...
    result.force_local(:); result.acceleration(:); result.sigma_min(:)]));
metrics.terminal_deviation_deg = rad2deg(task_error(:, end));
metrics.progress_slowdown_duration_s = config.dt*sum( ...
    result.progress_rate < config.nominal_progress_rate-1e-6);
metrics.pause_duration_s = config.dt*sum(result.progress_rate <= 1e-6);
metrics.force_aware_deviation_duration_s = config.dt*sum( ...
    any(abs(result.q_reference-result.q_nominal) > deg2rad(0.05), 1));
metrics.controller_feasible_fraction = mean(result.controller_feasible);
metrics.initial_hold_feasible = initial_hold_feasible;
metrics.initial_required_force_N = initial_hold.force_local;
metrics.initial_required_force_norm_N = initial_hold.force_norm;
result.jerk = jerk;
result.tracking_error = tracking_error;
result.task_error = task_error;
result.tube_excess = tube_excess;
result.plan = plan;
result.config = config;
result.parameters = p;
result.metrics = metrics;
end
