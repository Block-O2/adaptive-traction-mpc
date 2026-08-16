function r3b_recontact_create_artifacts(results,names,old_adaptive, ...
        old_oracle,output_dir,create_gifs)
%R3B_RECONTACT_CREATE_ARTIFACTS Required comparisons and synchronized GIFs.

if nargin<6,create_gifs=true;end

colors={[.1 .1 .1],[0 .35 .8],[0 .6 0]};
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
for index=1:3
    ax=nexttile(layout);stairs(ax,results{index}.t, ...
        mode_numbers(results{index}.mode),'Color',colors{index}, ...
        'LineWidth',1.2);grid(ax,'on');ylabel(ax,names(index), ...
        'Interpreter','none');yticks(ax,1:9);yticklabels(ax,state_order());
    set(ax,'TickLabelInterpreter','none');
end
xlabel(nexttile(layout,3),'time (s)');title(layout,'R3B state timeline');
save_png(fig,output_dir,'state_timeline.png');

fig=figure('Visible','off','Color','w');hold on;grid on;
for index=1:3
    [time,~,~,margin]=aligned_contact(results{index});
    plot(time,margin,'Color',colors{index},'LineWidth',1.3);
end
yline(0,'k--','2 N stable threshold');
yline(results{1}.config.r3b_contact_reserve_N,'r--','3 N target');
xlabel('time after first contact (s)');ylabel('contact margin (N)');
legend(names,'Interpreter','none','Location','best');
title('Measured bed-contact reserve');
save_png(fig,output_dir,'recontact_contact_margin.png');

r=results{2};[time,gap,gap_velocity,~]=aligned_contact(r);
first=first_contact_index(r);last=find(r.mode=="LOAD_RETURN",1,'last');
if isempty(last),last=find(r.mode=="RECONTACT",1,'last');end
indices=first:last;
fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,3,1);
ax=nexttile(layout);plot(ax,time,1e3*gap,'b','LineWidth',1.2);grid(ax,'on');
yline(ax,0,'k--');ylabel(ax,'minimum gap (mm)');
ax=nexttile(layout);plot(ax,time,1e3*gap_velocity,'b','LineWidth',1.2);
grid(ax,'on');yline(ax,1e3*r.config.r3b_gap_velocity_tolerance_m_s,'k--');
yline(ax,-1e3*r.config.r3b_gap_velocity_tolerance_m_s,'k--');
ylabel(ax,'gap velocity (mm/s)');
ax=nexttile(layout);plot(ax,time,r.bed_force_N(indices),'k','LineWidth',1.3);
grid(ax,'on');yline(ax,r.config.contact_force_threshold_N,'k--');
yline(ax,r.config.r3b_contact_target_N,'r--');ylabel(ax,'bed force (N)');
xlabel(ax,'time after first contact (s)');
title(layout,'Mild adaptive gap and contact-force build-up');
save_png(fig,output_dir,'recontact_gap_force.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
items={old_adaptive,results{2}};labels=["R2B mild adaptive","R3B mild adaptive"];
for panel=1:2
    ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
    for index=1:2
        [time,gap,~,margin]=aligned_contact(items{index});
        if panel==1,value=margin;ylabel(ax,'contact margin (N)');
        else,value=1e3*gap;ylabel(ax,'minimum gap (mm)');end
        plot(ax,time,value,'LineWidth',1.2);
    end
    yline(ax,0,'k--');
end
xlabel(nexttile(layout,2),'time after first contact (s)');
legend(nexttile(layout,1),labels,'Location','best');
title(layout,'Frozen R2B versus R3B mild adaptive recontact');
save_png(fig,output_dir,'mild_old_vs_r3b.png');

fig=figure('Visible','off','Color','w');layout=tiledlayout(fig,2,1);
items={results{2},results{3},old_oracle};
labels=["R3B adaptive","R3B oracle","frozen R2A oracle"];
for panel=1:2
    ax=nexttile(layout);hold(ax,'on');grid(ax,'on');
    for index=1:3
        [time,~,~,margin]=aligned_contact(items{index});
        if panel==1,value=margin;ylabel(ax,'contact margin (N)');
        else
            first=first_contact_index(items{index});
            last=find(items{index}.mode=="LOAD_RETURN",1,'last');
            if isempty(last),last=find(items{index}.mode=="RECONTACT",1,'last');end
            if isempty(last),last=numel(items{index}.t);end
            value=rad2deg(items{index}.state(2,first:last));ylabel(ax,'q2 (deg)');
        end
        plot(ax,time,value,'LineWidth',1.2);
    end
    if panel==1,yline(ax,0,'k--');end
end
xlabel(nexttile(layout,2),'time after first contact (s)');
legend(nexttile(layout,1),labels,'Location','best');
title(layout,'Adaptive and oracle recontact comparison');
save_png(fig,output_dir,'adaptive_vs_oracle_recontact.png');

if create_gifs
    for index=1:3
        case_dir=fullfile(output_dir,char(names(index)));
        create_gif(results{index},fullfile(case_dir,'r3b_recontact_margin.gif'));
    end
end
end


function [time,gap,gap_velocity,margin]=aligned_contact(result)
first=first_contact_index(result);
last=find(result.mode=="LOAD_RETURN",1,'last');
if isempty(last),last=find(result.mode=="RECONTACT",1,'last');end
if isempty(last) || last<first,last=numel(result.t);end
indices=first:last;
time=result.t(indices)-result.t(first);
if isfield(result,'minimum_gap_m')
    gap=result.minimum_gap_m(indices);
    gap_velocity=result.minimum_gap_velocity_m_s(indices);
    margin=result.contact_margin_N(indices);
else
    [all_gap,all_velocity]=legacy_gap(result);
    gap=all_gap(indices);gap_velocity=all_velocity(indices);
    margin=result.bed_force_N(indices)-result.config.contact_force_threshold_N;
end
end


function first=first_contact_index(result)
entry=find(result.mode=="RECONTACT",1,'first');
if isempty(entry),entry=numel(result.t);end
active=result.active_contacts>0;
transitions=find(active(2:entry) & ~active(1:entry-1))+1;
if isempty(transitions),first=entry;else,first=transitions(end);end
end


function [gap,velocity]=legacy_gap(result)
n=numel(result.t);gap=nan(1,n);velocity=nan(1,n);
for index=1:n
    bed=bed_supported_v1_contact(result.state(1:2,index), ...
        result.state(3:4,index),result.h_hip_m,result.plant_parameters, ...
        result.config);
    [gap(index),point]=min(bed.gap_m);
    velocity(index)=bed.points.velocity_world(2,point);
end
end


function create_gif(r,path)
p=r.plant_parameters;c=r.config;h=r.h_hip_m;t=r.t;
fig=figure('Visible','off','Color','w','Position',[20 20 1500 840]);
layout=tiledlayout(fig,5,2,'TileSpacing','compact','Padding','compact');
ax=nexttile(layout,1,[5 1]);hold(ax,'on');axis(ax,'equal');grid(ax,'on');
reach=p.L1+p.L2;xlim(ax,[-.1 reach+.15]);ylim(ax,[-.08 h+reach+.12]);
plot(ax,[-.2 reach+.3],[0 0],'k-','LineWidth',5);
plot(ax,0,h,'kp','MarkerFaceColor','k');
leg=plot(ax,nan,nan,'o-','LineWidth',5,'MarkerSize',8);
contacts=scatter(ax,nan,nan,55,'filled');
info=text(ax,.02,.98,'','Units','normalized','VerticalAlignment','top', ...
    'Interpreter','none');
qax=nexttile(layout,2);hold(qax,'on');grid(qax,'on');
plot(qax,t,rad2deg(r.q_ref),':');q1=plot(qax,nan,nan,'b','LineWidth',1.2);
q2=plot(qax,nan,nan,'r','LineWidth',1.2);ylabel(qax,'q / ref (deg)');
fax=nexttile(layout,4);hold(fax,'on');grid(fax,'on');
f1=plot(fax,nan,nan,'b');f2=plot(fax,nan,nan,'r');
yline(fax,c.force_bound_N,'k--');yline(fax,-c.force_bound_N,'k--');
ylabel(fax,'robot force (N)');
cax=nexttile(layout,6);hold(cax,'on');grid(cax,'on');
margin=plot(cax,nan,nan,'k','LineWidth',1.2);yline(cax,0,'k--');
yline(cax,c.r3b_contact_reserve_N,'r--');ylabel(cax,'contact margin (N)');
gax=nexttile(layout,8);hold(gax,'on');grid(gax,'on');
gap=plot(gax,nan,nan,'b');velocity=plot(gax,nan,nan,'r');
yline(gax,0,'k--');ylabel(gax,'gap mm / velocity mm/s');
pax=nexttile(layout,10);hold(pax,'on');grid(pax,'on');
progress=plot(pax,nan,nan,'b');state=stairs(pax,nan,nan,'r');
ylabel(pax,'progress / state');xlabel(pax,'time (s)');
for panel=[qax fax cax gax pax],xlim(panel,[0 max(t(end),eps)]);end
frames=unique(round(linspace(1,numel(t),min(240,numel(t)))));
mode_index=mode_numbers(r.mode);
for frame_index=1:numel(frames)
    k=frames(frame_index);q=r.state(1:2,k);phi=q(1)-q(2);hip=[0;h];
    knee=hip+p.L1*[cos(q(1));sin(q(1))];
    ankle=knee+p.L2*[cos(phi);sin(phi)];
    set(leg,'XData',[hip(1) knee(1) ankle(1)], ...
        'YData',[hip(2) knee(2) ankle(2)]);
    bed=bed_supported_v1_contact(q,r.state(3:4,k),h,p,c);active=bed.active;
    set(contacts,'XData',bed.points.position_world(1,active), ...
        'YData',bed.points.position_world(2,active), ...
        'CData',bed.normal_force_N(active)');
    set(info,'String',sprintf([ ...
        '%s / %s  t=%.2f s  s=%.3f\nbed=%.3f N margin=%.3f N\n' ...
        'gap=%.3f mm  velocity=%.3f mm/s'],r.mode(k), ...
        r.recontact_stage(k),t(k),r.task_s(k),r.bed_force_N(k), ...
        r.contact_margin_N(k),1e3*r.minimum_gap_m(k), ...
        1e3*r.minimum_gap_velocity_m_s(k)));
    set(q1,'XData',t(1:k),'YData',rad2deg(r.state(1,1:k)));
    set(q2,'XData',t(1:k),'YData',rad2deg(r.state(2,1:k)));
    set(f1,'XData',t(1:k),'YData',r.robot_force_N(1,1:k));
    set(f2,'XData',t(1:k),'YData',r.robot_force_N(2,1:k));
    set(margin,'XData',t(1:k),'YData',r.contact_margin_N(1:k));
    set(gap,'XData',t(1:k),'YData',1e3*r.minimum_gap_m(1:k));
    set(velocity,'XData',t(1:k), ...
        'YData',1e3*r.minimum_gap_velocity_m_s(1:k));
    set(progress,'XData',t(1:k),'YData',r.task_s(1:k));
    set(state,'XData',t(1:k),'YData',mode_index(1:k)/9);
    frame=getframe(fig);frame_image=frame2im(frame);
    [indexed,map]=rgb2ind(frame_image,256);
    if frame_index==1
        imwrite(indexed,map,path,'gif','LoopCount',Inf,'DelayTime',.08);
    else
        imwrite(indexed,map,path,'gif','WriteMode','append','DelayTime',.08);
    end
end
close(fig);
end


function numbers=mode_numbers(mode)
order=state_order();numbers=zeros(size(mode));
for index=1:numel(order),numbers(mode==order(index))=index;end
end


function order=state_order()
order=["BED_SUPPORTED_MOTION","TRANSFER_READY","LOAD_TAKEOVER", ...
    "LIFTOFF","SUSPENDED_MOTION","RECONTACT","LOAD_RETURN", ...
    "BED_SUPPORTED_RETURN","TASK_COMPLETE"];
end


function save_png(fig,output_dir,name)
exportgraphics(fig,fullfile(output_dir,name),'Resolution',180);close(fig);
end
