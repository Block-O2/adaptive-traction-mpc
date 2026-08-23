function table_value = r4_anchor_table(anchors)
%R4_ANCHOR_TABLE Flatten R4 anchors for CSV evidence.

n = numel(anchors);
anchor_id = strings(n,1); case_name = strings(n,1); role = strings(n,1);
primary = false(n,1); source_name = strings(n,1); source_result_index=zeros(n,1);
sample_index=zeros(n,1); time_s=zeros(n,1); task_s=zeros(n,1);
q1_deg=zeros(n,1); q2_deg=zeros(n,1); dq1_deg_s=zeros(n,1);
dq2_deg_s=zeros(n,1); u1_N=zeros(n,1); u2_N=zeros(n,1);
bed_force_N=zeros(n,1); active_contacts=zeros(n,1);
safety_state=strings(n,1); safety_reason=strings(n,1);
for k=1:n
    a=anchors(k); anchor_id(k)=a.anchor_id; case_name(k)=a.case_name;
    role(k)=a.role; primary(k)=a.primary; source_name(k)=a.source_name;
    source_result_index(k)=a.source_result_index; sample_index(k)=a.sample_index;
    time_s(k)=a.time_s; task_s(k)=a.task_s;
    q1_deg(k)=rad2deg(a.q_rad(1));q2_deg(k)=rad2deg(a.q_rad(2));
    dq1_deg_s(k)=rad2deg(a.dq_rad_s(1));
    dq2_deg_s(k)=rad2deg(a.dq_rad_s(2));
    u1_N(k)=a.u_previous_N(1);u2_N(k)=a.u_previous_N(2);
    bed_force_N(k)=a.bed_force_N;active_contacts(k)=a.active_contacts;
    safety_state(k)=a.safety_state;safety_reason(k)=a.safety_reason;
end
table_value=table(anchor_id,case_name,role,primary,source_name, ...
    source_result_index,sample_index,time_s,task_s,q1_deg,q2_deg, ...
    dq1_deg_s,dq2_deg_s,u1_N,u2_N,bed_force_N,active_contacts, ...
    safety_state,safety_reason);
end
