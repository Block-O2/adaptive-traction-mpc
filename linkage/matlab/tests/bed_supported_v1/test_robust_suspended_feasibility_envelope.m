function tests = test_robust_suspended_feasibility_envelope
%TEST_ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE Quasistatic contract tests.
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75);
uncertainty = bed_supported_v1_registered_uncertainty_set(p);
bed_config = bed_supported_v1_config(200, 10, "nominal");
calibration = bed_supported_v1_calibrate_hip_height(p, bed_config);
config = bed_supported_v1_robust_envelope_config();
config.force_bounds_N = 200;
config.tube_caps_deg = [0, 10];
config.robust_thresholds_N = 0;
config.progress_step = 0.25;
config.candidate_step_deg = 5;
config.refined_progress_step = 0.05;
config.refined_candidate_step_deg = 2.5;
config.boundary_window_s = 0.25;
study = bed_supported_v1_robust_suspended_envelope(p, config);
testCase.TestData.p = p;
testCase.TestData.uncertainty = uncertainty;
testCase.TestData.bed_config = bed_config;
testCase.TestData.calibration = calibration;
testCase.TestData.config = config;
testCase.TestData.study = study;
end


function testOutboundPathEndpoints(testCase)
path = bed_supported_v1_geometric_outbound_path([0, 1]);
verifyEqual(testCase, rad2deg(path.q(:,1)), [5;10], 'AbsTol', 1e-12);
verifyEqual(testCase, rad2deg(path.q(:,2)), [45;84], 'AbsTol', 1e-12);
end


function testStrictTubeCandidateEqualsPath(testCase)
tube = testCase.TestData.study.tubes( ...
    [testCase.TestData.study.tubes.cap_deg] == 0);
for index = 1:numel(tube.samples)
    verifyEqual(testCase, tube.samples(index).robust.q_deg, ...
        tube.samples(index).q_path_deg, 'AbsTol', 1e-10);
end
end


function testNominalKnownStartDiagnostic(testCase)
point = bed_supported_v1_force_margin_point(deg2rad([5;10]), ...
    testCase.TestData.p, 200, 1e-12);
verifyEqual(testCase, point.F_parallel_N, -315.030, 'AbsTol', 0.01);
verifyEqual(testCase, point.F_perp_N, 21.011, 'AbsTol', 0.01);
verifyEqual(testCase, point.force_norm_2_N, 315.730, 'AbsTol', 0.01);
end


function testRobustMarginNeverExceedsNominal(testCase)
robust = bed_supported_v1_robust_hold_point(deg2rad([25;47]), ...
    testCase.TestData.p, testCase.TestData.uncertainty, ...
    [80,120,200], 1e-12);
verifyLessThanOrEqual(testCase, robust.force_margin_N, ...
    robust.nominal.force_margin_N+1e-12);
end


function testForceBoundShiftIsExact(testCase)
robust = bed_supported_v1_robust_hold_point(deg2rad([25;47]), ...
    testCase.TestData.p, testCase.TestData.uncertainty, ...
    [80,120,200], 1e-12);
verifyEqual(testCase, diff(robust.force_margin_N), [40,80], ...
    'AbsTol', 1e-12);
end


function testSoftActiveCandidateCannotBeRecommended(testCase)
for tube = testCase.TestData.study.tubes
    verifyFalse(testCase, any(arrayfun(@(x) ...
        x.nominal.soft_limit_active || x.robust.soft_limit_active || ...
        (x.supported_robust.found && ...
        x.supported_robust.soft_limit_active), tube.samples)));
end
end


function testInitialBedAvailabilityReproducesCalibration(testCase)
study = testCase.TestData.study;
strict = study.tubes([study.tubes.cap_deg] == 0);
verifyEqual(testCase, strict.samples(1).path_bed_total_force_N, ...
    testCase.TestData.calibration.bed.total_normal_force_N, ...
    'AbsTol', 1e-10);
verifyGreaterThan(testCase, strict.samples(1).path_bed_total_force_N, ...
    testCase.TestData.bed_config.contact_force_threshold_N);
end


function testOverlapClassificationIsDeterministic(testCase)
s = 0:0.1:0.5;
bed = [true,true,true,true,false,false];
robot = [-2,1,3,4,5,6];
supported = [-Inf,1,2,3,-Inf,-Inf];
first = bed_supported_v1_transfer_window_classify( ...
    s, bed, robot, supported, 0);
second = bed_supported_v1_transfer_window_classify( ...
    s, bed, robot, supported, 0);
verifyEqual(testCase, first, second);
verifyEqual(testCase, first.label, ...
    "QUASISTATIC_TRANSFER_WINDOW_EXISTS");
verifyEqual(testCase, [first.overlap_start_s, first.overlap_end_s], ...
    [0.1,0.3], 'AbsTol', 1e-12);
end


function testSupportGapClassificationIsDeterministic(testCase)
s = 0:0.1:0.5;
bed = [true,true,false,false,false,false];
robot = [-3,-2,-1,1,2,3];
supported = -Inf(size(s));
result = bed_supported_v1_transfer_window_classify( ...
    s, bed, robot, supported, 0);
verifyTrue(testCase, result.support_gap);
verifyEqual(testCase, result.label, "SUPPORT_GAP");
verifyEqual(testCase, result.bed_support_end_s, 0.1, 'AbsTol', 1e-12);
verifyEqual(testCase, result.robot_entry_s, 0.3, 'AbsTol', 1e-12);
end


function testBoundaryRefinementConvergenceRecorded(testCase)
config = bed_supported_v1_robust_envelope_config();
config.force_bounds_N = 200;
config.tube_caps_deg = 0;
config.robust_thresholds_N = 0;
study = bed_supported_v1_robust_suspended_envelope( ...
    testCase.TestData.p, config);
details = study.boundary_details;
reached = details.reached;
verifyTrue(testCase, any(reached));
verifyTrue(testCase, all(isfinite(details.refined_entry_s(reached))));
verifyLessThanOrEqual(testCase, ...
    max(details.convergence_q2_delta_deg(reached)), ...
    config.convergence_q2_tolerance_deg);
verifyLessThanOrEqual(testCase, ...
    max(details.convergence_margin_delta_N(reached)), ...
    config.convergence_margin_tolerance_N);
end


function testNominalInputsRemainImmutable(testCase)
p = testCase.TestData.p;
config = testCase.TestData.config;
p_before = p;
config_before = config;
bed_supported_v1_robust_suspended_envelope(p, config);
verifyEqual(testCase, p, p_before);
verifyEqual(testCase, config, config_before);
end
