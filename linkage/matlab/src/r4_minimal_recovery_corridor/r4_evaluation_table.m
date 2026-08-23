function t = r4_evaluation_table(values)
%R4_EVALUATION_TABLE Flatten setting evaluations.

n=numel(values);anchor_id=strings(n,1);case_name=strings(n,1);role=strings(n,1);
model_kind=strings(n,1);support_mode=strings(n,1);family=strings(n,1);
scan_stage=strings(n,1);posture_cap_deg=zeros(n,1);backward_progress=zeros(n,1);
grid_step_deg=zeros(n,1);progress_step=zeros(n,1);rate_deg_s=zeros(n,1);
point_count=zeros(n,1);feasible_point_count=zeros(n,1);transit_point_count=zeros(n,1);
nearest_feasible_distance_deg=zeros(n,1);nearest_q1_deg=zeros(n,1);
nearest_q2_deg=zeros(n,1);nearest_feasible_s=zeros(n,1);classification=strings(n,1);
connected=false(n,1);seed_count=zeros(n,1);visited_count=zeros(n,1);
minimum_path_force_margin_N=zeros(n,1);maximum_path_residual_Nm=zeros(n,1);
for k=1:n
    v=values(k);anchor_id(k)=v.anchor_id;case_name(k)=v.case_name;role(k)=v.role;
    model_kind(k)=v.model_kind;support_mode(k)=v.support_mode;family(k)=v.family;
    scan_stage(k)=v.scan_stage;posture_cap_deg(k)=v.posture_cap_deg;
    backward_progress(k)=v.backward_progress;grid_step_deg(k)=v.grid_step_deg;
    progress_step(k)=v.progress_step;rate_deg_s(k)=v.rate_deg_s;
    point_count(k)=v.point_count;feasible_point_count(k)=v.feasible_point_count;
    transit_point_count(k)=v.transit_point_count;
    nearest_feasible_distance_deg(k)=v.nearest_feasible_distance_deg;
    nearest_q1_deg(k)=rad2deg(v.nearest_feasible_q_rad(1));
    nearest_q2_deg(k)=rad2deg(v.nearest_feasible_q_rad(2));
    nearest_feasible_s(k)=v.nearest_feasible_s;classification(k)=v.classification;
    connected(k)=v.connected;seed_count(k)=v.seed_count;visited_count(k)=v.visited_count;
    minimum_path_force_margin_N(k)=v.minimum_path_force_margin_N;
    maximum_path_residual_Nm(k)=v.maximum_path_residual_Nm;
end
t=table(anchor_id,case_name,role,model_kind,support_mode,family,scan_stage, ...
    posture_cap_deg,backward_progress,grid_step_deg,progress_step,rate_deg_s, ...
    point_count,feasible_point_count,transit_point_count, ...
    nearest_feasible_distance_deg,nearest_q1_deg,nearest_q2_deg, ...
    nearest_feasible_s,classification,connected,seed_count,visited_count, ...
    minimum_path_force_margin_N,maximum_path_residual_Nm);
end
