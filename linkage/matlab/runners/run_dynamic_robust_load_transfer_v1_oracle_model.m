function run_dynamic_robust_load_transfer_v1_oracle_model()
%RUN_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ORACLE_MODEL Formal R2A diagnostic.
%
% ORACLE DIAGNOSTIC ONLY: for each fixed case, the tracking-controller model
% equals the true plant from t=0. No parameter estimation or online update is
% present. The unchanged R1 safe takeover remains active.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_oracle_model_r2a');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R2A ORACLE MODEL DIAGNOSTIC ONLY MATLAB: %s\n',version);
fprintf('OUTPUT DIRECTORY: %s\n',output_dir);
fprintf(['FORMAL COMMAND: /Users/hankli/Desktop/MATLAB_R2025b.app/bin/' ...
    'matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_dynamic_robust_load_transfer_v1_oracle_model"\n']);
fprintf(['ORACLE DEFINITION: fixed theta_model = theta_true from t=0; ' ...
    'no estimator or runtime parameter update.\n']);

nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
plan=hybrid_tube_v1_build_plan(nominal,config);
oracle_cases=dynamic_robust_v1_oracle_case_set(nominal);
results=cell(1,numel(oracle_cases));
initializations=cell(1,numel(oracle_cases));
records=repmat(empty_record(),numel(oracle_cases),1);

for index=1:numel(oracle_cases)
    item=oracle_cases(index);
    [results{index},initializations{index}]=run_case( ...
        item,nominal,config,plan,calibration,output_dir);
    records(index)=make_record(item,results{index});
end

save(fullfile(output_dir,'formal_oracle_results.mat'),'results', ...
    'initializations','records','oracle_cases','nominal','config', ...
    'calibration','plan','-v7.3');
writetable(struct2table(records),fullfile(output_dir,'case_metrics.csv'));
write_summary(fullfile(output_dir,'summary.txt'),records);
create_cross_case_figure(records,output_dir);
if ~isempty(findall(groot,'Type','figure','Visible','on'))
    error('DynamicRobustV1:VisibleFigure', ...
        'R2A formal runner created a visible figure.');
end
end


function [result,initialization]=run_case( ...
        item,nominal,config,plan,calibration,output_dir)
name=item.case_name;plant=item.plant_parameters;
controller_model=item.controller_model_parameters;
case_config=config;case_config.case_name="r2a_"+name;
fprintf('RUN ORACLE CASE %s\n',name);
initialization=dynamic_robust_v1_initial_admissibility( ...
    nominal,plant,calibration,case_config,controller_model);
if ~initialization.pass
    error('DynamicRobustV1:InitialAdmissibilityFailed', ...
        'Oracle case %s failed initial admissibility.',name);
end
case_dir=fullfile(output_dir,char(name));mkdir(case_dir);
result=simulate_dynamic_robust_load_transfer_v1(case_config,nominal, ...
    plant,plan,calibration,initialization,controller_model);
save(fullfile(case_dir,'result.mat'),'result','initialization','item','-v7.3');
dynamic_robust_v1_create_artifacts(result,case_dir);
row=make_record(item,result);
fprintf(['ORACLE CASE %s status=%s phase=%s t=%.3f tracking=%.3f ' ...
    'survival=%.3f s=%.6f transfer=%d complete=%d ' ...
    'theta_gap=%.12g dynamic_gap=%.12gN\n'],name,row.final_status, ...
    row.failure_phase,row.duration_s,row.tracking_entry_time_s, ...
    row.tracking_survival_s,row.final_progress,row.transfer_begins, ...
    row.task_completes,row.oracle_mismatch_norm, ...
    row.max_model_realized_dynamic_margin_gap_N);
end


function row=empty_record()
row=struct('case_name',"",'oracle_diagnostic',true, ...
    'final_status',"",'failure_reason',"",'failure_phase',"", ...
    'duration_s',NaN,'completion_time_s',NaN,'final_progress',NaN, ...
    'takeover_duration_s',NaN,'tracking_entry_time_s',NaN, ...
    'tracking_survival_s',NaN,'tracking_entered',false, ...
    'takeover_soft_limit_safe',false,'q1_min_deg',NaN,'q1_max_deg',NaN, ...
    'q2_min_deg',NaN,'q2_max_deg',NaN,'minimum_rom_margin_deg',NaN, ...
    'minimum_soft_limit_margin_deg',NaN, ...
    'peak_soft_limit_torque_Nm',NaN,'peak_parallel_N',NaN, ...
    'peak_perp_N',NaN,'peak_actuator_component_N',NaN, ...
    'peak_robot_force_norm_N',NaN,'minimum_force_bound_margin_N',NaN, ...
    'minimum_bed_support_N',NaN,'peak_bed_support_N',NaN, ...
    'transfer_begins',false,'transfer_begin_time_s',NaN, ...
    'task_completes',false,'min_oracle_model_dynamic_margin_N',NaN, ...
    'min_realized_dynamic_margin_N',NaN, ...
    'max_model_realized_dynamic_margin_gap_N',NaN, ...
    'rms_model_realized_dynamic_margin_gap_N',NaN, ...
    'oracle_mismatch_norm',NaN,'nominal_model_mismatch_norm',NaN, ...
    'theta_true_json',"",'theta_model_json',"",'state_sequence',"");
end


function row=make_record(item,result)
m=result.metrics;q_deg=rad2deg(result.state(1:2,:));
p=result.plant_parameters;c=result.config;
rom_margin=min([result.state(1:2,:)-p.q_min; ...
    p.q_max-result.state(1:2,:)],[],'all');
force_margin=min([result.robot_force_N-c.u_min(:); ...
    c.u_max(:)-result.robot_force_N],[],'all');
finite_gap=isfinite(result.dynamic_margin_N) & ...
    isfinite(result.realized_dynamic_margin_N);
if any(finite_gap)
    gap=result.dynamic_margin_N(finite_gap)- ...
        result.realized_dynamic_margin_N(finite_gap);
    max_gap=max(abs(gap));rms_gap=sqrt(mean(gap.^2));
else
    max_gap=NaN;rms_gap=NaN;
end
transfer_index=find(result.mode=="TRANSFER_READY",1,'first');
tracking_index=find(result.takeover_mode=="TRACKING",1,'first');
row=empty_record();row.case_name=item.case_name;
row.final_status=result.terminal_state;row.failure_reason=result.terminal_state;
row.failure_phase=m.failure_phase;row.duration_s=m.duration_s;
row.completion_time_s=m.completion_time_s;row.final_progress=m.final_s;
row.takeover_duration_s=m.takeover_duration_s;
row.tracking_entered=m.takeover_tracking_entered;
if row.tracking_entered
    row.tracking_entry_time_s=result.t(tracking_index);
    row.tracking_survival_s=max(0,m.duration_s-m.takeover_duration_s);
end
takeover_indices=result.takeover_mode~="TRACKING";
row.takeover_soft_limit_safe=~any(result.soft_limit_active(takeover_indices));
row.q1_min_deg=min(q_deg(1,:));row.q1_max_deg=max(q_deg(1,:));
row.q2_min_deg=min(q_deg(2,:));row.q2_max_deg=max(q_deg(2,:));
row.minimum_rom_margin_deg=rad2deg(rom_margin);
row.minimum_soft_limit_margin_deg=m.min_soft_zone_clearance_deg;
row.peak_soft_limit_torque_Nm=m.max_soft_limit_torque_Nm;
row.peak_parallel_N=m.peak_abs_parallel_N;
row.peak_perp_N=m.peak_abs_perp_N;
row.peak_actuator_component_N=max(abs(result.robot_force_N),[],'all');
row.peak_robot_force_norm_N=m.peak_force_norm_N;
row.minimum_force_bound_margin_N=force_margin;
row.minimum_bed_support_N=min(result.bed_force_N);
row.peak_bed_support_N=m.peak_bed_force_N;
row.transfer_begins=~isempty(transfer_index);
if ~isempty(transfer_index),row.transfer_begin_time_s=result.t(transfer_index);end
row.task_completes=result.terminal_state=="TASK_COMPLETE";
row.min_oracle_model_dynamic_margin_N=m.min_predicted_dynamic_margin_N;
row.min_realized_dynamic_margin_N=m.min_realized_dynamic_margin_N;
row.max_model_realized_dynamic_margin_gap_N=max_gap;
row.rms_model_realized_dynamic_margin_gap_N=rms_gap;
row.oracle_mismatch_norm=item.oracle_mismatch_norm;
row.nominal_model_mismatch_norm=item.nominal_model_mismatch_norm;
row.theta_true_json=string(jsonencode(item.plant_parameters));
row.theta_model_json=string(jsonencode(item.controller_model_parameters));
row.state_sequence=strjoin(m.state_sequence," -> ");
end


function write_summary(path,records)
file=fopen(path,'w');assert(file>=0);cleanup=onCleanup(@()fclose(file));
fprintf(file,'R2A oracle model diagnostic only\nMATLAB %s\n',version);
fprintf(file,['theta_model is fixed equal to theta_true from t=0. ' ...
    'This is not a deployable or adaptive controller.\n']);
for index=1:numel(records)
    r=records(index);
    fprintf(file,['%s: %s, phase %s, takeover %.9g s, tracking survival ' ...
        '%.9g s, final s %.9g, transfer %d, complete %d, min soft ' ...
        '%.9g deg, peak robot %.9g N, min bed %.9g N, min dynamic ' ...
        '%.9g N, model-realized gap %.9g N, theta gap %.9g\n'], ...
        r.case_name,r.final_status,r.failure_phase,r.takeover_duration_s, ...
        r.tracking_survival_s,r.final_progress,r.transfer_begins, ...
        r.task_completes,r.minimum_soft_limit_margin_deg, ...
        r.peak_robot_force_norm_N,r.minimum_bed_support_N, ...
        r.min_oracle_model_dynamic_margin_N, ...
        r.max_model_realized_dynamic_margin_gap_N,r.oracle_mismatch_norm);
end
end


function create_cross_case_figure(records,output_dir)
T=struct2table(records);fig=figure('Visible','off','Color','w');
tiledlayout(fig,1,2);
nexttile;bar(categorical(T.case_name), ...
    [T.tracking_survival_s,T.final_progress]);grid on;
legend('tracking survival (s)','final progress','Location','best');
nexttile;bar(categorical(T.case_name), ...
    [T.minimum_soft_limit_margin_deg,T.minimum_force_bound_margin_N]);
grid on;legend('min soft margin (deg)','min force margin (N)', ...
    'Location','best');
exportgraphics(fig,fullfile(output_dir,'oracle_cross_case_summary.png'), ...
    'Resolution',180);close(fig);
end
