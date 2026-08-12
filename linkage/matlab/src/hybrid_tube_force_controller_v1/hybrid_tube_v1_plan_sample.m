function sample = hybrid_tube_v1_plan_sample(plan, s)
%HYBRID_TUBE_V1_PLAN_SAMPLE Evaluate governed C2 spatial task plan.

s = min(max(s, 0), 1);
q = zeros(2, 1); q_s = zeros(2, 1); q_ss = zeros(2, 1);
force = zeros(2, 1);
for joint = 1:2
    q(joint) = ppval(plan.pp_q{joint}, s);
    q_s(joint) = ppval(plan.pp_q_s{joint}, s);
    q_ss(joint) = ppval(plan.pp_q_ss{joint}, s);
    force(joint) = ppval(plan.pp_force{joint}, s);
end
nominal = hybrid_tube_v1_task_path(s);
tube = hybrid_tube_v1_tube_schedule(s, nominal.q, plan.config);
if plan.config.tube_cap_deg == 0
    q = nominal.q;
    q_s = nominal.q_s;
    q_ss = nominal.q_ss;
end
hold_feasible = interp1(plan.s, double(plan.hold_feasible), s, ...
    'previous', 'extrap') > 0.5;
residual = interp1(plan.s, plan.residual_norm, s, 'linear', 'extrap');
sample = struct('s', s, 'q', q, 'q_s', q_s, 'q_ss', q_ss, ...
    'force_local', force, 'force_norm', norm(force), ...
    'nominal_q', nominal.q, 'tube_rad', tube, ...
    'deviation', q-nominal.q, 'hold_feasible', hold_feasible, ...
    'bounded_residual_Nm', residual, 'phase', nominal.phase);
end
