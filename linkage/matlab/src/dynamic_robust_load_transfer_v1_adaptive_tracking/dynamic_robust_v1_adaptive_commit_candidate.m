function [state,validation] = dynamic_robust_v1_adaptive_commit_candidate( ...
        state, solver, current_fit_rms, nominal, adaptive, sample_index)
%DYNAMIC_ROBUST_V1_ADAPTIVE_COMMIT_CANDIDATE Validate then rate-limit update.

validation=dynamic_robust_v1_adaptive_validate_candidate( ...
    solver.theta,solver,current_fit_rms,adaptive);
state.theta_raw=solver.theta;
state.last_current_fit_rms=current_fit_rms;
state.last_fit_rms=solver.fit_rms;
state.last_condition_number=solver.condition_number;
state.last_rank=solver.rank;state.last_iterations=solver.iterations;
state.last_solve_time_s=solver.solve_time_s;
state.total_solve_time_s=state.total_solve_time_s+solver.solve_time_s;
state.last_status=validation.reason;
if validation.accepted
    state.theta_model=dynamic_robust_v1_adaptive_bounded_update( ...
        state.theta_model,solver.theta,adaptive);
    state.controller_model=dynamic_robust_v1_adaptive_apply_theta( ...
        nominal,state.theta_model);
    state.accepted_updates=state.accepted_updates+1;
    if isnan(state.first_accepted_sample)
        state.first_accepted_sample=sample_index;
    end
else
    state.rejected_updates=state.rejected_updates+1;
    if ~solver.success,state.solver_failures=state.solver_failures+1;end
end
end
