function [u_applied, state, details] = ...
        dynamic_robust_v1_safe_takeover_step(state, q, dq, ...
        u_previous, u_nominal_candidate, u_nominal_desired, tau_bed, ...
        nominal, config)
%DYNAMIC_ROBUST_V1_SAFE_TAKEOVER_STEP R1 constraint-aware startup governor.
%
% The governor sees only runtime-available quantities: applied command
% history, measured q/dq and bed torque, nominal controller outputs, the
% nominal model, and fixed safety/actuator limits.  It does not accept the
% true plant, a mismatch label, or an equilibrium helper/oracle.

q=q(:);dq=dq(:);u_previous=u_previous(:);
u_nominal_candidate=u_nominal_candidate(:);
u_nominal_desired=u_nominal_desired(:);tau_bed=tau_bed(:);
validate_inputs(q,dq,u_previous,u_nominal_candidate,u_nominal_desired,tau_bed);

lower=nominal.q_min+nominal.soft_limit_margin;
upper=nominal.q_max-nominal.soft_limit_margin;
[soft_margin, margin_velocity, boundary_velocity_safe] = measured_safety( ...
    q,dq,lower,upper,config);
margin_decreasing=all(isfinite(state.previous_soft_margin_rad)) && ...
    any(soft_margin<state.previous_soft_margin_rad- ...
    config.safe_takeover_prediction_tolerance_rad);
velocity_deteriorating=all(isfinite( ...
    state.previous_margin_velocity_rad_s)) && ...
    any(margin_velocity<state.previous_margin_velocity_rad_s- ...
    config.safe_takeover_velocity_tolerance_rad_s);
force_gap=norm(u_nominal_desired-u_previous,Inf);
capture_ready=force_gap<=config.safe_takeover_capture_band_N+ ...
    config.bound_tolerance_N;
state.elapsed_s=state.elapsed_s+config.dt;
state.mode_time_s=state.mode_time_s+config.dt;
reason="";lambda=0;lambda_components=zeros(2,1);
predicted_margin=soft_margin;

if state.mode=="SAFE_HOLD"
    u_applied=u_previous;
    reason="WAIT_FORCE_CAPTURE";
    if capture_ready && boundary_velocity_safe && all(soft_margin>= ...
            -config.safe_takeover_prediction_tolerance_rad)
        state.mode="TAKEOVER";state.mode_time_s=0;
    elseif capture_ready && ~boundary_velocity_safe
        reason="WAIT_BOUNDARY_DIRECTION";
    end
end

if state.mode=="TAKEOVER"
    if margin_decreasing || velocity_deteriorating || ...
            ~boundary_velocity_safe
        [u_applied,predicted_margin]=select_safety_recovery( ...
            q,dq,u_previous,tau_bed,soft_margin,lower,upper, ...
            state.initial_applied_force_N,nominal,config);
        lambda=0;lambda_components=zeros(2,1);
        reason="INWARD_SAFETY_RECOVERY";
    else
        [u_applied,lambda,lambda_components,predicted_margin] = ...
            select_safe_command( ...
            q,dq,u_previous,u_nominal_candidate,tau_bed,soft_margin, ...
            lower,upper,state.initial_applied_force_N,nominal,config);
        if lambda==1
            reason="FULL_SAFE_STEP";
        elseif lambda>0
            reason="SCALED_PREDICTED_MARGIN";
        else
            reason="HOLD_PREDICTED_MARGIN";
        end
    end
    applied_gap=norm(u_nominal_desired-u_applied,Inf);
    demand_captured=applied_gap<=config.safe_takeover_tracking_error_N+ ...
        config.bound_tolerance_N;
    clearance_established=all(soft_margin>= ...
        config.safe_takeover_tracking_clearance_rad);
    safe_and_stable=all(soft_margin>= ...
        -config.safe_takeover_prediction_tolerance_rad) && ...
        boundary_velocity_safe && ~velocity_deteriorating && ...
        all(predicted_margin>= ...
        -config.safe_takeover_prediction_tolerance_rad);
    if (demand_captured || clearance_established) && safe_and_stable
        state.stable_time_s=state.stable_time_s+config.dt;
        reason="DEMAND_CAPTURE_STABLE";
    else
        state.stable_time_s=0;
    end
    if state.stable_time_s+eps>=config.safe_takeover_stable_duration_s
        state.mode="TRACKING";state.mode_time_s=0;
        state.tracking_entered=true;state.tracking_time_s=state.elapsed_s;
        reason="TRACKING_ENTERED";
    end
end

if state.mode=="TRACKING"
    u_applied=u_nominal_candidate;lambda=1;lambda_components=ones(2,1);
    [~,predicted_margin]=predict_margin(q,dq,u_applied,tau_bed, ...
        lower,upper,state.initial_applied_force_N,nominal,config);
    if reason=="",reason="TRACKING";end
end

if state.mode~="TRACKING" && ...
        state.elapsed_s+eps>=config.safe_takeover_timeout_s
    state.mode="TAKEOVER_ABORT";state.mode_time_s=0;
    state.timed_out=true;u_applied=u_previous;lambda=0;
    lambda_components=zeros(2,1);
    reason="SAFE_TAKEOVER_TIMEOUT";
end

if state.mode~="TRACKING"
    if lambda==0
        state.hold_steps=state.hold_steps+1;
    elseif lambda<1
        state.scaled_steps=state.scaled_steps+1;
    else
        state.full_steps=state.full_steps+1;
    end
    state.minimum_lambda=min(state.minimum_lambda,lambda);
end
state.previous_soft_margin_rad=soft_margin;
state.previous_margin_velocity_rad_s=margin_velocity;
details=struct('mode',state.mode,'reason',reason,'lambda',lambda, ...
    'lambda_components',lambda_components, ...
    'nominal_desired_force_N',u_nominal_desired, ...
    'nominal_candidate_force_N',u_nominal_candidate, ...
    'applied_force_N',u_applied,'force_gap_N',force_gap, ...
    'soft_margin_rad',soft_margin, ...
    'predicted_soft_margin_rad',predicted_margin, ...
    'boundary_velocity_safe',boundary_velocity_safe, ...
    'measured_margin_decreasing',margin_decreasing, ...
    'margin_velocity_rad_s',margin_velocity, ...
    'margin_velocity_deteriorating',velocity_deteriorating, ...
    'capture_ready',capture_ready);
end


function [u,predicted_margin]=select_safety_recovery( ...
        q,dq,u_previous,tau_bed,current_margin,lower,upper,anchor,p,c)
steps=[-1 0 1];slew=c.du_max(:)*c.dt;
u=u_previous;predicted_margin=current_margin;best=-Inf;
for direction1=steps
for direction2=steps
    trial=u_previous+[direction1;direction2].*slew;
    if any(trial<c.u_min(:)-c.bound_tolerance_N | ...
            trial>c.u_max(:)+c.bound_tolerance_N)
        continue;
    end
    [~,margin]=predict_margin( ...
        q,dq,trial,tau_bed,lower,upper,anchor,p,c);
    score=min(margin-current_margin);
    if score>best+c.safe_takeover_prediction_tolerance_rad
        u=trial;predicted_margin=margin;best=score;
    end
end
end
end


function [u,lambda,lambda_components,predicted_margin]=select_safe_command( ...
        q,dq,u_previous,candidate,tau_bed,current_margin,lower,upper, ...
        anchor,p,c)
lambdas=[1 .5 .25 .125 0];
u=u_previous;lambda=0;lambda_components=zeros(2,1);
predicted_margin=current_margin;best_score=-Inf;
best_progress=-Inf;
du=candidate-u_previous;
for value1=lambdas
for value2=lambdas
    values=[value1;value2];
    trial=u_previous+values.*du;
    if any(trial<c.u_min(:)-c.bound_tolerance_N | ...
            trial>c.u_max(:)+c.bound_tolerance_N)
        continue;
    end
    [~,trial_margin]=predict_margin( ...
        q,dq,trial,tau_bed,lower,upper,anchor,p,c);
    admissible=all(trial_margin>= ...
        -c.safe_takeover_prediction_tolerance_rad);
    admissible=admissible && all(trial_margin>=current_margin- ...
        c.safe_takeover_prediction_tolerance_rad);
    if admissible
        score=min(trial_margin-current_margin);
        progress_score=sum(abs(trial-u_previous));
        if score>best_score+c.safe_takeover_prediction_tolerance_rad || ...
                (abs(score-best_score)<= ...
                c.safe_takeover_prediction_tolerance_rad && ...
                progress_score>best_progress+eps)
            u=trial;lambda_components=values;
            predicted_margin=trial_margin;best_score=score;
            best_progress=progress_score;
        end
    end
end
end
denominator=norm(du);
if denominator<=eps
    lambda=1;lambda_components=ones(2,1);
else
    lambda=min(1,norm(u-u_previous)/denominator);
end
end


function [q_next,margin]=predict_margin( ...
        q,dq,u,tau_bed,lower,upper,anchor,p,c)
mapping=single_arm_v2_force_map(q,dq,p);
[M,h,~,G]=human_two_link_v2_dynamics_terms(q,dq,p);
tau_passive=human_two_link_v2_passive_torque(q,dq,p);
% The initial applied command is a measured command-history anchor.  The
% nominal model is used only for local input sensitivity about that anchor;
% its incorrect absolute equilibrium is deliberately not used as a startup
% acceleration oracle under plant mismatch.
ddq_trial=M\(mapping.A*u+tau_bed-h-G-tau_passive);
ddq_anchor=M\(mapping.A*anchor+tau_bed-h-G-tau_passive);
ddq=ddq_trial-ddq_anchor;
q_next=q+c.dt*dq+0.5*c.dt^2*ddq;
margin=min(q_next-lower,upper-q_next);
end


function [margin,margin_velocity,safe]=measured_safety(q,dq,lower,upper,c)
lower_margin=q-lower;upper_margin=upper-q;
margin=min(lower_margin,upper_margin);
nearest_is_lower=lower_margin<=upper_margin;
margin_velocity=dq;
margin_velocity(~nearest_is_lower)=-dq(~nearest_is_lower);
safe=all(margin_velocity>=-c.safe_takeover_velocity_tolerance_rad_s);
end


function validate_inputs(q,dq,u_previous,u_candidate,u_desired,tau_bed)
items={q,dq,u_previous,u_candidate,u_desired,tau_bed};
if any(cellfun(@(x)numel(x)~=2 || any(~isfinite(x)),items))
    error('DynamicRobustV1:InvalidTakeoverInput', ...
        'Takeover inputs must each contain two finite values.');
end
end
