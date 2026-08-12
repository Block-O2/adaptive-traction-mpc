function tests = test_near_extension_force_mode_feasibility
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75.0);
study = single_arm_near_extension_force_mode_scan( ...
    p, 0:1:80, 1:1:30, [80, 120, 200], 1e-12);
testCase.TestData.p = p;
testCase.TestData.study = study;
end


function testExtendedKneeRankDeficient(testCase)
point = single_arm_quasistatic_hold_point( ...
    deg2rad([25; 0]), testCase.TestData.p, [80, 120, 200], 1e-12);
verifyTrue(testCase, point.rank_deficient);
verifyEqual(testCase, point.svd_details.rank, 1);
verifyTrue(testCase, all(isnan(point.force_local)));
end


function testExactForceResidualAtNonsingularPosture(testCase)
point = single_arm_quasistatic_hold_point( ...
    deg2rad([18; 12]), testCase.TestData.p, [80, 120, 200], 1e-12);
verifyLessThan(testCase, point.torque_residual_norm, 1e-10);
verifyEqual(testCase, point.mapping.A*point.force_local, ...
    point.holding_torque, 'AbsTol', 1e-10);
end


function testFrozenStartStaticForceReproduced(testCase)
point = single_arm_quasistatic_hold_point( ...
    deg2rad([5; 10]), testCase.TestData.p, [80, 120, 200], 1e-12);
verifyEqual(testCase, point.force_norm, 315.729763678, 'AbsTol', 1e-6);
end


function testParallelObjectiveIsGridMinimum(testCase)
study = testCase.TestData.study;
grid_values = abs(study.atlas.F_parallel(2:end, :));
verifyEqual(testCase, abs(study.parallel_optimum.F_parallel)', ...
    min(grid_values, [], 2), 'AbsTol', 1e-12);
end


function testBoundedForceSupportIdentity(testCase)
p = testCase.TestData.p;
q = deg2rad([12, 25; 5, 20]);
path = single_arm_quasistatic_path_support( ...
    q, [0, 1], p, [80, 120, 200], 1e-12);
for index = 1:size(q, 2)
    mapping = single_arm_v2_force_map(q(:, index), zeros(2, 1), p);
    for bound_index = 1:numel(path.component_bounds_N)
        reconstructed = mapping.A*path.robot_force(:, index, bound_index)+ ...
            path.support_torque(:, index, bound_index);
        verifyEqual(testCase, reconstructed, path.holding_torque(:, index), ...
            'AbsTol', 1e-12);
    end
end
end
