function parameters = r4_model_parameters(anchor, model_kind)
%R4_MODEL_PARAMETERS Explicit true/perceived model selection.

switch string(model_kind)
    case "true"
        parameters = anchor.plant_parameters;
    case "perceived"
        parameters = anchor.controller_parameters;
    otherwise
        error('R4:InvalidModelKind','model_kind must be true or perceived.');
end
end
