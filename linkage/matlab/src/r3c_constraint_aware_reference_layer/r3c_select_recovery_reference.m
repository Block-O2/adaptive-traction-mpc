function selected=r3c_select_recovery_reference(q,dq,path_q,tube_rad, ...
        tau_bed,u_previous,controller_model,config)
%R3C_SELECT_RECOVERY_REFERENCE Bounded task-local safety candidate search.

q=q(:);dq=dq(:);path_q=path_q(:);tube_rad=tube_rad(:);
lower_soft=controller_model.q_min+controller_model.soft_limit_margin;
upper_soft=controller_model.q_max-controller_model.soft_limit_margin;
offsets1=offsets(tube_rad(1),config.r3c_candidate_step_rad);
offsets2=offsets(tube_rad(2),config.r3c_candidate_step_rad);
rows=zeros(0,8);candidates=cell(0,1);
for d1=offsets1
    for d2=offsets2
        reference_q=path_q+[d1;d2];
        if any(reference_q<lower_soft+config.r3c_reference_soft_clearance_rad | ...
                reference_q>upper_soft-config.r3c_reference_soft_clearance_rad)
            continue;
        end
        [force,controller]=bed_supported_v1_robot_controller(q,dq, ...
            reference_q,zeros(2,1),zeros(2,1),tau_bed,u_previous, ...
            controller_model,config,1,1);
        mapping=single_arm_v2_force_map(q,dq,controller_model);
        [M,h,~,G]=human_two_link_v2_dynamics_terms(q,dq,controller_model);
        passive=human_two_link_v2_passive_torque(q,dq,controller_model);
        ddq=M\(mapping.A*force+tau_bed-h-G-passive);
        horizon=config.r3c_prediction_horizon_s;
        predicted_q=q+horizon*dq+.5*horizon^2*ddq;
        predicted_clearance=min([predicted_q-lower_soft; ...
            upper_soft-predicted_q]);
        predicted_q2_clearance=predicted_q(2)-lower_soft(2);
        force_margin=min([force-config.u_min;config.u_max-force]);
        residual=norm(controller.torque_residual_Nm);
        feasible=predicted_clearance>=config.r3c_hold_buffer_rad && ...
            force_margin>=-config.bound_tolerance_N && ...
            residual<=config.dynamic_residual_tolerance_Nm;
        row=[-double(feasible),-predicted_clearance, ...
            -predicted_q2_clearance,residual,norm(reference_q-path_q), ...
            -force_margin,d1,d2];
        rows(end+1,:)=row; %#ok<AGROW>
        candidates{end+1}=struct('q',reference_q,'force_N',force, ...
            'predicted_q_rad',predicted_q,'predicted_clearance_rad', ...
            predicted_clearance,'predicted_q2_clearance_rad', ...
            predicted_q2_clearance,'force_margin_N',force_margin, ...
            'residual_Nm',residual,'feasible',feasible); %#ok<AGROW>
    end
end
selected=struct('found',false,'feasible',false,'q',path_q, ...
    'force_N',[NaN;NaN],'predicted_q_rad',[NaN;NaN], ...
    'predicted_clearance_rad',NaN,'predicted_q2_clearance_rad',NaN, ...
    'force_margin_N',NaN,'residual_Nm',NaN,'candidate_count',0);
if isempty(rows),return;end
[~,order]=sortrows(rows,1:6);selected=candidates{order(1)};
selected.found=true;selected.candidate_count=numel(candidates);
end


function values=offsets(cap,step)
if cap<=eps,values=0;return;end
values=unique([0:step:cap,cap]);
end
