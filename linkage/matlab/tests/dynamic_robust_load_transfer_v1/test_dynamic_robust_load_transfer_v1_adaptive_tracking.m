function tests=test_dynamic_robust_load_transfer_v1_adaptive_tracking
%TEST_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING R2B contracts.
tests=functiontests(localfunctions);
end


function setupOnce(testCase)
p=human_two_link_v2_parameters(1.72,75);c=dynamic_robust_v1_config();
testCase.TestData.nominal=p;testCase.TestData.config=c;
testCase.TestData.adaptive=dynamic_robust_v1_adaptive_config(c);
end


function testWindowLengthOrderingAndNoFutureLeakage(testCase)
p=testCase.TestData.nominal;a=testCase.TestData.adaptive;
s=dynamic_robust_v1_adaptive_initial_state(p,a);
for index=1:a.window_size+5
    x=index*ones(4,1);u=-index*ones(2,1);xn=(index+.5)*ones(4,1);
    s=dynamic_robust_v1_adaptive_window_append(s,x,u,xn,index,a);
end
verifySize(testCase,s.x,[4,a.window_size]);
verifyEqual(testCase,s.sample_index,6:a.window_size+5);
verifyEqual(testCase,s.x(:,1),6*ones(4,1));
verifyEqual(testCase,s.x_next(:,end),(a.window_size+5.5)*ones(4,1));
verifyLessThanOrEqual(testCase,max(s.sample_index),a.window_size+5);
end


function testOutOfBoundsCandidateIsRejected(testCase)
a=testCase.TestData.adaptive;candidate=a.theta_nominal;
candidate(1)=a.theta_max(1)+1e-6;
solver=mock_solver(candidate,true,.1,7,1);
v=dynamic_robust_v1_adaptive_validate_candidate(candidate,solver,1,a);
verifyFalse(testCase,v.accepted);verifyEqual(testCase,v.reason,"REJECTED_BOUNDS");
end


function testSolverFailurePreservesAcceptedModel(testCase)
p=testCase.TestData.nominal;a=testCase.TestData.adaptive;
s=dynamic_robust_v1_adaptive_initial_state(p,a);before=s.theta_model;
solver=mock_solver(a.theta_max,false,NaN,0,Inf);
[s,v]=dynamic_robust_v1_adaptive_commit_candidate( ...
    s,solver,1,p,a,100);
verifyFalse(testCase,v.accepted);verifyEqual(testCase,s.theta_model,before);
verifyEqual(testCase,s.solver_failures,1);
verifyEqual(testCase,s.controller_model,p);
end


function testPoorResidualPreservesAcceptedModel(testCase)
p=testCase.TestData.nominal;a=testCase.TestData.adaptive;
s=dynamic_robust_v1_adaptive_initial_state(p,a);before=s.theta_model;
solver=mock_solver(a.theta_max,true,2,7,1);
[s,v]=dynamic_robust_v1_adaptive_commit_candidate( ...
    s,solver,1,p,a,100);
verifyFalse(testCase,v.accepted);verifyEqual(testCase,v.reason,"REJECTED_FIT");
verifyEqual(testCase,s.theta_model,before);
end


function testAcceptedUpdateRateIsBounded(testCase)
a=testCase.TestData.adaptive;current=a.theta_nominal;
updated=dynamic_robust_v1_adaptive_bounded_update(current,a.theta_max,a);
verifyLessThanOrEqual(testCase,abs(updated-current), ...
    a.maximum_update_step+100*eps);
verifyEqual(testCase,updated-current,a.maximum_update_step,'AbsTol',100*eps);
end


function testNominalReplayStaysAtNominal(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
a=testCase.TestData.adaptive;s=synthetic_window(p,p,c,a);
solver=dynamic_robust_v1_adaptive_solve_window(s,p,.1,c,a);
verifyTrue(testCase,solver.success);verifyEqual(testCase,solver.rank,7);
verifyLessThan(testCase,norm(solver.theta-a.theta_nominal,Inf),1e-8);
end


function testMismatchReplayMovesInCorrectDirection(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;
a=testCase.TestData.adaptive;cases=dynamic_robust_v1_oracle_case_set(p);
plant=cases(3).plant_parameters;s=synthetic_window(p,plant,c,a);
solver=dynamic_robust_v1_adaptive_solve_window(s,p,.1,c,a);
truth=dynamic_robust_v1_adaptive_theta_from_parameters(p,plant);
initial=norm((a.theta_nominal-truth)./a.theta_range);
final=norm((solver.theta-truth)./a.theta_range);
verifyTrue(testCase,solver.success);verifyEqual(testCase,solver.rank,7);
verifyLessThan(testCase,final,initial);
end


function testRuntimeIdentifierHasNoTrueThetaDependency(testCase)
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
folder=fullfile(root,'src', ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking');
names={ 'dynamic_robust_v1_adaptive_add_transition.m', ...
    'dynamic_robust_v1_adaptive_commit_candidate.m', ...
    'dynamic_robust_v1_adaptive_initial_state.m', ...
    'dynamic_robust_v1_adaptive_solve_window.m', ...
    'dynamic_robust_v1_adaptive_window_append.m', ...
    'dynamic_robust_v1_adaptive_window_residual.m'};
for index=1:numel(names)
    source=fileread(fullfile(folder,names{index}));
    for forbidden=["theta_from_parameters","plant_parameters", ...
            "combined_cases","oracle_case","true_theta","mismatch label"]
        verifyFalse(testCase,contains(source,forbidden,'IgnoreCase',true));
    end
end
end


function testAdaptivePathPreservesR1AndForceSafety(testCase)
p=testCase.TestData.nominal;c=testCase.TestData.config;c.max_time_s=1.2;
a=testCase.TestData.adaptive;z=bed_supported_v1_calibrate_hip_height(p,c);
plan=hybrid_tube_v1_build_plan(p,c);
init=dynamic_robust_v1_initial_admissibility(p,p,z,c,p);
r=simulate_dynamic_robust_load_transfer_v1(c,p,p,plan,z,init,p,a);
verifyTrue(testCase,r.adaptive_enabled);
verifyEqual(testCase,r.controller_model_initial_parameters,p);
verifyTrue(testCase,any(r.takeover_mode=="TAKEOVER"));
verifyTrue(testCase,any(r.takeover_mode=="TRACKING"));
verifyFalse(testCase,any(r.soft_limit_active));
verifyFalse(testCase,any(r.rom_violation));
verifyLessThanOrEqual(testCase,max(abs(r.robot_force_N),[],'all'), ...
    c.force_bound_N+c.bound_tolerance_N);
end


function testAdaptiveConfigDoesNotChangeSafetyOrTaskConfig(testCase)
c=testCase.TestData.config;before=c;
a=dynamic_robust_v1_adaptive_config(c); %#ok<NASGU>
verifyEqual(testCase,c,before);
verifyEqual(testCase,c.force_bound_N,200);
verifyEqual(testCase,c.max_time_s,60);
verifyEqual(testCase,c.dt,.002);
verifyEqual(testCase,c.robust_entry_trigger_N,20);
end


function state=synthetic_window(nominal,plant,config,adaptive)
state=dynamic_robust_v1_adaptive_initial_state(nominal,adaptive);
for index=1:adaptive.window_size
    fraction=(index-1)/(adaptive.window_size-1);
    q=deg2rad([10+25*fraction;20+40*fraction]);
    dq=deg2rad([4*cos(2*pi*fraction);6*sin(2*pi*fraction)]);
    x=[q;dq];u=[40+80*fraction;-20+30*sin(pi*fraction)];
    rhs=@(~,value)bed_supported_v1_dynamics(value,u,.1,plant,config);
    xn=human_two_link_v2_rk4_step(rhs,0,x,config.dt);
    state=dynamic_robust_v1_adaptive_window_append( ...
        state,x,u,xn,index,adaptive);
end
end


function solver=mock_solver(theta,success,fit_rms,rank_value,condition)
solver=struct('success',success,'theta',theta,'fit_rms',fit_rms, ...
    'initial_fit_rms',1,'iterations',1,'improved',success, ...
    'rank',rank_value,'condition_number',condition,'solve_time_s',0, ...
    'singular_values',ones(7,1));
end
