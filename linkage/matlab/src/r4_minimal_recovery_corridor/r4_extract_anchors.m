function anchors = r4_extract_anchors(paths)
%R4_EXTRACT_ANCHORS Extract intervention/HOLD/terminal states read-only.

oracle = load(paths.stage1_oracle,'results');
adaptive = load(paths.stage2_adaptive,'results');
sources = {oracle.results{2},adaptive.results{3},adaptive.results{4}};
case_names = ["moderate_oracle","moderate_adaptive", ...
    "adverse_adaptive"];
source_names = ["stage1_oracle","stage2_adaptive", ...
    "stage2_adaptive"];
source_indices = [2,3,4];
roles = ["first_intervention","first_hold","terminal_stop"];
anchors = repmat(empty_anchor(),0,1);
for case_index = 1:numel(sources)
    result = sources{case_index};
    indices = [find(string(result.safety_state) ~= "NORMAL",1), ...
        find(string(result.safety_state) == "HOLD",1),numel(result.t)];
    if numel(indices) ~= 3 || any(~isfinite(indices))
        error('R4:MissingAnchor','All three requested R4 anchors must exist.');
    end
    for role_index = 1:3
        k = indices(role_index);
        item = empty_anchor();
        item.anchor_id = case_names(case_index)+"__"+roles(role_index);
        item.case_name = case_names(case_index);
        item.role = roles(role_index);
        item.primary = roles(role_index) ~= "first_hold";
        item.source_name = source_names(case_index);
        item.source_result_index = source_indices(case_index);
        item.sample_index = k;
        item.time_s = result.t(k);
        item.task_s = result.task_s(k);
        item.q_rad = result.state(1:2,k);
        item.dq_rad_s = result.state(3:4,k);
        item.q_ref_rad = result.q_ref(:,k);
        item.u_previous_N = result.robot_force_N(:,k);
        item.bed_force_N = result.bed_force_N(k);
        item.active_contacts = result.active_contacts(k);
        item.safety_state = string(result.safety_state(k));
        item.safety_reason = string(result.safety_reason(k));
        item.h_hip_m = result.h_hip_m;
        item.config = result.config;
        item.nominal_parameters = result.nominal_parameters;
        item.plant_parameters = result.plant_parameters;
        if result.adaptive_enabled
            theta = result.identifier_theta_model(:,k);
            item.controller_parameters = ...
                dynamic_robust_v1_adaptive_apply_theta( ...
                result.nominal_parameters,theta);
            item.theta_model = theta;
        else
            item.controller_parameters = result.controller_model_parameters;
            item.theta_model = dynamic_robust_v1_adaptive_theta_from_parameters( ...
                result.nominal_parameters,item.controller_parameters);
        end
        anchors(end+1,1) = item; %#ok<AGROW>
    end
end
end

function item = empty_anchor()
item = struct('anchor_id',"",'case_name',"",'role',"", ...
    'primary',false,'source_name',"",'source_result_index',NaN, ...
    'sample_index',NaN,'time_s',NaN,'task_s',NaN,'q_rad',nan(2,1), ...
    'dq_rad_s',nan(2,1),'q_ref_rad',nan(2,1), ...
    'u_previous_N',nan(2,1),'bed_force_N',NaN,'active_contacts',NaN, ...
    'safety_state',"",'safety_reason',"",'h_hip_m',NaN, ...
    'config',struct(),'nominal_parameters',struct(), ...
    'plant_parameters',struct(),'controller_parameters',struct(), ...
    'theta_model',nan(7,1));
end
