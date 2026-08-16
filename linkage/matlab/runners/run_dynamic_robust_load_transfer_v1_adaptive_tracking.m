function run_dynamic_robust_load_transfer_v1_adaptive_tracking()
%RUN_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_TRACKING Formal R2B experiment.
%
% One fixed Windowed-NLS configuration is used for nominal, mild, moderate,
% and adverse. Every controller model starts nominal. True parameters are
% used only by the plant and post-hoc reporting.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking_r2b');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R2B WINDOWED-NLS ADAPTIVE TRACKING MATLAB: %s\n',version);
fprintf('OUTPUT DIRECTORY: %s\n',output_dir);
fprintf(['FORMAL COMMAND: /Users/hankli/Desktop/MATLAB_R2025b.app/bin/' ...
    'matlab -batch "addpath(genpath(''linkage/matlab'')); ' ...
    'run_dynamic_robust_load_transfer_v1_adaptive_tracking"\n']);

nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();
adaptive=dynamic_robust_v1_adaptive_config(config);
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
plan=hybrid_tube_v1_build_plan(nominal,config);
uncertainty=bed_supported_v1_registered_uncertainty_set(nominal);
names=["nominal","mild","moderate","adverse"];
plants=cell(1,4);plants{1}=nominal;
for index=1:3
    plants{index+1}=bed_supported_v1_parameter_override( ...
        nominal,uncertainty.combined_cases(index).override);
end
results=cell(1,4);initializations=cell(1,4);
records=repmat(empty_record(),4,1);checkpoint_rows=repmat(empty_checkpoint(),0,1);
for index=1:4
    [results{index},initializations{index}]=run_case(names(index), ...
        plants{index},nominal,config,adaptive,plan,calibration,output_dir);
    records(index)=make_record(names(index),results{index},index);
    checkpoint_rows=[checkpoint_rows;make_checkpoints( ...
        names(index),results{index})]; %#ok<AGROW>
end
save(fullfile(output_dir,'formal_adaptive_results.mat'),'results', ...
    'initializations','records','checkpoint_rows','plants','names', ...
    'nominal','config','adaptive','calibration','plan','uncertainty','-v7.3');
writetable(struct2table(records),fullfile(output_dir,'case_metrics.csv'));
writetable(struct2table(checkpoint_rows), ...
    fullfile(output_dir,'identifier_checkpoints.csv'));
write_summary(fullfile(output_dir,'summary.txt'),records,adaptive);
if ~isempty(findall(groot,'Type','figure','Visible','on'))
    error('DynamicRobustV1:VisibleFigure', ...
        'R2B formal runner created a visible figure.');
end
end


function [result,initialization]=run_case( ...
        name,plant,nominal,config,adaptive,plan,calibration,output_dir)
fprintf('RUN ADAPTIVE CASE %s\n',name);
case_config=config;case_config.case_name="r2b_adaptive_"+name;
initialization=dynamic_robust_v1_initial_admissibility( ...
    nominal,plant,calibration,case_config,nominal);
if ~initialization.pass
    error('DynamicRobustV1:InitialAdmissibilityFailed', ...
        'Adaptive case %s failed initial admissibility.',name);
end
case_dir=fullfile(output_dir,char(name));mkdir(case_dir);
result=simulate_dynamic_robust_load_transfer_v1(case_config,nominal, ...
    plant,plan,calibration,initialization,nominal,adaptive);
save(fullfile(case_dir,'result.mat'),'result','initialization','-v7.3');
dynamic_robust_v1_create_artifacts(result,case_dir);
dynamic_robust_v1_adaptive_create_artifacts(result,case_dir);
row=make_record(name,result,name_index(name));
fprintf(['ADAPTIVE CASE %s status=%s phase=%s t=%.3f survival=%.3f ' ...
    's=%.6f transfer=%d accepted=%d rejected=%d failures=%d ' ...
    'parameter_error=%.6g->%.6g progress_gap=%.6g survival_gap=%.6g\n'], ...
    name,row.final_status,row.failure_phase,row.duration_s, ...
    row.tracking_survival_s,row.final_progress,row.transfer_begins, ...
    row.accepted_updates,row.rejected_updates,row.solver_failures, ...
    row.initial_parameter_error,row.final_parameter_error, ...
    row.progress_gap_closure,row.survival_gap_closure);
end


function row=empty_record()
row=struct('case_name',"",'final_status',"",'failure_phase',"", ...
    'duration_s',NaN,'completion_time_s',NaN,'final_progress',NaN, ...
    'tracking_entered',false,'takeover_duration_s',NaN, ...
    'tracking_survival_s',NaN,'transfer_begins',false, ...
    'transfer_begin_time_s',NaN,'task_completes',false, ...
    'q1_min_deg',NaN,'q1_max_deg',NaN,'q2_min_deg',NaN,'q2_max_deg',NaN, ...
    'minimum_rom_margin_deg',NaN,'minimum_soft_margin_deg',NaN, ...
    'soft_limit_samples',0,'rom_violation_samples',0, ...
    'peak_soft_limit_torque_Nm',NaN,'peak_component_N',NaN, ...
    'peak_force_norm_N',NaN,'force_saturation_fraction',NaN, ...
    'minimum_force_margin_N',NaN,'minimum_bed_support_N',NaN, ...
    'peak_bed_support_N',NaN,'minimum_dynamic_margin_N',NaN, ...
    'accepted_updates',0,'rejected_updates',0,'solver_failures',0, ...
    'first_accepted_time_s',NaN,'final_fit_rms',NaN, ...
    'mean_solve_time_s',NaN,'max_solve_time_s',NaN, ...
    'initial_parameter_error',NaN,'final_parameter_error',NaN, ...
    'true_theta_json',"",'initial_theta_json',"", ...
    'final_raw_theta_json',"",'final_model_theta_json',"", ...
    'progress_gap_closure',NaN,'survival_gap_closure',NaN, ...
    'state_sequence',"");
end


function row=make_record(name,result,case_index)
m=result.metrics;id=m.identifier;c=result.config;p=result.plant_parameters;
q=result.state(1:2,:);force=result.robot_force_N;
row=empty_record();row.case_name=name;row.final_status=m.classification;
row.failure_phase=m.failure_phase;row.duration_s=m.duration_s;
row.completion_time_s=m.completion_time_s;row.final_progress=m.final_s;
row.tracking_entered=m.takeover_tracking_entered;
row.takeover_duration_s=m.takeover_duration_s;
if row.tracking_entered,row.tracking_survival_s=m.duration_s-m.takeover_duration_s;end
row.transfer_begins=m.events.transfer_ready.found;
row.transfer_begin_time_s=m.events.transfer_ready.time_s;
row.task_completes=result.terminal_state=="TASK_COMPLETE";
qdeg=rad2deg(q);row.q1_min_deg=min(qdeg(1,:));row.q1_max_deg=max(qdeg(1,:));
row.q2_min_deg=min(qdeg(2,:));row.q2_max_deg=max(qdeg(2,:));
row.minimum_rom_margin_deg=rad2deg(min([q-p.q_min;p.q_max-q],[],'all'));
row.minimum_soft_margin_deg=m.min_soft_zone_clearance_deg;
row.soft_limit_samples=m.soft_limit_active_samples;
row.rom_violation_samples=m.rom_violation_samples;
row.peak_soft_limit_torque_Nm=m.max_soft_limit_torque_Nm;
row.peak_component_N=max(abs(force),[],'all');
row.peak_force_norm_N=m.peak_force_norm_N;
row.force_saturation_fraction=m.force_saturation_fraction;
row.minimum_force_margin_N=min([force-c.u_min(:);c.u_max(:)-force],[],'all');
row.minimum_bed_support_N=min(result.bed_force_N);
row.peak_bed_support_N=m.peak_bed_force_N;
row.minimum_dynamic_margin_N=m.min_predicted_dynamic_margin_N;
row.accepted_updates=id.accepted_updates;row.rejected_updates=id.rejected_updates;
row.solver_failures=id.solver_failures;
row.first_accepted_time_s=id.first_accepted_time_s;
row.final_fit_rms=id.final_fit_rms;row.mean_solve_time_s=id.mean_solve_time_s;
row.max_solve_time_s=id.max_solve_time_s;
row.initial_parameter_error=id.initial_normalized_error;
row.final_parameter_error=id.final_normalized_error;
row.true_theta_json=string(jsonencode(id.true_theta));
row.initial_theta_json=string(jsonencode(result.adaptive_config.theta_nominal));
row.final_raw_theta_json=string(jsonencode(id.final_raw_theta));
row.final_model_theta_json=string(jsonencode(id.final_model_theta));
[row.progress_gap_closure,row.survival_gap_closure]= ...
    gap_closure(case_index,row.final_progress,row.tracking_survival_s);
row.state_sequence=strjoin(m.state_sequence," -> ");
end


function [progress_gap,survival_gap]=gap_closure(index,progress,survival)
baseline_progress=[1,.109980637586493,.156077453865264,.16330309931886];
oracle_progress=[1,1,.198248577226148,.162124103070759];
baseline_survival=[22.492,.524,.718,.546];
oracle_survival=[22.492,22.49,4.068,3.49];
progress_gap=NaN;survival_gap=NaN;
if oracle_progress(index)>baseline_progress(index)+eps
    progress_gap=(progress-baseline_progress(index))/ ...
        (oracle_progress(index)-baseline_progress(index));
end
if oracle_survival(index)>baseline_survival(index)+eps
    survival_gap=(survival-baseline_survival(index))/ ...
        (oracle_survival(index)-baseline_survival(index));
end
end


function rows=make_checkpoints(name,result)
indices=1;labels="start";
tracking_index=find(result.takeover_mode=="TRACKING",1,'first');
if ~isempty(tracking_index)
    indices(end+1)=tracking_index;labels(end+1)="tracking_entry";
end
for target=[.25,.50]
    index=find(result.task_s>=target,1,'first');
    if isempty(index)
        index=numel(result.t);label="pre_failure_for_"+string(round(100*target))+"pct";
    else
        label=string(round(100*target))+"pct_progress";
    end
    indices(end+1)=index;labels(end+1)=label; %#ok<AGROW>
end
indices(end+1)=numel(result.t);labels(end+1)="final";
truth=result.metrics.identifier.true_theta;a=result.adaptive_config;
rows=repmat(empty_checkpoint(),numel(indices),1);
for item_index=1:numel(indices)
    index=indices(item_index);model=result.identifier_theta_model(:,index);
    rows(item_index).case_name=name;rows(item_index).checkpoint=labels(item_index);
    rows(item_index).time_s=result.t(index);rows(item_index).progress=result.task_s(index);
    rows(item_index).identifier_status=result.identifier_status(index);
    rows(item_index).theta_raw_json=string(jsonencode( ...
        result.identifier_theta_raw(:,index)));
    rows(item_index).theta_model_json=string(jsonencode(model));
    rows(item_index).theta_true_json=string(jsonencode(truth));
    rows(item_index).normalized_error=norm((model-truth)./a.theta_range);
    rows(item_index).fit_rms=result.identifier_fit_rms(index);
end
end


function row=empty_checkpoint()
row=struct('case_name',"",'checkpoint',"",'time_s',NaN,'progress',NaN, ...
    'identifier_status',"",'theta_raw_json',"",'theta_model_json',"", ...
    'theta_true_json',"",'normalized_error',NaN,'fit_rms',NaN);
end


function write_summary(path,records,adaptive)
file=fopen(path,'w');assert(file>=0);cleanup=onCleanup(@()fclose(file));
fprintf(file,'R2B Windowed-NLS adaptive tracking\nMATLAB %s\n',version);
fprintf(file,'window=%d samples, cadence=%d samples, no deliberate excitation\n', ...
    adaptive.window_size,adaptive.update_interval);
for index=1:numel(records)
    r=records(index);fprintf(file,['%s: %s, phase %s, t %.9g s, ' ...
        'survival %.9g s, progress %.9g, transfer %d, accepted/rejected/' ...
        'failures %d/%d/%d, error %.9g -> %.9g, progress gap %.9g, ' ...
        'survival gap %.9g\n'],r.case_name,r.final_status,r.failure_phase, ...
        r.duration_s,r.tracking_survival_s,r.final_progress,r.transfer_begins, ...
        r.accepted_updates,r.rejected_updates,r.solver_failures, ...
        r.initial_parameter_error,r.final_parameter_error, ...
        r.progress_gap_closure,r.survival_gap_closure);
end
end


function index=name_index(name)
names=["nominal","mild","moderate","adverse"];
index=find(names==name,1);
end
