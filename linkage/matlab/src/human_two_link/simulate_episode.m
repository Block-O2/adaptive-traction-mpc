function result = simulate_episode(config, p)
%SIMULATE_EPISODE Deterministic closed-loop RK4 validation episode.

validate_parameters(p);
required = {'trajectory_name', 'contact_enabled', 'dt', 't_final', ...
    'Kp', 'Kd', 'initial_position_offset', 'initial_velocity_offset', ...
    'dissipativity_tolerance', 'limit_tolerance'};
for field_index = 1:numel(required)
    if ~isfield(config, required{field_index})
        error('HumanTwoLink:MissingSimulationConfig', ...
            'Missing simulation config field: %s', required{field_index});
    end
end

t = 0:config.dt:config.t_final;
sample_count = numel(t);
x = zeros(4, sample_count);
[q0_ref, dq0_ref, ~] = reference_trajectory(t(1), config.trajectory_name);
x(:, 1) = [q0_ref + config.initial_position_offset(:); ...
    dq0_ref + config.initial_velocity_offset(:)];

q_ref_log = zeros(2, sample_count);
dq_ref_log = zeros(2, sample_count);
ddq_ref_log = zeros(2, sample_count);
tau_joint_log = zeros(2, sample_count);
tau_contact_log = zeros(2, sample_count);
contact_force_log = zeros(2, sample_count);
contact_power_log = zeros(1, sample_count);
acceleration_log = zeros(2, sample_count);
robot_velocity_log = zeros(2, sample_count);

for sample_index = 1:sample_count
    [q_ref, dq_ref, ddq_ref] = reference_trajectory( ...
        t(sample_index), config.trajectory_name);
    [tau_joint, ~] = computed_torque_pd( ...
        x(1:2, sample_index), x(3:4, sample_index), ...
        q_ref, dq_ref, ddq_ref, p, config.Kp, config.Kd);
    reference_contact = shank_contact_kinematics(q_ref, dq_ref, p);
    vr = reference_contact.J * dq_ref;
    [~, dynamics_details] = continuous_dynamics( ...
        x(:, sample_index), tau_joint, vr, p, config.contact_enabled);

    q_ref_log(:, sample_index) = q_ref;
    dq_ref_log(:, sample_index) = dq_ref;
    ddq_ref_log(:, sample_index) = ddq_ref;
    tau_joint_log(:, sample_index) = tau_joint;
    tau_contact_log(:, sample_index) = dynamics_details.tau_contact;
    contact_force_log(:, sample_index) = dynamics_details.Fc;
    contact_power_log(sample_index) = ...
        dynamics_details.contact.relative_power;
    acceleration_log(:, sample_index) = dynamics_details.ddq;
    robot_velocity_log(:, sample_index) = vr;

    if sample_index < sample_count
        rhs = @(time, state) closed_loop_rhs(time, state, config, p);
        x(:, sample_index + 1) = rk4_step( ...
            rhs, t(sample_index), x(:, sample_index), config.dt);
    end
end

error_log = x(1:2, :) - q_ref_log;
nonfinite_count = sum(~isfinite([x(:); tau_joint_log(:); ...
    tau_contact_log(:); contact_force_log(:); acceleration_log(:)]));
joint_limit_violation = any( ...
    x(1:2, :) < p.q_min - config.limit_tolerance | ...
    x(1:2, :) > p.q_max + config.limit_tolerance, 1);
velocity_limit_violation = any( ...
    abs(x(3:4, :)) > p.dq_max + config.limit_tolerance, 1);
dissipativity_violation = contact_power_log > ...
    config.dissipativity_tolerance;

metrics = struct();
metrics.rmse_rad = sqrt(mean(error_log.^2, 2));
metrics.max_abs_error_rad = max(abs(error_log), [], 2);
metrics.max_abs_velocity_rad_s = max(abs(x(3:4, :)), [], 2);
metrics.max_abs_acceleration_rad_s2 = max(abs(acceleration_log), [], 2);
metrics.max_abs_joint_torque_Nm = max(abs(tau_joint_log), [], 2);
metrics.max_joint_torque_norm_Nm = max(vecnorm(tau_joint_log, 2, 1));
metrics.max_contact_force_N = max(vecnorm(contact_force_log, 2, 1));
metrics.contact_dissipativity_violation_count = ...
    sum(dissipativity_violation);
metrics.joint_limit_violation_count = sum(joint_limit_violation);
metrics.velocity_limit_violation_count = sum(velocity_limit_violation);
metrics.nonfinite_count = nonfinite_count;
metrics.completed = nonfinite_count == 0;

result = struct();
result.config = config;
result.parameters = p;
result.t = t;
result.state = x;
result.q_ref = q_ref_log;
result.dq_ref = dq_ref_log;
result.ddq_ref = ddq_ref_log;
result.tau_joint = tau_joint_log;
result.tau_contact = tau_contact_log;
result.contact_force = contact_force_log;
result.contact_power = contact_power_log;
result.robot_velocity = robot_velocity_log;
result.acceleration = acceleration_log;
result.metrics = metrics;
end


function xdot = closed_loop_rhs(t, x, config, p)
[q_ref, dq_ref, ddq_ref] = reference_trajectory( ...
    t, config.trajectory_name);
tau_joint = computed_torque_pd( ...
    x(1:2), x(3:4), q_ref, dq_ref, ddq_ref, ...
    p, config.Kp, config.Kd);
reference_contact = shank_contact_kinematics(q_ref, dq_ref, p);
vr = reference_contact.J * dq_ref;
xdot = continuous_dynamics( ...
    x, tau_joint, vr, p, config.contact_enabled);
end
