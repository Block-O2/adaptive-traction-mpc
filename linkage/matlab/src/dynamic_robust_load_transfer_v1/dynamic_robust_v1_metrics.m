function metrics = dynamic_robust_v1_metrics(result)
%DYNAMIC_ROBUST_V1_METRICS Required capability and safety measurements.

dt=result.config.dt;t=result.t;q=result.state(1:2,:);
error=q-result.q_ref;force=result.robot_force_N;
force_norm=vecnorm(force,2,1);force_rate=vecnorm(result.force_rate_N_s,2,1);
finite_dynamic=isfinite(result.dynamic_margin_N);
finite_robust=isfinite(result.robust_static_margin_N);
metrics=struct();
metrics.classification=result.terminal_state;
metrics.completion_time_s=conditional(result.terminal_state=="TASK_COMPLETE",t(end),NaN);
metrics.duration_s=t(end);metrics.final_s=result.task_s(end);
metrics.return_complete=result.task_s(end)>=1-result.config.progress_tolerance;
metrics.rmse_q_deg=rad2deg(sqrt(mean(error.^2,2)));
metrics.max_abs_q_error_deg=rad2deg(max(abs(error),[],2));
metrics.max_tube_deviation_deg=max(rad2deg(max(abs(q-result.q_nominal)- ...
    result.tube_rad,0)),[],2);
metrics.peak_abs_parallel_N=max(abs(force(1,:)));
metrics.peak_abs_perp_N=max(abs(force(2,:)));
metrics.peak_force_norm_N=max(force_norm);
metrics.rms_force_N=sqrt(mean(force_norm.^2));
metrics.peak_force_rate_N_s=max(force_rate);
metrics.force_saturation_fraction=mean(result.force_saturated);
metrics.min_robust_static_margin_N=min(result.robust_static_margin_N(finite_robust));
metrics.min_predicted_dynamic_margin_N=min(result.dynamic_margin_N(finite_dynamic));
finite_realized=isfinite(result.realized_dynamic_margin_N);
metrics.min_realized_dynamic_margin_N=min( ...
    result.realized_dynamic_margin_N(finite_realized));
metrics.peak_realized_dynamic_force_N=max( ...
    vecnorm(result.realized_dynamic_force_N,2,1),[],'omitnan');
metrics.time_robust_below_20N_s=sum(result.robust_static_margin_N<20)*dt;
metrics.time_robust_below_10N_s=sum(result.robust_static_margin_N<10)*dt;
metrics.time_robust_below_5N_s=sum(result.robust_static_margin_N<5)*dt;
metrics.dynamic_residual_rms_Nm=sqrt(mean(result.dynamic_bounded_residual_Nm.^2));
metrics.dynamic_residual_max_Nm=max(result.dynamic_bounded_residual_Nm);
metrics.realized_dynamic_residual_rms_Nm=sqrt(mean( ...
    result.realized_dynamic_bounded_residual_Nm.^2));
metrics.realized_dynamic_residual_max_Nm=max( ...
    result.realized_dynamic_bounded_residual_Nm);
metrics.sigma_min_min=min(result.sigma_min);
metrics.condition_number_max=max(result.condition_number);
metrics.initial_bed_force_N=result.bed_force_N(1);
metrics.peak_bed_force_N=max(result.bed_force_N);
metrics.soft_limit_active_samples=sum(result.soft_limit_active);
metrics.max_soft_limit_torque_Nm=max(abs(result.soft_limit_torque_Nm),[],'all');
metrics.rom_violation_samples=sum(result.rom_violation);
soft_lower=result.plant_parameters.q_min+result.plant_parameters.soft_limit_margin;
soft_upper=result.plant_parameters.q_max-result.plant_parameters.soft_limit_margin;
metrics.min_soft_zone_clearance_deg=rad2deg(min(min(q-soft_lower, ...
    soft_upper-q),[],'all'));
metrics.contact_chatter_count=sum( ...
    result.active_contacts(2:end)~=result.active_contacts(1:end-1));
metrics.takeover_tracking_entered=result.takeover_state.tracking_entered;
metrics.takeover_duration_s=result.takeover_state.tracking_time_s;
metrics.takeover_hold_steps=result.takeover_state.hold_steps;
metrics.takeover_scaled_steps=result.takeover_state.scaled_steps;
metrics.takeover_full_steps=result.takeover_state.full_steps;
metrics.takeover_minimum_lambda=result.takeover_state.minimum_lambda;
takeover_indices=result.takeover_mode~="TRACKING";
if ~any(takeover_indices),takeover_indices(1)=true;end
metrics.takeover_min_q1_deg=rad2deg(min(q(1,takeover_indices)));
metrics.takeover_min_soft_zone_clearance_deg=rad2deg(min(min( ...
    q(:,takeover_indices)-soft_lower, ...
    soft_upper-q(:,takeover_indices)),[],'all'));
metrics.takeover_min_bed_support_N=min(result.bed_force_N(takeover_indices));
metrics.failure_phase=failure_phase(result);
metrics.phase_durations=phase_durations(result.mode,dt);
metrics.state_sequence=unique_sequence(result.mode);
metrics.events=event_metrics(result);
metrics.identifier=identifier_metrics(result);
metrics.safety=safety_metrics(result);
end


function item=safety_metrics(result)
item=struct('enabled',false,'first_intervention_time_s',NaN, ...
    'first_intervention_progress',NaN,'slowdown_count',0, ...
    'slowdown_time_s',0,'hold_count',0,'hold_time_s',0, ...
    'recovery_count',0,'recovery_time_s',0,'recovery_success_count',0, ...
    'total_intervention_time_s',0,'max_reference_deviation_deg',0, ...
    'min_current_clearance_deg',NaN,'min_predicted_clearance_deg',NaN, ...
    'min_q1_soft_clearance_deg',NaN,'min_q2_soft_clearance_deg',NaN, ...
    'force_violation_samples',0);
if ~isfield(result,'r3c_enabled') || ~result.r3c_enabled,return;end
state=result.safety_state_final;q=result.state(1:2,:);
lower=result.plant_parameters.q_min+result.plant_parameters.soft_limit_margin;
upper=result.plant_parameters.q_max-result.plant_parameters.soft_limit_margin;
item.enabled=true;
names={'first_intervention_time_s','first_intervention_progress', ...
    'slowdown_count','slowdown_time_s','hold_count','hold_time_s', ...
    'recovery_count','recovery_time_s','recovery_success_count', ...
    'total_intervention_time_s'};
for index=1:numel(names),item.(names{index})=state.(names{index});end
if state.recovery_count==0
    item.max_reference_deviation_deg=0;
else
    item.max_reference_deviation_deg=rad2deg(max( ...
        result.safety_reference_deviation_rad));
end
item.min_current_clearance_deg=rad2deg(min( ...
    result.safety_current_clearance_rad,[],'omitnan'));
item.min_predicted_clearance_deg=rad2deg(min( ...
    result.safety_predicted_clearance_rad,[],'omitnan'));
item.min_q1_soft_clearance_deg=rad2deg(min([q(1,:)-lower(1); ...
    upper(1)-q(1,:)],[],'all'));
item.min_q2_soft_clearance_deg=rad2deg(min([q(2,:)-lower(2); ...
    upper(2)-q(2,:)],[],'all'));
c=result.config;
item.force_violation_samples=sum(any(result.robot_force_N< ...
    c.u_min(:)-c.bound_tolerance_N | result.robot_force_N> ...
    c.u_max(:)+c.bound_tolerance_N,1));
end


function item=identifier_metrics(result)
item=struct('enabled',false,'accepted_updates',0,'rejected_updates',0, ...
    'solver_failures',0,'first_accepted_time_s',NaN, ...
    'final_raw_theta',nan(7,1),'final_model_theta',nan(7,1), ...
    'true_theta',nan(7,1),'initial_normalized_error',NaN, ...
    'final_normalized_error',NaN,'mean_solve_time_s',NaN, ...
    'max_solve_time_s',NaN,'final_fit_rms',NaN, ...
    'final_rank',NaN,'final_condition_number',NaN);
if ~isfield(result,'adaptive_enabled') || ~result.adaptive_enabled,return;end
state=result.identifier_state;adaptive=result.adaptive_config;
item.enabled=true;item.accepted_updates=state.accepted_updates;
item.rejected_updates=state.rejected_updates;
item.solver_failures=state.solver_failures;
if ~isnan(state.first_accepted_sample) && ...
        state.first_accepted_sample<=numel(result.t)
    item.first_accepted_time_s=result.t(state.first_accepted_sample);
end
item.final_raw_theta=state.theta_raw;
item.final_model_theta=state.theta_model;
item.true_theta=dynamic_robust_v1_adaptive_theta_from_parameters( ...
    result.nominal_parameters,result.plant_parameters);
item.initial_normalized_error=norm((adaptive.theta_nominal-item.true_theta)./ ...
    adaptive.theta_range);
item.final_normalized_error=norm((state.theta_model-item.true_theta)./ ...
    adaptive.theta_range);
item.mean_solve_time_s=state.total_solve_time_s/max(1,state.solve_attempts);
times=result.identifier_solve_time_s(isfinite(result.identifier_solve_time_s));
if ~isempty(times),item.max_solve_time_s=max(times);end
item.final_fit_rms=state.last_fit_rms;item.final_rank=state.last_rank;
item.final_condition_number=state.last_condition_number;
end


function phase=failure_phase(result)
if result.terminal_state=="TASK_COMPLETE"
    phase="NONE";return;
end
if ~result.takeover_state.tracking_entered
    phase="TAKEOVER";return;
end
switch result.mode(end)
    case {"TRANSFER_READY","LOAD_TAKEOVER","LIFTOFF"}
        phase="TRANSFER";
    case {"RECONTACT","LOAD_RETURN","BED_SUPPORTED_RETURN"}
        phase="RETURN";
    otherwise
        phase="TRACKING";
end
end


function output=conditional(condition,yes,no)
if condition,output=yes;else,output=no;end
end


function durations=phase_durations(mode,dt)
names=unique_sequence(mode);durations=struct();
for k=1:numel(names)
    durations.(char(names(k)))=sum(mode==names(k))*dt;
end
end


function sequence=unique_sequence(mode)
keep=[true,mode(2:end)~=mode(1:end-1)];sequence=mode(keep);
end


function events=event_metrics(result)
names=["TRANSFER_READY","SUSPENDED_MOTION","RECONTACT", ...
    "BED_SUPPORTED_RETURN"];
labels=["transfer_ready","liftoff","recontact","load_return_complete"];
events=struct();
for k=1:numel(names)
    index=find(result.mode==names(k),1,'first');
    item=struct('found',~isempty(index),'time_s',NaN,'s',NaN, ...
        'q_deg',[NaN;NaN],'path_q_deg',[NaN;NaN], ...
        'governed_q_deg',[NaN;NaN],'bed_force_N',NaN, ...
        'robot_force_N',[NaN;NaN],'robot_force_norm_N',NaN, ...
        'robust_static_margin_N',NaN,'dynamic_margin_N',NaN, ...
        'dynamic_residual_Nm',NaN,'sigma_min',NaN,'condition_number',NaN, ...
        'contact_count',NaN);
    if ~isempty(index)
        item.time_s=result.t(index);item.s=result.task_s(index);
        item.q_deg=rad2deg(result.state(1:2,index));
        item.path_q_deg=rad2deg(result.q_nominal(:,index));
        item.governed_q_deg=rad2deg(result.q_ref(:,index));
        item.bed_force_N=result.bed_force_N(index);
        item.robot_force_N=result.robot_force_N(:,index);
        item.robot_force_norm_N=norm(result.robot_force_N(:,index));
        item.robust_static_margin_N=result.robust_static_margin_N(index);
        item.dynamic_margin_N=result.dynamic_margin_N(index);
        item.dynamic_residual_Nm=result.dynamic_bounded_residual_Nm(index);
        item.sigma_min=result.sigma_min(index);
        item.condition_number=result.condition_number(index);
        item.contact_count=result.active_contacts(index);
    end
    events.(char(labels(k)))=item;
end
peak_index=find(result.q_nominal(1,:)==max(result.q_nominal(1,:)),1,'first');
events.peak_flexion=struct('found',~isempty(peak_index), ...
    'time_s',result.t(peak_index),'s',result.task_s(peak_index), ...
    'q_deg',rad2deg(result.state(1:2,peak_index)));
events.load_return_duration_s=sum(result.mode=="LOAD_RETURN")*result.config.dt;
events.recontact_force_N=events.recontact.bed_force_N;
end
