function preflight = single_arm_v2_reference_preflight(p, config)
%SINGLE_ARM_V2_REFERENCE_PREFLIGHT Reference force/conditioning feasibility.

t = 0:config.dt:config.t_final;
n = numel(t);
q = zeros(2, n);
dq = zeros(2, n);
ddq = zeros(2, n);
tau_static = zeros(2, n);
tau_ff = zeros(2, n);
tau_dynamic_increment = zeros(2, n);
u_static = zeros(2, n);
u_ff = zeros(2, n);
force_residual_static = zeros(1, n);
force_residual_ff = zeros(1, n);
bounded_residual = zeros(1, n);
sigma_min = zeros(1, n);
condition_number = zeros(1, n);
det_A = zeros(1, n);
phase = strings(1, n);
engineering_limit = config.engineering_force_limit_N(:);

for index = 1:n
    [q(:, index), dq(:, index), ddq(:, index), phase(index)] = ...
        human_two_link_v2_reference(t(index), config.trajectory_name);
    mapping = single_arm_v2_force_map(q(:, index), dq(:, index), p);
    [M, h, ~, G] = human_two_link_v2_dynamics_terms( ...
        q(:, index), dq(:, index), p);
    passive_static = human_two_link_v2_passive_torque( ...
        q(:, index), zeros(2, 1), p);
    passive_dynamic = human_two_link_v2_passive_torque( ...
        q(:, index), dq(:, index), p);
    tau_static(:, index) = G+passive_static;
    tau_ff(:, index) = M*ddq(:, index)+h+G+passive_dynamic;
    tau_dynamic_increment(:, index) = ...
        tau_ff(:, index)-tau_static(:, index);
    [u_static(:, index), static_solve] = ...
        single_arm_v2_stable_force_solve(mapping.A, ...
        tau_static(:, index), config.svd_relative_tolerance);
    [u_ff(:, index), ff_solve] = single_arm_v2_stable_force_solve( ...
        mapping.A, tau_ff(:, index), config.svd_relative_tolerance);
    force_residual_static(index) = static_solve.residual_norm;
    force_residual_ff(index) = ff_solve.residual_norm;
    H = mapping.A'*mapping.A+1e-14*eye(2);
    f = -mapping.A'*tau_ff(:, index);
    bounded_u = single_arm_v2_solve_box_qp(H, f, ...
        -engineering_limit, engineering_limit);
    bounded_residual(index) = norm(mapping.A*bounded_u-tau_ff(:, index));
    sigma_min(index) = mapping.sigma_min;
    condition_number(index) = mapping.condition_number;
    det_A(index) = mapping.det_A;
end

force_rate = zeros(2, n);
force_rate(:, 2:end) = diff(u_ff, 1, 2)/config.dt;
force_rate(:, 1) = force_rate(:, 2);
force_norm = vecnorm(u_ff, 2, 1);
force_rate_norm = vecnorm(force_rate, 2, 1);
engineering_feasible = all(abs(u_ff) <= engineering_limit+1e-10, 1);

[max_force_norm, force_peak_index] = max(force_norm);
[max_force_rate_norm, rate_peak_index] = max(force_rate_norm);
[max_condition, condition_peak_index] = max(condition_number);
[min_sigma, sigma_min_index] = min(sigma_min);

preflight = struct();
preflight.t = t;
preflight.q_ref = q;
preflight.dq_ref = dq;
preflight.ddq_ref = ddq;
preflight.phase = phase;
preflight.tau_static = tau_static;
preflight.tau_ff = tau_ff;
preflight.tau_dynamic_increment = tau_dynamic_increment;
preflight.u_static = u_static;
preflight.u_ff = u_ff;
preflight.force_rate = force_rate;
preflight.force_norm = force_norm;
preflight.force_rate_norm = force_rate_norm;
preflight.static_residual_Nm = force_residual_static;
preflight.ff_residual_Nm = force_residual_ff;
preflight.engineering_bounded_residual_Nm = bounded_residual;
preflight.engineering_feasible = engineering_feasible;
preflight.sigma_min = sigma_min;
preflight.condition_number = condition_number;
preflight.det_A = det_A;
preflight.metrics = struct();
preflight.metrics.max_abs_Ft_N = max(abs(u_ff(1, :)));
preflight.metrics.max_abs_Fn_N = max(abs(u_ff(2, :)));
preflight.metrics.max_force_norm_N = max_force_norm;
preflight.metrics.max_force_rate_component_N_s = ...
    max(abs(force_rate), [], 2);
preflight.metrics.max_force_rate_norm_N_s = max_force_rate_norm;
preflight.metrics.max_static_force_norm_N = ...
    max(vecnorm(u_static, 2, 1));
preflight.metrics.max_dynamic_increment_torque_Nm = ...
    max(vecnorm(tau_dynamic_increment, 2, 1));
preflight.metrics.max_static_torque_Nm = ...
    max(vecnorm(tau_static, 2, 1));
preflight.metrics.max_static_residual_Nm = max(force_residual_static);
preflight.metrics.max_ff_residual_Nm = max(force_residual_ff);
preflight.metrics.engineering_feasible_fraction = ...
    mean(engineering_feasible);
preflight.metrics.engineering_residual_rms_Nm = ...
    sqrt(mean(bounded_residual.^2));
preflight.metrics.engineering_residual_max_Nm = max(bounded_residual);
preflight.metrics.min_sigma = min_sigma;
preflight.metrics.max_condition = max_condition;
preflight.metrics.min_abs_det_A = min(abs(det_A));
preflight.metrics.force_peak_time_s = t(force_peak_index);
preflight.metrics.force_peak_phase = phase(force_peak_index);
preflight.metrics.rate_peak_time_s = t(rate_peak_index);
preflight.metrics.rate_peak_phase = phase(rate_peak_index);
preflight.metrics.condition_peak_time_s = t(condition_peak_index);
preflight.metrics.condition_peak_phase = phase(condition_peak_index);
preflight.metrics.sigma_min_time_s = t(sigma_min_index);
preflight.metrics.sigma_min_phase = phase(sigma_min_index);
end
