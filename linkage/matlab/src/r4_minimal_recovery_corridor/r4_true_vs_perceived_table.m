function comparison = r4_true_vs_perceived_table(boundary)
%R4_TRUE_VS_PERCEIVED_TABLE Side-by-side classification without conflation.

keys=unique(boundary.anchor_id+"|"+boundary.support_mode+"|"+ ...
    boundary.family+"|"+boundary.criterion,'stable');
n=numel(keys);anchor_id=strings(n,1);support_mode=strings(n,1);
family=strings(n,1);criterion=strings(n,1);
true_posture_cap_deg=nan(n,1);true_backward_progress=nan(n,1);
true_classification=strings(n,1);true_connected=false(n,1);
perceived_posture_cap_deg=nan(n,1);perceived_backward_progress=nan(n,1);
perceived_classification=strings(n,1);perceived_connected=false(n,1);
for k=1:n
    parts=split(keys(k),"|");anchor_id(k)=parts(1);support_mode(k)=parts(2);
    family(k)=parts(3);criterion(k)=parts(4);
    mask=boundary.anchor_id==anchor_id(k) & ...
        boundary.support_mode==support_mode(k) & boundary.family==family(k) & ...
        boundary.criterion==criterion(k);
    left=find(mask & boundary.model_kind=="true",1);
    right=find(mask & boundary.model_kind=="perceived",1);
    if ~isempty(left)
        true_posture_cap_deg(k)=boundary.posture_cap_deg(left);
        true_backward_progress(k)=boundary.backward_progress(left);
        true_classification(k)=boundary.classification(left);
        true_connected(k)=boundary.connected(left);
    end
    if ~isempty(right)
        perceived_posture_cap_deg(k)=boundary.posture_cap_deg(right);
        perceived_backward_progress(k)=boundary.backward_progress(right);
        perceived_classification(k)=boundary.classification(right);
        perceived_connected(k)=boundary.connected(right);
    end
end
comparison=table(anchor_id,support_mode,family,criterion, ...
    true_posture_cap_deg,true_backward_progress,true_classification, ...
    true_connected,perceived_posture_cap_deg,perceived_backward_progress, ...
    perceived_classification,perceived_connected);
end
