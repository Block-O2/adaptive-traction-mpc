function diagnostic = dynamic_robust_v1_dynamic_margin( ...
        q, dq, q_ref, dq_ref, ddq_ref, nominal, config)
%DYNAMIC_ROBUST_V1_DYNAMIC_MARGIN Nominal robot-only dynamic force demand.
%
% This is intentionally distinct from the registered quasistatic robust
% margin. It predicts the force needed for the candidate closed-loop motion
% without taking credit for bed support.

q = q(:); dq = dq(:); q_ref = q_ref(:); dq_ref = dq_ref(:);
ddq_ref = ddq_ref(:);
[M, h, ~, G] = human_two_link_v2_dynamics_terms(q, dq, nominal);
tau_passive = human_two_link_v2_passive_torque(q, dq, nominal);
ddq_cmd = ddq_ref-config.Kp*(q-q_ref)-config.Kd*(dq-dq_ref);
tau_req = M*ddq_cmd+h+G+tau_passive;
mapping = single_arm_v2_force_map(q, dq, nominal);
[exact_force, solve] = single_arm_v2_stable_force_solve( ...
    mapping.A, tau_req, config.svd_relative_tolerance);
rank_deficient = solve.rank < 2;
if rank_deficient
    exact_force(:) = NaN;
    margin_N = -Inf;
else
    margin_N = config.force_bound_N-norm(exact_force, Inf);
end

limit = config.force_bound_N;
exact_feasible = ~rank_deficient && margin_N >= -config.bound_tolerance_N && ...
    solve.residual_norm <= config.dynamic_residual_tolerance_Nm;
if exact_feasible
    bounded_force = exact_force;
    tie_break = 0;
else
    H = mapping.A'*mapping.A;
    [~, chol_flag] = chol((H+H')/2);
    tie_break = 0;
    if chol_flag ~= 0
        tie_break = 1e-12*max(1, norm(mapping.A, 'fro')^2);
        H = H+tie_break*eye(2);
    end
    bounded_force = single_arm_v2_solve_box_qp(H, ...
        -mapping.A'*tau_req, -limit*ones(2,1), limit*ones(2,1));
end
bounded_residual = mapping.A*bounded_force-tau_req;

diagnostic = struct('q', q, 'dq', dq, 'q_ref', q_ref, ...
    'dq_ref', dq_ref, 'ddq_ref', ddq_ref, 'ddq_cmd', ddq_cmd, ...
    'tau_required_Nm', tau_req, 'exact_force_N', exact_force, ...
    'exact_force_norm_inf_N', norm(exact_force, Inf), ...
    'margin_N', margin_N, 'exact_feasible', exact_feasible, ...
    'bounded_force_N', bounded_force, ...
    'bounded_residual_Nm', bounded_residual, ...
    'bounded_residual_norm_Nm', norm(bounded_residual), ...
    'rank_deficient', rank_deficient, 'tie_break', tie_break, ...
    'mapping', mapping, 'solve', solve);
end
