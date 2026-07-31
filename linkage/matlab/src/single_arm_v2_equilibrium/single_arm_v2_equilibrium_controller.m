function [u, details] = single_arm_v2_equilibrium_controller( ...
        q, dq, q_ref, dq_ref, ddq_ref, u_prev, p, config)
%SINGLE_ARM_V2_EQUILIBRIUM_CONTROLLER Equilibrium-preserving endpoint QP.

q = q(:); dq = dq(:); q_ref = q_ref(:); dq_ref = dq_ref(:);
ddq_ref = ddq_ref(:); u_prev = u_prev(:);
if any(~isfinite([q; dq; q_ref; dq_ref; ddq_ref; u_prev])) || ...
        any([numel(q), numel(dq), numel(q_ref), numel(dq_ref), ...
        numel(ddq_ref), numel(u_prev)] ~= 2)
    error('SingleArmV2:InvalidControllerInput', ...
        'All controller inputs must be finite 2-vectors.');
end

mapping = single_arm_v2_force_map(q, dq, p);
[M, h, ~, G] = human_two_link_v2_dynamics_terms(q, dq, p);
[passive_dynamic, passive_details] = ...
    human_two_link_v2_passive_torque(q, dq, p);
passive_static = human_two_link_v2_passive_torque(q, zeros(2, 1), p);
e = q-q_ref;
de = dq-dq_ref;
ddq_feedback = -config.Kp*e-config.Kd*de;
ddq_cmd = ddq_ref+ddq_feedback;
tau_static = G+passive_static;
tau_dynamic = M*ddq_ref+h+(passive_dynamic-passive_static);
tau_feedback = M*ddq_feedback;
tau_des = tau_static+tau_dynamic+tau_feedback;
[u_des, linear_solve] = single_arm_v2_stable_force_solve( ...
    mapping.A, tau_des, config.svd_relative_tolerance);

slew_step = config.du_max(:)*config.dt;
lower = max(config.u_min(:), u_prev-slew_step);
upper = min(config.u_max(:), u_prev+slew_step);
B_tau = config.W_tau*mapping.A/config.tau_scale_Nm;
d_tau = config.W_tau*tau_des/config.tau_scale_Nm;
ref_weight = config.lambda_ref/config.F_scale_N^2;
du_denominator = config.du_scale_N_s*config.dt;
du_weight = config.lambda_du/du_denominator^2;
H = B_tau'*B_tau+(ref_weight+du_weight)*eye(2);
f = -B_tau'*d_tau-ref_weight*u_des-du_weight*u_prev;
[u, solver] = single_arm_v2_solve_box_qp(H, f, lower, upper);

tau_contact = mapping.A*u;
torque_residual = tau_contact-tau_des;
tol = config.bound_tolerance_N;
force_active = abs(u-config.u_min(:)) <= tol | ...
    abs(u-config.u_max(:)) <= tol;
slew_lower_active = lower > config.u_min(:)+tol & abs(u-lower) <= tol;
slew_upper_active = upper < config.u_max(:)-tol & abs(u-upper) <= tol;
force_bound_limited = any(u_des < config.u_min(:)-tol | ...
    u_des > config.u_max(:)+tol);
slew_bound_limited = any(u_des < lower-tol | u_des > upper+tol) && ...
    ~force_bound_limited;
conditioning_limited = mapping.condition_number > ...
    config.conditioning_threshold || ...
    mapping.sigma_min < config.sigma_min_threshold || ...
    linear_solve.rank < 2;
residual_large = norm(torque_residual) > config.residual_tolerance_Nm;
numerical_limited = residual_large && ~force_bound_limited && ...
    ~slew_bound_limited && ~conditioning_limited;

details = struct();
details.error = e;
details.velocity_error = de;
details.ddq_cmd = ddq_cmd;
details.ddq_feedback = ddq_feedback;
details.M = M;
details.h = h;
details.G = G;
details.passive = passive_details;
details.mapping = mapping;
details.A = mapping.A;
details.tau_static = tau_static;
details.tau_dynamic = tau_dynamic;
details.tau_feedback = tau_feedback;
details.tau_des = tau_des;
details.u_des = u_des;
details.u = u;
details.world_force = mapping.rotation*u;
details.tau_contact = tau_contact;
details.torque_residual = torque_residual;
details.force_rate = (u-u_prev)/config.dt;
details.effective_lower = lower;
details.effective_upper = upper;
details.force_saturated = any(force_active);
details.slew_saturated = any(slew_lower_active | slew_upper_active);
details.force_bound_limited = force_bound_limited;
details.slew_bound_limited = slew_bound_limited;
details.conditioning_limited = conditioning_limited;
details.numerical_limited = numerical_limited;
details.force_feasible = ~force_bound_limited;
details.full_constraint_feasible = all(u_des >= lower-tol & u_des <= upper+tol);
details.linear_solve = linear_solve;
details.solver = solver;
end
