function [tau_joint, details] = human_two_link_v2_oracle_controller( ...
        q, dq, q_ref, dq_ref, ddq_ref, p, Kp, Kd)
%HUMAN_TWO_LINK_V2_ORACLE_CONTROLLER Exact-model joint-torque validation law.

q = q(:);
dq = dq(:);
q_ref = q_ref(:);
dq_ref = dq_ref(:);
ddq_ref = ddq_ref(:);
if any(~isfinite([q; dq; q_ref; dq_ref; ddq_ref])) || ...
        any([numel(q), numel(dq), numel(q_ref), ...
        numel(dq_ref), numel(ddq_ref)] ~= 2) || ...
        ~isequal(size(Kp), [2, 2]) || ~isequal(size(Kd), [2, 2])
    error('HumanTwoLinkV2:InvalidOracleInput', ...
        'Oracle inputs and gains have invalid dimensions or values.');
end

[M, h, ~, G] = human_two_link_v2_dynamics_terms(q, dq, p);
[tau_passive, passive_details] = ...
    human_two_link_v2_passive_torque(q, dq, p);
position_error = q-q_ref;
velocity_error = dq-dq_ref;
feedforward = M*ddq_ref+h+G+tau_passive;
feedback = -Kp*position_error-Kd*velocity_error;
tau_joint = feedforward+feedback;

details = struct();
details.feedforward = feedforward;
details.feedback = feedback;
details.position_error = position_error;
details.velocity_error = velocity_error;
details.passive_left = tau_passive;
details.passive = passive_details;
end
