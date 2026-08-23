function tests = test_near_extension_protective_mode
%TEST_NEAR_EXTENSION_PROTECTIVE_MODE Sanity-only protective-mode contracts.
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
testCase.TestData.config = near_extension_protective_mode_config();
testCase.TestData.result = simulate_near_extension_protective_mode_sanity( ...
    testCase.TestData.config);
end


function testConfigPreservesExistingScientificSettings(testCase)
c = testCase.TestData.config; normal = dynamic_robust_v1_config();
verifyEqual(testCase, c.q_switch_deg, 30);
verifyEqual(testCase, c.q_terminal_deg, 2);
verifyEqual(testCase, c.force_bound_N, normal.force_bound_N);
verifyEqual(testCase, c.normal_config, normal);
verifyTrue(testCase, c.engineering_switch_not_clinical);
end


function testQuinticMatchesBoundaryState(testCase)
c = testCase.TestData.config; q0 = deg2rad([15; 30]);
dq0 = deg2rad([-1; -4]); qf = deg2rad([1; 2]);
start = near_extension_protective_mode_quintic( ...
    0, c.transition_duration_s, q0, dq0, qf, zeros(2, 1));
finish = near_extension_protective_mode_quintic( ...
    c.transition_duration_s, c.transition_duration_s, ...
    q0, dq0, qf, zeros(2, 1));
verifyEqual(testCase, start.q, q0, 'AbsTol', 1e-14);
verifyEqual(testCase, start.dq, dq0, 'AbsTol', 1e-14);
verifyEqual(testCase, finish.q, qf, 'AbsTol', 1e-12);
verifyEqual(testCase, finish.dq, zeros(2, 1), 'AbsTol', 1e-12);
verifyEqual(testCase, finish.ddq, zeros(2, 1), 'AbsTol', 1e-11);
end


function testLandingSequenceAndTerminal(testCase)
m = testCase.TestData.result.metrics;
verifyEqual(testCase, m.landing_sequence, ...
    "NORMAL_REHAB>BLEND_TO_LANDING>KINEMATIC_LANDING>TERMINAL");
verifyLessThanOrEqual(testCase, m.terminal_error_deg, 1e-9);
end


function testTakeoffSequenceAndHandoff(testCase)
m = testCase.TestData.result.metrics;
verifyEqual(testCase, m.takeoff_sequence, ...
    "BED_START>KINEMATIC_TAKEOFF>BLEND_TO_NORMAL>NORMAL_REHAB");
verifyLessThan(testCase, m.takeoff_handoff_q_jump_rad, 1e-3);
verifyLessThan(testCase, m.takeoff_handoff_dq_jump_rad_s, 1e-3);
end


function testLandingCapturesMeasuredStateWithoutJump(testCase)
m = testCase.TestData.result.metrics;
verifyEqual(testCase, m.landing_capture_jump_rad, 0, 'AbsTol', 1e-14);
end


function testNearExtensionBypassesForceInversion(testCase)
m = testCase.TestData.result.metrics;
verifyEqual(testCase, m.near_extension_force_inversion_calls, 0);
end


function testForceVetoIsLatched(testCase)
c = testCase.TestData.config;
p = human_two_link_v2_parameters(1.72, 75);
q = near_extension_protective_mode_coordinated_posture(c.q_terminal_rad);
reference = struct('q', q, 'dq', zeros(2, 1), 'ddq', zeros(2, 1));
context = struct('tau_bed_Nm', zeros(2, 1), ...
    'u_previous_N', zeros(2, 1), 'parameters', p, ...
    'config', c.normal_config, 'robot_authority', 1, 'bed_credit', 0);
input = struct('time_s', 0, 'measured_q_rad', q, ...
    'measured_dq_rad_s', zeros(2, 1), ...
    'measured_force_N', [c.force_bound_N+1; 0], ...
    'request_landing', false, 'request_takeoff', true, ...
    'normal_reference', reference, 'normal_context', context);
state = near_extension_protective_mode_initial_state("takeoff");
[state, command, telemetry] = ...
    near_extension_protective_mode_step(state, input, c);
verifyTrue(testCase, state.protective_stop_latched);
verifyEqual(testCase, state.mode, "PROTECTIVE_STOP");
verifyTrue(testCase, telemetry.force_veto_active);
verifyTrue(testCase, all(isnan(command.force_command_N)));
input.measured_force_N = zeros(2, 1);
[state, ~, telemetry] = near_extension_protective_mode_step(state, input, c);
verifyEqual(testCase, state.mode, "PROTECTIVE_STOP");
verifyTrue(testCase, telemetry.force_veto_active);
end


function testNormalControllerIsExactDelegation(testCase)
m = testCase.TestData.result.metrics;
verifyTrue(testCase, m.normal_controller_exact_reuse);
verifyEqual(testCase, m.normal_force_command_delta_N, 0);
end


function testQSwitchEvidenceHasExplicitMargin(testCase)
e = near_extension_protective_mode_q_switch_evidence();
verifyEqual(testCase, e.recommended_q_switch_deg, 30);
verifyEqual(testCase, e.snapshot.robust_reserve_N, [0; 5; 10; 20]);
verifyEqual(testCase, e.snapshot.q2_entry_deg, ...
    [27.020; 28.204; 29.536; 32.496], 'AbsTol', 1e-12);
verifyTrue(testCase, e.not_clinical_threshold);
end
