function path = bed_supported_v1_geometric_outbound_path(s)
%BED_SUPPORTED_V1_GEOMETRIC_OUTBOUND_PATH Frozen V2 outbound geometry.
%
% Progress parameterizes the geometric line from the retained start to peak
% posture. Time derivatives are deliberately absent: this is a qdot=qddot=0
% diagnostic, not a replay of the dynamic reference timing.

s = s(:)';
if any(~isfinite(s)) || any(s < 0) || any(s > 1)
    error('BedSupportedV1:InvalidEnvelopeProgress', ...
        'Envelope progress must be finite and lie in [0,1].');
end
[q_start, ~, ~, ~, start_progress] = ...
    human_two_link_v2_reference(0, "slow_passive_flexion_v2");
[q_peak, ~, ~, ~, peak_progress] = ...
    human_two_link_v2_reference(7.5, "slow_passive_flexion_v2");
if abs(start_progress) > 1e-14 || abs(peak_progress-1) > 1e-14
    error('BedSupportedV1:ReferenceGeometryChanged', ...
        'The retained V2 start/peak progress contract changed.');
end
q = q_start+(q_peak-q_start).*s;
path = struct('s', s, 'q', q, 'q_start', q_start, 'q_peak', q_peak);
end
