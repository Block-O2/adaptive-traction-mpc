function reference = dynamic_robust_v1_moving_blend_reference( ...
        q_entry, path_q_entry, nominal, progress, elapsed, duration)
%DYNAMIC_ROBUST_V1_MOVING_BLEND_REFERENCE Path-following offset decay.
%
% Unlike interpolation from a fixed q_entry to a moving endpoint, this form
% follows the current path immediately and smoothly removes only the spatial
% transfer offset. The reference therefore does not lag behind the moving
% tube center during load takeover.

r=min(max(elapsed/duration,0),1);g=10*r^3-15*r^4+6*r^5;
gd=(30*r^2-60*r^3+30*r^4)/duration;
gdd=(60*r-180*r^2+120*r^3)/duration^2;
offset=q_entry-path_q_entry;
nominal_dq=nominal.q_s*progress.s_dot;
nominal_ddq=nominal.q_ss*progress.s_dot^2+ ...
    nominal.q_s*progress.s_ddot;
reference=struct('q',nominal.q+(1-g)*offset, ...
    'dq',nominal_dq-gd*offset, ...
    'ddq',nominal_ddq-gdd*offset);
end
