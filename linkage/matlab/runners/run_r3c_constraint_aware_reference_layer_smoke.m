function run_r3c_constraint_aware_reference_layer_smoke()
%RUN_R3C_CONSTRAINT_AWARE_REFERENCE_LAYER_SMOKE Mechanical buffer sensitivity.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'r3c_constraint_aware_reference_layer_smoke');
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id);mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf('R3C MECHANICAL SMOKE MATLAB: %s\nOUTPUT DIRECTORY: %s\n', ...
    version,output_dir);
nominal=human_two_link_v2_parameters(1.72,75);
base=dynamic_robust_v1_config();base.max_time_s=6;
calibration=bed_supported_v1_calibrate_hip_height(nominal,base);
plan=hybrid_tube_v1_build_plan(nominal,base);
cases=dynamic_robust_v1_oracle_case_set(nominal);item=cases(3);
fractions=[.15,.20,.25];results=cell(size(fractions));records=[];
for index=1:numel(fractions)
    config=r3c_constraint_aware_config(base,nominal,fractions(index));
    config.case_name="r3c_smoke_oracle_moderate_"+string(fractions(index));
    init=dynamic_robust_v1_initial_admissibility(nominal, ...
        item.plant_parameters,calibration,config,item.controller_model_parameters);
    results{index}=simulate_dynamic_robust_load_transfer_v1(config,nominal, ...
        item.plant_parameters,plan,calibration,init,item.controller_model_parameters);
    row=r3c_case_record("oracle_moderate", ...
        "oracle_warning_fraction_"+string(fractions(index)),results{index});
    if isempty(records),records=row;else,records(end+1)=row;end %#ok<AGROW>
    fprintf(['SMOKE fraction=%.2f status=%s t=%.3f s=%.6f ' ...
        'q2clear=%.6gdeg first=%.3fs states=%s\n'],fractions(index), ...
        row.classification,row.duration_s,row.progress, ...
        row.min_q2_soft_clearance_deg,row.first_intervention_time_s, ...
        row.safety_sequence);
end
save(fullfile(output_dir,'smoke_results.mat'),'results','records', ...
    'fractions','base','nominal','item','-v7.3');
writetable(struct2table(records),fullfile(output_dir,'smoke_metrics.csv'));
end
