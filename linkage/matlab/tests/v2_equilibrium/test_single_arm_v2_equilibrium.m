function tests = test_single_arm_v2_equilibrium
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75.0);
base = single_arm_v2_equilibrium_base_config();
preflight = single_arm_v2_reference_preflight(p, base);
ideal_config = single_arm_v2_case_config( ...
    base, preflight, "ideal_authority");
ideal = simulate_single_arm_v2_equilibrium(ideal_config, p);
testCase.TestData.p = p;
testCase.TestData.base = base;
testCase.TestData.preflight = preflight;
testCase.TestData.ideal_config = ideal_config;
testCase.TestData.ideal = ideal;
end


function testContactJacobianFiniteDifference(testCase)
p = testCase.TestData.p;
q = deg2rad([32; 47]);
dq = deg2rad([8; -12]);
contact = human_two_link_v2_contact_kinematics(q, dq, p);
step = 1e-7;
J_numeric = zeros(2);
for coordinate = 1:2
    perturbation = zeros(2, 1);
    perturbation(coordinate) = step;
    plus = human_two_link_v2_contact_kinematics( ...
        q+perturbation, zeros(2, 1), p);
    minus = human_two_link_v2_contact_kinematics( ...
        q-perturbation, zeros(2, 1), p);
    J_numeric(:, coordinate) = ...
        (plus.position-minus.position)/(2*step);
end
verifyEqual(testCase, contact.J, J_numeric, 'AbsTol', 1e-9);
verifyEqual(testCase, contact.velocity, contact.J*dq, 'AbsTol', 1e-13);
end


function testLocalWorldFrameOrthonormal(testCase)
p = testCase.TestData.p;
mapping = single_arm_v2_force_map( ...
    deg2rad([41; 63]), deg2rad([5; -4]), p);
verifyEqual(testCase, mapping.rotation'*mapping.rotation, eye(2), ...
    'AbsTol', 1e-13);
verifyEqual(testCase, det(mapping.rotation), 1, 'AbsTol', 1e-13);
end


function testAnalyticGeneralizedForceMap(testCase)
p = testCase.TestData.p;
for q2 = deg2rad([10, 30, 60, 84])
    mapping = single_arm_v2_force_map( ...
        [deg2rad(25); q2], zeros(2, 1), p);
    numerical = mapping.contact.J'*mapping.rotation;
    verifyEqual(testCase, mapping.A, numerical, 'AbsTol', 1e-13);
    verifyEqual(testCase, mapping.A, mapping.analytic_A, ...
        'AbsTol', 1e-13);
end
end


function testAnalyticDeterminant(testCase)
p = testCase.TestData.p;
for q2 = deg2rad([10, 25, 50, 84])
    mapping = single_arm_v2_force_map([0.4; q2], [0; 0], p);
    expected = p.L1*p.sc*sin(q2);
    verifyEqual(testCase, mapping.det_A, expected, 'AbsTol', 1e-14);
    verifyEqual(testCase, mapping.det_A_analytic, expected, ...
        'AbsTol', 1e-14);
end
end


function testSingularValueAndConditionDiagnostics(testCase)
p = testCase.TestData.p;
mapping = single_arm_v2_force_map( ...
    deg2rad([20; 35]), zeros(2, 1), p);
s = svd(mapping.A);
verifyEqual(testCase, mapping.sigma_min, s(end), 'AbsTol', 1e-14);
verifyEqual(testCase, mapping.condition_number, cond(mapping.A), ...
    'RelTol', 1e-13);
verifyGreaterThan(testCase, mapping.sigma_min, 0);
end


function testEndpointDynamicsUsesOnlyEndpointForce(testCase)
p = testCase.TestData.p;
x = [deg2rad([25; 40]); deg2rad([4; -3])];
u = [-120; 18];
[xdot, details] = single_arm_v2_endpoint_dynamics(x, u, p);
verifyEqual(testCase, details.tau_contact, details.mapping.A*u, ...
    'AbsTol', 1e-13);
expected = details.M\(details.tau_contact-details.h-details.G- ...
    details.tau_passive_left);
verifyEqual(testCase, xdot(3:4), expected, 'AbsTol', 1e-12);
end


function testStaticBalanceResidual(testCase)
preflight = testCase.TestData.preflight;
verifyLessThan(testCase, max(preflight.static_residual_Nm), 1e-10);
verifyGreaterThan(testCase, ...
    preflight.metrics.max_static_force_norm_N, 300);
end


function testDynamicPreflightResidual(testCase)
preflight = testCase.TestData.preflight;
verifyLessThan(testCase, max(preflight.ff_residual_Nm), 1e-10);
verifyEqual(testCase, ...
    preflight.tau_ff-preflight.tau_static, ...
    preflight.tau_dynamic_increment, 'AbsTol', 1e-13);
end


function testUnconstrainedControllerReturnsDesiredForce(testCase)
p = testCase.TestData.p;
config = testCase.TestData.ideal_config;
config.u_min = [-1e6; -1e6];
config.u_max = [1e6; 1e6];
config.du_max = [1e9; 1e9];
[q, dq, ddq] = human_two_link_v2_reference( ...
    4.0, config.trajectory_name);
[u, details] = single_arm_v2_equilibrium_controller( ...
    q, dq, q, dq, ddq, [0; 0], p, config);
verifyEqual(testCase, u, details.u_des, 'AbsTol', 1e-9);
verifyLessThan(testCase, norm(details.torque_residual), 1e-10);
end


function testForceBound(testCase)
p = testCase.TestData.p;
config = testCase.TestData.ideal_config;
config.u_min = [-80; -80];
config.u_max = [80; 80];
config.du_max = [1e9; 1e9];
[q, dq, ddq] = human_two_link_v2_reference(0, config.trajectory_name);
[u, details] = single_arm_v2_equilibrium_controller( ...
    q, dq, q, dq, ddq, [-80; 20], p, config);
verifyGreaterThanOrEqual(testCase, u, config.u_min);
verifyLessThanOrEqual(testCase, u, config.u_max);
verifyTrue(testCase, details.force_bound_limited);
verifyTrue(testCase, details.force_saturated);
end


function testSlewBound(testCase)
p = testCase.TestData.p;
config = testCase.TestData.ideal_config;
config.u_min = [-1000; -1000];
config.u_max = [1000; 1000];
config.du_max = [0.1; 0.1];
[q, dq, ddq] = human_two_link_v2_reference(0, config.trajectory_name);
u_prev = [0; 0];
[u, details] = single_arm_v2_equilibrium_controller( ...
    q, dq, q, dq, ddq, u_prev, p, config);
verifyLessThanOrEqual(testCase, abs(u-u_prev), ...
    config.du_max*config.dt+1e-12);
verifyTrue(testCase, details.slew_bound_limited);
verifyTrue(testCase, details.slew_saturated);
end


function testSaturationCauseClassification(testCase)
p = testCase.TestData.p;
config = testCase.TestData.ideal_config;
config.u_min = [-1e9; -1e9];
config.u_max = [1e9; 1e9];
config.du_max = [1e12; 1e12];
q = deg2rad([20; 0]);
dq = [0; 0];
[~, details] = single_arm_v2_equilibrium_controller( ...
    q, dq, q, dq, [0; 0], [0; 0], p, config);
verifyTrue(testCase, details.conditioning_limited);
verifyFalse(testCase, details.force_bound_limited);
verifyFalse(testCase, details.slew_bound_limited);
verifyFalse(testCase, details.numerical_limited);
end


function testIdealInitializationHasNoArtificialRateSpike(testCase)
ideal = testCase.TestData.ideal;
verifyEqual(testCase, ideal.metrics.initial_force_rate_N_s, ...
    zeros(2, 1), 'AbsTol', 1e-8);
verifyEqual(testCase, ideal.force_local(:, 1), ...
    ideal.metrics.initial_force_N, 'AbsTol', 1e-12);
end


function testIdealRolloutFiniteAndWithinROM(testCase)
ideal = testCase.TestData.ideal;
verifyTrue(testCase, ideal.metrics.completed);
verifyEqual(testCase, ideal.metrics.nonfinite_count, 0);
verifyEqual(testCase, ideal.metrics.rom_violation_count, 0);
verifyLessThan(testCase, max(rad2deg(ideal.metrics.rmse_rad)), 0.1);
end


function testEngineeringPreflightIsDiagnosedBeforeClosedLoop(testCase)
preflight = testCase.TestData.preflight;
verifyLessThan(testCase, ...
    preflight.metrics.engineering_feasible_fraction, 1);
verifyGreaterThan(testCase, ...
    preflight.metrics.engineering_residual_rms_Nm, 0);
verifyGreaterThan(testCase, ...
    preflight.metrics.max_static_torque_Nm, ...
    preflight.metrics.max_dynamic_increment_torque_Nm);
end
