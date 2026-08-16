function solver = dynamic_robust_v1_adaptive_solve_window( ...
        state, nominal, h_hip, config, adaptive)
%DYNAMIC_ROBUST_V1_ADAPTIVE_SOLVE_WINDOW Bounded finite-difference NLS.
%
% This is a small projected Gauss-Newton/Levenberg-Marquardt solver. It uses
% central finite differences in normalized registered-parameter coordinates
% and a fixed backtracking list. It does not require Optimization Toolbox.

lower=adaptive.theta_min;upper=adaptive.theta_max;
solve_clock=tic;
center=(lower+upper)/2;half_range=(upper-lower)/2;
z=min(max((state.theta_model-center)./half_range,-1),1);
[residual,ok]=evaluate(z);
initial_rms=rms_value(residual);iterations=0;improved=false;
last_J=zeros(numel(residual),numel(z));
if ok
    for iteration=1:adaptive.maximum_iterations
        iterations=iteration;
        [J,jacobian_ok]=finite_difference_jacobian(z,residual);
        last_J=J;
        if ~jacobian_ok,ok=false;break;end
        normal=J'*J;
        damping=adaptive.lm_damping*max(1,max(diag(normal)));
        step=-(normal+damping*eye(numel(z)))\(J'*residual);
        if any(~isfinite(step)),ok=false;break;end
        if norm(step,Inf)<=sqrt(eps),break;end
        accepted_line=false;current_cost=residual'*residual;
        for scale=adaptive.line_search_scales
            trial=min(max(z+scale*step,-1),1);
            [trial_residual,trial_ok]=evaluate(trial);
            if trial_ok && trial_residual'*trial_residual < ...
                    current_cost*(1-adaptive.fit_improvement_tolerance)
                z=trial;residual=trial_residual;
                accepted_line=true;improved=true;break;
            end
        end
        if ~accepted_line,break;end
    end
end
if ok
    [last_J,jacobian_ok]=finite_difference_jacobian(z,residual);
    ok=jacobian_ok;
end
singular_values=svd(last_J,'econ');
if isempty(singular_values) || singular_values(1)<=0
    numerical_rank=0;condition_number=Inf;
else
    tolerance=max(size(last_J))*eps(singular_values(1));
    numerical_rank=sum(singular_values>tolerance);
    if numerical_rank<numel(z) || singular_values(end)<=0
        condition_number=Inf;
    else
        condition_number=singular_values(1)/singular_values(end);
    end
end
theta=center+half_range.*z;
solver=struct('success',ok,'theta',theta,'fit_rms',rms_value(residual), ...
    'initial_fit_rms',initial_rms,'iterations',iterations, ...
    'improved',improved,'rank',numerical_rank, ...
    'condition_number',condition_number,'solve_time_s',toc(solve_clock), ...
    'singular_values',singular_values);

    function [value,valid]=evaluate(z_value)
        theta_value=center+half_range.*z_value;
        try
            value=dynamic_robust_v1_adaptive_window_residual( ...
                theta_value,state,nominal,h_hip,config);
            valid=all(isfinite(value));
        catch
            value=NaN(4*size(state.x,2),1);valid=false;
        end
    end

    function [J,valid]=finite_difference_jacobian(z_value,base_residual)
        J=zeros(numel(base_residual),numel(z_value));valid=true;
        for parameter_index=1:numel(z_value)
            plus=z_value;minus=z_value;
            plus(parameter_index)=min(1,z_value(parameter_index)+ ...
                adaptive.finite_difference_step);
            minus(parameter_index)=max(-1,z_value(parameter_index)- ...
                adaptive.finite_difference_step);
            denominator=plus(parameter_index)-minus(parameter_index);
            if denominator<=0,valid=false;return;end
            [r_plus,plus_ok]=evaluate(plus);
            [r_minus,minus_ok]=evaluate(minus);
            if ~plus_ok || ~minus_ok,valid=false;return;end
            J(:,parameter_index)=(r_plus-r_minus)/denominator;
        end
    end
end


function value=rms_value(values)
if isempty(values) || any(~isfinite(values)),value=NaN;return;end
value=sqrt(mean(values.^2));
end
