function run_dynamic_robust_load_transfer_v1_adaptive_offline_replay()
%RUN_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_OFFLINE_REPLAY R2B gate.
%
% This replays already-recorded R1 transitions. It is an implementation and
% identifiability gate, not a formal adaptive-control result.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
source_dir=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1','20260815_171801');
output_root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking_r2b_offline_replay');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(output_root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R2B OFFLINE REPLAY GATE (NOT FORMAL) MATLAB: %s\n',version);
fprintf('SOURCE DIRECTORY: %s\nOUTPUT DIRECTORY: %s\n',source_dir,output_dir);

nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();
adaptive=dynamic_robust_v1_adaptive_config(config);
names=["nominal","mild","moderate","adverse"];
records=repmat(empty_record(),numel(names),1);
trajectories=cell(1,numel(names));states=cell(1,numel(names));
for case_index=1:numel(names)
    loaded=load(fullfile(source_dir,char(names(case_index)),'result.mat'), ...
        'result');
    result=loaded.result;
    [records(case_index),trajectories{case_index},states{case_index}]= ...
        replay_case(names(case_index),result,nominal,config,adaptive);
    print_record(records(case_index),adaptive);
end

finite_ok=all([records.finite_estimate]);
bounds_ok=all([records.within_bounds]);
nominal_near=[records(1).final_normalized_error]<=sqrt(eps);
mismatch_nonpathological=all([records(2:4).directional_improvement]>= ...
    -100*eps);
at_least_one_improves=any([records(2:4).directional_improvement]>100*eps);
updates_exist=any([records(2:4).accepted_updates]>0);
gate=struct('passed',finite_ok && bounds_ok && nominal_near && ...
    mismatch_nonpathological && at_least_one_improves && updates_exist, ...
    'finite_ok',finite_ok,'bounds_ok',bounds_ok, ...
    'nominal_near',nominal_near, ...
    'mismatch_nonpathological',mismatch_nonpathological, ...
    'at_least_one_improves',at_least_one_improves, ...
    'updates_exist',updates_exist, ...
    'closed_loop_connection_allowed',false);
fprintf(['OFFLINE REPLAY GATE passed=%d finite=%d bounds=%d nominal=%d ' ...
    'nonpathological=%d improves=%d updates=%d\n'],gate.passed, ...
    gate.finite_ok,gate.bounds_ok,gate.nominal_near, ...
    gate.mismatch_nonpathological,gate.at_least_one_improves, ...
    gate.updates_exist);
save(fullfile(output_dir,'offline_replay_result.mat'),'records', ...
    'trajectories','states','gate','nominal','config','adaptive', ...
    'source_dir','-v7.3');
writetable(struct2table(records),fullfile(output_dir,'replay_summary.csv'));
write_updates(trajectories,names,fullfile(output_dir,'replay_updates.csv'));
if ~gate.passed
    error('DynamicRobustV1:AdaptiveReplayGateFailed', ...
        'Offline replay did not authorize closed-loop adaptive integration.');
end
end


function [record,trajectory,state]=replay_case( ...
        name,result,nominal,config,adaptive)
state=dynamic_robust_v1_adaptive_initial_state(nominal,adaptive);
trajectory=repmat(empty_update(),0,1);
for index=1:numel(result.t)-1
    [state,details]=dynamic_robust_v1_adaptive_add_transition( ...
        state,result.state(:,index),result.robot_force_N(:,index), ...
        result.state(:,index+1),index+1,nominal,result.h_hip_m, ...
        config,adaptive,true);
    if details.attempted
        update=empty_update();update.sample_index=index+1;
        update.time_s=result.t(index+1);update.status=details.status;
        update.accepted=details.accepted;update.fit_rms=details.fit_rms;
        update.current_fit_rms=details.current_fit_rms;
        update.rank=details.rank;update.condition_number=details.condition_number;
        update.solve_time_s=details.solve_time_s;
        update.theta_raw_json=string(jsonencode(details.theta_raw));
        update.theta_model_json=string(jsonencode(details.theta_model));
        trajectory(end+1)=update; %#ok<AGROW>
    end
end
theta_true=dynamic_robust_v1_adaptive_theta_from_parameters( ...
    nominal,result.plant_parameters);
initial_error=norm((adaptive.theta_nominal-theta_true)./adaptive.theta_range);
final_error=norm((state.theta_model-theta_true)./adaptive.theta_range);
record=empty_record();record.case_name=name;
record.initial_theta_json=string(jsonencode(adaptive.theta_nominal));
record.final_raw_theta_json=string(jsonencode(state.theta_raw));
record.final_model_theta_json=string(jsonencode(state.theta_model));
record.true_theta_json=string(jsonencode(theta_true));
record.initial_normalized_error=initial_error;
record.final_normalized_error=final_error;
record.directional_improvement=initial_error-final_error;
record.accepted_updates=state.accepted_updates;
record.rejected_updates=state.rejected_updates;
record.solver_failures=state.solver_failures;
record.solve_attempts=state.solve_attempts;
if isnan(state.first_accepted_sample)
    record.first_accepted_time_s=NaN;
else
    record.first_accepted_time_s=result.t(state.first_accepted_sample);
end
record.final_fit_rms=state.last_fit_rms;
record.final_rank=state.last_rank;
record.final_condition_number=state.last_condition_number;
record.mean_solve_time_s=state.total_solve_time_s/max(1,state.solve_attempts);
record.max_solve_time_s=max_solve_time(trajectory);
record.finite_estimate=all(isfinite([state.theta_raw;state.theta_model]));
record.within_bounds=all(state.theta_model>=adaptive.theta_min & ...
    state.theta_model<=adaptive.theta_max);
end


function row=empty_record()
row=struct('case_name',"",'initial_theta_json',"", ...
    'final_raw_theta_json',"",'final_model_theta_json',"", ...
    'true_theta_json',"",'initial_normalized_error',NaN, ...
    'final_normalized_error',NaN,'directional_improvement',NaN, ...
    'accepted_updates',0,'rejected_updates',0,'solver_failures',0, ...
    'solve_attempts',0,'first_accepted_time_s',NaN,'final_fit_rms',NaN, ...
    'final_rank',0,'final_condition_number',NaN, ...
    'mean_solve_time_s',NaN,'max_solve_time_s',NaN, ...
    'finite_estimate',false,'within_bounds',false);
end


function row=empty_update()
row=struct('case_name',"",'sample_index',NaN,'time_s',NaN, ...
    'status',"",'accepted',false,'fit_rms',NaN, ...
    'current_fit_rms',NaN,'rank',NaN,'condition_number',NaN, ...
    'solve_time_s',NaN, ...
    'theta_raw_json',"",'theta_model_json',"");
end


function write_updates(trajectories,names,path)
rows=repmat(empty_update(),0,1);
for case_index=1:numel(names)
    items=trajectories{case_index};
    for index=1:numel(items)
        items(index).case_name=names(case_index);
    end
    rows=[rows;items(:)]; %#ok<AGROW>
end
writetable(struct2table(rows),path);
end


function print_record(record,adaptive)
fprintf(['REPLAY %s initial_error=%.9g final_error=%.9g direction=%.9g ' ...
    'accepted=%d rejected=%d failures=%d first=%.9g s fit=%.9g ' ...
    'rank=%d cond=%.9g solve_mean/max=%.6g/%.6g s\n'],record.case_name, ...
    record.initial_normalized_error,record.final_normalized_error, ...
    record.directional_improvement,record.accepted_updates, ...
    record.rejected_updates,record.solver_failures, ...
    record.first_accepted_time_s,record.final_fit_rms, ...
    record.final_rank,record.final_condition_number, ...
    record.mean_solve_time_s,record.max_solve_time_s);
fprintf('  nominal=%s\n  raw=%s\n  model=%s\n  true=%s\n', ...
    jsonencode(adaptive.theta_nominal),record.final_raw_theta_json, ...
    record.final_model_theta_json,record.true_theta_json);
end


function value=max_solve_time(trajectory)
if isempty(trajectory),value=NaN;else,value=max([trajectory.solve_time_s]);end
end
