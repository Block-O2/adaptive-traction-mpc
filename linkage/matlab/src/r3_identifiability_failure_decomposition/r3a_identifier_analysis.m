function analysis = r3a_identifier_analysis(r2b)
%R3A_IDENTIFIER_ANALYSIS Reconstruct all formal R2B sensitivity windows.

names=string(r2b.names);window_records=repmat(empty_window_record(),0,1);
singular_records=repmat(empty_singular_record(),0,1);
correlation_records=repmat(empty_correlation_record(),0,1);
phase_records=repmat(empty_phase_record(),0,1);
case_info=repmat(struct('name',"",'times',[],'ranks',[], ...
    'accepted',[],'statuses',strings(0,1),'stacked_J',[], ...
    'final_J',[],'stacked_V',[],'final_V',[], ...
    'stacked_singular_values',[],'final_singular_values',[], ...
    'stacked_correlation',[],'final_correlation',[]),numel(names),1);
for case_index=1:numel(names)
    result=r2b.results{case_index};attempts=find( ...
        result.identifier_update_attempted);
    stacked_J=zeros(0,7);phase_names=strings(0,1);phase_matrices=cell(0,1);
    times=zeros(numel(attempts),1);ranks=zeros(numel(attempts),1);
    accepted=false(numel(attempts),1);statuses=strings(numel(attempts),1);
    final_diagnostic=[];
    truth=dynamic_robust_v1_adaptive_theta_from_parameters( ...
        result.nominal_parameters,result.plant_parameters);
    for attempt_index=1:numel(attempts)
        end_index=attempts(attempt_index);
        window=r3a_reconstruct_identifier_window(result,end_index);
        theta_raw=result.identifier_theta_raw(:,end_index);
        diagnostic=r3a_identifier_window_jacobian(window,theta_raw, ...
            result.nominal_parameters,result.h_hip_m,result.config, ...
            result.adaptive_config);
        final_diagnostic=diagnostic;stacked_J=[stacked_J;diagnostic.J]; %#ok<AGROW>
        times(attempt_index)=result.t(end_index);ranks(attempt_index)=diagnostic.rank;
        accepted(attempt_index)=result.identifier_update_accepted(end_index);
        statuses(attempt_index)=result.identifier_status(end_index);
        before=result.identifier_theta_model(:,max(1,end_index-1));
        after=result.identifier_theta_model(:,end_index);
        record=empty_window_record();record.case_name=names(case_index);
        record.attempt_index=attempt_index;record.time_s=result.t(end_index);
        record.hybrid_mode=result.mode(end_index);
        record.takeover_mode=result.takeover_mode(end_index);
        record.window_start_time_s=window.start_time_s;
        record.window_end_time_s=window.end_time_s;
        record.window_start_index=window.source_index(1);
        record.window_end_index=end_index;record.sample_count=size(window.x,2);
        record.logged_rank=result.identifier_rank(end_index);
        record.reconstructed_rank=diagnostic.rank;
        values=pad_singular_values(diagnostic.singular_values);
        for value_index=1:7
            record.(sprintf('sigma_%d',value_index))=values(value_index);
        end
        record.smallest_singular_value=values(7);
        record.rank_tolerance=diagnostic.tolerance;
        record.condition_number=diagnostic.condition_number;
        record.logged_condition_number= ...
            result.identifier_condition_number(end_index);
        record.status=result.identifier_status(end_index);
        record.accepted=result.identifier_update_accepted(end_index);
        record.theta_before_json=string(jsonencode(before));
        record.theta_raw_json=string(jsonencode(theta_raw));
        record.theta_after_json=string(jsonencode(after));
        record.normalized_error_before=norm((before-truth)./ ...
            result.adaptive_config.theta_range);
        record.normalized_error_after=norm((after-truth)./ ...
            result.adaptive_config.theta_range);
        record.hybrid_composition_json=composition_json(window.hybrid_mode);
        record.takeover_composition_json=composition_json(window.takeover_mode);
        window_records(end+1)=record; %#ok<AGROW>
        window_modes=string(window.hybrid_mode);
        unique_modes=unique(window_modes,'stable');
        for mode_index=1:numel(unique_modes)
            phase=unique_modes(mode_index);location=find(phase_names==phase,1);
            if isempty(location)
                phase_names(end+1)=phase;phase_matrices{end+1}=zeros(0,7); %#ok<AGROW>
                location=numel(phase_names);
            end
            transition_indices=find(window_modes==phase);
            row_indices=reshape((4*(transition_indices-1)+(1:4)') ,[],1);
            phase_matrices{location}=[phase_matrices{location}; ...
                diagnostic.J(row_indices,:)];
        end
    end
    [stacked_rank,stacked_tol,stacked_condition,stacked_singular,stacked_V]= ...
        r3a_effective_rank(stacked_J);
    stacked_correlation=r3a_safe_column_correlation(stacked_J);
    singular_records(end+1)=make_singular_record(names(case_index), ...
        "stacked_attempt_windows",stacked_rank,stacked_tol, ...
        stacked_condition,stacked_singular); %#ok<AGROW>
    singular_records(end+1)=make_singular_record(names(case_index), ...
        "final_window",final_diagnostic.rank,final_diagnostic.tolerance, ...
        final_diagnostic.condition_number, ...
        final_diagnostic.singular_values); %#ok<AGROW>
    correlation_records=[correlation_records;make_correlation_records( ...
        names(case_index),"stacked_attempt_windows",stacked_correlation, ...
        result.adaptive_config.parameter_names)]; %#ok<AGROW>
    correlation_records=[correlation_records;make_correlation_records( ...
        names(case_index),"final_window", ...
        final_diagnostic.column_correlation, ...
        result.adaptive_config.parameter_names)]; %#ok<AGROW>
    for phase_index=1:numel(phase_names)
        matrix=phase_matrices{phase_index};
        [phase_rank,phase_tol,phase_condition,phase_singular]= ...
            r3a_effective_rank(matrix);
        phase_records(end+1)=make_phase_record(names(case_index), ...
            phase_names(phase_index),size(matrix,1)/4,size(matrix,1), ...
            phase_rank,phase_tol,phase_condition,phase_singular, ...
            norm(matrix,'fro')); %#ok<AGROW>
    end
    case_info(case_index).name=names(case_index);
    case_info(case_index).times=times;case_info(case_index).ranks=ranks;
    case_info(case_index).accepted=accepted;case_info(case_index).statuses=statuses;
    case_info(case_index).stacked_J=stacked_J;
    case_info(case_index).final_J=final_diagnostic.J;
    case_info(case_index).stacked_V=stacked_V;
    case_info(case_index).final_V=final_diagnostic.V;
    case_info(case_index).stacked_singular_values=stacked_singular;
    case_info(case_index).final_singular_values=final_diagnostic.singular_values;
    case_info(case_index).stacked_correlation=stacked_correlation;
    case_info(case_index).final_correlation=final_diagnostic.column_correlation;
end
subspace_records=make_subspace_records(case_info);
overlap_records=make_overlap_records(case_info);
analysis=struct('window_diagnostics',struct2table(window_records), ...
    'singular_value_summary',struct2table(singular_records), ...
    'parameter_correlation_summary',struct2table(correlation_records), ...
    'phase_information_summary',struct2table(phase_records), ...
    'identifiable_subspace_summary',struct2table(subspace_records), ...
    'subspace_overlap_summary',struct2table(overlap_records), ...
    'case_info',case_info,'parameter_names',r2b.adaptive.parameter_names);
end


function record=empty_window_record()
record=struct('case_name',"",'attempt_index',0,'time_s',NaN, ...
    'hybrid_mode',"",'takeover_mode',"",'window_start_time_s',NaN, ...
    'window_end_time_s',NaN,'window_start_index',0,'window_end_index',0, ...
    'sample_count',0,'logged_rank',0,'reconstructed_rank',0, ...
    'sigma_1',NaN,'sigma_2',NaN,'sigma_3',NaN,'sigma_4',NaN, ...
    'sigma_5',NaN,'sigma_6',NaN,'sigma_7',NaN, ...
    'smallest_singular_value',NaN,'rank_tolerance',NaN, ...
    'condition_number',NaN,'logged_condition_number',NaN, ...
    'status',"",'accepted',false,'theta_before_json',"", ...
    'theta_raw_json',"",'theta_after_json',"", ...
    'normalized_error_before',NaN,'normalized_error_after',NaN, ...
    'hybrid_composition_json',"",'takeover_composition_json',"");
end


function record=empty_singular_record()
record=struct('case_name',"",'matrix_scope',"",'rank',0, ...
    'rank_tolerance',NaN,'condition_number',NaN,'sigma_1',NaN, ...
    'sigma_2',NaN,'sigma_3',NaN,'sigma_4',NaN,'sigma_5',NaN, ...
    'sigma_6',NaN,'sigma_7',NaN,'sigma_min_over_max',NaN);
end


function record=make_singular_record(name,scope,rank_value,tolerance, ...
        condition_number,singular_values)
record=empty_singular_record();record.case_name=name;record.matrix_scope=scope;
record.rank=rank_value;record.rank_tolerance=tolerance;
record.condition_number=condition_number;values=pad_singular_values(singular_values);
for index=1:7,record.(sprintf('sigma_%d',index))=values(index);end
if values(1)>0,record.sigma_min_over_max=values(7)/values(1);end
end


function record=empty_correlation_record()
record=struct('case_name',"",'matrix_scope',"",'parameter_1',"", ...
    'parameter_2',"",'correlation',NaN,'absolute_correlation',NaN, ...
    'high_correlation',false);
end


function records=make_correlation_records(name,scope,correlation,parameters)
records=repmat(empty_correlation_record(),0,1);
for row=1:numel(parameters)
    for column=row+1:numel(parameters)
        record=empty_correlation_record();record.case_name=name;
        record.matrix_scope=scope;record.parameter_1=parameters(row);
        record.parameter_2=parameters(column);
        record.correlation=correlation(row,column);
        record.absolute_correlation=abs(record.correlation);
        record.high_correlation=record.absolute_correlation>=.95;
        records(end+1,1)=record; %#ok<AGROW>
    end
end
end


function record=empty_phase_record()
record=struct('case_name',"",'hybrid_mode',"",'sample_count',0, ...
    'row_count',0,'rank',0,'rank_tolerance',NaN, ...
    'condition_number',NaN,'sigma_1',NaN,'sigma_2',NaN, ...
    'sigma_3',NaN,'sigma_4',NaN,'sigma_5',NaN,'sigma_6',NaN, ...
    'sigma_7',NaN,'frobenius_norm',NaN);
end


function record=make_phase_record(name,phase,samples,rows,rank_value, ...
        tolerance,condition_number,singular_values,frobenius_norm)
record=empty_phase_record();record.case_name=name;record.hybrid_mode=phase;
record.sample_count=samples;record.row_count=rows;record.rank=rank_value;
record.rank_tolerance=tolerance;record.condition_number=condition_number;
values=pad_singular_values(singular_values);
for index=1:7,record.(sprintf('sigma_%d',index))=values(index);end
record.frobenius_norm=frobenius_norm;
end


function values=pad_singular_values(input)
values=zeros(7,1);count=min(7,numel(input));values(1:count)=input(1:count);
end


function value=composition_json(labels)
labels=string(labels(:));names=unique(labels,'stable');counts=zeros(numel(names),1);
for index=1:numel(names),counts(index)=sum(labels==names(index));end
items=struct('name',cell(numel(names),1),'count',cell(numel(names),1));
for index=1:numel(names)
    items(index).name=char(names(index));items(index).count=counts(index);
end
value=string(jsonencode(items));
end


function records=make_subspace_records(case_info)
records=repmat(empty_subspace_record(),0,1);
for case_index=1:numel(case_info)
    for scope=["final_window","stacked_attempt_windows"]
        if scope=="final_window"
            V=case_info(case_index).final_V;
            singular=case_info(case_index).final_singular_values;
            rank_value=r3a_effective_rank(case_info(case_index).final_J);
        else
            V=case_info(case_index).stacked_V;
            singular=case_info(case_index).stacked_singular_values;
            rank_value=r3a_effective_rank(case_info(case_index).stacked_J);
        end
        for direction=1:7
            record=empty_subspace_record();
            record.case_name=case_info(case_index).name;record.matrix_scope=scope;
            record.direction=direction;record.singular_value=singular(direction);
            record.sigma_ratio=singular(direction)/singular(1);
            record.inside_numerical_rank=direction<=rank_value;
            record.mass_scale=V(1,direction);record.lc1_scale=V(2,direction);
            record.lc2_scale=V(3,direction);record.K_scale=V(4,direction);
            record.qrest1_offset_rad=V(5,direction);
            record.qrest2_offset_rad=V(6,direction);
            record.sc_scale=V(7,direction);
            records(end+1,1)=record; %#ok<AGROW>
        end
    end
end
end


function record=empty_subspace_record()
record=struct('case_name',"",'matrix_scope',"",'direction',0, ...
    'singular_value',NaN,'sigma_ratio',NaN,'inside_numerical_rank',false, ...
    'mass_scale',NaN,'lc1_scale',NaN,'lc2_scale',NaN,'K_scale',NaN, ...
    'qrest1_offset_rad',NaN,'qrest2_offset_rad',NaN,'sc_scale',NaN);
end


function records=make_overlap_records(case_info)
records=repmat(empty_overlap_record(),0,1);adverse=case_info(4).final_V(:,1:4);
for case_index=[2 3]
    comparison=case_info(case_index).final_V(:,1:4);
    cosines=svd(adverse'*comparison);
    angles=rad2deg(acos(min(max(cosines,-1),1)));
    record=empty_overlap_record();record.reference_case="adverse";
    record.comparison_case=case_info(case_index).name;record.dimension=4;
    for index=1:4
        record.(sprintf('principal_cosine_%d',index))=cosines(index);
        record.(sprintf('principal_angle_deg_%d',index))=angles(index);
    end
    records(end+1,1)=record; %#ok<AGROW>
end
end


function record=empty_overlap_record()
record=struct('reference_case',"",'comparison_case',"",'dimension',0, ...
    'principal_cosine_1',NaN,'principal_cosine_2',NaN, ...
    'principal_cosine_3',NaN,'principal_cosine_4',NaN, ...
    'principal_angle_deg_1',NaN,'principal_angle_deg_2',NaN, ...
    'principal_angle_deg_3',NaN,'principal_angle_deg_4',NaN);
end
