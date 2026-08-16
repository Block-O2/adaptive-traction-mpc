function window = r3a_reconstruct_identifier_window(result,end_index)
%R3A_RECONSTRUCT_IDENTIFIER_WINDOW Rebuild one recorded R2B NLS window.

if ~result.adaptive_enabled || ~result.identifier_update_attempted(end_index)
    error('R3A:NotIdentifierAttempt','end_index is not an R2B solve attempt.');
end
count=result.adaptive_config.window_size;
source_indices=(end_index-count):(end_index-1);
if source_indices(1)<1
    error('R3A:IncompleteWindow','The recorded solve has no full source window.');
end
window=struct();
window.x=result.state(:,source_indices);
window.u=result.robot_force_N(:,source_indices);
window.x_next=result.state(:,source_indices+1);
window.sample_index=source_indices+1;
window.source_index=source_indices;
window.total_transitions=count;
window.theta_model=result.identifier_theta_model(:,max(1,end_index-1));
window.hybrid_mode=result.mode(source_indices);
window.takeover_mode=result.takeover_mode(source_indices);
window.start_time_s=result.t(source_indices(1));
window.end_time_s=result.t(end_index);
end
