function state = dynamic_robust_v1_adaptive_initial_state(nominal, adaptive)
%DYNAMIC_ROBUST_V1_ADAPTIVE_INITIAL_STATE Nominal-start R2B identifier state.

if nargin < 2 || isempty(adaptive)
    adaptive=dynamic_robust_v1_adaptive_config();
end
human_two_link_v2_validate_parameters(nominal);
state=struct();
state.theta_raw=adaptive.theta_nominal;
state.theta_model=adaptive.theta_nominal;
state.controller_model=nominal;
state.x=zeros(4,0);state.u=zeros(2,0);state.x_next=zeros(4,0);
state.sample_index=zeros(1,0);
state.total_transitions=0;state.solve_attempts=0;
state.accepted_updates=0;state.rejected_updates=0;
state.solver_failures=0;state.first_accepted_sample=NaN;
state.last_status="BUFFERING";state.last_fit_rms=NaN;
state.last_current_fit_rms=NaN;state.last_condition_number=NaN;
state.last_rank=0;state.last_iterations=0;
state.last_solve_time_s=NaN;state.total_solve_time_s=0;
end
