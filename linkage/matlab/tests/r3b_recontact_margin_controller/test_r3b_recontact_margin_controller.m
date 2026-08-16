function tests=test_r3b_recontact_margin_controller
tests=functiontests(localfunctions);
end


function setupOnce(testCase)
nominal=human_two_link_v2_parameters(1.72,75);
base=dynamic_robust_v1_config();
config=r3b_recontact_margin_config(base,1.0);
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
testCase.TestData.nominal=nominal;
testCase.TestData.base=base;
testCase.TestData.config=config;
testCase.TestData.calibration=calibration;
end


function testPrimaryReserveDoesNotRedefineThresholdOrTimeout(testCase)
c=testCase.TestData.config;b=testCase.TestData.base;
verifyEqual(testCase,c.contact_force_threshold_N,2,'AbsTol',0);
verifyEqual(testCase,c.recontact_timeout_s,8,'AbsTol',0);
verifyEqual(testCase,c.r3b_contact_reserve_N,1,'AbsTol',0);
verifyEqual(testCase,c.r3b_contact_target_N,3,'AbsTol',0);
verifyTrue(testCase,c.r3b_engineering_reserve_not_clinical);
verifyEqual(testCase,c.u_min,b.u_min,'AbsTol',0);
verifyEqual(testCase,c.u_max,b.u_max,'AbsTol',0);
verifyEqual(testCase,c.tube_cap_deg,b.tube_cap_deg,'AbsTol',0);
end


function testZeroForceErrorLeavesCommandUnchanged(testCase)
[q,path,tube]=candidate(testCase);
[command,details]=r3b_recontact_margin_step(q,path,tube,3, ...
    testCase.TestData.nominal,testCase.TestData.calibration.h_hip_m, ...
    testCase.TestData.config);
verifyEqual(testCase,command,q,'AbsTol',1e-14);
verifyEqual(testCase,details.force_error_N,0,'AbsTol',0);
end


function testSubtargetForceMovesTowardHigherPredictedSupport(testCase)
[q,path,tube]=candidate(testCase);p=testCase.TestData.nominal;
c=testCase.TestData.config;h=testCase.TestData.calibration.h_hip_m;
before=bed_supported_v1_contact(q,zeros(2,1),h,p,c);
[command,details]=r3b_recontact_margin_step(q,path,tube, ...
    before.total_normal_force_N,p,h,c);
after=bed_supported_v1_contact(command,zeros(2,1),h,p,c);
verifyGreaterThanOrEqual(testCase,after.total_normal_force_N, ...
    before.total_normal_force_N-1e-10);
verifyGreaterThan(testCase,norm(details.force_gradient_N_rad),0.1);
end


function testReferenceRateIsBounded(testCase)
[q,path,tube]=candidate(testCase);c=testCase.TestData.config;
[command,details]=r3b_recontact_margin_step(q,path,tube,0, ...
    testCase.TestData.nominal,testCase.TestData.calibration.h_hip_m,c);
verifyLessThanOrEqual(testCase,norm(command-q), ...
    c.r3b_reference_rate_rad_s*c.dt+1e-14);
verifyLessThanOrEqual(testCase,norm(details.command_rate_rad_s), ...
    c.r3b_reference_rate_rad_s+1e-12);
end


function testCommandRemainsInsideTubeRomAndSoftZone(testCase)
[q,path,tube]=candidate(testCase);p=testCase.TestData.nominal;
c=testCase.TestData.config;h=testCase.TestData.calibration.h_hip_m;
for iteration=1:1000
    q=r3b_recontact_margin_step(q,path,tube,0,p,h,c);
end
verifyLessThanOrEqual(testCase,abs(q-path),tube+1e-12);
verifyGreaterThanOrEqual(testCase,q,p.q_min-1e-12);
verifyLessThanOrEqual(testCase,q,p.q_max+1e-12);
[~,passive]=human_two_link_v2_passive_torque(q,zeros(2,1),p);
verifyFalse(testCase,any(passive.soft.active));
end


function testR3BManagerDoesNotAcceptThresholdOnlyContact(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="RECONTACT";signals=manager_signals();
signals.bed_supported=true;signals.bed_absent=false;
signals.recontact_stable=false;
for iteration=1:ceil(c.contact_stable_duration_s/c.dt)+1
    [state,~]=dynamic_robust_v1_manager_step(state,signals,c);
end
verifyEqual(testCase,state.mode,"RECONTACT");
verifyEqual(testCase,state.classification,"RUNNING");
end


function testR3BManagerRequiresReserveDwell(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="RECONTACT";signals=manager_signals();
signals.bed_supported=true;signals.bed_absent=false;
signals.recontact_stable=true;
for iteration=1:ceil(c.contact_stable_duration_s/c.dt)
    [state,~]=dynamic_robust_v1_manager_step(state,signals,c);
end
verifyEqual(testCase,state.mode,"LOAD_RETURN");
end


function testBaselineManagerRetainsOriginalDwellContract(testCase)
c=testCase.TestData.base;state=dynamic_robust_v1_initial_state();
state.mode="RECONTACT";signals=manager_signals();
signals.bed_supported=true;signals.bed_absent=false;
signals.recontact_stable=false;
for iteration=1:ceil(c.contact_stable_duration_s/c.dt)
    [state,~]=dynamic_robust_v1_manager_step(state,signals,c);
end
verifyEqual(testCase,state.mode,"LOAD_RETURN");
end


function testUnsafePenetrationFailsWithoutChangingThreshold(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="RECONTACT";signals=manager_signals();
signals.bed_supported=true;signals.bed_absent=false;
signals.recontact_unsafe=true;
[state,~]=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.classification,"RECONTACT_FAILED");
verifyEqual(testCase,c.contact_force_threshold_N,2,'AbsTol',0);
end


function testEstimatorConfigurationIsUnchanged(testCase)
a=dynamic_robust_v1_adaptive_config(testCase.TestData.base);
b=dynamic_robust_v1_adaptive_config(testCase.TestData.config);
verifyEqual(testCase,a,b);
end


function testSimulatorContainsNoR3BPlantStateClipping(testCase)
path=which('simulate_dynamic_robust_load_transfer_v1');text=fileread(path);
verifyFalse(testCase,contains(text,'min(max(x'));
verifyFalse(testCase,contains(text,'max(min(x'));
verifyFalse(testCase,contains(text,'x(:,index+1)=min'));
end


function testMetricsSeparateControlledAndGlobalBedLoad(testCase)
r=struct();r.config=struct('dt',.1);r.t=0:.1:.5;
r.active_contacts=[0 1 1 1 1 1];
r.mode=["SUSPENDED_MOTION","RECONTACT","RECONTACT", ...
    "LOAD_RETURN","BED_SUPPORTED_RETURN","TASK_COMPLETE"];
r.recontact_stage=["FIRST_CONTACT","CONTROLLED_CONTACT_BUILD", ...
    "STABLE_CONTACT","LOAD_RETURN","NOT_ACTIVE","NOT_ACTIVE"];
r.recontact_stable=[false false true true true true];
r.max_penetration_m=[0 .001 .0011 .0012 .02 .02];
r.contact_margin_N=[-2 0 .9 1 98 98];r.bed_force_N=r.contact_margin_N+2;
r.minimum_gap_velocity_m_s=zeros(1,6);
r.recontact_stable_time_s=[0 0 .1 .2 .3 .4];
r.robot_force_N=zeros(2,6);r.force_rate_N_s=zeros(2,6);
r.soft_limit_active=[false false false false true false];
r.rom_violation=false(1,6);r.recontact_reference_offset_rad=zeros(2,6);
r.task_s=[.7 .75 .75 .75 .8 1];r.terminal_state="TASK_COMPLETE";
m=r3b_recontact_metrics(r);
verifyEqual(testCase,m.peak_bed_force_N,3,'AbsTol',0);
verifyEqual(testCase,m.global_peak_bed_force_N,100,'AbsTol',0);
verifyEqual(testCase,m.maximum_penetration_m,.0012,'AbsTol',0);
verifyEqual(testCase,m.global_maximum_penetration_m,.02,'AbsTol',0);
verifyEqual(testCase,m.controlled_contact_soft_limit_samples,0);
verifyEqual(testCase,m.soft_limit_samples,1);
end


function [q,path,tube]=candidate(testCase)
c=testCase.TestData.config;p=testCase.TestData.nominal;
uncertainty=bed_supported_v1_registered_uncertainty_set(p);
selected=dynamic_robust_v1_select_recontact_posture(.75,[0;0],p, ...
    uncertainty,testCase.TestData.calibration.h_hip_m,c);
assert(selected.found);
q=selected.q;path=selected.path_q;tube=selected.tube_rad;
end


function signals=manager_signals()
signals=struct('entry_ready',false,'bed_supported',false, ...
    'bed_absent',true,'takeover_feasible',true,'liftoff_ready',false, ...
    'suspended_feasible',true,'prepare_recontact',false, ...
    'returning',true,'return_phase_reached',true,'task_at_end',false, ...
    'task_complete',false,'force_bound_violation',false, ...
    'rom_violation',false,'soft_limit_violation',false, ...
    'robust_static_margin_N',100,'recontact_stable',false, ...
    'recontact_unsafe',false);
end
