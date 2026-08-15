function result = simulate_bed_supported_load_transfer_v1(config, p, plan, calibration)
%SIMULATE_BED_SUPPORTED_LOAD_TRANSFER_V1 Eight-phase load-transfer rollout.

if nargin < 3 || isempty(plan), plan = hybrid_tube_v1_build_plan(p, config); end
if nargin < 4 || isempty(calibration)
    calibration = bed_supported_v1_calibrate_hip_height(p, config);
end
h_hip = calibration.h_hip_m;
q_start = deg2rad([5;10]);
plan_start = hybrid_tube_v1_plan_sample(plan,0);
preposition = bed_supported_v1_preposition_target( ...
    p,config,h_hip,calibration.robot_force_N);
n_max = floor(config.max_time_s/config.dt)+1;
t = (0:n_max-1)*config.dt;
x = zeros(4,n_max); x(:,1) = [q_start;zeros(2,1)];
u_previous = min(max(calibration.robot_force_N,config.u_min),config.u_max);

hybrid_mode = "BED_SUPPORT"; terminal_state = "RUNNING";
phase_start_time = 0; phase_start_q = q_start;
contact_stable_time = 0; feasible_stable_time = 0;
preposition_return_count = 0;
manager = struct('s',0,'s_dot',0,'s_ddot',0,'pause_time',0, ...
    'status',"RUNNING",'previous_force',plan_start.force_local);

q_reference=zeros(2,n_max);dq_reference=zeros(2,n_max);ddq_reference=zeros(2,n_max);
q_nominal=zeros(2,n_max);tube_rad=zeros(2,n_max);progress=zeros(1,n_max);
mode=strings(1,n_max);robot_force=zeros(2,n_max);bed_force=zeros(1,n_max);
robot_only_force=zeros(2,n_max);robot_only_residual=nan(1,n_max);
robot_only_force_margin=nan(1,n_max);robot_only_feasible=false(1,n_max);
robot_load_share=zeros(1,n_max);bed_torque=zeros(2,n_max);robot_torque=zeros(2,n_max);
balance_residual=zeros(2,n_max);controller_residual=zeros(2,n_max);
force_rate=zeros(2,n_max);sigma_min=zeros(1,n_max);condition_number=zeros(1,n_max);
active_contacts=zeros(1,n_max);max_penetration=zeros(1,n_max);
soft_limit_active=false(1,n_max);rom_violation=false(1,n_max);
robot_authority=ones(1,n_max);bed_credit=ones(1,n_max);
last_index=n_max;

for index=1:n_max
    now=t(index);q=x(1:2,index);dq=x(3:4,index);elapsed=now-phase_start_time;
    bed=bed_supported_v1_contact(q,dq,h_hip,p,config);
    hold_check=bed_supported_v1_robot_only_hold(q,p,config);
    witness=hold_check.point;
    robot_only_force(:,index)=witness.force_local;
    robot_only_residual(index)=witness.bounded_residual_norm(1);
    robot_only_force_margin(index)=config.force_bound_N-max(abs(witness.force_local));
    [~,soft_details]=human_two_link_v2_passive_torque(q,dq,p);
    nominal0=hybrid_tube_v1_task_path(0);
    tube0=hybrid_tube_v1_tube_schedule(0,nominal0.q,config);
    inside_initial_tube=all(abs(q-nominal0.q)<=tube0+deg2rad(0.05));
    robust_hold=hold_check.feasible && robot_only_force_margin(index)>= ...
        config.preposition_force_margin_N && ...
        robot_only_residual(index)<=config.plan_residual_tolerance_Nm && ...
        ~any(soft_details.soft.active) && inside_initial_tube && ...
        all(q>=p.q_min) && all(q<=p.q_max) && all(isfinite(witness.force_local));
    robot_only_feasible(index)=robust_hold;
    if bed.total_normal_force_N>=config.contact_force_threshold_N
        contact_stable_time=contact_stable_time+config.dt;
    else
        contact_stable_time=0;
    end

    switch hybrid_mode
        case "BED_SUPPORT"
            reference=fixed_reference(q_start);reference.nominal_q=q_start;
            if contact_stable_time>=config.contact_stable_duration_s
                if preposition.found
                    [hybrid_mode,phase_start_time,phase_start_q]= ...
                        transition("SUPPORTED_PREPOSITION",now,q);
                    feasible_stable_time=0;
                else
                    terminal_state="PREPOSITION_INFEASIBLE";
                end
            end
        case "SUPPORTED_PREPOSITION"
            reference=transition_reference(phase_start_q,preposition.q, ...
                elapsed,config.preposition_duration_s);
            reference.nominal_q=q_start;
            if elapsed>=config.preposition_duration_s && ...
                    norm(q-preposition.q,inf)<= ...
                    config.preposition_position_tolerance_rad && ...
                    robust_hold && contact_stable_time>= ...
                    config.contact_stable_duration_s
                feasible_stable_time=feasible_stable_time+config.dt;
            else
                feasible_stable_time=0;
            end
            if feasible_stable_time>=config.preposition_feasible_hold_s
                [hybrid_mode,phase_start_time,phase_start_q]= ...
                    transition("LOAD_TAKEOVER",now,q);
            elseif elapsed>=config.preposition_timeout_s || ...
                    (elapsed>config.dt && bed.total_normal_force_N< ...
                    config.contact_force_threshold_N)
                terminal_state="PREPOSITION_INFEASIBLE";
            end
        case "LOAD_TAKEOVER"
            reference=fixed_reference(preposition.q);reference.nominal_q=q_start;
            bed_credit(index)=1-smooth_progress(elapsed/config.load_takeover_duration_s);
            if ~robust_hold
                if preposition.found && preposition_return_count<1 && ...
                        bed.total_normal_force_N>=config.contact_force_threshold_N
                    preposition_return_count=preposition_return_count+1;
                    [hybrid_mode,phase_start_time,phase_start_q]= ...
                        transition("SUPPORTED_PREPOSITION",now,q);
                else
                    terminal_state="PREPOSITION_INFEASIBLE";
                end
            elseif elapsed>=config.load_takeover_duration_s
                [hybrid_mode,phase_start_time,phase_start_q]= ...
                    transition("LIFTOFF",now,q);
            end
        case "LIFTOFF"
            reference=fixed_reference(preposition.q);reference.nominal_q=q_start;
            bed_credit(index)=0;
            if ~robust_hold
                if preposition.found && preposition_return_count<1 && ...
                        bed.total_normal_force_N>=config.contact_force_threshold_N
                    preposition_return_count=preposition_return_count+1;
                    [hybrid_mode,phase_start_time,phase_start_q]= ...
                        transition("SUPPORTED_PREPOSITION",now,q);
                else
                    terminal_state="LIFTOFF_INFEASIBLE";
                end
            elseif elapsed>=config.liftoff_timeout_s
                terminal_state="LIFTOFF_INFEASIBLE";
            end
        case "SUSPENDED_MOTION"
            bed_credit(index)=0;
            [manager,managed]=hybrid_tube_v1_manager_step(manager,plan,q,dq,p,config);
            reference=struct('q',managed.q,'dq',managed.dq,'ddq',managed.ddq, ...
                'nominal_q',managed.sample.nominal_q);
            if manager.status~="RUNNING" && manager.status~="TASK_COMPLETE"
                terminal_state="SUSPENDED_INFEASIBLE";
            elseif manager.s>=config.recontact_progress_threshold && ...
                    bed.total_normal_force_N>=config.contact_force_threshold_N
                [hybrid_mode,phase_start_time,phase_start_q]= ...
                    transition("RECONTACT",now,q);contact_stable_time=config.dt;
            elseif manager.status=="TASK_COMPLETE"
                terminal_state="RECONTACT_FAILED";
            end
        case "RECONTACT"
            reference=transition_reference(phase_start_q,q_start,elapsed, ...
                config.load_return_duration_s);reference.nominal_q=q_start;
            bed_credit(index)=smooth_progress(elapsed/config.load_return_duration_s);
            if contact_stable_time>=config.contact_stable_duration_s
                [hybrid_mode,phase_start_time,phase_start_q]= ...
                    transition("LOAD_RETURN",now,q);
            elseif elapsed>=2*config.load_return_duration_s
                terminal_state="RECONTACT_FAILED";
            end
        case "LOAD_RETURN"
            reference=fixed_reference(q_start);reference.nominal_q=q_start;
            alpha=smooth_progress(elapsed/config.load_return_duration_s);
            robot_authority(index)=1-0.8*alpha;bed_credit(index)=1;
            if elapsed>=config.load_return_duration_s
                [hybrid_mode,phase_start_time,phase_start_q]= ...
                    transition("RELEASE",now,q);
            end
        case "RELEASE"
            reference=fixed_reference(q_start);reference.nominal_q=q_start;
            alpha=smooth_progress(elapsed/config.release_duration_s);
            robot_authority(index)=0.2*(1-alpha);bed_credit(index)=1;
            if elapsed>=config.release_duration_s
                if contact_stable_time>=config.contact_stable_duration_s
                    terminal_state="TASK_COMPLETE";
                else
                    terminal_state="LOAD_RETURN_FAILED";
                end
            end
        otherwise
            terminal_state="ABORTED";reference=fixed_reference(q);reference.nominal_q=q;
    end
    if hybrid_mode=="SUSPENDED_MOTION"
        sample=hybrid_tube_v1_plan_sample(plan,manager.s);tube_now=sample.tube_rad;
    else
        tube_now=tube0;
    end

    [u,controller]=bed_supported_v1_robot_controller(q,dq,reference.q, ...
        reference.dq,reference.ddq,bed.generalized_torque_Nm,u_previous,p, ...
        config,robot_authority(index),bed_credit(index));
    [~,dynamics]=bed_supported_v1_dynamics(x(:,index),u,h_hip,p,config);

    % Liftoff is a guarded event, evaluated with current force and rate data.
    force_rate_ok=max(abs(controller.force_rate_N_s))<=max(config.du_max)+1e-8;
    liftoff_guard=bed.total_normal_force_N<=config.contact_force_threshold_N && ...
        robust_hold && ~controller.force_saturated && force_rate_ok && ...
        ~any(dynamics.passive.soft.active) && ...
        norm(controller.torque_residual_Nm)<=config.residual_tolerance_Nm;
    if hybrid_mode=="LIFTOFF" && liftoff_guard
        [hybrid_mode,phase_start_time,phase_start_q]= ...
            transition("SUSPENDED_MOTION",now,q);
        manager.status="RUNNING";
    end

    q_reference(:,index)=reference.q;dq_reference(:,index)=reference.dq;
    ddq_reference(:,index)=reference.ddq;q_nominal(:,index)=reference.nominal_q;
    tube_rad(:,index)=tube_now;progress(index)=manager.s;mode(index)=hybrid_mode;
    robot_force(:,index)=u;bed_force(index)=bed.total_normal_force_N;
    robot_load_share(index)=norm(dynamics.tau_robot_Nm)/max( ...
        norm(dynamics.tau_robot_Nm)+norm(dynamics.tau_bed_Nm),eps);
    bed_torque(:,index)=dynamics.tau_bed_Nm;robot_torque(:,index)=dynamics.tau_robot_Nm;
    balance_residual(:,index)=dynamics.balance_residual_Nm;
    controller_residual(:,index)=controller.torque_residual_Nm;
    force_rate(:,index)=controller.force_rate_N_s;sigma_min(index)=dynamics.mapping.sigma_min;
    condition_number(index)=dynamics.mapping.condition_number;
    active_contacts(index)=sum(bed.active);max_penetration(index)=max(bed.penetration_m);
    soft_limit_active(index)=any(dynamics.passive.soft.active);
    rom_violation(index)=any(q<p.q_min-config.rom_tolerance_rad | ...
        q>p.q_max+config.rom_tolerance_rad);

    if terminal_state~="RUNNING",last_index=index;break;end
    if index<n_max
        held_force=u;rhs=@(~,state)bed_supported_v1_dynamics( ...
            state,held_force,h_hip,p,config);
        x(:,index+1)=human_two_link_v2_rk4_step(rhs,now,x(:,index),config.dt);
        if any(~isfinite(x(:,index+1)))
            terminal_state="ABORTED";last_index=index;break;
        end
        u_previous=u;
    end
end
if terminal_state=="RUNNING",terminal_state="ABORTED";end

result=struct('t',t(1:last_index),'state',x(:,1:last_index), ...
 'q_ref',q_reference(:,1:last_index),'dq_ref',dq_reference(:,1:last_index), ...
 'ddq_ref',ddq_reference(:,1:last_index),'q_nominal',q_nominal(:,1:last_index), ...
 'tube_rad',tube_rad(:,1:last_index),'progress',progress(1:last_index), ...
 'mode',mode(1:last_index),'robot_force_N',robot_force(:,1:last_index), ...
 'bed_force_N',bed_force(1:last_index),'robot_only_force_N', ...
 robot_only_force(:,1:last_index),'robot_only_residual_Nm', ...
 robot_only_residual(1:last_index),'robot_only_force_margin_N', ...
 robot_only_force_margin(1:last_index),'robot_only_feasible', ...
 robot_only_feasible(1:last_index),'robot_load_share', ...
 robot_load_share(1:last_index),'bed_torque_Nm',bed_torque(:,1:last_index), ...
 'robot_torque_Nm',robot_torque(:,1:last_index),'balance_residual_Nm', ...
 balance_residual(:,1:last_index),'controller_residual_Nm', ...
 controller_residual(:,1:last_index),'force_rate_N_s',force_rate(:,1:last_index), ...
 'sigma_min',sigma_min(1:last_index),'condition_number', ...
 condition_number(1:last_index),'active_contacts',active_contacts(1:last_index), ...
 'max_penetration_m',max_penetration(1:last_index),'soft_limit_active', ...
 soft_limit_active(1:last_index),'rom_violation',rom_violation(1:last_index), ...
 'robot_authority',robot_authority(1:last_index),'bed_credit', ...
 bed_credit(1:last_index),'terminal_state',terminal_state,'h_hip_m',h_hip, ...
 'calibration',calibration,'preposition_target',preposition,'config',config, ...
 'parameters',p,'plan',plan);
result.metrics=build_metrics(result);
end


function [mode,time,q]=transition(new_mode,now,current_q)
mode=string(new_mode);time=now;q=current_q;
end


function reference=fixed_reference(q)
reference=struct('q',q,'dq',zeros(2,1),'ddq',zeros(2,1));
end


function reference=transition_reference(q0,q1,elapsed,duration)
r=min(max(elapsed/duration,0),1);g=10*r^3-15*r^4+6*r^5;
gd=(30*r^2-60*r^3+30*r^4)/duration;
gdd=(60*r-180*r^2+120*r^3)/duration^2;delta=q1-q0;
reference=struct('q',q0+delta*g,'dq',delta*gd,'ddq',delta*gdd);
end


function value=smooth_progress(r)
r=min(max(r,0),1);value=10*r^3-15*r^4+6*r^5;
end


function metrics=build_metrics(result)
force_norm=vecnorm(result.robot_force_N,2,1);
metrics=struct('terminal_state',result.terminal_state,'duration_s',result.t(end), ...
 'final_progress',result.progress(end),'peak_robot_force_N',max(force_norm), ...
 'peak_bed_force_N',max(result.bed_force_N),'initial_robot_force_N', ...
 result.robot_force_N(:,1),'initial_bed_force_N',result.bed_force_N(1), ...
 'peak_force_rate_N_s',max(vecnorm(result.force_rate_N_s,2,1)), ...
 'peak_balance_residual_Nm',max(vecnorm(result.balance_residual_Nm,2,1)), ...
 'peak_controller_residual_Nm',max(vecnorm(result.controller_residual_Nm,2,1)), ...
 'max_penetration_m',max(result.max_penetration_m), ...
 'soft_limit_count',sum(result.soft_limit_active), ...
 'rom_violation_count',sum(result.rom_violation), ...
 'mode_transitions',sum(result.mode(2:end)~=result.mode(1:end-1)), ...
 'contact_chatter_count',sum((result.active_contacts(2:end)>0)~= ...
 (result.active_contacts(1:end-1)>0)),'nonfinite_count', ...
 sum(~isfinite([result.state(:);result.robot_force_N(:);result.bed_force_N(:)])));
pre=find(result.mode=="SUPPORTED_PREPOSITION",1,'last');
if isempty(pre),pre=1;end
metrics.preposition_time_s=sum(result.mode=="SUPPORTED_PREPOSITION")*result.config.dt;
metrics.preposition_final_q_deg=rad2deg(result.state(1:2,pre));
metrics.preposition_robot_only_force_N=result.robot_only_force_N(:,pre);
metrics.preposition_robot_only_residual_Nm=result.robot_only_residual_Nm(pre);
metrics.preposition_actual_robot_force_N=result.robot_force_N(:,pre);
metrics.preposition_bed_force_N=result.bed_force_N(pre);
metrics.preposition_boundary_seeking=any(result.preposition_target.soft_margin_rad<= ...
 result.config.preposition_soft_clearance_rad+1e-12);
lift=find(result.mode=="SUSPENDED_MOTION",1,'first');
if isempty(lift)
 metrics.liftoff_time_s=NaN;metrics.liftoff_q_deg=[NaN;NaN];
 metrics.liftoff_force_N=[NaN;NaN];metrics.liftoff_bed_force_N=NaN;
 metrics.liftoff_sigma_min=NaN;metrics.liftoff_condition=NaN;
 metrics.liftoff_residual_Nm=NaN;metrics.liftoff_tube_deviation_deg=[NaN;NaN];
else
 metrics.liftoff_time_s=result.t(lift);metrics.liftoff_q_deg=rad2deg(result.state(1:2,lift));
 metrics.liftoff_force_N=result.robot_force_N(:,lift);metrics.liftoff_bed_force_N=result.bed_force_N(lift);
 metrics.liftoff_sigma_min=result.sigma_min(lift);metrics.liftoff_condition=result.condition_number(lift);
 metrics.liftoff_residual_Nm=result.robot_only_residual_Nm(lift);
 metrics.liftoff_tube_deviation_deg=rad2deg(result.state(1:2,lift)-result.q_nominal(:,lift));
end
end
