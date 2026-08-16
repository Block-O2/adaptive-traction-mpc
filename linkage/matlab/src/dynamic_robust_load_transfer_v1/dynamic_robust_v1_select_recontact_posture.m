function selected = dynamic_robust_v1_select_recontact_posture( ...
        task_s, current_force_N, nominal, uncertainty, h_hip, config)
%DYNAMIC_ROBUST_V1_SELECT_RECONTACT_POSTURE Bed-aware return target search.

path=hybrid_tube_v1_task_path(task_s);
tube=hybrid_tube_v1_tube_schedule(task_s,path.q,config);
offsets1=candidate_offsets(rad2deg(tube(1)),config.posture_candidate_step_deg);
offsets2=candidate_offsets(rad2deg(tube(2)),config.posture_candidate_step_deg);
rows=zeros(0,10);candidates=cell(0,1);
for d1=offsets1
    for d2=offsets2
        q=path.q+deg2rad([d1;d2]);
        if any(q<nominal.q_min)||any(q>nominal.q_max),continue;end
        [~,passive]=human_two_link_v2_passive_torque(q,zeros(2,1),nominal);
        if any(passive.soft.active),continue;end
        bed=bed_supported_v1_contact(q,zeros(2,1),h_hip,nominal,config);
        if bed.total_normal_force_N<config.contact_force_threshold_N,continue;end
        robust=bed_supported_v1_robust_hold_point(q,nominal,uncertainty, ...
            config.force_bound_N,config.svd_relative_tolerance);
        robust_margin=config.force_bound_N-robust.worst_required_force_N;
        if robust_margin<=0||robust.nominal.exact_torque_residual_norm_Nm> ...
                config.plan_residual_tolerance_Nm
            continue;
        end
        dynamic=dynamic_robust_v1_dynamic_margin(q,zeros(2,1),q, ...
            zeros(2,1),zeros(2,1),nominal,config);
        if dynamic.margin_N<=0||dynamic.bounded_residual_norm_Nm> ...
                config.dynamic_residual_tolerance_Nm
            continue;
        end
        point=robust.nominal;
        row=[bed.total_normal_force_N-config.contact_force_threshold_N, ...
            -robust_margin,-dynamic.margin_N,point.force_norm_2_N, ...
            abs(point.F_parallel_N), ...
            norm(point.force_local_N-current_force_N(:)), ...
            norm(q-path.q),q(1),q(2),size(rows,1)+1];
        rows(end+1,:)=row; %#ok<AGROW>
        candidates{end+1}=struct('q',q,'path_q',path.q,'tube_rad',tube, ...
            'robust',robust,'dynamic',dynamic,'bed',bed); %#ok<AGROW>
    end
end
selected=struct('found',false,'q',[NaN;NaN],'path_q',path.q, ...
    'tube_rad',tube,'robust',[],'dynamic',[],'bed',[], ...
    'candidate_count',numel(candidates),'start_q',[NaN;NaN], ...
    'start_mode_time_s',NaN);
if isempty(rows),return;end
[~,order]=sortrows(rows,1:9);winner=rows(order(1),10);
selected=candidates{winner};selected.found=true;
selected.candidate_count=numel(candidates);
selected.start_q=[NaN;NaN];selected.start_mode_time_s=NaN;
end


function offsets=candidate_offsets(cap_deg,step_deg)
if cap_deg<=1e-12
    offsets=0;
else
    offsets=unique([-cap_deg:step_deg:cap_deg,0,cap_deg]);
end
end
