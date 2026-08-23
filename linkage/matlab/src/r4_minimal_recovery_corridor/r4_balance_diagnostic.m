function diagnostic = r4_balance_diagnostic(q,dq,ddq,anchor,model_kind,support_mode)
%R4_BALANCE_DIAGNOSTIC Bounded dynamic balance with explicit bed credit.

q=q(:);dq=dq(:);ddq=ddq(:);
model=r4_model_parameters(anchor,model_kind); c=anchor.config;
[M,h,~,G]=human_two_link_v2_dynamics_terms(q,dq,model);
[tau_passive,passive]=human_two_link_v2_passive_torque(q,dq,model);
bed=bed_supported_v1_contact(q,dq,anchor.h_hip_m, ...
    anchor.plant_parameters,c);
if string(support_mode)=="bed_assisted"
    tau_bed=bed.generalized_torque_Nm;
elseif string(support_mode)=="robot_only"
    tau_bed=zeros(2,1);
else
    error('R4:InvalidSupportMode', ...
        'support_mode must be bed_assisted or robot_only.');
end
tau_required=M*ddq+h+G+tau_passive-tau_bed;
mapping=single_arm_v2_force_map(q,dq,model);
[exact_force,solve]=single_arm_v2_stable_force_solve( ...
    mapping.A,tau_required,c.svd_relative_tolerance);
rank_deficient=solve.rank<2;
limit=c.force_bound_N;
if rank_deficient
    exact_force(:)=NaN; margin_N=-Inf;
else
    margin_N=limit-norm(exact_force,Inf);
end
exact_feasible=~rank_deficient && ...
    margin_N>=-c.bound_tolerance_N && ...
    solve.residual_norm<=c.dynamic_residual_tolerance_Nm;
if exact_feasible
    bounded_force=exact_force;
else
    H=mapping.A'*mapping.A;
    if rcond(H)<1e-14, H=H+1e-12*eye(2); end
    bounded_force=single_arm_v2_solve_box_qp(H, ...
        -mapping.A'*tau_required,-limit*ones(2,1),limit*ones(2,1));
end
bounded_residual=mapping.A*bounded_force-tau_required;
diagnostic=struct('q',q,'dq',dq,'ddq',ddq,'model_kind',string(model_kind), ...
    'support_mode',string(support_mode),'bed',bed,'tau_bed_Nm',tau_bed, ...
    'tau_required_Nm',tau_required,'mapping',mapping, ...
    'exact_force_N',exact_force,'bounded_force_N',bounded_force, ...
    'force_margin_N',margin_N,'rank_deficient',rank_deficient, ...
    'exact_feasible',exact_feasible,'solve',solve, ...
    'bounded_residual_Nm',bounded_residual, ...
    'bounded_residual_norm_Nm',norm(bounded_residual), ...
    'passive',passive,'model_parameters',model);
end
