function run_dynamic_robust_load_transfer_v1_startup_smoke()
%RUN_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_STARTUP_SMOKE R1 non-formal handover check.
%
% This deliberately limited four-second run is mechanical startup evidence,
% not a formal robustness experiment and not an authoritative result.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_startup_smoke');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R1 STARTUP SMOKE ONLY (NON-FORMAL) MATLAB: %s\n',version);
fprintf('OUTPUT DIRECTORY: %s\n',output_dir);

nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();config.max_time_s=4;
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
plan=hybrid_tube_v1_build_plan(nominal,config);
uncertainty=bed_supported_v1_registered_uncertainty_set(nominal);
names=["nominal","mild","moderate","adverse"];
plants=cell(1,4);plants{1}=nominal;
for k=1:3
    plants{k+1}=bed_supported_v1_parameter_override( ...
        nominal,uncertainty.combined_cases(k).override);
end
results=cell(1,4);rows=repmat(empty_row(),4,1);
for k=1:4
    initialization=dynamic_robust_v1_initial_admissibility( ...
        nominal,plants{k},calibration,config);
    results{k}=simulate_dynamic_robust_load_transfer_v1( ...
        config,nominal,plants{k},plan,calibration,initialization);
    rows(k)=make_row(names(k),results{k});
    r=rows(k);
    fprintf(['%s tracking=%d takeover=%.9g s status=%s phase=%s ' ...
        'takeover_min_q1=%.12g deg takeover_min_margin=%.12g deg ' ...
        'hold=%d scaled=%d min_lambda=%.9g final_s=%.9g\n'], ...
        r.case_name,r.tracking_entered,r.takeover_duration_s, ...
        r.final_status,r.failure_phase,r.takeover_min_q1_deg, ...
        r.takeover_min_soft_margin_deg,r.hold_steps,r.scaled_steps, ...
        r.minimum_lambda,r.final_s);
end
save(fullfile(output_dir,'startup_smoke_results.mat'), ...
    'results','rows','nominal','config','calibration','uncertainty','-v7.3');
writetable(struct2table(rows),fullfile(output_dir,'startup_smoke_metrics.csv'));
end


function row=empty_row()
row=struct('case_name',"",'tracking_entered',false, ...
    'takeover_duration_s',NaN,'final_status',"",'failure_phase',"", ...
    'duration_s',NaN,'takeover_min_q1_deg',NaN, ...
    'takeover_min_soft_margin_deg',NaN,'peak_robot_force_N',NaN, ...
    'minimum_bed_support_N',NaN,'hold_steps',NaN,'scaled_steps',NaN, ...
    'full_steps',NaN,'minimum_lambda',NaN,'final_s',NaN);
end


function row=make_row(name,result)
m=result.metrics;row=empty_row();row.case_name=name;
row.tracking_entered=m.takeover_tracking_entered;
row.takeover_duration_s=m.takeover_duration_s;
row.final_status=m.classification;row.failure_phase=m.failure_phase;
row.duration_s=m.duration_s;row.takeover_min_q1_deg=m.takeover_min_q1_deg;
row.takeover_min_soft_margin_deg=m.takeover_min_soft_zone_clearance_deg;
row.peak_robot_force_N=m.peak_force_norm_N;
row.minimum_bed_support_N=min(result.bed_force_N);
row.hold_steps=m.takeover_hold_steps;row.scaled_steps=m.takeover_scaled_steps;
row.full_steps=m.takeover_full_steps;
row.minimum_lambda=m.takeover_minimum_lambda;row.final_s=m.final_s;
end
