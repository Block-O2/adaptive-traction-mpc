function state = dynamic_robust_v1_adaptive_window_append( ...
        state, x, u, x_next, sample_index, adaptive)
%DYNAMIC_ROBUST_V1_ADAPTIVE_WINDOW_APPEND Ordered past-transition buffer.

x=x(:);u=u(:);x_next=x_next(:);
if numel(x)~=4 || numel(x_next)~=4 || numel(u)~=2 || ...
        any(~isfinite([x;x_next;u])) || ~isscalar(sample_index) || ...
        ~isfinite(sample_index)
    error('DynamicRobustV1:InvalidAdaptiveTransition', ...
        'A transition must contain finite x(4), u(2), x_next(4), and index.');
end
state.x(:,end+1)=x;state.u(:,end+1)=u;
state.x_next(:,end+1)=x_next;state.sample_index(end+1)=sample_index;
if size(state.x,2)>adaptive.window_size
    state.x(:,1)=[];state.u(:,1)=[];state.x_next(:,1)=[];
    state.sample_index(1)=[];
end
state.total_transitions=state.total_transitions+1;
end
