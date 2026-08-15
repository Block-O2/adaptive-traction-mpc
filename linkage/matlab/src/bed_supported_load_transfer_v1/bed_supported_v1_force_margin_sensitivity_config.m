function config = bed_supported_v1_force_margin_sensitivity_config()
%BED_SUPPORTED_V1_FORCE_MARGIN_SENSITIVITY_CONFIG Registered diagnostic cases.

bed_config = bed_supported_v1_config(200, 10, "nominal");
config = struct();
config.analysis_name = "robust_force_margin_sensitivity";
config.force_bound_N = 200;
config.guard_N = bed_config.preposition_force_margin_N;
config.posture_names = ["current_7deg", "max_margin_5deg"];
config.postures_deg = [7, 5; 20, 20];
config.primary_posture_name = "current_7deg";
config.svd_relative_tolerance = bed_config.svd_relative_tolerance;
config.torque_residual_tolerance_Nm = 1e-10;

cases = repmat(empty_case(), 0, 1);
cases(end+1) = make_case("nominal", "nominal", "zero", 0, ...
    identity_override());

cases = append_scale_cases(cases, "mass", "mass_scale", ...
    [0.95, 1.05, 0.90, 1.10], [1, 1, 2, 2], ...
    ["-5%", "+5%", "-10%", "+10%"]);
cases = append_scale_cases(cases, "lc1", "lc1_scale", ...
    [0.95, 1.05, 0.90, 1.10], [1, 1, 2, 2], ...
    ["-5%", "+5%", "-10%", "+10%"]);
cases = append_scale_cases(cases, "lc2", "lc2_scale", ...
    [0.95, 1.05, 0.90, 1.10], [1, 1, 2, 2], ...
    ["-5%", "+5%", "-10%", "+10%"]);
cases = append_scale_cases(cases, "K", "K_scale", ...
    [0.90, 1.10, 0.80, 1.20], [1, 1, 2, 2], ...
    ["-10%", "+10%", "-20%", "+20%"]);

rest_specs = { ...
    "qrest1_minus2deg", "q_rest", "q_rest1 -2 deg", [-2;0]; ...
    "qrest1_plus2deg",  "q_rest", "q_rest1 +2 deg", [2;0]; ...
    "qrest2_minus2deg", "q_rest", "q_rest2 -2 deg", [0;-2]; ...
    "qrest2_plus2deg",  "q_rest", "q_rest2 +2 deg", [0;2]; ...
    "qrest_both_minus2deg", "q_rest", "both -2 deg", [-2;-2]; ...
    "qrest_both_plus2deg",  "q_rest", "both +2 deg", [2;2]};
for index = 1:size(rest_specs, 1)
    override = identity_override();
    override.q_rest_offset_rad = deg2rad(rest_specs{index, 4});
    cases(end+1) = make_case(rest_specs{index, 1}, ...
        rest_specs{index, 2}, rest_specs{index, 3}, 2, override); %#ok<AGROW>
end

cases = append_scale_cases(cases, "sc", "sc_scale", ...
    [0.98, 1.02, 0.95, 1.05], [1, 1, 2, 2], ...
    ["-2%", "+2%", "-5%", "+5%"]);
config.one_at_a_time_cases = cases;
config.combined_family_order = ["mass", "lc1", "lc2", ...
    "K", "q_rest", "sc"];
config.mild_family_count = 2;
config.combined_case_names = ["mild", "moderate", "adverse"];
end


function cases = append_scale_cases(cases, family, field, values, tiers, labels)
for index = 1:numel(values)
    override = identity_override();
    override.(field) = values(index);
    case_id = sprintf('%s_%s', lower(family), ...
        replace(replace(labels(index), "%", "pct"), "+", "plus"));
    case_id = replace(case_id, "-", "minus");
    cases(end+1) = make_case(case_id, family, labels(index), ...
        tiers(index), override); %#ok<AGROW>
end
end


function item = make_case(case_id, family, perturbation, tier, override)
item = empty_case();
item.case_id = string(case_id);
item.family = string(family);
item.perturbation = string(perturbation);
item.tier = tier;
item.override = override;
end


function item = empty_case()
item = struct('case_id', "", 'family', "", 'perturbation', "", ...
    'tier', 0, 'override', identity_override());
end


function override = identity_override()
override = struct('mass_scale', 1, 'lc1_scale', 1, 'lc2_scale', 1, ...
    'K_scale', 1, 'q_rest_offset_rad', zeros(2, 1), 'sc_scale', 1);
end
