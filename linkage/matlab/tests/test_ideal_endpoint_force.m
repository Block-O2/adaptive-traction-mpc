function tests = test_ideal_endpoint_force
tests = functiontests(localfunctions);
end


function testLocalWorldGeneralizedForceMapping(testCase)
p = default_parameters("nominal");
states = deg2rad([ ...
    10, 30, 65; ...
    15, 55, 95; ...
    -5, 20, 40; ...
    10, -15, 5]);
forces = [120, -80, 45; -60, 95, -110];

for index = 1:size(states, 2)
    mapping = shank_endpoint_force_map( ...
        states(1:2, index), states(3:4, index), p);
    u = forces(:, index);
    world_force = mapping.rotation*u;
    verifyEqual(testCase, mapping.rotation'*mapping.rotation, ...
        eye(2), 'AbsTol', 1e-12);
    verifyEqual(testCase, ...
        mapping.generalized_force_map*u, ...
        mapping.contact.J'*world_force, 'AbsTol', 1e-12);
end
end


function testBoxSolverUnconstrainedAndBoundarySolutions(testCase)
[u_free, free_details] = solve_box_quadratic_2d( ...
    [2, 0.3; 0.3, 1], [-0.4; 0.2], [-2; -2], [2; 2]);
expected_free = -[2, 0.3; 0.3, 1] \ [-0.4; 0.2];
verifyEqual(testCase, u_free, expected_free, 'AbsTol', 1e-12);
verifyEqual(testCase, free_details.active_status, [0; 0]);

[u_boundary, boundary_details] = solve_box_quadratic_2d( ...
    eye(2), [-2; 1], [-0.5; -0.25], [0.8; 0.4]);
verifyEqual(testCase, u_boundary, [0.8; -0.25], 'AbsTol', 1e-12);
verifyEqual(testCase, boundary_details.active_status, [1; -1]);
end


function testBoxSolverIsDeterministic(testCase)
H = [1.4, -0.2; -0.2, 0.9];
f = [0.7; -1.2];
lower = [-0.3; -0.4];
upper = [0.6; 0.5];
[first, first_details] = solve_box_quadratic_2d( ...
    H, f, lower, upper);
[second, second_details] = solve_box_quadratic_2d( ...
    H, f, lower, upper);
verifyEqual(testCase, first, second);
verifyEqual(testCase, first_details.objective, second_details.objective);
end


function testControllerRespectsHardAndSlewBounds(testCase)
p = default_parameters("tall_heavy");
config = ideal_endpoint_force_config();
q = deg2rad([25; 35]);
dq = deg2rad([10; -8]);
[q_ref, dq_ref, ddq_ref] = ...
    rehabilitation_reference_trajectory(2.0, "coordinated_path");
u_prev = [100; -50];
[u, details] = ideal_endpoint_force_controller( ...
    q, dq, q_ref, dq_ref, ddq_ref, u_prev, p, config);

verifyGreaterThanOrEqual(testCase, u, config.u_min);
verifyLessThanOrEqual(testCase, u, config.u_max);
verifyLessThanOrEqual(testCase, abs(u-u_prev), ...
    config.du_max*config.dt + 1e-12);
verifyEqual(testCase, details.tau_contact, ...
    details.A*u, 'AbsTol', 1e-12);
verifyEqual(testCase, details.torque_residual, ...
    details.tau_contact-details.tau_req, 'AbsTol', 1e-12);
end


function testReferenceSegmentsAreSmoothAndWithinLimits(testCase)
p = default_parameters("nominal");
config = ideal_endpoint_force_config();
trajectories = [ ...
    "knee_dominant", "coordinated_path", "conflicting_boundary"];
t = 0:config.dt:config.t_final;

for trajectory = trajectories
    q = zeros(2, numel(t));
    dq = zeros(2, numel(t));
    ddq = zeros(2, numel(t));
    for index = 1:numel(t)
        [q(:, index), dq(:, index), ddq(:, index)] = ...
            rehabilitation_reference_trajectory(t(index), trajectory);
    end
    verifyGreaterThanOrEqual(testCase, q, p.q_min);
    verifyLessThanOrEqual(testCase, q, p.q_max);
    verifyLessThanOrEqual(testCase, abs(dq), p.dq_max + 1e-12);
    verifyLessThanOrEqual(testCase, abs(ddq), ...
        p.reference_ddq_max + 1e-12);
    boundary_times = [0, 1.0, 3.5, 4.5, 7.0, 8.0];
    for boundary_time = boundary_times
        [~, boundary_dq, boundary_ddq] = ...
            rehabilitation_reference_trajectory( ...
            boundary_time, trajectory);
        verifyEqual(testCase, boundary_dq, zeros(2, 1), ...
            'AbsTol', 1e-12);
        verifyEqual(testCase, boundary_ddq, zeros(2, 1), ...
            'AbsTol', 1e-12);
    end
end
end


function testCoordinatedReferenceLiesOnRecordedPath(testCase)
t = linspace(0, 8, 101);
maximum_deviation = 0;
for time = t
    [q, ~, ~, metadata] = ...
        rehabilitation_reference_trajectory(time, "coordinated_path");
    path_deviation = (q(2)-metadata.path_origin(2)) - ...
        metadata.path_slope*(q(1)-metadata.path_origin(1));
    maximum_deviation = max(maximum_deviation, abs(path_deviation));
end
verifyLessThanOrEqual(testCase, maximum_deviation, 1e-14);
end


function testConflictingReferenceApproachesMapSingularity(testCase)
p = default_parameters("nominal");
[q_peak, ~, ~] = rehabilitation_reference_trajectory( ...
    4.0, "conflicting_boundary");
mapping = shank_endpoint_force_map(q_peak, zeros(2, 1), p);
verifyGreaterThan(testCase, cond(mapping.generalized_force_map), 200);
verifyGreaterThan(testCase, abs(det(mapping.generalized_force_map)), 0);
end


function testEndpointDynamicsContainsOnlyMappedForce(testCase)
p = default_parameters("nominal");
x = [deg2rad([30; 45]); deg2rad([5; -3])];
u = [80; -55];
[xdot, details] = endpoint_force_dynamics(x, u, p);
mapping = shank_endpoint_force_map(x(1:2), x(3:4), p);
[M, h, ~, G] = dynamics_terms(x(1:2), x(3:4), p);
expected_tau = mapping.generalized_force_map*u;
expected_ddq = M \ (expected_tau-h-G-p.B*x(3:4));

verifyEqual(testCase, details.tau_contact, expected_tau, ...
    'AbsTol', 1e-12);
verifyEqual(testCase, xdot, [x(3:4); expected_ddq], ...
    'AbsTol', 1e-12);
verifyFalse(testCase, isfield(details, 'tau_joint'));
end


function testEndpointAndOracleAuthorityRemainSeparate(testCase)
p = default_parameters("nominal");
config = ideal_endpoint_force_config();
config.t_final = 0.05;
config.trajectory_name = "knee_dominant";

endpoint = simulate_ideal_endpoint_force_episode( ...
    config, p, "endpoint_force");
oracle = simulate_ideal_endpoint_force_episode( ...
    config, p, "oracle_joint_torque");

verifyTrue(testCase, endpoint.metrics.completed);
verifyTrue(testCase, oracle.metrics.completed);
verifyEqual(testCase, endpoint.tau_joint, ...
    zeros(size(endpoint.tau_joint)));
verifyTrue(testCase, all(isnan(oracle.force_local), 'all'));
verifyGreaterThan(testCase, max(vecnorm(oracle.tau_joint, 2, 1)), 0);
verifyLessThanOrEqual(testCase, ...
    max(abs(endpoint.force_local), [], 2), config.u_max + 1e-12);
verifyEqual(testCase, endpoint.metrics.initial_alignment_error_rad, 0);
verifyEqual(testCase, endpoint.force_local(:, 1), ...
    endpoint.initial_force_local, 'AbsTol', 1e-10);
verifyEqual(testCase, endpoint.force_rate(:, 1), zeros(2, 1), ...
    'AbsTol', 1e-10);
end
