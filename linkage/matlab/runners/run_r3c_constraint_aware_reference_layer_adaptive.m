function run_r3c_constraint_aware_reference_layer_adaptive()
%RUN_R3C_CONSTRAINT_AWARE_REFERENCE_LAYER_ADAPTIVE Formal R3C Stage 2.
%
% The latest Stage 1 gate must explicitly permit Stage 2. Windowed NLS is
% loaded unchanged from the retained R2B configuration builder.

set(groot,'DefaultFigureVisible','off');
runner_dir=fileparts(mfilename('fullpath'));
repo_root=fileparts(fileparts(fileparts(runner_dir)));
root=fullfile(repo_root,'linkage','results','local', ...
    'r3c_constraint_aware_reference_layer');
[gate_path,gate]=latest_permitted_gate(root);
run_id=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss'));
output_dir=fullfile(root,run_id,'stage2_adaptive');mkdir(output_dir);
diary(fullfile(output_dir,'console.log'));cleanup=onCleanup(@()diary('off'));
fprintf(['R3C FORMAL STAGE 2 ADAPTIVE MATLAB: %s\nOUTPUT DIRECTORY: %s\n' ...
    'PERMITTED BY: %s\n'],version,output_dir,gate_path);
nominal=human_two_link_v2_parameters(1.72,75);
base=dynamic_robust_v1_config();config=r3c_constraint_aware_config(base,nominal,.20);
adaptive=dynamic_robust_v1_adaptive_config(config);
calibration=bed_supported_v1_calibrate_hip_height(nominal,config);
plan=hybrid_tube_v1_build_plan(nominal,config);
uncertainty=bed_supported_v1_registered_uncertainty_set(nominal);
names=["nominal","mild","moderate","adverse"];plants=cell(1,4);plants{1}=nominal;
for index=1:3
    plants{index+1}=bed_supported_v1_parameter_override( ...
        nominal,uncertainty.combined_cases(index).override);
end
results=cell(1,4);records=[];initializations=cell(1,4);
for index=1:4
    name=names(index);case_config=config;case_config.case_name="r3c_adaptive_"+name;
    initializations{index}=dynamic_robust_v1_initial_admissibility( ...
        nominal,plants{index},calibration,case_config,nominal);
    results{index}=simulate_dynamic_robust_load_transfer_v1(case_config, ...
        nominal,plants{index},plan,calibration,initializations{index}, ...
        nominal,adaptive);
    row=r3c_case_record(name,"adaptive_windowed_nls",results{index});
    if isempty(records),records=row;else,records(end+1)=row;end %#ok<AGROW>
    case_dir=fullfile(output_dir,char(name));mkdir(case_dir);
    result=results{index};initialization=initializations{index}; %#ok<NASGU>
    save(fullfile(case_dir,'result.mat'),'result','initialization','-v7.3');
    r3c_create_artifacts(result,case_dir,ismember(name,["moderate","adverse"]));
    if result.adaptive_enabled
        dynamic_robust_v1_adaptive_create_artifacts(result,case_dir);
    end
    fprintf(['ADAPTIVE %s status=%s t=%.3f s=%.6f q2clear=%.6gdeg ' ...
        'soft=%d force=%d ID=%d/%d/%d interventions=%.3fs states=%s\n'], ...
        name,row.classification,row.duration_s,row.progress, ...
        row.min_q2_soft_clearance_deg,row.soft_limit_samples, ...
        row.force_violation_samples,row.accepted_updates,row.rejected_updates, ...
        row.solver_failures,row.total_intervention_time_s,row.safety_sequence);
end
save(fullfile(output_dir,'formal_adaptive_results.mat'),'results','records', ...
    'initializations','names','plants','nominal','base','config','adaptive', ...
    'calibration','plan','uncertainty','gate_path','gate','-v7.3');
writetable(struct2table(records),fullfile(output_dir,'case_metrics.csv'));
r3c_create_comparison_figures(gate.results,results,repo_root,output_dir);
end


function [path,data]=latest_permitted_gate(root)
entries=dir(root);entries=entries([entries.isdir]);
entries=entries(~ismember({entries.name},{'.','..'}));
names=string({entries.name});[~,order]=sort(names,'descend');
for index=order
    candidate=fullfile(entries(index).folder,entries(index).name, ...
        'stage1_oracle','formal_oracle_gate.mat');
    if isfile(candidate)
        data=load(candidate);
        if isfield(data,'stage2_permitted') && data.stage2_permitted
            path=candidate;return;
        end
    end
end
error('R3C:Stage1GateNotPermitted', ...
    'No reviewed Stage 1 oracle gate permits adaptive Stage 2.');
end
