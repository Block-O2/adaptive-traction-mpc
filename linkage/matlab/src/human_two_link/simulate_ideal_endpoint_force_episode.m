function result = simulate_ideal_endpoint_force_episode( ...
        config, p, actuator_mode)
%SIMULATE_IDEAL_ENDPOINT_FORCE_EPISODE Deterministic endpoint/oracle episode.

validate_parameters(p);
actuator_mode = string(actuator_mode);
if ~any(actuator_mode == ["endpoint_force", "oracle_joint_torque"])
    error('IdealEndpointForce:UnknownActuatorMode', ...
        'Unknown actuator mode: %s', actuator_mode);
end
required = {'trajectory_name', 'dt', 't_final', 'accel_Kp', ...
    'accel_Kd', 'W_tau', 'lambda_u', 'lambda_du', 'u_min', ...
    'u_max', 'du_max', 'oracle_Kp', 'oracle_Kd', ...
    'limit_tolerance', 'saturation_tolerance'};
for field_index = 1:numel(required)
    if ~isfield(config, required{field_index})
        error('IdealEndpointForce:MissingSimulationConfig', ...
            'Missing simulation configuration field: %s', ...
            required{field_index});
    end
end

t = 0:config.dt:config.t_final;
sample_count = numel(t);
x = zeros(4, sample_count);
[q0_ref, dq0_ref, ddq0_ref] = rehabilitation_reference_trajectory( ...
    t(1), config.trajectory_name);
x(:, 1) = [q0_ref; dq0_ref];

q_ref_log = zeros(2, sample_count);
dq_ref_log = zeros(2, sample_count);
ddq_ref_log = zeros(2, sample_count);
tau_joint_log = zeros(2, sample_count);
tau_contact_log = zeros(2, sample_count);
tau_required_log = nan(2, sample_count);
torque_residual_log = nan(2, sample_count);
force_local_log = nan(2, sample_count);
force_world_log = nan(2, sample_count);
force_rate_log = nan(2, sample_count);
acceleration_log = zeros(2, sample_count);
condition_log = zeros(1, sample_count);
hard_saturation_log = false(1, sample_count);
slew_saturation_log = false(1, sample_count);
path_error_log = nan(1, sample_count);
tracking_error_norm_log = zeros(1, sample_count);
u_prev = zeros(2, 1);
initial_force_local = nan(2, 1);
if actuator_mode == "endpoint_force"
    initialization_config = config;
    initialization_config.lambda_du = 0;
    initialization_config.du_max = ...
        (config.u_max(:)-config.u_min(:)) / config.dt;
    [initial_force_local, ~] = ideal_endpoint_force_controller( ...
        x(1:2, 1), x(3:4, 1), q0_ref, dq0_ref, ddq0_ref, ...
        zeros(2, 1), p, initialization_config);
    u_prev = initial_force_local;
end

for sample_index = 1:sample_count
    current_time = t(sample_index);
    [q_ref, dq_ref, ddq_ref, reference_metadata] = ...
        rehabilitation_reference_trajectory( ...
        current_time, config.trajectory_name);
    q = x(1:2, sample_index);
    dq = x(3:4, sample_index);
    mapping = shank_endpoint_force_map(q, dq, p);
    condition_log(sample_index) = ...
        cond(mapping.generalized_force_map);

    if actuator_mode == "endpoint_force"
        [u, controller] = ideal_endpoint_force_controller( ...
            q, dq, q_ref, dq_ref, ddq_ref, u_prev, p, config);
        [~, dynamics] = endpoint_force_dynamics( ...
            x(:, sample_index), u, p);

        force_local_log(:, sample_index) = u;
        force_world_log(:, sample_index) = dynamics.world_force;
        force_rate_log(:, sample_index) = controller.force_rate;
        tau_contact_log(:, sample_index) = dynamics.tau_contact;
        tau_required_log(:, sample_index) = controller.tau_req;
        torque_residual_log(:, sample_index) = ...
            controller.torque_residual;
        acceleration_log(:, sample_index) = dynamics.ddq;
        hard_saturation_log(sample_index) = ...
            controller.hard_saturated;
        slew_saturation_log(sample_index) = ...
            controller.slew_saturated;
    else
        [tau_joint, ~] = computed_torque_pd( ...
            q, dq, q_ref, dq_ref, ddq_ref, p, ...
            config.oracle_Kp, config.oracle_Kd);
        [~, dynamics] = continuous_dynamics( ...
            x(:, sample_index), tau_joint, zeros(2, 1), p, false);

        tau_joint_log(:, sample_index) = tau_joint;
        acceleration_log(:, sample_index) = dynamics.ddq;
    end

    q_ref_log(:, sample_index) = q_ref;
    dq_ref_log(:, sample_index) = dq_ref;
    ddq_ref_log(:, sample_index) = ddq_ref;
    position_error = q - q_ref;
    tracking_error_norm_log(sample_index) = norm(position_error);
    if config.trajectory_name == "coordinated_path"
        slope = reference_metadata.path_slope;
        path_error_log(sample_index) = ( ...
            q(2) - reference_metadata.path_origin(2) - ...
            slope*(q(1)-reference_metadata.path_origin(1))) / ...
            sqrt(1+slope^2);
    end

    if sample_index < sample_count
        if actuator_mode == "endpoint_force"
            held_force = force_local_log(:, sample_index);
            rhs = @(~, state) endpoint_force_dynamics( ...
                state, held_force, p);
            u_prev = held_force;
        else
            rhs = @(time, state) oracle_closed_loop_rhs( ...
                time, state, config, p);
        end
        x(:, sample_index + 1) = rk4_step( ...
            rhs, current_time, x(:, sample_index), config.dt);
    end
end

error_log = x(1:2, :) - q_ref_log;
jerk_log = zeros(size(acceleration_log));
jerk_log(:, 2:end) = diff(acceleration_log, 1, 2) / config.dt;
joint_limit_violation = any( ...
    x(1:2, :) < p.q_min - config.limit_tolerance | ...
    x(1:2, :) > p.q_max + config.limit_tolerance, 1);
velocity_limit_violation = any( ...
    abs(x(3:4, :)) > p.dq_max + config.limit_tolerance, 1);

if actuator_mode == "endpoint_force"
    checked_signals = [x(:); force_local_log(:); ...
        force_world_log(:); force_rate_log(:); ...
        tau_contact_log(:); tau_required_log(:); ...
        torque_residual_log(:); acceleration_log(:); jerk_log(:)];
else
    checked_signals = [x(:); tau_joint_log(:); ...
        acceleration_log(:); jerk_log(:)];
end
signal_nonfinite_count = sum(~isfinite(checked_signals));
condition_nonfinite_count = sum(~isfinite(condition_log));

metrics = struct();
metrics.completed = signal_nonfinite_count == 0;
metrics.initial_alignment_error_rad = norm(x(1:2, 1)-q_ref_log(:, 1));
metrics.rmse_rad = sqrt(mean(error_log.^2, 2));
metrics.max_abs_error_rad = max(abs(error_log), [], 2);
metrics.max_abs_velocity_rad_s = max(abs(x(3:4, :)), [], 2);
metrics.max_abs_acceleration_rad_s2 = ...
    max(abs(acceleration_log), [], 2);
metrics.max_abs_jerk_rad_s3 = max(abs(jerk_log), [], 2);
metrics.joint_limit_violation_count = sum(joint_limit_violation);
metrics.velocity_limit_violation_count = sum(velocity_limit_violation);
metrics.signal_nonfinite_count = signal_nonfinite_count;
metrics.condition_nonfinite_count = condition_nonfinite_count;
metrics.condition_median = finite_percentile(condition_log, 50);
metrics.condition_p95 = finite_percentile(condition_log, 95);
metrics.condition_max = finite_percentile(condition_log, 100);

if config.trajectory_name == "knee_dominant"
    metrics.non_target_hip_excursion_rad = ...
        max(x(1, :)) - min(x(1, :));
else
    metrics.non_target_hip_excursion_rad = NaN;
end
if config.trajectory_name == "coordinated_path"
    metrics.path_rmse_rad = sqrt(mean(path_error_log.^2));
    metrics.path_max_abs_rad = max(abs(path_error_log));
else
    metrics.path_rmse_rad = NaN;
    metrics.path_max_abs_rad = NaN;
end

if actuator_mode == "endpoint_force"
    force_norm = vecnorm(force_local_log, 2, 1);
    force_rate_norm = vecnorm(force_rate_log, 2, 1);
    residual_norm = vecnorm(torque_residual_log, 2, 1);
    metrics.max_abs_Ft_N = max(abs(force_local_log(1, :)));
    metrics.max_abs_Fn_N = max(abs(force_local_log(2, :)));
    metrics.max_force_norm_N = max(force_norm);
    metrics.max_force_rate_N_s = max(force_rate_norm);
    metrics.rms_force_rate_N_s = sqrt(mean(force_rate_norm.^2));
    metrics.hard_saturation_fraction = mean(hard_saturation_log);
    metrics.slew_saturation_fraction = mean(slew_saturation_log);
    metrics.torque_residual_rms_Nm = sqrt(mean(residual_norm.^2));
    metrics.torque_residual_max_Nm = max(residual_norm);
    metrics.max_joint_torque_norm_Nm = 0;
else
    metrics.max_abs_Ft_N = NaN;
    metrics.max_abs_Fn_N = NaN;
    metrics.max_force_norm_N = NaN;
    metrics.max_force_rate_N_s = NaN;
    metrics.rms_force_rate_N_s = NaN;
    metrics.hard_saturation_fraction = NaN;
    metrics.slew_saturation_fraction = NaN;
    metrics.torque_residual_rms_Nm = NaN;
    metrics.torque_residual_max_Nm = NaN;
    metrics.max_joint_torque_norm_Nm = ...
        max(vecnorm(tau_joint_log, 2, 1));
end

result = struct();
result.config = config;
result.parameters = p;
result.actuator_mode = actuator_mode;
result.initial_force_local = initial_force_local;
result.t = t;
result.state = x;
result.q_ref = q_ref_log;
result.dq_ref = dq_ref_log;
result.ddq_ref = ddq_ref_log;
result.tau_joint = tau_joint_log;
result.tau_contact = tau_contact_log;
result.tau_required = tau_required_log;
result.torque_residual = torque_residual_log;
result.force_local = force_local_log;
result.force_world = force_world_log;
result.force_rate = force_rate_log;
result.acceleration = acceleration_log;
result.jerk = jerk_log;
result.condition_number = condition_log;
result.hard_saturation = hard_saturation_log;
result.slew_saturation = slew_saturation_log;
result.path_error = path_error_log;
result.tracking_error_norm = tracking_error_norm_log;
result.metrics = metrics;
end


function xdot = oracle_closed_loop_rhs(t, x, config, p)
[q_ref, dq_ref, ddq_ref] = rehabilitation_reference_trajectory( ...
    t, config.trajectory_name);
tau_joint = computed_torque_pd( ...
    x(1:2), x(3:4), q_ref, dq_ref, ddq_ref, p, ...
    config.oracle_Kp, config.oracle_Kd);
xdot = continuous_dynamics( ...
    x, tau_joint, zeros(2, 1), p, false);
end


function value = finite_percentile(values, percentile)
finite_values = sort(values(isfinite(values)));
if isempty(finite_values)
    value = Inf;
    return;
end
if percentile <= 0
    value = finite_values(1);
elseif percentile >= 100
    value = finite_values(end);
else
    rank = 1 + (numel(finite_values)-1)*percentile/100;
    lower_rank = floor(rank);
    upper_rank = ceil(rank);
    fraction = rank-lower_rank;
    value = (1-fraction)*finite_values(lower_rank) + ...
        fraction*finite_values(upper_rank);
end
end
