function study = bed_supported_v1_robust_suspended_envelope(nominal, config)
%BED_SUPPORTED_V1_ROBUST_SUSPENDED_ENVELOPE Quasistatic liftoff envelope.

if nargin < 2 || isempty(config)
    config = bed_supported_v1_robust_envelope_config();
end
validate_config(config);
human_two_link_v2_validate_parameters(nominal);
nominal_before = nominal;
config_before = config;
bed_config = bed_supported_v1_config(200, 10, "nominal");
calibration = bed_supported_v1_calibrate_hip_height(nominal, bed_config);
uncertainty = bed_supported_v1_registered_uncertainty_set(nominal);

s = regular_grid(0, 1, config.progress_step);
path = bed_supported_v1_geometric_outbound_path(s);
tube_cells = cell(1, numel(config.tube_caps_deg));
for tube_index = 1:numel(config.tube_caps_deg)
    cap_deg = config.tube_caps_deg(tube_index);
    samples = repmat(empty_sample(), 1, numel(s));
    for progress_index = 1:numel(s)
        samples(progress_index) = evaluate_sample(s(progress_index), ...
            cap_deg, config.candidate_step_deg, nominal, uncertainty, ...
            bed_config, calibration.h_hip_m, config);
    end
    tube_cells{tube_index} = make_tube(cap_deg, samples, config);
end
tubes = [tube_cells{:}];

[boundary_summary, boundary_details, refinement] = build_boundaries( ...
    tubes, nominal, uncertainty, bed_config, calibration.h_hip_m, config);
envelope_samples = build_sample_table(tubes, config.force_bounds_N);

if ~isequaln(nominal, nominal_before) || ~isequaln(config, config_before)
    error('BedSupportedV1:EnvelopeMutatedNominalInput', ...
        'The envelope diagnostic mutated its nominal input or config.');
end
study = struct('config', config, 'nominal_parameters', nominal, ...
    'bed_config', bed_config, 'calibration', calibration, ...
    'uncertainty', uncertainty, 'path', path, 'tubes', tubes, ...
    'envelope_samples', envelope_samples, ...
    'boundary_summary', boundary_summary, ...
    'boundary_details', boundary_details, ...
    'refinement', refinement);
end


function validate_config(config)
required = {'force_bounds_N', 'tube_caps_deg', 'robust_thresholds_N', ...
    'progress_step', 'candidate_step_deg', 'refined_progress_step', ...
    'refined_candidate_step_deg', 'boundary_window_s', ...
    'svd_relative_tolerance', 'torque_residual_tolerance_Nm', ...
    'force_tie_tolerance_N', 'convergence_q2_tolerance_deg', ...
    'convergence_margin_tolerance_N', 'run_boundary_refinement'};
if ~isstruct(config) || ~isscalar(config) || ...
        any(~isfield(config, required)) || ...
        any(~ismember(config.force_bounds_N, [80, 120, 200])) || ...
        any(~ismember(config.tube_caps_deg, [0, 5, 10])) || ...
        any(config.robust_thresholds_N < 0) || ...
        config.progress_step <= 0 || config.progress_step > 1 || ...
        config.candidate_step_deg <= 0 || ...
        config.refined_progress_step <= 0 || ...
        config.refined_progress_step > config.progress_step || ...
        config.refined_candidate_step_deg <= 0 || ...
        config.refined_candidate_step_deg > config.candidate_step_deg
    error('BedSupportedV1:InvalidRobustEnvelopeConfig', ...
        'Robust envelope configuration is invalid.');
end
end


function sample = evaluate_sample(s, cap_deg, candidate_step_deg, ...
        nominal, uncertainty, bed_config, h_hip, config)
path = bed_supported_v1_geometric_outbound_path(s);
q_path = path.q;
tube_config = hybrid_tube_v1_config(200, cap_deg);
tube_rad = hybrid_tube_v1_tube_schedule(s, q_path, tube_config);
tube_deg = rad2deg(tube_rad);
q_candidates_deg = candidate_grid(rad2deg(q_path), tube_deg, ...
    candidate_step_deg, nominal);
records = repmat(empty_candidate(), 1, size(q_candidates_deg, 2));
for candidate_index = 1:size(q_candidates_deg, 2)
    q = deg2rad(q_candidates_deg(:, candidate_index));
    records(candidate_index) = evaluate_candidate(q, q_path, nominal, ...
        uncertainty, bed_config, h_hip, config);
end
eligible = [records.eligible];
supported = eligible & [records.bed_available];
sample = empty_sample();
sample.s = s;
sample.q_path_deg = rad2deg(q_path);
sample.tube_half_width_deg = tube_deg;
sample.candidate_count = numel(records);
sample.eligible_count = sum(eligible);
sample.soft_limit_active_count = sum([records.soft_limit_active]);
sample.nominal = select_candidate(records, eligible, "nominal", config);
sample.robust = select_candidate(records, eligible, "robust", config);
sample.supported_robust = select_candidate(records, supported, ...
    "robust", config);
sample.bed_support = select_candidate(records, supported, "bed", config);
sample.bed_available_any = any(supported);
if any(supported)
    sample.maximum_bed_force_N = max([records(supported).bed_total_force_N]);
else
    sample.maximum_bed_force_N = 0;
end
path_bed = bed_supported_v1_contact(q_path, zeros(2,1), h_hip, ...
    nominal, bed_config);
sample.path_bed_total_force_N = path_bed.total_normal_force_N;
sample.path_bed_active_count = sum(path_bed.active);
sample.path_bed_contact_point_count = sum(path_bed.active);
sample.path_bed_available = path_bed.total_normal_force_N > ...
    bed_config.contact_force_threshold_N;
sample.path_bed_gap_m = path_bed.gap_m;
sample.path_bed_penetration_m = path_bed.penetration_m;
sample.path_bed_generalized_torque_Nm = path_bed.generalized_torque_Nm;
end


function record = evaluate_candidate(q, q_path, nominal, uncertainty, ...
        bed_config, h_hip, config)
robust = bed_supported_v1_robust_hold_point(q, nominal, uncertainty, ...
    config.force_bounds_N, config.svd_relative_tolerance);
bed = bed_supported_v1_contact(q, zeros(2,1), h_hip, nominal, bed_config);
point = robust.nominal;
record = empty_candidate();
record.q_deg = rad2deg(q);
record.path_deviation_norm_deg = norm(rad2deg(q-q_path));
record.eligible = q(2) > 0 && ~point.soft_limit_active && ...
    ~point.rank_deficient && isfinite(point.force_norm_inf_N) && ...
    point.exact_torque_residual_norm_Nm <= ...
        config.torque_residual_tolerance_Nm;
record.soft_limit_active = point.soft_limit_active;
record.nominal_required_force_N = point.force_norm_inf_N;
record.nominal_force_local_N = point.force_local_N;
record.nominal_force_norm_2_N = point.force_norm_2_N;
record.robust_required_force_N = robust.worst_required_force_N;
record.robust_force_local_N = robust.worst_force_local_N;
record.worst_case_id = robust.worst_case_id;
record.sigma_min = point.sigma_min;
record.condition_number = point.condition_number;
record.torque_residual_norm_Nm = point.exact_torque_residual_norm_Nm;
record.soft_limit_clearance_deg = rad2deg( ...
    point.minimum_soft_limit_margin_rad);
record.bed_total_force_N = bed.total_normal_force_N;
record.bed_active_count = sum(bed.active);
record.bed_contact_point_count = sum(bed.active);
record.bed_available = bed.total_normal_force_N > ...
    bed_config.contact_force_threshold_N;
record.bed_gap_m = bed.gap_m;
record.bed_penetration_m = bed.penetration_m;
record.bed_generalized_torque_Nm = bed.generalized_torque_Nm;
end


function selected = select_candidate(records, mask, objective, config)
selected = empty_selected();
indices = find(mask);
if isempty(indices), return; end
if objective == "nominal"
    required = [records(indices).nominal_required_force_N]';
elseif objective == "bed"
    required = -[records(indices).bed_total_force_N]';
else
    required = [records(indices).robust_required_force_N]';
end
deviation = [records(indices).path_deviation_norm_deg]';
q = [records(indices).q_deg]';
[~, order] = sortrows([round(required/config.force_tie_tolerance_N)* ...
    config.force_tie_tolerance_N, deviation, q], [1, 2, 3, 4]);
record = records(indices(order(1)));
selected.found = true;
selected.q_deg = record.q_deg;
selected.path_deviation_norm_deg = record.path_deviation_norm_deg;
selected.nominal_required_force_N = record.nominal_required_force_N;
selected.nominal_force_local_N = record.nominal_force_local_N;
selected.nominal_force_norm_2_N = record.nominal_force_norm_2_N;
selected.robust_required_force_N = record.robust_required_force_N;
selected.robust_force_local_N = record.robust_force_local_N;
selected.worst_case_id = record.worst_case_id;
selected.sigma_min = record.sigma_min;
selected.condition_number = record.condition_number;
selected.torque_residual_norm_Nm = record.torque_residual_norm_Nm;
selected.soft_limit_active = record.soft_limit_active;
selected.soft_limit_clearance_deg = record.soft_limit_clearance_deg;
selected.bed_total_force_N = record.bed_total_force_N;
selected.bed_active_count = record.bed_active_count;
selected.bed_contact_point_count = record.bed_contact_point_count;
selected.bed_available = record.bed_available;
selected.bed_gap_m = record.bed_gap_m;
selected.bed_penetration_m = record.bed_penetration_m;
selected.bed_generalized_torque_Nm = record.bed_generalized_torque_Nm;
end


function tube = make_tube(cap_deg, samples, config)
s = [samples.s];
nominal_required = arrayfun(@(x) x.nominal.nominal_required_force_N, ...
    samples);
robust_required = arrayfun(@(x) x.robust.robust_required_force_N, samples);
supported_required = arrayfun(@(x) ...
    x.supported_robust.robust_required_force_N, samples);
bed_available = [samples.bed_available_any];
class_cells = cell(numel(config.force_bounds_N), ...
    numel(config.robust_thresholds_N));
for bound_index = 1:numel(config.force_bounds_N)
    bound_N = config.force_bounds_N(bound_index);
    for threshold_index = 1:numel(config.robust_thresholds_N)
        threshold_N = config.robust_thresholds_N(threshold_index);
        class_cells{bound_index, threshold_index} = ...
            bed_supported_v1_transfer_window_classify(s, bed_available, ...
            bound_N-robust_required, bound_N-supported_required, ...
            threshold_N);
    end
end
tube = struct('cap_deg', cap_deg, 's', s, 'samples', samples, ...
    'nominal_required_force_N', nominal_required, ...
    'robust_required_force_N', robust_required, ...
    'supported_robust_required_force_N', supported_required, ...
    'bed_available_any', bed_available, ...
    'path_bed_available', [samples.path_bed_available], ...
    'path_bed_total_force_N', [samples.path_bed_total_force_N], ...
    'classifications', {class_cells});
end


function [summary, details, refinement] = build_boundaries(tubes, nominal, ...
        uncertainty, bed_config, h_hip, config)
summary_rows = repmat(empty_summary_row(), ...
    numel(tubes)*numel(config.force_bounds_N), 1);
detail_rows = repmat(empty_detail_row(), 0, 1);
refinement_rows = repmat(empty_refinement_row(), 0, 1);
summary_index = 0;
for tube_index = 1:numel(tubes)
    tube = tubes(tube_index);
    cache = containers.Map('KeyType', 'char', 'ValueType', 'any');
    for bound_index = 1:numel(config.force_bounds_N)
        bound_N = config.force_bounds_N(bound_index);
        summary_index = summary_index+1;
        row = empty_summary_row();
        row.force_bound_N = bound_N;
        row.tube_cap_deg = tube.cap_deg;
        [entry, cache] = boundary_entry(tube, "nominal", bound_N, 0, ...
            nominal, uncertainty, bed_config, h_hip, config, cache);
        row.nominal_0N_entry_s = entry.refined_entry_s;
        detail_rows(end+1) = entry; %#ok<AGROW>
        for threshold_N = config.robust_thresholds_N
            [entry, cache] = boundary_entry(tube, "robust", bound_N, ...
                threshold_N, nominal, uncertainty, bed_config, h_hip, ...
                config, cache);
            detail_rows(end+1) = entry; %#ok<AGROW>
            row = assign_robust_entry(row, threshold_N, ...
                entry.refined_entry_s);
        end
        classification = tube.classifications{bound_index, 1};
        [bed_end, cache] = boundary_exit(tube, "bed", bound_N, 0, ...
            nominal, uncertainty, bed_config, h_hip, config, cache);
        detail_rows(end+1) = bed_end; %#ok<AGROW>
        row.bed_support_end_s = bed_end.refined_entry_s;
        for threshold_N = config.robust_thresholds_N
            [overlap_start, cache] = boundary_entry(tube, ...
                "supported_robust", bound_N, threshold_N, nominal, ...
                uncertainty, bed_config, h_hip, config, cache);
            overlap_start.boundary_type = "overlap_start";
            detail_rows(end+1) = overlap_start; %#ok<AGROW>
            [overlap_end, cache] = boundary_exit(tube, ...
                "supported_robust", bound_N, threshold_N, nominal, ...
                uncertainty, bed_config, h_hip, config, cache);
            overlap_end.boundary_type = "overlap_end";
            detail_rows(end+1) = overlap_end; %#ok<AGROW>
            if threshold_N == 0
                row.overlap_start_s = overlap_start.refined_entry_s;
                row.overlap_end_s = overlap_end.refined_entry_s;
            end
        end
        row.overlap_segment_count = classification.segment_count;
        if isfinite(row.overlap_start_s) && isfinite(row.overlap_end_s)
            row.overlap_duration_s = row.overlap_end_s- ...
                row.overlap_start_s;
            row.support_gap_flag = false;
            row.classification = "QUASISTATIC_TRANSFER_WINDOW_EXISTS";
        else
            row.overlap_duration_s = 0;
            row.support_gap_flag = isfinite(row.robust_0N_entry_s) && ...
                isfinite(row.bed_support_end_s) && ...
                row.robust_0N_entry_s > row.bed_support_end_s;
            if row.support_gap_flag
                row.classification = "SUPPORT_GAP";
            elseif ~isfinite(row.robust_0N_entry_s)
                row.classification = "ROBOT_ONLY_THRESHOLD_NOT_REACHED";
            else
                row.classification = "NO_SAME_POSTURE_OVERLAP";
            end
        end
        summary_rows(summary_index) = row;
    end
    for cache_key = string(keys(cache))
        item = cache(char(cache_key));
        refinement_item = struct( ...
            'tube_cap_deg', tube.cap_deg, 's', item.s, ...
            'candidate_step_deg', config.refined_candidate_step_deg, ...
            'sample', item);
        refinement_rows(end+1) = refinement_item; %#ok<AGROW>
    end
end
summary = struct2table(summary_rows);
details = struct2table(detail_rows);
refinement = refinement_rows;
end


function [entry, cache] = boundary_exit(tube, type, bound_N, ...
        threshold_N, nominal, uncertainty, bed_config, h_hip, config, cache)
if type == "bed"
    mask = tube.bed_available_any;
else
    mask = bound_N-tube.supported_robust_required_force_N > threshold_N;
end
coarse_index = find(mask, 1, 'last');
entry = empty_detail_row();
entry.force_bound_N = bound_N;
entry.tube_cap_deg = tube.cap_deg;
entry.boundary_type = type+"_end";
entry.threshold_N = threshold_N;
if isempty(coarse_index), return; end
entry.reached = true;
entry.coarse_entry_s = tube.s(coarse_index);
coarse_sample = tube.samples(coarse_index);
if type == "bed"
    coarse_selected = coarse_sample.bed_support;
else
    coarse_selected = coarse_sample.supported_robust;
end
entry = fill_detail(entry, coarse_sample, coarse_selected, bound_N, ...
    threshold_N, false);
if ~config.run_boundary_refinement || coarse_index == numel(tube.s)
    entry.refined_entry_s = entry.coarse_entry_s;
    entry.convergence_q2_delta_deg = 0;
    entry.convergence_margin_delta_N = 0;
    entry.mechanical_convergence = true;
    return;
end
lower = tube.s(coarse_index);
upper = min(1, lower+config.boundary_window_s);
fine_s = regular_grid(lower, upper, config.refined_progress_step);
fine_mask = false(size(fine_s));
fine_samples = repmat(empty_sample(), 1, numel(fine_s));
for fine_index = 1:numel(fine_s)
    key = sprintf('%.12f', fine_s(fine_index));
    if isKey(cache, key)
        fine_samples(fine_index) = cache(key);
    else
        fine_samples(fine_index) = evaluate_sample(fine_s(fine_index), ...
            tube.cap_deg, config.refined_candidate_step_deg, nominal, ...
            uncertainty, bed_config, h_hip, config);
        cache(key) = fine_samples(fine_index);
    end
    if type == "bed"
        fine_mask(fine_index) = fine_samples(fine_index).bed_available_any;
    else
        fine_mask(fine_index) = bound_N- ...
            fine_samples(fine_index).supported_robust.robust_required_force_N ...
            > threshold_N;
    end
end
fine_index = find(fine_mask, 1, 'last');
if isempty(fine_index)
    refined_sample = coarse_sample;
    refined_selected = coarse_selected;
else
    refined_sample = fine_samples(fine_index);
    if type == "bed"
        refined_selected = refined_sample.bed_support;
    else
        refined_selected = refined_sample.supported_robust;
    end
end
entry = fill_detail(entry, refined_sample, refined_selected, bound_N, ...
    threshold_N, true);
entry.convergence_q2_delta_deg = abs( ...
    refined_selected.q_deg(2)-coarse_selected.q_deg(2));
if type == "bed"
    entry.convergence_margin_delta_N = abs( ...
        refined_selected.bed_total_force_N- ...
        coarse_selected.bed_total_force_N);
else
    entry.convergence_margin_delta_N = abs( ...
        (bound_N-refined_selected.robust_required_force_N)- ...
        (bound_N-coarse_selected.robust_required_force_N));
end
entry.mechanical_convergence = ...
    entry.convergence_q2_delta_deg <= ...
        config.convergence_q2_tolerance_deg && ...
    entry.convergence_margin_delta_N <= ...
        config.convergence_margin_tolerance_N;
end


function [entry, cache] = boundary_entry(tube, type, bound_N, ...
        threshold_N, nominal, uncertainty, bed_config, h_hip, config, cache)
switch type
    case "nominal"
        required = tube.nominal_required_force_N;
    case "robust"
        required = tube.robust_required_force_N;
    case "supported_robust"
        required = tube.supported_robust_required_force_N;
    otherwise
        error('BedSupportedV1:UnknownEnvelopeBoundary', ...
            'Unknown boundary type.');
end
margin = bound_N-required;
if type == "supported_robust"
    coarse_index = find(margin > threshold_N, 1, 'first');
else
    coarse_index = find(margin >= threshold_N, 1, 'first');
end
entry = empty_detail_row();
entry.force_bound_N = bound_N;
entry.tube_cap_deg = tube.cap_deg;
entry.boundary_type = type;
entry.threshold_N = threshold_N;
if isempty(coarse_index), return; end
entry.reached = true;
entry.coarse_entry_s = tube.s(coarse_index);
coarse_sample = tube.samples(coarse_index);
selected = select_from_sample(coarse_sample, type);
entry = fill_detail(entry, coarse_sample, selected, bound_N, ...
    threshold_N, false);
if ~config.run_boundary_refinement || coarse_index == 1
    entry.refined_entry_s = entry.coarse_entry_s;
    entry.convergence_q2_delta_deg = 0;
    entry.convergence_margin_delta_N = 0;
    entry.mechanical_convergence = true;
    return;
end
lower = max(0, tube.s(coarse_index)-config.boundary_window_s);
upper = tube.s(coarse_index);
fine_s = regular_grid(lower, upper, config.refined_progress_step);
fine_margin = -Inf(size(fine_s));
fine_samples = repmat(empty_sample(), 1, numel(fine_s));
for fine_index = 1:numel(fine_s)
    key = sprintf('%.12f', fine_s(fine_index));
    if isKey(cache, key)
        fine_samples(fine_index) = cache(key);
    else
        fine_samples(fine_index) = evaluate_sample(fine_s(fine_index), ...
            tube.cap_deg, config.refined_candidate_step_deg, nominal, ...
            uncertainty, bed_config, h_hip, config);
        cache(key) = fine_samples(fine_index);
    end
    fine_selected = select_from_sample(fine_samples(fine_index), type);
    fine_margin(fine_index) = bound_N-required_from_selected( ...
        fine_selected, type);
end
if type == "supported_robust"
    fine_index = find(fine_margin > threshold_N, 1, 'first');
else
    fine_index = find(fine_margin >= threshold_N, 1, 'first');
end
if isempty(fine_index)
    entry.refined_entry_s = entry.coarse_entry_s;
    refined_sample = coarse_sample;
    refined_selected = selected;
else
    entry.refined_entry_s = fine_s(fine_index);
    refined_sample = fine_samples(fine_index);
    refined_selected = select_from_sample(refined_sample, type);
end
entry = fill_detail(entry, refined_sample, refined_selected, bound_N, ...
    threshold_N, true);
entry.convergence_q2_delta_deg = abs( ...
    refined_selected.q_deg(2)-selected.q_deg(2));
entry.convergence_margin_delta_N = abs( ...
    (bound_N-required_from_selected(refined_selected, type))- ...
    (bound_N-required_from_selected(selected, type)));
entry.mechanical_convergence = ...
    entry.convergence_q2_delta_deg <= ...
        config.convergence_q2_tolerance_deg && ...
    entry.convergence_margin_delta_N <= ...
        config.convergence_margin_tolerance_N;
end


function selected = select_from_sample(sample, type)
if type == "nominal"
    selected = sample.nominal;
elseif type == "robust"
    selected = sample.robust;
else
    selected = sample.supported_robust;
end
end


function required = required_from_selected(selected, type)
if ~selected.found
    required = Inf;
elseif type == "nominal"
    required = selected.nominal_required_force_N;
else
    required = selected.robust_required_force_N;
end
end


function entry = fill_detail(entry, sample, selected, bound_N, ...
        threshold_N, refined)
if ~selected.found, return; end
if refined
    entry.refined_entry_s = sample.s;
end
entry.q_path1_deg = sample.q_path_deg(1);
entry.q_path2_deg = sample.q_path_deg(2);
entry.q_star1_deg = selected.q_deg(1);
entry.q_star2_deg = selected.q_deg(2);
entry.F_parallel_N = selected.robust_force_local_N(1);
entry.F_perp_N = selected.robust_force_local_N(2);
entry.force_norm_2_N = norm(selected.robust_force_local_N, 2);
entry.force_norm_inf_N = selected.robust_required_force_N;
entry.margin_N = bound_N-selected.robust_required_force_N;
if entry.boundary_type == "nominal"
    entry.F_parallel_N = selected.nominal_force_local_N(1);
    entry.F_perp_N = selected.nominal_force_local_N(2);
    entry.force_norm_2_N = selected.nominal_force_norm_2_N;
    entry.force_norm_inf_N = selected.nominal_required_force_N;
    entry.margin_N = bound_N-selected.nominal_required_force_N;
    entry.worst_case_id = "nominal";
else
    entry.worst_case_id = selected.worst_case_id;
end
entry.sigma_min = selected.sigma_min;
entry.condition_number = selected.condition_number;
entry.torque_residual_norm_Nm = selected.torque_residual_norm_Nm;
entry.soft_limit_clearance_deg = selected.soft_limit_clearance_deg;
entry.bed_total_force_N = selected.bed_total_force_N;
entry.bed_active_count = selected.bed_active_count;
entry.threshold_N = threshold_N;
end


function row = assign_robust_entry(row, threshold_N, value)
field = sprintf('robust_%gN_entry_s', threshold_N);
row.(field) = value;
end


function table_data = build_sample_table(tubes, bounds)
rows = repmat(empty_sample_row(), ...
    sum(arrayfun(@(x) numel(x.samples), tubes))*numel(bounds), 1);
row_index = 0;
for tube = tubes
    for sample = tube.samples
        for bound_N = bounds
            row_index = row_index+1;
            row = empty_sample_row();
            row.s = sample.s;
            row.force_bound_N = bound_N;
            row.tube_cap_deg = tube.cap_deg;
            row.q_path1_deg = sample.q_path_deg(1);
            row.q_path2_deg = sample.q_path_deg(2);
            row.tube_half_width1_deg = sample.tube_half_width_deg(1);
            row.tube_half_width2_deg = sample.tube_half_width_deg(2);
            row.nominal_required_force_N = ...
                sample.nominal.nominal_required_force_N;
            row.nominal_margin_N = bound_N-row.nominal_required_force_N;
            row.robust_required_force_N = ...
                sample.robust.robust_required_force_N;
            row.robust_margin_N = bound_N-row.robust_required_force_N;
            row.supported_robust_required_force_N = ...
                sample.supported_robust.robust_required_force_N;
            row.supported_robust_margin_N = ...
                bound_N-row.supported_robust_required_force_N;
            row.q_star_robust1_deg = sample.robust.q_deg(1);
            row.q_star_robust2_deg = sample.robust.q_deg(2);
            row.robust_F_parallel_N = ...
                sample.robust.robust_force_local_N(1);
            row.robust_F_perp_N = ...
                sample.robust.robust_force_local_N(2);
            row.robust_force_norm_2_N = ...
                norm(sample.robust.robust_force_local_N, 2);
            row.worst_case_id = sample.robust.worst_case_id;
            row.sigma_min = sample.robust.sigma_min;
            row.condition_number = sample.robust.condition_number;
            row.torque_residual_norm_Nm = ...
                sample.robust.torque_residual_norm_Nm;
            row.soft_limit_clearance_deg = ...
                sample.robust.soft_limit_clearance_deg;
            row.path_bed_total_force_N = sample.path_bed_total_force_N;
            row.path_bed_active_count = sample.path_bed_active_count;
            row.path_bed_available = sample.path_bed_available;
            row.bed_available_any = sample.bed_available_any;
            row.supported_q1_deg = sample.supported_robust.q_deg(1);
            row.supported_q2_deg = sample.supported_robust.q_deg(2);
            row.supported_bed_force_N = ...
                sample.supported_robust.bed_total_force_N;
            row.supported_bed_active_count = ...
                sample.supported_robust.bed_active_count;
            rows(row_index) = row;
        end
    end
end
table_data = struct2table(rows);
end


function q_candidates_deg = candidate_grid(q_path_deg, tube_deg, step, p)
if all(tube_deg == 0)
    q_candidates_deg = q_path_deg;
    return;
end
offset1 = offset_grid(tube_deg(1), step);
offset2 = offset_grid(tube_deg(2), step);
[grid1, grid2] = meshgrid(offset1, offset2);
q_candidates_deg = q_path_deg+[grid1(:)'; grid2(:)'];
q_candidates_deg(:, end+1) = q_path_deg;
lower = rad2deg(p.q_min);
upper = rad2deg(p.q_max);
valid = all(q_candidates_deg >= lower-1e-10 & ...
    q_candidates_deg <= upper+1e-10, 1) & q_candidates_deg(2,:) > 0;
q_candidates_deg = q_candidates_deg(:, valid);
q_candidates_deg = unique(round(q_candidates_deg', 10), 'rows', ...
    'stable')';
end


function values = offset_grid(cap, step)
if cap <= 0, values = 0; return; end
values = -cap:step:cap;
values = unique(round([values, -cap, 0, cap], 10));
end


function values = regular_grid(lower, upper, step)
values = lower:step:upper;
if isempty(values) || values(end) < upper-1e-12
    values(end+1) = upper;
end
values = unique(round(values, 12));
end


function value = nan_vector(n)
value = NaN(n, 1);
end


function candidate = empty_candidate()
candidate = struct('q_deg', nan_vector(2), ...
    'path_deviation_norm_deg', NaN, 'eligible', false, ...
    'soft_limit_active', false, 'nominal_required_force_N', NaN, ...
    'nominal_force_local_N', nan_vector(2), ...
    'nominal_force_norm_2_N', NaN, 'robust_required_force_N', NaN, ...
    'robust_force_local_N', nan_vector(2), 'worst_case_id', "", ...
    'sigma_min', NaN, 'condition_number', NaN, ...
    'torque_residual_norm_Nm', NaN, 'soft_limit_clearance_deg', NaN, ...
    'bed_total_force_N', NaN, 'bed_active_count', 0, ...
    'bed_contact_point_count', 0, 'bed_available', false, ...
    'bed_gap_m', nan_vector(8)', 'bed_penetration_m', nan_vector(8)', ...
    'bed_generalized_torque_Nm', nan_vector(2));
end


function selected = empty_selected()
selected = struct('found', false, 'q_deg', nan_vector(2), ...
    'path_deviation_norm_deg', NaN, 'nominal_required_force_N', Inf, ...
    'nominal_force_local_N', nan_vector(2), ...
    'nominal_force_norm_2_N', NaN, 'robust_required_force_N', Inf, ...
    'robust_force_local_N', nan_vector(2), 'worst_case_id', "", ...
    'sigma_min', NaN, 'condition_number', NaN, ...
    'torque_residual_norm_Nm', NaN, 'soft_limit_active', false, ...
    'soft_limit_clearance_deg', NaN, 'bed_total_force_N', NaN, ...
    'bed_active_count', 0, 'bed_contact_point_count', 0, ...
    'bed_available', false, 'bed_gap_m', nan_vector(8)', ...
    'bed_penetration_m', nan_vector(8)', ...
    'bed_generalized_torque_Nm', nan_vector(2));
end


function sample = empty_sample()
sample = struct('s', NaN, 'q_path_deg', nan_vector(2), ...
    'tube_half_width_deg', nan_vector(2), 'candidate_count', 0, ...
    'eligible_count', 0, 'soft_limit_active_count', 0, ...
    'nominal', empty_selected(), 'robust', empty_selected(), ...
    'supported_robust', empty_selected(), ...
    'bed_support', empty_selected(), 'bed_available_any', false, ...
    'maximum_bed_force_N', NaN, 'path_bed_total_force_N', NaN, ...
    'path_bed_active_count', 0, 'path_bed_contact_point_count', 0, ...
    'path_bed_available', false, 'path_bed_gap_m', nan_vector(8)', ...
    'path_bed_penetration_m', nan_vector(8)', ...
    'path_bed_generalized_torque_Nm', nan_vector(2));
end


function row = empty_summary_row()
row = struct('force_bound_N', NaN, 'tube_cap_deg', NaN, ...
    'nominal_0N_entry_s', NaN, 'robust_0N_entry_s', NaN, ...
    'robust_5N_entry_s', NaN, 'robust_10N_entry_s', NaN, ...
    'robust_20N_entry_s', NaN, 'bed_support_end_s', NaN, ...
    'overlap_start_s', NaN, 'overlap_end_s', NaN, ...
    'overlap_duration_s', 0, 'overlap_segment_count', 0, ...
    'support_gap_flag', false, 'classification', "");
end


function row = empty_detail_row()
row = struct('force_bound_N', NaN, 'tube_cap_deg', NaN, ...
    'boundary_type', "", 'threshold_N', NaN, 'reached', false, ...
    'coarse_entry_s', NaN, 'refined_entry_s', NaN, ...
    'q_path1_deg', NaN, 'q_path2_deg', NaN, ...
    'q_star1_deg', NaN, 'q_star2_deg', NaN, ...
    'F_parallel_N', NaN, 'F_perp_N', NaN, ...
    'force_norm_2_N', NaN, 'force_norm_inf_N', NaN, ...
    'margin_N', NaN, 'worst_case_id', "", 'sigma_min', NaN, ...
    'condition_number', NaN, 'torque_residual_norm_Nm', NaN, ...
    'soft_limit_clearance_deg', NaN, 'bed_total_force_N', NaN, ...
    'bed_active_count', 0, 'convergence_q2_delta_deg', NaN, ...
    'convergence_margin_delta_N', NaN, ...
    'mechanical_convergence', false);
end


function row = empty_refinement_row()
row = struct('tube_cap_deg', NaN, 's', NaN, ...
    'candidate_step_deg', NaN, 'sample', empty_sample());
end


function row = empty_sample_row()
row = struct('s', NaN, 'force_bound_N', NaN, 'tube_cap_deg', NaN, ...
    'q_path1_deg', NaN, 'q_path2_deg', NaN, ...
    'tube_half_width1_deg', NaN, 'tube_half_width2_deg', NaN, ...
    'nominal_required_force_N', NaN, 'nominal_margin_N', NaN, ...
    'robust_required_force_N', NaN, 'robust_margin_N', NaN, ...
    'supported_robust_required_force_N', NaN, ...
    'supported_robust_margin_N', NaN, 'q_star_robust1_deg', NaN, ...
    'q_star_robust2_deg', NaN, 'robust_F_parallel_N', NaN, ...
    'robust_F_perp_N', NaN, 'robust_force_norm_2_N', NaN, ...
    'worst_case_id', "", 'sigma_min', NaN, ...
    'condition_number', NaN, 'torque_residual_norm_Nm', NaN, ...
    'soft_limit_clearance_deg', NaN, 'path_bed_total_force_N', NaN, ...
    'path_bed_active_count', 0, 'path_bed_available', false, ...
    'bed_available_any', false, 'supported_q1_deg', NaN, ...
    'supported_q2_deg', NaN, 'supported_bed_force_N', NaN, ...
    'supported_bed_active_count', 0);
end
