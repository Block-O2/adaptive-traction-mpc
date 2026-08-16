function rows = r3a_moderate_state_conditioned_replay(result)
%R3A_MODERATE_STATE_CONDITIONED_REPLAY Offline same-state model comparison.
%
% This does not generate a counterfactual trajectory. It recomputes the
% retained dynamic diagnostic at adaptive-recorded states/references only.

alignment=r3a_tracking_alignment(result);indices=alignment.indices;
n=numel(indices);time_s=result.t(indices)';
tracking_time_s=(result.t(indices)-result.t(alignment.entry_index))';
progress=result.task_s(indices)';
nominal_margin_N=zeros(n,1);adaptive_margin_N=zeros(n,1);
oracle_margin_N=zeros(n,1);nominal_force_norm_N=zeros(n,1);
adaptive_force_norm_N=zeros(n,1);oracle_force_norm_N=zeros(n,1);
parameter_error=zeros(n,1);
truth=dynamic_robust_v1_adaptive_theta_from_parameters( ...
    result.nominal_parameters,result.plant_parameters);
for item=1:n
    index=indices(item);q=result.state(1:2,index);dq=result.state(3:4,index);
    arguments={q,dq,result.q_ref(:,index),result.dq_ref(:,index), ...
        result.ddq_ref(:,index)};
    nominal=dynamic_robust_v1_dynamic_margin(arguments{:}, ...
        result.nominal_parameters,result.config);
    theta=result.identifier_theta_model(:,index);
    adaptive_parameters=dynamic_robust_v1_adaptive_apply_theta( ...
        result.nominal_parameters,theta);
    adaptive=dynamic_robust_v1_dynamic_margin(arguments{:}, ...
        adaptive_parameters,result.config);
    oracle=dynamic_robust_v1_dynamic_margin(arguments{:}, ...
        result.plant_parameters,result.config);
    nominal_margin_N(item)=nominal.margin_N;
    adaptive_margin_N(item)=adaptive.margin_N;
    oracle_margin_N(item)=oracle.margin_N;
    nominal_force_norm_N(item)=norm(nominal.exact_force_N);
    adaptive_force_norm_N(item)=norm(adaptive.exact_force_N);
    oracle_force_norm_N(item)=norm(oracle.exact_force_N);
    parameter_error(item)=norm((theta-truth)./result.adaptive_config.theta_range);
end
rows=table(time_s,tracking_time_s,progress,nominal_margin_N, ...
    adaptive_margin_N,oracle_margin_N,nominal_force_norm_N, ...
    adaptive_force_norm_N,oracle_force_norm_N,parameter_error);
end
