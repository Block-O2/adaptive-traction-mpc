function reference = dynamic_robust_v1_return_reference( ...
        mode, transition_q, recontact_path_q, nominal, progress, ...
        elapsed, duration)
%DYNAMIC_ROBUST_V1_RETURN_REFERENCE Contact-preserving return references.
%
% RECONTACT and LOAD_RETURN hold the physically established contact pose.
% Once load return is complete, BED_SUPPORTED_RETURN follows the moving
% nominal path while smoothly removing only the contact-posture offset.

mode=string(mode);
if mode=="RECONTACT" || mode=="LOAD_RETURN"
    reference=struct('q',transition_q,'dq',zeros(2,1), ...
        'ddq',zeros(2,1));
elseif mode=="BED_SUPPORTED_RETURN"
    reference=dynamic_robust_v1_moving_blend_reference( ...
        transition_q,recontact_path_q,nominal,progress,elapsed,duration);
else
    error('DynamicRobustV1:InvalidReturnMode', ...
        'Unsupported return-reference mode: %s',mode);
end
end
