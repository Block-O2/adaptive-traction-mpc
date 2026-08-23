function output_dir = run_r4_minimal_recovery_corridor()
%RUN_R4_MINIMAL_RECOVERY_CORRIDOR Approved long-running offline R4 study.

runner_dir=fileparts(mfilename('fullpath'));
matlab_root=fileparts(runner_dir);repo_root=fileparts(fileparts(matlab_root));
addpath(genpath(matlab_root));paths=r4_source_paths(repo_root);config=r4_config();
before=r4_source_manifest(paths);anchors=r4_extract_anchors(paths);
stamp=datestr(now,'yyyymmdd_HHMMSS');output_dir=fullfile(paths.output_root,stamp);
if ~exist(output_dir,'dir'),mkdir(output_dir);end
writetable(r4_anchor_table(anchors),fullfile(output_dir,'anchor_states.csv'));
fid=fopen(fullfile(output_dir,'config_snapshot.json'),'w');
fprintf(fid,'%s\n',jsonencode(config,'PrettyPrint',true));fclose(fid);
study=r4_run_study(anchors,config);
writetable(study.point_feasibility_summary, ...
    fullfile(output_dir,'point_feasibility_summary.csv'));
writetable(study.recovery_boundary_summary, ...
    fullfile(output_dir,'recovery_boundary_summary.csv'));
writetable(study.connected_corridor_summary, ...
    fullfile(output_dir,'connected_corridor_summary.csv'));
writetable(study.true_vs_perceived_feasibility, ...
    fullfile(output_dir,'true_vs_perceived_feasibility.csv'));
writetable(study.recovery_paths,fullfile(output_dir,'recovery_paths.csv'));
r4_create_artifacts(output_dir,anchors,study);
r4_write_summary(output_dir,anchors,study,config,before);
after=r4_source_manifest(paths);unchanged=before.bytes==after.bytes & ...
    before.modified_datenum==after.modified_datenum & before.sha256==after.sha256;
manifest=before;manifest.after_bytes=after.bytes;
manifest.after_modified_datenum=after.modified_datenum;
manifest.after_sha256=after.sha256;manifest.unchanged=unchanged;
writetable(manifest,fullfile(output_dir,'source_manifest.csv'));
if ~all(unchanged),error('R4:FrozenSourceMutation','A frozen R3C source changed.');end
save(fullfile(output_dir,'formal_r4_workspace.mat'),'anchors','config', ...
    'paths','manifest','study','-v7.3');
fprintf('R4 offline study complete: %s\n',output_dir);
end
