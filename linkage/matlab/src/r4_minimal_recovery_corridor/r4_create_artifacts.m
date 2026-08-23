function r4_create_artifacts(output_dir,anchors,study)
%R4_CREATE_ARTIFACTS Create the nine approved static PNG diagnostics.

anchor_table=r4_anchor_table(anchors);b=study.recovery_boundary_summary;
save_plot(@()anchor_map(anchor_table),output_dir,'anchor_state_map.png');
save_plot(@()tube_geometry(anchors),output_dir,'expanded_tube_geometry.png');
save_plot(@()family_boundary(b,"A_POSTURE_ONLY"),output_dir, ...
    'posture_relaxation_boundary.png');
save_plot(@()family_boundary(b,"B_BACKWARD_ONLY"),output_dir, ...
    'progress_reversal_boundary.png');
save_plot(@()combined_pareto(b),output_dir,'combined_recovery_pareto.png');
save_plot(@()corridor_paths(study.recovery_paths),output_dir, ...
    'connected_recovery_corridor.png');
save_plot(@()model_comparison(b),output_dir,'true_vs_perceived_feasibility.png');
save_plot(@()support_comparison(b),output_dir,'bed_assisted_vs_robot_only.png');
save_plot(@()timing_comparison(b),output_dir,'intervention_vs_stop_thresholds.png');
end

function save_plot(draw,output_dir,name)
fig=figure('Visible','off','Color','w','Position',[100,100,900,600]);
cleanup=onCleanup(@()close(fig)); %#ok<NASGU>
draw();grid on;box on;exportgraphics(fig,fullfile(output_dir,name),'Resolution',160);
end
function anchor_map(t)
names=unique(t.case_name,'stable');colors=lines(numel(names));hold on;
for k=1:numel(names)
    mask=t.case_name==names(k);
    scatter(t.q1_deg(mask),t.q2_deg(mask),55,colors(k,:),'filled', ...
        'DisplayName',names(k));
end
xlabel('q_1 (deg)');ylabel('q_2 (deg)');title('Frozen R3C anchor states');
for k=1:height(t)
    text(t.q1_deg(k),t.q2_deg(k)," "+t.role(k),'FontSize',7, ...
        'Interpreter','none');
end
xlim([min(t.q1_deg)-0.3,max(t.q1_deg)+1.2]);
ylim([min(t.q2_deg)-0.3,max(t.q2_deg)+0.5]);
legend('Location','best','Interpreter','none');
end
function tube_geometry(anchors)
a=anchors(find([anchors.case_name]=="moderate_oracle" & ...
    [anchors.role]=="terminal_stop",1));s=a.task_s;path=hybrid_tube_v1_task_path(s);
caps=[10,20,30];colors=lines(numel(caps));hold on;
for k=1:numel(caps)
    c=a.config;c.tube_cap_deg=caps(k);tube=hybrid_tube_v1_tube_schedule(s,path.q,c);
    rectangle('Position',[rad2deg(path.q(1)-tube(1)), ...
        rad2deg(path.q(2)-tube(2)),2*rad2deg(tube(1)),2*rad2deg(tube(2))], ...
        'EdgeColor',colors(k,:),'LineWidth',1.5);
end
plot(rad2deg(a.q_rad(1)),rad2deg(a.q_rad(2)),'kx','LineWidth',2);
xlabel('q_1 (deg)');ylabel('q_2 (deg)');title('Frozen path center with expanded tube geometry');
text(rad2deg(path.q(1)),rad2deg(path.q(2)), ...
    '  nested caps: 10 / 20 / 30 deg','FontSize',8);
end
function family_boundary(b,family)
rows=b(b.family==family & b.support_mode=="bed_assisted",:);hold on;
if isempty(rows),text(.5,.5,'No rows','HorizontalAlignment','center');return;end
y=rows.posture_cap_deg;if family=="B_BACKWARD_ONLY",y=rows.backward_progress;end
scatter(1:height(rows),y,45,double(rows.connected)+1,'filled');
xticks(1:height(rows));xticklabels(rows.anchor_id+"/"+rows.model_kind);xtickangle(35);
ylabel(strrep(char(family),'_',' '));title(strrep(char(family),'_',' '));
end
function combined_pareto(b)
rows=b(b.family=="C_COMBINED" & b.support_mode=="bed_assisted" & ...
    b.connected,:);hold on;
if isempty(rows),text(.5,.5,'No connected Pareto points');return;end
scatter(rows.posture_cap_deg,rows.backward_progress,60, ...
    double(rows.connected)+1,'filled');xlabel('Posture cap (deg)');
ylabel('Backward progress');title('Combined recovery Pareto selections');
end
function corridor_paths(t)
hold on;if isempty(t),text(.5,.5,'No connected corridor');axis([0,1,0,1]);return;end
groups=findgroups(t.anchor_id+"/"+t.model_kind+"/"+t.support_mode);
for g=unique(groups)',r=t(groups==g,:);plot(r.q1_deg,r.q2_deg,'-o');end
xlabel('q_1 (deg)');ylabel('q_2 (deg)');title('Selected connected recovery corridors');
end
function model_comparison(b)
rows=b(b.support_mode=="bed_assisted" & b.criterion=="minimum_posture",:);
bar(categorical(rows.anchor_id+"/"+rows.model_kind),rows.posture_cap_deg);
ylabel('Minimum tested posture cap (deg)');title('True versus perceived feasibility');xtickangle(35);
end
function support_comparison(b)
rows=b(b.criterion=="minimum_posture",:);
labels=rows.anchor_id+"/"+rows.model_kind+"/"+rows.support_mode;
bar(categorical(labels,labels,'Ordinal',true),rows.posture_cap_deg);
ylabel('Minimum tested posture cap (deg)');title('Bed-assisted versus robot-only');xtickangle(35);
end
function timing_comparison(b)
rows=b(b.criterion=="minimum_posture" & b.model_kind=="true" & ...
    b.support_mode=="bed_assisted",:);
bar(categorical(rows.anchor_id),rows.posture_cap_deg);
ylabel('Minimum tested posture cap (deg)');title('First intervention versus terminal stop');xtickangle(35);
end
