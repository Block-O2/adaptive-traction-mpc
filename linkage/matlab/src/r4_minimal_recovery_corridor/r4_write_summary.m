function r4_write_summary(output_dir,anchors,study,config,manifest)
%R4_WRITE_SUMMARY Human-readable offline R4 result summary.

path=fullfile(output_dir,'summary.md');file=fopen(path,'w');
if file<0,error('R4:SummaryWriteFailed','Cannot write %s',path);end
cleanup=onCleanup(@()fclose(file)); %#ok<NASGU>
fprintf(file,'# R4 Minimal Recovery Corridor Study\n\n');
fprintf(file,'Offline diagnostic only. No controller was designed and no R3C closed-loop experiment was rerun.\n\n');
fprintf(file,'## Frozen sources\n\n');
for k=1:height(manifest)
    fprintf(file,'- `%s`: `%s` (SHA-256 `%s`)\n',manifest.source(k), ...
        manifest.path(k),manifest.sha256(k));
end
fprintf(file,'\n## Configuration\n\n');
fprintf(file,'- posture caps: `%s` deg\n',mat2str(config.posture_caps_deg));
fprintf(file,'- backward progress: `%s`\n',mat2str(config.backward_progress));
fprintf(file,'- grid: %.2f deg coarse, %.2f deg refined, %.2f deg convergence\n', ...
    config.coarse_posture_step_deg,config.refined_posture_step_deg, ...
    config.convergence_posture_step_deg);
fprintf(file,'- recovery rates: `%s` deg/s (20 deg/s primary)\n', ...
    mat2str(config.recovery_rate_sensitivity_deg_s));
fprintf(file,'- force components: +/- %.0f N; residual tolerance inherited from R3C\n', ...
    config.force_bound_N);
fprintf(file,'\n## Anchors\n\n');
t=r4_anchor_table(anchors);
for k=1:height(t)
    fprintf(file,'- %s: t=%.3f s, s=%.9f, q=[%.3f, %.3f] deg, dq=[%.3f, %.3f] deg/s, bed=%.3f N\n', ...
        t.anchor_id(k),t.time_s(k),t.task_s(k),t.q1_deg(k),t.q2_deg(k), ...
        t.dq1_deg_s(k),t.dq2_deg_s(k),t.bed_force_N(k));
end
fprintf(file,'\n## Boundary classifications\n\n');
b=study.recovery_boundary_summary;
fprintf(file,'| anchor | model | support | family | criterion | cap deg | back | classification |\n');
fprintf(file,'|---|---|---|---|---|---:|---:|---|\n');
for k=1:height(b)
    fprintf(file,'| %s | %s | %s | %s | %s | %.3f | %.4f | %s |\n', ...
        b.anchor_id(k),b.model_kind(k),b.support_mode(k),b.family(k), ...
        b.criterion(k),b.posture_cap_deg(k),b.backward_progress(k), ...
        b.classification(k));
end
fprintf(file,'\nPoint feasibility and graph connectivity remain separate in the CSV evidence. Bad or disconnected results are retained.\n');
end
