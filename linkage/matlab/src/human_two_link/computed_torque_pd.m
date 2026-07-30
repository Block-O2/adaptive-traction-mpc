function [tau_joint, components] = computed_torque_pd( ...
        q, dq, q_ref, dq_ref, ddq_ref, p, Kp, Kd)
%COMPUTED_TORQUE_PD Oracle validation controller using true plant parameters.

q = q(:);
dq = dq(:);
q_ref = q_ref(:);
dq_ref = dq_ref(:);
ddq_ref = ddq_ref(:);
if ~isequal(size(Kp), [2, 2]) || ~isequal(size(Kd), [2, 2])
    error('HumanTwoLink:InvalidControllerGain', ...
        'Kp and Kd must be 2-by-2 matrices.');
end

[M, h, ~, G] = dynamics_terms(q, dq, p);
e = q - q_ref;
de = dq - dq_ref;
feedforward = M*ddq_ref + h + G;
feedback = -Kp*e - Kd*de;
tau_joint = feedforward + feedback;

components = struct();
components.feedforward = feedforward;
components.feedback = feedback;
components.error = e;
components.velocity_error = de;
end
