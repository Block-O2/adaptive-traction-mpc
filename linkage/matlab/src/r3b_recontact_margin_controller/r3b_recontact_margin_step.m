function [command_q,details] = r3b_recontact_margin_step( ...
        previous_q,path_q,tube_rad,measured_bed_force_N,controller_model, ...
        h_hip,config)
%R3B_RECONTACT_MARGIN_STEP Rate-limited measured-force reference correction.

previous_q=previous_q(:);path_q=path_q(:);tube_rad=tube_rad(:);
lower=max(path_q-tube_rad,controller_model.q_min);
upper=min(path_q+tube_rad,controller_model.q_max);
target=config.r3b_contact_target_N;
error_N=target-measured_bed_force_N;
step=config.r3b_gradient_step_rad;
gradient=zeros(2,1);
for joint=1:2
    plus=previous_q;minus=previous_q;
    plus(joint)=min(previous_q(joint)+step,upper(joint));
    minus(joint)=max(previous_q(joint)-step,lower(joint));
    denominator=plus(joint)-minus(joint);
    if denominator<=eps,continue;end
    force_plus=bed_supported_v1_contact(plus,zeros(2,1),h_hip, ...
        controller_model,config).total_normal_force_N;
    force_minus=bed_supported_v1_contact(minus,zeros(2,1),h_hip, ...
        controller_model,config).total_normal_force_N;
    gradient(joint)=(force_plus-force_minus)/denominator;
end
gradient_norm=norm(gradient);
blocked=false;
if gradient_norm<=0.1
    delta=zeros(2,1);blocked=true;
else
    delta=gradient*error_N/(gradient_norm^2+ ...
        config.r3b_gradient_regularization_N2_rad2);
    maximum_step=config.r3b_reference_rate_rad_s*config.dt;
    if norm(delta)>maximum_step
        delta=delta*(maximum_step/norm(delta));
    end
end
candidate=min(max(previous_q+delta,lower),upper);
for attempt=1:10
    [~,passive]=human_two_link_v2_passive_torque( ...
        candidate,zeros(2,1),controller_model);
    if ~any(passive.soft.active),break;end
    candidate=previous_q+0.5*(candidate-previous_q);
end
[~,passive]=human_two_link_v2_passive_torque( ...
    candidate,zeros(2,1),controller_model);
if any(passive.soft.active)
    candidate=previous_q;blocked=true;
end
command_q=candidate;
details=struct('target_force_N',target,'measured_force_N', ...
    measured_bed_force_N,'force_error_N',error_N, ...
    'force_gradient_N_rad',gradient,'command_rate_rad_s', ...
    (command_q-previous_q)/config.dt,'inside_tube', ...
    all(command_q>=path_q-tube_rad-10*eps & ...
        command_q<=path_q+tube_rad+10*eps), ...
    'inside_rom',all(command_q>=controller_model.q_min & ...
        command_q<=controller_model.q_max),'blocked',blocked);
end
