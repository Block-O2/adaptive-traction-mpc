function study = bed_supported_v1_robust_force_margin_sensitivity( ...
        nominal, config)
%BED_SUPPORTED_V1_ROBUST_FORCE_MARGIN_SENSITIVITY Quasistatic robustness study.

human_two_link_v2_validate_parameters(nominal);
case_count = numel(config.one_at_a_time_cases);
posture_count = numel(config.posture_names);
nominal_margin = NaN(1, posture_count);
for posture_index = 1:posture_count
    point = evaluate_point(config.postures_deg(:, posture_index), nominal, ...
        config);
    nominal_margin(posture_index) = point.force_margin_N;
end

rows = repmat(empty_row(), case_count*posture_count, 1);
row_index = 0;
for case_index = 1:case_count
    item = config.one_at_a_time_cases(case_index);
    parameters = bed_supported_v1_parameter_override(nominal, item.override);
    for posture_index = 1:posture_count
        row_index = row_index+1;
        point = evaluate_point(config.postures_deg(:, posture_index), ...
            parameters, config);
        rows(row_index) = result_row("one_at_a_time", item.case_id, ...
            item.family, item.perturbation, "", posture_index, point, ...
            nominal_margin(posture_index), item.override, config);
    end
end

[low_choices, full_choices] = choose_adverse_directions(rows, config);
combined = build_combined_cases(low_choices, full_choices, rows, config);
combined_rows = repmat(empty_row(), ...
    numel(combined)*posture_count, 1);
row_index = 0;
for case_index = 1:numel(combined)
    parameters = bed_supported_v1_parameter_override( ...
        nominal, combined(case_index).override);
    for posture_index = 1:posture_count
        row_index = row_index+1;
        point = evaluate_point(config.postures_deg(:, posture_index), ...
            parameters, config);
        combined_rows(row_index) = result_row("combined", ...
            combined(case_index).case_id, "combined", ...
            combined(case_index).perturbation, ...
            combined(case_index).source_case_ids, posture_index, point, ...
            nominal_margin(posture_index), combined(case_index).override, ...
            config);
    end
end

all_rows = [rows; combined_rows];
study = struct();
study.config = config;
study.nominal_parameters = nominal;
study.nominal_margin_N = nominal_margin;
study.one_at_a_time_rows = rows;
study.low_adverse_choices = low_choices;
study.full_adverse_choices = full_choices;
study.combined_cases = combined;
study.combined_rows = combined_rows;
study.rows = all_rows;
study.results_table = struct2table(all_rows);
end


function point = evaluate_point(q_deg, parameters, config)
point = bed_supported_v1_force_margin_point(deg2rad(q_deg), parameters, ...
    config.force_bound_N, config.svd_relative_tolerance);
end


function row = result_row(layer, case_id, family, perturbation, sources, ...
        posture_index, point, nominal_margin, override, config)
row = empty_row();
row.layer = string(layer);
row.case_id = string(case_id);
row.family = string(family);
row.perturbation = string(perturbation);
row.source_case_ids = string(sources);
row.posture_name = config.posture_names(posture_index);
row.q1_deg = config.postures_deg(1, posture_index);
row.q2_deg = config.postures_deg(2, posture_index);
row.F_parallel_N = point.F_parallel_N;
row.F_perp_N = point.F_perp_N;
row.force_norm_2_N = point.force_norm_2_N;
row.force_norm_inf_N = point.force_norm_inf_N;
row.force_margin_N = point.force_margin_N;
row.delta_margin_N = point.force_margin_N-nominal_margin;
row.torque_residual_norm_Nm = point.exact_torque_residual_norm_Nm;
row.sigma_min = point.sigma_min;
row.condition_number = point.condition_number;
row.feasible_200N = point.exact_feasible;
row.margin_ge_10N = point.force_margin_N >= 10;
row.margin_ge_5N = point.force_margin_N >= config.guard_N;
row.margin_positive_below_5N = point.force_margin_N > 0 && ...
    point.force_margin_N < config.guard_N;
row.margin_nonpositive = point.force_margin_N <= 0;
row.mass_scale = override.mass_scale;
row.lc1_scale = override.lc1_scale;
row.lc2_scale = override.lc2_scale;
row.K_scale = override.K_scale;
row.q_rest1_offset_deg = rad2deg(override.q_rest_offset_rad(1));
row.q_rest2_offset_deg = rad2deg(override.q_rest_offset_rad(2));
row.sc_scale = override.sc_scale;
end


function [low_choices, full_choices] = choose_adverse_directions(rows, config)
families = config.combined_family_order;
low_choices = repmat(empty_choice(), numel(families), 1);
full_choices = repmat(empty_choice(), numel(families), 1);
for family_index = 1:numel(families)
    family = families(family_index);
    if family == "q_rest"
        low_tier = 2;
        full_tier = 2;
    else
        low_tier = 1;
        full_tier = 2;
    end
    low_choices(family_index) = choose_one(rows, config, family, low_tier);
    full_choices(family_index) = choose_one(rows, config, family, full_tier);
end
end


function choice = choose_one(rows, config, family, tier)
cases = config.one_at_a_time_cases;
eligible = [cases.family] == family & [cases.tier] == tier;
candidate_indices = find(eligible);
margins = NaN(size(candidate_indices));
for index = 1:numel(candidate_indices)
    case_id = cases(candidate_indices(index)).case_id;
    match = [rows.case_id] == case_id & ...
        [rows.posture_name] == config.primary_posture_name;
    margins(index) = rows(find(match, 1)).force_margin_N;
end
[margin, local_index] = min(margins);
item = cases(candidate_indices(local_index));
choice = empty_choice();
choice.family = family;
choice.case_id = item.case_id;
choice.margin_at_primary_N = margin;
choice.override = item.override;
end


function combined = build_combined_cases(low_choices, full_choices, rows, config)
primary_nominal = rows([rows.case_id] == "nominal" & ...
    [rows.posture_name] == config.primary_posture_name).force_margin_N;
erosion = primary_nominal-[low_choices.margin_at_primary_N];
[~, order] = sort(erosion, 'descend');
mild_choices = low_choices(order(1:config.mild_family_count));

combined = repmat(empty_combined(), 3, 1);
combined(1) = make_combined("mild", mild_choices);
combined(2) = make_combined("moderate", low_choices);
combined(3) = make_combined("adverse", full_choices);
end


function item = make_combined(name, choices)
item = empty_combined();
item.case_id = string(name);
item.perturbation = string(name)+" deterministic combination";
item.source_case_ids = strjoin([choices.case_id], ";");
item.override = combine_overrides([choices.override]);
end


function combined = combine_overrides(overrides)
combined = identity_override();
for index = 1:numel(overrides)
    combined.mass_scale = combined.mass_scale*overrides(index).mass_scale;
    combined.lc1_scale = combined.lc1_scale*overrides(index).lc1_scale;
    combined.lc2_scale = combined.lc2_scale*overrides(index).lc2_scale;
    combined.K_scale = combined.K_scale*overrides(index).K_scale;
    combined.q_rest_offset_rad = combined.q_rest_offset_rad+ ...
        overrides(index).q_rest_offset_rad;
    combined.sc_scale = combined.sc_scale*overrides(index).sc_scale;
end
end


function row = empty_row()
row = struct('layer', "", 'case_id', "", 'family', "", ...
    'perturbation', "", 'source_case_ids', "", 'posture_name', "", ...
    'q1_deg', NaN, 'q2_deg', NaN, 'F_parallel_N', NaN, ...
    'F_perp_N', NaN, 'force_norm_2_N', NaN, ...
    'force_norm_inf_N', NaN, 'force_margin_N', NaN, ...
    'delta_margin_N', NaN, 'torque_residual_norm_Nm', NaN, ...
    'sigma_min', NaN, 'condition_number', NaN, ...
    'feasible_200N', false, 'margin_ge_10N', false, ...
    'margin_ge_5N', false, 'margin_positive_below_5N', false, ...
    'margin_nonpositive', false, 'mass_scale', NaN, ...
    'lc1_scale', NaN, 'lc2_scale', NaN, 'K_scale', NaN, ...
    'q_rest1_offset_deg', NaN, 'q_rest2_offset_deg', NaN, ...
    'sc_scale', NaN);
end


function choice = empty_choice()
choice = struct('family', "", 'case_id', "", ...
    'margin_at_primary_N', NaN, 'override', identity_override());
end


function item = empty_combined()
item = struct('case_id', "", 'perturbation', "", ...
    'source_case_ids', "", 'override', identity_override());
end


function override = identity_override()
override = struct('mass_scale', 1, 'lc1_scale', 1, 'lc2_scale', 1, ...
    'K_scale', 1, 'q_rest_offset_rad', zeros(2, 1), 'sc_scale', 1);
end
