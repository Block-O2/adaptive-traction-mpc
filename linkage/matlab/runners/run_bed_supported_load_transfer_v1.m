function run_bed_supported_load_transfer_v1()
%RUN_BED_SUPPORTED_LOAD_TRANSFER_V1 Formal 18-case supported-cycle matrix.
%
% Repository policy reserves execution of this formal scientific matrix for
% the user. Figures remain invisible and all artifacts are ignored locally.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'bed_supported_load_transfer_v1');
if ~isfolder(output_dir), mkdir(output_dir); end
old_gifs = dir(fullfile(output_dir, '*.gif'));
for k = 1:numel(old_gifs), delete(fullfile(old_gifs(k).folder, old_gifs(k).name)); end
diary_path = fullfile(output_dir, 'console.log');
if isfile(diary_path), delete(diary_path); end
diary(diary_path); cleanup = onCleanup(@() diary('off'));

fprintf('BED-SUPPORTED LOAD TRANSFER V1 MATLAB: %s\n', version);
fprintf('OUTPUT DIRECTORY: %s\n', output_dir);
fprintf(['FORMAL COMMAND: matlab -batch "addpath(genpath(''' ...
    'linkage/matlab'')); run_bed_supported_load_transfer_v1"\n']);
p = human_two_link_v2_parameters(1.72, 75);
bounds = [80, 120, 200]; caps = [5, 10];
stiffness_cases = ["softer", "nominal", "stiffer"];
results = cell(numel(stiffness_cases), numel(bounds), numel(caps));
records = repmat(empty_record(), numel(results), 1); row = 0;
for stiffness_index = 1:numel(stiffness_cases)
    for bound_index = 1:numel(bounds)
        for cap_index = 1:numel(caps)
            config = bed_supported_v1_config(bounds(bound_index), ...
                caps(cap_index), stiffness_cases(stiffness_index));
            calibration = bed_supported_v1_calibrate_hip_height(p, config);
            plan = hybrid_tube_v1_build_plan(p, config);
            result = simulate_bed_supported_load_transfer_v1( ...
                config, p, plan, calibration);
            results{stiffness_index,bound_index,cap_index} = result;
            row = row+1; records(row) = make_record(result);
            print_record(records(row));
        end
    end
end
save(fullfile(output_dir, 'formal_results.mat'), 'results', 'records', ...
    'p', 'bounds', 'caps', 'stiffness_cases', '-v7.3');
writetable(struct2table(records), fullfile(output_dir, 'case_metrics.csv'));
write_summary(fullfile(output_dir, 'summary.txt'), records, results);

representative = results{2,3,2}; % nominal bed, 200 N, 10-degree tube.
create_static_figures(representative, records, output_dir);
for bound_index = 1:numel(bounds)
    result = results{2,bound_index,2};
    create_supported_gif(result, fullfile(output_dir, sprintf( ...
        'nominal_tube_10deg_%gN_representative.gif', bounds(bound_index))));
end
if numel(dir(fullfile(output_dir, '*.gif'))) ~= 3
    error('BedSupportedV1:GifCount', 'Expected exactly three GIF files.');
end
if ~isempty(findall(groot, 'Type', 'figure', 'Visible', 'on'))
    error('BedSupportedV1:VisibleFigure', ...
        'The formal runner created a visible figure.');
end
end


function r = empty_record()
r = struct('case_name',"",'stiffness_case',"",'force_bound_N',NaN, ...
    'tube_cap_deg',NaN,'terminal_state',"",'duration_s',NaN, ...
    'final_progress',NaN,'h_hip_m',NaN,'initial_bed_force_N',NaN, ...
    'initial_robot_parallel_N',NaN,'initial_robot_perp_N',NaN, ...
    'initial_robot_norm_N',NaN,'peak_robot_force_N',NaN, ...
    'peak_bed_force_N',NaN,'peak_force_rate_N_s',NaN, ...
    'liftoff_time_s',NaN,'liftoff_q1_deg',NaN,'liftoff_q2_deg',NaN, ...
    'liftoff_parallel_N',NaN,'liftoff_perp_N',NaN, ...
    'liftoff_force_norm_N',NaN,'liftoff_sigma_min',NaN, ...
    'liftoff_condition',NaN,'peak_balance_residual_Nm',NaN, ...
    'peak_controller_residual_Nm',NaN,'max_penetration_m',NaN, ...
    'contact_chatter_count',NaN,'soft_limit_count',NaN, ...
    'rom_violation_count',NaN,'nonfinite_count',NaN);
end


function r = make_record(result)
m = result.metrics; c = result.config; r = empty_record();
r.case_name = string(c.case_name); r.stiffness_case = c.stiffness_case;
r.force_bound_N = c.force_bound_N; r.tube_cap_deg = c.tube_cap_deg;
r.terminal_state = m.terminal_state; r.duration_s = m.duration_s;
r.final_progress = m.final_progress; r.h_hip_m = result.h_hip_m;
r.initial_bed_force_N = m.initial_bed_force_N;
r.initial_robot_parallel_N = m.initial_robot_force_N(1);
r.initial_robot_perp_N = m.initial_robot_force_N(2);
r.initial_robot_norm_N = norm(m.initial_robot_force_N);
r.peak_robot_force_N = m.peak_robot_force_N;
r.peak_bed_force_N = m.peak_bed_force_N;
r.peak_force_rate_N_s = m.peak_force_rate_N_s;
r.liftoff_time_s = m.liftoff_time_s;
r.liftoff_q1_deg = m.liftoff_q_deg(1); r.liftoff_q2_deg = m.liftoff_q_deg(2);
r.liftoff_parallel_N = m.liftoff_force_N(1); r.liftoff_perp_N = m.liftoff_force_N(2);
r.liftoff_force_norm_N = norm(m.liftoff_force_N);
r.liftoff_sigma_min = m.liftoff_sigma_min; r.liftoff_condition = m.liftoff_condition;
r.peak_balance_residual_Nm = m.peak_balance_residual_Nm;
r.peak_controller_residual_Nm = m.peak_controller_residual_Nm;
r.max_penetration_m = m.max_penetration_m;
r.contact_chatter_count = m.contact_chatter_count;
r.soft_limit_count = m.soft_limit_count;
r.rom_violation_count = m.rom_violation_count;
r.nonfinite_count = m.nonfinite_count;
end


function print_record(r)
fprintf(['CASE %s terminal=%s t=%.3f s=%.5f h=%.5f ' ...
    'initial_bed=%.3fN initial_robot=%.3fN peak_robot=%.3fN ' ...
    'peak_bed=%.3fN liftoff=%.3fs residual=%.3gNm\n'], ...
    r.case_name,r.terminal_state,r.duration_s,r.final_progress,r.h_hip_m, ...
    r.initial_bed_force_N,r.initial_robot_norm_N,r.peak_robot_force_N, ...
    r.peak_bed_force_N,r.liftoff_time_s,r.peak_balance_residual_Nm);
end


function write_summary(path, records, results)
file = fopen(path,'w'); assert(file>=0); cleanup = onCleanup(@() fclose(file));
fprintf(file,'Bed-supported load-transfer V1 formal comparison\nMATLAB %s\n',version);
z = results{2,1,1}.calibration;
fprintf(file,['nominal calibrated h_hip=%.9g m; initial gaps=%s m; ' ...
    'initial penetration=%s m\n'],z.h_hip_m,mat2str(z.bed.gap_m,6), ...
    mat2str(z.bed.penetration_m,6));
for k=1:numel(records)
    r=records(k); fprintf(file,['%s: terminal=%s, progress=%.9g, ' ...
        'initial bed=%.9g N, initial robot=%.9g N, peak robot=%.9g N, ' ...
        'peak bed=%.9g N, liftoff=%.9g s\n'],r.case_name,r.terminal_state, ...
        r.final_progress,r.initial_bed_force_N,r.initial_robot_norm_N, ...
        r.peak_robot_force_N,r.peak_bed_force_N,r.liftoff_time_s);
end
end


function create_static_figures(r, records, output_dir)
t=r.t;
fig=figure('Visible','off','Color','w'); hold on; grid on;
plot(t,r.bed_force_N,'LineWidth',1.5); plot(t,vecnorm(r.robot_force_N,2,1),'LineWidth',1.5);
xlabel('time (s)'); ylabel('force (N)'); legend('bed total normal','robot norm');
title('Bed and robot load share'); savefigpng(fig,output_dir,'bed_vs_robot_load_share.png');
fig=figure('Visible','off','Color','w'); hold on; grid on;
plot(rad2deg(r.q_nominal(1,:)),rad2deg(r.q_nominal(2,:)),'k--');
plot(rad2deg(r.q_ref(1,:)),rad2deg(r.q_ref(2,:)),'b-');
plot(rad2deg(r.state(1,:)),rad2deg(r.state(2,:)),'r-');
xlabel('q1 (deg)');ylabel('q2 (deg)');legend('path','governed','actual');
title('Joint-space path and supported cycle');savefigpng(fig,output_dir,'q1_q2_actual_tube_path.png');
fig=figure('Visible','off','Color','w');plot(t,[r.robot_force_N;vecnorm(r.robot_force_N,2,1)]);grid on;
xlabel('time (s)');ylabel('robot force (N)');legend('F parallel','F perp','norm');
savefigpng(fig,output_dir,'robot_force.png');
fig=figure('Visible','off','Color','w');plot(t,r.bed_force_N);grid on;xlabel('time (s)');ylabel('bed normal force (N)');
savefigpng(fig,output_dir,'bed_support_force.png');
fig=figure('Visible','off','Color','w');semilogy(t,max(vecnorm(r.balance_residual_Nm,2,1),eps));grid on;
xlabel('time (s)');ylabel('balance residual (Nm)');savefigpng(fig,output_dir,'generalized_torque_balance_residual.png');
fig=figure('Visible','off','Color','w');stairs(t,double(categorical(r.mode)));grid on;xlabel('time (s)');ylabel('hybrid mode index');
savefigpng(fig,output_dir,'contact_state_timeline.png');
fig=figure('Visible','off','Color','w');plot(t,r.bed_force_N,'LineWidth',1.4);hold on;grid on;
idx=find(r.mode=="LIFTOFF",1);if ~isempty(idx),plot(t(idx),r.bed_force_N(idx),'ko','MarkerFaceColor','k');text(t(idx),r.bed_force_N(idx),' lift-off');end
idx=find(r.mode=="RECONTACT",1);if ~isempty(idx),plot(t(idx),r.bed_force_N(idx),'ks','MarkerFaceColor','k');text(t(idx),r.bed_force_N(idx),' re-contact');end
xlabel('time (s)');ylabel('bed force (N)');title('Lift-off and re-contact events');savefigpng(fig,output_dir,'liftoff_recontact_annotated.png');
T=struct2table(records);fig=figure('Visible','off','Color','w');scatter(T.initial_bed_force_N,T.peak_robot_force_N,60,T.force_bound_N,'filled');grid on;
xlabel('initial bed force (N)');ylabel('peak robot force (N)');colorbar;savefigpng(fig,output_dir,'stiffness_sensitivity.png');
end


function savefigpng(fig,output_dir,name)
exportgraphics(fig,fullfile(output_dir,name),'Resolution',180);close(fig);
end


function create_supported_gif(r,path)
p=r.parameters;c=r.config;h=r.h_hip_m;t=r.t;
fig=figure('Visible','off','Color','w','Position',[20 20 1400 780]);
layout=tiledlayout(fig,4,2,'TileSpacing','compact');
ax=nexttile(layout,1,[4 1]);hold(ax,'on');axis(ax,'equal');grid(ax,'on');
reach=p.L1+p.L2;xlim(ax,[-0.1 reach+0.15]);ylim(ax,[-0.08 h+reach+0.12]);
plot(ax,[-0.2 reach+0.3],[0 0],'k-','LineWidth',5);text(ax,0.01,0.02,'bed y=0');
leg=plot(ax,nan,nan,'o-','LineWidth',5,'MarkerSize',8);plot(ax,0,h,'kp','MarkerFaceColor','k');text(ax,0,h,sprintf(' hip h=%.3f m',h));
contacts=scatter(ax,nan,nan,60,'filled');bedarrows=quiver(ax,nan,nan,nan,nan,0,'Color',[0.2 0.65 0.2],'LineWidth',1.5);robotarrow=quiver(ax,nan,nan,nan,nan,0,'r','LineWidth',2);
info=text(ax,0.02,0.98,'','Units','normalized','VerticalAlignment','top');
qax=nexttile(layout,2);hold(qax,'on');grid(qax,'on');plot(qax,t,rad2deg(r.q_nominal),'--');qa=plot(qax,nan,nan);qb=plot(qax,nan,nan);ylabel(qax,'q (deg)');
fax=nexttile(layout,4);hold(fax,'on');grid(fax,'on');fp=plot(fax,nan,nan);fn=plot(fax,nan,nan);bf=plot(fax,nan,nan,'k-');ylabel(fax,'force (N)');
pax=nexttile(layout,6);hold(pax,'on');grid(pax,'on');pg=plot(pax,nan,nan);ls=plot(pax,nan,nan);ylabel(pax,'progress/share');ylim(pax,[0 1.05]);
maxmode=max(double(categorical(r.mode)));maxmode=max(maxmode,1);
maxax=nexttile(layout,8);hold(maxax,'on');grid(maxax,'on');md=stairs(maxax,nan,nan);ylabel(maxax,'mode');ylim(maxax,[0.5 maxmode+0.5]);xlabel(maxax,'time (s)');
for a=[qax fax pax maxax],xlim(a,[0 max(t(end),eps)]);end
frames=unique(round(linspace(1,numel(t),min(240,numel(t)))));
for j=1:numel(frames)
 k=frames(j);q=r.state(1:2,k);phi=q(1)-q(2);hip=[0;h];knee=hip+p.L1*[cos(q(1));sin(q(1))];ankle=knee+p.L2*[cos(phi);sin(phi)];
 set(leg,'XData',[hip(1) knee(1) ankle(1)],'YData',[hip(2) knee(2) ankle(2)]);
 bed=bed_supported_v1_contact(q,r.state(3:4,k),h,p,c);active=bed.active;
 set(contacts,'XData',bed.points.position_world(1,active),'YData',bed.points.position_world(2,active),'CData',bed.normal_force_N(active)');
 set(bedarrows,'XData',bed.points.position_world(1,active),'YData',bed.points.position_world(2,active),'UData',zeros(1,sum(active)),'VData',bed.normal_force_N(active)/800);
 map=single_arm_v2_force_map(q,r.state(3:4,k),p);fw=map.rotation*r.robot_force_N(:,k)/800;cp=hip+map.contact.position;
 set(robotarrow,'XData',cp(1),'YData',cp(2),'UData',fw(1),'VData',fw(2));
 set(info,'String',sprintf(['+x right, +y up; q1 from +x\n%s  t=%.2f s  s=%.3f\n' ...
  'robot=[%.1f %.1f] N  bed=%.1f N'],r.mode(k),t(k),r.progress(k),r.robot_force_N(1,k),r.robot_force_N(2,k),r.bed_force_N(k)));
 set(qa,'XData',t(1:k),'YData',rad2deg(r.state(1,1:k)));set(qb,'XData',t(1:k),'YData',rad2deg(r.state(2,1:k)));
 set(fp,'XData',t(1:k),'YData',r.robot_force_N(1,1:k));set(fn,'XData',t(1:k),'YData',r.robot_force_N(2,1:k));set(bf,'XData',t(1:k),'YData',r.bed_force_N(1:k));
 set(pg,'XData',t(1:k),'YData',r.progress(1:k));set(ls,'XData',t(1:k),'YData',r.robot_load_share(1:k));
 set(md,'XData',t(1:k),'YData',double(categorical(r.mode(1:k))));
 frame=getframe(fig);im=frame2im(frame);[ind,cmap]=rgb2ind(im,256);
 if j==1,imwrite(ind,cmap,path,'gif','LoopCount',Inf,'DelayTime',0.08);else,imwrite(ind,cmap,path,'gif','WriteMode','append','DelayTime',0.08);end
end
close(fig);
end
