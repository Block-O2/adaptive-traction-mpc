function result = simulate_dynamic_robust_load_transfer_v1( ...
        config, nominal, plant, plan, calibration, initialization, ...
        controller_model, adaptive_config)
%SIMULATE_DYNAMIC_ROBUST_LOAD_TRANSFER_V1 Full bed/suspended/bed cycle.
%
% NOMINAL remains the fixed task/supervisor baseline. CONTROLLER_MODEL is
% used only by the existing tracking law, its dynamic-margin prediction, and
% the R1 takeover predictor that already shares that controller model. Only
% the physical contact and RK4 dynamics receive PLANT.

if nargin < 1 || isempty(config), config = dynamic_robust_v1_config(); end
if nargin < 2 || isempty(nominal)
    nominal = human_two_link_v2_parameters(1.72, 75);
end
if nargin < 3 || isempty(plant), plant = nominal; end
if nargin < 4 || isempty(plan)
    plan = hybrid_tube_v1_build_plan(nominal, config);
end
if nargin < 5 || isempty(calibration)
    calibration = bed_supported_v1_calibrate_hip_height(nominal, config);
end
if nargin < 7 || isempty(controller_model), controller_model = nominal; end
adaptive_enabled=nargin>=8 && ~isempty(adaptive_config) && ...
    isfield(adaptive_config,'enabled') && adaptive_config.enabled;
human_two_link_v2_validate_parameters(nominal);
human_two_link_v2_validate_parameters(plant);
human_two_link_v2_validate_parameters(controller_model);
nominal_before = nominal; plant_before = plant;
controller_model_before = controller_model;
if adaptive_enabled
    if ~isequaln(controller_model,nominal)
        error('DynamicRobustV1:AdaptiveMustStartNominal', ...
            'R2B controller_model must start at the nominal parameters.');
    end
    identifier=dynamic_robust_v1_adaptive_initial_state( ...
        nominal,adaptive_config);
else
    identifier=[];
end
uncertainty = bed_supported_v1_registered_uncertainty_set(nominal);
if numel(uncertainty.case_ids) ~= 30
    error('DynamicRobustV1:RegisteredSetChanged', ...
        'The static supervisor requires the exact registered 30-case set.');
end
h_hip = calibration.h_hip_m;
if nargin < 6 || isempty(initialization)
    initialization = dynamic_robust_v1_initial_admissibility( ...
        nominal, plant, calibration, config, controller_model);
end
if ~initialization.pass
    error('DynamicRobustV1:InitialAdmissibilityFailed', ...
        'The case does not satisfy the explicit initial-admissibility contract.');
end
q_start = initialization.q_rad;
n_max = floor(config.max_time_s/config.dt)+1;
t = (0:n_max-1)*config.dt;
x = zeros(4,n_max); x(:,1) = [q_start;zeros(2,1)];
u_previous = min(max(initialization.true_equilibrium_force_N, ...
    config.u_min), config.u_max);
takeover = dynamic_robust_v1_safe_takeover_initial_state(u_previous);
supervisor_stride = max(1, round(config.supervisor_period_s/config.dt));
recontact_search_stride = max(1,round( ...
    config.recontact_search_period_s/config.dt));

manager = dynamic_robust_v1_initial_state();
progress = struct('s',0,'s_dot',0,'s_ddot',0);
transition_q = q_start;
transfer_target = struct('found',false,'q',q_start,'path_q',q_start, ...
    'tube_rad',zeros(2,1),'robust',[],'bed',[],'candidate_count',0);
recontact_target = struct('found',false,'q',q_start,'path_q',q_start, ...
    'tube_rad',zeros(2,1),'robust',[],'dynamic',[],'bed',[], ...
    'candidate_count',0,'start_q',q_start,'start_mode_time_s',0);
previous_force_rate_ok = true; previous_force_saturated = false;

q_ref=zeros(2,n_max);dq_ref=zeros(2,n_max);ddq_ref=zeros(2,n_max);
q_nominal=zeros(2,n_max);tube_rad=zeros(2,n_max);task_s=zeros(1,n_max);
mode=strings(1,n_max);classification=strings(1,n_max);
robot_force=zeros(2,n_max);bed_force=zeros(1,n_max);bed_credit=zeros(1,n_max);
robust_static_margin=nan(1,n_max);robust_required=nan(1,n_max);
robust_worst_case=strings(1,n_max);nominal_static_force=nan(2,n_max);
dynamic_margin=nan(1,n_max);dynamic_exact_force=nan(2,n_max);
dynamic_bounded_force=nan(2,n_max);dynamic_residual=nan(1,n_max);
realized_dynamic_margin=nan(1,n_max);realized_dynamic_force=nan(2,n_max);
realized_dynamic_residual=nan(1,n_max);
controller_residual=nan(2,n_max);balance_residual=nan(2,n_max);
force_rate=zeros(2,n_max);force_saturated=false(1,n_max);
slew_saturated=false(1,n_max);sigma_min=nan(1,n_max);condition_number=nan(1,n_max);
active_contacts=zeros(1,n_max);max_penetration=zeros(1,n_max);
soft_limit_active=false(1,n_max);soft_limit_torque=zeros(2,n_max);
rom_violation=false(1,n_max);inside_tube=false(1,n_max);
recovery_active=false(1,n_max);progress_enabled=false(1,n_max);
event_name=strings(1,n_max);event_name(:)="";
takeover_mode=strings(1,n_max);takeover_reason=strings(1,n_max);
takeover_nominal_force=nan(2,n_max);takeover_candidate_force=nan(2,n_max);
takeover_lambda=nan(1,n_max);takeover_force_gap=nan(1,n_max);
takeover_lambda_components=nan(2,n_max);
takeover_soft_margin=nan(2,n_max);takeover_predicted_margin=nan(2,n_max);
identifier_theta_raw=nan(7,n_max);identifier_theta_model=nan(7,n_max);
identifier_status=strings(1,n_max);identifier_status(:)="NOT_ENABLED";
identifier_update_attempted=false(1,n_max);
identifier_update_accepted=false(1,n_max);
identifier_fit_rms=nan(1,n_max);identifier_current_fit_rms=nan(1,n_max);
identifier_rank=nan(1,n_max);identifier_condition_number=nan(1,n_max);
identifier_solve_time=nan(1,n_max);identifier_accepted_count=zeros(1,n_max);
identifier_rejected_count=zeros(1,n_max);identifier_solver_failures=zeros(1,n_max);
last_robust=[]; last_index=n_max;

for index=1:n_max
    now=t(index); q=x(1:2,index); dq=x(3:4,index);
    if adaptive_enabled
        identifier_theta_raw(:,index)=identifier.theta_raw;
        identifier_theta_model(:,index)=identifier.theta_model;
        identifier_accepted_count(index)=identifier.accepted_updates;
        identifier_rejected_count(index)=identifier.rejected_updates;
        identifier_solver_failures(index)=identifier.solver_failures;
        if index==1,identifier_status(index)=identifier.last_status;end
    end
    old_mode=manager.mode;
    reference = reference_for_mode(manager, progress, transition_q, ...
        transfer_target, recontact_target, plan, config);
    nominal_path = hybrid_tube_v1_task_path(progress.s);
    tube_now = hybrid_tube_v1_tube_schedule(progress.s, ...
        nominal_path.q, config);
    bed = bed_supported_v1_contact(q,dq,h_hip,plant,config);
    [~, passive] = human_two_link_v2_passive_torque(q,dq,plant);
    if isempty(last_robust) || mod(index-1,supervisor_stride)==0
        last_robust = bed_supported_v1_robust_hold_point(q, nominal, ...
            uncertainty, config.force_bound_N, ...
            config.svd_relative_tolerance);
    end
    robust = last_robust;
    robust_margin_now = config.force_bound_N- ...
        robust.worst_required_force_N;
    dynamic = dynamic_robust_v1_dynamic_margin(q,dq,reference.q, ...
        reference.dq,reference.ddq,controller_model,config);
    realized_dynamic = dynamic_robust_v1_dynamic_margin(q,dq,reference.q, ...
        reference.dq,reference.ddq,plant,config);
    return_phase = nominal_path.phase=="return" || ...
        nominal_path.phase=="final_hold";
    task_at_end = progress.s >= 1-config.progress_tolerance;
    terminal_error = q-q_start;
    task_complete = task_at_end && ...
        norm(terminal_error,Inf)<=config.terminal_position_tolerance_rad && ...
        norm(dq,Inf)<=config.return_terminal_velocity_tolerance_rad_s && ...
        bed.total_normal_force_N>=config.contact_force_threshold_N;
    static_residual_ok = robust.nominal.exact_torque_residual_norm_Nm <= ...
        config.plan_residual_tolerance_Nm;
    no_soft = ~any(passive.soft.active);
    bed_supported = bed.total_normal_force_N >= ...
        config.contact_force_threshold_N;
    bed_absent = bed.total_normal_force_N < ...
        config.contact_force_threshold_N;
    if manager.mode=="SUSPENDED_MOTION" && return_phase && bed_absent && ...
            ~recontact_target.found && ...
            mod(index-1,recontact_search_stride)==0
        candidate=dynamic_robust_v1_select_recontact_posture( ...
            progress.s,u_previous,nominal,uncertainty,h_hip,config);
        if candidate.found
            candidate.start_q=q;
            candidate.start_mode_time_s=manager.mode_time_s;
            recontact_target=candidate;
            reference=reference_for_mode(manager,progress,transition_q, ...
                transfer_target,recontact_target,plan,config);
            dynamic=dynamic_robust_v1_dynamic_margin(q,dq,reference.q, ...
                reference.dq,reference.ddq,controller_model,config);
        end
    end
    dynamic_ok = dynamic.margin_N > 0 && dynamic.exact_feasible && ...
        dynamic.bounded_residual_norm_Nm <= ...
        config.dynamic_residual_tolerance_Nm;
    in_tube = all(abs(q-nominal_path.q)<=tube_now+ ...
        config.event_position_tolerance_rad);
    signals = struct();
    signals.robust_static_margin_N = robust_margin_now;
    signals.bed_supported = bed_supported;
    signals.bed_absent = bed_absent;
    signals.entry_ready = robust_margin_now >= ...
        config.robust_entry_trigger_N && bed_supported && no_soft && ...
        static_residual_ok && dynamic_ok && previous_force_rate_ok && ...
        in_tube && takeover.tracking_entered;
    signals.takeover_feasible = robust_margin_now >= ...
        config.robust_entry_trigger_N-config.robust_entry_hysteresis_N && ...
        dynamic_ok && no_soft && static_residual_ok && in_tube;
    signals.liftoff_ready = bed_absent && robust_margin_now > 0 && ...
        dynamic_ok && no_soft && previous_force_rate_ok && ...
        ~previous_force_saturated && in_tube;
    sample = hybrid_tube_v1_plan_sample(plan,progress.s);
    signals.suspended_feasible = robust_margin_now > 0 && dynamic_ok && ...
        no_soft && (sample.hold_feasible || recontact_target.found) && in_tube;
    signals.prepare_recontact = recontact_target.found && return_phase;
    signals.returning = return_phase;
    signals.return_phase_reached = return_phase;
    signals.task_at_end = task_at_end;
    signals.task_complete = task_complete;
    signals.force_bound_violation = any(abs(u_previous)> ...
        config.force_bound_N+config.bound_tolerance_N);
    signals.rom_violation = any(q<plant.q_min-config.rom_tolerance_rad | ...
        q>plant.q_max+config.rom_tolerance_rad);
    signals.soft_limit_violation = any(passive.soft.active) && ...
        norm(passive.soft_rhs,Inf)>config.soft_torque_tolerance_Nm;

    [manager, action] = dynamic_robust_v1_manager_step( ...
        manager,signals,config);
    if manager.mode~=old_mode
        transition_q=q;
        event_name(index)=manager.mode;
        if manager.mode=="TRANSFER_READY"
            transfer_target=dynamic_robust_v1_select_transfer_posture( ...
                progress.s,u_previous,nominal,uncertainty,h_hip,config);
            if ~transfer_target.found
                manager.classification="LOAD_TAKEOVER_FAILED";
            end
        end
    end
    reference = reference_for_mode(manager, progress, transition_q, ...
        transfer_target, recontact_target, plan, config);
    dynamic = dynamic_robust_v1_dynamic_margin(q,dq,reference.q, ...
        reference.dq,reference.ddq,controller_model,config);
    realized_dynamic = dynamic_robust_v1_dynamic_margin(q,dq,reference.q, ...
        reference.dq,reference.ddq,plant,config);
    [u_candidate,controller]=bed_supported_v1_robot_controller(q,dq,reference.q, ...
        reference.dq,reference.ddq,bed.generalized_torque_Nm,u_previous, ...
        controller_model,config,1,action.bed_credit);
    [u,takeover,takeover_details]=dynamic_robust_v1_safe_takeover_step( ...
        takeover,q,dq,u_previous,u_candidate,controller.u_desired_N, ...
        bed.generalized_torque_Nm,controller_model,config);
    startup_progress_enabled=action.progress_enabled && ...
        ~ismember(takeover.mode,["TAKEOVER","TAKEOVER_ABORT"]);
    controller.torque_residual_Nm=controller.mapping.A*u- ...
        controller.tau_robot_desired_Nm;
    controller.force_rate_N_s=(u-u_previous)/config.dt;
    controller.force_saturated=any(abs(u-config.u_min(:))<= ...
        config.bound_tolerance_N | abs(u-config.u_max(:))<= ...
        config.bound_tolerance_N);
    controller.slew_saturated=any(abs(controller.force_rate_N_s)>= ...
        config.du_max(:)-1e-8);
    if takeover.timed_out
        manager.classification="SAFE_TAKEOVER_TIMEOUT";
    end
    [~,dynamics]=bed_supported_v1_dynamics(x(:,index),u,h_hip,plant,config);

    q_ref(:,index)=reference.q;dq_ref(:,index)=reference.dq;
    ddq_ref(:,index)=reference.ddq;q_nominal(:,index)=nominal_path.q;
    tube_rad(:,index)=tube_now;task_s(index)=progress.s;mode(index)=manager.mode;
    classification(index)=manager.classification;robot_force(:,index)=u;
    bed_force(index)=bed.total_normal_force_N;bed_credit(index)=action.bed_credit;
    robust_static_margin(index)=robust_margin_now;
    robust_required(index)=robust.worst_required_force_N;
    robust_worst_case(index)=robust.worst_case_id;
    nominal_static_force(:,index)=robust.nominal.force_local_N;
    dynamic_margin(index)=dynamic.margin_N;
    dynamic_exact_force(:,index)=dynamic.exact_force_N;
    dynamic_bounded_force(:,index)=dynamic.bounded_force_N;
    dynamic_residual(index)=dynamic.bounded_residual_norm_Nm;
    realized_dynamic_margin(index)=realized_dynamic.margin_N;
    realized_dynamic_force(:,index)=realized_dynamic.exact_force_N;
    realized_dynamic_residual(index)= ...
        realized_dynamic.bounded_residual_norm_Nm;
    controller_residual(:,index)=controller.torque_residual_Nm;
    balance_residual(:,index)=dynamics.balance_residual_Nm;
    force_rate(:,index)=controller.force_rate_N_s;
    force_saturated(index)=controller.force_saturated;
    slew_saturated(index)=controller.slew_saturated;
    sigma_min(index)=dynamics.mapping.sigma_min;
    condition_number(index)=dynamics.mapping.condition_number;
    active_contacts(index)=sum(bed.active);
    max_penetration(index)=max(bed.penetration_m);
    soft_limit_active(index)=any(passive.soft.active);
    soft_limit_torque(:,index)=passive.soft_rhs;
    rom_violation(index)=signals.rom_violation;inside_tube(index)=in_tube;
    recovery_active(index)=action.pause_unloading || ...
        ~startup_progress_enabled || ...
        (~action.progress_enabled && manager.mode=="SUSPENDED_MOTION");
    progress_enabled(index)=startup_progress_enabled;
    takeover_mode(index)=takeover_details.mode;
    takeover_reason(index)=takeover_details.reason;
    takeover_nominal_force(:,index)=takeover_details.nominal_desired_force_N;
    takeover_candidate_force(:,index)= ...
        takeover_details.nominal_candidate_force_N;
    takeover_lambda(index)=takeover_details.lambda;
    takeover_lambda_components(:,index)=takeover_details.lambda_components;
    takeover_force_gap(index)=takeover_details.force_gap_N;
    takeover_soft_margin(:,index)=takeover_details.soft_margin_rad;
    takeover_predicted_margin(:,index)= ...
        takeover_details.predicted_soft_margin_rad;

    if manager.classification~="RUNNING"
        last_index=index; break;
    end
    if index<n_max
        held_force=u;
        rhs=@(~,state)bed_supported_v1_dynamics( ...
            state,held_force,h_hip,plant,config);
        x(:,index+1)=human_two_link_v2_rk4_step( ...
            rhs,now,x(:,index),config.dt);
        if any(~isfinite(x(:,index+1)))
            manager.classification="ABORTED";last_index=index;break;
        end
        progress=dynamic_robust_v1_advance_progress( ...
            progress,startup_progress_enabled,config);
        if adaptive_enabled
            [identifier,identifier_details]= ...
                dynamic_robust_v1_adaptive_add_transition( ...
                identifier,x(:,index),u,x(:,index+1),index+1,nominal, ...
                h_hip,config,adaptive_config,true);
            controller_model=identifier.controller_model;
            identifier_status(index+1)=identifier_details.status;
            identifier_update_attempted(index+1)= ...
                identifier_details.attempted;
            identifier_update_accepted(index+1)=identifier_details.accepted;
            identifier_fit_rms(index+1)=identifier_details.fit_rms;
            identifier_current_fit_rms(index+1)= ...
                identifier_details.current_fit_rms;
            identifier_rank(index+1)=identifier_details.rank;
            identifier_condition_number(index+1)= ...
                identifier_details.condition_number;
            identifier_solve_time(index+1)=identifier_details.solve_time_s;
        end
        u_previous=u;
        previous_force_rate_ok=max(abs(controller.force_rate_N_s)) <= ...
            config.force_rate_tolerance_N_s;
        previous_force_saturated=controller.force_saturated;
    end
end
if manager.classification=="RUNNING",manager.classification="ABORTED";end
if ~isequaln(nominal,nominal_before) || ~isequaln(plant,plant_before) || ...
        (~adaptive_enabled && ~isequaln(controller_model,controller_model_before))
    error('DynamicRobustV1:ParameterMutation', ...
        'Controller or plant parameter input was mutated.');
end

fields={'t','state','q_ref','dq_ref','ddq_ref','q_nominal','tube_rad', ...
    'task_s','mode','classification','robot_force_N','bed_force_N', ...
    'bed_credit','robust_static_margin_N','robust_required_N', ...
    'robust_worst_case','nominal_static_force_N','dynamic_margin_N', ...
    'dynamic_exact_force_N','dynamic_bounded_force_N', ...
    'dynamic_bounded_residual_Nm','realized_dynamic_margin_N', ...
    'realized_dynamic_force_N', ...
    'realized_dynamic_bounded_residual_Nm', ...
    'controller_residual_Nm','balance_residual_Nm','force_rate_N_s', ...
    'force_saturated', ...
    'slew_saturated','sigma_min','condition_number','active_contacts', ...
    'max_penetration_m','soft_limit_active','soft_limit_torque_Nm', ...
    'rom_violation','inside_tube','recovery_active','progress_enabled', ...
    'event_name','takeover_mode','takeover_reason', ...
    'takeover_nominal_force_N','takeover_candidate_force_N', ...
    'takeover_lambda','takeover_lambda_components', ...
    'takeover_force_gap_N','takeover_soft_margin_rad', ...
    'takeover_predicted_soft_margin_rad','identifier_theta_raw', ...
    'identifier_theta_model','identifier_status', ...
    'identifier_update_attempted','identifier_update_accepted', ...
    'identifier_fit_rms','identifier_current_fit_rms','identifier_rank', ...
    'identifier_condition_number','identifier_solve_time_s', ...
    'identifier_accepted_count','identifier_rejected_count', ...
    'identifier_solver_failures'};
values={t,x,q_ref,dq_ref,ddq_ref,q_nominal,tube_rad,task_s,mode, ...
    classification,robot_force,bed_force,bed_credit,robust_static_margin, ...
    robust_required,robust_worst_case,nominal_static_force,dynamic_margin, ...
    dynamic_exact_force,dynamic_bounded_force,dynamic_residual, ...
    realized_dynamic_margin,realized_dynamic_force, ...
    realized_dynamic_residual, ...
    controller_residual,balance_residual,force_rate,force_saturated, ...
    slew_saturated,sigma_min,condition_number,active_contacts,max_penetration, ...
    soft_limit_active,soft_limit_torque,rom_violation,inside_tube, ...
    recovery_active,progress_enabled,event_name,takeover_mode, ...
    takeover_reason,takeover_nominal_force,takeover_candidate_force, ...
    takeover_lambda,takeover_lambda_components,takeover_force_gap, ...
    takeover_soft_margin, ...
    takeover_predicted_margin,identifier_theta_raw,identifier_theta_model, ...
    identifier_status,identifier_update_attempted, ...
    identifier_update_accepted,identifier_fit_rms, ...
    identifier_current_fit_rms,identifier_rank, ...
    identifier_condition_number,identifier_solve_time, ...
    identifier_accepted_count,identifier_rejected_count, ...
    identifier_solver_failures};
result=struct();
for k=1:numel(fields)
    value=values{k};
    if ismatrix(value) && size(value,2)==n_max
        result.(fields{k})=value(:,1:last_index);
    else
        result.(fields{k})=value;
    end
end
result.terminal_state=manager.classification;
result.h_hip_m=h_hip;result.calibration=calibration;
result.transfer_target=transfer_target;result.config=config;
result.recontact_target=recontact_target;
result.nominal_parameters=nominal;result.plant_parameters=plant;
result.controller_model_parameters=controller_model;
result.controller_model_initial_parameters=controller_model_before;
result.adaptive_enabled=adaptive_enabled;
if adaptive_enabled,result.adaptive_config=adaptive_config;
else,result.adaptive_config=struct();end
result.identifier_state=identifier;
result.initial_admissibility=initialization;
result.takeover_state=takeover;
result.uncertainty=uncertainty;result.plan=plan;
result.metrics=dynamic_robust_v1_metrics(result);
end


function reference=reference_for_mode(manager,progress,transition_q, ...
        transfer_target,recontact_target,plan,config)
nominal=hybrid_tube_v1_task_path(progress.s);
switch manager.mode
    case "TRANSFER_READY"
        reference=blend_reference(transition_q,transfer_target.q, ...
            manager.mode_time_s,config.transfer_ready_duration_s);
    case "LOAD_TAKEOVER"
        moving_progress=progress;
        if manager.takeover_paused
            moving_progress.s_dot=0;moving_progress.s_ddot=0;
        end
        reference=dynamic_robust_v1_moving_blend_reference( ...
            transition_q,transfer_target.path_q,nominal,moving_progress, ...
            manager.takeover_time_s,config.load_takeover_duration_s);
    case "LIFTOFF"
        reference=fixed_reference(transition_q);
    case "SUSPENDED_MOTION"
        governed=hybrid_tube_v1_plan_sample(plan,progress.s);
        if recontact_target.found
            elapsed=max(0,manager.mode_time_s- ...
                recontact_target.start_mode_time_s);
            reference=blend_reference(recontact_target.start_q, ...
                recontact_target.q,elapsed,config.transfer_ready_duration_s);
        elseif manager.mode_time_s<config.suspended_blend_duration_s
            reference=blend_reference(transition_q,governed.q, ...
                manager.mode_time_s,config.suspended_blend_duration_s);
        else
            reference=struct('q',governed.q,'dq', ...
                governed.q_s*progress.s_dot,'ddq', ...
                governed.q_ss*progress.s_dot^2+ ...
                governed.q_s*progress.s_ddot);
        end
    case {"RECONTACT","LOAD_RETURN","BED_SUPPORTED_RETURN"}
        if recontact_target.found
            return_path_q=recontact_target.path_q;
        else
            return_path_q=nominal.q;
        end
        reference=dynamic_robust_v1_return_reference(manager.mode, ...
            transition_q,return_path_q,nominal,progress, ...
            manager.mode_time_s,config.load_return_duration_s);
    otherwise
        reference=struct('q',nominal.q,'dq',nominal.q_s*progress.s_dot, ...
            'ddq',nominal.q_ss*progress.s_dot^2+ ...
            nominal.q_s*progress.s_ddot);
end
end


function reference=fixed_reference(q)
reference=struct('q',q,'dq',zeros(2,1),'ddq',zeros(2,1));
end


function reference=blend_reference(q0,q1,elapsed,duration)
r=min(max(elapsed/duration,0),1);g=10*r^3-15*r^4+6*r^5;
gd=(30*r^2-60*r^3+30*r^4)/duration;
gdd=(60*r-180*r^2+120*r^3)/duration^2;delta=q1-q0;
reference=struct('q',q0+delta*g,'dq',delta*gd,'ddq',delta*gdd);
end
