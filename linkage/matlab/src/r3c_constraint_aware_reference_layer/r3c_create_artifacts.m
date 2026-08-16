function r3c_create_artifacts(result,output_dir,make_gif)
%R3C_CREATE_ARTIFACTS Safety-specific figures and synchronized trajectory GIF.

if nargin<3,make_gif=true;end
if ~isfolder(output_dir),mkdir(output_dir);end
t=result.t;q=result.state(1:2,:);c=result.config;p=result.plant_parameters;
lower=p.q_min+p.soft_limit_margin;upper=p.q_max-p.soft_limit_margin;

fig=figure('Visible','off','Color','w');stairs(t,state_numbers( ...
    result.safety_state),'LineWidth',1.5);grid on;yticks(1:4);
yticklabels(state_order());xlabel('time (s)');ylabel('R3C state');
title('Constraint-aware safety state timeline');
save_png(fig,output_dir,'safety_state_timeline.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,rad2deg(q(2,:)-lower(2)),'k','LineWidth',1.3);
plot(ax,t,rad2deg(result.safety_predicted_q2_clearance_rad),'r:');
yline(ax,rad2deg(c.r3c_warning_buffer_rad),'b--','warning');
yline(ax,rad2deg(c.r3c_hold_buffer_rad),'m--','hold');yline(ax,0,'k--');
ylabel(ax,'q2 lower-soft clearance (deg)');
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,rad2deg(q(1,:)-lower(1)),'b');
plot(ax,t,rad2deg(upper(1)-q(1,:)),'r');yline(ax,0,'k--');
ylabel(ax,'q1 clearance (deg)');xlabel(ax,'time (s)');
title(layout,'Measured and predicted soft-zone clearance');
save_png(fig,output_dir,'q2_soft_clearance.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);plot(ax,t,result.task_s,'k','LineWidth',1.3);grid(ax,'on');
ylabel(ax,'task progress');
ax=nexttile(layout);plot(ax,t,result.safety_alpha,'b','LineWidth',1.3);grid(ax,'on');
ylim(ax,[-.05 1.05]);ylabel(ax,'action scale alpha');xlabel(ax,'time (s)');
title(layout,'Progress and predictive action scaling');
save_png(fig,output_dir,'progress_and_action_scaling.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
plot(ax,t,result.robot_force_N);yline(ax,c.force_bound_N,'k--');
yline(ax,-c.force_bound_N,'k--');ylabel(ax,'robot force (N)');
ax=nexttile(layout);semilogy(ax,t,max(result.dynamic_bounded_residual_Nm,eps));
grid(ax,'on');ylabel(ax,'bounded residual (Nm)');xlabel(ax,'time (s)');
title(layout,'Force bounds and dynamic residual');
save_png(fig,output_dir,'force_and_residual.png');

if make_gif
    create_safety_gif(result,fullfile(output_dir,'r3c_safety_trajectory.gif'));
end
end


function create_safety_gif(r,path)
p=r.plant_parameters;c=r.config;h=r.h_hip_m;t=r.t;
lower=p.q_min+p.soft_limit_margin;
fig=figure('Visible','off','Color','w','Position',[20 20 1500 840]);
layout=tiledlayout(fig,5,2,'TileSpacing','compact','Padding','compact');
ax=nexttile(layout,1,[5 1]);hold(ax,'on');axis(ax,'equal');grid(ax,'on');
reach=p.L1+p.L2;xlim(ax,[-.1 reach+.15]);ylim(ax,[-.08 h+reach+.12]);
plot(ax,[-.2 reach+.3],[0 0],'k-','LineWidth',5);plot(ax,0,h,'kp','MarkerFaceColor','k');
leg=plot(ax,nan,nan,'o-','LineWidth',5,'MarkerSize',8);
contacts=scatter(ax,nan,nan,55,'filled');
robotarrow=quiver(ax,nan,nan,nan,nan,0,'r','LineWidth',2);
info=text(ax,.02,.98,'','Units','normalized','VerticalAlignment','top', ...
    'Interpreter','none');
qax=nexttile(layout,2);hold(qax,'on');grid(qax,'on');
plot(qax,t,rad2deg(r.q_nominal),'k--');plot(qax,t,rad2deg(r.q_ref),':');
q1=plot(qax,nan,nan,'b','LineWidth',1.3);q2=plot(qax,nan,nan,'r','LineWidth',1.3);
ylabel(qax,'q / references (deg)');
cax=nexttile(layout,4);hold(cax,'on');grid(cax,'on');
clearance=rad2deg(r.state(2,:)-lower(2));
plot(cax,t,rad2deg(r.safety_predicted_q2_clearance_rad),'r:');
yline(cax,rad2deg(c.r3c_warning_buffer_rad),'b--');yline(cax,0,'k--');
cl=plot(cax,nan,nan,'k','LineWidth',1.3);ylabel(cax,'q2 clearance (deg)');
aax=nexttile(layout,6);hold(aax,'on');grid(aax,'on');
al=plot(aax,nan,nan,'b','LineWidth',1.2);st=stairs(aax,nan,nan,'r');
ylim(aax,[0 1.1]);ylabel(aax,'alpha / safety state');
fax=nexttile(layout,8);hold(fax,'on');grid(fax,'on');
f1=plot(fax,nan,nan,'b');f2=plot(fax,nan,nan,'r');
yline(fax,c.force_bound_N,'k--');yline(fax,-c.force_bound_N,'k--');
ylabel(fax,'robot force (N)');
pax=nexttile(layout,10);hold(pax,'on');grid(pax,'on');
pg=plot(pax,nan,nan,'k','LineWidth',1.2);
accepted=find(r.identifier_update_accepted);
if ~isempty(accepted),scatter(pax,t(accepted),r.task_s(accepted),18,'g','filled');end
ylabel(pax,'progress / accepted ID');xlabel(pax,'time (s)');
for panel=[qax cax aax fax pax],xlim(panel,[0 max(t(end),eps)]);end
frames=unique(round(linspace(1,numel(t),min(180,numel(t)))));
numbers=state_numbers(r.safety_state);
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
    set(info,'String',sprintf(['%s / %s  t=%.2f s  s=%.3f\n' ...
        'q2 clearance=%.2f deg  alpha=%.3f\nrobot=[%.1f %.1f] N'], ...
        r.mode(k),r.safety_state(k),t(k),r.task_s(k),clearance(k), ...
        r.safety_alpha(k),r.robot_force_N(1,k),r.robot_force_N(2,k)));
    set(q1,'XData',t(1:k),'YData',rad2deg(r.state(1,1:k)));
    set(q2,'XData',t(1:k),'YData',rad2deg(r.state(2,1:k)));
    set(cl,'XData',t(1:k),'YData',clearance(1:k));
    set(al,'XData',t(1:k),'YData',r.safety_alpha(1:k));
    set(st,'XData',t(1:k),'YData',numbers(1:k)/4);
    set(f1,'XData',t(1:k),'YData',r.robot_force_N(1,1:k));
    set(f2,'XData',t(1:k),'YData',r.robot_force_N(2,1:k));
    set(pg,'XData',t(1:k),'YData',r.task_s(1:k));
    frame=getframe(fig);image=frame2im(frame);[indexed,mapc]=rgb2ind(image,256);
    if frame_index==1
        imwrite(indexed,mapc,path,'gif','LoopCount',Inf,'DelayTime',.08);
    else
        imwrite(indexed,mapc,path,'gif','WriteMode','append','DelayTime',.08);
    end
end
close(fig);
end


function numbers=state_numbers(values)
order=state_order();numbers=zeros(size(values));
for index=1:numel(order),numbers(values==order(index))=index;end
end


function order=state_order()
order=["NORMAL","SLOWDOWN","HOLD","RECOVERY_REFERENCE"];
end


function save_png(fig,output_dir,name)
exportgraphics(fig,fullfile(output_dir,name),'Resolution',180);close(fig);
end
