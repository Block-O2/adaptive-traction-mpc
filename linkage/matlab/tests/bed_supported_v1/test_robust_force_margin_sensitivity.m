function tests = test_robust_force_margin_sensitivity
%TEST_ROBUST_FORCE_MARGIN_SENSITIVITY Deterministic sensitivity contracts.
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75);
config = bed_supported_v1_force_margin_sensitivity_config();
study = bed_supported_v1_robust_force_margin_sensitivity(p, config);
testCase.TestData.p = p;
testCase.TestData.config = config;
testCase.TestData.study = study;
end


function testNominalReproducesForceMarginMap(testCase)
table_data = testCase.TestData.study.results_table;
current = table_data(table_data.case_id == "nominal" & ...
    table_data.posture_name == "current_7deg", :);
optimum = table_data(table_data.case_id == "nominal" & ...
    table_data.posture_name == "max_margin_5deg", :);
verifyEqual(testCase, current.force_margin_N, 9.51471947, 'AbsTol', 1e-7);
verifyEqual(testCase, optimum.force_margin_N, 10.5541268, 'AbsTol', 1e-7);
end


function testZeroPerturbationReproducesNominal(testCase)
p = testCase.TestData.p;
override = identity_override();
actual = bed_supported_v1_parameter_override(p, override);
verifyEqual(testCase, actual, p);
end


function testOverrideDoesNotMutateNominal(testCase)
p = testCase.TestData.p;
before = p;
override = identity_override();
override.mass_scale = 1.10;
override.sc_scale = 0.95;
bed_supported_v1_parameter_override(p, override);
verifyEqual(testCase, p, before);
end


function testForceDecompositionRemainsFinite(testCase)
table_data = testCase.TestData.study.results_table;
signals = [table_data.F_parallel_N; table_data.F_perp_N; ...
    table_data.force_norm_2_N; table_data.force_norm_inf_N; ...
    table_data.force_margin_N];
verifyTrue(testCase, all(isfinite(signals)));
end


function testTorqueResidualWithinTolerance(testCase)
table_data = testCase.TestData.study.results_table;
verifyLessThanOrEqual(testCase, max(table_data.torque_residual_norm_Nm), ...
    testCase.TestData.config.torque_residual_tolerance_Nm);
end


function testPositiveMassChangesGravityConsistently(testCase)
p = testCase.TestData.p;
override = identity_override();
override.mass_scale = 1.10;
perturbed = bed_supported_v1_parameter_override(p, override);
q = deg2rad([7;20]);
[~,~,~,nominal_G] = human_two_link_v2_dynamics_terms(q, zeros(2,1), p);
[~,~,~,perturbed_G] = human_two_link_v2_dynamics_terms( ...
    q, zeros(2,1), perturbed);
verifyEqual(testCase, perturbed_G, 1.10*nominal_G, 'AbsTol', 1e-12);
end


function testContactLocationUpdatesForceMapConsistently(testCase)
p = testCase.TestData.p;
override = identity_override();
override.sc_scale = 1.05;
perturbed = bed_supported_v1_parameter_override(p, override);
q = deg2rad([7;20]);
nominal_map = single_arm_v2_force_map(q, zeros(2,1), p);
perturbed_map = single_arm_v2_force_map(q, zeros(2,1), perturbed);
delta_sc = perturbed.sc-p.sc;
verifyEqual(testCase, perturbed_map.A-nominal_map.A, ...
    [0, delta_sc; 0, -delta_sc], 'AbsTol', 1e-13);
end


function testCombinedCasesAreDeterministic(testCase)
p = testCase.TestData.p;
config = testCase.TestData.config;
first = bed_supported_v1_robust_force_margin_sensitivity(p, config);
second = bed_supported_v1_robust_force_margin_sensitivity(p, config);
verifyEqual(testCase, first.combined_cases, second.combined_cases);
verifyEqual(testCase, first.combined_rows, second.combined_rows);
end


function override = identity_override()
override = struct('mass_scale', 1, 'lc1_scale', 1, 'lc2_scale', 1, ...
    'K_scale', 1, 'q_rest_offset_rad', zeros(2, 1), 'sc_scale', 1);
end
