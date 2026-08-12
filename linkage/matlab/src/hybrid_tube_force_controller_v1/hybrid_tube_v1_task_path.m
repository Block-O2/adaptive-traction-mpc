function sample = hybrid_tube_v1_task_path(s)
%HYBRID_TUBE_V1_TASK_PATH Frozen V2 reference parameterized by progress.

if any(~isfinite(s(:))) || any(s(:) < 0) || any(s(:) > 1)
    error('HybridTubeV1:InvalidProgress', ...
        'Task progress must be finite and lie in [0,1].');
end
s = s(:)';
n = numel(s);
q = zeros(2, n); q_s = zeros(2, n); q_ss = zeros(2, n);
phase = strings(1, n);
for index = 1:n
    [q(:, index), dq, ddq, phase(index)] = ...
        human_two_link_v2_reference(16*s(index), ...
        "slow_passive_flexion_v2");
    q_s(:, index) = 16*dq;
    q_ss(:, index) = 16^2*ddq;
end
sample = struct('s', s, 'q', q, 'q_s', q_s, 'q_ss', q_ss, ...
    'phase', phase);
end
