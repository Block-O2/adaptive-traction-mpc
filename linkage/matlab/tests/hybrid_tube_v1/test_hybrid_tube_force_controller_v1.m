function tests = test_hybrid_tube_force_controller_v1
%TEST_HYBRID_TUBE_FORCE_CONTROLLER_V1 Mechanical and contract tests.
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75);
exact = hybrid_tube_v1_config(200, 0);
exact.plan_node_count = 41;
wide = hybrid_tube_v1_config(200, 10);
wide.plan_node_count = 41;
wide.candidate_step_deg = 2;
testCase.TestData.p = p;
testCase.TestData.exact = exact;
testCase.TestData.wide = wide;
testCase.TestData.exact_plan = hybrid_tube_v1_build_plan(p, exact);
testCase.TestData.wide_plan = hybrid_tube_v1_build_plan(p, wide);
end


function testProgressMonotoneAndBounded(testCase)
p = testCase.TestData.p; config = testCase.TestData.wide;
plan = testCase.TestData.wide_plan;
state = struct('s', 0, 's_dot', 0, 's_ddot', 0, ...
    'pause_time', 0, 'status', "RUNNING", ...
    'previous_force', plan.force_local(:, 1));
history = zeros(1, 50);
q = plan.q(:, 1);
for k = 1:numel(history)
    [state, reference] = hybrid_tube_v1_manager_step( ...
        state, plan, q, zeros(2, 1), p, config);
    history(k) = state.s;
    q = reference.q;
end
verifyGreaterThanOrEqual(testCase, min(diff(history)), -1e-14);
verifyGreaterThanOrEqual(testCase, min(history), 0);
verifyLessThanOrEqual(testCase, max(history), 1);
end


function testZeroTubePreservesFrozenPath(testCase)
plan = testCase.TestData.exact_plan;
verifyEqual(testCase, plan.q, plan.nominal.q, 'AbsTol', 1e-13);
end


function testGovernedPathStaysInsideTube(testCase)
plan = testCase.TestData.wide_plan;
s = linspace(0, 1, 401);
for k = 1:numel(s)
    sample = hybrid_tube_v1_plan_sample(plan, s(k));
    verifyLessThanOrEqual(testCase, abs(sample.deviation), ...
        sample.tube_rad+deg2rad(0.05));
end
end


function testReferenceDerivativesAreFiniteAndContinuous(testCase)
plan = testCase.TestData.wide_plan;
s = linspace(0, 1, 801);
q = zeros(2, numel(s)); qs = q; qss = q;
for k = 1:numel(s)
    sample = hybrid_tube_v1_plan_sample(plan, s(k));
    q(:, k) = sample.q; qs(:, k) = sample.q_s; qss(:, k) = sample.q_ss;
end
verifyTrue(testCase, all(isfinite([q(:); qs(:); qss(:)])));
verifyLessThan(testCase, max(vecnorm(diff(q, 1, 2), 2, 1)), 0.1);
verifyLessThan(testCase, max(vecnorm(diff(qs, 1, 2), 2, 1)), 2.0);
verifyLessThan(testCase, max(vecnorm(diff(qss, 1, 2), 2, 1)), 50.0);
end


function testForceMapResidualAndBoundsAreExplicit(testCase)
p = testCase.TestData.p; config = testCase.TestData.wide;
sample = hybrid_tube_v1_plan_sample(testCase.TestData.wide_plan, 0.5);
point = single_arm_quasistatic_hold_point(sample.q, p, ...
    config.force_bound_N, config.svd_relative_tolerance);
verifyEqual(testCase, point.mapping.A*point.force_local, ...
    point.holding_torque, 'AbsTol', 1e-9);
verifyEqual(testCase, point.mapping.A*point.bounded_force(:, 1)- ...
    point.bounded_residual(:, 1), point.holding_torque, 'AbsTol', 1e-9);
verifyLessThanOrEqual(testCase, max(abs(point.bounded_force(:, 1))), ...
    config.force_bound_N+1e-10);
end


function testTerminalClassification(testCase)
p = testCase.TestData.p; config = testCase.TestData.wide;
plan = testCase.TestData.wide_plan;
sample = hybrid_tube_v1_plan_sample(plan, 1);
state = struct('s', 1, 's_dot', 0, 's_ddot', 0, ...
    'pause_time', 0, 'status', "RUNNING", ...
    'previous_force', sample.force_local);
[state, ~] = hybrid_tube_v1_manager_step(state, plan, sample.q, ...
    zeros(2, 1), p, config);
verifyEqual(testCase, state.status, "TASK_COMPLETE");
end


function testPlanRespectsRomAndAvoidsSoftLimit(testCase)
p = testCase.TestData.p; plan = testCase.TestData.wide_plan;
verifyGreaterThanOrEqual(testCase, min(plan.q-p.q_min, [], 'all'), -1e-12);
verifyGreaterThanOrEqual(testCase, min(p.q_max-plan.q, [], 'all'), -1e-12);
for k = 1:size(plan.q, 2)
    [~, details] = human_two_link_v2_passive_torque( ...
        plan.q(:, k), zeros(2, 1), p);
    verifyFalse(testCase, any(details.soft.active));
end
end


function testStrictStartReproducesHighStaticForce(testCase)
p = testCase.TestData.p;
point = single_arm_quasistatic_hold_point(deg2rad([5; 10]), p, ...
    200, 1e-12);
verifyEqual(testCase, point.force_norm, 315.730, 'AbsTol', 0.02);
end


function testWideTubeMovesTowardLowerForceAtStart(testCase)
p = testCase.TestData.p;
strict = single_arm_quasistatic_hold_point(deg2rad([5; 10]), p, [], 1e-12);
sample = hybrid_tube_v1_plan_sample(testCase.TestData.wide_plan, 0);
wide = single_arm_quasistatic_hold_point(sample.q, p, [], 1e-12);
verifyLessThan(testCase, abs(wide.F_parallel), abs(strict.F_parallel));
verifyLessThan(testCase, wide.force_norm, strict.force_norm);
end


function testInfeasibleSuspendedStartStopsBeforePlantDrift(testCase)
p = testCase.TestData.p;
config = hybrid_tube_v1_config(200, 10);
config.plan_node_count = 41;
config.candidate_step_deg = 2;
plan = testCase.TestData.wide_plan;
result = simulate_hybrid_tube_force_controller_v1(config, p, plan);
verifyEqual(testCase, result.metrics.terminal_state, ...
    "INITIAL_SUPPORT_REQUIRED");
verifyEqual(testCase, numel(result.t), 1);
verifyEqual(testCase, rad2deg(result.x(1:2, 1)), [5; 10], ...
    'AbsTol', 1e-12);
verifyFalse(testCase, result.metrics.initial_hold_feasible);
verifyEqual(testCase, result.metrics.initial_required_force_norm_N, ...
    315.730, 'AbsTol', 0.02);
end
