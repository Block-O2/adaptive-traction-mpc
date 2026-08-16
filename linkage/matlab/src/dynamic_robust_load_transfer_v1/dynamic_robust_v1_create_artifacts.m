function dynamic_robust_v1_create_artifacts(result, output_dir)
%DYNAMIC_ROBUST_V1_CREATE_ARTIFACTS Synchronized GIF and required panels.

if ~isfolder(output_dir),mkdir(output_dir);end
t=result.t;q=result.state(1:2,:);bound=result.config.force_bound_N;
mode_index=mode_numbers(result.mode);
event_indices=find(result.event_name~="");

fig=figure('Visible','off','Color','w');stairs(t,mode_index,'LineWidth',1.5);
grid on;xlabel('time (s)');ylabel('hybrid state');yticks(1:9);
yticklabels(state_order());title('Hybrid state timeline');
save_png(fig,output_dir,'state_timeline.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,rad2deg(q(1,:)),'b','LineWidth',1.3);
plot(ax,t,rad2deg(result.q_nominal(1,:)),'k--');
plot(ax,t,rad2deg(result.q_ref(1,:)),'b:');ylabel(ax,'q1 (deg)');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,rad2deg(q(2,:)),'r','LineWidth',1.3);
plot(ax,t,rad2deg(result.q_nominal(2,:)),'k--');
plot(ax,t,rad2deg(result.q_ref(2,:)),'r:');ylabel(ax,'q2 (deg)');xlabel(ax,'time (s)');
title(layout,'Actual, nominal, and governed references');
save_png(fig,output_dir,'tracking_and_tube.png');

fig=figure('Visible','off','Color','w');hold on;grid on;
plot(t,result.robot_force_N(1,:),'b');plot(t,result.robot_force_N(2,:),'r');
plot(t,vecnorm(result.robot_force_N,2,1),'k','LineWidth',1.3);
yline(bound,'k--');yline(-bound,'k--');xlabel('time (s)');ylabel('force (N)');
legend('F parallel','F perp','norm','component bounds');
save_png(fig,output_dir,'robot_force_and_bounds.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,result.takeover_nominal_force_N(1,:),'b--');
plot(ax,t,result.takeover_nominal_force_N(2,:),'r--');
plot(ax,t,result.robot_force_N(1,:),'b');
plot(ax,t,result.robot_force_N(2,:),'r');
ylabel(ax,'force (N)');legend(ax,'nominal parallel','nominal perp', ...
    'applied parallel','applied perp');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,result.takeover_lambda,'k','LineWidth',1.2);
plot(ax,t,result.takeover_lambda_components(1,:),'b:');
plot(ax,t,result.takeover_lambda_components(2,:),'r:');
ylabel(ax,'takeover scale');legend(ax,'aggregate','parallel','perp');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,rad2deg(result.takeover_soft_margin_rad(1,:)),'b');
plot(ax,t,rad2deg(result.takeover_soft_margin_rad(2,:)),'r');
yline(ax,0,'k--');ylabel(ax,'soft margin (deg)');xlabel(ax,'time (s)');
title(layout,'R1 Safe Takeover diagnostics');
save_png(fig,output_dir,'safe_takeover_diagnostics.png');

fig=figure('Visible','off','Color','w');hold on;grid on;
plot(t,result.robust_static_margin_N,'LineWidth',1.3);
plot(t,result.dynamic_margin_N,'LineWidth',1.3);
plot(t,result.realized_dynamic_margin_N,':','LineWidth',1.2);
yline(20,'k--');yline(0,'r--');
xlabel('time (s)');ylabel('component margin (N)');
legend('registered robust static','nominal predicted dynamic', ...
    'offline realized-plant dynamic','20 N trigger','zero');
save_png(fig,output_dir,'static_vs_dynamic_margin.png');

fig=figure('Visible','off','Color','w');hold on;grid on;
plot(t,result.bed_force_N,'k','LineWidth',1.3);
plot(t,vecnorm(result.robot_force_N,2,1),'r','LineWidth',1.3);
plot(t,bound*result.bed_credit,'b--');xlabel('time (s)');ylabel('force / credit scale');
legend('real bed normal force','robot force norm','200 x bed credit');
save_png(fig,output_dir,'bed_robot_load_share.png');

fig=figure('Visible','off','Color','w');hold on;grid on;
plot(t,result.bed_force_N,'k','LineWidth',1.2);
plot(t,vecnorm(result.robot_force_N,2,1),'r','LineWidth',1.2);
for k=event_indices
    xline(t(k),':',char(result.event_name(k)),'LabelVerticalAlignment','middle');
end
xlabel('time (s)');ylabel('force (N)');title('Mechanically triggered transfer events');
save_png(fig,output_dir,'transfer_events.png');

fig=figure('Visible','off','Color','w');semilogy(t, ...
    max(result.dynamic_bounded_residual_Nm,eps),'LineWidth',1.3);hold on;
semilogy(t,max(result.realized_dynamic_bounded_residual_Nm,eps),':', ...
    'LineWidth',1.2);grid on;
xlabel('time (s)');ylabel('bounded dynamic residual (Nm)');
legend('nominal prediction','offline realized plant');
save_png(fig,output_dir,'dynamic_residual.png');

create_gif(result,fullfile(output_dir,'dynamic_robust_load_transfer.gif'));
end


function create_gif(r,path)
p=r.plant_parameters;c=r.config;h=r.h_hip_m;t=r.t;
fig=figure('Visible','off','Color','w','Position',[20 20 1500 840]);
layout=tiledlayout(fig,5,2,'TileSpacing','compact','Padding','compact');
ax=nexttile(layout,1,[5 1]);hold(ax,'on');axis(ax,'equal');grid(ax,'on');
reach=p.L1+p.L2;xlim(ax,[-.1 reach+.15]);ylim(ax,[-.08 h+reach+.12]);
plot(ax,[-.2 reach+.3],[0 0],'k-','LineWidth',5);plot(ax,0,h,'kp','MarkerFaceColor','k');
leg=plot(ax,nan,nan,'o-','LineWidth',5,'MarkerSize',8);
contacts=scatter(ax,nan,nan,55,'filled');
robotarrow=quiver(ax,nan,nan,nan,nan,0,'r','LineWidth',2);
info=text(ax,.02,.98,'','Units','normalized','VerticalAlignment','top','Interpreter','none');
qax=nexttile(layout,2);hold(qax,'on');grid(qax,'on');
plot(qax,t,rad2deg(r.q_nominal),'--');plot(qax,t,rad2deg(r.q_ref),':');
q1=plot(qax,nan,nan,'b','LineWidth',1.3);q2=plot(qax,nan,nan,'r','LineWidth',1.3);ylabel(qax,'q (deg)');
fax=nexttile(layout,4);hold(fax,'on');grid(fax,'on');
f1=plot(fax,nan,nan,'b');f2=plot(fax,nan,nan,'r');yline(fax,c.force_bound_N,'k--');yline(fax,-c.force_bound_N,'k--');ylabel(fax,'robot N');
bax=nexttile(layout,6);hold(bax,'on');grid(bax,'on');bf=plot(bax,nan,nan,'k');ylabel(bax,'bed N');
maxis=nexttile(layout,8);hold(maxis,'on');grid(maxis,'on');
rm=plot(maxis,nan,nan,'b');dm=plot(maxis,nan,nan,'r');yline(maxis,20,'k--');yline(maxis,0,'k:');ylabel(maxis,'margin N');
pax=nexttile(layout,10);hold(pax,'on');grid(pax,'on');
pg=plot(pax,nan,nan,'b');md=stairs(pax,nan,nan,'r');ylabel(pax,'s / state');xlabel(pax,'time (s)');
for panel=[qax fax bax maxis pax],xlim(panel,[0 max(t(end),eps)]);end
frames=unique(round(linspace(1,numel(t),min(240,numel(t)))));
mode_index=mode_numbers(r.mode);
for frame_index=1:numel(frames)
    k=frames(frame_index);q=r.state(1:2,k);phi=q(1)-q(2);hip=[0;h];
    knee=hip+p.L1*[cos(q(1));sin(q(1))];ankle=knee+p.L2*[cos(phi);sin(phi)];
    set(leg,'XData',[hip(1) knee(1) ankle(1)],'YData',[hip(2) knee(2) ankle(2)]);
    bed=bed_supported_v1_contact(q,r.state(3:4,k),h,p,c);active=bed.active;
    set(contacts,'XData',bed.points.position_world(1,active), ...
        'YData',bed.points.position_world(2,active),'CData',bed.normal_force_N(active)');
    map=single_arm_v2_force_map(q,r.state(3:4,k),p);
    world_force=map.rotation*r.robot_force_N(:,k)/800;point=hip+map.contact.position;
    set(robotarrow,'XData',point(1),'YData',point(2), ...
        'UData',world_force(1),'VData',world_force(2));
    set(info,'String',sprintf(['%s  t=%.2f s  s=%.3f\n' ...
        'robot=[%.1f %.1f] N  bed=%.1f N\nrobust=%.1f N  dynamic=%.1f N'], ...
        r.mode(k),t(k),r.task_s(k),r.robot_force_N(1,k), ...
        r.robot_force_N(2,k),r.bed_force_N(k), ...
        r.robust_static_margin_N(k),r.dynamic_margin_N(k)));
    set(q1,'XData',t(1:k),'YData',rad2deg(r.state(1,1:k)));
    set(q2,'XData',t(1:k),'YData',rad2deg(r.state(2,1:k)));
    set(f1,'XData',t(1:k),'YData',r.robot_force_N(1,1:k));
    set(f2,'XData',t(1:k),'YData',r.robot_force_N(2,1:k));
    set(bf,'XData',t(1:k),'YData',r.bed_force_N(1:k));
    set(rm,'XData',t(1:k),'YData',r.robust_static_margin_N(1:k));
    set(dm,'XData',t(1:k),'YData',r.dynamic_margin_N(1:k));
    set(pg,'XData',t(1:k),'YData',r.task_s(1:k));
    set(md,'XData',t(1:k),'YData',mode_index(1:k)/9);
    frame=getframe(fig);image=frame2im(frame);[indexed,mapc]=rgb2ind(image,256);
    if frame_index==1
        imwrite(indexed,mapc,path,'gif','LoopCount',Inf,'DelayTime',.08);
    else
        imwrite(indexed,mapc,path,'gif','WriteMode','append','DelayTime',.08);
    end
end
close(fig);
end


function numbers=mode_numbers(mode)
order=state_order();numbers=zeros(size(mode));
for k=1:numel(order),numbers(mode==order(k))=k;end
end


function order=state_order()
order=["BED_SUPPORTED_MOTION","TRANSFER_READY","LOAD_TAKEOVER", ...
    "LIFTOFF","SUSPENDED_MOTION","RECONTACT","LOAD_RETURN", ...
    "BED_SUPPORTED_RETURN","TASK_COMPLETE"];
end


function save_png(fig,output_dir,name)
exportgraphics(fig,fullfile(output_dir,name),'Resolution',180);close(fig);
end
