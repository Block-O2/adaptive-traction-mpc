function classification = bed_supported_v1_transfer_window_classify( ...
        s, bed_available_any, robust_margin_N, supported_robust_margin_N, ...
        threshold_N)
%BED_SUPPORTED_V1_TRANSFER_WINDOW_CLASSIFY Deterministic overlap/gap logic.

s = s(:)';
bed_available_any = logical(bed_available_any(:)');
robust_margin_N = robust_margin_N(:)';
supported_robust_margin_N = supported_robust_margin_N(:)';
if numel(s) ~= numel(bed_available_any) || ...
        numel(s) ~= numel(robust_margin_N) || ...
        numel(s) ~= numel(supported_robust_margin_N) || ...
        any(diff(s) < 0) || ~isscalar(threshold_N) || ...
        ~isfinite(threshold_N)
    error('BedSupportedV1:InvalidTransferWindowInput', ...
        'Transfer-window inputs must be aligned and ordered.');
end
robot_mask = robust_margin_N > threshold_N;
overlap_mask = supported_robust_margin_N > threshold_N;
segments = logical_segments(overlap_mask);
classification = struct();
classification.threshold_N = threshold_N;
classification.robot_mask = robot_mask;
classification.overlap_mask = overlap_mask;
classification.segment_indices = segments;
classification.segment_count = size(segments, 1);
classification.bed_support_end_s = last_or_nan(s, bed_available_any);
classification.robot_entry_s = first_or_nan(s, robot_mask);
classification.overlap_start_s = first_or_nan(s, overlap_mask);
classification.overlap_end_s = last_or_nan(s, overlap_mask);
classification.overlap_duration_s = total_duration(s, segments);
classification.window_exists = any(overlap_mask);
classification.support_gap = ~classification.window_exists && ...
    isfinite(classification.bed_support_end_s) && ...
    isfinite(classification.robot_entry_s) && ...
    classification.robot_entry_s > classification.bed_support_end_s;
if classification.window_exists
    classification.label = "QUASISTATIC_TRANSFER_WINDOW_EXISTS";
elseif classification.support_gap
    classification.label = "SUPPORT_GAP";
elseif ~isfinite(classification.robot_entry_s)
    classification.label = "ROBOT_ONLY_THRESHOLD_NOT_REACHED";
else
    classification.label = "NO_SAME_POSTURE_OVERLAP";
end
end


function segments = logical_segments(mask)
edges = diff([false, mask, false]);
starts = find(edges == 1);
ends = find(edges == -1)-1;
segments = [starts(:), ends(:)];
end


function value = first_or_nan(s, mask)
index = find(mask, 1, 'first');
if isempty(index), value = NaN; else, value = s(index); end
end


function value = last_or_nan(s, mask)
index = find(mask, 1, 'last');
if isempty(index), value = NaN; else, value = s(index); end
end


function duration = total_duration(s, segments)
duration = 0;
for index = 1:size(segments, 1)
    duration = duration+s(segments(index, 2))-s(segments(index, 1));
end
end
