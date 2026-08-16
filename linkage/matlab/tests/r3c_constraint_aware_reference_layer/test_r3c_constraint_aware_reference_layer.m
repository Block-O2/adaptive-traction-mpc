function tests=test_r3c_constraint_aware_reference_layer
%TEST_R3C_CONSTRAINT_AWARE_REFERENCE_LAYER Transparent R3C contracts.
tests=functiontests(localfunctions);
end


function setupOnce(testCase)
p=human_two_link_v2_parameters(1.72,75);base=dynamic_robust_v1_config();
testCase.TestData.nominal=p;testCase.TestData.base=base;
testCase.TestData.config=r3c_constraint_aware_config(base,p,.20);
end


function testEngineeringBuffersAreExplicitAndDerived(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
verifyEqual(testCase,c.r3c_warning_buffer_rad,.20*min(p.soft_limit_margin));
verifyEqual(testCase,c.r3c_hold_buffer_rad,.5*c.r3c_warning_buffer_rad);
verifyEqual(testCase,c.r3c_resume_buffer_rad,1.5*c.r3c_warning_buffer_rad);
verifyTrue(testCase,c.r3c_engineering_buffer_not_clinical);
verifyFalse(testCase,c.r3c_formal_safety_guarantee);
end


function testNoInterventionWhenComfortablySafe(testCase)
[state,signals,c]=fixture(testCase,deg2rad(4),false,true);
state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.mode,"NORMAL");verifyEqual(testCase,state.alpha,1);
end


function testSlowdownTriggersBeforeViolation(testCase)
[state,signals,c]=fixture(testCase,.9*testCase.TestData.config.r3c_warning_buffer_rad,false,true);
state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.mode,"SLOWDOWN");
verifyGreaterThan(testCase,signals.predicted_min_soft_clearance_rad,0);
end


function testActionScalingIsContinuousAndBounded(testCase)
[state,signals,c]=fixture(testCase,candidate_mid(testCase),false,true);
state.mode="SLOWDOWN";state=r3c_safety_step(state,signals,c);
verifyGreaterThan(testCase,state.alpha,0);verifyLessThan(testCase,state.alpha,1);
signals.predicted_min_soft_clearance_rad=signals.predicted_min_soft_clearance_rad+1e-9;
next=r3c_safety_step(state,signals,c);
verifyLessThan(testCase,abs(next.alpha-state.alpha),1e-5);
end


function testHoldPreventsUnsafeProgress(testCase)
[state,signals,c]=fixture(testCase,.9*testCase.TestData.config.r3c_hold_buffer_rad,false,true);
state.mode="SLOWDOWN";state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.mode,"HOLD");verifyEqual(testCase,state.alpha,0);
end


function testNoSafeRecoveryClassifiesInfeasible(testCase)
[state,signals,c]=fixture(testCase,candidate_mid(testCase),false,false);
state.mode="HOLD";state.mode_time_s=c.r3c_hold_before_recovery_s;
state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.classification,"TASK_INFEASIBLE");
end


function testResumeRequiresRestoredMargin(testCase)
c0=testCase.TestData.config;
[state,signals,c]=fixture(testCase,c0.r3c_warning_buffer_rad,false,true);
state.mode="RECOVERY_REFERENCE";state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.mode,"RECOVERY_REFERENCE");
signals.current_min_soft_clearance_rad=c.r3c_resume_buffer_rad;
signals.predicted_min_soft_clearance_rad=c.r3c_resume_buffer_rad;
state=r3c_safety_step(state,signals,c);
verifyEqual(testCase,state.mode,"NORMAL");verifyTrue(testCase,state.resume_blending);
end


function testRecoveryReferenceInsideTubeAndRom(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
q=deg2rad([15;20]);path=q;tube=deg2rad([10;10]);
selected=r3c_select_recovery_reference(q,zeros(2,1),path,tube, ...
    zeros(2,1),zeros(2,1),p,c);
verifyTrue(testCase,selected.found);
verifyLessThanOrEqual(testCase,abs(selected.q-path),tube+100*eps);
lower=p.q_min+p.soft_limit_margin;upper=p.q_max-p.soft_limit_margin;
verifyGreaterThanOrEqual(testCase,selected.q,lower-c.soft_margin_tolerance_rad);
verifyLessThanOrEqual(testCase,selected.q,upper+c.soft_margin_tolerance_rad);
end


function testRecoveryForceBoundRemainsHard(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
q=deg2rad([15;20]);selected=r3c_select_recovery_reference(q,zeros(2,1), ...
    q,deg2rad([10;10]),zeros(2,1),zeros(2,1),p,c);
verifyLessThanOrEqual(testCase,selected.force_N,c.u_max(:)+c.bound_tolerance_N);
verifyGreaterThanOrEqual(testCase,selected.force_N,c.u_min(:)-c.bound_tolerance_N);
end


function testNoHiddenPlantStateClipping(testCase)
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
source=fileread(fullfile(root,'src','dynamic_robust_load_transfer_v1', ...
    'simulate_dynamic_robust_load_transfer_v1.m'));
verifyFalse(testCase,contains(source,'x(1:2,index+1)=min'));
verifyFalse(testCase,contains(source,'x(1:2,index+1)=max'));
end


function testNominalModelIsNotSilentlyReplaced(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;c.max_time_s=1.2;
cases=dynamic_robust_v1_oracle_case_set(p);plant=cases(4).plant_parameters;
z=bed_supported_v1_calibrate_hip_height(p,c);plan=hybrid_tube_v1_build_plan(p,c);
init=dynamic_robust_v1_initial_admissibility(p,plant,z,c,p);
a=dynamic_robust_v1_adaptive_config(c);
r=simulate_dynamic_robust_load_transfer_v1(c,p,plant,plan,z,init,p,a);
verifyTrue(testCase,r.r3c_enabled);verifyTrue(testCase,r.adaptive_enabled);
verifyEqual(testCase,r.controller_model_initial_parameters,p);
verifyEqual(testCase,r.identifier_state.accepted_updates,0);
end


function testEstimatorConfigurationUnchanged(testCase)
base=testCase.TestData.base;before=dynamic_robust_v1_adaptive_config(base);
c=r3c_constraint_aware_config(base,testCase.TestData.nominal,.20); %#ok<NASGU>
after=dynamic_robust_v1_adaptive_config(base);
verifyEqual(testCase,after,before);
end


function testScientificTaskAndConstraintConfigurationUnchanged(testCase)
base=testCase.TestData.base;c=testCase.TestData.config;
fields={'Kp','Kd','u_min','u_max','du_max','force_bound_N', ...
    'contact_force_threshold_N','max_time_s','dt','tube_cap_deg'};
for index=1:numel(fields),verifyEqual(testCase,c.(fields{index}),base.(fields{index}));end
end


function [state,signals,c]=fixture(testCase,predicted,force_infeasible,recovery)
c=testCase.TestData.config;state=r3c_safety_initial_state([0;0]);
signals=struct('time_s',1,'progress',.2, ...
    'current_min_soft_clearance_rad',max(predicted,c.r3c_hold_buffer_rad), ...
    'predicted_min_soft_clearance_rad',predicted, ...
    'predicted_q2_clearance_rad',predicted, ...
    'force_infeasible',force_infeasible,'recovery_feasible',recovery);
end


function value=candidate_mid(testCase)
c=testCase.TestData.config;
value=.5*(c.r3c_hold_buffer_rad+c.r3c_warning_buffer_rad);
end
