function segments = r3a_phase_segments(mode,t)
%R3A_PHASE_SEGMENTS Deterministic contiguous segmentation of logged modes.

mode=string(mode(:));t=t(:);
if numel(mode)~=numel(t)
    error('R3A:PhaseSizeMismatch','mode and time must have equal length.');
end
if isempty(mode)
    segments=table(strings(0,1),zeros(0,1),zeros(0,1),zeros(0,1), ...
        zeros(0,1),zeros(0,1),'VariableNames', ...
        {'mode','start_index','end_index','start_time_s','end_time_s', ...
        'sample_count'});return;
end
starts=[1;find(mode(2:end)~=mode(1:end-1))+1];
ends=[starts(2:end)-1;numel(mode)];
segments=table(mode(starts),starts,ends,t(starts),t(ends),ends-starts+1, ...
    'VariableNames',{'mode','start_index','end_index','start_time_s', ...
    'end_time_s','sample_count'});
end
