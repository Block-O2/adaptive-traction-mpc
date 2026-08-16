function r3c_create_comparison_figures(oracle,adaptive,repo_root,output_dir)
%R3C_CREATE_COMPARISON_FIGURES Frozen R2B versus R3C formal evidence.

old=load_frozen_r2b(repo_root);
old_moderate=old.results{3};old_adverse=old.results{4};
oracle_moderate=oracle{2};oracle_adverse=oracle{3};
adaptive_moderate=adaptive{3};adaptive_adverse=adaptive{4};

fig=figure('Visible','off','Color','w');hold on;grid on;
plot_clearance(old_moderate,'old R2B moderate');
plot_clearance(oracle_moderate,'R3C oracle moderate');
plot_clearance(adaptive_moderate,'R3C adaptive moderate');
yline(0,'k--','HandleVisibility','off');xlabel('time (s)');
ylabel('q2 lower-soft clearance (deg)');
legend('Location','best');save_png(fig,output_dir,'q2_clearance_comparison.png');

fig=comparison_layout(old_moderate,oracle_moderate,adaptive_moderate, ...
    'Moderate: frozen R2B versus R3C');
save_png(fig,output_dir,'moderate_old_vs_r3c.png');

fig=comparison_layout(old_adverse,[],adaptive_adverse, ...
    'Adverse: frozen R2B versus R3C adaptive');
save_png(fig,output_dir,'adverse_old_vs_r3c.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,2);
plot_pair(nexttile(layout),oracle_moderate,adaptive_moderate,'moderate');
plot_pair(nexttile(layout),oracle_adverse,adaptive_adverse,'adverse');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,oracle_moderate.t,oracle_moderate.task_s,'k');
plot(ax,adaptive_moderate.t,adaptive_moderate.task_s,'b');
ylabel(ax,'moderate progress');xlabel(ax,'time (s)');legend(ax,'oracle','adaptive');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,oracle_adverse.t,oracle_adverse.task_s,'k');
plot(ax,adaptive_adverse.t,adaptive_adverse.task_s,'b');
ylabel(ax,'adverse progress');xlabel(ax,'time (s)');legend(ax,'oracle','adaptive');
title(layout,'Oracle versus adaptive safety behavior');
save_png(fig,output_dir,'oracle_vs_adaptive_safety.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,adaptive_moderate.t,adaptive_moderate.robot_force_N);
yline(ax,adaptive_moderate.config.force_bound_N,'k--');
yline(ax,-adaptive_moderate.config.force_bound_N,'k--');ylabel(ax,'force (N)');
ax=nexttile(layout);semilogy(ax,adaptive_moderate.t, ...
    max(adaptive_moderate.dynamic_bounded_residual_Nm,eps));grid(ax,'on');
ylabel(ax,'bounded residual (Nm)');xlabel(ax,'time (s)');
title(layout,'R3C adaptive moderate force and residual');
save_png(fig,output_dir,'force_and_residual.png');
end


function source=load_frozen_r2b(repo_root)
root=fullfile(repo_root,'linkage','results','local', ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking_r2b');
entries=dir(root);entries=entries([entries.isdir]);
names={entries.name};keep=~ismember(names,{'.','..'});entries=entries(keep);
names=string({entries.name});[~,order]=sort(names,'descend');
for index=order
    path=fullfile(entries(index).folder,entries(index).name, ...
        'formal_adaptive_results.mat');
    if isfile(path),source=load(path,'results');return;end
end
error('R3C:FrozenR2BMissing','Frozen R2B formal result was not found.');
end


function fig=comparison_layout(old,oracle,adaptive,title_text)
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,old.t,old.task_s,'Color',[.5 .5 .5],'DisplayName','old R2B');
if ~isempty(oracle),plot(ax,oracle.t,oracle.task_s,'k','DisplayName','R3C oracle');end
plot(ax,adaptive.t,adaptive.task_s,'b','DisplayName','R3C adaptive');
ylabel(ax,'task progress');legend(ax,'Location','best');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot_clearance_on(ax,old,'old R2B');
if ~isempty(oracle),plot_clearance_on(ax,oracle,'R3C oracle');end
plot_clearance_on(ax,adaptive,'R3C adaptive');
yline(ax,0,'k--','HandleVisibility','off');
ylabel(ax,'q2 clearance (deg)');xlabel(ax,'time (s)');legend(ax,'Location','best');
title(layout,title_text);
end


function plot_pair(ax,oracle,adaptive,label)
hold(ax,'on');grid(ax,'on');
plot(ax,oracle.t,oracle.safety_alpha,'k','DisplayName','oracle');
plot(ax,adaptive.t,adaptive.safety_alpha,'b','DisplayName','adaptive');
ylim(ax,[-.05 1.05]);ylabel(ax,string(label)+" alpha");xlabel(ax,'time (s)');
legend(ax,'Location','best');
end


function plot_clearance(result,label)
plot(result.t,q2_clearance(result),'DisplayName',label,'LineWidth',1.2);
end


function plot_clearance_on(ax,result,label)
plot(ax,result.t,q2_clearance(result),'DisplayName',label,'LineWidth',1.2);
end


function values=q2_clearance(result)
lower=result.plant_parameters.q_min+result.plant_parameters.soft_limit_margin;
values=rad2deg(result.state(2,:)-lower(2));
end


function save_png(fig,output_dir,name)
exportgraphics(fig,fullfile(output_dir,name),'Resolution',180);close(fig);
end
