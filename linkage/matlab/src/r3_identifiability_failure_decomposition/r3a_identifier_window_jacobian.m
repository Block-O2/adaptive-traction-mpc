function diagnostic = r3a_identifier_window_jacobian( ...
        window,theta,nominal,h_hip,config,adaptive)
%R3A_IDENTIFIER_WINDOW_JACOBIAN Rebuild the normalized R2B sensitivity.
%
% The derivative is with respect to the same normalized z coordinate used by
% R2B. It calls the retained exact-discrete residual and does not alter the
% estimator or any source result.

lower=adaptive.theta_min;upper=adaptive.theta_max;
center=(lower+upper)/2;half_range=(upper-lower)/2;
z=min(max((theta(:)-center)./half_range,-1),1);
base=dynamic_robust_v1_adaptive_window_residual( ...
    theta(:),window,nominal,h_hip,config);
J=zeros(numel(base),numel(z));
for parameter_index=1:numel(z)
    plus=z;minus=z;
    plus(parameter_index)=min(1,z(parameter_index)+ ...
        adaptive.finite_difference_step);
    minus(parameter_index)=max(-1,z(parameter_index)- ...
        adaptive.finite_difference_step);
    denominator=plus(parameter_index)-minus(parameter_index);
    if denominator<=0
        error('R3A:InvalidFiniteDifference','Zero normalized FD interval.');
    end
    theta_plus=center+half_range.*plus;
    theta_minus=center+half_range.*minus;
    r_plus=dynamic_robust_v1_adaptive_window_residual( ...
        theta_plus,window,nominal,h_hip,config);
    r_minus=dynamic_robust_v1_adaptive_window_residual( ...
        theta_minus,window,nominal,h_hip,config);
    J(:,parameter_index)=(r_plus-r_minus)/denominator;
end
[U,S,V]=svd(J,'econ'); %#ok<ASGLU>
singular_values=diag(S);
if isempty(singular_values) || singular_values(1)<=0
    tolerance=0;rank_value=0;condition_number=Inf;
else
    tolerance=max(size(J))*eps(singular_values(1));
    rank_value=sum(singular_values>tolerance);
    if rank_value<size(J,2) || singular_values(end)<=0
        condition_number=Inf;
    else
        condition_number=singular_values(1)/singular_values(end);
    end
end
V=normalize_vector_signs(V);
diagnostic=struct('J',J,'residual',base,'singular_values', ...
    singular_values,'V',V,'rank',rank_value,'tolerance',tolerance, ...
    'condition_number',condition_number, ...
    'column_correlation',r3a_safe_column_correlation(J));
end


function vectors=normalize_vector_signs(vectors)
for column=1:size(vectors,2)
    [~,index]=max(abs(vectors(:,column)));
    if vectors(index,column)<0,vectors(:,column)=-vectors(:,column);end
end
end
