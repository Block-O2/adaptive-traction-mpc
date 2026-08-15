function tests = test_bed_supported_load_transfer_v1
%TEST_BED_SUPPORTED_LOAD_TRANSFER_V1 Mechanics and hybrid guard tests.
tests = functiontests(localfunctions);
end


function setupOnce(testCase)
p = human_two_link_v2_parameters(1.72, 75);
config = bed_supported_v1_config(200, 10, "nominal");
calibration = bed_supported_v1_calibrate_hip_height(p, config);
force_margin_study = bed_supported_v1_force_margin_map( ...
    p, [5, 10], [80, 120, 200], 0.1, config.svd_relative_tolerance);
testCase.TestData.p = p;
testCase.TestData.config = config;
testCase.TestData.calibration = calibration;
testCase.TestData.force_margin_study = force_margin_study;
end


function testQ1ZeroIsHorizontal(testCase)
p = testCase.TestData.p;
g = human_two_link_v2_kinematics([0;0], p);
verifyEqual(testCase, g.knee, [p.L1;0], 'AbsTol', 1e-14);
end


function testShankAngleConvention(testCase)
p = testCase.TestData.p; q = deg2rad([30;20]);
g = human_two_link_v2_kinematics(q, p);
verifyEqual(testCase, g.phi, q(1)-q(2), 'AbsTol', 1e-14);
end


function testInitialPostureIsNearlyHorizontal(testCase)
p = testCase.TestData.p;
g = human_two_link_v2_kinematics(deg2rad([5;10]), p);
verifyLessThan(testCase, abs(g.knee(2))/p.L1, sin(deg2rad(6)));
verifyLessThan(testCase, abs(g.ankle(2))/(p.L1+p.L2), sin(deg2rad(6)));
end


function testBedOffExactlyRecoversSuspendedDynamics(testCase)
p = testCase.TestData.p; c = testCase.TestData.config; c.bed_enabled = false;
x = [deg2rad([31;46]); 0.2; -0.1]; u = [37;-22];
[a, old] = single_arm_v2_endpoint_dynamics(x, u, p);
[b, added] = bed_supported_v1_dynamics(x, u, 0.1, p, c);
verifyEqual(testCase, b, a, 'AbsTol', 1e-13);
verifyEqual(testCase, added.tau_bed_Nm, zeros(2,1), 'AbsTol', 0);
verifyEqual(testCase, added.ddq, old.ddq, 'AbsTol', 1e-13);
end


function testBedForceIsUnilateral(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
bed = bed_supported_v1_contact(deg2rad([5;10]), [0.3;-0.2], ...
    testCase.TestData.calibration.h_hip_m, p, c);
verifyGreaterThanOrEqual(testCase, min(bed.normal_force_N), 0);
end


function testNoContactMeansZeroForce(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
bed = bed_supported_v1_contact(deg2rad([45;84]), [0;0], 1.0, p, c);
verifyEqual(testCase, bed.normal_force_N, zeros(size(bed.normal_force_N)), ...
    'AbsTol', 0);
end


function testBedGeneralizedTorqueIsJacobianSum(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
bed = bed_supported_v1_contact(deg2rad([5;10]), [0.1;-0.05], ...
    testCase.TestData.calibration.h_hip_m, p, c);
tau = zeros(2,1);
for k = 1:numel(bed.normal_force_N)
    tau = tau+bed.points.J(:,:,k)'*[0;bed.normal_force_N(k)];
end
verifyEqual(testCase, bed.generalized_torque_Nm, tau, 'AbsTol', 1e-13);
end


function testInitialSupportedEquilibriumCalibration(testCase)
z = testCase.TestData.calibration;
verifyLessThan(testCase, norm(z.balance_residual_Nm), 1e-10);
verifyGreaterThan(testCase, z.bed.total_normal_force_N, 0.5*z.leg_weight_N);
verifyLessThan(testCase, z.robot_force_norm_N, 0.25*315.730);
end


function testControllerForceChangeRespectsSlew(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
z = testCase.TestData.calibration; q = z.q_initial_rad;
[u, ~] = bed_supported_v1_robot_controller(q, zeros(2,1), q, ...
    zeros(2,1), zeros(2,1), z.bed_generalized_torque_Nm, ...
    z.robot_force_N+[1;-1], p, c, 1);
verifyLessThanOrEqual(testCase, max(abs(u-(z.robot_force_N+[1;-1]))), ...
    max(c.du_max)*c.dt+1e-12);
end


function testLiftoffGuardRequiresRobotOnlyFeasibility(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
bad = bed_supported_v1_robot_only_hold(deg2rad([5;10]), p, c);
good = bed_supported_v1_robot_only_hold(deg2rad([45;84]), p, c);
verifyFalse(testCase, bad.feasible);
verifyTrue(testCase, good.feasible);
end


function testRecontactRestoresBedForce(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
h = testCase.TestData.calibration.h_hip_m;
lifted = bed_supported_v1_contact(deg2rad([45;84]), [0;0], h, p, c);
returned = bed_supported_v1_contact(deg2rad([5;10]), [0;0], h, p, c);
verifyEqual(testCase, lifted.total_normal_force_N, 0, 'AbsTol', 1e-12);
verifyGreaterThan(testCase, returned.total_normal_force_N, ...
    c.contact_force_threshold_N);
end


function testReleaseRequiresStableExternalSupport(testCase)
z = testCase.TestData.calibration; c = testCase.TestData.config;
verifyGreaterThan(testCase, z.bed.total_normal_force_N, ...
    c.contact_force_threshold_N);
verifyGreaterThan(testCase, sum(z.bed.active), 0);
end


function testDynamicsBalanceResidual(testCase)
p = testCase.TestData.p; c = testCase.TestData.config;
x = [deg2rad([7;14]);0.03;-0.02];
[~, d] = bed_supported_v1_dynamics(x, [20;-10], ...
    testCase.TestData.calibration.h_hip_m, p, c);
verifyLessThan(testCase, norm(d.balance_residual_Nm), 1e-10);
end


function testPrepositionCandidateStaysAtZeroTaskProgress(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;
c.plan_node_count=41;c.candidate_step_deg=2;c.max_time_s=1;
z=testCase.TestData.calibration;plan=hybrid_tube_v1_build_plan(p,c);
r=simulate_bed_supported_load_transfer_v1(c,p,plan,z);
indices=r.mode=="SUPPORTED_PREPOSITION";
verifyTrue(testCase,any(indices));
verifyEqual(testCase,r.progress(indices),zeros(1,sum(indices)),'AbsTol',0);
end


function testPrepositionCandidateIsInsideTubeAndRom(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;z=testCase.TestData.calibration;
target=bed_supported_v1_preposition_target(p,c,z.h_hip_m,z.robot_force_N);
verifyTrue(testCase,target.found);
verifyLessThanOrEqual(testCase,abs(target.q-target.nominal_q),target.tube_rad+1e-12);
verifyGreaterThanOrEqual(testCase,target.q,p.q_min);
verifyLessThanOrEqual(testCase,target.q,p.q_max);
end


function testBedSupportedAndRobotOnlyFeasibilityAreDistinct(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;z=testCase.TestData.calibration;
hold=bed_supported_v1_robot_only_hold(z.q_initial_rad,p,c);
verifyLessThan(testCase,norm(z.balance_residual_Nm),1e-10);
verifyFalse(testCase,hold.feasible);
verifyGreaterThan(testCase,z.bed.total_normal_force_N,c.contact_force_threshold_N);
end


function testMissingCandidateBlocksLoadTakeover(testCase)
p=testCase.TestData.p;c=bed_supported_v1_config(80,5,"nominal");
c.plan_node_count=21;c.candidate_step_deg=2;c.max_time_s=1;
z=bed_supported_v1_calibrate_hip_height(p,c);plan=hybrid_tube_v1_build_plan(p,c);
r=simulate_bed_supported_load_transfer_v1(c,p,plan,z);
verifyEqual(testCase,r.terminal_state,"PREPOSITION_INFEASIBLE");
verifyFalse(testCase,any(r.mode=="LOAD_TAKEOVER"));
verifyFalse(testCase,any(r.mode=="LIFTOFF"));
end


function testTakeoverLossDoesNotContinueToLiftoff(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;
c.plan_node_count=41;c.candidate_step_deg=2;c.max_time_s=10;
z=testCase.TestData.calibration;plan=hybrid_tube_v1_build_plan(p,c);
r=simulate_bed_supported_load_transfer_v1(c,p,plan,z);
if any(r.mode=="LOAD_TAKEOVER") && ...
        any(~r.robot_only_feasible(r.mode=="LOAD_TAKEOVER"))
    verifyFalse(testCase,any(r.mode=="SUSPENDED_MOTION"));
end
end


function testLiftoffSamplesSatisfyGuards(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;
c.plan_node_count=41;c.candidate_step_deg=2;c.max_time_s=10;
z=testCase.TestData.calibration;plan=hybrid_tube_v1_build_plan(p,c);
r=simulate_bed_supported_load_transfer_v1(c,p,plan,z);
index=find(r.mode=="SUSPENDED_MOTION",1,'first');
if ~isempty(index)
    verifyLessThanOrEqual(testCase,r.bed_force_N(index),c.contact_force_threshold_N);
    verifyTrue(testCase,r.robot_only_feasible(index));
end
end


function testReferenceAndForceCommandsRemainContinuous(testCase)
p=testCase.TestData.p;c=testCase.TestData.config;
c.plan_node_count=41;c.candidate_step_deg=2;c.max_time_s=4;
z=testCase.TestData.calibration;plan=hybrid_tube_v1_build_plan(p,c);
r=simulate_bed_supported_load_transfer_v1(c,p,plan,z);
verifyLessThanOrEqual(testCase,max(abs(diff(r.robot_force_N,1,2)),[],'all'), ...
    max(c.du_max)*c.dt+1e-9);
verifyLessThan(testCase,max(abs(diff(r.q_ref,1,2)),[],'all'),deg2rad(0.1));
end


function testForceMarginDefinition(testCase)
p = testCase.TestData.p;
point = bed_supported_v1_force_margin_point( ...
    deg2rad([7;20]), p, [80,120,200], 1e-12);
verifyEqual(testCase, point.force_margin_N, ...
    [80,120,200]-norm(point.force_local_N,Inf), 'AbsTol', 1e-12);
end


function testForceMarginExactTorqueResidual(testCase)
p = testCase.TestData.p;
point = bed_supported_v1_force_margin_point( ...
    deg2rad([7;20]), p, 200, 1e-12);
verifyLessThan(testCase, point.exact_torque_residual_norm_Nm, 1e-10);
verifyEqual(testCase, point.exact_torque_residual_Nm, ...
    zeros(2,1), 'AbsTol', 1e-10);
end


function testCurrentPrepositionForceIsReproduced(testCase)
p = testCase.TestData.p;
point = bed_supported_v1_force_margin_point( ...
    deg2rad([7;20]), p, 200, 1e-12);
verifyEqual(testCase, point.F_parallel_N, -190.48528, 'AbsTol', 1e-3);
end


function testDenseGridOptimumIsNoWorseThanCurrent(testCase)
study = testCase.TestData.force_margin_study;
tube = study.tubes([study.tubes.cap_deg] == 10);
bound_index = find(study.component_bounds_N == 200);
point = bed_supported_v1_force_margin_point(deg2rad([7;20]), ...
    testCase.TestData.p, 200, 1e-12);
verifyGreaterThanOrEqual(testCase, ...
    tube.best(bound_index).maximum_margin_N, ...
    point.force_margin_N-1e-12);
end


function testSoftLimitActiveSamplesAreNotRecommended(testCase)
study = testCase.TestData.force_margin_study;
for tube_index = 1:numel(study.tubes)
    tube = study.tubes(tube_index);
    verifyFalse(testCase, any(tube.robust_feasible & ...
        repmat(tube.soft_limit_active, 1, 1, ...
        numel(study.component_bounds_N)), 'all'));
    verifyFalse(testCase, any([tube.best.soft_limit_active]));
end
end
