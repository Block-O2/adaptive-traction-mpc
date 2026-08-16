function rows = r3a_moderate_event_rows(result,source_name)
%R3A_MODERATE_EVENT_ROWS Key tracking/failure checkpoints for one result.

alignment=r3a_tracking_alignment(result);
indices=alignment.entry_index;
labels="tracking_entry";
if isfinite(alignment.first_outside_index)
    indices(end+1)=alignment.first_outside_index;
    labels(end+1)="first_outside_tube";
end
adaptive_enabled=isfield(result,'adaptive_enabled') && result.adaptive_enabled;
if adaptive_enabled
    update=find(result.identifier_update_accepted,1,'first');
    if ~isempty(update)
        indices(end+1)=update;labels(end+1)="first_accepted_update";
    end
end
indices(end+1)=numel(result.t);labels(end+1)="terminal";
n=numel(indices);source=repmat(string(source_name),n,1);
time_s=zeros(n,1);tracking_time_s=zeros(n,1);progress=zeros(n,1);
q1_deg=zeros(n,1);q2_deg=zeros(n,1);q1_error_deg=zeros(n,1);
q2_error_deg=zeros(n,1);q2_soft_clearance_deg=zeros(n,1);
tube_deviation_deg=zeros(n,1);force_norm_N=zeros(n,1);bed_force_N=zeros(n,1);
dynamic_margin_N=zeros(n,1);parameter_error=nan(n,1);hybrid_mode=strings(n,1);
soft_lower=result.plant_parameters.q_min+ ...
    result.plant_parameters.soft_limit_margin;
truth=[];range=[];
if adaptive_enabled
    truth=dynamic_robust_v1_adaptive_theta_from_parameters( ...
        result.nominal_parameters,result.plant_parameters);
    range=result.adaptive_config.theta_range;
end
for item=1:n
    index=indices(item);error=result.state(1:2,index)-result.q_ref(:,index);
    time_s(item)=result.t(index);
    tracking_time_s(item)=result.t(index)-result.t(alignment.entry_index);
    progress(item)=result.task_s(index);q1_deg(item)=rad2deg(result.state(1,index));
    q2_deg(item)=rad2deg(result.state(2,index));q1_error_deg(item)=rad2deg(error(1));
    q2_error_deg(item)=rad2deg(error(2));
    q2_soft_clearance_deg(item)=rad2deg(result.state(2,index)-soft_lower(2));
    tube_deviation_deg(item)=rad2deg(max(max(abs( ...
        result.state(1:2,index)-result.q_nominal(:,index))- ...
        result.tube_rad(:,index),0)));
    force_norm_N(item)=norm(result.robot_force_N(:,index));
    bed_force_N(item)=result.bed_force_N(index);
    dynamic_margin_N(item)=result.dynamic_margin_N(index);
    hybrid_mode(item)=result.mode(index);
    if adaptive_enabled
        parameter_error(item)=norm(( ...
            result.identifier_theta_model(:,index)-truth)./range);
    elseif isfield(result,'controller_model_parameters') && ...
            isequaln(result.controller_model_parameters,result.plant_parameters)
        parameter_error(item)=0;
    end
end
event=labels(:);
rows=table(source,event,time_s,tracking_time_s,progress,q1_deg,q2_deg, ...
    q1_error_deg,q2_error_deg,q2_soft_clearance_deg,tube_deviation_deg, ...
    force_norm_N,bed_force_N,dynamic_margin_N,parameter_error,hybrid_mode);
end
