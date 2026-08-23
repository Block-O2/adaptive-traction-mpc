function tests = test_r4_minimal_recovery_corridor
%TEST_R4_MINIMAL_RECOVERY_CORRIDOR Deterministic offline R4 mechanics.
tests=functiontests(localfunctions);
end

function setupOnce(testCase)
root=fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
addpath(genpath(fullfile(root,'linkage','matlab')));
paths=r4_source_paths(root);anchors=r4_extract_anchors(paths);
testCase.TestData.root=root;testCase.TestData.paths=paths;
testCase.TestData.anchors=anchors;testCase.TestData.manifest=r4_source_manifest(paths);
end

function testApprovedConfigIsExact(testCase)
c=r4_config();verifyEqual(testCase,c.posture_caps_deg,[10,12,15,20,25,30]);
verifyEqual(testCase,c.backward_progress,[0,.01,.02,.05,.10,.15,.20]);
verifyEqual(testCase,c.recovery_rate_sensitivity_deg_s,[10,20]);
end
function testFrozenSourcesExist(testCase)
verifyTrue(testCase,isfile(testCase.TestData.paths.stage1_oracle));
verifyTrue(testCase,isfile(testCase.TestData.paths.stage2_adaptive));
end
function testSourceManifestDeterministic(testCase)
second=r4_source_manifest(testCase.TestData.paths);
verifyEqual(testCase,second.sha256,testCase.TestData.manifest.sha256);
verifyEqual(testCase,second.bytes,testCase.TestData.manifest.bytes);
end
function testAllRequestedAnchorsExtracted(testCase)
a=testCase.TestData.anchors;verifyEqual(testCase,numel(a),9);
verifyEqual(testCase,sum([a.primary]),6);
verifyEqual(testCase,sum([a.role]=="first_hold"),3);
end
function testModerateOracleAnchorIndices(testCase)
a=testCase.TestData.anchors([testCase.TestData.anchors.case_name]=="moderate_oracle");
verifyEqual(testCase,[a.sample_index],[1990,1999,2004]);
end
function testTerminalIsNotFutureData(testCase)
a=testCase.TestData.anchors;for k=1:numel(a)
    verifyGreaterThanOrEqual(testCase,a(k).task_s,0);
    verifyLessThanOrEqual(testCase,a(k).task_s,1);
end
end
function testTrueModelSelection(testCase)
a=testCase.TestData.anchors(1);p=r4_model_parameters(a,"true");
verifyEqual(testCase,dynamic_robust_v1_parameter_vector(p), ...
    dynamic_robust_v1_parameter_vector(a.plant_parameters),'AbsTol',0);
end
function testPerceivedModelSelection(testCase)
a=testCase.TestData.anchors(4);p=r4_model_parameters(a,"perceived");
verifyEqual(testCase,dynamic_robust_v1_parameter_vector(p), ...
    dynamic_robust_v1_parameter_vector(a.controller_parameters),'AbsTol',0);
end
function testTubeGeometryUsesFrozenPath(testCase)
a=testCase.TestData.anchors(1);path=hybrid_tube_v1_task_path(a.task_s);
c=a.config;c.tube_cap_deg=20;tube=hybrid_tube_v1_tube_schedule(a.task_s,path.q,c);
verifyGreaterThan(testCase,tube(1),0);verifyLessThanOrEqual(testCase,rad2deg(tube(1)),20);
end
function testCandidateDomainNeverUsesFutureProgress(testCase)
a=testCase.TestData.anchors(1);d=r4_candidate_domain(a,"true","bed_assisted",10,.02,1,.01);
verifyLessThanOrEqual(testCase,max(d.s),a.task_s+1e-12);
verifyGreaterThanOrEqual(testCase,min(d.s),max(0,a.task_s-.02)-1e-12);
end
function testPointPredicateIncludesResumeAndForce(testCase)
a=testCase.TestData.anchors(1);p=r4_point_feasibility(a.q_rad,a,"true","bed_assisted");
verifyTrue(testCase,isfield(p,'resume_ok'));verifyTrue(testCase,isfield(p,'force_ok'));
verifyTrue(testCase,isfield(p,'horizon_ok'));verifyLessThanOrEqual(testCase, ...
    max(abs(p.bounded_force_N)),a.config.force_bound_N+1e-8);
end
function testTrueAndPerceivedRemainLabeled(testCase)
a=testCase.TestData.anchors(4);
t=r4_point_feasibility(a.q_rad,a,"true","bed_assisted");
p=r4_point_feasibility(a.q_rad,a,"perceived","bed_assisted");
verifyEqual(testCase,t.model_kind,"true");verifyEqual(testCase,p.model_kind,"perceived");
end
function testInitialConnectionDeterministic(testCase)
a=testCase.TestData.anchors(1);
first=r4_initial_connection(a.q_rad,a,"true","bed_assisted");
second=r4_initial_connection(a.q_rad,a,"true","bed_assisted");
verifyEqual(testCase,first.feasible,second.feasible);
verifyEqual(testCase,first.q_pred_rad,second.q_pred_rad,'AbsTol',1e-12);
end
function testLocalEdgeRejectsZeroLength(testCase)
a=testCase.TestData.anchors(1);
e=r4_local_edge_feasibility(a.q_rad,a.q_rad,a,"true","bed_assisted",20);
verifyFalse(testCase,e.feasible);
end
function testGraphNoPointClassification(testCase)
d=struct('q_rad',zeros(2,1),'s',0,'is_goal',false,'is_transit',false, ...
    'force_margin_N',NaN,'residual_Nm',NaN);
g=r4_graph_search(d,testCase.TestData.anchors(1),"true","bed_assisted",20);
verifyEqual(testCase,g.classification,"NO_RECOVERY_POINT_FOUND");
end
function testSettingClassificationDeterministic(testCase)
a=testCase.TestData.anchors(1);
one=r4_evaluate_setting(a,"true","bed_assisted","A_POSTURE_ONLY",10,0,1,.01,20);
two=r4_evaluate_setting(a,"true","bed_assisted","A_POSTURE_ONLY",10,0,1,.01,20);
verifyEqual(testCase,one.classification,two.classification);
verifyEqual(testCase,one.feasible_point_count,two.feasible_point_count);
end
function testHalfDegreeRefinementConvergesPointExistence(testCase)
a=testCase.TestData.anchors(1);
coarse=r4_evaluate_setting(a,"true","bed_assisted","A_POSTURE_ONLY",10,0,1,.01,20);
fine=r4_evaluate_setting(a,"true","bed_assisted","A_POSTURE_ONLY",10,0,.5,.01,20);
verifyEqual(testCase,coarse.feasible_point_count>0,fine.feasible_point_count>0);
end
function testEvaluationDoesNotMutateSources(testCase)
a=testCase.TestData.anchors(1);
r4_evaluate_setting(a,"true","bed_assisted","A_POSTURE_ONLY",10,0,1,.01,20);
after=r4_source_manifest(testCase.TestData.paths);
verifyEqual(testCase,after.sha256,testCase.TestData.manifest.sha256);
end
