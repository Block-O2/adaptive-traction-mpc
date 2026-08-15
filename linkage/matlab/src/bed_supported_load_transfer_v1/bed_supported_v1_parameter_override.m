function perturbed = bed_supported_v1_parameter_override(nominal, override)
%BED_SUPPORTED_V1_PARAMETER_OVERRIDE Validated sensitivity-only parameters.
%
% The nominal Human Model V2 constructor remains unchanged. This interface
% applies explicit engineering sensitivity factors to a copy and validates
% the resulting parameter struct before it is used by the retained dynamics,
% passive-torque, and force-map functions.

human_two_link_v2_validate_parameters(nominal);
required = {'mass_scale', 'lc1_scale', 'lc2_scale', 'K_scale', ...
    'q_rest_offset_rad', 'sc_scale'};
if ~isstruct(override) || ~isscalar(override) || ...
        ~isempty(setxor(fieldnames(override), required(:)))
    error('BedSupportedV1:InvalidParameterOverride', ...
        'Override must contain exactly the registered sensitivity fields.');
end
scales = [override.mass_scale, override.lc1_scale, ...
    override.lc2_scale, override.K_scale, override.sc_scale];
if any(~isfinite(scales)) || any(scales <= 0) || ...
        numel(override.q_rest_offset_rad) ~= 2 || ...
        any(~isfinite(override.q_rest_offset_rad))
    error('BedSupportedV1:InvalidParameterOverride', ...
        'Sensitivity scales must be positive and rest offsets finite.');
end

perturbed = nominal;
perturbed.body_mass_kg = nominal.body_mass_kg*override.mass_scale;
perturbed.m1 = nominal.m1*override.mass_scale;
perturbed.m2 = nominal.m2*override.mass_scale;
perturbed.I1 = nominal.I1*override.mass_scale;
perturbed.I2 = nominal.I2*override.mass_scale;
perturbed.lc1 = nominal.lc1*override.lc1_scale;
perturbed.lc2 = nominal.lc2*override.lc2_scale;
perturbed.K_passive = nominal.K_passive*override.K_scale;
perturbed.q_rest = nominal.q_rest+override.q_rest_offset_rad(:);
perturbed.sc = nominal.sc*override.sc_scale;
human_two_link_v2_validate_parameters(perturbed);
end
