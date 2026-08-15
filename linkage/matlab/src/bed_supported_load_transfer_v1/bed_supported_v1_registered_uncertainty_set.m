function uncertainty = bed_supported_v1_registered_uncertainty_set(nominal)
%BED_SUPPORTED_V1_REGISTERED_UNCERTAINTY_SET Reuse registered stress cases.

sensitivity_config = bed_supported_v1_force_margin_sensitivity_config();
sensitivity = bed_supported_v1_robust_force_margin_sensitivity( ...
    nominal, sensitivity_config);
oat = sensitivity_config.one_at_a_time_cases;
combined = sensitivity.combined_cases;
count = numel(oat)+numel(combined);
case_ids = strings(count, 1);
layers = strings(count, 1);
parameters = cell(count, 1);
overrides = cell(count, 1);
index = 0;
for case_index = 1:numel(oat)
    index = index+1;
    case_ids(index) = oat(case_index).case_id;
    layers(index) = "one_at_a_time";
    overrides{index} = oat(case_index).override;
    parameters{index} = bed_supported_v1_parameter_override( ...
        nominal, oat(case_index).override);
end
for case_index = 1:numel(combined)
    index = index+1;
    case_ids(index) = combined(case_index).case_id;
    layers(index) = "combined";
    overrides{index} = combined(case_index).override;
    parameters{index} = bed_supported_v1_parameter_override( ...
        nominal, combined(case_index).override);
end
uncertainty = struct('case_ids', case_ids, 'layers', layers, ...
    'parameters', {parameters}, 'overrides', {overrides}, ...
    'sensitivity_config', sensitivity_config, ...
    'combined_cases', combined, ...
    'low_adverse_choices', sensitivity.low_adverse_choices, ...
    'full_adverse_choices', sensitivity.full_adverse_choices);
end
