function run_r3b_recontact_margin_smoke()
%RUN_R3B_RECONTACT_MARGIN_SMOKE Mechanical oracle-mild integration smoke.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'r3b_recontact_margin_controller_smoke');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
nominal=human_two_link_v2_parameters(1.72,75);
base=dynamic_robust_v1_config();config=r3b_recontact_margin_config(base,1);
config.max_time_s=16.5;
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
plan=hybrid_tube_v1_build_plan(nominal,config);
uncertainty=bed_supported_v1_registered_uncertainty_set(nominal);
plant=bed_supported_v1_parameter_override(nominal, ...
    uncertainty.combined_cases(1).override);
initialization=dynamic_robust_v1_initial_admissibility( ...
    nominal,plant,calibration,config,plant);
result=simulate_dynamic_robust_load_transfer_v1(config,nominal,plant, ...
    plan,calibration,initialization,plant);
if ~any(result.mode=="RECONTACT")
    error('R3B:SmokeDidNotReachRecontact', ...
        'The fixed 16.5 s oracle-mild smoke did not exercise RECONTACT.');
end
metrics=r3b_recontact_metrics(result);
save(fullfile(output_dir,'smoke_result.mat'),'result','metrics', ...
    'config','base','-v7.3');
fprintf(['R3B SMOKE ONLY status=%s t=%.3f recontact=%.3f ' ...
    'peakBed=%.6g maxPen=%.6g maxRefDev=%.6g\n'], ...
    metrics.classification,metrics.duration_s,metrics.recontact_duration_s, ...
    metrics.peak_bed_force_N,metrics.maximum_penetration_m, ...
    metrics.maximum_reference_deviation_deg);
end
