function config = r3b_recontact_margin_config(config, reserve_N)
%R3B_RECONTACT_MARGIN_CONFIG Explicit engineering recontact reserve.

if nargin<1 || isempty(config),config=dynamic_robust_v1_config();end
if nargin<2 || isempty(reserve_N),reserve_N=1.0;end
validateattributes(reserve_N,{'numeric'},{'scalar','real','finite','positive'});
config.r3b_recontact_enabled=true;
config.r3b_contact_reserve_N=reserve_N;
config.r3b_contact_target_N=config.contact_force_threshold_N+reserve_N;
config.r3b_target_tolerance_N=0.05;
config.r3b_gap_velocity_tolerance_m_s=1e-3;
config.r3b_reference_rate_rad_s=deg2rad(0.5);
config.r3b_gradient_step_rad=deg2rad(0.05);
config.r3b_gradient_regularization_N2_rad2=0.1^2;
config.r3b_max_penetration_m=0.005;
config.r3b_max_bed_force_N=config.r3b_contact_target_N+5.0;
config.r3b_engineering_reserve_not_clinical=true;
end
