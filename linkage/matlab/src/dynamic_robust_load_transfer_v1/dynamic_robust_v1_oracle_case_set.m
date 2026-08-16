function cases = dynamic_robust_v1_oracle_case_set(nominal)
%DYNAMIC_ROBUST_V1_ORACLE_CASE_SET Fixed R2A diagnostic model mapping.
%
% This builder is intentionally outside runtime controller and supervisor
% logic. It constructs one formal case at the runner boundary, where the
% oracle intervention is explicit and auditable.

human_two_link_v2_validate_parameters(nominal);
uncertainty = bed_supported_v1_registered_uncertainty_set(nominal);
names = ["nominal","oracle_mild","oracle_moderate","oracle_adverse"];
plants = cell(1,4); plants{1} = nominal;
for index = 1:3
    plants{index+1} = bed_supported_v1_parameter_override( ...
        nominal, uncertainty.combined_cases(index).override);
end
template = struct('case_name',"",'plant_parameters',struct(), ...
    'controller_model_parameters',struct(),'oracle_diagnostic',true, ...
    'oracle_mismatch_norm',NaN,'nominal_model_mismatch_norm',NaN);
cases = repmat(template,1,4);
nominal_vector = dynamic_robust_v1_parameter_vector(nominal);
for index = 1:4
    plant = plants{index};
    controller_model = plant;
    plant_vector = dynamic_robust_v1_parameter_vector(plant);
    model_vector = dynamic_robust_v1_parameter_vector(controller_model);
    cases(index).case_name = names(index);
    cases(index).plant_parameters = plant;
    cases(index).controller_model_parameters = controller_model;
    cases(index).oracle_mismatch_norm = norm(plant_vector-model_vector);
    cases(index).nominal_model_mismatch_norm = ...
        norm(plant_vector-nominal_vector);
end
end
