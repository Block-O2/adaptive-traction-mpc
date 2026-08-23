function sample = near_extension_protective_mode_quintic( ...
        elapsed_s, duration_s, q0, dq0, qf, dqf, ddq0, ddqf)
%NEAR_EXTENSION_PROTECTIVE_MODE_QUINTIC C2 boundary-matched trajectory.

q0 = q0(:); dq0 = dq0(:); qf = qf(:); dqf = dqf(:);
if nargin < 7, ddq0 = zeros(size(q0)); end
if nargin < 8, ddqf = zeros(size(q0)); end
ddq0 = ddq0(:); ddqf = ddqf(:);
if duration_s <= 0 || ~isfinite(duration_s)
    error('NearExtensionProtectiveMode:InvalidDuration', ...
        'duration_s must be finite and positive.');
end
t = min(max(elapsed_s, 0), duration_s);
T = duration_s;
a0 = q0; a1 = dq0; a2 = ddq0/2;
rhs1 = qf-a0-a1*T-a2*T^2;
rhs2 = dqf-a1-2*a2*T;
% Final acceleration is zero. Solve the three terminal constraints for
% a3:a5 independently for each joint.
matrix = [T^3 T^4 T^5; 3*T^2 4*T^3 5*T^4; ...
    6*T 12*T^2 20*T^3];
coeff = matrix\[rhs1'; rhs2'; (ddqf-2*a2)'];
a3 = coeff(1, :)'; a4 = coeff(2, :)'; a5 = coeff(3, :)';
q = a0+a1*t+a2*t^2+a3*t^3+a4*t^4+a5*t^5;
dq = a1+2*a2*t+3*a3*t^2+4*a4*t^3+5*a5*t^4;
ddq = 2*a2+6*a3*t+12*a4*t^2+20*a5*t^3;
sample = struct('q', q, 'dq', dq, 'ddq', ddq, ...
    'elapsed_s', t, 'complete', elapsed_s >= duration_s);
end
