function boundary = r4_boundary_table(values)
%R4_BOUNDARY_TABLE Minimal A/B freedoms and C Pareto/knee selections.

anchor_values=reshape([values.anchor_id],[],1);
model_values=reshape([values.model_kind],[],1);
support_values=reshape([values.support_mode],[],1);
contexts=unique(anchor_values+"|"+model_values+"|"+support_values,'stable');
selected=repmat(values(1),0,1);criteria=strings(0,1);
for context=reshape(contexts,1,[])
    parts=split(context,"|");
    mask=[values.anchor_id]==parts(1) & [values.model_kind]==parts(2) & ...
        [values.support_mode]==parts(3) & ...
        ~ismember([values.scan_stage],["rate_sensitivity","convergence_0p25deg"]);
    rows=values(mask);
    for family=["A_POSTURE_ONLY","B_BACKWARD_ONLY"]
        family_rows=rows([rows.family]==family);
        connected=family_rows([family_rows.connected]);
        if isempty(connected)
            if isempty(family_rows),continue;end
            [~,idx]=max([family_rows.posture_cap_deg]+ ...
                100*[family_rows.backward_progress]);pick=family_rows(idx);
        elseif family=="A_POSTURE_ONLY"
            [~,idx]=min([connected.posture_cap_deg]);pick=connected(idx);
        else
            [~,idx]=min([connected.backward_progress]);pick=connected(idx);
        end
        selected(end+1)=pick; %#ok<AGROW>
        if family=="A_POSTURE_ONLY"
            criteria(end+1)="minimum_posture"; %#ok<AGROW>
        else
            criteria(end+1)="minimum_reversal"; %#ok<AGROW>
        end
    end
    family_rows=rows([rows.family]=="C_COMBINED");
    connected=family_rows([family_rows.connected]);
    if isempty(connected)
        if ~isempty(family_rows)
            [~,idx]=max([family_rows.posture_cap_deg]+ ...
                100*[family_rows.backward_progress]);
            selected(end+1)=family_rows(idx);criteria(end+1)="no_connected_pareto"; %#ok<AGROW>
        end
    else
        caps=[connected.posture_cap_deg];backs=[connected.backward_progress];
        pareto=true(size(caps));
        for i=1:numel(caps)
            pareto(i)=~any((caps<=caps(i)&backs<=backs(i)) & ...
                (caps<caps(i)|backs<backs(i)));
        end
        candidates=connected(pareto);caps=[candidates.posture_cap_deg];
        backs=[candidates.backward_progress];
        [~,i1]=min(caps);selected(end+1)=candidates(i1);criteria(end+1)="pareto_min_posture"; %#ok<AGROW>
        [~,i2]=min(backs);selected(end+1)=candidates(i2);criteria(end+1)="pareto_min_reversal"; %#ok<AGROW>
        [~,ik]=min((caps/30).^2+(backs/0.20).^2);
        selected(end+1)=candidates(ik);criteria(end+1)="pareto_balanced_knee"; %#ok<AGROW>
    end
end
boundary=r4_evaluation_table(selected);
if height(boundary)~=numel(criteria)
    error('R4:BoundaryAssemblyMismatch', ...
        'Boundary rows %d do not match criteria %d.',height(boundary),numel(criteria));
end
boundary.criterion=criteria(:);
end
