function tests = test_single_arm_quasistatic_feasibility_atlas
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75.0);
bounds = [80, 120, 200];
atlas = single_arm_quasistatic_atlas_grid( ...
    p, 0:1:80, 0:1:100, bounds, 1e-12);
testCase.TestData.p = p;
testCase.TestData.bounds = bounds;
testCase.TestData.atlas = atlas;
end


function testExtendedKneeIsRankDeficient(testCase)
p = testCase.TestData.p;
point = single_arm_quasistatic_hold_point( ...
    deg2rad([25; 0]), p, testCase.TestData.bounds, 1e-12);
verifyTrue(testCase, point.rank_deficient);
verifyEqual(testCase, point.svd_details.rank, 1);
verifyTrue(testCase, all(isnan(point.force_local)));
verifyEqual(testCase, point.sigma_min, 0, 'AbsTol', 0);
verifyEqual(testCase, point.condition_number, Inf);
verifyFalse(testCase, any(point.exact_feasible));
end


function testNonsingularForceReconstructsHoldingTorque(testCase)
p = testCase.TestData.p;
point = single_arm_quasistatic_hold_point( ...
    deg2rad([31; 47]), p, [], 1e-12);
verifyEqual(testCase, point.mapping.A*point.force_local, ...
    point.holding_torque, 'AbsTol', 1e-11);
end


function testNonsingularTorqueResidualTolerance(testCase)
atlas = testCase.TestData.atlas;
valid = ~atlas.rank_deficient;
verifyLessThan(testCase, max(atlas.torque_residual_norm(valid)), 1e-9);
end


function testStartingStaticForceMatchesFrozenEvidence(testCase)
p = testCase.TestData.p;
point = single_arm_quasistatic_hold_point( ...
    deg2rad([5; 10]), p, [], 1e-12);
verifyEqual(testCase, point.force_norm, 315.730, 'AbsTol', 0.05);
end


function testAllNonsingularGridResultsAreFinite(testCase)
atlas = testCase.TestData.atlas;
valid = ~atlas.rank_deficient;
signals = [atlas.F_parallel(valid); atlas.F_perp(valid); ...
    atlas.force_norm(valid); atlas.torque_residual_norm(valid); ...
    atlas.sigma_min(valid); atlas.condition_number(valid); ...
    atlas.det_A(valid); atlas.gravity_torque(:); ...
    atlas.passive_torque_left(:); atlas.holding_torque(:); ...
    atlas.bounded_force(:); atlas.bounded_residual_norm(:)];
verifyTrue(testCase, all(isfinite(signals)));
verifyTrue(testCase, all(atlas.sigma_min(valid) > 0));
end


function testFeasibilityMasksMatchComponentBounds(testCase)
atlas = testCase.TestData.atlas;
for bound_index = 1:numel(atlas.component_bounds_N)
    limit = atlas.component_bounds_N(bound_index);
    expected = ~atlas.rank_deficient & ...
        abs(atlas.F_parallel) <= limit+1e-10 & ...
        abs(atlas.F_perp) <= limit+1e-10;
    verifyEqual(testCase, atlas.feasible(:, :, bound_index), expected);
end
end
