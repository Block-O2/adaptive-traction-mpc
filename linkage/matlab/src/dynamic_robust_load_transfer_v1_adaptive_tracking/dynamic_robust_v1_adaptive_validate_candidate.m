function validation = dynamic_robust_v1_adaptive_validate_candidate( ...
        candidate, solver, current_fit_rms, adaptive)
%DYNAMIC_ROBUST_V1_ADAPTIVE_VALIDATE_CANDIDATE Fixed estimate gate.

candidate=candidate(:);
finite_ok=numel(candidate)==7 && all(isfinite(candidate));
bounds_ok=finite_ok && all(candidate>=adaptive.theta_min- ...
    adaptive.parameter_bound_tolerance) && ...
    all(candidate<=adaptive.theta_max+adaptive.parameter_bound_tolerance);
solver_ok=isstruct(solver) && isfield(solver,'success') && solver.success;
rank_ok=solver_ok && solver.rank==numel(adaptive.theta_nominal);
condition_ok=rank_ok && isfinite(solver.condition_number) && ...
    solver.condition_number<=adaptive.maximum_condition_number;
fit_ok=solver_ok && isfinite(solver.fit_rms) && ...
    isfinite(current_fit_rms) && solver.fit_rms<=current_fit_rms*(1+ ...
    adaptive.fit_improvement_tolerance);
accepted=finite_ok && bounds_ok && solver_ok && rank_ok && ...
    condition_ok && fit_ok;
if ~finite_ok
    reason="REJECTED_NONFINITE";
elseif ~bounds_ok
    reason="REJECTED_BOUNDS";
elseif ~solver_ok
    reason="REJECTED_SOLVER";
elseif ~rank_ok || ~condition_ok
    reason="REJECTED_DEGENERATE";
elseif ~fit_ok
    reason="REJECTED_FIT";
else
    reason="ACCEPTED";
end
validation=struct('accepted',accepted,'reason',reason, ...
    'finite_ok',finite_ok,'bounds_ok',bounds_ok,'solver_ok',solver_ok, ...
    'rank_ok',rank_ok,'condition_ok',condition_ok,'fit_ok',fit_ok);
end
