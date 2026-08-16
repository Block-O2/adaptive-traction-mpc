function dynamic_robust_v1_adaptive_create_artifacts(result,output_dir)
%DYNAMIC_ROBUST_V1_ADAPTIVE_CREATE_ARTIFACTS R2B identifier diagnostics.

if ~result.adaptive_enabled,return;end
t=result.t;a=result.adaptive_config;
truth=result.metrics.identifier.true_theta;
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,4,2);
for parameter_index=1:7
    ax=nexttile(layout);hold(ax,'on');
    plot(ax,t,result.identifier_theta_model(parameter_index,:), ...
        'b','LineWidth',1.2);
    attempted=result.identifier_update_attempted;
    plot(ax,t(attempted),result.identifier_theta_raw( ...
        parameter_index,attempted),'r.');
    yline(ax,a.theta_nominal(parameter_index),'k--');
    yline(ax,truth(parameter_index),'g-.');grid(ax,'on');
    ylabel(ax,a.parameter_names(parameter_index));
end
legend(ax,{'accepted model','raw NLS','nominal','true'},'Location','best');
blank=nexttile(layout,8);axis(blank,'off');
xlabel(layout,'time (s)');title(layout,'R2B parameter trajectories');
exportgraphics(fig,fullfile(output_dir,'adaptive_parameter_trajectory.png'), ...
    'Resolution',180);close(fig);

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
ax=nexttile(layout);semilogy(ax,t,result.identifier_current_fit_rms,'k');
hold(ax,'on');semilogy(ax,t,result.identifier_fit_rms,'b');grid(ax,'on');
ylabel(ax,'fit RMS');legend(ax,'current','raw NLS');
ax=nexttile(layout);yyaxis(ax,'left');stairs(ax,t,result.identifier_rank,'b');
ylabel(ax,'rank');yyaxis(ax,'right');semilogy(ax,t, ...
    result.identifier_condition_number,'r');ylabel(ax,'condition');grid(ax,'on');
ax=nexttile(layout);stairs(ax,t,result.identifier_accepted_count,'g');
hold(ax,'on');stairs(ax,t,result.identifier_rejected_count,'r');
stairs(ax,t,result.identifier_solver_failures,'k');grid(ax,'on');
ylabel(ax,'count');xlabel(ax,'time (s)');
legend(ax,'accepted','rejected','solver failures','Location','best');
title(layout,'R2B Windowed-NLS diagnostics');
exportgraphics(fig,fullfile(output_dir,'adaptive_identifier_diagnostics.png'), ...
    'Resolution',180);close(fig);
end
