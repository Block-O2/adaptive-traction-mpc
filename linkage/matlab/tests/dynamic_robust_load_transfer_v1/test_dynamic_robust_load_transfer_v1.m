function tests = test_dynamic_robust_load_transfer_v1
%TEST_DYNAMIC_ROBUST_LOAD_TRANSFER_V1 Supervisor and model-boundary tests.
tests=functiontests(localfunctions);
end


function setupOnce(testCase)
nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();
uncertainty=bed_supported_v1_registered_uncertainty_set(nominal);
testCase.TestData.nominal=nominal;
testCase.TestData.config=config;
testCase.TestData.uncertainty=uncertainty;
end


function testBedSupportedMotionAdvancesProgress(testCase)
state=dynamic_robust_v1_initial_state();
[next,action]=dynamic_robust_v1_manager_step( ...
    state,base_signals(),testCase.TestData.config);
verifyEqual(testCase,next.mode,"BED_SUPPORTED_MOTION");
verifyTrue(testCase,action.progress_enabled);
end


function testPausedGovernorHoldsTaskCoordinate(testCase)
c=testCase.TestData.config;
progress=struct('s',0.228,'s_dot',c.nominal_progress_rate,'s_ddot',0);
initial_s=progress.s;initial_rate=progress.s_dot;
for k=1:round(0.5/c.dt)
    progress=dynamic_robust_v1_advance_progress(progress,false,c);
end
verifyEqual(testCase,progress.s,initial_s,'AbsTol',0);
verifyLessThan(testCase,progress.s_dot,initial_rate);
progress=dynamic_robust_v1_advance_progress(progress,true,c);
verifyGreaterThan(testCase,progress.s,initial_s);
end


function testTransferReadyCannotTriggerBelowTwentyN(testCase)
c=testCase.TestData.config;c.entry_guard_duration_s=2*c.dt;
state=dynamic_robust_v1_initial_state();signals=base_signals();
signals.robust_static_margin_N=20-1e-6;signals.entry_ready=false;
for k=1:4,state=dynamic_robust_v1_manager_step(state,signals,c);end
verifyEqual(testCase,state.mode,"BED_SUPPORTED_MOTION");
signals.robust_static_margin_N=20;signals.entry_ready=true;
state=dynamic_robust_v1_manager_step(state,signals,c);
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.mode,"TRANSFER_READY");
end


function testStaticAndDynamicMarginsAreDistinct(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;q=deg2rad([30;50]);
static=bed_supported_v1_robust_hold_point(q,p, ...
    testCase.TestData.uncertainty,c.force_bound_N,c.svd_relative_tolerance);
dynamic=dynamic_robust_v1_dynamic_margin(q,zeros(2,1),q,zeros(2,1), ...
    [2;-1],p,c);
static_margin=c.force_bound_N-static.worst_required_force_N;
verifyGreaterThan(testCase,abs(static_margin-dynamic.margin_N),1e-6);
end


function testTakeoverCannotModifyPlantBedForce(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
z=bed_supported_v1_calibrate_hip_height(p,c);q=deg2rad([18;32]);dq=[0;0];
before=bed_supported_v1_contact(q,dq,z.h_hip_m,p,c);
state=dynamic_robust_v1_initial_state();state.mode="LOAD_TAKEOVER";
state.bed_credit=.6;signals=base_signals();signals.takeover_feasible=false;
[~,action]=dynamic_robust_v1_manager_step(state,signals,c);
after=bed_supported_v1_contact(q,dq,z.h_hip_m,p,c);
verifyTrue(testCase,action.pause_unloading);
verifyEqual(testCase,after.total_normal_force_N,before.total_normal_force_N,'AbsTol',0);
verifyEqual(testCase,after.generalized_torque_Nm,before.generalized_torque_Nm,'AbsTol',0);
end


function testMarginErosionPausesBeforeFailure(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="LOAD_TAKEOVER";state.bed_credit=.55;signals=base_signals();
signals.takeover_feasible=false;signals.bed_supported=true;
[state,action]=dynamic_robust_v1_manager_step(state,signals,c);
verifyTrue(testCase,action.pause_unloading);
verifyFalse(testCase,action.progress_enabled);
verifyEqual(testCase,state.bed_credit,.55,'AbsTol',0);
verifyEqual(testCase,state.classification,"RUNNING");
end


function testFeasibleTakeoverAdvancesMotionAndUnloadClock(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="LOAD_TAKEOVER";signals=base_signals();
[state,action]=dynamic_robust_v1_manager_step(state,signals,c);
verifyTrue(testCase,action.progress_enabled);
verifyEqual(testCase,state.takeover_time_s,c.dt,'AbsTol',1e-15);
verifyLessThan(testCase,state.bed_credit,1);
end


function testMovingBlendFollowsTubeCenterWithoutEndpointLag(testCase)
c=testCase.TestData.config;s0=.228;s1=.240;
path0=hybrid_tube_v1_task_path(s0);path1=hybrid_tube_v1_task_path(s1);
tube0=hybrid_tube_v1_tube_schedule(s0,path0.q,c);
entry_q=path0.q+.8*tube0;
progress=struct('s',s1,'s_dot',c.nominal_progress_rate,'s_ddot',0);
elapsed=.2;
reference=dynamic_robust_v1_moving_blend_reference( ...
    entry_q,path0.q,path1,progress,elapsed,c.load_takeover_duration_s);
r=elapsed/c.load_takeover_duration_s;g=10*r^3-15*r^4+6*r^5;
verifyEqual(testCase,reference.q-path1.q, ...
    (1-g)*(entry_q-path0.q),'AbsTol',1e-14);
tube1=hybrid_tube_v1_tube_schedule(s1,path1.q,c);
verifyLessThanOrEqual(testCase,abs(reference.q-path1.q),tube1+1e-12);
end


function testLoadReturnReferencePreservesContactThenRejoinsPath(testCase)
c=testCase.TestData.config;s0=.751;s1=.770;
path0=hybrid_tube_v1_task_path(s0);path1=hybrid_tube_v1_task_path(s1);
contact_q=path0.q+deg2rad([-1;1]);
progress0=struct('s',s0,'s_dot',0,'s_ddot',0);
for mode=["RECONTACT","LOAD_RETURN"]
    reference=dynamic_robust_v1_return_reference(mode,contact_q,path0.q, ...
        path0,progress0,c.load_return_duration_s,c.load_return_duration_s);
    verifyEqual(testCase,reference.q,contact_q,'AbsTol',0);
    verifyEqual(testCase,reference.dq,zeros(2,1),'AbsTol',0);
    verifyEqual(testCase,reference.ddq,zeros(2,1),'AbsTol',0);
end
progress1=struct('s',s1,'s_dot',c.nominal_progress_rate,'s_ddot',0);
elapsed=.5*c.load_return_duration_s;
reference=dynamic_robust_v1_return_reference("BED_SUPPORTED_RETURN", ...
    contact_q,path0.q,path1,progress1,elapsed,c.load_return_duration_s);
verifyEqual(testCase,reference.q-path1.q,.5*(contact_q-path0.q), ...
    'AbsTol',1e-14);
end


function testLiftoffRequiresStableAbsenceAndDynamicGuard(testCase)
c=testCase.TestData.config;state=dynamic_robust_v1_initial_state();
state.mode="LIFTOFF";state.bed_credit=0;signals=base_signals();
signals.bed_supported=false;signals.bed_absent=true;signals.liftoff_ready=true;
count=ceil(c.contact_stable_duration_s/c.dt)-1;
for k=1:count,state=dynamic_robust_v1_manager_step(state,signals,c);end
verifyEqual(testCase,state.mode,"LIFTOFF");
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.mode,"SUSPENDED_MOTION");
state=dynamic_robust_v1_initial_state();state.mode="LIFTOFF";
signals.liftoff_ready=false;signals.takeover_feasible=false;
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.classification,"LIFTOFF_INFEASIBLE");
end


function testSuspendedDynamicInfeasibilityPausesThenFails(testCase)
c=testCase.TestData.config;c.suspended_pause_timeout_s=2*c.dt;
state=dynamic_robust_v1_initial_state();state.mode="SUSPENDED_MOTION";
state.mode_time_s=c.suspended_blend_duration_s;signals=base_signals();
signals.suspended_feasible=false;signals.bed_supported=false;
[state,action]=dynamic_robust_v1_manager_step(state,signals,c);
verifyFalse(testCase,action.progress_enabled);
verifyEqual(testCase,state.classification,"RUNNING");
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.classification,"SUSPENDED_INFEASIBLE");
end


function testRecontactRequiresRealSupportedSignal(testCase)
c=testCase.TestData.config;c.contact_stable_duration_s=2*c.dt;
state=dynamic_robust_v1_initial_state();state.mode="SUSPENDED_MOTION";
state.mode_time_s=c.suspended_blend_duration_s;signals=base_signals();
signals.returning=true;signals.bed_supported=false;
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.mode,"SUSPENDED_MOTION");
signals.bed_supported=true;
state=dynamic_robust_v1_manager_step(state,signals,c);
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.mode,"RECONTACT");
end


function testLoadReturnCompletesBeforeNonrobustBoundary(testCase)
c=testCase.TestData.config;signals=base_signals();
state=dynamic_robust_v1_initial_state();state.mode="LOAD_RETURN";
state.mode_time_s=c.load_return_duration_s;state.contact_stable_time_s= ...
    c.contact_stable_duration_s;
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.mode,"BED_SUPPORTED_RETURN");
state=dynamic_robust_v1_initial_state();state.mode="LOAD_RETURN";
signals.bed_supported=false;signals.robust_static_margin_N=0;
state=dynamic_robust_v1_manager_step(state,signals,c);
verifyEqual(testCase,state.classification,"LOAD_RETURN_FAILED");
end


function testRegisteredStressCasesAreDeterministic(testCase)
p=testCase.TestData.nominal;
a=testCase.TestData.uncertainty;
b=bed_supported_v1_registered_uncertainty_set(p);
verifyEqual(testCase,[a.combined_cases.case_id],[b.combined_cases.case_id]);
for k=1:3
    verifyEqual(testCase,a.combined_cases(k).override,b.combined_cases(k).override);
end
end


function testForceBoundsAreHardEnforced(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;q=deg2rad([30;50]);
[u,~]=bed_supported_v1_robot_controller(q,zeros(2,1),deg2rad([45;84]), ...
    zeros(2,1),zeros(2,1),zeros(2,1),[199;-199],p,c,1,0);
verifyLessThanOrEqual(testCase,max(abs(u)),c.force_bound_N+c.bound_tolerance_N);
end


function testPlantMismatchDoesNotMutateNominalModel(testCase)
nominal=testCase.TestData.nominal;c=testCase.TestData.config;
plant=bed_supported_v1_parameter_override(nominal, ...
    testCase.TestData.uncertainty.combined_cases(1).override);
nominal_before=nominal;plant_before=plant;
q=deg2rad([30;50]);
dynamic_robust_v1_dynamic_margin(q,zeros(2,1),q,zeros(2,1), ...
    zeros(2,1),nominal,c);
bed_supported_v1_dynamics([q;zeros(2,1)],[0;0],.1,plant,c);
verifyEqual(testCase,nominal,nominal_before);
verifyEqual(testCase,plant,plant_before);
verifyFalse(testCase,isequaln(nominal,plant));
end


function testInitialConditionContractIsUnchanged(testCase)
[q,~,~,~,progress]=human_two_link_v2_reference(0,"slow_passive_flexion_v2");
verifyEqual(testCase,q,deg2rad([5;10]),'AbsTol',0);
verifyEqual(testCase,progress,0,'AbsTol',0);
state=dynamic_robust_v1_initial_state();
verifyEqual(testCase,state.mode,"BED_SUPPORTED_MOTION");
end


function testMismatchInitializationIsPlantConsistentAndBounded(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
z=bed_supported_v1_calibrate_hip_height(p,c);
cases=testCase.TestData.uncertainty.combined_cases;
for k=1:3
    plant=bed_supported_v1_parameter_override(p,cases(k).override);
    a=dynamic_robust_v1_initial_admissibility(p,plant,z,c);
    verifyTrue(testCase,a.pass);
    verifyEqual(testCase,a.q_deg,[5;10],'AbsTol',1e-12);
    verifyLessThanOrEqual(testCase, ...
        norm(a.true_equilibrium_alpha_deg_s2,Inf),1e-9);
    verifyGreaterThanOrEqual(testCase,a.true_equilibrium_force_margin_N,0);
    verifyFalse(testCase,a.true_soft_violation);
    verifyFalse(testCase,a.rom_violation);
    verifyTrue(testCase,a.bed_supported);
end
end


function testMismatchStartupDoesNotEnterSoftLimit(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
c.max_time_s=5*c.dt;
z=bed_supported_v1_calibrate_hip_height(p,c);
plan=hybrid_tube_v1_build_plan(p,c);
cases=testCase.TestData.uncertainty.combined_cases;
for k=1:3
    plant=bed_supported_v1_parameter_override(p,cases(k).override);
    a=dynamic_robust_v1_initial_admissibility(p,plant,z,c);
    result=simulate_dynamic_robust_load_transfer_v1( ...
        c,p,plant,plan,z,a);
    verifyFalse(testCase,any(result.soft_limit_active));
    verifyLessThanOrEqual(testCase, ...
        max(abs(result.soft_limit_torque_Nm),[],'all'), ...
        c.soft_torque_tolerance_Nm);
    verifyGreaterThanOrEqual(testCase,min(result.state(1,:)), ...
        plant.q_min(1)+plant.soft_limit_margin- ...
        plant.soft_limit_numerical_tolerance);
end
end


function testR1NominalEntersTrackingWithoutStartupSafetyEvent(testCase)
r=r1_startup_results(testCase);result=r{1};
verifyTrue(testCase,result.takeover_state.tracking_entered);
verify_takeover_safe(testCase,result);
end


function testR1RegisteredMismatchCasesSafelyReachTracking(testCase)
r=r1_startup_results(testCase);
for k=2:4
    verifyTrue(testCase,r{k}.takeover_state.tracking_entered, ...
        sprintf('registered startup case %d did not enter tracking',k-1));
    verify_takeover_safe(testCase,r{k});
end
end


function testR1AdverseZeroBoundaryPredictionNeverWorsensMargin(testCase)
r=r1_startup_results(testCase);result=r{4};
before_tracking=result.takeover_mode~="TRACKING";
at_zero=abs(result.takeover_soft_margin_rad(1,:))<=1e-10;
indices=before_tracking & at_zero;
verifyTrue(testCase,any(indices));
verifyGreaterThanOrEqual(testCase, ...
    result.takeover_predicted_soft_margin_rad(1,indices), ...
    result.takeover_soft_margin_rad(1,indices)- ...
    result.config.safe_takeover_prediction_tolerance_rad);
end


function testR1RuntimeGovernorHasNoPlantOracleDependency(testCase)
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
path=fullfile(root,'src','dynamic_robust_load_transfer_v1', ...
    'dynamic_robust_v1_safe_takeover_step.m');
    source=fileread(path);
for forbidden=["dynamic_robust_v1_initial_admissibility", ...
        "bed_supported_v1_parameter_override","plant_parameters", ...
        "combined_cases","case_name"]
    verifyFalse(testCase,contains(source,forbidden));
end
end


function testR1ForceBoundsAndNominalTrackingBypass(testCase)
r=r1_startup_results(testCase);c=testCase.TestData.config;
for k=1:4
    verifyLessThanOrEqual(testCase,max(abs(r{k}.robot_force_N),[],'all'), ...
        c.force_bound_N+c.bound_tolerance_N);
end
nominal=r{1};indices=nominal.takeover_mode=="TRACKING";
verifyTrue(testCase,any(indices));
verifyEqual(testCase,nominal.robot_force_N(:,indices), ...
    nominal.takeover_candidate_force_N(:,indices),'AbsTol',0);
end


function testR1TimeoutIsStructuredAndHoldsAppliedCommand(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
c.safe_takeover_timeout_s=c.dt;
q=p.q_min+p.soft_limit_margin;dq=zeros(2,1);u=[0;0];
state=dynamic_robust_v1_safe_takeover_initial_state(u);
[applied,state,details]=dynamic_robust_v1_safe_takeover_step( ...
    state,q,dq,u,u,[100;100],zeros(2,1),p,c);
verifyEqual(testCase,state.mode,"TAKEOVER_ABORT");
verifyTrue(testCase,state.timed_out);
verifyEqual(testCase,details.reason,"SAFE_TAKEOVER_TIMEOUT");
verifyEqual(testCase,applied,u,'AbsTol',0);
end


function testR2ANominalExplicitModelIsUnchanged(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;c.max_time_s=10*c.dt;
z=bed_supported_v1_calibrate_hip_height(p,c);
plan=hybrid_tube_v1_build_plan(p,c);
a=dynamic_robust_v1_initial_admissibility(p,p,z,c);
implicit=simulate_dynamic_robust_load_transfer_v1(c,p,p,plan,z,a);
explicit=simulate_dynamic_robust_load_transfer_v1(c,p,p,plan,z,a,p);
verifyEqual(testCase,explicit.robot_force_N,implicit.robot_force_N,'AbsTol',0);
verifyEqual(testCase,explicit.state,implicit.state,'AbsTol',0);
verifyEqual(testCase,explicit.mode,implicit.mode);
verifyEqual(testCase,explicit.takeover_mode,implicit.takeover_mode);
verifyEqual(testCase,explicit.terminal_state,implicit.terminal_state);
end


function testR2AMildOracleMapping(testCase)
verify_oracle_mapping(testCase,2);
end


function testR2AModerateOracleMapping(testCase)
verify_oracle_mapping(testCase,3);
end


function testR2AAdverseOracleMapping(testCase)
verify_oracle_mapping(testCase,4);
end


function testR2AControllerModelDoesNotUpdateDuringRollout(testCase)
r=r2a_oracle_startup_results(testCase);
for index=1:numel(r)
    verifyEqual(testCase,r{index}.controller_model_parameters, ...
        r{index}.controller_model_initial_parameters);
    verifyEqual(testCase,dynamic_robust_v1_parameter_vector( ...
        r{index}.controller_model_parameters), ...
        dynamic_robust_v1_parameter_vector(r{index}.plant_parameters), ...
        'AbsTol',0);
end
end


function testR2AOraclePreservesR1ModePath(testCase)
initial=dynamic_robust_v1_safe_takeover_initial_state([0;0]);
verifyEqual(testCase,initial.mode,"SAFE_HOLD");
r=r2a_oracle_startup_results(testCase);
for index=1:numel(r)
    verifyTrue(testCase,any(r{index}.takeover_mode=="TAKEOVER"));
    verifyTrue(testCase,any(r{index}.takeover_mode=="TRACKING"));
    verifyTrue(testCase,r{index}.takeover_state.tracking_entered);
    verify_takeover_safe(testCase,r{index});
end
end


function testR2AOracleMappingIsAbsentFromRuntimeSafetyLogic(testCase)
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
paths={fullfile(root,'src','dynamic_robust_load_transfer_v1', ...
        'dynamic_robust_v1_safe_takeover_step.m'), ...
    fullfile(root,'src','dynamic_robust_load_transfer_v1', ...
        'dynamic_robust_v1_manager_step.m'), ...
    fullfile(root,'src','dynamic_robust_load_transfer_v1', ...
        'dynamic_robust_v1_dynamic_margin.m'), ...
    fullfile(root,'src','bed_supported_load_transfer_v1', ...
        'bed_supported_v1_robot_controller.m')};
for index=1:numel(paths)
    source=fileread(paths{index});
    for forbidden=["dynamic_robust_v1_oracle_case_set", ...
            "combined_cases","parameter_override","plant_parameters", ...
            "oracle_mismatch_norm"]
        verifyFalse(testCase,contains(source,forbidden), ...
            sprintf('oracle leakage token %s in %s',forbidden,paths{index}));
    end
end
end


function verify_takeover_safe(testCase,result)
last=find(result.takeover_mode=="TRACKING",1,'first');
verifyNotEmpty(testCase,last);
indices=1:last;
verifyFalse(testCase,any(result.soft_limit_active(indices)));
verifyFalse(testCase,any(result.rom_violation(indices)));
verifyGreaterThanOrEqual(testCase, ...
    min(result.takeover_soft_margin_rad(:,indices),[],'all'), ...
    -result.nominal_parameters.soft_limit_numerical_tolerance);
end


function verify_oracle_mapping(testCase,index)
cases=dynamic_robust_v1_oracle_case_set(testCase.TestData.nominal);
item=cases(index);
verifyEqual(testCase,item.controller_model_parameters,item.plant_parameters);
verifyEqual(testCase,item.oracle_mismatch_norm,0,'AbsTol',0);
verifyGreaterThan(testCase,item.nominal_model_mismatch_norm,0);
end


function results=r2a_oracle_startup_results(testCase)
persistent cached
if isempty(cached)
    p=testCase.TestData.nominal;c=testCase.TestData.config;c.max_time_s=4;
    z=bed_supported_v1_calibrate_hip_height(p,c);
    plan=hybrid_tube_v1_build_plan(p,c);
    cases=dynamic_robust_v1_oracle_case_set(p);
    cached=cell(1,numel(cases));
    for index=1:numel(cases)
        plant=cases(index).plant_parameters;
        model=cases(index).controller_model_parameters;
        a=dynamic_robust_v1_initial_admissibility(p,plant,z,c,model);
        cached{index}=simulate_dynamic_robust_load_transfer_v1( ...
            c,p,plant,plan,z,a,model);
    end
end
results=cached;
end


function results=r1_startup_results(testCase)
persistent cached
if isempty(cached)
    p=testCase.TestData.nominal;c=testCase.TestData.config;
    c.max_time_s=4.0;
    z=bed_supported_v1_calibrate_hip_height(p,c);
    plan=hybrid_tube_v1_build_plan(p,c);
    cases=testCase.TestData.uncertainty.combined_cases;
    plants=cell(1,4);plants{1}=p;
    for k=1:3
        plants{k+1}=bed_supported_v1_parameter_override(p,cases(k).override);
    end
    cached=cell(1,4);
    for k=1:4
        a=dynamic_robust_v1_initial_admissibility(p,plants{k},z,c);
        cached{k}=simulate_dynamic_robust_load_transfer_v1( ...
            c,p,plants{k},plan,z,a);
    end
end
results=cached;
end


function signals=base_signals()
signals=struct('entry_ready',false,'bed_supported',true,'bed_absent',false, ...
    'takeover_feasible',true,'liftoff_ready',false, ...
    'suspended_feasible',true,'returning',false, ...
    'prepare_recontact',false, ...
    'return_phase_reached',false,'task_at_end',false,'task_complete',false, ...
    'force_bound_violation',false,'rom_violation',false, ...
    'soft_limit_violation',false,'robust_static_margin_N',30);
end
