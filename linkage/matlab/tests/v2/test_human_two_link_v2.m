function tests = test_human_two_link_v2
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75.0);
config = human_two_link_v2_baseline_config();
result = simulate_human_two_link_v2_oracle(config, p);
testCase.TestData.p = p;
testCase.TestData.config = config;
testCase.TestData.result = result;
end


function testNominalAnthropometricFormulas(testCase)
p = testCase.TestData.p;
H = 1.72;
body_mass = 75.0;
verifyEqual(testCase, p.L1, 0.254*H, 'AbsTol', 1e-14);
verifyEqual(testCase, p.L2, 0.233*H, 'AbsTol', 1e-14);
verifyEqual(testCase, p.m1, 0.099*body_mass, 'AbsTol', 1e-14);
verifyEqual(testCase, p.m2, (0.046+0.014)*body_mass, ...
    'AbsTol', 1e-14);
verifyEqual(testCase, p.lc1, 0.433*p.L1, 'AbsTol', 1e-14);
verifyEqual(testCase, p.lc2, 0.430*p.L2, 'AbsTol', 1e-14);
verifyEqual(testCase, p.I1, p.m1*(0.30*p.L1)^2, ...
    'AbsTol', 1e-14);
verifyEqual(testCase, p.I2, p.m2*(0.30*p.L2)^2, ...
    'AbsTol', 1e-14);
end


function testArbitraryValidAnthropometry(testCase)
p = human_two_link_v2_parameters(1.55, 52.0);
verifyEqual(testCase, p.height_m, 1.55);
verifyEqual(testCase, p.body_mass_kg, 52.0);
verifyGreaterThan(testCase, min([p.L1, p.L2, p.m1, p.m2]), 0);
end


function testInvalidAnthropometryRejected(testCase)
invalid_pairs = [ ...
     0, 75; ...
    -1, 75; ...
   NaN, 75; ...
   1.7, 0; ...
   1.7, -5; ...
   1.7, Inf];
for index = 1:size(invalid_pairs, 1)
    height = invalid_pairs(index, 1);
    mass = invalid_pairs(index, 2);
    verifyError(testCase, ...
        @() human_two_link_v2_parameters(height, mass), ...
        'HumanTwoLinkV2:InvalidAnthropometry');
end
end


function testMassMatrixSymmetryAndPositiveDefiniteness(testCase)
p = testCase.TestData.p;
[q_values, dq_values] = deterministic_grid();
minimum_eigenvalue = inf;
maximum_symmetry_residual = 0;
for index = 1:size(q_values, 2)
    M = human_two_link_v2_dynamics_terms( ...
        q_values(:, index), dq_values(:, index), p);
    maximum_symmetry_residual = max(maximum_symmetry_residual, ...
        norm(M-M', inf));
    minimum_eigenvalue = min(minimum_eigenvalue, ...
        min(eig((M+M')/2)));
end
verifyLessThanOrEqual(testCase, maximum_symmetry_residual, 1e-12);
verifyGreaterThan(testCase, minimum_eigenvalue, 0);
end


function testCoriolisVectorConsistency(testCase)
p = testCase.TestData.p;
[q_values, dq_values] = deterministic_grid();
maximum_residual = 0;
for index = 1:size(q_values, 2)
    [~, h, C] = human_two_link_v2_dynamics_terms( ...
        q_values(:, index), dq_values(:, index), p);
    maximum_residual = max(maximum_residual, ...
        norm(C*dq_values(:, index)-h, inf));
end
verifyLessThanOrEqual(testCase, maximum_residual, 1e-12);
end


function testManipulatorSkewSymmetry(testCase)
p = testCase.TestData.p;
[q_values, dq_values] = deterministic_grid();
step = 1e-7;
maximum_residual = 0;
for index = 1:size(q_values, 2)
    q = q_values(:, index);
    dq = dq_values(:, index);
    [~, ~, C] = human_two_link_v2_dynamics_terms(q, dq, p);
    M_plus = human_two_link_v2_dynamics_terms(q+step*dq, dq, p);
    M_minus = human_two_link_v2_dynamics_terms(q-step*dq, dq, p);
    M_dot = (M_plus-M_minus)/(2*step);
    candidate = M_dot-2*C;
    maximum_residual = max(maximum_residual, ...
        norm(candidate+candidate', inf));
end
verifyLessThanOrEqual(testCase, maximum_residual, 1e-8);
end


function testGravityMatchesPotentialGradient(testCase)
p = testCase.TestData.p;
[q_values, dq_values] = deterministic_grid();
step = 1e-6;
maximum_residual = 0;
for index = 1:size(q_values, 2)
    q = q_values(:, index);
    [~, ~, ~, G] = human_two_link_v2_dynamics_terms( ...
        q, dq_values(:, index), p);
    numerical = zeros(2, 1);
    for coordinate = 1:2
        perturbation = zeros(2, 1);
        perturbation(coordinate) = step;
        numerical(coordinate) = ( ...
            human_two_link_v2_potential_energy(q+perturbation, p) - ...
            human_two_link_v2_potential_energy(q-perturbation, p)) / ...
            (2*step);
    end
    maximum_residual = max(maximum_residual, norm(numerical-G, inf));
end
verifyLessThanOrEqual(testCase, maximum_residual, 1e-7);
end


function testPassiveTorqueZeroAtRest(testCase)
p = testCase.TestData.p;
[tau_passive, details] = human_two_link_v2_passive_torque( ...
    p.q_rest, zeros(2, 1), p);
verifyEqual(testCase, tau_passive, zeros(2, 1), 'AbsTol', 1e-14);
verifyEqual(testCase, details.soft_rhs, zeros(2, 1));
end


function testPassiveDampingDissipativity(testCase)
p = testCase.TestData.p;
q = deg2rad([30; 45]);
dq_values = deg2rad([ ...
    -30, 20, 45; ...
     40, -35, 10]);
for index = 1:size(dq_values, 2)
    dq = dq_values(:, index);
    tau_moving = human_two_link_v2_passive_torque(q, dq, p);
    tau_static = human_two_link_v2_passive_torque( ...
        q, zeros(2, 1), p);
    damping_left = tau_moving-tau_static;
    verifyEqual(testCase, damping_left, p.B_passive*dq, ...
        'AbsTol', 1e-12);
    verifyGreaterThanOrEqual(testCase, dq'*damping_left, 0);
end
end


function testSoftLimitZeroInSafeRegion(testCase)
p = testCase.TestData.p;
lower = p.q_min+p.soft_limit_margin;
upper = p.q_max-p.soft_limit_margin;
q_values = [lower, (lower+upper)/2, upper];
for index = 1:size(q_values, 2)
    tau = human_two_link_v2_soft_limit_rhs_torque( ...
        q_values(:, index), deg2rad([20; -20]), p);
    verifyEqual(testCase, tau, zeros(2, 1));
end
end


function testSoftLimitDirectionAtBothBounds(testCase)
p = testCase.TestData.p;
lower_dq = deg2rad([-10; -15]);
upper_dq = deg2rad([10; 15]);
tau_lower = human_two_link_v2_soft_limit_rhs_torque( ...
    p.q_min, lower_dq, p);
tau_upper = human_two_link_v2_soft_limit_rhs_torque( ...
    p.q_max, upper_dq, p);
verifyGreaterThan(testCase, tau_lower, zeros(2, 1));
verifyLessThan(testCase, tau_upper, zeros(2, 1));
verifyLessThan(testCase, lower_dq'*tau_lower, 0);
verifyLessThan(testCase, upper_dq'*tau_upper, 0);
end


function testSoftLimitContinuityAtActivation(testCase)
p = testCase.TestData.p;
lower = p.q_min+p.soft_limit_margin;
upper = p.q_max-p.soft_limit_margin;
epsilon = 1e-7;
at_lower = human_two_link_v2_soft_limit_rhs_torque( ...
    lower, zeros(2, 1), p);
below_lower = human_two_link_v2_soft_limit_rhs_torque( ...
    lower-epsilon, zeros(2, 1), p);
at_upper = human_two_link_v2_soft_limit_rhs_torque( ...
    upper, zeros(2, 1), p);
above_upper = human_two_link_v2_soft_limit_rhs_torque( ...
    upper+epsilon, zeros(2, 1), p);
verifyEqual(testCase, at_lower, zeros(2, 1));
verifyEqual(testCase, at_upper, zeros(2, 1));
verifyLessThan(testCase, norm(below_lower, inf), 1e-12);
verifyLessThan(testCase, norm(above_upper, inf), 1e-12);
end


function testDistalContactLocation(testCase)
p = testCase.TestData.p;
verifyEqual(testCase, p.sc, 0.90*p.L2, 'AbsTol', 1e-14);
q = deg2rad([35; 55]);
geometry = human_two_link_v2_kinematics(q, p);
verifyEqual(testCase, norm(geometry.contact-geometry.knee), ...
    p.sc, 'AbsTol', 1e-14);
end


function testReferenceBoundaryContinuity(testCase)
boundary_times = [0, 1.0, 7.5, 8.5, 15.0, 16.0];
for time = boundary_times
    [~, dq, ddq] = human_two_link_v2_reference( ...
        time, "slow_passive_flexion_v2");
    verifyEqual(testCase, dq, zeros(2, 1), 'AbsTol', 1e-12);
    verifyEqual(testCase, ddq, zeros(2, 1), 'AbsTol', 1e-12);
end
[q_start, ~] = human_two_link_v2_reference( ...
    0, "slow_passive_flexion_v2");
[q_peak, ~] = human_two_link_v2_reference( ...
    8.0, "slow_passive_flexion_v2");
[q_end, ~] = human_two_link_v2_reference( ...
    16.0, "slow_passive_flexion_v2");
verifyEqual(testCase, q_start, deg2rad([5; 10]), 'AbsTol', 1e-14);
verifyEqual(testCase, q_peak, deg2rad([45; 84]), 'AbsTol', 1e-14);
verifyEqual(testCase, q_end, q_start, 'AbsTol', 1e-14);
end


function testReferenceROMVelocityAccelerationAndProgress(testCase)
p = testCase.TestData.p;
config = testCase.TestData.config;
t = 0:config.dt:config.t_final;
q = zeros(2, numel(t));
dq = zeros(2, numel(t));
ddq = zeros(2, numel(t));
progress = zeros(1, numel(t));
for index = 1:numel(t)
    [q(:, index), dq(:, index), ddq(:, index), ~, progress(index)] = ...
        human_two_link_v2_reference( ...
        t(index), config.trajectory_name);
end
verifyGreaterThanOrEqual(testCase, q, p.q_min);
verifyLessThanOrEqual(testCase, q, p.q_max);
verifyLessThanOrEqual(testCase, max(abs(dq), [], 'all'), 0.40);
verifyLessThanOrEqual(testCase, max(abs(ddq), [], 'all'), 1.5);
verifyGreaterThanOrEqual(testCase, progress, 0);
verifyLessThanOrEqual(testCase, progress, 1);
end


function testOracleRolloutFiniteAndAccurate(testCase)
result = testCase.TestData.result;
verifyTrue(testCase, result.metrics.completed);
verifyEqual(testCase, result.metrics.nonfinite_count, 0);
verifyLessThan(testCase, ...
    max(rad2deg(result.metrics.rmse_rad)), 1e-4);
end


function testOracleRolloutWithinROMAndNoSoftLimit(testCase)
result = testCase.TestData.result;
verifyEqual(testCase, result.metrics.rom_violation_count, 0);
verifyEqual(testCase, result.metrics.soft_limit_activation_count, 0);
verifyGreaterThanOrEqual(testCase, ...
    result.metrics.minimum_rom_margin_rad, zeros(2, 1));
end


function testDynamicsUsesLeftSidePassiveSign(testCase)
p = testCase.TestData.p;
x = [deg2rad([25; 35]); deg2rad([8; -6])];
tau_joint = [12; -4];
[xdot, details] = human_two_link_v2_continuous_dynamics( ...
    x, tau_joint, p);
expected_ddq = details.M\(tau_joint-details.h-details.G- ...
    details.tau_passive_left);
verifyEqual(testCase, xdot(3:4), expected_ddq, 'AbsTol', 1e-12);
verifyGreaterThanOrEqual(testCase, ...
    details.passive.damping_dissipation_W, 0);
end


function [q_values, dq_values] = deterministic_grid()
q1 = deg2rad([0, 20, 45, 80]);
q2 = deg2rad([0, 25, 60, 100]);
dq1 = deg2rad([-50, 0, 50]);
dq2 = deg2rad([-60, 0, 60]);
[q1_grid, q2_grid, dq1_grid, dq2_grid] = ...
    ndgrid(q1, q2, dq1, dq2);
q_values = [q1_grid(:)'; q2_grid(:)'];
dq_values = [dq1_grid(:)'; dq2_grid(:)'];
end
