function tests=test_r3_identifiability_failure_decomposition
%TEST_R3_IDENTIFIABILITY_FAILURE_DECOMPOSITION Offline R3A contracts.
tests=functiontests(localfunctions);
end


function setupOnce(testCase)
test_file=mfilename('fullpath');repo_root=fileparts(fileparts(fileparts( ...
    fileparts(fileparts(test_file)))));
paths=r3a_source_paths(repo_root);manifest=r3a_source_manifest(paths);
r2b=load(paths.r2b);
adverse=r2b.results{4};attempts=find(adverse.identifier_update_attempted);
window=r3a_reconstruct_identifier_window(adverse,attempts(end));
diagnostic=r3a_identifier_window_jacobian(window, ...
    adverse.identifier_theta_raw(:,attempts(end)), ...
    adverse.nominal_parameters,adverse.h_hip_m,adverse.config, ...
    adverse.adaptive_config);
testCase.TestData.repo_root=repo_root;testCase.TestData.paths=paths;
testCase.TestData.manifest=manifest;testCase.TestData.r2b=r2b;
testCase.TestData.adverse_window=window;
testCase.TestData.adverse_diagnostic=diagnostic;
end


function testExistingR2BLogLoadsWithoutMutation(testCase)
before=r3a_source_manifest(testCase.TestData.paths);
loaded=load(testCase.TestData.paths.r2b,'records');
after=r3a_source_manifest(testCase.TestData.paths);
verifyEqual(testCase,numel(loaded.records),4);
verifyEqual(testCase,before(:,{'path','bytes','modified_datenum'}), ...
    after(:,{'path','bytes','modified_datenum'}));
end


function testReconstructedWindowDimensions(testCase)
window=testCase.TestData.adverse_window;
verifySize(testCase,window.x,[4 100]);verifySize(testCase,window.u,[2 100]);
verifySize(testCase,window.x_next,[4 100]);
verifyEqual(testCase,window.sample_index(2:end)-window.sample_index(1:end-1), ...
    ones(1,99));
end


function testAdverseFinalRankMatchesLoggedFour(testCase)
adverse=testCase.TestData.r2b.results{4};attempts=find( ...
    adverse.identifier_update_attempted);
verifyEqual(testCase,adverse.identifier_rank(attempts(end)),4);
verifyEqual(testCase,testCase.TestData.adverse_diagnostic.rank,4);
end


function testSingularValuesFiniteAndNonnegative(testCase)
values=testCase.TestData.adverse_diagnostic.singular_values;
verifyTrue(testCase,all(isfinite(values)));verifyGreaterThanOrEqual(testCase,values,0);
verifyGreaterThanOrEqual(testCase,values(1:end-1),values(2:end));
end


function testSafeCorrelationHandlesZeroColumns(testCase)
matrix=[1 0 1;2 0 -1;3 0 0];correlation=r3a_safe_column_correlation(matrix);
verifyTrue(testCase,all(isfinite(correlation),'all'));
verifyEqual(testCase,correlation(:,2),zeros(3,1));
verifyEqual(testCase,correlation(2,:),zeros(1,3));
verifyEqual(testCase,correlation(1,1),1,'AbsTol',eps);
end


function testPhaseSegmentationIsDeterministic(testCase)
mode=["A","A","B","B","A"];t=0:4;
first=r3a_phase_segments(mode,t);second=r3a_phase_segments(mode,t);
verifyEqual(testCase,first,second);verifyEqual(testCase,first.mode,["A";"B";"A"]);
verifyEqual(testCase,first.sample_count,[2;2;1]);
end


function testAcceptedRejectedCheckpointsAlign(testCase)
for case_index=1:4
    result=testCase.TestData.r2b.results{case_index};
    attempted=find(result.identifier_update_attempted);
    accepted=result.identifier_update_accepted(attempted);
    statuses=result.identifier_status(attempted);
    verifyEqual(testCase,accepted,statuses=="ACCEPTED");
    verifyEqual(testCase,sum(accepted),result.metrics.identifier.accepted_updates);
    verifyEqual(testCase,sum(~accepted),result.metrics.identifier.rejected_updates);
end
end


function testModerateTrackingAlignmentIsDeterministic(testCase)
moderate=testCase.TestData.r2b.results{3};first=r3a_tracking_alignment(moderate);
second=r3a_tracking_alignment(moderate);verifyEqual(testCase,first,second);
verifyEqual(testCase,first.time_s(1),0,'AbsTol',eps);
verifyEqual(testCase,first.progress(end),moderate.metrics.final_s,'AbsTol',eps);
end


function testMildRecontactIntervalMatchesLoggedTimeout(testCase)
mild=testCase.TestData.r2b.results{2};[rows,summary]= ...
    r3a_recontact_diagnostics(mild,"adaptive");
verifyTrue(testCase,summary.reached);verifyTrue(testCase,all(rows.hybrid_mode=="RECONTACT"));
verifyEqual(testCase,summary.logged_span_s, ...
    mild.config.recontact_timeout_s+mild.config.dt,'AbsTol',1e-12);
end


function testAnalysisDoesNotModifyFormalSources(testCase)
after=r3a_source_manifest(testCase.TestData.paths);
verifyEqual(testCase,testCase.TestData.manifest(:, ...
    {'path','bytes','modified_datenum'}),after(:, ...
    {'path','bytes','modified_datenum'}));
end
