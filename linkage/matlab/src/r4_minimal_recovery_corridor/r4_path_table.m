function paths = r4_path_table(values,boundary)
%R4_PATH_TABLE Flatten selected connected paths for CSV export.

anchor_id=strings(0,1);model_kind=strings(0,1);support_mode=strings(0,1);
family=strings(0,1);criterion=strings(0,1);path_index=zeros(0,1);
task_s=zeros(0,1);q1_deg=zeros(0,1);q2_deg=zeros(0,1);
for row=1:height(boundary)
    if ~boundary.connected(row),continue;end
    mask=[values.anchor_id]==boundary.anchor_id(row) & ...
        [values.model_kind]==boundary.model_kind(row) & ...
        [values.support_mode]==boundary.support_mode(row) & ...
        [values.family]==boundary.family(row) & ...
        abs([values.posture_cap_deg]-boundary.posture_cap_deg(row))<1e-12 & ...
        abs([values.backward_progress]-boundary.backward_progress(row))<1e-12 & ...
        [values.connected];
    match=find(mask,1);if isempty(match),continue;end
    value=values(match);
    for k=1:size(value.path_q_rad,2)
        anchor_id(end+1,1)=value.anchor_id;model_kind(end+1,1)=value.model_kind; %#ok<AGROW>
        support_mode(end+1,1)=value.support_mode;family(end+1,1)=value.family; %#ok<AGROW>
        criterion(end+1,1)=boundary.criterion(row);path_index(end+1,1)=k; %#ok<AGROW>
        task_s(end+1,1)=value.path_s(k);q1_deg(end+1,1)=rad2deg(value.path_q_rad(1,k)); %#ok<AGROW>
        q2_deg(end+1,1)=rad2deg(value.path_q_rad(2,k)); %#ok<AGROW>
    end
end
paths=table(anchor_id,model_kind,support_mode,family,criterion,path_index, ...
    task_s,q1_deg,q2_deg);
end
