function config = bed_supported_v1_config(force_bound_N, tube_cap_deg, stiffness_case)
%BED_SUPPORTED_V1_CONFIG Fixed engineering abstraction and hybrid settings.

if nargin < 3, stiffness_case = "nominal"; end
config = hybrid_tube_v1_config(force_bound_N, tube_cap_deg);
config.case_name = sprintf('bed_%s_tube_%gdeg_%gN', ...
    stiffness_case, tube_cap_deg, force_bound_N);
config.stiffness_case = string(stiffness_case);
switch config.stiffness_case
    case "softer"
        config.k_bed_N_m = 1500;
        config.c_bed_Ns_m = 35;
    case "nominal"
        config.k_bed_N_m = 3000;
        config.c_bed_Ns_m = 55;
    case "stiffer"
        config.k_bed_N_m = 6000;
        config.c_bed_Ns_m = 80;
    otherwise
        error('BedSupportedV1:InvalidStiffnessCase', ...
            'stiffness_case must be softer, nominal, or stiffer.');
end
config.bed_enabled = true;
config.bed_plane_y_m = 0;
config.thigh_support_fractions = [0.2, 0.4, 0.6, 0.8];
config.shank_support_fractions = [0.2, 0.4, 0.6, 0.8];
config.thigh_surface_offset_m = 0.10;
config.shank_surface_offset_m = 0.075;
config.calibration_h_range_m = [0.04, 0.16];
config.calibration_samples = 2401;
config.calibration_max_penetration_m = 0.03;
config.contact_force_threshold_N = 2.0;
config.contact_stable_duration_s = 0.50;
config.preposition_duration_s = 3.0;
config.preposition_timeout_s = 6.0;
config.preposition_feasible_hold_s = 0.30;
config.preposition_position_tolerance_rad = deg2rad(0.25);
config.preposition_force_margin_N = 5.0;
config.preposition_soft_clearance_rad = deg2rad(0.5);
config.load_takeover_duration_s = 3.0;
config.liftoff_timeout_s = 8.0;
config.recontact_progress_threshold = 0.70;
config.load_return_duration_s = 2.0;
config.release_duration_s = 2.0;
config.force_jump_tolerance_N = max(config.du_max)*config.dt+1e-9;
config.max_time_s = 55;
end
