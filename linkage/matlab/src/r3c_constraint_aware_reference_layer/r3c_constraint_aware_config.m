function config=r3c_constraint_aware_config(config,nominal,warning_fraction)
%R3C_CONSTRAINT_AWARE_CONFIG Engineering buffers from existing soft zone.

if nargin<1 || isempty(config),config=dynamic_robust_v1_config();end
if nargin<2 || isempty(nominal)
    nominal=human_two_link_v2_parameters(1.72,75);
end
if nargin<3 || isempty(warning_fraction),warning_fraction=.20;end
validateattributes(warning_fraction,{'numeric'}, ...
    {'scalar','real','finite','positive','<',.5});
soft_width=min(nominal.soft_limit_margin);
config.r3c_enabled=true;
config.r3c_warning_buffer_rad=warning_fraction*soft_width;
config.r3c_hold_buffer_rad=.5*config.r3c_warning_buffer_rad;
config.r3c_resume_buffer_rad=1.5*config.r3c_warning_buffer_rad;
config.r3c_prediction_horizon_s=10*config.supervisor_period_s;
config.r3c_hold_before_recovery_s=config.supervisor_period_s;
config.r3c_recovery_timeout_s=config.takeover_recovery_timeout_s;
config.r3c_recovery_reference_rate_rad_s= ...
    deg2rad(config.tube_cap_deg)/config.transfer_ready_duration_s;
config.r3c_candidate_step_rad=deg2rad(1);
config.r3c_reference_soft_clearance_rad=config.soft_margin_tolerance_rad;
config.r3c_engineering_buffer_not_clinical=true;
config.r3c_formal_safety_guarantee=false;
end
