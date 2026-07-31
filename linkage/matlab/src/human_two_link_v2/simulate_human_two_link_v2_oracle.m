function result = simulate_human_two_link_v2_oracle(config, p)
%SIMULATE_HUMAN_TWO_LINK_V2_ORACLE Exact-model nominal plant validation.

human_two_link_v2_validate_parameters(p);
required = {'trajectory_name', 'dt', 't_final', 'Kp', 'Kd', ...
    'rom_tolerance'};
for field_index = 1:numel(required)
    if ~isfield(config, required{field_index})
        error('HumanTwoLinkV2:MissingSimulationConfig', ...
            'Missing simulation field: %s', required{field_index});
    end
end

t = 0:config.dt:config.t_final;
sample_count = numel(t);
x = zeros(4, sample_count);
[q0, dq0] = human_two_link_v2_reference( ...
    0, config.trajectory_name);
x(:, 1) = [q0; dq0];

q_ref_log = zeros(2, sample_count);
dq_ref_log = zeros(2, sample_count);
ddq_ref_log = zeros(2, sample_count);
jerk_ref_log = zeros(2, sample_count);
tau_joint_log = zeros(2, sample_count);
tau_passive_log = zeros(2, sample_count);
tau_soft_rhs_log = zeros(2, sample_count);
acceleration_log = zeros(2, sample_count);
phase_log = strings(1, sample_count);
progress_log = zeros(1, sample_count);
soft_active_log = false(2, sample_count);

for sample_index = 1:sample_count
    current_time = t(sample_index);
    [q_ref, dq_ref, ddq_ref, phase, progress, jerk_ref] = ...
        human_two_link_v2_reference(current_time, config.trajectory_name);
    [tau_joint, oracle_details] = human_two_link_v2_oracle_controller( ...
        x(1:2, sample_index), x(3:4, sample_index), ...
        q_ref, dq_ref, ddq_ref, p, config.Kp, config.Kd);
    [~, dynamics_details] = human_two_link_v2_continuous_dynamics( ...
        x(:, sample_index), tau_joint, p);

    q_ref_log(:, sample_index) = q_ref;
    dq_ref_log(:, sample_index) = dq_ref;
    ddq_ref_log(:, sample_index) = ddq_ref;
    jerk_ref_log(:, sample_index) = jerk_ref;
    tau_joint_log(:, sample_index) = tau_joint;
    tau_passive_log(:, sample_index) = ...
        dynamics_details.tau_passive_left;
    tau_soft_rhs_log(:, sample_index) = ...
        dynamics_details.passive.soft_rhs;
    acceleration_log(:, sample_index) = dynamics_details.ddq;
    phase_log(sample_index) = phase;
    progress_log(sample_index) = progress;
    soft_active_log(:, sample_index) = ...
        dynamics_details.passive.soft.active;

    if sample_index < sample_count
        rhs = @(time, state) closed_loop_rhs(time, state, config, p);
        x(:, sample_index+1) = human_two_link_v2_rk4_step( ...
            rhs, current_time, x(:, sample_index), config.dt);
    end
end

error_log = x(1:2, :)-q_ref_log;
jerk_actual_log = zeros(size(acceleration_log));
jerk_actual_log(:, 2:end) = diff(acceleration_log, 1, 2)/config.dt;
lower_margin = x(1:2, :)-p.q_min;
upper_margin = p.q_max-x(1:2, :);
rom_margin = min(lower_margin, upper_margin);
rom_violation = any( ...
    x(1:2, :) < p.q_min-config.rom_tolerance | ...
    x(1:2, :) > p.q_max+config.rom_tolerance, 1);
checked = [x(:); q_ref_log(:); dq_ref_log(:); ddq_ref_log(:); ...
    jerk_ref_log(:); tau_joint_log(:); tau_passive_log(:); ...
    tau_soft_rhs_log(:); acceleration_log(:); jerk_actual_log(:)];

metrics = struct();
metrics.completed = all(isfinite(checked));
metrics.nonfinite_count = sum(~isfinite(checked));
metrics.rmse_rad = sqrt(mean(error_log.^2, 2));
metrics.max_abs_error_rad = max(abs(error_log), [], 2);
metrics.reference_max_velocity_rad_s = max(abs(dq_ref_log), [], 2);
metrics.reference_max_acceleration_rad_s2 = ...
    max(abs(ddq_ref_log), [], 2);
metrics.reference_max_jerk_rad_s3 = max(abs(jerk_ref_log), [], 2);
metrics.actual_max_velocity_rad_s = max(abs(x(3:4, :)), [], 2);
metrics.actual_max_acceleration_rad_s2 = ...
    max(abs(acceleration_log), [], 2);
metrics.actual_max_jerk_rad_s3 = max(abs(jerk_actual_log), [], 2);
metrics.max_abs_passive_torque_Nm = max(abs(tau_passive_log), [], 2);
metrics.max_abs_soft_rhs_torque_Nm = ...
    max(abs(tau_soft_rhs_log), [], 2);
metrics.max_abs_oracle_torque_Nm = max(abs(tau_joint_log), [], 2);
metrics.max_oracle_torque_norm_Nm = max(vecnorm(tau_joint_log, 2, 1));
metrics.soft_limit_activation_count = sum(any(soft_active_log, 1));
metrics.rom_violation_count = sum(rom_violation);
metrics.minimum_rom_margin_rad = min(rom_margin, [], 2);

result = struct();
result.config = config;
result.parameters = p;
result.t = t;
result.state = x;
result.q_ref = q_ref_log;
result.dq_ref = dq_ref_log;
result.ddq_ref = ddq_ref_log;
result.jerk_ref = jerk_ref_log;
result.acceleration = acceleration_log;
result.jerk_actual = jerk_actual_log;
result.tau_joint = tau_joint_log;
result.tau_passive_left = tau_passive_log;
result.tau_soft_rhs = tau_soft_rhs_log;
result.phase = phase_log;
result.progress = progress_log;
result.soft_active = soft_active_log;
result.tracking_error = error_log;
result.rom_margin = rom_margin;
result.metrics = metrics;
result.oracle_details_at_final_sample = oracle_details;
end


function xdot = closed_loop_rhs(t, x, config, p)
[q_ref, dq_ref, ddq_ref] = human_two_link_v2_reference( ...
    t, config.trajectory_name);
tau_joint = human_two_link_v2_oracle_controller( ...
    x(1:2), x(3:4), q_ref, dq_ref, ddq_ref, ...
    p, config.Kp, config.Kd);
xdot = human_two_link_v2_continuous_dynamics(x, tau_joint, p);
end
