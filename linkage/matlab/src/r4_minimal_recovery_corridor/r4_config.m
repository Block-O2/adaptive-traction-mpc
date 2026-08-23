function config = r4_config()
%R4_CONFIG Approved offline R4 recovery-corridor study contract.

config.posture_caps_deg = [10,12,15,20,25,30];
config.backward_progress = [0,0.01,0.02,0.05,0.10,0.15,0.20];
config.coarse_posture_step_deg = 1.0;
config.refined_posture_step_deg = 0.5;
config.convergence_posture_step_deg = 0.25;
config.refined_progress_step = 0.005;
config.coarse_progress_step = 0.01;
config.primary_recovery_rate_deg_s = 20;
config.recovery_rate_sensitivity_deg_s = [10,20];
config.initial_connection_radius_deg = 1.5;
config.local_edge_radius_deg = 1.5;
config.force_bound_N = 200;
config.family_labels = ["A_POSTURE_ONLY","B_BACKWARD_ONLY", ...
    "C_COMBINED"];
config.support_modes = ["bed_assisted","robot_only"];
config.model_kinds = ["true","perceived"];
config.classifications = ["NO_RECOVERY_POINT_FOUND", ...
    "FEASIBLE_POINT_DISCONNECTED", ...
    "CONTINUOUS_RECOVERY_CORRIDOR_EXISTS"];
config.formal_closed_loop_rerun = false;
config.engineering_diagnostic_not_clinical = true;
end
