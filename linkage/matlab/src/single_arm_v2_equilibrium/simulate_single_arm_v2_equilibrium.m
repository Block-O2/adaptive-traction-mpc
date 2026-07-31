function result = simulate_single_arm_v2_equilibrium(config, p)
%SIMULATE_SINGLE_ARM_V2_EQUILIBRIUM Endpoint-only V2 closed-loop rollout.

t = 0:config.dt:config.t_final;
n = numel(t);
x = zeros(4, n);
[q0, dq0, ddq0] = human_two_link_v2_reference( ...
    t(1), config.trajectory_name);
x(:, 1) = [q0; dq0];

q_ref = zeros(2, n); dq_ref = zeros(2, n); ddq_ref = zeros(2, n);
phase = strings(1, n);
force_local = zeros(2, n); force_desired = zeros(2, n);
force_world = zeros(2, n); force_rate = zeros(2, n);
tau_contact = zeros(2, n); tau_des = zeros(2, n);
tau_static = zeros(2, n); tau_dynamic = zeros(2, n);
tau_feedback = zeros(2, n); torque_residual = zeros(2, n);
acceleration = zeros(2, n);
sigma_min = zeros(1, n); condition_number = zeros(1, n);
det_A = zeros(1, n); rom_margin = zeros(2, n);
force_saturated = false(1, n); slew_saturated = false(1, n);
force_bound_limited = false(1, n); slew_bound_limited = false(1, n);
conditioning_limited = false(1, n); numerical_limited = false(1, n);
force_feasible = false(1, n); full_constraint_feasible = false(1, n);
soft_limit_active = false(1, n); rom_violation = false(1, n);

initial_mapping = single_arm_v2_force_map(q0, dq0, p);
[M0, h0, ~, G0] = human_two_link_v2_dynamics_terms(q0, dq0, p);
passive0 = human_two_link_v2_passive_torque(q0, dq0, p);
tau0 = M0*ddq0+h0+G0+passive0;
[u0_des, ~] = single_arm_v2_stable_force_solve( ...
    initial_mapping.A, tau0, config.svd_relative_tolerance);
H0 = initial_mapping.A'*initial_mapping.A+ ...
    (config.lambda_ref/config.F_scale_N^2)*eye(2);
f0 = -initial_mapping.A'*tau0- ...
    (config.lambda_ref/config.F_scale_N^2)*u0_des;
[u_prev, initialization_solver] = single_arm_v2_solve_box_qp( ...
    H0, f0, config.u_min(:), config.u_max(:));
initial_force = u_prev;

for index = 1:n
    [q_ref(:, index), dq_ref(:, index), ddq_ref(:, index), ...
        phase(index)] = human_two_link_v2_reference( ...
        t(index), config.trajectory_name);
    q = x(1:2, index);
    dq = x(3:4, index);
    [u, controller] = single_arm_v2_equilibrium_controller( ...
        q, dq, q_ref(:, index), dq_ref(:, index), ...
        ddq_ref(:, index), u_prev, p, config);
    [~, dynamics] = single_arm_v2_endpoint_dynamics(x(:, index), u, p);

    force_local(:, index) = u;
    force_desired(:, index) = controller.u_des;
    force_world(:, index) = dynamics.force_world;
    force_rate(:, index) = controller.force_rate;
    tau_contact(:, index) = dynamics.tau_contact;
    tau_des(:, index) = controller.tau_des;
    tau_static(:, index) = controller.tau_static;
    tau_dynamic(:, index) = controller.tau_dynamic;
    tau_feedback(:, index) = controller.tau_feedback;
    torque_residual(:, index) = controller.torque_residual;
    acceleration(:, index) = dynamics.ddq;
    sigma_min(index) = controller.mapping.sigma_min;
    condition_number(index) = controller.mapping.condition_number;
    det_A(index) = controller.mapping.det_A;
    rom_margin(:, index) = min(q-p.q_min, p.q_max-q);
    force_saturated(index) = controller.force_saturated;
    slew_saturated(index) = controller.slew_saturated;
    force_bound_limited(index) = controller.force_bound_limited;
    slew_bound_limited(index) = controller.slew_bound_limited;
    conditioning_limited(index) = controller.conditioning_limited;
    numerical_limited(index) = controller.numerical_limited;
    force_feasible(index) = controller.force_feasible;
    full_constraint_feasible(index) = controller.full_constraint_feasible;
    soft_limit_active(index) = any(dynamics.passive.soft.active);
    rom_violation(index) = any(q < p.q_min-config.rom_tolerance_rad | ...
        q > p.q_max+config.rom_tolerance_rad);

    if index < n
        held_force = u;
        rhs = @(~, state) single_arm_v2_endpoint_dynamics( ...
            state, held_force, p);
        x(:, index+1) = human_two_link_v2_rk4_step( ...
            rhs, t(index), x(:, index), config.dt);
        u_prev = u;
    end
end

tracking_error = x(1:2, :)-q_ref;
jerk = zeros(2, n);
jerk(:, 2:end) = diff(acceleration, 1, 2)/config.dt;
checked = [x(:); force_local(:); force_world(:); force_rate(:); ...
    tau_contact(:); tau_des(:); torque_residual(:); acceleration(:); ...
    jerk(:); sigma_min(:); condition_number(:)];
nonfinite_count = sum(~isfinite(checked));
residual_norm = vecnorm(torque_residual, 2, 1);
force_norm = vecnorm(force_local, 2, 1);
force_rate_norm = vecnorm(force_rate, 2, 1);
failure_event = force_bound_limited | slew_bound_limited | ...
    conditioning_limited | numerical_limited | rom_violation | ...
    soft_limit_active;
first_failure_index = find(failure_event, 1, 'first');
if isempty(first_failure_index)
    first_failure_time = NaN;
    first_failure_phase = "none";
else
    first_failure_time = t(first_failure_index);
    first_failure_phase = phase(first_failure_index);
end

metrics = struct();
metrics.completed = nonfinite_count == 0 && abs(t(end)-config.t_final) < eps;
metrics.nonfinite_count = nonfinite_count;
metrics.rmse_rad = sqrt(mean(tracking_error.^2, 2));
metrics.max_abs_error_rad = max(abs(tracking_error), [], 2);
metrics.max_force_component_N = max(abs(force_local), [], 2);
metrics.max_force_norm_N = max(force_norm);
metrics.max_force_rate_component_N_s = max(abs(force_rate), [], 2);
metrics.max_force_rate_norm_N_s = max(force_rate_norm);
metrics.torque_residual_rms_Nm = sqrt(mean(residual_norm.^2));
metrics.torque_residual_max_Nm = max(residual_norm);
metrics.force_feasible_fraction = mean(force_feasible);
metrics.full_constraint_feasible_fraction = mean(full_constraint_feasible);
metrics.force_saturation_fraction = mean(force_saturated);
metrics.slew_saturation_fraction = mean(slew_saturated);
metrics.force_bound_limited_fraction = mean(force_bound_limited);
metrics.slew_bound_limited_fraction = mean(slew_bound_limited);
metrics.conditioning_limited_fraction = mean(conditioning_limited);
metrics.numerical_limited_fraction = mean(numerical_limited);
metrics.rom_violation_count = sum(rom_violation);
metrics.soft_limit_activation_count = sum(soft_limit_active);
metrics.min_rom_margin_rad = min(rom_margin, [], 2);
metrics.min_sigma = min(sigma_min);
metrics.max_condition = max(condition_number);
metrics.max_abs_acceleration_rad_s2 = max(abs(acceleration), [], 2);
metrics.max_abs_jerk_rad_s3 = max(abs(jerk), [], 2);
metrics.first_failure_time_s = first_failure_time;
metrics.first_failure_phase = first_failure_phase;
metrics.initial_force_N = initial_force;
metrics.initial_force_rate_N_s = force_rate(:, 1);

result = struct();
result.config = config;
result.parameters = p;
result.t = t;
result.state = x;
result.q_ref = q_ref;
result.dq_ref = dq_ref;
result.ddq_ref = ddq_ref;
result.phase = phase;
result.tracking_error = tracking_error;
result.force_local = force_local;
result.force_desired = force_desired;
result.force_world = force_world;
result.force_rate = force_rate;
result.tau_contact = tau_contact;
result.tau_des = tau_des;
result.tau_static = tau_static;
result.tau_dynamic = tau_dynamic;
result.tau_feedback = tau_feedback;
result.torque_residual = torque_residual;
result.acceleration = acceleration;
result.jerk = jerk;
result.sigma_min = sigma_min;
result.condition_number = condition_number;
result.det_A = det_A;
result.rom_margin = rom_margin;
result.force_saturated = force_saturated;
result.slew_saturated = slew_saturated;
result.force_bound_limited = force_bound_limited;
result.slew_bound_limited = slew_bound_limited;
result.conditioning_limited = conditioning_limited;
result.numerical_limited = numerical_limited;
result.force_feasible = force_feasible;
result.full_constraint_feasible = full_constraint_feasible;
result.soft_limit_active = soft_limit_active;
result.rom_violation = rom_violation;
result.initialization_solver = initialization_solver;
result.metrics = metrics;
end
