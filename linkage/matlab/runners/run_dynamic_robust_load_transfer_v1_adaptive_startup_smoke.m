function run_dynamic_robust_load_transfer_v1_adaptive_startup_smoke()
%RUN_DYNAMIC_ROBUST_LOAD_TRANSFER_V1_ADAPTIVE_STARTUP_SMOKE R2B short check.
%
% Six simulated seconds are used only to observe estimator attempts, accepted
% or rejected updates, R1 traversal, and immediate numerical/safety behavior.
% This is not a formal scientific result.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking_r2b_startup_smoke');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R2B ADAPTIVE STARTUP SMOKE ONLY (NON-FORMAL) MATLAB: %s\n',version);
fprintf('OUTPUT DIRECTORY: %s\n',output_dir);

nominal=human_two_link_v2_parameters(1.72,75);
config=dynamic_robust_v1_config();config.max_time_s=6;
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
results=cell(1,4);rows=repmat(empty_row(),4,1);
for index=1:4
    plant=plants{index};
    initialization=dynamic_robust_v1_initial_admissibility( ...
        nominal,plant,calibration,config,nominal);
    results{index}=simulate_dynamic_robust_load_transfer_v1( ...
        config,nominal,plant,plan,calibration,initialization,nominal,adaptive);
    rows(index)=make_row(names(index),results{index});
    r=rows(index);
    fprintf(['SMOKE %s status=%s phase=%s t=%.3f tracking=%d takeover=%.3f ' ...
        'attempts=%d accepted=%d rejected=%d failures=%d first=%.3f ' ...
        'error=%.6g->%.6g finite=%d soft=%d rom=%d peakComp=%.6gN\n'], ...
        r.case_name,r.final_status,r.failure_phase,r.duration_s, ...
        r.tracking_entered,r.takeover_duration_s,r.solve_attempts, ...
        r.accepted_updates,r.rejected_updates,r.solver_failures, ...
        r.first_accepted_time_s,r.initial_parameter_error, ...
        r.final_parameter_error,r.finite_estimate,r.soft_limit_samples, ...
        r.rom_violation_samples,r.peak_component_N);
end
save(fullfile(output_dir,'startup_smoke_results.mat'),'results','rows', ...
    'plants','names','nominal','config','adaptive','calibration','plan','-v7.3');
writetable(struct2table(rows),fullfile(output_dir,'startup_smoke_metrics.csv'));
end


function row=empty_row()
row=struct('case_name',"",'final_status',"",'failure_phase',"", ...
    'duration_s',NaN,'final_progress',NaN,'tracking_entered',false, ...
    'takeover_duration_s',NaN,'solve_attempts',0,'accepted_updates',0, ...
    'rejected_updates',0,'solver_failures',0, ...
    'first_accepted_time_s',NaN,'initial_parameter_error',NaN, ...
    'final_parameter_error',NaN,'finite_estimate',false, ...
    'soft_limit_samples',0,'rom_violation_samples',0, ...
    'peak_component_N',NaN,'minimum_bed_support_N',NaN);
end


function row=make_row(name,result)
m=result.metrics;id=m.identifier;s=result.identifier_state;
row=empty_row();row.case_name=name;row.final_status=m.classification;
row.failure_phase=m.failure_phase;row.duration_s=m.duration_s;
row.final_progress=m.final_s;row.tracking_entered=m.takeover_tracking_entered;
row.takeover_duration_s=m.takeover_duration_s;
row.solve_attempts=s.solve_attempts;row.accepted_updates=id.accepted_updates;
row.rejected_updates=id.rejected_updates;row.solver_failures=id.solver_failures;
row.first_accepted_time_s=id.first_accepted_time_s;
row.initial_parameter_error=id.initial_normalized_error;
row.final_parameter_error=id.final_normalized_error;
row.finite_estimate=all(isfinite([id.final_raw_theta;id.final_model_theta]));
row.soft_limit_samples=m.soft_limit_active_samples;
row.rom_violation_samples=m.rom_violation_samples;
row.peak_component_N=max(abs(result.robot_force_N),[],'all');
row.minimum_bed_support_N=min(result.bed_force_N);
end
