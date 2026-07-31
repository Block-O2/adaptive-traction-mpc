function [u, details] = ideal_endpoint_force_controller( ...
        q, dq, q_ref, dq_ref, ddq_ref, u_prev, p, config)
%IDEAL_ENDPOINT_FORCE_CONTROLLER Constrained local shank-cuff force command.

q = q(:);
dq = dq(:);
q_ref = q_ref(:);
dq_ref = dq_ref(:);
ddq_ref = ddq_ref(:);
u_prev = u_prev(:);
vectors = [q; dq; q_ref; dq_ref; ddq_ref; u_prev];
if numel(q) ~= 2 || numel(dq) ~= 2 || numel(q_ref) ~= 2 || ...
        numel(dq_ref) ~= 2 || numel(ddq_ref) ~= 2 || ...
        numel(u_prev) ~= 2 || any(~isfinite(vectors))
    error('IdealEndpointForce:InvalidControllerInput', ...
        'Controller inputs must be finite 2-vectors.');
end

required = {'dt', 'accel_Kp', 'accel_Kd', 'W_tau', ...
    'lambda_u', 'lambda_du', 'u_min', 'u_max', 'du_max', ...
    'saturation_tolerance'};
for field_index = 1:numel(required)
    if ~isfield(config, required{field_index})
        error('IdealEndpointForce:MissingControllerConfig', ...
            'Missing controller configuration field: %s', ...
            required{field_index});
    end
end
if ~isequal(size(config.accel_Kp), [2, 2]) || ...
        ~isequal(size(config.accel_Kd), [2, 2]) || ...
        ~isequal(size(config.W_tau), [2, 2]) || ...
        ~isscalar(config.lambda_u) || config.lambda_u < 0 || ...
        ~isscalar(config.lambda_du) || config.lambda_du < 0 || ...
        ~isscalar(config.dt) || config.dt <= 0
    error('IdealEndpointForce:InvalidControllerConfig', ...
        'Controller matrices and nonnegative regularizers are invalid.');
end

u_min = config.u_min(:);
u_max = config.u_max(:);
du_max = config.du_max(:);
if numel(u_min) ~= 2 || numel(u_max) ~= 2 || ...
        numel(du_max) ~= 2 || any(~isfinite([u_min; u_max; du_max])) || ...
        any(u_min > u_max) || any(du_max <= 0) || ...
        any(u_prev < u_min) || any(u_prev > u_max)
    error('IdealEndpointForce:InvalidForceBounds', ...
        'Force/slew bounds and previous force must be finite and feasible.');
end

mapping = shank_endpoint_force_map(q, dq, p);
A = mapping.generalized_force_map;
[M, h, ~, G] = dynamics_terms(q, dq, p);
position_error = q - q_ref;
velocity_error = dq - dq_ref;
ddq_cmd = ddq_ref - config.accel_Kp*position_error - ...
    config.accel_Kd*velocity_error;
tau_req = M*ddq_cmd + h + G + p.B*dq;

weighted_map = config.W_tau * A;
weighted_torque = config.W_tau * tau_req;
H = weighted_map'*weighted_map + ...
    (config.lambda_u + config.lambda_du)*eye(2);
f = -weighted_map'*weighted_torque - config.lambda_du*u_prev;

slew = du_max * config.dt;
lower = max(u_min, u_prev - slew);
upper = min(u_max, u_prev + slew);
[u, solver] = solve_box_quadratic_2d(H, f, lower, upper);

world_force = mapping.rotation * u;
tau_contact = A * u;
torque_residual = tau_contact - tau_req;
tolerance = config.saturation_tolerance;
hard_saturated = any(abs(u-u_min) <= tolerance | ...
    abs(u-u_max) <= tolerance);
slew_lower_active = lower > u_min + tolerance & ...
    abs(u-lower) <= tolerance;
slew_upper_active = upper < u_max - tolerance & ...
    abs(u-upper) <= tolerance;

details = struct();
details.error = position_error;
details.velocity_error = velocity_error;
details.ddq_cmd = ddq_cmd;
details.M = M;
details.h = h;
details.G = G;
details.mapping = mapping;
details.A = A;
details.tau_req = tau_req;
details.world_force = world_force;
details.tau_contact = tau_contact;
details.torque_residual = torque_residual;
details.condition_number = cond(A);
details.effective_lower = lower;
details.effective_upper = upper;
details.hard_saturated = hard_saturated;
details.slew_saturated = any(slew_lower_active | slew_upper_active);
details.force_rate = (u-u_prev) / config.dt;
details.solver = solver;
end
