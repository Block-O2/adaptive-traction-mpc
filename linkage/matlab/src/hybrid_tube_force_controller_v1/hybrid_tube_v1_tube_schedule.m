function tube_rad = hybrid_tube_v1_tube_schedule(s, q_path, config)
%HYBRID_TUBE_V1_TUBE_SCHEDULE Continuous near-extension tube envelope.

s = s(:)';
if size(q_path, 1) ~= 2 || size(q_path, 2) ~= numel(s)
    error('HybridTubeV1:InvalidTubeInput', ...
        'q_path must be 2-by-numel(s).');
end
cap = deg2rad(config.tube_cap_deg);
q2_deg = rad2deg(q_path(2, :));
near_extension = quintic01((35-q2_deg)/25);
% The near-extension task set is available at both repeated endpoint poses;
% it narrows continuously through the normal flexion region and re-expands
% continuously on return without a hard angle switch.
phase_weight = 0.15+0.85*near_extension;
tube_rad = cap*[phase_weight; phase_weight];
if cap == 0
    tube_rad(:) = 0;
end
end


function y = quintic01(x)
x = min(max(x, 0), 1);
y = 10*x.^3-15*x.^4+6*x.^5;
end
