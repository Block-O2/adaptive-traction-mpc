function domain = r4_candidate_domain(anchor,model_kind,support_mode, ...
        posture_cap_deg,backward_progress,grid_step_deg,progress_step,cache)
%R4_CANDIDATE_DOMAIN Deterministic lattice inside the frozen task tube.

if nargin<8 || isempty(cache)
    cache=containers.Map('KeyType','char','ValueType','any');
end
s_min=max(0,anchor.task_s-backward_progress);
if backward_progress<=1e-12
    s_values=anchor.task_s;
else
    s_values=unique([s_min:progress_step:anchor.task_s,anchor.task_s]);
end
q_values=zeros(2,0);s_column=zeros(0,1);d1_column=zeros(0,1);
d2_column=zeros(0,1);is_goal=false(0,1);is_transit=false(0,1);
force_margin=zeros(0,1);residual=zeros(0,1);bed_force=zeros(0,1);
for s=s_values
    path=hybrid_tube_v1_task_path(s);
    tube_config=anchor.config;tube_config.tube_cap_deg=posture_cap_deg;
    tube=hybrid_tube_v1_tube_schedule(s,path.q,tube_config);
    d1=offset_values(rad2deg(tube(1)),grid_step_deg);
    d2=offset_values(rad2deg(tube(2)),grid_step_deg);
    for a=d1
        for b=d2
            q=path.q+deg2rad([a;b]);
            key=sprintf('%.12f|%.12f',q(1),q(2));
            if isKey(cache,key)
                point=cache(key);
            else
                point=r4_point_feasibility(q,anchor,model_kind,support_mode);
                cache(key)=point;
            end
            q_values(:,end+1)=q; %#ok<AGROW>
            s_column(end+1,1)=s;d1_column(end+1,1)=a;d2_column(end+1,1)=b; %#ok<AGROW>
            is_goal(end+1,1)=point.feasible; %#ok<AGROW>
            is_transit(end+1,1)=point.transit_feasible; %#ok<AGROW>
            force_margin(end+1,1)=point.force_margin_N; %#ok<AGROW>
            residual(end+1,1)=point.bounded_residual_norm_Nm; %#ok<AGROW>
            bed_force(end+1,1)=point.bed_force_N; %#ok<AGROW>
        end
    end
end
domain=struct('q_rad',q_values,'s',s_column,'d1_deg',d1_column, ...
    'd2_deg',d2_column,'is_goal',is_goal,'is_transit',is_transit, ...
    'force_margin_N',force_margin,'residual_Nm',residual, ...
    'bed_force_N',bed_force,'s_values',s_values, ...
    'posture_cap_deg',posture_cap_deg, ...
    'backward_progress',backward_progress,'grid_step_deg',grid_step_deg);
end

function values=offset_values(cap,step)
if cap<=1e-12
    values=0;
else
    interior=floor(cap/step)*step;
    values=unique([-interior:step:interior,-cap,0,cap]);
end
end
