function bed_supported_v1_create_smoke_gif(result, gif_path)
%BED_SUPPORTED_V1_CREATE_SMOKE_GIF Supported-preposition smoke visualization.

p=result.parameters;c=result.config;h=result.h_hip_m;t=result.t;
fig=figure('Visible','off','Color','w','Position',[20 20 1500 820]);
layout=tiledlayout(fig,4,2,'TileSpacing','compact','Padding','compact');
ax=nexttile(layout,1,[4 1]);hold(ax,'on');axis(ax,'equal');grid(ax,'on');
reach=p.L1+p.L2;xlim(ax,[-0.1 reach+0.15]);ylim(ax,[-0.08 h+reach+0.12]);
plot(ax,[-0.2 reach+0.3],[0 0],'k-','LineWidth',5);text(ax,0.01,0.02,'bed y=0');
leg=plot(ax,nan,nan,'o-','LineWidth',5,'MarkerSize',8);plot(ax,0,h,'kp','MarkerFaceColor','k');
contacts=scatter(ax,nan,nan,55,'filled');bedarrows=quiver(ax,nan,nan,nan,nan,0,'Color',[.2 .65 .2],'LineWidth',1.4);
robotarrow=quiver(ax,nan,nan,nan,nan,0,'r','LineWidth',2);
info=text(ax,.02,.98,'','Units','normalized','VerticalAlignment','top', ...
    'Interpreter','none');

qax=nexttile(layout,2);hold(qax,'on');grid(qax,'on');
plot(qax,t,rad2deg(result.q_nominal(1,:)),'k--');plot(qax,t,rad2deg(result.q_nominal(2,:)),'k:');
plot(qax,t,rad2deg(result.q_ref(1,:)+result.tube_rad(1,:)),'Color',[.6 .6 1]);
plot(qax,t,rad2deg(result.q_ref(1,:)-result.tube_rad(1,:)),'Color',[.6 .6 1]);
plot(qax,t,rad2deg(result.q_ref(2,:)+result.tube_rad(2,:)),'Color',[1 .7 .7]);
plot(qax,t,rad2deg(result.q_ref(2,:)-result.tube_rad(2,:)),'Color',[1 .7 .7]);
q1=plot(qax,nan,nan,'b-','LineWidth',1.4);q2=plot(qax,nan,nan,'r-','LineWidth',1.4);
ylabel(qax,'q (deg)');title(qax,'Nominal, governed tube, and actual');

fax=nexttile(layout,4);hold(fax,'on');grid(fax,'on');
fa1=plot(fax,nan,nan,'b-');fa2=plot(fax,nan,nan,'r-');
fp1=plot(fax,nan,nan,'b--');fp2=plot(fax,nan,nan,'r--');
ylabel(fax,'robot force (N)');title(fax,'Actual solid; robot-only witness dashed');

bax=nexttile(layout,6);hold(bax,'on');grid(bax,'on');
bf=plot(bax,nan,nan,'k-','LineWidth',1.4);res=plot(bax,nan,nan,'m-');
ylabel(bax,'bed N / residual Nm');title(bax,'Bed support and bounded residual');

pax=nexttile(layout,8);hold(pax,'on');grid(pax,'on');
pg=plot(pax,nan,nan,'LineWidth',1.4);credit=plot(pax,nan,nan,'--');
ylabel(pax,'progress / bed credit');xlabel(pax,'time (s)');ylim(pax,[0 1.05]);
for panel=[qax fax bax pax],xlim(panel,[0 max(t(end),eps)]);end

frames=unique(round(linspace(1,numel(t),min(240,numel(t)))));
for frame_index=1:numel(frames)
    k=frames(frame_index);q=result.state(1:2,k);phi=q(1)-q(2);hip=[0;h];
    knee=hip+p.L1*[cos(q(1));sin(q(1))];ankle=knee+p.L2*[cos(phi);sin(phi)];
    set(leg,'XData',[hip(1) knee(1) ankle(1)],'YData',[hip(2) knee(2) ankle(2)]);
    bed=bed_supported_v1_contact(q,result.state(3:4,k),h,p,c);active=bed.active;
    set(contacts,'XData',bed.points.position_world(1,active), ...
        'YData',bed.points.position_world(2,active),'CData',bed.normal_force_N(active)');
    set(bedarrows,'XData',bed.points.position_world(1,active), ...
        'YData',bed.points.position_world(2,active),'UData',zeros(1,sum(active)), ...
        'VData',bed.normal_force_N(active)/800);
    mapping=single_arm_v2_force_map(q,result.state(3:4,k),p);
    force_world=mapping.rotation*result.robot_force_N(:,k)/800;
    contact=hip+mapping.contact.position;
    set(robotarrow,'XData',contact(1),'YData',contact(2), ...
        'UData',force_world(1),'VData',force_world(2));
    set(info,'String',sprintf(['+x right, +y up; q1 from +x\n%s  t=%.2f s  s=%.4f\n' ...
        'bed=%.1f N  robot=[%.1f %.1f] N\nrobot-only=[%.1f %.1f] N  residual=%.3g Nm'], ...
        result.mode(k),t(k),result.progress(k),result.bed_force_N(k), ...
        result.robot_force_N(1,k),result.robot_force_N(2,k), ...
        result.robot_only_force_N(1,k),result.robot_only_force_N(2,k), ...
        result.robot_only_residual_Nm(k)));
    set(q1,'XData',t(1:k),'YData',rad2deg(result.state(1,1:k)));
    set(q2,'XData',t(1:k),'YData',rad2deg(result.state(2,1:k)));
    set(fa1,'XData',t(1:k),'YData',result.robot_force_N(1,1:k));
    set(fa2,'XData',t(1:k),'YData',result.robot_force_N(2,1:k));
    set(fp1,'XData',t(1:k),'YData',result.robot_only_force_N(1,1:k));
    set(fp2,'XData',t(1:k),'YData',result.robot_only_force_N(2,1:k));
    set(bf,'XData',t(1:k),'YData',result.bed_force_N(1:k));
    set(res,'XData',t(1:k),'YData',result.robot_only_residual_Nm(1:k));
    set(pg,'XData',t(1:k),'YData',result.progress(1:k));
    set(credit,'XData',t(1:k),'YData',result.bed_credit(1:k));
    frame=getframe(fig);image=frame2im(frame);[indexed,map]=rgb2ind(image,256);
    if frame_index==1
        imwrite(indexed,map,gif_path,'gif','LoopCount',Inf,'DelayTime',.08);
    else
        imwrite(indexed,map,gif_path,'gif','WriteMode','append','DelayTime',.08);
    end
end
close(fig);
end
