function r3a_create_figures(identifier,r1,r2a,r2b,moderate_replay, ...
        mild_rows,output_dir)
%R3A_CREATE_FIGURES Required headless R3A diagnostics.

create_rank_figure(identifier,output_dir);
create_singular_figure(identifier,output_dir);
create_correlation_figure(identifier,output_dir);
create_subspace_figure(identifier,output_dir);
create_moderate_comparison(r1.results{3},r2b.results{3}, ...
    r2a.results{3},output_dir);
create_moderate_decomposition(r2b.results{3},r2a.results{3}, ...
    moderate_replay,output_dir);
create_mild_recontact(mild_rows,output_dir);
create_mild_comparison(mild_rows,output_dir);
create_taxonomy(output_dir);
end


function create_rank_figure(identifier,output_dir)
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,2);
for index=1:4
    item=identifier.case_info(index);ax=nexttile(layout);hold(ax,'on');
    stairs(ax,item.times,item.ranks,'k-','LineWidth',1.2);
    scatter(ax,item.times(item.accepted),item.ranks(item.accepted),36, ...
        [0 .55 0],'filled');
    scatter(ax,item.times(~item.accepted),item.ranks(~item.accepted),42, ...
        [0.8 0 0],'x','LineWidth',1.2);
    yline(ax,7,'b--');ylim(ax,[0 7.5]);grid(ax,'on');
    title(ax,item.name);xlabel(ax,'time (s)');ylabel(ax,'effective rank');
end
legend(ax,{'rank','accepted','rejected','full-rank gate'}, ...
    'Orientation','horizontal');title(layout,'R2B identifier rank over time');
exportgraphics(fig,fullfile(output_dir,'identifier_rank_over_time.png'), ...
    'Resolution',180);close(fig);
end


function create_singular_figure(identifier,output_dir)
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,2);
for index=1:4
    item=identifier.case_info(index);ax=nexttile(layout);hold(ax,'on');
    stacked=item.stacked_singular_values;
    final=item.final_singular_values;
    semilogy(ax,1:7,max(stacked/stacked(1),realmin),'o-','LineWidth',1.2);
    semilogy(ax,1:7,max(final/final(1),realmin),'s--','LineWidth',1.2);
    set(ax,'YScale','log');ylim(ax,[1e-20 1.1]);
    grid(ax,'on');xticks(ax,1:7);title(ax,item.name);
    xlabel(ax,'singular direction');ylabel(ax,'sigma / sigma_1');
end
legend(ax,{'stacked attempt windows','final window'}, ...
    'Orientation','horizontal');title(layout,'Normalized sensitivity spectra');
exportgraphics(fig,fullfile(output_dir,'identifier_singular_values.png'), ...
    'Resolution',180);close(fig);
end


function create_correlation_figure(identifier,output_dir)
indices=[2 3 4];fig=figure('Visible','off','Color','w');
layout=tiledlayout(fig,1,3);
for tile=1:3
    index=indices(tile);ax=nexttile(layout);
    if index==4,matrix=identifier.case_info(index).final_correlation;
        scope='final window';
    else,matrix=identifier.case_info(index).stacked_correlation;
        scope='stacked windows';
    end
    imagesc(ax,matrix,[-1 1]);axis(ax,'square');colormap(ax,parula);
    xticks(ax,1:7);yticks(ax,1:7);xticklabels(ax,identifier.parameter_names);
    yticklabels(ax,identifier.parameter_names);xtickangle(ax,45);
    set(ax,'TickLabelInterpreter','none');
    title(ax,sprintf('%s (%s)',identifier.case_info(index).name,scope));
end
colorbar(nexttile(layout,3));title(layout,'Normalized sensitivity-column correlation');
exportgraphics(fig,fullfile(output_dir,'parameter_correlation_matrix.png'), ...
    'Resolution',180);close(fig);
end


function create_subspace_figure(identifier,output_dir)
item=identifier.case_info(4);fig=figure('Visible','off','Color','w');
layout=tiledlayout(fig,1,2);
ax=nexttile(layout);imagesc(ax,item.final_V,[-1 1]);
xticks(ax,1:7);yticks(ax,1:7);yticklabels(ax,identifier.parameter_names);
set(ax,'TickLabelInterpreter','none');
xlabel(ax,'right singular direction');title(ax,'Adverse final-window V');
colormap(ax,parula);colorbar(ax);
ax=nexttile(layout);values=item.final_singular_values;
bar(ax,1:7,values/values(1));set(ax,'YScale','log');grid(ax,'on');
hold(ax,'on');xline(ax,4.5,'r--','rank 4 / weak-null side');
xlabel(ax,'right singular direction');ylabel(ax,'sigma / sigma_1');
title(ax,'Adverse final-window excitation');
title(layout,'Identifiable and weak parameter combinations');
exportgraphics(fig,fullfile(output_dir,'identifiable_subspace.png'), ...
    'Resolution',180);close(fig);
end


function create_moderate_comparison(nominal,adaptive,oracle,output_dir)
items={nominal,adaptive,oracle};labels={'nominal model','adaptive','oracle'};
colors={[.2 .2 .2],[0 .35 .8],[0 .6 0]};
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
for panel=1:3
    ax=nexttile(layout);hold(ax,'on');
    for item_index=1:3
        aligned=r3a_tracking_alignment(items{item_index});
        switch panel
            case 1,value=aligned.q2_soft_clearance_deg;label='q2 soft clearance (deg)';
            case 2,value=aligned.progress;label='task progress';
            otherwise,value=aligned.force_norm_N;label='robot force norm (N)';
        end
        plot(ax,aligned.time_s,value,'Color',colors{item_index}, ...
            'LineWidth',1.2);
    end
    if panel==1,yline(ax,0,'r--');end
    if panel==3,yline(ax,200,'k--');end
    if panel==1
        accepted=find(adaptive.identifier_update_accepted);
        entry=find(adaptive.takeover_mode=="TRACKING",1,'first');
        for index=accepted
            xline(ax,adaptive.t(index)-adaptive.t(entry),'b:');
        end
    end
    ylabel(ax,label);grid(ax,'on');
end
xlabel(nexttile(layout,3),'time after TRACKING entry (s)');
legend(nexttile(layout,1),labels,'Orientation','horizontal');
title(layout,'Moderate nominal/adaptive/oracle phase-aligned comparison');
exportgraphics(fig,fullfile(output_dir, ...
    'moderate_nominal_adaptive_oracle.png'),'Resolution',180);close(fig);
end


function create_moderate_decomposition(adaptive,oracle,replay,output_dir)
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
ax=nexttile(layout);plot(ax,replay.tracking_time_s,replay.parameter_error, ...
    'b','LineWidth',1.2);grid(ax,'on');ylabel(ax,'normalized theta error');
accepted=find(adaptive.identifier_update_accepted);
entry=find(adaptive.takeover_mode=="TRACKING",1,'first');hold(ax,'on');
for index=accepted,xline(ax,adaptive.t(index)-adaptive.t(entry),'b:');end
ax=nexttile(layout);hold(ax,'on');
plot(ax,replay.tracking_time_s,replay.nominal_margin_N,'k');
plot(ax,replay.tracking_time_s,replay.adaptive_margin_N,'b');
plot(ax,replay.tracking_time_s,replay.oracle_margin_N,'g');
yline(ax,0,'r--');grid(ax,'on');ylabel(ax,'same-state margin (N)');
legend(ax,{'nominal model','accepted model','true model','zero'});
ax=nexttile(layout);a=r3a_tracking_alignment(adaptive);
o=r3a_tracking_alignment(oracle);hold(ax,'on');
plot(ax,a.time_s,a.q2_soft_clearance_deg,'b','LineWidth',1.2);
plot(ax,o.time_s,o.q2_soft_clearance_deg,'g','LineWidth',1.2);
yline(ax,0,'r--');grid(ax,'on');ylabel(ax,'q2 clearance (deg)');
xlabel(ax,'time after TRACKING entry (s)');legend(ax,{'adaptive','oracle'});
title(layout,['Moderate decomposition: estimation gap versus ' ...
    'oracle-level boundary']);
exportgraphics(fig,fullfile(output_dir, ...
    'moderate_failure_decomposition.png'),'Resolution',180);close(fig);
end


function create_mild_recontact(rows,output_dir)
rows=rows(rows.source=="adaptive",:);
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,4,1);
ax=nexttile(layout);plot(ax,rows.relative_time_s,1e3*rows.min_gap_m,'k');
yline(ax,0,'r--');ylabel(ax,'min gap (mm)');grid(ax,'on');
ax=nexttile(layout);plot(ax,rows.relative_time_s,rows.total_bed_force_N,'b');
yline(ax,2,'r--');ylabel(ax,'bed force (N)');grid(ax,'on');
ax=nexttile(layout);stairs(ax,rows.relative_time_s,rows.active_contact_count,'k');
hold(ax,'on');stairs(ax,rows.relative_time_s,rows.force_threshold_contact,'r');
ylabel(ax,'contact state');grid(ax,'on');legend(ax,{'penetration count','force >= 2 N'});
ax=nexttile(layout);plot(ax,rows.relative_time_s,rows.q1_deg,'b');hold(ax,'on');
plot(ax,rows.relative_time_s,rows.q2_deg,'r');
plot(ax,rows.relative_time_s,rows.q1_ref_deg,'b--');
plot(ax,rows.relative_time_s,rows.q2_ref_deg,'r--');
ylabel(ax,'joint angle (deg)');xlabel(ax,'time in RECONTACT (s)');grid(ax,'on');
title(layout,'Mild adaptive recontact diagnostics');
exportgraphics(fig,fullfile(output_dir,'mild_recontact_diagnostics.png'), ...
    'Resolution',180);close(fig);
end


function create_mild_comparison(rows,output_dir)
adaptive=rows(rows.source=="adaptive",:);oracle=rows(rows.source=="oracle",:);
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,4,1);
variables={'min_gap_m','total_bed_force_N','robot_force_norm_N','q2_deg'};
labels={'min gap (m)','bed force (N)','robot force norm (N)','q2 (deg)'};
for panel=1:4
    ax=nexttile(layout);hold(ax,'on');
    plot(ax,adaptive.relative_time_s,adaptive.(variables{panel}),'b');
    plot(ax,oracle.relative_time_s,oracle.(variables{panel}),'g');
    if panel==1,yline(ax,0,'r--');end
    if panel==2,yline(ax,2,'r--');end
    ylabel(ax,labels{panel});grid(ax,'on');
end
xlabel(nexttile(layout,4),'time in RECONTACT (s)');
legend(nexttile(layout,1),{'adaptive','oracle'},'Orientation','horizontal');
title(layout,'Mild adaptive versus oracle recontact');
exportgraphics(fig,fullfile(output_dir, ...
    'mild_adaptive_vs_oracle_recontact.png'),'Resolution',180);close(fig);
end


function create_taxonomy(output_dir)
fig=figure('Visible','off','Color','w','Position',[100 100 1500 520]);
ax=axes(fig);axis(ax,[0 5 0 4]);axis(ax,'off');
headers=["case","estimator evidence","remaining estimator gap", ...
    "oracle/constraint limit","contact-policy limit"];
for column=1:5,text(ax,column-.5,3.55,headers(column), ...
        'HorizontalAlignment','center','FontWeight','bold');end
rows=["mild","strong improvement","small residual","oracle completes", ...
    "stable recontact fails"; ...
    "moderate","partial improvement","material at failure", ...
    "oracle also hits q2","not observed"; ...
    "adverse","no accepted update","rank/excitation limited", ...
    "oracle still hits q2","not reached"];
colors={[.8 1 .8],[1 .95 .7],[.85 .9 1]};
for row=1:3
    y=3-row;
    rectangle(ax,'Position',[0 y 5 1],'FaceColor',colors{row}, ...
        'EdgeColor',[.7 .7 .7]);
    for column=1:5,text(ax,column-.5,y+.5,rows(row,column), ...
            'HorizontalAlignment','center');end
end
title(ax,'R3A failure taxonomy: different failures require different mechanisms');
exportgraphics(fig,fullfile(output_dir,'r3a_failure_taxonomy.png'), ...
    'Resolution',180);close(fig);
end
