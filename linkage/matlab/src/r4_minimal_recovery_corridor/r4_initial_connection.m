function edge = r4_initial_connection(q_target,anchor,model_kind,support_mode)
%R4_INITIAL_CONNECTION Frozen R3C one-step predictor from a real anchor.

c=anchor.config; model=r4_model_parameters(anchor,model_kind);
q=anchor.q_rad;dq=anchor.dq_rad_s;
bed=bed_supported_v1_contact(q,dq,anchor.h_hip_m, ...
    anchor.plant_parameters,c);
if string(support_mode)=="bed_assisted"
    tau_bed=bed.generalized_torque_Nm; bed_ok= ...
        bed.total_normal_force_N>=c.contact_force_threshold_N;
else
    tau_bed=zeros(2,1);bed_ok=true;
end
[u,details]=bed_supported_v1_robot_controller(q,dq,q_target, ...
    zeros(2,1),zeros(2,1),tau_bed,anchor.u_previous_N,model,c,1,1);
[M,h,~,G]=human_two_link_v2_dynamics_terms(q,dq,model);
passive=human_two_link_v2_passive_torque(q,dq,model);
mapping=single_arm_v2_force_map(q,dq,model);
ddq=M\(mapping.A*u+tau_bed-h-G-passive);
horizon=c.r3c_prediction_horizon_s;
q_pred=q+dq*horizon+0.5*ddq*horizon^2;
lower=model.q_min+model.soft_limit_margin;
upper=model.q_max-model.soft_limit_margin;
current_clearance=min(q-lower,upper-q);
predicted_clearance=min(q_pred-lower,upper-q_pred);
hold_ok=all(current_clearance>=-c.soft_margin_tolerance_rad) && ...
    all(predicted_clearance>=-c.soft_margin_tolerance_rad) && ...
    predicted_clearance(2)>=c.r3c_hold_buffer_rad;
force_ok=all(abs(u)<=c.force_bound_N+c.bound_tolerance_N);
residual_ok=norm(details.torque_residual_Nm)<= ...
    c.dynamic_residual_tolerance_Nm;
target_local=all(abs(rad2deg(q_target-q))<=1.5+1e-12);
feasible=bed_ok && hold_ok && force_ok && residual_ok && target_local;
edge=struct('feasible',feasible,'q_from_rad',q,'q_to_rad',q_target, ...
    'q_pred_rad',q_pred,'u_N',u,'ddq_rad_s2',ddq, ...
    'bed_ok',bed_ok,'hold_ok',hold_ok,'force_ok',force_ok, ...
    'residual_ok',residual_ok,'target_local',target_local, ...
    'residual_norm_Nm',norm(details.torque_residual_Nm), ...
    'predicted_q2_clearance_rad',predicted_clearance(2));
end
